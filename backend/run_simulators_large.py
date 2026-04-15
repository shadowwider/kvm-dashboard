#!/usr/bin/env python3
"""
KVM 仿真器 — 3台交换机，每台 4 CPU + 36 CON
状态每 10 秒动态更新一次，模拟真实设备的抖动、上下线、温度漂移等。
"""
import os
import sys
import asyncio
import logging
import random
import threading
import time
import socket
from pysnmp.proto import api as snmp_api
from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("simulators_large")

OID_BASE = "1.3.6.1.4.1.32828.3.257.16"

# ─── SNMP Trap 发送目标（G&D GUD-GENERALTRAPS-MIB 格式）──────────────
TRAP_TARGET_HOST = os.environ.get("TRAP_TARGET_HOST", "127.0.0.1")
TRAP_TARGET_PORT = int(os.environ.get("SNMP_TRAP_PORT", "10162"))
TRAP_COMMUNITY   = os.environ.get("SNMP_COMMUNITY", "public")

_TRAP_NOTIF_OID  = "1.3.6.1.4.1.32828.5.0.4"   # G&D GeneralTrap notification OID
_TRAP_LEVEL_OID  = "1.3.6.1.4.1.32828.5.1.0.2"  # level varbind
_TRAP_MSG_OID    = "1.3.6.1.4.1.32828.5.1.0.3"  # message varbind
_SYS_UPTIME_OID  = "1.3.6.1.2.1.1.3.0"
_SNMPTRAPOID_OID = "1.3.6.1.6.3.1.1.4.1.0"


def _oid_tup(s: str) -> tuple:
    return tuple(int(x) for x in s.strip('.').split('.'))


def _send_trap(level: int, message: str):
    """Build and send G&D format SNMPv2c trap via UDP (synchronous, thread-safe).

    Level mapping (GUD-GENERALTRAPS-MIB):
      0=Emergency, 1=Alert, 2=Critical → critical severity
      3=Error,     4=Warning           → warning severity
      5=Notice                         → info severity
    """
    try:
        from pysnmp.proto.rfc1905 import SNMPv2TrapPDU
        from pysnmp.proto.rfc1902 import TimeTicks

        pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

        trap_msg = pMod.Message()
        pMod.apiMessage.setDefaults(trap_msg)
        pMod.apiMessage.setCommunity(trap_msg, TRAP_COMMUNITY)

        trap_pdu = SNMPv2TrapPDU()
        pMod.apiPDU.setDefaults(trap_pdu)

        uptime = int(time.monotonic() * 100)   # hundredths of seconds (TimeTicks)

        var_binds = [
            (ObjectIdentifier(_oid_tup(_SYS_UPTIME_OID)),   TimeTicks(uptime)),
            (ObjectIdentifier(_oid_tup(_SNMPTRAPOID_OID)),   pMod.ObjectIdentifier(_oid_tup(_TRAP_NOTIF_OID))),
            (ObjectIdentifier(_oid_tup(_TRAP_LEVEL_OID)),    pMod.Integer(level)),
            (ObjectIdentifier(_oid_tup(_TRAP_MSG_OID)),      pMod.OctetString(message.encode('utf-8'))),
        ]
        pMod.apiPDU.setVarBinds(trap_pdu, var_binds)
        pMod.apiMessage.setPDU(trap_msg, trap_pdu)

        data = ber_encoder.encode(trap_msg)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(data, (TRAP_TARGET_HOST, TRAP_TARGET_PORT))

        logger.info(
            f"SNMP Trap → {TRAP_TARGET_HOST}:{TRAP_TARGET_PORT} "
            f"level={level} msg={message!r}"
        )
    except Exception as e:
        logger.warning(f"_send_trap failed: {e}")

NUM_CPU = 3
NUM_CON = 3
STATE_UPDATE_INTERVAL = 10  # 秒

DISPLAY_MODELS = [
    "Dell-U2722D", "LG-27UN880", "ASUS-PA279CV", "BenQ-PD2705U",
    "HP-Z27k-G3", "Samsung-F27T850", "LG-32UN880", "Dell-U3223QE",
    "ViewSonic-VP2768", "Philips-279P1", "AOC-U27G3X", "Eizo-EV2795",
]

