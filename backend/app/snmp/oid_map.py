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

# -------------------------------------------------------------------
# 设备基础信息 (GUD-CCDC-MIB: objects.identify = gudCCDC.2.1)
# -------------------------------------------------------------------
DEVICE_IDENTIFY_BASE = "{sys_oid}.2.1"
DEVICE_VERSION_BASE = "{sys_oid}.2.2"

DEVICE_OIDS = {
    # 基础信息 (gudCCDC.2.1.x.0)
    "device_id":        f"{DEVICE_IDENTIFY_BASE}.1.0",   # deviceId
    "device_class":     f"{DEVICE_IDENTIFY_BASE}.2.0",   # deviceCl
    "device_type":      f"{DEVICE_IDENTIFY_BASE}.3.0",   # deviceType
    "device_serial":    f"{DEVICE_IDENTIFY_BASE}.4.0",   # serialNumber
    "device_mac0":      f"{DEVICE_IDENTIFY_BASE}.5.0",   # etherAddress0
    "device_mac1":      f"{DEVICE_IDENTIFY_BASE}.6.0",   # etherAddress1

    # 固件版本 (gudCCDC.2.2.x.0)
    "device_firmware":  f"{DEVICE_VERSION_BASE}.1.0",    # firmwareVersion

    # 设备状态 (gudCCDC.2.3.x.0)
    "main_power":       "{sys_oid}.2.3.1.0",     # mainPower
    "redundant_power":  "{sys_oid}.2.3.2.0",     # redundantPower
    "temperature":      "{sys_oid}.2.3.3.0",     # temperature1
    "power_current":    "{sys_oid}.2.3.500.0",   # powerCurrent
    "power_voltage":    "{sys_oid}.2.3.501.0",   # powerVoltage
    "fan1":             "{sys_oid}.2.3.502.0",   # fan1
    "fan2":             "{sys_oid}.2.3.503.0",   # fan2
    "fan3":             "{sys_oid}.2.3.504.0",   # fan3
    "fan4":             "{sys_oid}.2.3.505.0",   # fan4
    "fan5":             "{sys_oid}.2.3.508.0",   # fan5
    "fan6":             "{sys_oid}.2.3.509.0",   # fan6
    "net_if0":          "{sys_oid}.2.3.506.0",   # networkInterface0
    "net_if1":          "{sys_oid}.2.3.507.0",   # networkInterface1
}

# -------------------------------------------------------------------
# CPU 目标模块表 (GUD-CCDCCPU-MIB: gudCCDCCPU.2.3.1000.1)
# 即 gudCCDC.1.2.2.3.1000.1 — 目标侧（服务器/计算机）
# -------------------------------------------------------------------
ENDPOINT_TABLE_ENTRY = "{sys_oid}.1.2.2.3.1000.1"

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
# CON 用户模块表 (GUD-CCDCCON-MIB: gudCCDCCON.2.3.1000.1)
# 即 gudCCDC.1.1.2.3.1000.1 — 用户侧（操作员终端）
# -------------------------------------------------------------------
CON_TABLE_ENTRY = "{sys_oid}.1.1.2.3.1000.1"

CON_COLUMNS = {
    "con_id":               2,   # id (终端 hex ID)
    "con_class":            3,   # cl (类别编号)
    "con_name":             4,   # name (显示名称)
    "con_device_status":    5,   # deviceStatus
    "con_main_power":       6,   # mainPower
    "con_redundant_power":  7,   # redundantPower
    "con_temperature":      8,   # temperature1
    "con_console_ps2":      9,   # consolePS2Connection
    "con_console_usb":      10,  # consoleUSBConnection
    "con_display_conn":     11,  # displayConnection
    "con_display_conn1":    12,  # displayConnection1
    "con_display_conn2":    13,  # displayConnection2
    "con_display_type":     14,  # displayType (string)
    "con_display_type1":    15,  # displayType1
    "con_display_type2":    16,  # displayType2
    "con_freeze":           17,  # freeze (0=false, 1=true)
    "con_freeze1":          18,  # freeze1
    "con_freeze2":          19,  # freeze2
    "con_sfp_tx_power":     20,  # sfpTxPower (uW)
    "con_sfp_tx_power1":    21,  # sfpTxPower1
    "con_sfp_tx_power2":    22,  # sfpTxPower2
    "con_sfp_rx_power":     23,  # sfpRxPower (uW)
    "con_sfp_rx_power1":    24,  # sfpRxPower1
    "con_sfp_rx_power2":    25,  # sfpRxPower2
    "con_sfp_type":         26,  # sfpType (string)
    "con_sfp_type1":        27,  # sfpType1
    "con_sfp_type2":        28,  # sfpType2
    "con_active_tx_port":   29,  # activeTransmissionPort (integer)
    "con_net_if0":          30,  # networkInterface0
}

