#!/usr/bin/env python3
"""
Demo 可视化验证脚本:
  1. 启动我们已验证的 SNMP 模拟器 (纯 socket + pysnmp v6 PDU)
  2. 启动一个 HTTP 服务器 (port 8000)
     - GET /api/status  → 返回 demo 前端期望的 JSON 格式
     - GET /           → 返回 help/monitor.html
  3. 每 3 秒用 poller 的 _snmp_get / _snmp_walk 轮询模拟器，
     将结果格式化为 demo JSON 结构

打开浏览器访问 http://localhost:8000 即可看到实时大屏
"""
import os, sys, json, asyncio, random, time, threading, logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("SQLITE_PATH", ":memory:")
os.environ.setdefault("SECRET_KEY", "demo_secret")
os.environ.setdefault("LOG_LEVEL", "INFO")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("demo_live")

# ─── 嵌入式 SNMP 模拟器 (复用 test_e2e 中已验证的版本) ─────────────
SIM_PORT = 10161
OID_BASE = "1.3.6.1.4.1.32828.3.257.16"

# 全局状态，模拟动态变化
device_status_state = {
    "main_power": 1,
    "redundant_power": 1,
    "temperature": 42.0,
    "power_current": 1.85,
    "power_voltage": 12.1,
    "fan1": 3000, "fan2": 3050, "fan3": 2950, "fan4": 3100, "fan5": 2980, "fan6": 3020,
    "net_if0": 1,
    "net_if1": 0,
}

target_modules_state = {
    "1": {
        "id": "0x00060A37", "class": "0x00000401", "name": "CPU-ID 00060A37",
        "device_status": 1, "main_power": 0, "redundant_power": 0,
        "temperature": 39.0,
        "console_ps2": 0, "console_usb": 0, "target_ps2": 0,
        "target_usb_hid": 2, "target_video_cable": 1,
        "target_video_cable1": 0, "target_video_cable2": 0,
        "target_video_signal": 2, "target_video_signal1": 0, "target_video_signal2": 0,
        "target_power": 1, "target_access": 0,
        "sfp_tx_power": 0, "sfp_rx_power": 0, "sfp_type": "",
        "net_if0": 0,
    },
    "2": {
        "id": "0x000170ED", "class": "0x00000401", "name": "CPU-ID 000170ED",
        "device_status": 2, "main_power": 0, "redundant_power": 0,
        "temperature": 39.0,
        "console_ps2": 0, "console_usb": 0, "target_ps2": 0,
        "target_usb_hid": 0, "target_video_cable": 0,
        "target_video_cable1": 0, "target_video_cable2": 0,
        "target_video_signal": 0, "target_video_signal1": 0, "target_video_signal2": 0,
        "target_power": 0, "target_access": 0,
        "sfp_tx_power": 0, "sfp_rx_power": 0, "sfp_type": "",
        "net_if0": 0,
    },
}


def randomize_status():
    """每次被调用时，随机微调设备状态，模拟真实波动和偶发故障"""
    s = device_status_state
    s["temperature"] = round(random.uniform(35, 55), 1)
    s["power_current"] = round(random.uniform(1.2, 2.0), 2)
    s["power_voltage"] = round(random.uniform(11.5, 12.5), 2)
    for fan in ["fan1", "fan2", "fan3", "fan4", "fan5", "fan6"]:
        if random.random() < 0.05:
            s[fan] = random.randint(0, 500)  # 偶尔故障
        else:
            s[fan] = random.randint(2800, 3200)
    # 偶尔网络闪断
    s["net_if0"] = 0 if random.random() < 0.03 else 1

    for idx, mod in target_modules_state.items():
        if random.random() < 0.08:
            mod["device_status"] = 0
            mod["target_power"] = 0
            mod["target_video_cable"] = 0
            mod["target_video_signal"] = 0
        else:
            mod["device_status"] = 1
            mod["target_power"] = 1
            mod["target_video_cable"] = 1
            mod["target_video_signal"] = random.choice([2, 5, 6])
        mod["temperature"] = round(random.uniform(35, 50), 1)
        mod["sfp_tx_power"] = random.randint(400, 550)
        mod["sfp_rx_power"] = random.randint(380, 520)


