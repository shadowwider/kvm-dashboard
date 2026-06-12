#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KVM Simulator Pro
=================
可配置的 G&D KVM 模拟器，用于验证 kvm-dashboard 前后端。

功能：
  - 每台交换机独立 SNMP Agent（UDP，pysnmp v2c，GET/GETNEXT/GETBULK）
  - OID 结构与 oid_map.py 完全对齐
  - Trap 发送（OID: 1.3.6.1.4.1.32828.2.1.0.x，符合 GUD-GENERALTRAPS-MIB）
  - Web 控制台（http://localhost:8888）动态增删交换机、插拔 CPU/CON、修改所有字段

启动:
  python backend/kvm_simulator.py
  # 或指定基础端口和 Web 端口
  SIM_BASE_PORT=11160 SIM_WEB_PORT=8888 python backend/kvm_simulator.py

在 KVM Dashboard 后台手动添加设备时：
  host=127.0.0.1  port=11161（第1台），11162（第2台）……
"""

import os
import sys
import json
import time
import socket
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from pysnmp.proto import api as snmp_api
from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier

# ─── 配置 ────────────────────────────────────────────────────────────
BASE_PORT   = int(os.environ.get("SIM_BASE_PORT", "11160"))  # 第1台用 BASE_PORT+1
WEB_PORT    = int(os.environ.get("SIM_WEB_PORT",  "8888"))
TRAP_HOST   = os.environ.get("TRAP_TARGET_HOST",  "127.0.0.1")
TRAP_PORT   = int(os.environ.get("SNMP_TRAP_PORT", "10162"))
COMMUNITY   = os.environ.get("SNMP_COMMUNITY",    "public")

OID_BASE    = "1.3.6.1.4.1.32828.3.257.16"   # sysObjectID / gudCCDC

# Trap OID — 来自 GUD-SMI-MIB + GUD-GENERALTRAPS-MIB
# gudTrap=32828.2, gudGeneralTrap=32828.2.1, gudGeneralNotifications=32828.2.1.0
_TRAP_NOTIF_OID  = "1.3.6.1.4.1.32828.2.1.0.4"
_TRAP_LEVEL_OID  = "1.3.6.1.4.1.32828.2.1.0.2"
_TRAP_MSG_OID    = "1.3.6.1.4.1.32828.2.1.0.3"
_SYS_UPTIME_OID  = "1.3.6.1.2.1.1.3.0"
_SNMPTRAPOID_OID = "1.3.6.1.6.3.1.1.4.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("KvmSim")

# ─── 全局状态 ─────────────────────────────────────────────────────────
# switches: list of switch_state dict
# 每个 switch_state:
#   { id, name, snmp_port, sys: {...}, cpus: {row: {...}}, cons: {row: {...}} }
_state_lock = threading.Lock()
_switches: list[dict] = []
_next_sw_id = 1
_snmp_threads: dict[int, threading.Thread] = {}   # snmp_port -> Thread


# ─── 默认值工厂 ──────────────────────────────────────────────────────

def _default_sys():
    return {
        "temperature": 45.0,
        "main_power": 1,       # 0=off 1=on
        "redundant_power": 1,
        "fan1": 3200, "fan2": 3150, "fan3": 3100, "fan4": 3050,
        "net_if0": 1, "net_if1": 0,
        "device_type": "ControlCenter-Compact-8C",
        "firmware": "1.7.000",
    }


def _default_cpu(sw_id: int, row: int) -> dict:
    """
    字段与 oid_map.py ENDPOINT_COLUMNS 一一对应（Column 号注释）。
    ep_id = Column 2（MIB 里的 id，用于 Trap 消息匹配）
    ep_name = Column 4（MIB 里的 name，用于 UI 显示）
    """
    return {
        # col 1: targetModuleIndex（模块索引，等于 row）
        "ep_port": row,
        # col 2: id
        "ep_id": f"CPU-{sw_id}-{row:03d}",
        # col 3: cl
        "ep_class": "0x00000401",
        # col 4: name
        "ep_name": f"CPU-HOST-SW{sw_id}-{row:03d}",
        # col 5: deviceStatus  0=offline 1=online 2=ready
        "ep_device_status": 1,
        # col 6: mainPower
        "ep_main_power": 1,
        # col 7: redundantPower
        "ep_redundant_power": 0,
        # col 8: temperature1
        "ep_temperature": 42.0,
        # col 9: consolePS2Connection  (CPU 侧此字段固定为 0)
        "ep_console_ps2": 0,
        # col 10: consoleUSBConnection
        "ep_console_usb": 0,
        # col 11: targetPS2Connection
        "ep_target_ps2": 0,
        # col 12: targetUsbHid  0=notConnected 1=connected 2=initialized
        "ep_target_usb_hid": 2,
        # col 13: targetVideoCable  0=notConnected 1=connected
        "ep_target_video_cable": 1,
        # col 14,15: targetVideoCable1/2
        "ep_target_video_cable1": 0,
        "ep_target_video_cable2": 0,
        # col 16: targetVideoSignal  0=none 1=vga 2=dvisl 3=dvidl 4=dmdp 5=dp 6=hdmi
        "ep_target_video_signal": 5,
        # col 17,18: targetVideoSignal1/2
        "ep_target_video_signal1": 0,
        "ep_target_video_signal2": 0,
        # col 19: targetPower  0=off 1=on
        "ep_target_power": 1,
        # col 20: targetAccess  0=local 1=remote 2=localExclusive 3=remoteExclusive
        "ep_target_access": 0,
        # col 21: sfpTxPower (uW)
        "ep_sfp_tx_power": 500,
        # col 22: sfpRxPower (uW)
        "ep_sfp_rx_power": 480,
        # col 23: sfpType
        "ep_sfp_type": "LC-SMF",
        # col 24: networkInterface0
        "ep_net_if0": 1,
    }


def _default_con(sw_id: int, row: int) -> dict:
    """
    字段与 oid_map.py CON_COLUMNS 一一对应（Column 号注释）。
    """
    return {
        # col 1: userModuleIndex
        "con_port": row,
        # col 2: id（用于 Trap 消息匹配）
        "con_id": f"CON-{sw_id}-{row:03d}",
        # col 3: cl
        "con_class": "0x00000101",
        # col 4: name
        "con_name": f"CON-USER-SW{sw_id}-{row:03d}",
        # col 5: deviceStatus
        "con_device_status": 1,
        # col 6: mainPower
        "con_main_power": 1,
        # col 7: redundantPower
        "con_redundant_power": 0,
        # col 8: temperature1
        "con_temperature": 38.0,
        # col 9: consolePS2Connection  0=none 1=keyboard 2=mouse 3=keyboardMouse
        "con_console_ps2": 3,
        # col 10: consoleUSBConnection
        "con_console_usb": 3,
        # col 11: displayConnection  0=notConnected 1=connected
        "con_display_conn": 1,
        # col 12,13: displayConnection1/2
        "con_display_conn1": 0,
        "con_display_conn2": 0,
        # col 14: displayType (string)
        "con_display_type": "Dell-U2722D",
        # col 15,16: displayType1/2
        "con_display_type1": "",
        "con_display_type2": "",
        # col 17: freeze  0=false 1=true
        "con_freeze": 0,
        # col 18,19: freeze1/2
        "con_freeze1": 0,
        "con_freeze2": 0,
        # col 20-22: sfpTxPower/1/2 (uW)
        "con_sfp_tx_power": 510,
        "con_sfp_tx_power1": 505,
        "con_sfp_tx_power2": 0,
        # col 23-25: sfpRxPower/1/2 (uW)
        "con_sfp_rx_power": 490,
        "con_sfp_rx_power1": 485,
        "con_sfp_rx_power2": 0,
        # col 26-28: sfpType/1/2
        "con_sfp_type": "LC-SMF",
        "con_sfp_type1": "LC-SMF",
        "con_sfp_type2": "",
        # col 29: activeTransmissionPort  1 or 2
        "con_active_tx_port": 1,
        # col 30: networkInterface0
        "con_net_if0": 1,
    }


# ─── 状态管理 API ─────────────────────────────────────────────────────

def _alloc_port() -> int:
    used = {sw["snmp_port"] for sw in _switches}
    p = BASE_PORT + 1
    while p in used:
        p += 1
    return p


def switch_add(name: str | None = None) -> dict:
    global _next_sw_id
    with _state_lock:
        sw_id = _next_sw_id
        _next_sw_id += 1
        port = _alloc_port()
        sw = {
            "id": sw_id,
            "name": name or f"KVM-SIM-{sw_id}",
            "snmp_port": port,
            "sys": _default_sys(),
            "cpus": {},   # row(int) -> cpu_dict
            "cons": {},   # row(int) -> con_dict
        }
        _switches.append(sw)
    _start_snmp_agent(sw)
    logger.info("交换机 %s (id=%d) 已添加，SNMP 端口 %d", sw["name"], sw_id, port)
    return sw


def switch_remove(sw_id: int) -> bool:
    with _state_lock:
        idx = next((i for i, s in enumerate(_switches) if s["id"] == sw_id), None)
        if idx is None:
            return False
        _switches.pop(idx)
    logger.info("交换机 id=%d 已移除", sw_id)
    return True


def switch_sys_update(sw_id: int, fields: dict) -> bool:
    with _state_lock:
        sw = next((s for s in _switches if s["id"] == sw_id), None)
        if sw is None:
            return False
        sw["sys"].update(fields)
    return True


def endpoint_add(sw_id: int, ep_type: str, row: int | None = None) -> dict | None:
    """插入 CPU 或 CON，row 不指定则自动取最小空位"""
    with _state_lock:
        sw = next((s for s in _switches if s["id"] == sw_id), None)
        if sw is None:
            return None
        pool = sw["cpus"] if ep_type == "cpu" else sw["cons"]
        if row is None:
            r = 1
            while r in pool:
                r += 1
            row = r
        ep = _default_cpu(sw_id, row) if ep_type == "cpu" else _default_con(sw_id, row)
        pool[row] = ep
    return ep


def endpoint_remove(sw_id: int, ep_type: str, row: int) -> bool:
    with _state_lock:
        sw = next((s for s in _switches if s["id"] == sw_id), None)
        if sw is None:
            return False
        pool = sw["cpus"] if ep_type == "cpu" else sw["cons"]
        if row not in pool:
            return False
        del pool[row]
    return True


def endpoint_update(sw_id: int, ep_type: str, row: int, fields: dict) -> bool:
    with _state_lock:
        sw = next((s for s in _switches if s["id"] == sw_id), None)
        if sw is None:
            return False
        pool = sw["cpus"] if ep_type == "cpu" else sw["cons"]
        if row not in pool:
            return False
        pool[row].update(fields)
    return True


def state_snapshot() -> list[dict]:
    """线程安全地返回全部交换机状态（深拷贝）"""
    import copy
    with _state_lock:
        return copy.deepcopy(_switches)


# ─── OID Map 构建 ─────────────────────────────────────────────────────

def build_oid_map(sw: dict) -> dict:
    """
    根据交换机状态生成完整 OID Map。
    与 run_simulators_large.py 的 build_oid_map() 结构完全一致，
    字段顺序与 oid_map.py ENDPOINT_COLUMNS / CON_COLUMNS 对齐。
    """
    b = OID_BASE
    sys = sw["sys"]

    m: dict = {
        "1.3.6.1.2.1.1.2.0": b,
        f"{b}.2.1.1.0": f"SIM-{sw['id']}",
        f"{b}.2.1.2.0": "257",
        f"{b}.2.1.3.0": sys["device_type"],
        f"{b}.2.1.4.0": f"GD-SIM-{sw['id']}",
        f"{b}.2.1.5.0": f"00:00:00:00:00:{sw['id']:02x}",
        f"{b}.2.1.6.0": f"00:00:00:00:01:{sw['id']:02x}",
        f"{b}.2.2.1.0": sys["firmware"],
        f"{b}.2.3.1.0": sys["main_power"],
        f"{b}.2.3.2.0": sys["redundant_power"],
        f"{b}.2.3.3.0": str(sys["temperature"]),
        f"{b}.2.3.502.0": sys["fan1"],
        f"{b}.2.3.503.0": sys["fan2"],
        f"{b}.2.3.504.0": sys["fan3"],
        f"{b}.2.3.505.0": sys["fan4"],
        f"{b}.2.3.506.0": sys["net_if0"],
        f"{b}.2.3.507.0": sys["net_if1"],
    }

    # ── CPU 端点表 → {b}.1.2.2.3.1000.1.{col}.{row} ──────────────
    ep_base = f"{b}.1.2.2.3.1000.1"
    for row, cpu in sorted(sw["cpus"].items()):
        m[f"{ep_base}.1.{row}"]  = cpu["ep_port"]
        m[f"{ep_base}.2.{row}"]  = cpu["ep_id"]
        m[f"{ep_base}.3.{row}"]  = cpu["ep_class"]
        m[f"{ep_base}.4.{row}"]  = cpu["ep_name"]
        m[f"{ep_base}.5.{row}"]  = cpu["ep_device_status"]
        m[f"{ep_base}.6.{row}"]  = cpu["ep_main_power"]
        m[f"{ep_base}.7.{row}"]  = cpu["ep_redundant_power"]
        m[f"{ep_base}.8.{row}"]  = str(cpu["ep_temperature"])
        m[f"{ep_base}.9.{row}"]  = cpu["ep_console_ps2"]
        m[f"{ep_base}.10.{row}"] = cpu["ep_console_usb"]
        m[f"{ep_base}.11.{row}"] = cpu["ep_target_ps2"]
        m[f"{ep_base}.12.{row}"] = cpu["ep_target_usb_hid"]
        m[f"{ep_base}.13.{row}"] = cpu["ep_target_video_cable"]
        m[f"{ep_base}.14.{row}"] = cpu["ep_target_video_cable1"]
        m[f"{ep_base}.15.{row}"] = cpu["ep_target_video_cable2"]
        m[f"{ep_base}.16.{row}"] = cpu["ep_target_video_signal"]
        m[f"{ep_base}.17.{row}"] = cpu["ep_target_video_signal1"]
        m[f"{ep_base}.18.{row}"] = cpu["ep_target_video_signal2"]
        m[f"{ep_base}.19.{row}"] = cpu["ep_target_power"]
        m[f"{ep_base}.20.{row}"] = cpu["ep_target_access"]
        m[f"{ep_base}.21.{row}"] = cpu["ep_sfp_tx_power"]
        m[f"{ep_base}.22.{row}"] = cpu["ep_sfp_rx_power"]
        m[f"{ep_base}.23.{row}"] = cpu["ep_sfp_type"]
        m[f"{ep_base}.24.{row}"] = cpu["ep_net_if0"]

    # ── CON 端点表 → {b}.1.1.2.3.1000.1.{col}.{row} ──────────────
    con_base = f"{b}.1.1.2.3.1000.1"
    for row, con in sorted(sw["cons"].items()):
        m[f"{con_base}.1.{row}"]  = con["con_port"]
        m[f"{con_base}.2.{row}"]  = con["con_id"]
        m[f"{con_base}.3.{row}"]  = con["con_class"]
        m[f"{con_base}.4.{row}"]  = con["con_name"]
        m[f"{con_base}.5.{row}"]  = con["con_device_status"]
        m[f"{con_base}.6.{row}"]  = con["con_main_power"]
        m[f"{con_base}.7.{row}"]  = con["con_redundant_power"]
        m[f"{con_base}.8.{row}"]  = str(con["con_temperature"])
        m[f"{con_base}.9.{row}"]  = con["con_console_ps2"]
        m[f"{con_base}.10.{row}"] = con["con_console_usb"]
        m[f"{con_base}.11.{row}"] = con["con_display_conn"]
        m[f"{con_base}.12.{row}"] = con["con_display_conn1"]
        m[f"{con_base}.13.{row}"] = con["con_display_conn2"]
        m[f"{con_base}.14.{row}"] = con["con_display_type"]
        m[f"{con_base}.15.{row}"] = con["con_display_type1"]
        m[f"{con_base}.16.{row}"] = con["con_display_type2"]
        m[f"{con_base}.17.{row}"] = con["con_freeze"]
        m[f"{con_base}.18.{row}"] = con["con_freeze1"]
        m[f"{con_base}.19.{row}"] = con["con_freeze2"]
        m[f"{con_base}.20.{row}"] = con["con_sfp_tx_power"]
        m[f"{con_base}.21.{row}"] = con["con_sfp_tx_power1"]
        m[f"{con_base}.22.{row}"] = con["con_sfp_tx_power2"]
        m[f"{con_base}.23.{row}"] = con["con_sfp_rx_power"]
        m[f"{con_base}.24.{row}"] = con["con_sfp_rx_power1"]
        m[f"{con_base}.25.{row}"] = con["con_sfp_rx_power2"]
        m[f"{con_base}.26.{row}"] = con["con_sfp_type"]
        m[f"{con_base}.27.{row}"] = con["con_sfp_type1"]
        m[f"{con_base}.28.{row}"] = con["con_sfp_type2"]
        m[f"{con_base}.29.{row}"] = con["con_active_tx_port"]
        m[f"{con_base}.30.{row}"] = con["con_net_if0"]

    # ── portTable → {b}.2.3.1000.1.{col}.{portIndex} ──────────────
    # GUD-CCDC-MIB portTable: 物理传输端口链路状态和光模块指标
    # col 2=portStatus, 3=portSfpModule, 4=portSfpTxPower, 5=portSfpRxPower, 6=portSfpType
    # portStatus: 0=noModule, 1=deactivated, 2=down, 3=up
    # portIndex 范围：MIB 定义 1..80
    # 注：portTable 只反映物理层链路，不包含 CPU↔CON 业务路由映射
    port_base = f"{b}.2.3.1000.1"
    occupied: dict[int, dict] = {}
    for row, cpu in sw["cpus"].items():
        occupied[cpu["ep_port"]] = {
            "status": 3 if cpu["ep_device_status"] != 0 else 2,
            "tx": cpu["ep_sfp_tx_power"] if cpu["ep_device_status"] != 0 else 0,
            "rx": cpu["ep_sfp_rx_power"] if cpu["ep_device_status"] != 0 else 0,
            "sfp_type": cpu["ep_sfp_type"] if cpu["ep_device_status"] != 0 else "",
        }
    for row, con in sw["cons"].items():
        occupied[con["con_port"]] = {
            "status": 3 if con["con_device_status"] != 0 else 2,
            "tx": con["con_sfp_tx_power"] if con["con_device_status"] != 0 else 0,
            "rx": con["con_sfp_rx_power"] if con["con_device_status"] != 0 else 0,
            "sfp_type": con["con_sfp_type"] if con["con_device_status"] != 0 else "",
        }
    max_port = max(occupied.keys(), default=0)
    for port_idx in range(1, max_port + 1):
        p = occupied.get(port_idx)
        st = p["status"] if p else 0
        m[f"{port_base}.2.{port_idx}"] = st
        m[f"{port_base}.3.{port_idx}"] = st
        m[f"{port_base}.4.{port_idx}"] = p["tx"] if p else 0
        m[f"{port_base}.5.{port_idx}"] = p["rx"] if p else 0
        m[f"{port_base}.6.{port_idx}"] = p["sfp_type"] if p else ""

    return m


# ─── SNMP Agent ───────────────────────────────────────────────────────

def _to_snmp_val(pMod, val):
    if isinstance(val, int):
        return pMod.Integer(val)
    s = str(val)
    if s.startswith("1.3.6"):
        return pMod.ObjectIdentifier(tuple(int(x) for x in s.split(".")))
    return pMod.OctetString(str(val).encode("utf-8"))


def _snmp_agent(sw_id: int, snmp_port: int):
    pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", snmp_port))
    sock.settimeout(1.0)
    logger.info("SNMP Agent sw_id=%d 监听 UDP:%d", sw_id, snmp_port)

    def find_next(sorted_oids, cur_tup):
        for ot, os_, ov in sorted_oids:
            if ot > cur_tup:
                return os_, ov
        return None, None

    while True:
        # 检查该交换机是否还存在
        with _state_lock:
            sw = next((s for s in _switches if s["id"] == sw_id), None)
        if sw is None:
            logger.info("SNMP Agent sw_id=%d 退出", sw_id)
            break

        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception as e:
            logger.debug("SNMP recv error: %s", e)
            continue

        try:
            req_msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            community = pMod.apiMessage.getCommunity(req_msg)
            req_pdu   = pMod.apiMessage.getPDU(req_msg)

            with _state_lock:
                sw_snap = next((s for s in _switches if s["id"] == sw_id), None)
            if sw_snap is None:
                break
            oid_map = build_oid_map(sw_snap)

            sorted_oids = sorted(
                [(tuple(int(x) for x in k.split(".")), k, v) for k, v in oid_map.items()],
                key=lambda x: x[0],
            )

            resp_msg = pMod.Message()
            pMod.apiMessage.setDefaults(resp_msg)
            pMod.apiMessage.setCommunity(resp_msg, community)

            resp_pdu = pMod.GetResponsePDU()
            pMod.apiPDU.setDefaults(resp_pdu)
            pMod.apiPDU.setRequestID(resp_pdu, pMod.apiPDU.getRequestID(req_pdu))

            req_vbs  = pMod.apiPDU.getVarBinds(req_pdu)
            resp_vbs = []

            pdu_tag  = req_pdu.tagSet
            is_get   = pdu_tag == pMod.GetRequestPDU.tagSet
            is_next  = pdu_tag == pMod.GetNextRequestPDU.tagSet
            is_bulk  = pdu_tag == pMod.GetBulkRequestPDU.tagSet

            if is_get:
                for oid, _ in req_vbs:
                    s = str(oid).lstrip(".")
                    if s in oid_map:
                        resp_vbs.append((oid, _to_snmp_val(pMod, oid_map[s])))
                    else:
                        resp_vbs.append((oid, pMod.NoSuchObject()))

            elif is_next:
                for oid, _ in req_vbs:
                    cur = tuple(int(x) for x in str(oid).lstrip(".").split("."))
                    ns, nv = find_next(sorted_oids, cur)
                    if ns:
                        resp_vbs.append((
                            ObjectIdentifier(tuple(int(x) for x in ns.split("."))),
                            _to_snmp_val(pMod, nv),
                        ))
                    else:
                        resp_vbs.append((oid, pMod.EndOfMibView()))

            elif is_bulk:
                nr  = pMod.apiBulkPDU.getNonRepeaters(req_pdu)
                mr  = pMod.apiBulkPDU.getMaxRepetitions(req_pdu)
                for i, (oid, _) in enumerate(req_vbs):
                    cur = tuple(int(x) for x in str(oid).lstrip(".").split("."))
                    if i < nr:
                        ns, nv = find_next(sorted_oids, cur)
                        if ns:
                            resp_vbs.append((
                                ObjectIdentifier(tuple(int(x) for x in ns.split("."))),
                                _to_snmp_val(pMod, nv),
                            ))
                        else:
                            resp_vbs.append((oid, pMod.EndOfMibView()))
                    else:
                        ct = cur
                        for _ in range(mr):
                            ns, nv = find_next(sorted_oids, ct)
                            if ns:
                                resp_vbs.append((
                                    ObjectIdentifier(tuple(int(x) for x in ns.split("."))),
                                    _to_snmp_val(pMod, nv),
                                ))
                                ct = tuple(int(x) for x in ns.split("."))
                            else:
                                resp_vbs.append((oid, pMod.EndOfMibView()))
                                break

            pMod.apiPDU.setVarBinds(resp_pdu, resp_vbs)
            pMod.apiMessage.setPDU(resp_msg, resp_pdu)
            sock.sendto(ber_encoder.encode(resp_msg), addr)

        except Exception as e:
            logger.debug("SNMP handle error: %s", e)

    sock.close()


def _start_snmp_agent(sw: dict):
    t = threading.Thread(
        target=_snmp_agent,
        args=(sw["id"], sw["snmp_port"]),
        daemon=True,
        name=f"snmp-{sw['id']}",
    )
    t.start()
    _snmp_threads[sw["snmp_port"]] = t


# ─── Trap 发送 ────────────────────────────────────────────────────────

def send_trap(level: int, message: str):
    """
    发送 G&D 标准 SNMPv2c Trap。
    level: 0=Emergency 1=Alert 2=Critical 3=Error 4=Warning 5=Notice
    """
    try:
        from pysnmp.proto.rfc1905 import SNMPv2TrapPDU
        from pysnmp.proto.rfc1902 import TimeTicks

        pMod = snmp_api.protoModules[snmp_api.protoVersion2c]

        def _ot(s):
            return tuple(int(x) for x in s.strip(".").split("."))

        trap_msg = pMod.Message()
        pMod.apiMessage.setDefaults(trap_msg)
        pMod.apiMessage.setCommunity(trap_msg, COMMUNITY)

        trap_pdu = SNMPv2TrapPDU()
        pMod.apiPDU.setDefaults(trap_pdu)

        uptime = int(time.monotonic() * 100)
        pMod.apiPDU.setVarBinds(trap_pdu, [
            (ObjectIdentifier(_ot(_SYS_UPTIME_OID)),  TimeTicks(uptime)),
            (ObjectIdentifier(_ot(_SNMPTRAPOID_OID)), pMod.ObjectIdentifier(_ot(_TRAP_NOTIF_OID))),
            (ObjectIdentifier(_ot(_TRAP_LEVEL_OID)),  pMod.Integer(level)),
            (ObjectIdentifier(_ot(_TRAP_MSG_OID)),    pMod.OctetString(message.encode("utf-8"))),
        ])
        pMod.apiMessage.setPDU(trap_msg, trap_pdu)

        data = ber_encoder.encode(trap_msg)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(data, (TRAP_HOST, TRAP_PORT))

        logger.info("Trap 已发送 → %s:%d  level=%d  msg=%r", TRAP_HOST, TRAP_PORT, level, message)
    except Exception as e:
        logger.warning("Trap 发送失败: %s", e)


# ─── HTTP API 处理 ────────────────────────────────────────────────────

class _ApiHandler(BaseHTTPRequestHandler):

    def _send_json(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def log_message(self, fmt, *args):
        pass  # 静默 HTTP 日志

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            self._send_html(_UI_HTML)

        elif path == "/api/state":
            self._send_json(200, {"switches": state_snapshot()})

        else:
            self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        # ── 交换机管理 ───────────────────────────────────────────
        if path == "/api/switch/add":
            sw = switch_add(body.get("name"))
            self._send_json(200, {"ok": True, "switch": sw})

        elif path == "/api/switch/remove":
            ok = switch_remove(int(body["id"]))
            self._send_json(200, {"ok": ok})

        elif path == "/api/switch/sys_update":
            ok = switch_sys_update(int(body["id"]), body.get("fields", {}))
            self._send_json(200, {"ok": ok})

        # ── 端点管理 ─────────────────────────────────────────────
        elif path == "/api/endpoint/add":
            ep = endpoint_add(
                int(body["sw_id"]),
                body["type"],           # "cpu" | "con"
                body.get("row"),
            )
            self._send_json(200, {"ok": ep is not None, "endpoint": ep})

        elif path == "/api/endpoint/remove":
            ok = endpoint_remove(int(body["sw_id"]), body["type"], int(body["row"]))
            self._send_json(200, {"ok": ok})

        elif path == "/api/endpoint/update":
            ok = endpoint_update(
                int(body["sw_id"]),
                body["type"],
                int(body["row"]),
                body.get("fields", {}),
            )
            self._send_json(200, {"ok": ok})

        # ── Trap ─────────────────────────────────────────────────
        elif path == "/api/trap/send":
            level   = int(body.get("level", 3))
            message = body.get("message", "Test trap from KVM Simulator")
            threading.Thread(target=send_trap, args=(level, message), daemon=True).start()
            self._send_json(200, {"ok": True})

        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ─── 内嵌 Web UI ──────────────────────────────────────────────────────

_UI_HTML = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>KVM Simulator Pro</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0f1e;--panel:#0d1628;--card:#111c33;--border:#1e3050;
  --cyan:#00d4ff;--green:#00ff88;--red:#ff3355;--amber:#ffb300;
  --text:#8ba8c8;--bright:#e8f4ff;--dim:#3d5a7a
}
body{background:var(--bg);color:var(--text);font-family:'Courier New',monospace;font-size:12px;height:100vh;display:flex;flex-direction:column;overflow:hidden}
header{background:var(--panel);border-bottom:1px solid var(--border);padding:10px 18px;display:flex;align-items:center;gap:16px;flex-shrink:0}
header h1{color:var(--cyan);font-size:15px;letter-spacing:2px;text-transform:uppercase}
header span{color:var(--dim);font-size:10px}
#add-sw-btn{margin-left:auto;background:#0e2040;border:1px solid var(--cyan);color:var(--cyan);padding:5px 14px;cursor:pointer;font-size:11px;letter-spacing:1px}
#add-sw-btn:hover{background:rgba(0,212,255,.12)}
main{display:flex;flex:1;overflow:hidden}
/* 左侧交换机列表 */
#sw-list{width:180px;flex-shrink:0;border-right:1px solid var(--border);overflow-y:auto;padding:8px}
.sw-item{padding:8px 10px;margin-bottom:4px;border:1px solid var(--border);cursor:pointer;position:relative}
.sw-item:hover,.sw-item.active{border-color:var(--cyan);background:rgba(0,212,255,.06)}
.sw-name{color:var(--bright);font-size:11px;margin-bottom:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sw-port{color:var(--dim);font-size:9px}
.sw-del{position:absolute;top:6px;right:6px;color:var(--red);cursor:pointer;font-size:11px;opacity:.6}
.sw-del:hover{opacity:1}
/* 右侧详情 */
#detail{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:12px}
#detail-placeholder{flex:1;display:flex;align-items:center;justify-content:center;color:var(--dim)}
/* 区块 */
.section{background:var(--panel);border:1px solid var(--border);padding:12px}
.sec-title{color:var(--cyan);font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;border-bottom:1px solid var(--border);padding-bottom:6px}
/* 系统状态表格 */
.sys-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.sys-cell label{display:block;color:var(--dim);font-size:9px;margin-bottom:3px}
.sys-cell input,.sys-cell select{width:100%;background:var(--card);border:1px solid var(--border);color:var(--bright);padding:4px 6px;font-size:11px;font-family:inherit}
.sys-cell input:focus,.sys-cell select:focus{outline:none;border-color:var(--cyan)}
/* 端点列表 */
.ep-item{background:var(--card);border:1px solid var(--border);margin-bottom:6px;padding:8px 10px}
.ep-header{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.ep-badge{padding:1px 6px;font-size:9px;letter-spacing:1px;text-transform:uppercase}
.ep-badge.cpu{background:rgba(0,212,255,.15);color:var(--cyan);border:1px solid rgba(0,212,255,.3)}
.ep-badge.con{background:rgba(0,255,136,.1);color:var(--green);border:1px solid rgba(0,255,136,.25)}
.ep-id{color:var(--dim);font-size:9px}
.ep-remove{margin-left:auto;color:var(--red);cursor:pointer;font-size:11px;opacity:.5}
.ep-remove:hover{opacity:1}
.ep-fields{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.ep-fields.wide{grid-template-columns:repeat(4,1fr)}
.field-cell label{display:block;color:var(--dim);font-size:9px;margin-bottom:2px}
.field-cell select,.field-cell input{width:100%;background:var(--bg);border:1px solid var(--border);color:var(--bright);padding:3px 5px;font-size:10px;font-family:inherit}
.field-cell select:focus,.field-cell input:focus{outline:none;border-color:var(--cyan)}
/* 按钮 */
.btn{padding:5px 12px;font-size:10px;letter-spacing:1px;cursor:pointer;border:1px solid;font-family:inherit;text-transform:uppercase}
.btn-cyan{background:rgba(0,212,255,.1);border-color:var(--cyan);color:var(--cyan)}
.btn-green{background:rgba(0,255,136,.08);border-color:var(--green);color:var(--green)}
.btn-red{background:rgba(255,51,85,.08);border-color:var(--red);color:var(--red)}
.btn-amber{background:rgba(255,179,0,.08);border-color:var(--amber);color:var(--amber)}
.btn:hover{opacity:.8}
.btn-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}
/* Trap 区块 */
.trap-row{display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap}
.trap-cell label{display:block;color:var(--dim);font-size:9px;margin-bottom:3px}
.trap-cell select,.trap-cell input{background:var(--card);border:1px solid var(--border);color:var(--bright);padding:5px 8px;font-size:11px;font-family:inherit}
.trap-cell input{width:320px}
.trap-cell select:focus,.trap-cell input:focus{outline:none;border-color:var(--amber)}
/* toast */
#toast{position:fixed;bottom:20px;right:20px;background:var(--card);border:1px solid var(--cyan);color:var(--cyan);padding:8px 16px;font-size:11px;letter-spacing:1px;opacity:0;transition:opacity .3s;pointer-events:none;z-index:999}
</style>
</head>
<body>
<header>
  <h1>KVM Simulator Pro</h1>
  <span id="hdr-status">就绪</span>
  <button id="add-sw-btn" onclick="addSwitch()">＋ 添加交换机</button>
</header>
<main>
  <div id="sw-list"></div>
  <div id="detail"><div id="detail-placeholder">← 选择或添加交换机</div></div>
</main>
<div id="toast"></div>

<script>
let _state = { switches: [] };
let _selId = null;

// ── 数据层 ──────────────────────────────────────────────────────────

async function api(path, body) {
  const r = await fetch(path, {
    method: body !== undefined ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

async function loadState() {
  const data = await api('/api/state');
  _state = data;
  renderSwList();
  if (_selId !== null) {
    const sw = _state.switches.find(s => s.id === _selId);
    if (sw) renderDetail(sw); else renderDetail(null);
  }
}

setInterval(loadState, 3000);
loadState();

// ── 交换机列表 ──────────────────────────────────────────────────────

function renderSwList() {
  const el = document.getElementById('sw-list');
  el.innerHTML = _state.switches.map(sw => `
    <div class="sw-item ${sw.id === _selId ? 'active' : ''}" onclick="selectSw(${sw.id})">
      <span class="sw-del" onclick="event.stopPropagation();removeSw(${sw.id})">✕</span>
      <div class="sw-name">${esc(sw.name)}</div>
      <div class="sw-port">UDP :${sw.snmp_port}</div>
    </div>
  `).join('');
}

function selectSw(id) {
  _selId = id;
  const sw = _state.switches.find(s => s.id === id);
  renderSwList();
  renderDetail(sw || null);
}

async function addSwitch() {
  const name = prompt('交换机名称（留空自动命名）', '') || undefined;
  await api('/api/switch/add', { name });
  await loadState();
  toast('交换机已添加');
}

async function removeSw(id) {
  if (!confirm('删除该交换机？')) return;
  await api('/api/switch/remove', { id });
  if (_selId === id) { _selId = null; renderDetail(null); }
  await loadState();
  toast('交换机已删除');
}

// ── 详情面板 ────────────────────────────────────────────────────────

function renderDetail(sw) {
  const el = document.getElementById('detail');
  if (!sw) {
    el.innerHTML = '<div id="detail-placeholder">← 选择或添加交换机</div>';
    return;
  }

  const sysH = renderSysSection(sw);
  const epsH = renderEpsSection(sw);
  const trapH = renderTrapSection(sw);

  el.innerHTML = `
    <div class="section">${sysH}</div>
    <div class="section">${epsH}</div>
    <div class="section">${trapH}</div>
  `;
}

// ── 系统状态区 ──────────────────────────────────────────────────────

function renderSysSection(sw) {
  const s = sw.sys;
  const pOpts = o => [['1','ON'],['0','OFF']].map(([v,l]) =>
    `<option value="${v}" ${s[o]==v||s[o]==parseInt(v)?'selected':''}>${l}</option>`).join('');
  const netOpts = o => [['1','UP'],['0','DOWN']].map(([v,l]) =>
    `<option value="${v}" ${s[o]==v||s[o]==parseInt(v)?'selected':''}>${l}</option>`).join('');

  return `
    <div class="sec-title">交换机状态 — ${esc(sw.name)} (id=${sw.id})</div>
    <div class="sys-grid">
      <div class="sys-cell">
        <label>温度 (°C)</label>
        <input type="number" id="sys_temperature_${sw.id}" value="${s.temperature}" step="0.1">
      </div>
      <div class="sys-cell">
        <label>主电源</label>
        <select id="sys_main_power_${sw.id}">${pOpts('main_power')}</select>
      </div>
      <div class="sys-cell">
        <label>冗余电源</label>
        <select id="sys_redundant_power_${sw.id}">${pOpts('redundant_power')}</select>
      </div>
      <div class="sys-cell">
        <label>网口0</label>
        <select id="sys_net_if0_${sw.id}">${netOpts('net_if0')}</select>
      </div>
      <div class="sys-cell">
        <label>风扇1 (RPM)</label>
        <input type="number" id="sys_fan1_${sw.id}" value="${s.fan1}">
      </div>
      <div class="sys-cell">
        <label>风扇2 (RPM)</label>
        <input type="number" id="sys_fan2_${sw.id}" value="${s.fan2}">
      </div>
      <div class="sys-cell">
        <label>风扇3 (RPM)</label>
        <input type="number" id="sys_fan3_${sw.id}" value="${s.fan3}">
      </div>
      <div class="sys-cell">
        <label>风扇4 (RPM)</label>
        <input type="number" id="sys_fan4_${sw.id}" value="${s.fan4}">
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-cyan" onclick="applySys(${sw.id})">应用系统状态</button>
      <button class="btn btn-red" onclick="applySysPreset(${sw.id},'power_fail')">模拟断电</button>
      <button class="btn btn-amber" onclick="applySysPreset(${sw.id},'overheat')">模拟过温</button>
      <button class="btn btn-green" onclick="applySysPreset(${sw.id},'normal')">恢复正常</button>
    </div>
  `;
}

async function applySys(swId) {
  const fields = {};
  const keys = ['temperature','main_power','redundant_power','net_if0','fan1','fan2','fan3','fan4'];
  for (const k of keys) {
    const el = document.getElementById(`sys_${k}_${swId}`);
    if (!el) continue;
    const v = el.tagName === 'SELECT' ? parseInt(el.value) : parseFloat(el.value);
    fields[k] = v;
  }
  await api('/api/switch/sys_update', { id: swId, fields });
  await loadState();
  toast('系统状态已更新');
}

async function applySysPreset(swId, preset) {
  const presets = {
    power_fail: { main_power: 0, redundant_power: 0 },
    overheat:   { temperature: 72.0 },
    normal:     { main_power: 1, redundant_power: 1, temperature: 45.0, fan1: 3200, fan2: 3150, fan3: 3100, fan4: 3050 },
  };
  await api('/api/switch/sys_update', { id: swId, fields: presets[preset] });
  await loadState();
  toast(`预设 "${preset}" 已应用`);
}

// ── 端点区 ──────────────────────────────────────────────────────────

const STATUS_OPTS_CPU = [[1,'online'],[2,'ready'],[0,'offline']];
const STATUS_OPTS_CON = [[1,'online'],[2,'ready'],[0,'offline']];
const PWR_OPTS = [[1,'on'],[0,'off']];
const KM_OPTS = [[3,'键盘+鼠标'],[1,'仅键盘'],[2,'仅鼠标'],[0,'none']];
const VIDEO_SIG_OPTS = [[5,'DP'],[6,'HDMI'],[2,'DVI-SL'],[3,'DVI-DL'],[1,'VGA'],[0,'none']];
const VIDEO_CABLE_OPTS = [[1,'connected'],[0,'notConnected']];
const USB_HID_OPTS = [[2,'initialized'],[1,'connected'],[0,'notConnected']];
const ACCESS_OPTS = [[0,'local'],[1,'remote'],[2,'localExclusive'],[3,'remoteExclusive']];
const DISPLAY_OPTS = [[1,'connected'],[0,'notConnected']];
const FREEZE_OPTS = [[0,'false'],[1,'true']];
const NET_OPTS = [[1,'up'],[0,'down']];
const TX_PORT_OPTS = [[1,'1'],[2,'2']];

function sel(opts, cur) {
  return opts.map(([v,l]) => `<option value="${v}" ${cur==v?'selected':''}>${l}</option>`).join('');
}

function renderEpsSection(sw) {
  const allEps = [];
  for (const [row, cpu] of Object.entries(sw.cpus||{})) allEps.push({row:parseInt(row),type:'cpu',data:cpu});
  for (const [row, con] of Object.entries(sw.cons||{})) allEps.push({row:parseInt(row),type:'con',data:con});
  allEps.sort((a,b) => a.type.localeCompare(b.type)||a.row-b.row);

  let html = `<div class="sec-title">端点 (CPU: ${Object.keys(sw.cpus||{}).length} / CON: ${Object.keys(sw.cons||{}).length})</div>`;

  for (const ep of allEps) {
    const d = ep.data;
    if (ep.type === 'cpu') {
      html += `
        <div class="ep-item">
          <div class="ep-header">
            <span class="ep-badge cpu">CPU</span>
            <span>Row ${ep.row}</span>
            <span class="ep-id">${esc(d.ep_id)}</span>
            <span class="ep-id" style="color:var(--text)">${esc(d.ep_name)}</span>
            <span class="ep-remove" onclick="removeEp(${sw.id},'cpu',${ep.row})">✕ 拔出</span>
          </div>
          <div class="ep-fields wide">
            <div class="field-cell"><label>在线状态</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_device_status',parseInt(this.value))">
                ${sel(STATUS_OPTS_CPU,d.ep_device_status)}</select></div>
            <div class="field-cell"><label>目标电源</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_target_power',parseInt(this.value))">
                ${sel(PWR_OPTS,d.ep_target_power)}</select></div>
            <div class="field-cell"><label>视频线缆</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_target_video_cable',parseInt(this.value))">
                ${sel(VIDEO_CABLE_OPTS,d.ep_target_video_cable)}</select></div>
            <div class="field-cell"><label>视频信号</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_target_video_signal',parseInt(this.value))">
                ${sel(VIDEO_SIG_OPTS,d.ep_target_video_signal)}</select></div>
            <div class="field-cell"><label>USB HID</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_target_usb_hid',parseInt(this.value))">
                ${sel(USB_HID_OPTS,d.ep_target_usb_hid)}</select></div>
            <div class="field-cell"><label>访问状态</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_target_access',parseInt(this.value))">
                ${sel(ACCESS_OPTS,d.ep_target_access)}</select></div>
            <div class="field-cell"><label>温度 (°C)</label>
              <input type="number" value="${d.ep_temperature}" step="0.1"
                onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_temperature',parseFloat(this.value))"></div>
            <div class="field-cell"><label>网口</label>
              <select onchange="updateEp(${sw.id},'cpu',${ep.row},'ep_net_if0',parseInt(this.value))">
                ${sel(NET_OPTS,d.ep_net_if0)}</select></div>
          </div>
        </div>`;
    } else {
      html += `
        <div class="ep-item">
          <div class="ep-header">
            <span class="ep-badge con">CON</span>
            <span>Row ${ep.row}</span>
            <span class="ep-id">${esc(d.con_id)}</span>
            <span class="ep-id" style="color:var(--text)">${esc(d.con_name)}</span>
            <span class="ep-remove" onclick="removeEp(${sw.id},'con',${ep.row})">✕ 拔出</span>
          </div>
          <div class="ep-fields wide">
            <div class="field-cell"><label>在线状态</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_device_status',parseInt(this.value))">
                ${sel(STATUS_OPTS_CON,d.con_device_status)}</select></div>
            <div class="field-cell"><label>PS/2 键鼠</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_console_ps2',parseInt(this.value))">
                ${sel(KM_OPTS,d.con_console_ps2)}</select></div>
            <div class="field-cell"><label>USB 键鼠</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_console_usb',parseInt(this.value))">
                ${sel(KM_OPTS,d.con_console_usb)}</select></div>
            <div class="field-cell"><label>显示器连接</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_display_conn',parseInt(this.value))">
                ${sel(DISPLAY_OPTS,d.con_display_conn)}</select></div>
            <div class="field-cell"><label>显示器型号</label>
              <input type="text" value="${esc(d.con_display_type)}"
                onchange="updateEp(${sw.id},'con',${ep.row},'con_display_type',this.value)"></div>
            <div class="field-cell"><label>画面冻结</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_freeze',parseInt(this.value))">
                ${sel(FREEZE_OPTS,d.con_freeze)}</select></div>
            <div class="field-cell"><label>活跃TX口</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_active_tx_port',parseInt(this.value))">
                ${sel(TX_PORT_OPTS,d.con_active_tx_port)}</select></div>
            <div class="field-cell"><label>温度 (°C)</label>
              <input type="number" value="${d.con_temperature}" step="0.1"
                onchange="updateEp(${sw.id},'con',${ep.row},'con_temperature',parseFloat(this.value))"></div>
            <div class="field-cell"><label>网口</label>
              <select onchange="updateEp(${sw.id},'con',${ep.row},'con_net_if0',parseInt(this.value))">
                ${sel(NET_OPTS,d.con_net_if0)}</select></div>
          </div>
        </div>`;
    }
  }

  html += `
    <div class="btn-row">
      <button class="btn btn-cyan" onclick="insertEp(${sw.id},'cpu')">＋ 插入 CPU</button>
      <button class="btn btn-green" onclick="insertEp(${sw.id},'con')">＋ 插入 CON</button>
    </div>`;
  return html;
}

async function insertEp(swId, type) {
  await api('/api/endpoint/add', { sw_id: swId, type });
  await loadState();
  const sw = _state.switches.find(s => s.id === swId);
  if (sw) renderDetail(sw);
  toast(`${type.toUpperCase()} 已插入`);
}

async function removeEp(swId, type, row) {
  await api('/api/endpoint/remove', { sw_id: swId, type, row });
  await loadState();
  const sw = _state.switches.find(s => s.id === swId);
  if (sw) renderDetail(sw);
  toast(`${type.toUpperCase()} Row${row} 已拔出`);
}

async function updateEp(swId, type, row, field, value) {
  await api('/api/endpoint/update', { sw_id: swId, type, row, fields: { [field]: value } });
}

// ── Trap 区 ──────────────────────────────────────────────────────────

function renderTrapSection(sw) {
  return `
    <div class="sec-title">手动发送 Trap (→ ${TRAP_HOST}:${TRAP_PORT})</div>
    <div class="trap-row">
      <div class="trap-cell">
        <label>Level</label>
        <select id="trap-level-${sw.id}">
          <option value="5">5 NOTICE (info)</option>
          <option value="4">4 WARNING</option>
          <option value="3" selected>3 ERROR (warning)</option>
          <option value="2">2 CRITICAL</option>
          <option value="1">1 ALERT</option>
          <option value="0">0 EMERGENCY</option>
        </select>
      </div>
      <div class="trap-cell">
        <label>Message</label>
        <input type="text" id="trap-msg-${sw.id}" value="Test trap from KVM Simulator">
      </div>
      <button class="btn btn-amber" onclick="sendTrap(${sw.id})" style="align-self:flex-end">发送 Trap</button>
    </div>
    <div class="btn-row" style="margin-top:10px">
      <button class="btn btn-red" onclick="quickTrap(${sw.id},3,'CPU module CPU-${sw.id}-001 went offline')">CPU 掉线</button>
      <button class="btn btn-green" onclick="quickTrap(${sw.id},5,'CPU module CPU-${sw.id}-001 came online')">CPU 上线</button>
      <button class="btn btn-red" onclick="quickTrap(${sw.id},3,'CON module CON-${sw.id}-001 went offline')">CON 掉线</button>
      <button class="btn btn-green" onclick="quickTrap(${sw.id},5,'CON module CON-${sw.id}-001 came online')">CON 上线</button>
      <button class="btn btn-amber" onclick="quickTrap(${sw.id},4,'Temperature too high on KVM-SIM-${sw.id}: 72.0C')">温度告警</button>
      <button class="btn btn-amber" onclick="quickTrap(${sw.id},3,'Main power failure on KVM-SIM-${sw.id}')">电源告警</button>
    </div>
  `;
}

async function sendTrap(swId) {
  const level = parseInt(document.getElementById(`trap-level-${swId}`).value);
  const message = document.getElementById(`trap-msg-${swId}`).value;
  await api('/api/trap/send', { level, message });
  toast(`Trap 已发送 level=${level}`);
}

async function quickTrap(swId, level, message) {
  await api('/api/trap/send', { level, message });
  toast(`Trap: ${message}`);
}

// ── 工具 ────────────────────────────────────────────────────────────

const TRAP_HOST = location.hostname;
const TRAP_PORT = 10162;

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let _toastTimer = null;
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.opacity = '1';
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.style.opacity = '0', 2500);
}
</script>
</body>
</html>
"""