# CPU video signal enum: 0=none,1=vga,2=dvisl,3=dvidl,4=dmdp,5=dp,6=hdmi
VIDEO_SIGNALS = [1, 2, 3, 5, 6]  # 常见信号类型


# ─── 状态初始化 ─────────────────────────────────────────────────────

def _init_cpu(sw_id, idx):
    """初始化单个 CPU 模块状态"""
    return {
        "id": f"CPU-{sw_id}-{idx:03d}",
        "name": f"CPU-HOST-SW{sw_id}-{idx:03d}",
        "device_status": random.choices([1, 2, 0], weights=[88, 8, 4])[0],
        "main_power": 1,
        "redundant_power": random.choice([0, 1]),
        "temperature": round(random.uniform(38, 52), 1),
        "target_usb_hid": random.choice([0, 2]),     # 0=notConnected, 2=initialized
        "target_video_cable": random.choice([0, 1]),  # 0=notConnected, 1=connected
        "target_video_signal": random.choice(VIDEO_SIGNALS + [0]),
        "target_power": random.choice([0, 1]),
        "target_access": random.choices([0, 1, 2, 3], weights=[60, 25, 10, 5])[0],
        "sfp_tx_power": random.randint(440, 530),
        "sfp_rx_power": random.randint(400, 500),
        "net_if0": 1,
    }


def _init_con(sw_id, idx):
    """初始化单个 CON 模块状态"""
    display = random.choice(DISPLAY_MODELS)
    online = random.choices([1, 2, 0], weights=[82, 8, 10])[0]
    # console_ps2/usb: 0=none,1=keyboard,2=mouse,3=keyboardMouse
    # 大多数操作员站接键盘+鼠标(3)，少数只接键盘(1)或未接(0)
    km = random.choices([3, 1, 0], weights=[75, 15, 10])[0] if online == 1 else 0
    return {
        "id": f"CON-{sw_id}-{idx:03d}",
        "name": f"CON-USER-SW{sw_id}-{idx:03d}",
        "device_status": online,
        "main_power": 1,
        "redundant_power": 0,
        "temperature": round(random.uniform(33, 47), 1),
        "console_ps2": km,
        "console_usb": km,
        "display_conn": 1 if online == 1 else 0,
        "display_type": display,
        "freeze": 0,
        "sfp_tx_power": random.randint(480, 540),
        "sfp_rx_power": random.randint(460, 510),
        "sfp_tx_power1": random.randint(480, 540),
        "sfp_rx_power1": random.randint(460, 510),
        "active_tx_port": random.choice([1, 2]),
        "net_if0": 1 if online != 0 else 0,
        # 过渡计数器：连续几轮保持离线后才恢复，模拟真实断线时长
        "_offline_ticks": random.randint(0, 2) if online == 0 else 0,
    }


def init_switch_state(sw_id):
    """初始化整台交换机状态"""
    return {
        "sw_id": sw_id,
        "temperature": round(random.uniform(38, 48), 1),
        "main_power": 1,
        "redundant_power": random.choice([0, 1]),
        "fan1": random.randint(2900, 3200),
        "fan2": random.randint(2900, 3200),
        "fan3": random.randint(2900, 3200),
        "fan4": random.randint(2900, 3200),
        "net_if0": 1,
        "net_if1": 0,
        "cpus": [_init_cpu(sw_id, i) for i in range(1, NUM_CPU + 1)],
        "cons": [_init_con(sw_id, i) for i in range(1, NUM_CON + 1)],
        "_lock": threading.Lock(),
    }