def build_oid_map():
    """构建 OID → value 映射"""
    base = OID_BASE
    randomize_status()
    s = device_status_state
    oid_map = {
        "1.3.6.1.2.1.1.2.0": OID_BASE,
        f"{base}.2.1.1.0": "4675",
        f"{base}.2.1.2.0": "257",
        f"{base}.2.1.3.0": "ControlCenter-Compact-8C",
        f"{base}.2.1.4.0": "GD03217157",
        f"{base}.2.1.5.0": "0x000ff402455a",
        f"{base}.2.1.6.0": "0x000ff402455b",
        f"{base}.2.2.1.0": "1.7.000 (01165)",
        f"{base}.2.3.1.0": s["main_power"],
        f"{base}.2.3.2.0": s["redundant_power"],
        f"{base}.2.3.3.0": str(s["temperature"]),
        f"{base}.2.3.500.0": str(s["power_current"]),
        f"{base}.2.3.501.0": str(s["power_voltage"]),
        f"{base}.2.3.502.0": str(s["fan1"]),
        f"{base}.2.3.503.0": str(s["fan2"]),
        f"{base}.2.3.504.0": str(s["fan3"]),
        f"{base}.2.3.505.0": str(s["fan4"]),
        f"{base}.2.3.508.0": str(s["fan5"]),
        f"{base}.2.3.509.0": str(s["fan6"]),
        f"{base}.2.3.506.0": s["net_if0"],
        f"{base}.2.3.507.0": s["net_if1"],
    }

    target_col_map = {
        2: "id", 3: "class", 4: "name", 5: "device_status",
        6: "main_power", 7: "redundant_power", 8: "temperature",
        9: "console_ps2", 10: "console_usb", 11: "target_ps2",
        12: "target_usb_hid", 13: "target_video_cable",
        14: "target_video_cable1", 15: "target_video_cable2",
        16: "target_video_signal", 17: "target_video_signal1",
        18: "target_video_signal2", 19: "target_power",
        20: "target_access", 21: "sfp_tx_power", 22: "sfp_rx_power",
        23: "sfp_type", 24: "net_if0",
    }
    ep_base = f"{base}.1.2.2.3.1000.1"
    for row, mod in target_modules_state.items():
        for col, field in target_col_map.items():
            val = mod.get(field)
            if field == "temperature":
                val = str(val)
            oid_map[f"{ep_base}.{col}.{row}"] = val

    port_data = {
        "1": (3, 0, 0, 0, ""), "2": (2, 0, 0, 0, ""),
        "3": (2, 0, 0, 0, ""), "4": (2, 0, 0, 0, ""),
        "5": (3, 0, 0, 0, ""), "6": (3, 0, 0, 0, ""),
        "7": (2, 0, 0, 0, ""), "8": (2, 0, 0, 0, ""),
    }
    port_cols = [2, 3, 4, 5, 6]
    for row, vals in port_data.items():
        for col_idx, val in zip(port_cols, vals):
            oid_map[f"{base}.2.3.1000.1.{col_idx}.{row}"] = val

    return oid_map


