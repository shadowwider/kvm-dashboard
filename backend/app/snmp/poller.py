"""
SNMP 多设备并行轮询器 (生产级)。
  - 限流并发 (Semaphore): 同时最多 N 台设备
  - SnmpEngine 复用池: 避免每次 GET/WALK 都创建新引擎
  - 批量 INSERT: 一次性写入所有 metrics
  - 告警去重: 10 分钟内同设备同指标不重复告警
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity,
    getCmd, bulkCmd,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.status_metric import StatusMetric
from app.models.alert import Alert
from app.snmp.parser import parse_snmp_value, is_alert_triggered
from app.websocket.hub import ws_manager

logger = logging.getLogger(__name__)

# ─── 配置 ─────────────────────────────────────────────────────────
CONCURRENCY_LIMIT = 20      # 同时最多轮询 N 台设备
SNMP_TIMEOUT = 3             # SNMP 请求超时 (秒)
SNMP_RETRIES = 1             # 超时重试次数
BULK_MAX_REPETITIONS = 25    # GETBULK 每批返回行数
WALK_MAX_ITERATIONS = 100    # WALK 防止无限循环
ALERT_DEDUP_MINUTES = 10     # 告警去重窗口 (分钟)
BATCH_INSERT_SIZE = 5000     # 每批 INSERT 行数

# ─── SnmpEngine 池 ────────────────────────────────────────────────
_engine_pool: list[SnmpEngine] = []
_engine_lock = asyncio.Lock()


async def _get_engine() -> SnmpEngine:
    async with _engine_lock:
        if _engine_pool:
            return _engine_pool.pop()
    return SnmpEngine()


def _discard_engine(eng: SnmpEngine):
    """安全销毁一个不可用的引擎"""
    try:
        eng.transportDispatcher.closeDispatcher()
    except Exception:
        pass


async def _return_engine(eng: SnmpEngine, discard: bool = False):
    """将引擎放回池中。如果 discard=True（连接失败），则销毁该引擎而非复用。"""
    if discard:
        _discard_engine(eng)
        return
    async with _engine_lock:
        if len(_engine_pool) < CONCURRENCY_LIMIT:
            _engine_pool.append(eng)
        else:
            _discard_engine(eng)


async def _snmp_get(host: str, port: int, community: str, oid: str) -> tuple[str, any]:
    """单个 OID GET 查询，返回 (oid, raw_value)"""
    engine = await _get_engine()
    failed = False
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=SNMP_TIMEOUT, retries=SNMP_RETRIES),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )
        if error_indication:
            # 超时或网络错误 → 引擎可能已被污染
            failed = True
            return oid, None
        if error_status:
            return oid, None
        if var_binds:
            return oid, var_binds[0][1]
        return oid, None
    except Exception as e:
        failed = True
        logger.warning(f"SNMP GET {host}:{oid} 失败: {e}")
        return oid, None
    finally:
        await _return_engine(engine, discard=failed)


async def _snmp_walk(host: str, port: int, community: str, base_oid: str) -> dict[str, any]:
    """SNMP WALK via pysnmp v6 bulkCmd (SnmpEngine 复用)"""
    engine = await _get_engine()
    results = {}
    next_oid = base_oid
    base_tuple = tuple(int(x) for x in base_oid.lstrip(".").split("."))
    failed = False
    try:
        for iteration in range(WALK_MAX_ITERATIONS):
            error_indication, error_status, error_index, var_bind_table = await bulkCmd(
                engine,
                CommunityData(community, mpModel=1),
                UdpTransportTarget((host, port), timeout=SNMP_TIMEOUT + 2, retries=SNMP_RETRIES),
                ContextData(),
                0, BULK_MAX_REPETITIONS,
                ObjectType(ObjectIdentity(next_oid)),
            )
            if error_indication:
                failed = True
                break
            if error_status or not var_bind_table:
                break

            flat_binds = []
            for item in var_bind_table:
                if isinstance(item, list):
                    flat_binds.extend(item)
                else:
                    flat_binds.append(item)

            out_of_scope = False
            for obj_type in flat_binds:
                oid_identity = obj_type[0]
                value = obj_type[1]

                if hasattr(oid_identity, 'getOid'):
                    oid_name = oid_identity.getOid()
                    oid_tuple = tuple(int(x) for x in oid_name)
                else:
                    oid_tuple = tuple(int(x) for x in oid_identity)
                oid_str = ".".join(str(x) for x in oid_tuple)

                from pysnmp.proto.rfc1905 import EndOfMibView
                if hasattr(value, 'tagSet') and value.tagSet == EndOfMibView.tagSet:
                    out_of_scope = True
                    break

                if len(oid_tuple) <= len(base_tuple) or oid_tuple[:len(base_tuple)] != base_tuple:
                    out_of_scope = True
                    break

                results[oid_str] = value
                next_oid = oid_str

            if out_of_scope:
                break
    except Exception as e:
        failed = True
        logger.warning(f"SNMP WALK {host}:{base_oid} failed: {e}")
    finally:
        await _return_engine(engine, discard=failed)
    logger.debug(f"WALK {base_oid}: {len(results)} results")
    return results


async def poll_device(device: Device, oid_configs: list[OIDRegistry]):
    """轮询单台设备，写入时序数据并检测告警"""
    logger.info(f"开始轮询设备: {device.id} ({device.host})")
    now = datetime.now(timezone.utc)

    device_oids = [o for o in oid_configs if o.category == "device" and o.poll_enabled and not o.is_table]
    table_oid_configs = [o for o in oid_configs if o.poll_enabled and o.is_table]

    metrics_to_insert: list[dict] = []
    alerts_to_create: list[dict] = []

    # ── 读取 sysObjectID ──────────────────────────────────────────
    SYS_OBJECT_ID_OID = "1.3.6.1.2.1.1.2.0"
    sys_oid = "1.3.6.1.4.1.32828.3.257.16"  # 默认 GUD-CCDC
    try:
        _, raw_sys_oid = await _snmp_get(device.host, device.port, device.community, SYS_OBJECT_ID_OID)
        if raw_sys_oid:
            if hasattr(raw_sys_oid, 'asTuple'):
                sys_oid_str = ".".join(str(x) for x in raw_sys_oid.asTuple())
            else:
                sys_oid_str = str(raw_sys_oid).lstrip(".")
            if "32828" in sys_oid_str:
                sys_oid = sys_oid_str
        else:
            # sysObjectID 获取失败，判定为离线，提前结束以免后续所有 OID 全部卡超时
            logger.warning(f"设备 {device.id} (IP: {device.host}) 连接超时，判定离线，跳过深度轮询。")
            async with AsyncSessionLocal() as db:
                await db.execute(update(Device).where(Device.id == device.id).values(last_poll=now, last_status="offline"))
                await db.commit()
            await ws_manager.broadcast({
                "type": "device_update",
                "device_id": device.id,
                "online_status": "offline",
                "status": {},
                "timestamp": now.isoformat(),
            })
            return
    except Exception as e:
        logger.warning(f"获取 {device.id} sysObjectID 失败: {e}")

    # ── 设备级 OID 并行 GET ─────────────────────────────────────
    device_status_summary = {}
    tasks = []
    for o in device_oids:
        real_oid = o.oid.replace("{sys_oid}", sys_oid)
        tasks.append(_snmp_get(device.host, device.port, device.community, real_oid))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for oid_cfg, result in zip(device_oids, results):
        if isinstance(result, Exception):
            continue
        _, raw_value = result
        value_str, value_num = parse_snmp_value(raw_value, oid_cfg.data_type, oid_cfg.enum_map)
        device_status_summary[oid_cfg.name] = value_str

        if getattr(oid_cfg, 'archive_enabled', True):
            metrics_to_insert.append({
                "time": now, "device_id": device.id, "endpoint_id": None,
                "oid_name": oid_cfg.name, "value_str": value_str, "value_num": value_num,
            })

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

    # ── 轮询表类型 OID（终端模块 + 端口）─────────────────────────
    if table_oid_configs:
        endpoint_data: dict[int, dict[str, tuple]] = {}

        walk_tasks = []
        for ep_cfg in table_oid_configs:
            col_oid = f"{ep_cfg.table_base_oid}.{ep_cfg.table_column}"
            col_oid = col_oid.replace("{sys_oid}", sys_oid)
            walk_tasks.append(_snmp_walk(device.host, device.port, device.community, col_oid))

        walk_results_list = await asyncio.gather(*walk_tasks, return_exceptions=True)

        for ep_cfg, walk_results in zip(table_oid_configs, walk_results_list):
            if isinstance(walk_results, Exception) or not isinstance(walk_results, dict):
                continue

            for full_oid, raw_value in walk_results.items():
                try:
                    row_index = int(full_oid.split(".")[-1])
                except ValueError:
                    continue

                value_str, value_num = parse_snmp_value(raw_value, ep_cfg.data_type, ep_cfg.enum_map)

                if row_index not in endpoint_data:
                    endpoint_data[row_index] = {}
                endpoint_data[row_index][ep_cfg.name] = (value_str, value_num, ep_cfg)

        # 写入/更新终端
        async with AsyncSessionLocal() as db:
            for row_index, field_map in endpoint_data.items():
                ep_id = f"{device.id}_{row_index}"
                ep_status_summary = {k: v[0] for k, v in field_map.items()}

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
                        index=row_index, last_status=ep_status_summary,
                        updated_at=now, created_at=now,
                    ))

                for oid_name, (value_str, value_num, ep_cfg) in field_map.items():
                    if getattr(ep_cfg, 'archive_enabled', True):
                        metrics_to_insert.append({
                            "time": now, "device_id": device.id, "endpoint_id": ep_id,
                            "oid_name": oid_name, "value_str": value_str, "value_num": value_num,
                        })
                    if ep_cfg.alert_enabled and is_alert_triggered(
                        value_str, value_num,
                        alert_gt=ep_cfg.alert_gt, alert_lt=ep_cfg.alert_lt,
                        alert_eq_str=ep_cfg.alert_eq_str, alert_ne_str=ep_cfg.alert_ne_str,
                    ):
                        ep_name_display = ep_status_summary.get("ep_name", ep_id)
                        alerts_to_create.append({
                            "device_id": device.id, "endpoint_id": ep_id, "oid_name": oid_name,
                            "alert_type": "threshold", "severity": ep_cfg.alert_severity,
                            "message": f"{device.name}/{ep_name_display} {ep_cfg.display_name} 异常: {value_str}",
                            "raw_value": str(value_str),
                        })
            await db.commit()

    # ── 批量写入 metrics + 告警去重 ──────────────────────────────
    async with AsyncSessionLocal() as db:
        # 批量 INSERT metrics
        if metrics_to_insert:
            for i in range(0, len(metrics_to_insert), BATCH_INSERT_SIZE):
                batch = metrics_to_insert[i:i + BATCH_INSERT_SIZE]
                await db.execute(insert(StatusMetric.__table__), batch)

        # 更新设备状态
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

        # 告警去重：同设备同指标 10 分钟内不重复
        dedup_cutoff = now - timedelta(minutes=ALERT_DEDUP_MINUTES)
        for a in alerts_to_create:
            existing_alert = await db.execute(
                select(Alert).where(
                    Alert.device_id == a["device_id"],
                    Alert.oid_name == a["oid_name"],
                    Alert.is_resolved == False,
                    Alert.created_at >= dedup_cutoff,
                ).limit(1)
            )
            if existing_alert.scalar_one_or_none():
                continue  # 已有未处理告警，跳过
            db.add(Alert(created_at=now, **a))

        await db.commit()

    # ── WebSocket 广播 ──────────────────────────────────────────
    await ws_manager.broadcast({
        "type": "device_update",
        "device_id": device.id,
        "online_status": device_online_status,
        "status": device_status_summary,
        "timestamp": now.isoformat(),
    })
    if alerts_to_create:
        await ws_manager.broadcast({
            "type": "new_alerts",
            "alerts": alerts_to_create,
            "timestamp": now.isoformat(),
        })

    logger.info(f"设备 {device.id} 轮询完成，写入 {len(metrics_to_insert)} 条指标，{len(alerts_to_create)} 条待去重告警")


async def run_poll_cycle():
    """轮询主循环：限流并发，分批轮询所有活跃设备"""
    async with AsyncSessionLocal() as db:
        devices_result = await db.execute(select(Device).where(Device.is_active == True))
        devices = devices_result.scalars().all()

        oids_result = await db.execute(select(OIDRegistry).where(OIDRegistry.poll_enabled == True))
        oid_configs = oids_result.scalars().all()

    if not devices:
        logger.debug("没有活跃设备，跳过轮询")
        return

    logger.info(f"开始轮询周期: {len(devices)} 台设备, 并发上限 {CONCURRENCY_LIMIT}")
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def limited_poll(device):
        async with semaphore:
            try:
                await poll_device(device, oid_configs)
            except Exception as e:
                logger.error(f"设备 {device.id} 轮询异常: {e}", exc_info=True)

    await asyncio.gather(*[limited_poll(d) for d in devices], return_exceptions=True)
    logger.info(f"轮询周期完成: {len(devices)} 台设备")
