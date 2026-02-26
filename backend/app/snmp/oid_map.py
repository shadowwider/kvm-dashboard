"""
G&D CCDC KVM 系列 OID 定义基础库。
企业号: 1.3.6.1.4.1.32828 (Guntermann & Drunck GmbH)

所有 OID 均根据以下真实数据源校准：
  - help/config.py（demo 中与真机 192.168.0.1 对接验证的配置）
  - help/kvm_status.json（真机返回数据）
  - help/snmp_simulator.py（模拟器 OID 映射）
  - help/kvm_snmp_monitor.log（真机通信日志）
  - MIB 文件：GUD-CCDC-MIB.txt, GUD-CCDCCPU-MIB.txt

此文件定义所有已知 OID 的静态映射，作为 oid_registry 表的初始数据种子。
运行时实际使用的监控项从数据库 oid_registry 表动态读取。
"""

# 企业根 OID
GUD_ENTERPRISE = "1.3.6.1.4.1.32828"
GUD_CCDC_BASE = f"{GUD_ENTERPRISE}.3.257.16"

# -------------------------------------------------------------------
# 设备基础信息 (GUD-CCDC-MIB: objects.identify = gudCCDC.2.1)
# -------------------------------------------------------------------
DEVICE_IDENTIFY_BASE = f"{GUD_CCDC_BASE}.2.1"
DEVICE_VERSION_BASE = f"{GUD_CCDC_BASE}.2.2"

DEVICE_OIDS = {
    # 基础信息 (gudCCDC.2.1.x.0)
    "device_id":        f"{DEVICE_IDENTIFY_BASE}.1.0",   # deviceId
    "device_class":     f"{DEVICE_IDENTIFY_BASE}.2.0",   # deviceCl (类别编号 257)
    "device_type":      f"{DEVICE_IDENTIFY_BASE}.3.0",   # deviceType (ControlCenter-Compact-8C)
    "device_serial":    f"{DEVICE_IDENTIFY_BASE}.4.0",   # serialNumber (GD03217157)
    "device_mac0":      f"{DEVICE_IDENTIFY_BASE}.5.0",   # etherAddress0
    "device_mac1":      f"{DEVICE_IDENTIFY_BASE}.6.0",   # etherAddress1

    # 固件版本 (gudCCDC.2.2.x.0)
    "device_firmware":  f"{DEVICE_VERSION_BASE}.1.0",    # firmwareVersion (1.7.000)

    # 设备状态 (gudCCDC.2.3.x.0)  ⚠️ 编号是稀疏的！
    "main_power":       f"{GUD_CCDC_BASE}.2.3.1.0",     # mainPower
    "redundant_power":  f"{GUD_CCDC_BASE}.2.3.2.0",     # redundantPower
    "temperature":      f"{GUD_CCDC_BASE}.2.3.3.0",     # temperature1
    "power_current":    f"{GUD_CCDC_BASE}.2.3.500.0",   # powerCurrent
    "power_voltage":    f"{GUD_CCDC_BASE}.2.3.501.0",   # powerVoltage
    "fan1":             f"{GUD_CCDC_BASE}.2.3.502.0",   # fan1
    "fan2":             f"{GUD_CCDC_BASE}.2.3.503.0",   # fan2
    "fan3":             f"{GUD_CCDC_BASE}.2.3.504.0",   # fan3
    "fan4":             f"{GUD_CCDC_BASE}.2.3.505.0",   # fan4
    "fan5":             f"{GUD_CCDC_BASE}.2.3.508.0",   # fan5 (注: 跳过了506/507)
    "fan6":             f"{GUD_CCDC_BASE}.2.3.509.0",   # fan6
    "net_if0":          f"{GUD_CCDC_BASE}.2.3.506.0",   # networkInterface0
    "net_if1":          f"{GUD_CCDC_BASE}.2.3.507.0",   # networkInterface1
}

# -------------------------------------------------------------------
# 终端模块表 (GUD-CCDCCPU-MIB: targetModuleTable)
# gudCCDCCPU.2.3.1000.1 = gudCCDC.1.2.2.3.1000.1
# OID: ...1000.1.{column}.{row}
# 列号来源: help/config.py 和 help/snmp_simulator.py 已验证
# -------------------------------------------------------------------
ENDPOINT_TABLE_ENTRY = f"{GUD_ENTERPRISE}.3.257.16.1.2.2.3.1000.1"