# ─── 主入口 ───────────────────────────────────────────────────────────

def main():
    logger.info("KVM Simulator Pro 启动")
    logger.info("Web 控制台: http://localhost:%d", WEB_PORT)
    logger.info("Trap 目标: %s:%d", TRAP_HOST, TRAP_PORT)
    logger.info("SNMP 社区: %s", COMMUNITY)
    logger.info("")
    logger.info("使用说明:")
    logger.info("  1. 在 Web UI 中添加交换机，记录其 UDP 端口")
    logger.info("  2. 在 KVM Dashboard 后台添加设备: host=127.0.0.1 port=<UDP端口>")
    logger.info("  3. 通过 Web UI 插拔 CPU/CON、修改状态、发送 Trap")

    # 默认创建一台交换机，方便快速开始
    sw = switch_add("KVM-SIM-1")
    endpoint_add(sw["id"], "cpu")
    endpoint_add(sw["id"], "cpu")
    endpoint_add(sw["id"], "cpu")
    endpoint_add(sw["id"], "con")
    endpoint_add(sw["id"], "con")
    logger.info("默认交换机已创建: %s UDP:%d", sw["name"], sw["snmp_port"])

    httpd = HTTPServer(("0.0.0.0", WEB_PORT), _ApiHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("模拟器已停止")
        httpd.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
