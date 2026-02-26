#!/usr/bin/env python3
"""
端到端测试脚本：
  1. 启动 SNMP 模拟器（help/snmp_simulator.py 的简化版，集成到同一进程）
  2. 通过 API 注册设备（指向模拟器 127.0.0.1:10161）
  3. 触发一次轮询
  4. 查询 SQLite 验证数据写入
"""
import os
import sys
import asyncio
import json
import logging
import random
import threading
import time

# 将 backend 目录添加到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 强制使用 SQLite 测试模式
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("SQLITE_PATH", "kvm_test.db")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("test_e2e")


# ─── SNMP 模拟器（内嵌，不依赖 help/ 中的文件）──────────────────────

SIM_PORT = 10161  # 非特权端口
OID_BASE = "1.3.6.1.4.1.32828.3.257.16"


def build_oid_map():
    """构建 OID → value 映射（模拟真机数据）"""
    base = OID_BASE
    oid_map = {
        # 标准 MIB-2 节点
        "1.3.6.1.2.1.1.2.0": OID_BASE,                         # sysObjectID

        # 设备基础信息
        f"{base}.2.1.1.0": "4675",                             # deviceId
        f"{base}.2.1.2.0": "257",                              # deviceCl
        f"{base}.2.1.3.0": "ControlCenter-Compact-8C",         # deviceType
        f"{base}.2.1.4.0": "GD03217157",                       # serialNumber
        f"{base}.2.1.5.0": "0x000ff402455a",                   # mac0
        f"{base}.2.1.6.0": "0x000ff402455b",                   # mac1
        f"{base}.2.2.1.0": "1.7.000 (01165)",                  # firmwareVersion

        # 设备状态
        f"{base}.2.3.1.0":   1,                                 # mainPower=on
        f"{base}.2.3.2.0":   1,                                 # redundantPower=on
        f"{base}.2.3.3.0":   f"{random.uniform(30,50):.1f}",   # temperature
        f"{base}.2.3.500.0": f"{random.uniform(1.2,2.0):.2f}", # powerCurrent
        f"{base}.2.3.501.0": f"{random.uniform(11.5,12.5):.2f}",# powerVoltage
        f"{base}.2.3.502.0": str(random.randint(2800, 3200)),  # fan1
        f"{base}.2.3.503.0": str(random.randint(2800, 3200)),  # fan2
        f"{base}.2.3.504.0": str(random.randint(2800, 3200)),  # fan3
        f"{base}.2.3.505.0": str(random.randint(2800, 3200)),  # fan4
        f"{base}.2.3.508.0": str(random.randint(2800, 3200)),  # fan5
        f"{base}.2.3.509.0": str(random.randint(2800, 3200)),  # fan6
        f"{base}.2.3.506.0": 1,                                 # net_if0=up
        f"{base}.2.3.507.0": 0,                                 # net_if1=down
    }

    # 终端模块表 (2 个终端)
    target_col_map = {
        2: ("0x00060A37", "0x000170ED"),     # id
        3: ("0x00000401", "0x00000401"),     # class
        4: ("CPU-ID 00060A37", "CPU-ID 000170ED"),  # name
        5: (1, 2),                            # deviceStatus (online/ready)
        6: (0, 0),                            # mainPower
        7: (0, 0),                            # redundantPower
        8: ("39.0", "39.0"),                  # temperature
        9: (0, 0),                            # consolePS2
        10: (0, 0),                           # consoleUSB
        11: (0, 0),                           # targetPS2
        12: (2, 0),                           # targetUsbHid (initialized/not)
        13: (1, 0),                           # targetVideoCable (connected/not)
        14: (0, 0),                           # targetVideoCable1
        15: (0, 0),                           # targetVideoCable2
        16: (2, 0),                           # targetVideoSignal (dvisl/none)
        17: (0, 0),                           # targetVideoSignal1
        18: (0, 0),                           # targetVideoSignal2
        19: (0, 0),                           # targetPower
        20: (0, 0),                           # targetAccess (local)
        21: (0, 0),                           # sfpTxPower
        22: (0, 0),                           # sfpRxPower
        23: ("", ""),                          # sfpType
        24: (0, 0),                           # netIf0
    }
    for col, (val1, val2) in target_col_map.items():
        ep_base = "1.3.6.1.4.1.32828.3.257.16.1.2.2.3.1000.1"
        oid_map[f"{ep_base}.{col}.1"] = val1
        oid_map[f"{ep_base}.{col}.2"] = val2

    # 端口表 (8 ports)
    port_data = {
        1: (3, 0, 0, 0, ""),   # up
        2: (2, 0, 0, 0, ""),   # down
        3: (2, 0, 0, 0, ""),
        4: (2, 0, 0, 0, ""),
        5: (3, 0, 0, 0, ""),   # up
        6: (3, 0, 0, 0, ""),   # up
        7: (2, 0, 0, 0, ""),
        8: (2, 0, 0, 0, ""),
    }
    port_cols = [2, 3, 4, 5, 6]
    for row, vals in port_data.items():
        for col_idx, val in zip(port_cols, vals):
            oid_map[f"{base}.2.3.1000.1.{col_idx}.{row}"] = val

    return oid_map