# ─── 状态更新（每 10s 调用一次） ────────────────────────────────────

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def update_switch_state(state) -> list[tuple[int, str]]:
    """对交换机状态做一次真实的随机漂移。返回需要发送的 Trap 事件列表 [(level, message)]。

    Level 含义（GUD-GENERALTRAPS-MIB）：
      3=Error（设备掉线）, 5=Notice（设备恢复上线）
    """
    events: list[tuple[int, str]] = []

    with state["_lock"]:
        # 机箱温度小幅漂移
        state["temperature"] = _clamp(
            round(state["temperature"] + random.uniform(-0.8, 0.8), 1), 35, 58
        )
        # 风扇转速抖动 ±100 rpm
        for f in ["fan1", "fan2", "fan3", "fan4"]:
            state[f] = _clamp(state[f] + random.randint(-100, 100), 2600, 3500)

        # ── CPU 模块更新 ──────────────────────────────────────────
        for cpu in state["cpus"]:
            prev_st = cpu["device_status"]

            # 状态转移
            if prev_st == 0:  # offline → 有概率恢复
                if random.random() < 0.35:
                    cpu["device_status"] = random.choice([1, 2])
                    cpu["target_power"] = 1
                    cpu["target_video_cable"] = 1
                    cpu["target_video_signal"] = random.choice(VIDEO_SIGNALS)
                    events.append((5, f"CPU module {cpu['id']} came online"))
            elif prev_st in (1, 2):
                r = random.random()
                if r < 0.03:   # 3% 概率掉线
                    cpu["device_status"] = 0
                    cpu["target_power"] = 0
                    cpu["target_video_cable"] = 0
                    cpu["target_video_signal"] = 0
                    events.append((3, f"CPU module {cpu['id']} went offline"))
                elif r < 0.08:  # 5% 概率在 online/ready 之间切换
                    cpu["device_status"] = 2 if prev_st == 1 else 1

            # 温度漂移
            cpu["temperature"] = _clamp(
                round(cpu["temperature"] + random.uniform(-1.0, 1.0), 1), 30, 65
            )
            # SFP 抖动
            cpu["sfp_tx_power"] = _clamp(cpu["sfp_tx_power"] + random.randint(-8, 8), 380, 580)
            cpu["sfp_rx_power"] = _clamp(cpu["sfp_rx_power"] + random.randint(-8, 8), 350, 540)

            # online 状态下偶尔切换视频接入方式
            if cpu["device_status"] == 1 and random.random() < 0.05:
                cpu["target_access"] = random.choices([0, 1, 2, 3], weights=[60, 25, 10, 5])[0]

        # ── CON 模块更新 ──────────────────────────────────────────
        for con in state["cons"]:
            prev_st = con["device_status"]

            if prev_st == 0:
                con["_offline_ticks"] += 1
                # 离线至少 1 轮（10s），之后以 25% 概率恢复
                if con["_offline_ticks"] >= 1 and random.random() < 0.25:
                    con["device_status"] = 1
                    con["display_conn"] = 1
                    con["freeze"] = 0
                    con["net_if0"] = 1
                    con["console_ps2"] = random.choices([3, 1, 0], weights=[75, 15, 10])[0]
                    con["console_usb"] = con["console_ps2"]
                    con["_offline_ticks"] = 0
                    events.append((5, f"CON module {con['id']} came online"))
            else:
                r = random.random()
                if r < 0.05:    # 5% 掉线
                    con["device_status"] = 0
                    con["display_conn"] = 0
                    con["freeze"] = 0
                    con["net_if0"] = 0
                    con["console_ps2"] = 0
                    con["console_usb"] = 0
                    con["_offline_ticks"] = 0
                    events.append((3, f"CON module {con['id']} went offline"))
                elif r < 0.08:  # 3% ready/online 互切
                    con["device_status"] = 2 if prev_st == 1 else 1
                elif r < 0.10:  # 2% 显示器断开（设备还在线，非关键事件，不发 Trap）
                    con["display_conn"] = 0 if con["display_conn"] == 1 else 1
                elif r < 0.12:  # 2% 画面冻结（非关键事件，不发 Trap）
                    con["freeze"] = 1 if con["freeze"] == 0 else 0

            # 温度漂移
            con["temperature"] = _clamp(
                round(con["temperature"] + random.uniform(-0.8, 0.8), 1), 28, 58
            )
            # SFP 抖动（CON 有两路光口）
            for k in ["sfp_tx_power", "sfp_rx_power", "sfp_tx_power1", "sfp_rx_power1"]:
                con[k] = _clamp(con[k] + random.randint(-6, 6), 420, 580)

            # 偶尔切换主备光口
            if con["device_status"] != 0 and random.random() < 0.02:
                con["active_tx_port"] = 2 if con["active_tx_port"] == 1 else 1

    return events