# -------------------------------------------------------------------
# 端口表 (GUD-CCDC-MIB: portTable)
# {sys_oid}.2.3.1000.1.{column}.{row}
# -------------------------------------------------------------------
PORT_TABLE_ENTRY = "{sys_oid}.2.3.1000.1"

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
    "freeze_status": {0: "false", 1: "true"},
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

    # ─── CON 用户模块（SNMP Table，30个列）─────────────────────────
    {"name": "con_id",              "display_name": "CON终端ID",      "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 2,  "alert_enabled": False, "display_order": 130},
    {"name": "con_class",           "display_name": "CON类别",        "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 3,  "alert_enabled": False, "display_order": 131},
    {"name": "con_name",            "display_name": "CON名称",        "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 4,  "alert_enabled": False, "display_order": 132},
    {"name": "con_device_status",   "display_name": "CON在线状态",    "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 5,  "enum_map": ENUM_MAPS["device_status"],     "alert_enabled": True,  "alert_ne_str": "online", "alert_severity": "warning",  "display_order": 133},
    {"name": "con_main_power",      "display_name": "CON主电源",      "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 6,  "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": False, "display_order": 134},
    {"name": "con_redundant_power", "display_name": "CON冗余电源",    "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 7,  "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": False, "display_order": 135},
    {"name": "con_temperature",     "display_name": "CON温度",        "category": "con_endpoint", "data_type": "float",   "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 8,  "unit": "°C",  "alert_enabled": False, "display_order": 136},
    {"name": "con_console_ps2",     "display_name": "CON控制台PS/2",  "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 9,  "enum_map": ENUM_MAPS["keyboard_mouse"],    "alert_enabled": False, "display_order": 137},
    {"name": "con_console_usb",     "display_name": "CON控制台USB",   "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 10, "enum_map": ENUM_MAPS["keyboard_mouse"],    "alert_enabled": False, "display_order": 138},
    {"name": "con_display_conn",    "display_name": "显示器连接",     "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 11, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": True,  "alert_ne_str": "connected", "alert_severity": "info", "display_order": 139},
    {"name": "con_display_conn1",   "display_name": "显示器1连接",    "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 12, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": False, "display_order": 140},
    {"name": "con_display_conn2",   "display_name": "显示器2连接",    "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 13, "enum_map": ENUM_MAPS["connection"],        "alert_enabled": False, "display_order": 141},
    {"name": "con_display_type",    "display_name": "显示器类型",     "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 14, "alert_enabled": False, "display_order": 142},
    {"name": "con_display_type1",   "display_name": "显示器1类型",    "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 15, "alert_enabled": False, "display_order": 143},
    {"name": "con_display_type2",   "display_name": "显示器2类型",    "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 16, "alert_enabled": False, "display_order": 144},
    {"name": "con_freeze",          "display_name": "冻结状态",       "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 17, "enum_map": ENUM_MAPS["freeze_status"],     "alert_enabled": False, "display_order": 145},
    {"name": "con_freeze1",         "display_name": "冻结通道1",      "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 18, "enum_map": ENUM_MAPS["freeze_status"],     "alert_enabled": False, "display_order": 146},
    {"name": "con_freeze2",         "display_name": "冻结通道2",      "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 19, "enum_map": ENUM_MAPS["freeze_status"],     "alert_enabled": False, "display_order": 147},
    {"name": "con_sfp_tx_power",    "display_name": "CON SFP发送",    "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 20, "unit": "uW",  "alert_enabled": False, "display_order": 148},
    {"name": "con_sfp_tx_power1",   "display_name": "CON SFP发送1",   "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 21, "unit": "uW",  "alert_enabled": False, "display_order": 149},
    {"name": "con_sfp_tx_power2",   "display_name": "CON SFP发送2",   "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 22, "unit": "uW",  "alert_enabled": False, "display_order": 150},
    {"name": "con_sfp_rx_power",    "display_name": "CON SFP接收",    "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 23, "unit": "uW",  "alert_enabled": False, "display_order": 151},
    {"name": "con_sfp_rx_power1",   "display_name": "CON SFP接收1",   "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 24, "unit": "uW",  "alert_enabled": False, "display_order": 152},
    {"name": "con_sfp_rx_power2",   "display_name": "CON SFP接收2",   "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 25, "unit": "uW",  "alert_enabled": False, "display_order": 153},
    {"name": "con_sfp_type",        "display_name": "CON SFP类型",    "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 26, "alert_enabled": False, "display_order": 154},
    {"name": "con_sfp_type1",       "display_name": "CON SFP类型1",   "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 27, "alert_enabled": False, "display_order": 155},
    {"name": "con_sfp_type2",       "display_name": "CON SFP类型2",   "category": "con_endpoint", "data_type": "string",  "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 28, "alert_enabled": False, "display_order": 156},
    {"name": "con_active_tx_port",  "display_name": "活跃传输端口",   "category": "con_endpoint", "data_type": "integer", "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 29, "alert_enabled": False, "display_order": 157},
    {"name": "con_net_if0",         "display_name": "CON网口",        "category": "con_endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": CON_TABLE_ENTRY, "table_column": 30, "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": False, "display_order": 158},

    # ─── 端口表（SNMP Table）────────────────────────────────────────
    {"name": "port_status",        "display_name": "端口状态",     "category": "port", "data_type": "enum",    "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 2,  "enum_map": ENUM_MAPS["port_status"],  "alert_enabled": False, "display_order": 200},
    {"name": "port_sfp_module",    "display_name": "SFP模块",      "category": "port", "data_type": "enum",    "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 3,  "enum_map": ENUM_MAPS["port_status"],  "alert_enabled": False, "display_order": 201},
    {"name": "port_sfp_tx_power",  "display_name": "端口发送功率", "category": "port", "data_type": "integer",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 4,  "unit": "uW",  "alert_enabled": False, "display_order": 202},
    {"name": "port_sfp_rx_power",  "display_name": "端口接收功率", "category": "port", "data_type": "integer",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 5,  "unit": "uW",  "alert_enabled": False, "display_order": 203},
    {"name": "port_sfp_type",      "display_name": "端口SFP类型",  "category": "port", "data_type": "string",  "is_table": True, "table_base_oid": PORT_TABLE_ENTRY, "table_column": 6,  "alert_enabled": False, "display_order": 204},
]