def start_simulator():
    """在后台线程启动 SNMP 模拟器（socket + pysnmp SNMPv2c PDU 实现）"""
    import socket
    from pysnmp.proto import api as snmp_api
    from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
    from pyasn1.type.univ import ObjectIdentifier, Integer, OctetString, Null

    pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

    def find_next_oid(sorted_oids, current_tuple):
        for oid_t, oid_s, val in sorted_oids:
            if oid_t > current_tuple:
                return oid_s, val
        return None, None

    def to_snmp_val(val):
        if isinstance(val, int):
            return pMod.Integer(val)
        return pMod.OctetString(str(val))

    def handle_request(data):
        try:
            msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            community = msg.getComponentByPosition(1)
            pdu = snmp_api.decodeMessageVersion(data)

            # 重新解码以获取 PDU
            req_msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            req_pdu = pMod.apiMessage.getPDU(req_msg)

            oid_map = build_oid_map()
            sorted_oids = sorted(
                [(tuple(int(x) for x in k.split(".")), k, v) for k, v in oid_map.items()],
                key=lambda x: x[0]
            )

            # 构建响应 PDU
            resp_msg = pMod.Message()
            pMod.apiMessage.setDefaults(resp_msg)
            pMod.apiMessage.setCommunity(resp_msg, community)

            resp_pdu = pMod.GetResponsePDU()
            pMod.apiPDU.setDefaults(resp_pdu)
            pMod.apiPDU.setRequestID(resp_pdu, pMod.apiPDU.getRequestID(req_pdu))

            req_var_binds = pMod.apiPDU.getVarBinds(req_pdu)
            resp_var_binds = []

            # 检测请求类型
            pdu_tag = req_pdu.tagSet
            is_get = (pdu_tag == pMod.GetRequestPDU.tagSet)
            is_bulk = (pdu_tag == pMod.GetBulkRequestPDU.tagSet)
            is_next = (pdu_tag == pMod.GetNextRequestPDU.tagSet)

            if is_get:
                for oid, val in req_var_binds:
                    oid_str = str(oid)
                    # 处理可能的 "." 开头
                    if oid_str.startswith("."):
                        oid_str = oid_str[1:]
                    if oid_str in oid_map:
                        resp_var_binds.append((oid, to_snmp_val(oid_map[oid_str])))
                    else:
                        resp_var_binds.append((oid, pMod.NoSuchObject()))

            elif is_next:
                for oid, val in req_var_binds:
                    oid_str = str(oid)
                    if oid_str.startswith("."):
                        oid_str = oid_str[1:]
                    current_tuple = tuple(int(x) for x in oid_str.split("."))
                    ns, nv = find_next_oid(sorted_oids, current_tuple)
                    if ns:
                        resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                    else:
                        resp_var_binds.append((oid, pMod.EndOfMibView()))

            elif is_bulk:
                non_repeaters = pMod.apiBulkPDU.getNonRepeaters(req_pdu)
                max_repetitions = pMod.apiBulkPDU.getMaxRepetitions(req_pdu)

                for i, (oid, val) in enumerate(req_var_binds):
                    oid_str = str(oid)
                    if oid_str.startswith("."):
                        oid_str = oid_str[1:]
                    current_tuple = tuple(int(x) for x in oid_str.split("."))

                    if i < non_repeaters:
                        ns, nv = find_next_oid(sorted_oids, current_tuple)
                        if ns:
                            resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                        else:
                            resp_var_binds.append((oid, pMod.EndOfMibView()))
                    else:
                        ct = current_tuple
                        for _ in range(max_repetitions):
                            ns, nv = find_next_oid(sorted_oids, ct)
                            if ns:
                                resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                                ct = tuple(int(x) for x in ns.split("."))
                            else:
                                resp_var_binds.append((oid, pMod.EndOfMibView()))
                                break

            pMod.apiPDU.setVarBinds(resp_pdu, resp_var_binds)
            pMod.apiMessage.setPDU(resp_msg, resp_pdu)

            return ber_encoder.encode(resp_msg)
        except Exception as e:
            logger.error(f"模拟器处理请求失败: {e}", exc_info=True)
            return None

    def run_sim():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", SIM_PORT))
        sock.settimeout(1.0)
        logger.info(f"SNMP 模拟器已启动: 0.0.0.0:{SIM_PORT}")
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                response = handle_request(data)
                if response:
                    sock.sendto(response, addr)
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"模拟器错误: {e}")

    t = threading.Thread(target=run_sim, daemon=True)
    t.start()
    time.sleep(0.5)
    return t