def state_updater(all_states):
    """后台线程：每 STATE_UPDATE_INTERVAL 秒刷新一次所有交换机状态，并发送 Trap 通知"""
    while True:
        time.sleep(STATE_UPDATE_INTERVAL)
        for state in all_states:
            try:
                events = update_switch_state(state)
                logger.debug(f"Switch {state['sw_id']} state updated, {len(events)} trap(s)")
                for level, msg in events:
                    _send_trap(level, msg)
            except Exception as e:
                logger.warning(f"State update error: {e}")


# ─── OID Map 构建（从当前状态快照生成） ─────────────────────────────

def build_oid_map(state):
    sw_id = state["sw_id"]
    base = OID_BASE

    with state["_lock"]:
        s = {
            "temperature": state["temperature"],
            "main_power": state["main_power"],
            "redundant_power": state["redundant_power"],
            "fan1": state["fan1"],
            "fan2": state["fan2"],
            "fan3": state["fan3"],
            "fan4": state["fan4"],
            "net_if0": state["net_if0"],
            "net_if1": state["net_if1"],
            "cpus": [dict(c) for c in state["cpus"]],
            "cons": [dict(c) for c in state["cons"]],
        }

    oid_map = {
        # sysObjectID
        "1.3.6.1.2.1.1.2.0": base,
        # 设备信息
        f"{base}.2.1.1.0": f"SIM-{sw_id}",
        f"{base}.2.1.2.0": "257",
        f"{base}.2.1.3.0": "ControlCenter-Compact-8C",
        f"{base}.2.1.4.0": f"GD-SIM-{sw_id}",
        f"{base}.2.1.5.0": f"0x000ff402455{sw_id}",
        f"{base}.2.1.6.0": f"0x000ff402456{sw_id}",
        f"{base}.2.2.1.0": "1.7.000 (01165)",
        # 机箱状态
        f"{base}.2.3.1.0": s["main_power"],
        f"{base}.2.3.2.0": s["redundant_power"],
        f"{base}.2.3.3.0": f"{s['temperature']:.1f}",
        f"{base}.2.3.500.0": f"{random.uniform(1.2, 2.0):.2f}",
        f"{base}.2.3.501.0": f"{random.uniform(11.8, 12.2):.2f}",
        f"{base}.2.3.502.0": s["fan1"],
        f"{base}.2.3.503.0": s["fan2"],
        f"{base}.2.3.504.0": s["fan3"],
        f"{base}.2.3.505.0": s["fan4"],
        f"{base}.2.3.506.0": s["net_if0"],
        f"{base}.2.3.507.0": s["net_if1"],
    }

    # ── CPU 终端模块 → .1.2.2.3.1000.1.{col}.{row} ──────────────
    ep_base = f"{base}.1.2.2.3.1000.1"
    for row, cpu in enumerate(s["cpus"], start=1):
        oid_map[f"{ep_base}.2.{row}"]  = cpu["id"]
        oid_map[f"{ep_base}.3.{row}"]  = "0x00000401"
        oid_map[f"{ep_base}.4.{row}"]  = cpu["name"]
        oid_map[f"{ep_base}.5.{row}"]  = cpu["device_status"]
        oid_map[f"{ep_base}.6.{row}"]  = cpu["main_power"]
        oid_map[f"{ep_base}.7.{row}"]  = cpu["redundant_power"]
        oid_map[f"{ep_base}.8.{row}"]  = f"{cpu['temperature']:.1f}"
        oid_map[f"{ep_base}.9.{row}"]  = 0    # console_ps2
        oid_map[f"{ep_base}.10.{row}"] = 0    # console_usb
        oid_map[f"{ep_base}.11.{row}"] = 0    # target_ps2
        oid_map[f"{ep_base}.12.{row}"] = cpu["target_usb_hid"]
        oid_map[f"{ep_base}.13.{row}"] = cpu["target_video_cable"]
        oid_map[f"{ep_base}.14.{row}"] = 0    # target_video_cable1
        oid_map[f"{ep_base}.15.{row}"] = 0    # target_video_cable2
        oid_map[f"{ep_base}.16.{row}"] = cpu["target_video_signal"]
        oid_map[f"{ep_base}.17.{row}"] = 0    # target_video_signal1
        oid_map[f"{ep_base}.18.{row}"] = 0    # target_video_signal2
        oid_map[f"{ep_base}.19.{row}"] = cpu["target_power"]
        oid_map[f"{ep_base}.20.{row}"] = cpu["target_access"]
        oid_map[f"{ep_base}.21.{row}"] = cpu["sfp_tx_power"]
        oid_map[f"{ep_base}.22.{row}"] = cpu["sfp_rx_power"]
        oid_map[f"{ep_base}.23.{row}"] = ""
        oid_map[f"{ep_base}.24.{row}"] = cpu["net_if0"]

    # ── CON 用户模块 → .1.1.2.3.1000.1.{col}.{row} ──────────────
    con_base = f"{base}.1.1.2.3.1000.1"
    for row, con in enumerate(s["cons"], start=1):
        oid_map[f"{con_base}.2.{row}"]  = con["id"]
        oid_map[f"{con_base}.3.{row}"]  = "0x00000101"
        oid_map[f"{con_base}.4.{row}"]  = con["name"]
        oid_map[f"{con_base}.5.{row}"]  = con["device_status"]
        oid_map[f"{con_base}.6.{row}"]  = con["main_power"]
        oid_map[f"{con_base}.7.{row}"]  = con["redundant_power"]
        oid_map[f"{con_base}.8.{row}"]  = f"{con['temperature']:.1f}"
        oid_map[f"{con_base}.9.{row}"]  = con["console_ps2"]
        oid_map[f"{con_base}.10.{row}"] = con["console_usb"]
        oid_map[f"{con_base}.11.{row}"] = con["display_conn"]
        oid_map[f"{con_base}.12.{row}"] = 0    # display_conn1
        oid_map[f"{con_base}.13.{row}"] = 0    # display_conn2
        oid_map[f"{con_base}.14.{row}"] = con["display_type"]
        oid_map[f"{con_base}.15.{row}"] = ""   # display_type1
        oid_map[f"{con_base}.16.{row}"] = ""   # display_type2
        oid_map[f"{con_base}.17.{row}"] = con["freeze"]
        oid_map[f"{con_base}.18.{row}"] = 0    # freeze1
        oid_map[f"{con_base}.19.{row}"] = 0    # freeze2
        oid_map[f"{con_base}.20.{row}"] = con["sfp_tx_power"]
        oid_map[f"{con_base}.21.{row}"] = con["sfp_tx_power1"]
        oid_map[f"{con_base}.22.{row}"] = 0    # sfp_tx_power2
        oid_map[f"{con_base}.23.{row}"] = con["sfp_rx_power"]
        oid_map[f"{con_base}.24.{row}"] = con["sfp_rx_power1"]
        oid_map[f"{con_base}.25.{row}"] = 0    # sfp_rx_power2
        oid_map[f"{con_base}.26.{row}"] = "LC-SMF"
        oid_map[f"{con_base}.27.{row}"] = "LC-SMF"
        oid_map[f"{con_base}.28.{row}"] = ""   # sfp_type2
        oid_map[f"{con_base}.29.{row}"] = con["active_tx_port"]
        oid_map[f"{con_base}.30.{row}"] = con["net_if0"]

    return oid_map


