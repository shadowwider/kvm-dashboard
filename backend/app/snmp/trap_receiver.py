"""
SNMP Trap 接收器（UDP:162）。
接收 G&D KVM 设备发送的 Trap 通知（GUD-GENERALTRAPS-MIB），
解析 level/message varbind，写入告警表，广播前端，并将原始数据记录到文件。

G&D 通用 Trap 格式（GUD-GENERALTRAPS-MIB，由 GUD-SMI-MIB 推导）：
  OID 路径：
    gudEnterprise       = 1.3.6.1.4.1.32828
    gudTrap             = gudEnterprise.2   → 1.3.6.1.4.1.32828.2
    gudGeneralTrap      = gudTrap.1         → 1.3.6.1.4.1.32828.2.1
    gudGeneralNotifications = gudGeneralTrap.0 → 1.3.6.1.4.1.32828.2.1.0

  VarBinds:
    1.3.6.1.2.1.1.3.0          sysUpTime  (TimeTicks，固定标准字段)
    1.3.6.1.6.3.1.1.4.1.0      snmpTrapOID = 1.3.6.1.4.1.32828.2.1.0.4
    1.3.6.1.4.1.32828.2.1.0.2  level    Integer32 (0=Emergency..5=Notice)
    1.3.6.1.4.1.32828.2.1.0.3  message  DisplayString
"""
import asyncio
import logging
import logging.handlers
import os
import socket
import threading
from datetime import datetime, timezone

from pysnmp.hlapi.asyncio import SnmpEngine
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

from app.database import AsyncSessionLocal
from app.models.alert import Alert
from app.websocket.hub import ws_manager
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── 原始 Trap 数据专用日志（轮转，调试用）───────────────────
_raw_logger = logging.getLogger('snmp.trap.raw')
_raw_log_enabled: bool = settings.snmp_raw_log_enabled
_status_lock = threading.Lock()
_receiver_status: dict = {
    "state": "not_started",
    "listen_host": "0.0.0.0",
    "listen_port": settings.snmp_trap_port,
    "detail": None,
    "error_type": None,
    "started_at": None,
}


def _init_raw_logger():
    """初始化原始 Trap 专用 RotatingFileHandler（不影响主日志）"""
    log_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    )
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'trap_raw.log'),
        maxBytes=20 * 1024 * 1024,   # 20 MB per file
        backupCount=10,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
    _raw_logger.addHandler(handler)
    _raw_logger.setLevel(logging.DEBUG)
    _raw_logger.propagate = False  # 不冒泡到 root logger


if _raw_log_enabled:
    _init_raw_logger()


def _set_receiver_status(
    state: str,
    *,
    detail: str | None = None,
    error_type: str | None = None,
) -> None:
    with _status_lock:
        _receiver_status.update({
            "state": state,
            "listen_host": "0.0.0.0",
            "listen_port": settings.snmp_trap_port,
            "detail": detail,
            "error_type": error_type,
            "started_at": (
                datetime.now(timezone.utc).isoformat()
                if state == "running"
                else _receiver_status.get("started_at")
            ),
        })


def trap_receiver_status() -> dict:
    """Return a small read-only startup/health snapshot."""
    with _status_lock:
        return dict(_receiver_status)

# ─── G&D Trap 级别映射（GUD-GENERALTRAPS-MIB §9）────────────
#   0=Emergency, 1=Alert, 2=Critical → critical
#   3=Error, 4=Warning               → warning
#   5=Notice                         → info
_LEVEL_SEVERITY: dict[int, str] = {
    0: 'critical', 1: 'critical', 2: 'critical',
    3: 'warning',  4: 'warning',
    5: 'info',
}
_LEVEL_NAME: dict[int, str] = {
    0: 'EMERGENCY', 1: 'ALERT', 2: 'CRITICAL',
    3: 'ERROR',     4: 'WARNING', 5: 'NOTICE',
}

# 已观察到的设备/模拟器 Trap 使用 .32828.5.1.0.{2,3}；同时保留旧 MIB
# 推导布局 .32828.2.1.0.{2,3} 的兼容性。必须精确匹配，避免误把其他 varbind 当作级别/消息。
_LEVEL_OIDS = {
    "1.3.6.1.4.1.32828.5.1.0.2",
    "1.3.6.1.4.1.32828.2.1.0.2",
}
_MESSAGE_OIDS = {
    "1.3.6.1.4.1.32828.5.1.0.3",
    "1.3.6.1.4.1.32828.2.1.0.3",
}


def _normalize_oid(oid: object) -> str:
    return str(oid).lstrip(".")


