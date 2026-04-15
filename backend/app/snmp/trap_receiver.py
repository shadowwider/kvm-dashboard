"""
SNMP Trap 接收器（UDP:162）。
接收 G&D KVM 设备发送的 Trap 通知（GUD-GENERALTRAPS-MIB），
解析 level/message varbind，写入告警表，广播前端，并将原始数据记录到文件。

G&D 通用 Trap 格式（GUD-GENERALTRAPS-MIB）：
  Trap OID:  1.3.6.1.4.1.32828.5.0.4
  VarBinds:
    1.3.6.1.4.1.32828.5.1.0.2  level    整数 (0=Emergency .. 5=Notice)
    1.3.6.1.4.1.32828.5.1.0.3  message  字符串描述
"""
import asyncio
import logging
import logging.handlers
import os
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


_init_raw_logger()

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

# G&D varbind OID 中出现的标志串（唯一标识 level / message 字段）
_LEVEL_OID_MARKER   = '32828.5.1.0.2'
_MESSAGE_OID_MARKER = '32828.5.1.0.3'


def _start_trap_receiver(main_loop: asyncio.AbstractEventLoop):
    """在后台线程中启动 SNMP Trap 监听（独立事件循环）"""
    thread_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(thread_loop)

    snmp_engine = SnmpEngine()
    config.addTransport(
        snmp_engine,
        udp.domainName,
        udp.UdpTransport().openServerMode(("0.0.0.0", settings.snmp_trap_port)),
    )
    config.addV1System(snmp_engine, "trap-area", settings.snmp_default_community)

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
        raw_binds: list[dict] = []
        trap_level: int | None = None
        trap_message: str | None = None

        for oid, val in var_binds:
            oid_str = str(oid)
            val_str = val.prettyPrint()
            raw_binds.append({'oid': oid_str, 'value': val_str})

            if _LEVEL_OID_MARKER in oid_str:
                try:
                    trap_level = int(val_str)
                except (ValueError, TypeError):
                    pass
            elif _MESSAGE_OID_MARKER in oid_str:
                trap_message = val_str

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

    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except Exception as e:
        logger.error(f"Trap 接收器错误: {e}")
    finally:
        snmp_engine.transportDispatcher.closeDispatcher()


async def _save_trap(
    source_ip: str,
    message: str,
    severity: str,
    binds: list[dict],
    timestamp: datetime,
):
    """异步写库并广播 WebSocket"""
    async with AsyncSessionLocal() as db:
        db.add(Alert(
            device_id=source_ip,
            oid_name="trap",
            alert_type="trap",
            severity=severity,
            message=message,
            raw_value=str(binds),   # 全量 varbind 原始数据
            created_at=timestamp,
        ))
        await db.commit()

    await ws_manager.broadcast({
        "type": "trap_received",
        "source_ip": source_ip,
        "message": message,
        "severity": severity,
        "binds": binds,             # 前端可访问原始数据
        "timestamp": timestamp.isoformat(),
    })


async def start_trap_receiver():
    """在后台守护线程中启动同步 Trap 监听器"""
    import threading
    loop = asyncio.get_event_loop()
    thread = threading.Thread(
        target=_start_trap_receiver,
        args=(loop,),
        daemon=True,
        name="snmp-trap-receiver",
    )
    thread.start()
    logger.info(f"SNMP Trap 接收器已启动，监听 UDP:{settings.snmp_trap_port}")