# ─── 测试主逻辑 ──────────────────────────────────────────────

async def run_test():
    """主测试流程"""

    # 清理旧测试数据库
    db_path = os.environ.get("SQLITE_PATH", "kvm_test.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"已清理旧 DB: {db_path}")

    # 步骤 1: 启动模拟器
    logger.info("=" * 60)
    logger.info("步骤 1: 启动 SNMP 模拟器")
    start_simulator()

    # 步骤 2: 初始化数据库和种子数据
    logger.info("=" * 60)
    logger.info("步骤 2: 初始化数据库")
    from app.database import engine, AsyncSessionLocal, Base
    from app.models.user import User
    from app.models.device import Device
    from app.models.endpoint import Endpoint
    from app.models.oid_registry import OIDRegistry
    from app.models.status_metric import StatusMetric
    from app.models.alert import Alert
    from app.main import _init_database, _seed_data

    await _init_database()
    await _seed_data()

    # 步骤 3: 通过代码创建测试设备（指向模拟器）
    logger.info("=" * 60)
    logger.info("步骤 3: 创建测试设备")
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Device).where(Device.id == "test_kvm_01"))
        if not result.scalar_one_or_none():
            db.add(Device(
                id="test_kvm_01",
                name="测试KVM-01 (模拟器)",
                host="127.0.0.1",
                port=SIM_PORT,
                community="public",
                is_active=True,
                poll_interval=10,
            ))
            await db.commit()
            logger.info("设备 'test_kvm_01' 创建成功")

    # 步骤 4: 执行轮询
    logger.info("=" * 60)
    logger.info("步骤 4: 执行 SNMP 轮询")
    from app.snmp.poller import run_poll_cycle
    await run_poll_cycle()

    # 步骤 5: 验证结果
    logger.info("=" * 60)
    logger.info("步骤 5: 验证数据写入")


    async with AsyncSessionLocal() as db:
        # 检查 OID 注册表
        oid_count = (await db.execute(select(OIDRegistry))).scalars().all()
        logger.info(f"  OID 注册表: {len(oid_count)} 条")

        # 检查设备
        devices = (await db.execute(select(Device))).scalars().all()
        for d in devices:
            logger.info(f"  设备: {d.id} | 名称: {d.name} | 状态: {d.last_status} | 最后轮询: {d.last_poll}")

        # 检查终端
        endpoints = (await db.execute(select(Endpoint))).scalars().all()
        logger.info(f"  终端数量: {len(endpoints)}")
        for ep in endpoints:
            logger.info(f"    终端: {ep.id} | 名称: {ep.name} | 状态: {json.dumps(ep.last_status, ensure_ascii=False) if ep.last_status else 'N/A'}")

        # 检查指标
        metrics = (await db.execute(select(StatusMetric))).scalars().all()
        logger.info(f"  指标数量: {len(metrics)}")

        # 按 OID 名分组统计
        from collections import Counter
        metric_names = Counter(m.oid_name for m in metrics)
        for name, count in sorted(metric_names.items()):
            sample = next((m for m in metrics if m.oid_name == name), None)
            if sample:
                logger.info(f"    {name:35s} x{count}  →  value_str={sample.value_str}  value_num={sample.value_num}")

        # 检查告警
        alerts = (await db.execute(select(Alert))).scalars().all()
        logger.info(f"  告警数量: {len(alerts)}")
        for a in alerts:
            logger.info(f"    [{a.severity}] {a.message}")

    # 步骤 6: 验证 SNMP GET 直连
    logger.info("=" * 60)
    logger.info("步骤 6: 直连 SNMP GET 测试")
    from app.snmp.poller import _snmp_get
    test_oids = [
        ("device_type", f"{OID_BASE}.2.1.3.0"),
        ("temperature", f"{OID_BASE}.2.3.3.0"),
        ("main_power",  f"{OID_BASE}.2.3.1.0"),
        ("fan1",        f"{OID_BASE}.2.3.502.0"),
    ]
    for name, oid in test_oids:
        _, val = await _snmp_get("127.0.0.1", SIM_PORT, "public", oid)
        logger.info(f"  GET {name:20s} = {val}")

    # 总结
    logger.info("=" * 60)
    ok = len(metrics) > 0 and len(endpoints) > 0
    if ok:
        logger.info("✅ 端到端测试通过！后端成功对接 SNMP 模拟器，数据写入 SQLite 正常。")
        logger.info(f"   - 写入 {len(metrics)} 条指标")
        logger.info(f"   - 发现 {len(endpoints)} 个终端")
        logger.info(f"   - 触发 {len(alerts)} 条告警")
    else:
        logger.error("❌ 测试失败！请检查日志。")
        return False

    return True


if __name__ == "__main__":
    result = asyncio.run(run_test())
    sys.exit(0 if result else 1)
