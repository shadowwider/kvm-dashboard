"""
SNMP 多设备并行轮询器 (生产级)。
  - 限流并发 (Semaphore): 同时最多 N 台设备
  - SnmpEngine 复用池: 避免每次 GET/WALK 都创建新引擎
  - 批量 INSERT: 一次性写入所有 metrics
  - 告警去重: 10 分钟内同设备同指标不重复告警
"""
import asyncio
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone, timedelta
from pysnmp.hlapi.asyncio import (
    SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity,
    getCmd, bulkCmd,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, update, insert
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.status_metric import StatusMetric
from app.models.alert import Alert
from app.snmp.parser import parse_snmp_value, is_alert_triggered
from app.snmp.profile_runtime import (
    ProfilePollResult,
    collect_profile_snapshot,
    identify_profile,
    mark_profile_data_stale,
    persist_profile_snapshot,
)
from app.serializers import serialize_alert, serialize_device_summary
from app.websocket.hub import event_envelope, ws_manager
from app.config import get_settings as _get_settings

logger = logging.getLogger(__name__)

def is_full_poll_eligible(device: Device) -> bool:
    """All active devices are eligible for exact Profile identification."""
    return bool(getattr(device, "is_active", True))


def is_full_poll_due(
    device: Device,
    now: datetime | None = None,
) -> bool:
    """Honor the per-device full polling interval."""
    now = now or datetime.now(timezone.utc)
    retry_after = _full_poll_retry_after.get(device.id)
    if retry_after is not None:
        if now < retry_after:
            return False
        _full_poll_retry_after.pop(device.id, None)

    last_poll = getattr(device, "last_poll", None)
    if last_poll is None:
        return True
    if last_poll.tzinfo is None:
        last_poll = last_poll.replace(tzinfo=timezone.utc)
    interval = max(1, int(getattr(device, "poll_interval", 60) or 60))
    return (now - last_poll).total_seconds() >= interval


# ─── 轮询原始数据专用日志（受 SNMP_RAW_LOG_ENABLED 控制）────────
_poll_raw_logger = logging.getLogger('snmp.poll.raw')
_poll_settings = _get_settings()
_raw_log_enabled: bool = _poll_settings.snmp_raw_log_enabled


class _SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def handleError(self, record):
        exc = sys.exc_info()[1]
        if isinstance(exc, PermissionError):
            return
        super().handleError(record)


def _init_poll_raw_logger():
    """初始化轮询原始数据 RotatingFileHandler（不影响主日志）"""
    if not _raw_log_enabled or _poll_raw_logger.handlers:
        return
    log_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    )
    os.makedirs(log_dir, exist_ok=True)
    handler = _SafeRotatingFileHandler(
        os.path.join(log_dir, 'poll_raw.log'),
        maxBytes=_poll_settings.snmp_raw_log_max_mb * 1024 * 1024,
        backupCount=_poll_settings.snmp_raw_log_backup_count,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
    _poll_raw_logger.addHandler(handler)
    _poll_raw_logger.setLevel(logging.DEBUG)
    _poll_raw_logger.propagate = False


_init_poll_raw_logger()

# ─── 配置 ─────────────────────────────────────────────────────────
CONCURRENCY_LIMIT = 20      # 同时最多轮询 N 台设备
SNMP_REQUEST_CONCURRENCY = 10  # 完整轮询的同时在途 SNMP 请求数
SNMP_TIMEOUT = 3             # 完整指标轮询的 SNMP 请求超时 (秒)
SNMP_RETRIES = 1             # 完整指标轮询的超时重试次数
BULK_MAX_REPETITIONS = 25    # GETBULK 每批返回行数
WALK_MAX_ITERATIONS = 100    # WALK 防止无限循环
ALERT_DEDUP_MINUTES = 10     # 告警去重窗口 (分钟)
BATCH_INSERT_SIZE = 5000     # 每批 INSERT 行数
TRAP_POLL_COOLDOWN = 10      # Trap 触发轮询冷却时间 (秒)，避免与定时轮询并发写冲突
FULL_POLL_FAILURE_RETRY_MIN_SECONDS = 5
SYS_OBJECT_ID_OID = "1.3.6.1.2.1.1.2.0"
CCDC_LEGACY_SYS_OBJECT_ID = "1.3.6.1.4.1.32828.3.257.16"

# 轻量路径与完整指标轮询隔离：可达性探测不执行 WALK/写指标；可选状态列探测仅查询三列。
_health_failures: dict[str, int] = {}
_health_port_statuses: dict[str, dict[str, str]] = {}
_health_device_locks: dict[str, asyncio.Lock] = {}
_endpoint_status_locks: dict[str, asyncio.Lock] = {}
_health_device_locks_guard = asyncio.Lock()
_pending_health_heartbeats: dict[str, tuple[datetime, float]] = {}
_latest_health_successes: dict[str, datetime] = {}
_full_poll_retry_after: dict[str, datetime] = {}
_health_heartbeat_guard = asyncio.Lock()
health_monitor_state: dict[str, object] = {
    "last_started_at": None,
    "last_finished_at": None,
    "last_duration_ms": None,
    "active_devices": 0,
    "successes": 0,
    "failures": 0,
    "transitions": 0,
    "max_probe_ms": 0,
    "capacity_degraded": False,
    "heartbeat_pending": 0,
    "heartbeat_last_flush_at": None,
}

# ─── SnmpEngine 池 ────────────────────────────────────────────────
_engine_pool: list[SnmpEngine] = []
_engine_lock = asyncio.Lock()
_engine_creation_lock = asyncio.Lock()
_snmp_request_semaphore = asyncio.Semaphore(SNMP_REQUEST_CONCURRENCY)
_health_engine_pool: list[SnmpEngine] = []
_health_engine_lock = asyncio.Lock()
_health_engine_creation_lock = asyncio.Lock()
_health_request_semaphore = asyncio.Semaphore(
    _poll_settings.snmp_health_concurrency
)

# ─── Trap 触发轮询冷却表（host → 上次触发时间戳）────────────────────
import time as _time
_trap_poll_last: dict[str, float] = {}


async def _get_engine(*, health: bool = False) -> SnmpEngine:
    pool = _health_engine_pool if health else _engine_pool
    lock = _health_engine_lock if health else _engine_lock
    creation_lock = (
        _health_engine_creation_lock if health else _engine_creation_lock
    )
    async with lock:
        if pool:
            return pool.pop()

    # SnmpEngine imports internal MIBs synchronously. Keep construction off the
    # event loop and serialize cold creation so a request burst cannot saturate
    # the interpreter before health probes get a chance to run.
    async with creation_lock:
        async with lock:
            if pool:
                return pool.pop()
        return await asyncio.to_thread(SnmpEngine)


def _discard_engine(eng: SnmpEngine):
    """安全销毁一个不可用的引擎"""
    try:
        eng.transportDispatcher.closeDispatcher()
    except Exception:
        pass


async def _return_engine(
    eng: SnmpEngine,
    discard: bool = False,
    *,
    health: bool = False,
):
    """将引擎放回池中。如果 discard=True（连接失败），则销毁该引擎而非复用。"""
    if discard:
        _discard_engine(eng)
        return
    pool = _health_engine_pool if health else _engine_pool
    lock = _health_engine_lock if health else _engine_lock
    limit = (
        _poll_settings.snmp_health_concurrency
        if health
        else SNMP_REQUEST_CONCURRENCY
    )
    async with lock:
        if len(pool) < limit:
            pool.append(eng)
        else:
            _discard_engine(eng)


def _numeric_oid_tuple(oid: str) -> tuple[int, ...]:
    """Keep numeric OIDs on pysnmp's direct path and avoid MIB name resolution."""
    return tuple(int(part) for part in oid.lstrip(".").split("."))


async def _snmp_get(
    host: str,
    port: int,
    community: str,
    oid: str,
    *,
    timeout: float = SNMP_TIMEOUT,
    retries: int = SNMP_RETRIES,
    health: bool = False,
) -> tuple[str, any]:
    """单个 OID GET 查询，返回 (oid, raw_value)。"""
    semaphore = (
        _health_request_semaphore if health else _snmp_request_semaphore
    )
    await semaphore.acquire()
    engine: SnmpEngine | None = None
    failed = False
    try:
        engine = await _get_engine(health=health)
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=timeout, retries=retries),
            ContextData(),
            ObjectType(ObjectIdentity(_numeric_oid_tuple(oid))),
        )
        if error_indication:
            # A transport timeout can leave the pysnmp dispatcher/LCD state
            # unusable in a long-running process. Do not return that engine to
            # the pool: a fresh engine is cheaper than keeping reachability
            # probes stuck after the device comes back.
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
        if engine is not None:
            await _return_engine(engine, discard=failed, health=health)
        semaphore.release()