ENDPOINT_COLUMNS = {
    "ep_id":                  2,   # id (设备 hex ID)
    "ep_class":               3,   # cl (类别编号)
    "ep_name":                4,   # name (显示名称)
    "ep_device_status":       5,   # deviceStatus
    "ep_main_power":          6,   # mainPower
    "ep_redundant_power":     7,   # redundantPower
    "ep_temperature":         8,   # temperature1
    "ep_console_ps2":         9,   # consolePS2Connection
    "ep_console_usb":         10,  # consoleUSBConnection
    "ep_target_ps2":          11,  # targetPS2Connection
    "ep_target_usb_hid":      12,  # targetUsbHid
    "ep_target_video_cable":  13,  # targetVideoCable
    "ep_target_video_cable1": 14,  # targetVideoCable1
    "ep_target_video_cable2": 15,  # targetVideoCable2
    "ep_target_video_signal": 16,  # targetVideoSignal
    "ep_target_video_signal1":17,  # targetVideoSignal1
    "ep_target_video_signal2":18,  # targetVideoSignal2
    "ep_target_power":        19,  # targetPower
    "ep_target_access":       20,  # targetAccess
    "ep_sfp_tx_power":        21,  # sfpTxPower (uW)
    "ep_sfp_rx_power":        22,  # sfpRxPower (uW)
    "ep_sfp_type":            23,  # sfpType
    "ep_net_if0":             24,  # networkInterface0
}

# -------------------------------------------------------------------
# 端口表 (GUD-CCDC-MIB: portTable)
# gudCCDC.2.3.1000.1.{column}.{row}
# -------------------------------------------------------------------
PORT_TABLE_ENTRY = f"{GUD_CCDC_BASE}.2.3.1000.1"

PORT_COLUMNS = {
    "port_status":         2,    # portStatus (0=noModule,1=deactivated,2=down,3=up)
    "port_sfp_module":     3,    # portSfpModule
    "port_sfp_tx_power":   4,    # portSfpTxPower
    "port_sfp_rx_power":   5,    # portSfpRxPower
    "port_sfp_type":       6,    # portSfpType
}


def get_endpoint_column_oid(col_name: str, row_index: int) -> str:
    col_num = ENDPOINT_COLUMNS[col_name]
    return f"{ENDPOINT_TABLE_ENTRY}.{col_num}.{row_index}"

def get_endpoint_table_base_oid(col_name: str) -> str:
    col_num = ENDPOINT_COLUMNS[col_name]
    return f"{ENDPOINT_TABLE_ENTRY}.{col_num}"

def get_port_column_oid(col_name: str, row_index: int) -> str:
    col_num = PORT_COLUMNS[col_name]
    return f"{PORT_TABLE_ENTRY}.{col_num}.{row_index}"

def get_port_table_base_oid(col_name: str) -> str:
    col_num = PORT_COLUMNS[col_name]
    return f"{PORT_TABLE_ENTRY}.{col_num}"


# -------------------------------------------------------------------
# 枚举值映射（与 help/config.py STATUS_ENUM 完全一致）
# -------------------------------------------------------------------
ENUM_MAPS = {
    "power_status": {0: "off", 1: "on"},
    "device_status": {0: "offline", 1: "online", 2: "ready"},
    "net_if_status": {0: "down", 1: "up"},
    "connection": {0: "notConnected", 1: "connected"},
    "keyboard_mouse": {0: "none", 1: "keyboard", 2: "mouse", 3: "keyboardMouse"},
    "usb_hid": {0: "notConnected", 1: "connected", 2: "initialized"},
    "video_type": {
        0: "none", 1: "vga", 2: "dvisl", 3: "dvidl",
        4: "dmdp", 5: "dp", 6: "hdmi",
    },
    "access_status": {
        0: "local", 1: "remote",
        2: "localExclusive", 3: "remoteExclusive",
    },
    "port_status": {
        0: "noModule", 1: "moduleDeactivated", 2: "down", 3: "up",
    },
}