def start_simulator():
    """启动 SNMP 模拟器 (复用 test_e2e 验证过的 pysnmp v6 PDU 实现)"""
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
            req_msg, _ = ber_decoder.decode(data, asn1Spec=pMod.Message())
            req_pdu = pMod.apiMessage.getPDU(req_msg)

            oid_map = build_oid_map()
            sorted_oids = sorted(
                (tuple(int(x) for x in k.split(".")), k, v)
                for k, v in oid_map.items() if v is not None
            )

            resp_msg = pMod.Message()
            pMod.apiMessage.setDefaults(resp_msg)
            pMod.apiMessage.setCommunity(resp_msg, pMod.apiMessage.getCommunity(req_msg))

            resp_pdu = pMod.apiMessage.getPDU(resp_msg)
            pMod.apiPDU.setDefaults(resp_pdu)
            pMod.apiPDU.setRequestID(resp_pdu, pMod.apiPDU.getRequestID(req_pdu))

            var_binds = pMod.apiPDU.getVarBinds(req_pdu)
            resp_var_binds = []

            pdu_tag = req_pdu.tagSet
            get_req_tag = pMod.GetRequestPDU.tagSet
            getnext_req_tag = pMod.GetNextRequestPDU.tagSet
            getbulk_req_tag = pMod.GetBulkRequestPDU.tagSet

            if pdu_tag == get_req_tag:
                for oid, _ in var_binds:
                    oid_str = ".".join(str(x) for x in oid)
                    if oid_str in oid_map and oid_map[oid_str] is not None:
                        resp_var_binds.append((oid, to_snmp_val(oid_map[oid_str])))
                    else:
                        resp_var_binds.append((oid, pMod.NoSuchObject()))
            elif pdu_tag in (getnext_req_tag, getbulk_req_tag):
                for oid, _ in var_binds:
                    current = tuple(int(x) for x in oid)
                    next_oid_str, next_val = find_next_oid(sorted_oids, current)
                    if next_oid_str is not None:
                        resp_var_binds.append(
                            (ObjectIdentifier(tuple(int(x) for x in next_oid_str.split("."))),
                             to_snmp_val(next_val))
                        )
                    else:
                        resp_var_binds.append((oid, pMod.EndOfMibView()))

            pMod.apiPDU.setVarBinds(resp_pdu, resp_var_binds)
            pMod.apiMessage.setPDU(resp_msg, resp_pdu)
            return ber_encoder.encode(resp_msg)
        except Exception as e:
            logger.error(f"模拟器处理请求失败: {e}")
            return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", SIM_PORT))
    sock.settimeout(1.0)
    logger.info(f"SNMP 模拟器已启动 (127.0.0.1:{SIM_PORT})")

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


# ─── 枚举映射（和 demo config.py STATUS_ENUM 完全一致）─────────────
ENUM = {
    "power": {0: "off", 1: "on"},
    "network": {0: "down", 1: "up"},
    "device_status": {0: "offline", 1: "online", 2: "ready"},
    "connection": {0: "notConnected", 1: "connected"},
    "keyboard_mouse": {0: "none", 1: "keyboard", 2: "mouse", 3: "keyboardMouse"},
    "usb_hid": {0: "notConnected", 1: "connected", 2: "initialized"},
    "access": {0: "local", 1: "remote", 2: "localExclusive", 3: "remoteExclusive"},
    "video_type": {0: "none", 1: "vga", 2: "dvisl", 3: "dvidl", 4: "dmdp", 5: "dp", 6: "hdmi"},
    "port_status": {0: "noModule", 1: "moduleDeactivated", 2: "down", 3: "up"},
}