async def _snmp_walk(
    host: str,
    port: int,
    community: str,
    base_oid: str,
    *,
    timeout: float = SNMP_TIMEOUT + 2,
    retries: int = SNMP_RETRIES,
    max_iterations: int = WALK_MAX_ITERATIONS,
    strict: bool = False,
) -> dict[str, any]:
    """SNMP WALK via pysnmp v6 bulkCmd (SnmpEngine 复用)。"""
    await _snmp_request_semaphore.acquire()
    engine: SnmpEngine | None = None
    results = {}
    next_oid = base_oid
    base_tuple = _numeric_oid_tuple(base_oid)
    failed = False
    try:
        engine = await _get_engine()
        for iteration in range(max_iterations):
            error_indication, error_status, error_index, var_bind_table = await bulkCmd(
                engine,
                CommunityData(community, mpModel=1),
                UdpTransportTarget((host, port), timeout=timeout, retries=retries),
                ContextData(),
                0, BULK_MAX_REPETITIONS,
                ObjectType(ObjectIdentity(_numeric_oid_tuple(next_oid))),
            )
            if error_indication:
                failed = True
                if strict:
                    raise RuntimeError(str(error_indication))
                break
            if error_status:
                if strict:
                    raise RuntimeError(error_status.prettyPrint())
                break
            if not var_bind_table:
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
        if strict:
            raise
    finally:
        if engine is not None:
            await _return_engine(engine, discard=failed)
        _snmp_request_semaphore.release()
    logger.debug(f"WALK {base_oid}: {len(results)} results")
    return results


async def _profile_snmp_walk(
    host: str,
    port: int,
    community: str,
    base_oid: str,
) -> dict[str, any]:
    """Profile collector adapter that preserves WALK transport failures."""
    return await _snmp_walk(
        host,
        port,
        community,
        base_oid,
        strict=True,
    )


async def _get_health_device_lock(device_id: str) -> asyncio.Lock:
    async with _health_device_locks_guard:
        return _health_device_locks.setdefault(device_id, asyncio.Lock())


async def _queue_health_heartbeat(
    device_id: str,
    checked_at: datetime,
    elapsed_ms: float,
) -> None:
    """Merge stable-online probe metadata without entering the database write path."""
    heartbeat = (checked_at, round(elapsed_ms, 2))
    async with _health_heartbeat_guard:
        _latest_health_successes[device_id] = checked_at
        current = _pending_health_heartbeats.get(device_id)
        if current is None or checked_at >= current[0]:
            _pending_health_heartbeats[device_id] = heartbeat
        health_monitor_state["heartbeat_pending"] = len(_pending_health_heartbeats)