def parse_trap_varbinds(var_binds) -> tuple[list[dict], int | None, str | None]:
    """Extract raw binds plus G&D level/message from observed or legacy layouts."""
    raw_binds: list[dict] = []
    trap_level: int | None = None
    trap_message: str | None = None
    for oid, val in var_binds:
        oid_str = _normalize_oid(oid)
        val_str = val.prettyPrint()
        raw_binds.append({"oid": oid_str, "value": val_str})
        if oid_str in _LEVEL_OIDS:
            try:
                trap_level = int(val_str)
            except (ValueError, TypeError):
                pass
        elif oid_str in _MESSAGE_OIDS:
            trap_message = val_str
    return raw_binds, trap_level, trap_message


def simulator_device_from_trap_source(runs, source_ip: str) -> str | None:
    """Resolve a simulator Trap using the explicit manifest source identity.

    Port mode deliberately keeps all SNMP polling endpoints on 127.0.0.1 with
    different ports, but a passive UDP Trap exposes only its source IP.  The
    bridge manifest therefore records an independent loopback trap source per
    device.  Ambiguous or legacy manifests return ``None`` rather than
    arbitrarily attributing an alert to the first device.
    """
    matches: list[str] = []
    for run in runs:
        manifest = getattr(run, "manifest", {}) or {}
        for device in manifest.get("scenario", {}).get("devices", []):
            if device.get("trap_source_host") == source_ip:
                matches.append(f"sim_{run.id}_{device.get('id', '')}"[:64])
    return matches[0] if len(matches) == 1 else None


async def _device_for_trap_source(db, source_ip: str):
    """Find one Dashboard device without allowing same-host ambiguity."""
    from app.models.device import Device
    from app.models.simulator_run import SimulatorRun
    from sqlalchemy import select

    runs = (await db.execute(select(SimulatorRun))).scalars().all()
    simulator_id = simulator_device_from_trap_source(runs, source_ip)
    if simulator_id:
        return await db.get(Device, simulator_id)
    devices = (await db.execute(select(Device).where(Device.host == source_ip))).scalars().all()
    return devices[0] if len(devices) == 1 else None


def _start_trap_receiver(
    main_loop: asyncio.AbstractEventLoop,
    ready_event: threading.Event | None = None,
):
    """在后台线程中启动 SNMP Trap 监听（独立事件循环）"""
    thread_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(thread_loop)

    snmp_engine = None
    try:
        snmp_engine = SnmpEngine()
        config.addTransport(
            snmp_engine,
            udp.domainName,
            udp.UdpTransport().openServerMode(("0.0.0.0", settings.snmp_trap_port)),
        )
        config.addV1System(snmp_engine, "trap-area", settings.snmp_default_community)
    except Exception as exc:
        _set_receiver_status(
            "failed",
            detail=str(exc),
            error_type=type(exc).__name__,
        )
        if ready_event:
            ready_event.set()
        logger.exception(
            "SNMP Trap 接收器绑定失败，UDP %s:%s",
            "0.0.0.0",
            settings.snmp_trap_port,
        )
        if snmp_engine is not None and snmp_engine.transportDispatcher is not None:
            snmp_engine.transportDispatcher.closeDispatcher()
        thread_loop.close()
        return

    def trap_callback(snmp_engine, state_reference, context_engine_id,
                      context_name, var_binds, cb_ctx):
        now = datetime.now(timezone.utc)
        source_ip = "unknown"

        try:
            _, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(state_reference)
            source_ip = str(transport_address[0])
        except Exception:
            pass

        # ── 解析所有 varbinds ──────────────────────────────
        raw_binds, trap_level, trap_message = parse_trap_varbinds(var_binds)

        # ── 原始数据全量记录（调试用，轮转文件，受 SNMP_RAW_LOG_ENABLED 控制）──
        if _raw_log_enabled:
            _raw_logger.info(
                f"src={source_ip} level={trap_level} msg={trap_message!r} | "
                f"all_binds={raw_binds}"
            )
        logger.debug(f"SNMP Trap 原始数据 from {source_ip}: {raw_binds}")

        # ── 映射严重级别 & 构建告警消息 ──────────────────────
        severity   = _LEVEL_SEVERITY.get(trap_level, 'warning') if trap_level is not None else 'warning'
        level_name = _LEVEL_NAME.get(trap_level, 'TRAP')

        if trap_message:
            message = f"[{level_name}] {trap_message}"
        else:
            # 降级：拼接前 3 条 varbind（向后兼容非 G&D 格式）
            message = "Trap from {}: {}".format(
                source_ip,
                "; ".join(f"{b['oid']}={b['value']}" for b in raw_binds[:3])
            )

        logger.warning(
            f"SNMP Trap ({level_name}/{severity}) from {source_ip}: "
            f"{trap_message or '<no message varbind>'}"
        )

        # ── 派发到 FastAPI 主线程写库 & 广播 ─────────────────
        asyncio.run_coroutine_threadsafe(
            _save_trap(source_ip, message, severity, raw_binds, now),
            main_loop,
        )
        # Trap 已携带完整告警信息，无需触发补轮询；定时轮询负责刷新设备状态

    ntfrcv.NotificationReceiver(snmp_engine, trap_callback)
    snmp_engine.transportDispatcher.jobStarted(1)
    _set_receiver_status("running")
    if ready_event:
        ready_event.set()

    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except Exception as e:
        _set_receiver_status(
            "failed",
            detail=str(e),
            error_type=type(e).__name__,
        )
        logger.exception("Trap 接收器运行错误")
    finally:
        snmp_engine.transportDispatcher.closeDispatcher()
        thread_loop.close()
        if trap_receiver_status()["state"] == "running":
            _set_receiver_status("stopped")