# ─── SNMP 仿真器核心 ─────────────────────────────────────────────────

def start_simulator(port, state):
    pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

    def find_next_oid(sorted_oids, current_tuple):
        for oid_t, oid_s, val in sorted_oids:
            if oid_t > current_tuple:
                return oid_s, val
        return None, None

    def to_snmp_val(val):
        if isinstance(val, int):
            return pMod.Integer(val)
        if isinstance(val, str) and val.startswith("1.3.6.1"):
            return pMod.ObjectIdentifier(tuple(int(x) for x in val.split(".")))
        return pMod.OctetString(str(val))

    def handle_request(data):
        try:
            req_msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            community = pMod.apiMessage.getCommunity(req_msg)
            req_pdu = pMod.apiMessage.getPDU(req_msg)

            oid_map = build_oid_map(state)
            sorted_oids = sorted(
                [(tuple(int(x) for x in k.split(".")), k, v) for k, v in oid_map.items()],
                key=lambda x: x[0]
            )

            resp_msg = pMod.Message()
            pMod.apiMessage.setDefaults(resp_msg)
            pMod.apiMessage.setCommunity(resp_msg, community)

            resp_pdu = pMod.GetResponsePDU()
            pMod.apiPDU.setDefaults(resp_pdu)
            pMod.apiPDU.setRequestID(resp_pdu, pMod.apiPDU.getRequestID(req_pdu))

            req_var_binds = pMod.apiPDU.getVarBinds(req_pdu)
            resp_var_binds = []

            pdu_tag = req_pdu.tagSet
            is_get  = (pdu_tag == pMod.GetRequestPDU.tagSet)
            is_bulk = (pdu_tag == pMod.GetBulkRequestPDU.tagSet)
            is_next = (pdu_tag == pMod.GetNextRequestPDU.tagSet)

            if is_get:
                for oid, _ in req_var_binds:
                    oid_str = str(oid).lstrip(".")
                    if oid_str in oid_map:
                        resp_var_binds.append((oid, to_snmp_val(oid_map[oid_str])))
                    else:
                        resp_var_binds.append((oid, pMod.NoSuchObject()))

            elif is_next:
                for oid, _ in req_var_binds:
                    current_tuple = tuple(int(x) for x in str(oid).lstrip(".").split("."))
                    ns, nv = find_next_oid(sorted_oids, current_tuple)
                    if ns:
                        resp_var_binds.append((ObjectIdentifier(tuple(int(x) for x in ns.split("."))), to_snmp_val(nv)))
                    else:
                        resp_var_binds.append((oid, pMod.EndOfMibView()))

            elif is_bulk:
                non_repeaters  = pMod.apiBulkPDU.getNonRepeaters(req_pdu)
                max_repetitions = pMod.apiBulkPDU.getMaxRepetitions(req_pdu)

                for i, (oid, _) in enumerate(req_var_binds):
                    current_tuple = tuple(int(x) for x in str(oid).lstrip(".").split("."))
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
            logger.debug(f"handle_request error: {e}")
            return None

    def run_sim():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", port))
        sock.settimeout(1.0)
        logger.info(
            f"Switch {state['sw_id']} on :{port}  "
            f"({NUM_CPU} CPU + {NUM_CON} CON)"
        )
        while True:
            try:
                data, addr = sock.recvfrom(65535)
                response = handle_request(data)
                if response:
                    sock.sendto(response, addr)
            except socket.timeout:
                continue
            except Exception:
                pass

    t = threading.Thread(target=run_sim, daemon=True)
    t.start()
    return t