async def _clear_health_success(device_id: str) -> None:
    """Invalidate buffered success metadata after a newer failed probe."""
    async with _health_heartbeat_guard:
        _latest_health_successes.pop(device_id, None)
        _pending_health_heartbeats.pop(device_id, None)
        health_monitor_state["heartbeat_pending"] = len(
            _pending_health_heartbeats
        )


def _defer_full_poll_retry(
    device: Device,
    now: datetime | None = None,
) -> None:
    """Prevent failed first polls from being retried by every scheduler tick."""
    now = now or datetime.now(timezone.utc)
    retry_seconds = max(
        FULL_POLL_FAILURE_RETRY_MIN_SECONDS,
        int(getattr(device, "poll_interval", 60) or 60),
    )
    _full_poll_retry_after[device.id] = now + timedelta(seconds=retry_seconds)


def _clear_full_poll_retry(device_id: str) -> None:
    _full_poll_retry_after.pop(device_id, None)


async def flush_health_heartbeats() -> int:
    """Persist merged stable-online heartbeats in one non-critical transaction."""
    async with _health_heartbeat_guard:
        if not _pending_health_heartbeats:
            health_monitor_state["heartbeat_pending"] = 0
            return 0
        snapshot = dict(_pending_health_heartbeats)
        _pending_health_heartbeats.clear()
        health_monitor_state["heartbeat_pending"] = 0

    try:
        async with AsyncSessionLocal() as db:
            for device_id, (checked_at, latency_ms) in snapshot.items():
                await db.execute(
                    update(Device)
                    .where(
                        Device.id == device_id,
                        or_(
                            Device.last_status.is_(None),
                            Device.last_status != "offline",
                        ),
                        or_(
                            Device.last_health_check.is_(None),
                            Device.last_health_check <= checked_at,
                        ),
                    )
                    .values(
                        last_health_check=checked_at,
                        last_health_latency_ms=latency_ms,
                    )
                )
            await db.commit()
    except Exception:
        async with _health_heartbeat_guard:
            for device_id, heartbeat in snapshot.items():
                current = _pending_health_heartbeats.get(device_id)
                if current is None or heartbeat[0] > current[0]:
                    _pending_health_heartbeats[device_id] = heartbeat
            health_monitor_state["heartbeat_pending"] = len(
                _pending_health_heartbeats
            )
        logger.exception(
            "health_heartbeat_flush_failed devices=%s",
            len(snapshot),
        )
        return 0

    health_monitor_state["heartbeat_last_flush_at"] = (
        datetime.now(timezone.utc).isoformat()
    )
    async with _health_heartbeat_guard:
        health_monitor_state["heartbeat_pending"] = len(
            _pending_health_heartbeats
        )
    logger.debug("health_heartbeat_flush devices=%s", len(snapshot))
    return len(snapshot)


async def _broadcast_health_transition(
    device_id: str,
    status: str,
    now: datetime,
    reason: str,
    alert_payload: dict | None = None,
):
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
        device_payload = (
            await serialize_device_summary(db, device)
            if device is not None
            else None
        )
    await ws_manager.broadcast(event_envelope(
        "device_update",
        event_id=f"device:{device_id}:{now.isoformat()}",
        timestamp=now,
        data={"device": device_payload} if device_payload else {"device_id": device_id},
        device=device_payload,
        device_id=device_id,
        online_status=status,
        reachability=status,
        reason=reason,
        last_health_check=now.isoformat(),
    ))
    if alert_payload is not None:
        await _broadcast_persisted_alerts([alert_payload], now)


async def _broadcast_persisted_alerts(
    alert_payloads: list[dict],
    timestamp: datetime,
) -> None:
    """Broadcast committed alerts using the stable and compatibility contracts."""
    if not alert_payloads:
        return
    for alert in alert_payloads:
        await ws_manager.broadcast(event_envelope(
            "alert_created",
            event_id=f"alert:{alert['id']}",
            timestamp=timestamp,
            data={"alert": alert},
            alert=alert,
        ))
    await ws_manager.broadcast(event_envelope(
        "new_alerts",
        event_id="alerts:" + ",".join(str(alert["id"]) for alert in alert_payloads),
        timestamp=timestamp,
        data={"alerts": alert_payloads},
        alerts=alert_payloads,
    ))