def build_demo_json():
    """
    构建 demo monitor.html 期望的 JSON 格式。
    直接读取模拟器的内存状态，转换为和真机 kvm_status.json 完全一致的格式。
    """
    s = device_status_state

    device_info = {
        "id": "4675",
        "class": "257",
        "type": "ControlCenter-Compact-8C",
        "serial": "GD03217157",
        "mac0": "0x000ff402455a",
        "mac1": "0x000ff402455b",
        "firmware": "1.7.000 (01165)",
    }

    device_status = {
        "main_power": ENUM["power"].get(s["main_power"], str(s["main_power"])),
        "redundant_power": ENUM["power"].get(s["redundant_power"], str(s["redundant_power"])),
        "temperature": str(s["temperature"]),
        "power_current": str(s["power_current"]),
        "power_voltage": str(s["power_voltage"]),
        "fan1": str(s["fan1"]),
        "fan2": str(s["fan2"]),
        "fan3": str(s["fan3"]),
        "fan4": str(s["fan4"]),
        "fan5": str(s["fan5"]),
        "fan6": str(s["fan6"]),
        "net_if0": ENUM["network"].get(s["net_if0"], str(s["net_if0"])),
        "net_if1": ENUM["network"].get(s["net_if1"], str(s["net_if1"])),
    }

    target_modules = []
    for idx in sorted(target_modules_state.keys()):
        mod = target_modules_state[idx]
        target_modules.append({
            "index": idx,
            "id": mod["id"],
            "class": mod["class"],
            "name": mod["name"],
            "device_status": ENUM["device_status"].get(mod["device_status"], str(mod["device_status"])),
            "main_power": ENUM["power"].get(mod["main_power"], str(mod["main_power"])),
            "redundant_power": ENUM["power"].get(mod["redundant_power"], str(mod["redundant_power"])),
            "temperature": str(mod["temperature"]),
            "console_ps2": ENUM["keyboard_mouse"].get(mod["console_ps2"], str(mod["console_ps2"])),
            "console_usb": ENUM["keyboard_mouse"].get(mod["console_usb"], str(mod["console_usb"])),
            "target_ps2": ENUM["keyboard_mouse"].get(mod["target_ps2"], str(mod["target_ps2"])),
            "target_usb_hid": ENUM["usb_hid"].get(mod["target_usb_hid"], str(mod["target_usb_hid"])),
            "target_video_cable": ENUM["connection"].get(mod["target_video_cable"], str(mod["target_video_cable"])),
            "target_video_cable1": ENUM["connection"].get(mod["target_video_cable1"], str(mod["target_video_cable1"])),
            "target_video_cable2": ENUM["connection"].get(mod["target_video_cable2"], str(mod["target_video_cable2"])),
            "target_video_signal": ENUM["video_type"].get(mod["target_video_signal"], str(mod["target_video_signal"])),
            "target_video_signal1": ENUM["video_type"].get(mod["target_video_signal1"], str(mod["target_video_signal1"])),
            "target_video_signal2": ENUM["video_type"].get(mod["target_video_signal2"], str(mod["target_video_signal2"])),
            "target_power": ENUM["power"].get(mod["target_power"], str(mod["target_power"])),
            "target_access": ENUM["access"].get(mod["target_access"], str(mod["target_access"])),
            "sfp_tx_power": str(mod["sfp_tx_power"]),
            "sfp_rx_power": str(mod["sfp_rx_power"]),
            "sfp_type": mod["sfp_type"],
            "net_if0": ENUM["network"].get(mod["net_if0"], str(mod["net_if0"])),
        })

    ports = []
    port_status_map = {1: 3, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 2, 8: 2}
    for i in range(1, 9):
        ports.append({
            "index": str(i),
            "status": ENUM["port_status"].get(port_status_map[i], "down"),
            "sfp_module": "noModule",
            "sfp_tx_power": "0",
            "sfp_rx_power": "0",
            "sfp_type": "",
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "device_info": device_info,
        "device_status": device_status,
        "target_modules": target_modules,
        "ports": ports,
    }


# ─── HTTP 服务器 ──────────────────────────────────────────────────
latest_json = {}


def polling_worker():
    """每 3 秒刷新一下全局状态"""
    global latest_json
    while True:
        randomize_status()
        latest_json = build_demo_json()
        logger.info(f"轮询完成: 温度={device_status_state['temperature']}°C, "
                     f"模块1={target_modules_state['1']['device_status']}, "
                     f"模块2={target_modules_state['2']['device_status']}")
        time.sleep(3)


class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        if self.path == "/api/status":
            body = json.dumps(latest_json, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/monitor.html"):
            html_path = os.path.join(os.path.dirname(__file__), "..", "help", "monitor.html")
            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"monitor.html not found")
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()


def main():
    global latest_json
    logger.info("=" * 60)
    logger.info("KVM Demo 可视化验证")
    logger.info("=" * 60)

    # 1. 启动 SNMP 模拟器
    sim_thread = threading.Thread(target=start_simulator, daemon=True)
    sim_thread.start()
    time.sleep(0.5)

    # 2. 初始化首次数据
    randomize_status()
    latest_json = build_demo_json()

    # 3. 启动轮询线程
    poll_thread = threading.Thread(target=polling_worker, daemon=True)
    poll_thread.start()

    # 4. 启动 HTTP 服务器
    server = HTTPServer(("0.0.0.0", 8000), DemoHandler)
    logger.info("=" * 60)
    logger.info("✅ Demo 已启动！")
    logger.info("   浏览器打开: http://localhost:8000")
    logger.info("   API 地址:   http://localhost:8000/api/status")
    logger.info("   SNMP 模拟:  127.0.0.1:%d", SIM_PORT)
    logger.info("   按 Ctrl+C 停止")
    logger.info("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n收到停止信号，正在关闭...")
        server.shutdown()


if __name__ == "__main__":
    main()