# -------------------------------------------------------------------
# 初始化 OID 注册表的种子数据
# -------------------------------------------------------------------
SEED_OID_REGISTRY = [
    # ─── 设备基础信息 ───────────────────────────────────────────────
    {"name": "device_id",       "oid": DEVICE_OIDS["device_id"],       "display_name": "设备ID",     "category": "device", "data_type": "string", "display_order": 1},
    {"name": "device_class",    "oid": DEVICE_OIDS["device_class"],    "display_name": "设备类别",   "category": "device", "data_type": "string", "display_order": 2},
    {"name": "device_type",     "oid": DEVICE_OIDS["device_type"],     "display_name": "设备类型",   "category": "device", "data_type": "string", "display_order": 3},
    {"name": "device_serial",   "oid": DEVICE_OIDS["device_serial"],   "display_name": "序列号",     "category": "device", "data_type": "string", "display_order": 4},
    {"name": "device_mac0",     "oid": DEVICE_OIDS["device_mac0"],     "display_name": "MAC地址0",   "category": "device", "data_type": "string", "display_order": 5},
    {"name": "device_mac1",     "oid": DEVICE_OIDS["device_mac1"],     "display_name": "MAC地址1",   "category": "device", "data_type": "string", "display_order": 6},
    {"name": "device_firmware", "oid": DEVICE_OIDS["device_firmware"], "display_name": "固件版本",   "category": "device", "data_type": "string", "display_order": 7},

    # ─── 设备状态 ───────────────────────────────────────────────────
    {"name": "main_power",      "oid": DEVICE_OIDS["main_power"],      "display_name": "主电源",     "category": "device", "data_type": "enum",    "enum_map": ENUM_MAPS["power_status"],       "alert_enabled": True,  "alert_ne_str": "on",    "alert_severity": "critical", "display_order": 10},
    {"name": "redundant_power", "oid": DEVICE_OIDS["redundant_power"], "display_name": "冗余电源",   "category": "device", "data_type": "enum",    "enum_map": ENUM_MAPS["power_status"],       "alert_enabled": True,  "alert_ne_str": "on",    "alert_severity": "warning",  "display_order": 11},
    {"name": "temperature",     "oid": DEVICE_OIDS["temperature"],     "display_name": "温度",       "category": "device", "data_type": "float",   "unit": "°C",   "alert_enabled": True,  "alert_gt": 55.0, "alert_severity": "warning",  "display_order": 12},
    {"name": "power_current",   "oid": DEVICE_OIDS["power_current"],   "display_name": "电流",       "category": "device", "data_type": "float",   "unit": "A",    "alert_enabled": False, "display_order": 13},
    {"name": "power_voltage",   "oid": DEVICE_OIDS["power_voltage"],   "display_name": "电压",       "category": "device", "data_type": "float",   "unit": "V",    "alert_enabled": False, "display_order": 14},
    {"name": "fan1",            "oid": DEVICE_OIDS["fan1"],            "display_name": "风扇1",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 20},
    {"name": "fan2",            "oid": DEVICE_OIDS["fan2"],            "display_name": "风扇2",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 21},
    {"name": "fan3",            "oid": DEVICE_OIDS["fan3"],            "display_name": "风扇3",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 22},
    {"name": "fan4",            "oid": DEVICE_OIDS["fan4"],            "display_name": "风扇4",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 23},
    {"name": "fan5",            "oid": DEVICE_OIDS["fan5"],            "display_name": "风扇5",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 24},
    {"name": "fan6",            "oid": DEVICE_OIDS["fan6"],            "display_name": "风扇6",      "category": "device", "data_type": "integer", "unit": "RPM",  "alert_enabled": True,  "alert_lt": 500.0,  "alert_severity": "warning",  "display_order": 25},
    {"name": "net_if0",         "oid": DEVICE_OIDS["net_if0"],         "display_name": "网口0",      "category": "device", "data_type": "enum",    "enum_map": ENUM_MAPS["net_if_status"],      "alert_enabled": True,  "alert_ne_str": "up",    "alert_severity": "warning",  "display_order": 30},
    {"name": "net_if1",         "oid": DEVICE_OIDS["net_if1"],         "display_name": "网口1",      "category": "device", "data_type": "enum",    "enum_map": ENUM_MAPS["net_if_status"],      "alert_enabled": False, "display_order": 31},

    # ─── 终端模块（SNMP Table，23个列）──────────────────────────────
    {"name": "ep_id",                  "display_name": "终端ID",         "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 2,  "alert_enabled": False, "display_order": 100},
    {"name": "ep_class",               "display_name": "终端类别",       "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 3,  "alert_enabled": False, "display_order": 101},
    {"name": "ep_name",                "display_name": "终端名称",       "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 4,  "alert_enabled": False, "display_order": 102},
    {"name": "ep_device_status",       "display_name": "在线状态",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 5,  "enum_map": ENUM_MAPS["device_status"],     "alert_enabled": True,  "alert_ne_str": "online", "alert_severity": "warning",  "display_order": 103},
    {"name": "ep_main_power",          "display_name": "终端主电源",     "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 6,  "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": False, "display_order": 104},
    {"name": "ep_redundant_power",     "display_name": "终端冗余电源",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 7,  "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": False, "display_order": 105},
    {"name": "ep_temperature",         "display_name": "终端温度",       "category": "endpoint", "data_type": "float",   "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 8,  "unit": "°C",  "alert_enabled": False, "display_order": 106},
    {"name": "ep_console_ps2",         "display_name": "控制台PS/2",     "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 9,  "enum_map": ENUM_MAPS["keyboard_mouse"],    "alert_enabled": False, "display_order": 107},
    {"name": "ep_console_usb",         "display_name": "控制台USB",      "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 10, "enum_map": ENUM_MAPS["keyboard_mouse"],    "alert_enabled": False, "display_order": 108},
    {"name": "ep_target_ps2",          "display_name": "目标PS/2",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 11, "enum_map": ENUM_MAPS["keyboard_mouse"],    "alert_enabled": False, "display_order": 109},
    {"name": "ep_target_usb_hid",      "display_name": "目标USB-HID",    "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 12, "enum_map": ENUM_MAPS["usb_hid"],           "alert_enabled": False, "display_order": 110},
    {"name": "ep_target_video_cable",  "display_name": "视频线缆",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 13, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": True,  "alert_ne_str": "connected", "alert_severity": "info", "display_order": 111},
    {"name": "ep_target_video_cable1", "display_name": "视频线缆1",      "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 14, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": False, "display_order": 112},
    {"name": "ep_target_video_cable2", "display_name": "视频线缆2",      "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 15, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": False, "display_order": 113},
    {"name": "ep_target_video_signal", "display_name": "视频信号",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 16, "enum_map": ENUM_MAPS["video_type"],        "alert_enabled": True,  "alert_eq_str": "none", "alert_severity": "info", "display_order": 114},
    {"name": "ep_target_video_signal1","display_name": "视频信号1",      "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 17, "enum_map": ENUM_MAPS["video_type"],        "alert_enabled": False, "display_order": 115},
    {"name": "ep_target_video_signal2","display_name": "视频信号2",      "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 18, "enum_map": ENUM_MAPS["video_type"],        "alert_enabled": False, "display_order": 116},
    {"name": "ep_target_power",        "display_name": "目标电源",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 19, "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": True,  "alert_ne_str": "on",     "alert_severity": "warning", "display_order": 117},
    {"name": "ep_target_access",       "display_name": "访问状态",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 20, "enum_map": ENUM_MAPS["access_status"],     "alert_enabled": False, "display_order": 118},
    {"name": "ep_sfp_tx_power",        "display_name": "SFP发送功率",    "category": "endpoint", "data_type": "integer", "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 21, "unit": "uW",  "alert_enabled": False, "display_order": 119},
    {"name": "ep_sfp_rx_power",        "display_name": "SFP接收功率",    "category": "endpoint", "data_type": "integer", "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 22, "unit": "uW",  "alert_enabled": False, "display_order": 120},
    {"name": "ep_sfp_type",            "display_name": "SFP类型",        "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 23, "alert_enabled": False, "display_order": 121},
    {"name": "ep_net_if0",             "display_name": "终端网口",       "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": 24, "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": False, "display_order": 122},

    # ─── 端口表（SNMP Table）────────────────────────────────────────
    {"name": "port_status",        "display_name": "端口状态",     "category": "port", "data_type": "enum",    "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 2,  "enum_map": ENUM_MAPS["port_status"],  "alert_enabled": False, "display_order": 200},
    {"name": "port_sfp_module",    "display_name": "SFP模块",      "category": "port", "data_type": "enum",    "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 3,  "enum_map": ENUM_MAPS["port_status"],  "alert_enabled": False, "display_order": 201},
    {"name": "port_sfp_tx_power",  "display_name": "端口发送功率", "category": "port", "data_type": "integer",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 4,  "unit": "uW",  "alert_enabled": False, "display_order": 202},
    {"name": "port_sfp_rx_power",  "display_name": "端口接收功率", "category": "port", "data_type": "integer",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 5,  "unit": "uW",  "alert_enabled": False, "display_order": 203},
    {"name": "port_sfp_type",      "display_name": "端口SFP类型",  "category": "port", "data_type": "string",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 6,  "alert_enabled": False, "display_order": 204},
]