async def _save_trap(
    source_ip: str,
    message: str,
    severity: str,
    binds: list[dict],
    timestamp: datetime,
):
    """
    异步写库并广播 WebSocket。

    增强逻辑：
    - 从 Trap message 解析 ep_id/con_id（MIB Column 2）
    - 通过 Endpoint.last_status JSON 字段精确定位端点（不依赖 source_ip）
    - 从端点反查所属设备，再查别名
    - 降级：找不到设备/端点时保留原始消息，不报错
    """
    from app.models.device import Device
    from app.models.endpoint import Endpoint
    from app.models.device_alias import DeviceAlias
    from sqlalchemy import select
    import re

    async with AsyncSessionLocal() as db:
        # ── 1. 从消息中解析模块 ID（ep_id / con_id = MIB Column 2）──
        # Trap message 格式（真实设备日志确认）:
        #   "CPU module CPU-1-001 went offline"
        #   "CON module CON-2-003 came online"
        # 消息里用的是 ep_id / con_id（Column 2），不是 ep_name / con_name（Column 4）
        endpoint_id = None
        endpoint_name = None
        endpoint_status_update = None
        device_id = source_ip
        device_name = source_ip
        enhanced_message = message

        match = re.search(r'\b(CPU|CON) module ((CPU|CON)-\d+-\d+)\b', message)
        if (
            match
            and match.group(1) == match.group(3)
            and ("went offline" in message or "came online" in message)
        ):
            module_type_str = match.group(1)   # 'CPU' 或 'CON'
            module_id = match.group(2)          # e.g. 'CPU-1-001'
            action = "went offline" if "went offline" in message else "came online"
            # last_status JSON 里对应的键名
            id_field = "ep_id" if module_type_str == "CPU" else "con_id"

            # ── 2. 通过 last_status JSON 搜索端点 ─────────────────
            # 不依赖 source_ip（Docker 环境下 Trap 来源 IP 可能是网关而非设备 IP）
            # SQLAlchemy JSON 路径：
            #   PostgreSQL: last_status->>'ep_id' = 'CPU-1-001'
            #   SQLite:     json_extract(last_status, '$.ep_id') = 'CPU-1-001'
            ep_query = select(Endpoint).where(
                Endpoint.last_status[id_field].as_string() == module_id
            )
            ep_result = await db.execute(ep_query)
            endpoint = ep_result.scalar_one_or_none()

            if endpoint:
                endpoint_id = endpoint.id
                status_field = "ep_device_status" if module_type_str == "CPU" else "con_device_status"
                status_value = "offline" if action == "went offline" else "online"
                endpoint.last_status = {**(endpoint.last_status or {}), status_field: status_value}
                endpoint.updated_at = timestamp
                endpoint_status_update = {status_field: status_value}

                # ── 3. 从端点反查所属设备 ──────────────────────────
                device = await db.get(Device, endpoint.device_id)
                if device:
                    device_id = device.id
                    device_name = device.name

                    dev_alias = await db.execute(
                        select(DeviceAlias).where(DeviceAlias.target_id == device.id)
                    )
                    dev_alias = dev_alias.scalar_one_or_none()
                    if dev_alias and dev_alias.alias:
                        device_name = dev_alias.alias

                # ── 4. 端点别名 ────────────────────────────────────
                endpoint_name = endpoint.name
                ep_alias = await db.execute(
                    select(DeviceAlias).where(DeviceAlias.target_id == endpoint.id)
                )
                ep_alias = ep_alias.scalar_one_or_none()
                if ep_alias and ep_alias.alias:
                    endpoint_name = ep_alias.alias

                enhanced_message = f"{device_name}/{endpoint_name} {action}"
            else:
                # 找不到端点：尝试仅用 source_ip 查设备（兼容非 Docker 部署）
                device = await _device_for_trap_source(db, source_ip)
                if device:
                    device_id = device.id
                    device_name = device.name
                    dev_alias = await db.execute(
                        select(DeviceAlias).where(DeviceAlias.target_id == device.id)
                    )
                    dev_alias = dev_alias.scalar_one_or_none()
                    if dev_alias and dev_alias.alias:
                        device_name = dev_alias.alias
                enhanced_message = f"{device_name}: {message}"
        else:
            # 消息格式无法解析（非 G&D 标准格式）：尝试 source_ip 查设备
            device = await _device_for_trap_source(db, source_ip)
            if device:
                device_id = device.id
                device_name = device.name
                dev_alias = await db.execute(
                    select(DeviceAlias).where(DeviceAlias.target_id == device.id)
                )
                dev_alias = dev_alias.scalar_one_or_none()
                if dev_alias and dev_alias.alias:
                    device_name = dev_alias.alias
                enhanced_message = f"{device_name}: {message}"

        # ── 5. 保存告警 ──────────────────────────────────────────
        db.add(Alert(
            device_id=device_id,
            endpoint_id=endpoint_id,
            oid_name="trap",
            alert_type="trap",
            severity=severity,
            message=enhanced_message,
            raw_value=str(binds),
            created_at=timestamp,
        ))
        await db.commit()

    # ── 6. 已验证的模块状态 Trap 立即更新大屏，并以轻量 SNMP 查询复核 ──
    if endpoint_id and endpoint_status_update:
        await ws_manager.broadcast({
            "type": "endpoint_update",
            "device_id": device_id,
            "endpoint_id": endpoint_id,
            "last_status": endpoint_status_update,
            "reason": "snmp_trap",
            "timestamp": timestamp.isoformat(),
        })
        # 延后到当前事务完成后运行；失败只影响复核，不影响已收到的 Trap 状态。
        from app.snmp.poller import probe_device_endpoint_statuses
        asyncio.create_task(probe_device_endpoint_statuses(device_id))

    # ── 7. 广播 Trap 告警 ──────────────────────────────────────
    await ws_manager.broadcast({
        "type": "trap_received",
        "source_ip": source_ip,
        "device_id": device_id,
        "device_name": device_name,
        "endpoint_id": endpoint_id,
        "endpoint_name": endpoint_name,
        "message": enhanced_message,
        "original_message": message,
        "severity": severity,
        "binds": binds,
        "timestamp": timestamp.isoformat(),
    })


