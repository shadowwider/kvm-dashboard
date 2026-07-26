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
from sqlalchemy import select, update, insert
from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.status_metric import StatusMetric
from app.models.alert import Alert
from app.snmp.parser import parse_snmp_value, is_alert_triggered
from app.websocket.hub import ws_manager
from app.config import get_settings as _get_settings

logger = logging.getLogger(__name__)

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
        maxBytes=20 * 1024 * 1024,   # 20 MB per file
        backupCount=10,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
    _poll_raw_logger.addHandler(handler)
    _poll_raw_logger.setLevel(logging.DEBUG)
    _poll_raw_logger.propagate = False


_init_poll_raw_logger()

# ─── 配置 ─────────────────────────────────────────────────────────
CONCURRENCY_LIMIT = 20      # 同时最多轮询 N 台设备
SNMP_TIMEOUT = 3             # 完整指标轮询的 SNMP 请求超时 (秒)
SNMP_RETRIES = 1             # 完整指标轮询的超时重试次数
BULK_MAX_REPETITIONS = 25    # GETBULK 每批返回行数
WALK_MAX_ITERATIONS = 100    # WALK 防止无限循环
ALERT_DEDUP_MINUTES = 10     # 告警去重窗口 (分钟)
BATCH_INSERT_SIZE = 5000     # 每批 INSERT 行数
TRAP_POLL_COOLDOWN = 10      # Trap 触发轮询冷却时间 (秒)，避免与定时轮询并发写冲突
SYS_OBJECT_ID_OID = "1.3.6.1.2.1.1.2.0"

# 轻量路径与完整指标轮询隔离：可达性探测不执行 WALK/写指标；可选状态列探测仅查询三列。
_health_failures: dict[str, int] = {}
_health_port_statuses: dict[str, dict[str, str]] = {}
_health_device_locks: dict[str, asyncio.Lock] = {}
_endpoint_status_locks: dict[str, asyncio.Lock] = {}
_health_device_locks_guard = asyncio.Lock()
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
}

# ─── SnmpEngine 池 ────────────────────────────────────────────────
_engine_pool: list[SnmpEngine] = []
_engine_lock = asyncio.Lock()

# ─── Trap 触发轮询冷却表（host → 上次触发时间戳）────────────────────
import time as _time
_trap_poll_last: dict[str, float] = {}


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


async def _snmp_get(
    host: str,
    port: int,
    community: str,
    oid: str,
    *,
    timeout: float = SNMP_TIMEOUT,
    retries: int = SNMP_RETRIES,
) -> tuple[str, any]:
    """单个 OID GET 查询，返回 (oid, raw_value)。"""
    engine = await _get_engine()
    failed = False
    try:
        error_indication, error_status, error_index, var_binds = await getCmd(
            engine,
            CommunityData(community, mpModel=1),
            UdpTransportTarget((host, port), timeout=timeout, retries=retries),
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


async def _snmp_walk(
    host: str,
    port: int,
    community: str,
    base_oid: str,
    *,
    timeout: float = SNMP_TIMEOUT + 2,
    retries: int = SNMP_RETRIES,
    max_iterations: int = WALK_MAX_ITERATIONS,
) -> dict[str, any]:
    """SNMP WALK via pysnmp v6 bulkCmd (SnmpEngine 复用)。"""
    engine = await _get_engine()
    results = {}
    next_oid = base_oid
    base_tuple = tuple(int(x) for x in base_oid.lstrip(".").split("."))
    failed = False
    try:
        for iteration in range(max_iterations):
            error_indication, error_status, error_index, var_bind_table = await bulkCmd(
                engine,
                CommunityData(community, mpModel=1),
                UdpTransportTarget((host, port), timeout=timeout, retries=retries),
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


async def _get_health_device_lock(device_id: str) -> asyncio.Lock:
    async with _health_device_locks_guard:
        return _health_device_locks.setdefault(device_id, asyncio.Lock())


async def _broadcast_health_transition(
    device_id: str,
    status: str,
    now: datetime,
    reason: str,
):
    await ws_manager.broadcast({
        "type": "device_update",
        "device_id": device_id,
        "online_status": status,
        "reachability": status,
        "reason": reason,
        "last_health_check": now.isoformat(),
        "timestamp": now.isoformat(),
    })


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
    )
    elapsed_ms = (_time.monotonic() - started) * 1000
    reachable = raw_sys_oid is not None
    transitioned = False
    now = datetime.now(timezone.utc)

    lock = await _get_health_device_lock(device.id)
    async with lock:
        if reachable:
            _health_failures.pop(device.id, None)
            # 健康周期加载的快照已经不是 offline 时，无需每秒访问数据库。
            if device.last_status == "offline":
                async with AsyncSessionLocal() as db:
                    current = await db.get(Device, device.id)
                    if current and current.last_status == "offline":
                        await db.execute(
                            update(Device).where(Device.id == device.id).values(
                                last_status="online", last_health_check=now
                            )
                        )
                        await db.commit()
                        transitioned = True
            if transitioned:
                logger.warning(
                    "device_health_recovered device_id=%s host=%s elapsed_ms=%.1f",
                    device.id, device.host, elapsed_ms,
                )
                await _broadcast_health_transition(device.id, "online", now, "snmp_health_probe_recovered")
        else:
            failures = _health_failures.get(device.id, 0) + 1
            _health_failures[device.id] = failures
            # 健康周期加载的快照已是离线时，不访问数据库或重复广播。
            if failures >= settings.snmp_health_failure_threshold and device.last_status != "offline":
                async with AsyncSessionLocal() as db:
                    current = await db.get(Device, device.id)
                    if current and current.last_status != "offline":
                        await db.execute(
                            update(Device).where(Device.id == device.id).values(
                                last_status="offline", last_health_check=now
                            )
                        )
                        await db.commit()
                        transitioned = True
                if transitioned:
                    logger.warning(
                        "device_health_offline device_id=%s host=%s failures=%s elapsed_ms=%.1f",
                        device.id, device.host, failures, elapsed_ms,
                    )
                    await _broadcast_health_transition(device.id, "offline", now, "snmp_health_probe_timeout")

    return reachable, transitioned, elapsed_ms


async def probe_device_endpoint_statuses(device_id: str):
    """按设备 ID 复核 CPU/CON 与物理端口状态，供已验证 Trap 触发。

    此函数不是一秒健康循环的一部分；它只在 Trap 到达后执行。
    """
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
    if not device or not device.is_active:
        return
    await _probe_endpoint_statuses(device)


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
                # 仅扫描三个状态列（CPU、CON、物理端口），使模块/网线事件无需等待完整 WALK。
                if reachable and settings.snmp_endpoint_status_poll_enabled:
                    await _probe_endpoint_statuses(device)
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
    # 每台设备在可达后还会并发查询 3 个单批状态列；这些查询不能从 SLO 容量估算中忽略。
    per_device_budget = health_timeout_budget + settings.snmp_health_timeout
    estimated_scan_seconds = ((len(devices) + settings.snmp_health_concurrency - 1) // settings.snmp_health_concurrency) * per_device_budget
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
                "reachability": "offline",
                "reason": "snmp_rich_poll_timeout",
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
    if table_oid_configs:
        # key = (module_namespace, row_index) 避免 CON 和 CPU 行号碰撞
        endpoint_data: dict[tuple, dict[str, tuple]] = {}

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
                endpoint_count=ep_count
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
        # 完整轮询成功同样要清除前端的父设备离线覆盖状态。
        "reachability": "online",
        "status": device_status_summary,
        "last_metrics": full_metrics,
        "endpoint_count": ep_count,
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