async def _persist_health_transition(
    device: Device,
    *,
    reachable: bool,
    threshold_reached: bool,
    elapsed_ms: float,
    now: datetime,
    not_newer_than: datetime | None = None,
) -> tuple[bool, dict | None]:
    """Persist reachability state and its alert before any WebSocket broadcast."""
    transitioned = False
    alert: Alert | None = None
    if not reachable and not_newer_than is not None:
        async with _health_heartbeat_guard:
            latest_success = _latest_health_successes.get(device.id)
        if latest_success is not None and latest_success > not_newer_than:
            return False, None

    async with AsyncSessionLocal() as db:
        current = await db.get(Device, device.id)
        if current is None:
            return False, None
        if (
            not reachable
            and not_newer_than is not None
            and current.last_health_check is not None
        ):
            last_health_check = current.last_health_check
            if last_health_check.tzinfo is None:
                last_health_check = last_health_check.replace(tzinfo=timezone.utc)
            if last_health_check > not_newer_than:
                return False, None

        latency = round(elapsed_ms, 2)
        if reachable:
            if current.last_status == "offline":
                transitioned = True
                current.last_status = "online"
                current.last_health_check = now
                current.last_health_latency_ms = latency
                await db.execute(
                    update(Alert)
                    .where(
                        Alert.device_id == current.id,
                        Alert.alert_type == "offline",
                        Alert.is_resolved.is_(False),
                    )
                    .values(is_resolved=True, resolved_at=now)
                )
                alert = Alert(
                    device_id=current.id,
                    oid_name="reachability",
                    alert_type="recovery",
                    severity="info",
                    message=f"{current.name} 已恢复在线",
                    raw_value="online",
                    created_at=now,
                )
                db.add(alert)
        elif threshold_reached and current.last_status != "offline":
            transitioned = True
            current.last_status = "offline"
            current.last_health_check = now
            current.last_health_latency_ms = latency
            alert = Alert(
                device_id=current.id,
                oid_name="reachability",
                alert_type="offline",
                severity="critical",
                message=f"{current.name} 已离线",
                raw_value="offline",
                created_at=now,
            )
            db.add(alert)

        if transitioned:
            await db.commit()
            await db.refresh(alert)
            alert_payload = serialize_alert(alert)
        else:
            alert_payload = None

    if transitioned and not reachable:
        await _clear_health_success(device.id)
        await mark_profile_data_stale(device.id)
    return transitioned, alert_payload


async def probe_device_health(device: Device) -> tuple[bool, bool, float]:
    """只读取 sysObjectID 的快速可达性探测。

    返回 (reachable, transitioned, elapsed_ms)。此路径不能执行 WALK、写指标或更新端点。
    """
    settings = _get_settings()
    started = _time.monotonic()
    _, raw_sys_oid = await _snmp_get(
        device.host,
        device.port,
        device.community,
        SYS_OBJECT_ID_OID,
        timeout=settings.snmp_health_timeout,
        retries=settings.snmp_health_retries,
        health=True,
    )
    elapsed_ms = (_time.monotonic() - started) * 1000
    reachable = raw_sys_oid is not None
    transitioned = False
    now = datetime.now(timezone.utc)

    lock = await _get_health_device_lock(device.id)
    async with lock:
        if reachable:
            had_failures = device.id in _health_failures
            _health_failures.pop(device.id, None)
            if had_failures or device.last_status == "offline":
                _clear_full_poll_retry(device.id)
            if device.last_status == "offline":
                transitioned, alert_payload = await _persist_health_transition(
                    device,
                    reachable=True,
                    threshold_reached=False,
                    elapsed_ms=elapsed_ms,
                    now=now,
                )
            else:
                await _queue_health_heartbeat(device.id, now, elapsed_ms)
                alert_payload = None
            if transitioned:
                logger.warning(
                    "device_health_recovered device_id=%s host=%s elapsed_ms=%.1f",
                    device.id, device.host, elapsed_ms,
                )
                await _broadcast_health_transition(
                    device.id,
                    "online",
                    now,
                    "snmp_health_probe_recovered",
                    alert_payload,
                )
        else:
            await _clear_health_success(device.id)
            failures = _health_failures.get(device.id, 0) + 1
            _health_failures[device.id] = failures
            threshold_reached = (
                failures >= settings.snmp_health_failure_threshold
            )
            if threshold_reached and device.last_status != "offline":
                _defer_full_poll_retry(device, now)
                transitioned, alert_payload = await _persist_health_transition(
                    device,
                    reachable=False,
                    threshold_reached=True,
                    elapsed_ms=elapsed_ms,
                    now=now,
                )
            else:
                alert_payload = None
            if transitioned:
                logger.warning(
                    "device_health_offline device_id=%s host=%s failures=%s elapsed_ms=%.1f",
                    device.id, device.host, failures, elapsed_ms,
                )
                await _broadcast_health_transition(
                    device.id,
                    "offline",
                    now,
                    "snmp_health_probe_timeout",
                    alert_payload,
                )

    return reachable, transitioned, elapsed_ms


async def probe_device_endpoint_statuses(device_id: str):
    """按设备 ID 复核 CPU/CON 与物理端口状态，供已验证 Trap 触发。

    此函数不是一秒健康循环的一部分；它只在 Trap 到达后执行。
    """
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
    if not device or not device.is_active or not _supports_legacy_endpoint_probe(device):
        return
    await _probe_endpoint_statuses(device)


def _supports_legacy_endpoint_probe(device: Device) -> bool:
    """Only the legacy CCDC profile uses the three known endpoint status tables."""
    return (
        getattr(device, "profile_id", None) == "ccdc_legacy"
        or getattr(device, "system_oid", None) == CCDC_LEGACY_SYS_OBJECT_ID
    )