async def start_trap_receiver(startup_timeout: float = 5.0) -> dict:
    """启动 Trap 监听，并等待后台线程确认 UDP 已成功绑定。"""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_EXCLUSIVEADDRUSE,
                1,
            )
        probe.bind(("0.0.0.0", settings.snmp_trap_port))
    except OSError as exc:
        _set_receiver_status(
            "failed",
            detail=str(exc),
            error_type=type(exc).__name__,
        )
        raise RuntimeError(
            "SNMP Trap receiver failed to reserve "
            f"udp://0.0.0.0:{settings.snmp_trap_port}: {exc}"
        ) from exc
    finally:
        probe.close()

    loop = asyncio.get_running_loop()
    ready_event = threading.Event()
    _set_receiver_status("starting")
    thread = threading.Thread(
        target=_start_trap_receiver,
        args=(loop, ready_event),
        daemon=True,
        name="snmp-trap-receiver",
    )
    thread.start()
    ready = await asyncio.to_thread(ready_event.wait, startup_timeout)
    status = trap_receiver_status()
    if not ready:
        _set_receiver_status(
            "failed",
            detail=f"startup readiness timeout after {startup_timeout:.1f}s",
            error_type="TimeoutError",
        )
        status = trap_receiver_status()
    if status["state"] != "running":
        raise RuntimeError(
            "SNMP Trap receiver failed to bind "
            f"udp://{status['listen_host']}:{status['listen_port']}: "
            f"{status.get('detail') or 'unknown startup error'}"
        )
    logger.info("SNMP Trap 接收器已启动，监听 UDP:%s", settings.snmp_trap_port)
    return status
