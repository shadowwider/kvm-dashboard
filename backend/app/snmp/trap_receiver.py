"""
SNMP Trap 接收器（UDP:162）。
接收 KVM 设备发送的 Trap 通知，解析并写入告警表，同时广播到前端。
"""
import asyncio
import logging
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


def _start_trap_receiver(loop: asyncio.AbstractEventLoop):
    """在事件循环中启动 Trap 监听器"""
    snmp_engine = SnmpEngine()

    # 传输配置
    config.addTransport(
        snmp_engine,
        udp.domainName,
        udp.UdpTransport().openServerMode(("0.0.0.0", settings.snmp_trap_port)),
    )

    # SNMPv2c community
    config.addV1System(snmp_engine, "trap-area", settings.snmp_default_community)

    def trap_callback(snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        """Trap 到达时的回调"""
        now = datetime.now(timezone.utc)
        binds = []
        source_ip = "unknown"

        try:
            transport_domain, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(state_reference)
            source_ip = str(transport_address[0])
        except Exception:
            pass

        for oid, val in var_binds:
            binds.append({"oid": str(oid), "value": val.prettyPrint()})

        message = f"Trap from {source_ip}: " + "; ".join(f"{b['oid']}={b['value']}" for b in binds[:3])
        logger.warning(f"收到 SNMP Trap: {message}")

        # 异步写入数据库
        asyncio.run_coroutine_threadsafe(_save_trap(source_ip, message, binds, now), loop)

    ntfrcv.NotificationReceiver(snmp_engine, trap_callback)
    snmp_engine.transportDispatcher.jobStarted(1)

    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except Exception as e:
        logger.error(f"Trap 接收器错误: {e}")
    finally:
        snmp_engine.transportDispatcher.closeDispatcher()


async def _save_trap(source_ip: str, message: str, binds: list, timestamp: datetime):
    """异步保存 Trap 到数据库并广播"""
    async with AsyncSessionLocal() as db:
        alert = Alert(
            device_id=source_ip,  # 用 IP 标识，后续可关联到设备表
            oid_name="trap",
            alert_type="trap",
            severity="warning",
            message=message,
            raw_value=str(binds[:5]),
            created_at=timestamp,
        )
        db.add(alert)
        await db.commit()

    await ws_manager.broadcast({
        "type": "trap_received",
        "source_ip": source_ip,
        "message": message,
        "binds": binds[:10],
        "timestamp": timestamp.isoformat(),
    })


async def start_trap_receiver():
    """在后台线程中启动同步 Trap 监听器"""
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