async def _probe_endpoint_statuses(device: Device):
    """快速读取 CPU/CON 状态列和物理端口状态列，不假设端口与模块索引对应。"""
    settings = _get_settings()
    from app.snmp.oid_map import CON_TABLE_ENTRY, ENDPOINT_TABLE_ENTRY, ENUM_MAPS, PORT_TABLE_ENTRY

    sys_oid = device.system_oid or "1.3.6.1.4.1.32828.3.257.16"
    probes = [
        ("cpu", f"{ENDPOINT_TABLE_ENTRY}.5", "ep_device_status", ENUM_MAPS["device_status"]),
        ("con", f"{CON_TABLE_ENTRY}.5", "con_device_status", ENUM_MAPS["device_status"]),
        ("port", f"{PORT_TABLE_ENTRY}.2", "port_status", ENUM_MAPS["port_status"]),
    ]
    results = await asyncio.gather(*(
        _snmp_walk(
            device.host, device.port, device.community, base_oid.replace("{sys_oid}", sys_oid),
            timeout=settings.snmp_health_timeout,
            retries=0,
            # 单个 GETBULK 最多返回 25 行，覆盖当前 20 端点部署而不把状态检测拖成深度 WALK。
            max_iterations=1,
        )
        for _, base_oid, _, _ in probes
    ), return_exceptions=True)

    now = datetime.now(timezone.utc)
    port_statuses = _health_port_statuses.setdefault(device.id, {})
    async with _health_device_locks_guard:
        status_lock = _endpoint_status_locks.setdefault(device.id, asyncio.Lock())
    async with status_lock, AsyncSessionLocal() as db:
        for (namespace, _, status_field, enum_map), result in zip(probes, results):
            if isinstance(result, Exception) or not isinstance(result, dict):
                continue
            for full_oid, raw_value in result.items():
                row_index = full_oid.rsplit(".", 1)[-1]
                value_str, _ = parse_snmp_value(raw_value, "enum", enum_map)
                if namespace == "port":
                    previous = port_statuses.get(row_index)
                    port_statuses[row_index] = value_str
                    if previous is not None and previous != value_str:
                        await ws_manager.broadcast({
                            "type": "port_update",
                            "device_id": device.id,
                            "port_index": row_index,
                            "status": value_str,
                            "previous_status": previous,
                            "timestamp": now.isoformat(),
                            "mapping_verified": False,
                        })
                    continue

                endpoint = await db.get(Endpoint, f"{device.id}_{namespace}_{row_index}")
                if not endpoint:
                    continue
                previous_status = (endpoint.last_status or {}).get(status_field)
                if previous_status == value_str:
                    continue
                endpoint.last_status = {**(endpoint.last_status or {}), status_field: value_str}
                endpoint.updated_at = now
                await ws_manager.broadcast({
                    "type": "endpoint_update",
                    "device_id": device.id,
                    "endpoint_id": endpoint.id,
                    "last_status": {status_field: value_str},
                    "reason": "snmp_targeted_status_probe",
                    "timestamp": now.isoformat(),
                })
        await db.commit()


async def run_health_probe_cycle():
    """并发运行轻量 sysObjectID 可达性探测，不与完整指标轮询共享限流。"""
    settings = _get_settings()
    if not settings.snmp_health_poll_enabled:
        return

    started_at = datetime.now(timezone.utc)
    started = _time.monotonic()
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device).where(Device.is_active == True))
        devices = result.scalars().all()

    semaphore = asyncio.Semaphore(settings.snmp_health_concurrency)
    successes = failures = transitions = 0
    max_probe_ms = 0.0

    async def limited_probe(device: Device):
        nonlocal successes, failures, transitions, max_probe_ms
        async with semaphore:
            try:
                reachable, transitioned, elapsed_ms = await probe_device_health(device)
                successes += int(reachable)
                failures += int(not reachable)
                transitions += int(transitioned)
                max_probe_ms = max(max_probe_ms, elapsed_ms)
            except Exception:
                failures += 1
                logger.exception("设备 %s 健康探测异常", device.id)

    await asyncio.gather(*(limited_probe(device) for device in devices), return_exceptions=True)
    duration_ms = (_time.monotonic() - started) * 1000
    health_timeout_budget = settings.snmp_health_timeout * (settings.snmp_health_retries + 1)
    estimated_scan_seconds = (
        (len(devices) + settings.snmp_health_concurrency - 1)
        // settings.snmp_health_concurrency
    ) * health_timeout_budget
    capacity_degraded = estimated_scan_seconds > settings.snmp_health_poll_interval
    health_monitor_state.update({
        "last_started_at": started_at.isoformat(),
        "last_finished_at": datetime.now(timezone.utc).isoformat(),
        "last_duration_ms": round(duration_ms, 1),
        "active_devices": len(devices),
        "successes": successes,
        "failures": failures,
        "transitions": transitions,
        "max_probe_ms": round(max_probe_ms, 1),
        "capacity_degraded": capacity_degraded,
        "estimated_scan_seconds": round(estimated_scan_seconds, 3),
    })
    if capacity_degraded:
        logger.error(
            "health_probe_capacity_degraded devices=%s concurrency=%s estimated_scan_seconds=%.3f interval=%.3f",
            len(devices), settings.snmp_health_concurrency, estimated_scan_seconds,
            settings.snmp_health_poll_interval,
        )
    logger.info(
        "health_probe_cycle devices=%s successes=%s failures=%s transitions=%s duration_ms=%.1f max_probe_ms=%.1f",
        len(devices), successes, failures, transitions, duration_ms, max_probe_ms,
    )


async def run_endpoint_status_probe_cycle():
    """Refresh legacy CPU/CON/port states without delaying reachability detection."""
    settings = _get_settings()
    if not settings.snmp_endpoint_status_poll_enabled:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Device).where(
                Device.is_active == True,
                or_(
                    Device.profile_id == "ccdc_legacy",
                    Device.system_oid == CCDC_LEGACY_SYS_OBJECT_ID,
                ),
            )
        )
        devices = result.scalars().all()

    semaphore = asyncio.Semaphore(settings.snmp_health_concurrency)

    async def limited_probe(device: Device):
        async with semaphore:
            try:
                await _probe_endpoint_statuses(device)
            except Exception:
                logger.exception("设备 %s 端点状态探测异常", device.id)

    await asyncio.gather(*(limited_probe(device) for device in devices), return_exceptions=True)
    logger.info("endpoint_status_probe_cycle devices=%s", len(devices))


