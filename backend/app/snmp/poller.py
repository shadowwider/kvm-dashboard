"""
SNMP 多设备并行轮询器。
从数据库动态读取：
  1. 所有活跃设备列表
  2. 所有启用的 OID 配置（oid_registry）
动态构建 SNMP 查询，将结果写入 status_metrics，并触发告警检测。
"""
import asyncio
import logging
from datetime import datetime, timezone
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity,
    getCmd, bulkCmd,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.status_metric import StatusMetric
from app.models.alert import Alert
from app.snmp.parser import parse_snmp_value, is_alert_triggered
from app.websocket.hub import ws_manager

logger = logging.getLogger(__name__)


async def _snmp_get(host: str, port: int, community: str, oid: str) -> tuple[str, any]:
    """单个 OID GET 查询，返回 (oid, raw_value)"""
    engine = SnmpEngine()
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),  # mpModel=1 → SNMPv2c
            UdpTransportTarget((host, port), timeout=3, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error_indication or error_status:
            return oid, None
        if var_binds:
            return oid, var_binds[0][1]
        return oid, None
    except Exception as e:
        logger.warning(f"SNMP GET {host}:{oid} 失败: {e}")
        return oid, None
    finally:
        engine.transportDispatcher.closeDispatcher()


async def _snmp_walk(host: str, port: int, community: str, base_oid: str) -> dict[str, any]:
    """SNMP WALK 查询（用于终端模块表），返回 {full_oid: raw_value}"""
    engine = SnmpEngine()
    results = {}
    try:
        async for error_indication, error_status, _, var_bind_table in bulkCmd(
            engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=5, retries=1),
            ContextData(),
            0, 50,  # nonRepeaters=0, maxRepetitions=50
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if error_indication or error_status:
                break
            for var_bind in var_bind_table:
                oid_str = str(var_bind[0])
                if not oid_str.startswith(base_oid):
                    return results
                results[oid_str] = var_bind[1]
    except Exception as e:
        logger.warning(f"SNMP WALK {host}:{base_oid} 失败: {e}")
    finally:
        try:
            engine.transportDispatcher.closeDispatcher()
        except Exception:
            pass
    return results


async def poll_device(device: Device, oid_configs: list[OIDRegistry]):
    """轮询单台设备，写入时序数据并检测告警"""
    logger.info(f"开始轮询设备: {device.id} ({device.host})")
    now = datetime.now(timezone.utc)

    # 分离设备级 OID 和终端表 OID
    device_oids = [o for o in oid_configs if o.category == "device" and o.poll_enabled]
    endpoint_oid_configs = [o for o in oid_configs if o.category == "endpoint" and o.poll_enabled and o.is_table]

    metrics_to_insert: list[dict] = []
    alerts_to_create: list[dict] = []

    # ── 轮询设备级 OID ──────────────────────────────────────────────
    device_status_summary = {}
    tasks = [_snmp_get(device.host, device.port, device.community, o.oid) for o in device_oids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for oid_cfg, result in zip(device_oids, results):
        if isinstance(result, Exception):
            continue
        _, raw_value = result
        value_str, value_num = parse_snmp_value(raw_value, oid_cfg.data_type, oid_cfg.enum_map)
        device_status_summary[oid_cfg.name] = value_str

        metrics_to_insert.append({
            "time": now, "device_id": device.id, "endpoint_id": None,
            "oid_name": oid_cfg.name, "value_str": value_str, "value_num": value_num,
        })

        # 告警检测
        if oid_cfg.alert_enabled and is_alert_triggered(
            value_str, value_num,
            alert_gt=oid_cfg.alert_gt, alert_lt=oid_cfg.alert_lt,
            alert_eq_str=oid_cfg.alert_eq_str, alert_ne_str=oid_cfg.alert_ne_str,
        ):
            alerts_to_create.append({
                "device_id": device.id, "endpoint_id": None, "oid_name": oid_cfg.name,
                "alert_type": "threshold", "severity": oid_cfg.alert_severity,
                "message": f"{device.name} {oid_cfg.display_name} 异常: {value_str}",
                "raw_value": str(raw_value),
            })

    # ── 轮询终端模块表 ────────────────────────────────────────────────
    if endpoint_oid_configs:
        # 按列分组 WALK（同列一次 WALK 获取所有行）
        endpoint_data: dict[int, dict[str, tuple]] = {}  # {row_index: {oid_name: (value_str, value_num)}}

        for ep_cfg in endpoint_oid_configs:
            col_oid = f"{ep_cfg.table_base_oid}.{ep_cfg.table_column}"
            walk_results = await _snmp_walk(device.host, device.port, device.community, col_oid)

            for full_oid, raw_value in walk_results.items():
                # 从 OID 末尾提取行索引
                try:
                    row_index = int(full_oid.split(".")[-1])
                except ValueError:
                    continue

                value_str, value_num = parse_snmp_value(raw_value, ep_cfg.data_type, ep_cfg.enum_map)

                if row_index not in endpoint_data:
                    endpoint_data[row_index] = {}
                endpoint_data[row_index][ep_cfg.name] = (value_str, value_num, ep_cfg)

        # 写入终端数据
        async with AsyncSessionLocal() as db:
            for row_index, field_map in endpoint_data.items():
                ep_id = f"{device.id}_{row_index}"
                ep_status_summary = {k: v[0] for k, v in field_map.items()}

                # upsert endpoint
                existing = await db.get(Endpoint, ep_id)
                if existing:
                    existing.last_status = ep_status_summary
                    existing.updated_at = now
                    ep_name = ep_status_summary.get("ep_name") or existing.name
                    if ep_name:
                        existing.name = ep_name
                else:
                    ep_name = ep_status_summary.get("ep_name") or f"终端-{row_index}"
                    db.add(Endpoint(
                        id=ep_id, device_id=device.id, name=ep_name,
                        index=row_index, last_status=ep_status_summary, updated_at=now, created_at=now,
                    ))

                for oid_name, (value_str, value_num, ep_cfg) in field_map.items():
                    metrics_to_insert.append({
                        "time": now, "device_id": device.id, "endpoint_id": ep_id,
                        "oid_name": oid_name, "value_str": value_str, "value_num": value_num,
                    })
                    # 告警检测
                    if ep_cfg.alert_enabled and is_alert_triggered(
                        value_str, value_num,
                        alert_gt=ep_cfg.alert_gt, alert_lt=ep_cfg.alert_lt,
                        alert_eq_str=ep_cfg.alert_eq_str, alert_ne_str=ep_cfg.alert_ne_str,
                    ):
                        ep_name = ep_status_summary.get("ep_name", ep_id)
                        alerts_to_create.append({
                            "device_id": device.id, "endpoint_id": ep_id, "oid_name": oid_name,
                            "alert_type": "threshold", "severity": ep_cfg.alert_severity,
                            "message": f"{device.name}/{ep_name} {ep_cfg.display_name} 异常: {value_str}",
                            "raw_value": str(value_str),
                        })
            await db.commit()

    # ── 批量写入 status_metrics ────────────────────────────────────
    async with AsyncSessionLocal() as db:
        for m in metrics_to_insert:
            db.add(StatusMetric(**m))

        # 更新设备最后轮询时间和状态
        device_online_status = "online"
        if device_status_summary.get("main_power") not in (None, "on"):
            device_online_status = "warning"
        temp = None
        try:
            temp_str = device_status_summary.get("temperature")
            if temp_str:
                temp = float(temp_str.replace("°C", "").strip())
        except Exception:
            pass
        if temp and temp > 55:
            device_online_status = "warning"

        await db.execute(
            update(Device).where(Device.id == device.id).values(
                last_poll=now, last_status=device_online_status
            )
        )

        # 写入告警（跳过重复告警）
        for a in alerts_to_create:
            db.add(Alert(created_at=now, **a))

        await db.commit()

    # ── WebSocket 广播 ─────────────────────────────────────────────
    await ws_manager.broadcast({
        "type": "device_update",
        "device_id": device.id,
        "status": device_status_summary,
        "timestamp": now.isoformat(),
    })
    if alerts_to_create:
        await ws_manager.broadcast({
            "type": "new_alerts",
            "alerts": alerts_to_create,
            "timestamp": now.isoformat(),
        })

    logger.info(f"设备 {device.id} 轮询完成，写入 {len(metrics_to_insert)} 条指标，{len(alerts_to_create)} 条告警")


async def run_poll_cycle():
    """轮询主循环：读取所有活跃设备和 OID 配置，并行执行轮询"""
    async with AsyncSessionLocal() as db:
        devices_result = await db.execute(select(Device).where(Device.is_active == True))
        devices = devices_result.scalars().all()

        oids_result = await db.execute(select(OIDRegistry).where(OIDRegistry.poll_enabled == True))
        oid_configs = oids_result.scalars().all()

    if not devices:
        logger.debug("没有活跃设备，跳过轮询")
        return

    # 所有设备并行轮询
    await asyncio.gather(*[poll_device(d, oid_configs) for d in devices], return_exceptions=True)