# ─── 入口 ─────────────────────────────────────────────────────────────

async def main():
    base_port = 11161
    num_switches = 3

    # 初始化所有交换机状态
    all_states = [init_switch_state(i) for i in range(1, num_switches + 1)]

    # 启动后台状态更新线程
    updater = threading.Thread(
        target=state_updater, args=(all_states,), daemon=True, name="state-updater"
    )
    updater.start()

    # 启动各台仿真器
    for i, state in enumerate(all_states):
        start_simulator(base_port + i + 1, state)

    # 写入数据库
    os.environ.setdefault("DB_MODE", "sqlite")
    from app.database import AsyncSessionLocal
    from app.models.device import Device
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        for i in range(1, num_switches + 1):
            dev_id = f"sim_kvm_0{i}"
            res = await db.execute(select(Device).where(Device.id == dev_id))
            if not res.scalar_one_or_none():
                db.add(Device(
                    id=dev_id,
                    name=f"KVM Switch SIM-{i}",
                    host="127.0.0.1",
                    port=base_port + i,
                    community="public",
                    is_active=True,
                    poll_interval=15,
                ))
        await db.commit()

    logger.info(
        f"{num_switches} switches registered. "
        f"Each: {NUM_CPU} CPU + {NUM_CON} CON endpoints. "
        f"State updates every {STATE_UPDATE_INTERVAL}s. "
        "Backend poller will collect data automatically."
    )

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