def _profile_alert_candidates(
    device: Device,
    result: ProfilePollResult,
) -> list[dict]:
    candidates: list[dict] = []

    def add_candidate(state: dict, *, entity_key: str | None = None, label: str | None = None):
        status = state.get("status")
        if status not in {"warning", "critical"}:
            return
        field_key = str(state.get("key") or "profile_state")
        target = f"/{label}" if label else ""
        candidates.append({
            "device_id": device.id,
            "endpoint_id": None,
            "entity_key": entity_key,
            "oid_name": field_key[:64],
            "alert_type": "threshold",
            "severity": status,
            "message": f"{device.name}{target} {field_key} 异常: {state.get('value')}",
            "raw_value": str(state.get("raw")),
        })

    for state in result.scalar_states.values():
        add_candidate(state)
    for entity in result.entities:
        for state in entity["field_states"].values():
            add_candidate(
                state,
                entity_key=entity["entity_key"],
                label=entity.get("label"),
            )
    return candidates


async def _persist_alert_candidates(
    db: AsyncSession,
    candidates: list[dict],
    now: datetime,
) -> list[Alert]:
    """Apply the shared 10-minute dedup rule and retain committed Alert IDs."""
    created: list[Alert] = []
    dedup_cutoff = now - timedelta(minutes=ALERT_DEDUP_MINUTES)
    for candidate in candidates:
        existing_alert = await db.execute(
            select(Alert).where(
                Alert.device_id == candidate["device_id"],
                Alert.endpoint_id == candidate.get("endpoint_id"),
                Alert.oid_name == candidate.get("oid_name"),
                Alert.entity_key == candidate.get("entity_key"),
                Alert.is_resolved.is_(False),
                Alert.created_at >= dedup_cutoff,
            ).limit(1)
        )
        if existing_alert.scalar_one_or_none():
            continue
        alert = Alert(created_at=now, **candidate)
        db.add(alert)
        created.append(alert)
    if created:
        await db.flush()
    return created


async def _broadcast_device_snapshot(
    device_id: str,
    *,
    timestamp: datetime,
    reason: str,
) -> None:
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
        if device is None:
            return
        payload = await serialize_device_summary(db, device)
    await ws_manager.broadcast(event_envelope(
        "device_update",
        event_id=f"device:{device_id}:{timestamp.isoformat()}",
        timestamp=timestamp,
        data={"device": payload},
        device=payload,
        device_id=device_id,
        online_status=payload["reachability"]["status"],
        reachability=payload["reachability"]["status"],
        last_metrics=payload.get("last_metrics"),
        endpoint_count=payload.get("endpoint_count", 0),
        reason=reason,
    ))


async def _poll_profile_device(
    device: Device,
    profile,
    now: datetime,
) -> None:
    result = await collect_profile_snapshot(
        device,
        profile,
        _snmp_get,
        _profile_snmp_walk,
    )
    await persist_profile_snapshot(device.id, result)

    candidates = _profile_alert_candidates(device, result)
    async with AsyncSessionLocal() as db:
        alerts = await _persist_alert_candidates(db, candidates, now)
        await db.commit()
        alert_payloads = [serialize_alert(alert) for alert in alerts]

    await _broadcast_device_snapshot(
        device.id,
        timestamp=now,
        reason=f"profile_poll_{result.status}",
    )
    await _broadcast_persisted_alerts(alert_payloads, now)
    logger.info(
        "Profile 轮询完成 device=%s profile=%s status=%s entities=%s alerts=%s",
        device.id,
        profile.profile_id,
        result.status,
        len(result.entities),
        len(alert_payloads),
    )


async def poll_device(device: Device, oid_configs: list[OIDRegistry]):
    """轮询单台设备，写入时序数据并检测告警"""
    logger.info(f"开始轮询设备: {device.id} ({device.host})")
    now = datetime.now(timezone.utc)

    device_oids = [o for o in oid_configs if o.category == "device" and o.poll_enabled and not o.is_table]
    table_oid_configs = [o for o in oid_configs if o.poll_enabled and o.is_table]

    metrics_to_insert: list[dict] = []
    alerts_to_create: list[dict] = []

    # ── 读取 sysObjectID 并精确选择五 Profile 之一 ─────────────────
    sys_oid = device.system_oid
    discovered_system_oid = None
    profile = None
    rich_probe_started_at = now
    rich_probe_started_monotonic = _time.monotonic()
    try:
        _, raw_sys_oid = await _snmp_get(device.host, device.port, device.community, SYS_OBJECT_ID_OID)
        if raw_sys_oid:
            profile = identify_profile(raw_sys_oid)
            if hasattr(raw_sys_oid, "asTuple"):
                sys_oid = ".".join(str(x) for x in raw_sys_oid.asTuple())
            else:
                sys_oid = str(raw_sys_oid).lstrip(".")
            discovered_system_oid = sys_oid
        else:
            logger.warning(f"设备 {device.id} (IP: {device.host}) 完整轮询 sysObjectID 超时，跳过深度轮询。")
            _defer_full_poll_retry(device, now)
            lock = await _get_health_device_lock(device.id)
            async with lock:
                transitioned, alert_payload = await _persist_health_transition(
                    device,
                    reachable=False,
                    threshold_reached=True,
                    elapsed_ms=(_time.monotonic() - rich_probe_started_monotonic) * 1000,
                    now=now,
                    not_newer_than=rich_probe_started_at,
                )
            if transitioned:
                await _broadcast_health_transition(
                    device.id,
                    "offline",
                    now,
                    "snmp_rich_poll_timeout",
                    alert_payload,
                )
            else:
                logger.info(
                    "忽略过期完整轮询离线结果：设备 %s 在请求开始后已通过健康探测确认可达",
                    device.id,
                )
            return
    except Exception as e:
        logger.warning(f"获取 {device.id} sysObjectID 失败: {e}")
        return

    lock = await _get_health_device_lock(device.id)
    async with lock:
        transitioned, alert_payload = await _persist_health_transition(
            device,
            reachable=True,
            threshold_reached=False,
            elapsed_ms=(_time.monotonic() - rich_probe_started_monotonic) * 1000,
            now=now,
        )
    if transitioned:
        await _broadcast_health_transition(
            device.id,
            "online",
            now,
            "snmp_rich_poll_recovery",
            alert_payload,
        )

    if profile is None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Device)
                .where(Device.id == device.id)
                .values(
                    system_oid=discovered_system_oid,
                    profile_id=None,
                    profile_version=None,
                    profile_evidence_version=None,
                    last_poll=now,
                    last_full_poll_status="unsupported",
                    last_status="online",
                )
            )
            await db.commit()
        await _broadcast_device_snapshot(
            device.id,
            timestamp=now,
            reason="unsupported_profile",
        )
        logger.warning(
            "设备 %s sysObjectID=%s 不匹配已接受的五个 Profile",
            device.id,
            discovered_system_oid,
        )
        return

    if profile.profile_id != "ccdc_legacy":
        await _poll_profile_device(device, profile, now)
        _clear_full_poll_retry(device.id)
        return

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
        if _raw_log_enabled and raw_value is not None:
            _poll_raw_logger.info(
                f"GET device={device.id} host={device.host} "
                f"oid={oid_cfg.name} type={type(raw_value).__name__} value={raw_value!r}"
            )
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

    # ── 轮询表类型 OID（CPU 终端模块 + CON 用户模块 + 端口）────────
    endpoint_data: dict[tuple, dict[str, tuple]] = {}
    if table_oid_configs:
        # key = (module_namespace, row_index) 避免 CON 和 CPU 行号碰撞
        walk_tasks = []
        for ep_cfg in table_oid_configs:
            col_oid = f"{ep_cfg.table_base_oid}.{ep_cfg.table_column}"
            col_oid = col_oid.replace("{sys_oid}", sys_oid)
            walk_tasks.append(_snmp_walk(device.host, device.port, device.community, col_oid))

        walk_results_list = await asyncio.gather(*walk_tasks, return_exceptions=True)

        for ep_cfg, walk_results in zip(table_oid_configs, walk_results_list):
            if isinstance(walk_results, Exception) or not isinstance(walk_results, dict):
                continue

            if _raw_log_enabled and walk_results:
                _poll_raw_logger.info(
                    f"WALK device={device.id} host={device.host} "
                    f"oid={ep_cfg.name} rows={len(walk_results)} "
                    f"values={[(k, type(v).__name__, repr(v)) for k, v in list(walk_results.items())[:10]]}"
                )

            # 从 category 推导 namespace: endpoint→cpu, con_endpoint→con, port→port
            namespace = {"endpoint": "cpu", "con_endpoint": "con", "port": "port"}.get(
                ep_cfg.category, ep_cfg.category
            )

            for full_oid, raw_value in walk_results.items():
                try:
                    row_index = int(full_oid.split(".")[-1])
                except ValueError:
                    continue

                value_str, value_num = parse_snmp_value(raw_value, ep_cfg.data_type, ep_cfg.enum_map)

                key = (namespace, row_index)
                if key not in endpoint_data:
                    endpoint_data[key] = {}
                endpoint_data[key][ep_cfg.name] = (value_str, value_num, ep_cfg)

        # 写入/更新终端（仅 cpu / con；port 不创建 endpoint 记录，只归档 metrics）
        _EP_NAMESPACES = {"cpu", "con"}
        async with AsyncSessionLocal() as db:
            # 关闭 autoflush：endpoint 循环中每次 db.get() 都会触发 autoflush，
            # 导致 SQLite 在同一 session 内出现并发写锁错误；全部积累到 commit() 统一写入
            db.sync_session.autoflush = False
            for (namespace, row_index), field_map in endpoint_data.items():
                ep_status_summary = {k: v[0] for k, v in field_map.items()}

                if namespace in _EP_NAMESPACES:
                    # Column 1 是厂商表里的 module index。部分型号上它可能等于面板接口位，
                    # 但 MIB 未证明它就是 portTable 的物理 portIndex。
                    module_index = row_index
                    if namespace == "cpu" and "ep_port" in field_map:
                        _, val_num, _ = field_map["ep_port"]
                        if val_num is not None: module_index = int(val_num)
                    elif namespace == "con" and "con_port" in field_map:
                        _, val_num, _ = field_map["con_port"]
                        if val_num is not None: module_index = int(val_num)

                    ep_id = f"{device.id}_{namespace}_{row_index}"
                    ep_name = (
                        ep_status_summary.get("ep_name")
                        or ep_status_summary.get("con_name")
                    )
                    existing = await db.get(Endpoint, ep_id)
                    if existing:
                        existing.last_status = ep_status_summary
                        existing.updated_at = now
                        existing.index = module_index
                        if ep_name:
                            existing.name = ep_name
                    else:
                        ep_name = ep_name or f"{namespace.upper()}-{module_index}"
                        db.add(Endpoint(
                            id=ep_id, device_id=device.id, name=ep_name,
                            index=module_index, module_type=namespace,
                            last_status=ep_status_summary,
                            updated_at=now, created_at=now,
                        ))
                else:
                    # port 等非终端类型：不创建 endpoint 行，metrics 使用 None endpoint_id
                    ep_id = None

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
                        ep_name_display = ep_status_summary.get("ep_name") or ep_status_summary.get("con_name") or (ep_id or f"{namespace}-{row_index}")
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

        # 聚合端口状态与模块接口位。ports 来自 portTable；module_occupancy 来自 CPU/CON 表。
        ports_map = {}
        module_occupancy = {"cpu": {}, "con": {}}
        port_occupancy = {}  # legacy: kept for old frontends, do not rely on it for CPU/CON mapping
        endpoint_id_list = set()

        for (namespace, row_index), field_map in endpoint_data.items():
            if namespace == "port":
                ports_map[row_index] = {k: v[0] for k, v in field_map.items()}
            elif namespace in ("cpu", "con"):
                module_index = row_index
                if namespace == "cpu" and "ep_port" in field_map:
                    module_index = int(field_map["ep_port"][1] or row_index)
                elif namespace == "con" and "con_port" in field_map:
                    module_index = int(field_map["con_port"][1] or row_index)

                status_key = "ep_device_status" if namespace == "cpu" else "con_device_status"
                status_value = field_map.get(status_key, ("offline", None, None))[0]
                name_key = "ep_name" if namespace == "cpu" else "con_name"
                module_entry = {
                    "type": namespace,
                    "status": status_value,
                    "row_index": row_index,
                    "module_index": module_index,
                    "endpoint_id": f"{device.id}_{namespace}_{row_index}",
                    "name": field_map.get(name_key, ("", None, None))[0],
                }
                module_occupancy[namespace][str(module_index)] = module_entry
                port_occupancy.setdefault(str(module_index), module_entry)
                endpoint_id_list.add(f"{device.id}_{namespace}_{row_index}")

        # 整理最终的设备指标快照
        endpoint_count_by_type = {
            "cpu": len(module_occupancy["cpu"]),
            "con": len(module_occupancy["con"]),
        }
        full_metrics = {
            "summary": device_status_summary,
            "ports": ports_map,
            "module_occupancy": module_occupancy,
            "port_occupancy": port_occupancy,
            "endpoint_count": endpoint_count_by_type,
        }
        ep_count = len(endpoint_id_list)

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
                last_poll=now,
                last_status=device_online_status,
                last_metrics=full_metrics,
                endpoint_count=ep_count,
                system_oid=profile.sys_object_id,
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                profile_evidence_version=profile.evidence_version,
                model_name=device.model_name or profile.product,
                last_full_poll_status="success",
            )
        )

        persisted_alerts = await _persist_alert_candidates(
            db,
            alerts_to_create,
            now,
        )

        await db.commit()
        alert_payloads = [
            serialize_alert(alert)
            for alert in persisted_alerts
        ]

    # ── WebSocket 广播 ──────────────────────────────────────────
    await _broadcast_device_snapshot(
        device.id,
        timestamp=now,
        reason="profile_poll_success",
    )
    await _broadcast_persisted_alerts(alert_payloads, now)
    _clear_full_poll_retry(device.id)

    logger.info(
        "设备 %s 轮询完成，写入 %s 条指标，新增 %s 条告警",
        device.id,
        len(metrics_to_insert),
        len(alert_payloads),
    )


async def run_poll_cycle():
    """轮询主循环：限流并发，并按 sysObjectID 选择五种 Profile。"""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        devices_result = await db.execute(select(Device).where(Device.is_active == True))
        active_devices = devices_result.scalars().all()
        devices = [
            device
            for device in active_devices
            if is_full_poll_eligible(device) and is_full_poll_due(device, now)
        ]

        oids_result = await db.execute(select(OIDRegistry).where(OIDRegistry.poll_enabled == True))
        oid_configs = oids_result.scalars().all()

    if not devices:
        logger.debug("没有到达各自轮询间隔的活跃设备，跳过完整轮询")
        return

    logger.info(
        "开始轮询周期: %s/%s 台设备到期, 并发上限 %s",
        len(devices), len(active_devices), CONCURRENCY_LIMIT,
    )
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def limited_poll(device):
        async with semaphore:
            try:
                await poll_device(device, oid_configs)
            except Exception as e:
                logger.error(f"设备 {device.id} 轮询异常: {e}", exc_info=True)

    await asyncio.gather(*[limited_poll(d) for d in devices], return_exceptions=True)
    logger.info(f"轮询周期完成: {len(devices)} 台设备")


async def poll_device_by_host(host: str):
    """按 IP 地址立即轮询该 IP 下所有活跃设备（供 Trap 触发使用）。
    同一 IP 可能有多台设备（端口不同），全部触发。
    带冷却期（TRAP_POLL_COOLDOWN 秒），防止 Trap 风暴与定时轮询并发写 SQLite。
    """
    now = _time.monotonic()
    if now - _trap_poll_last.get(host, 0) < TRAP_POLL_COOLDOWN:
        logger.debug(f"Trap 触发轮询 host={host} 冷却中，跳过（避免并发写冲突）")
        return
    _trap_poll_last[host] = now

    from sqlalchemy import select as sa_select
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_select(Device).where(Device.host == host, Device.is_active == True)
        )
        devices = result.scalars().all()
        if not devices:
            logger.debug(f"Trap 触发: 未找到 host={host} 的活跃设备，跳过即时轮询")
            return
        oids_result = await db.execute(
            sa_select(OIDRegistry).where(OIDRegistry.poll_enabled == True)
        )
        oid_configs = oids_result.scalars().all()

    logger.info(f"Trap 触发即时轮询: {len(devices)} 台设备 (host={host})")
    for device in devices:
        try:
            await poll_device(device, oid_configs)
        except Exception as e:
            logger.error(f"Trap 触发轮询异常 {device.id}: {e}", exc_info=True)
