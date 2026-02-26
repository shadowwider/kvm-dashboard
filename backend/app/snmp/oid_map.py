"""
G&D CCDC KVM 系列 OID 定义基础库。
企业号: 1.3.6.1.4.1.32828 (Guntermann & Drunck GmbH)

此文件定义所有已知 OID 的静态映射，作为 oid_registry 表的初始数据种子。
运行时实际使用的监控项从数据库 oid_registry 表动态读取。
"""

# 企业根 OID
GUD_ENTERPRISE = "1.3.6.1.4.1.32828"
GUD_CCDC_BASE = f"{GUD_ENTERPRISE}.3.257.16"

# -------------------------------------------------------------------
# 设备基础信息 (GUD-CCDC-MIB: objects.identify)
# -------------------------------------------------------------------
DEVICE_IDENTIFY_BASE = f"{GUD_CCDC_BASE}.2.1"

DEVICE_OIDS = {
    # 基础信息
    "device_id":      f"{DEVICE_IDENTIFY_BASE}.1.0",
    "device_type":    f"{DEVICE_IDENTIFY_BASE}.2.0",
    "device_serial":  f"{DEVICE_IDENTIFY_BASE}.3.0",
    "device_mac":     f"{DEVICE_IDENTIFY_BASE}.4.0",
    "device_firmware":f"{DEVICE_IDENTIFY_BASE}.5.0",

    # 设备状态 (objects.status = objects.3)
    "main_power":       f"{GUD_CCDC_BASE}.2.3.1.0",
    "redundant_power":  f"{GUD_CCDC_BASE}.2.3.2.0",
    "temperature":      f"{GUD_CCDC_BASE}.2.3.3.0",
    "current":          f"{GUD_CCDC_BASE}.2.3.4.0",
    "voltage":          f"{GUD_CCDC_BASE}.2.3.5.0",
    "fan1":             f"{GUD_CCDC_BASE}.2.3.6.0",
    "fan2":             f"{GUD_CCDC_BASE}.2.3.7.0",
    "fan3":             f"{GUD_CCDC_BASE}.2.3.8.0",
    "fan4":             f"{GUD_CCDC_BASE}.2.3.9.0",
    "fan5":             f"{GUD_CCDC_BASE}.2.3.10.0",
    "fan6":             f"{GUD_CCDC_BASE}.2.3.11.0",
    "net_if0":          f"{GUD_CCDC_BASE}.2.3.12.0",
    "net_if1":          f"{GUD_CCDC_BASE}.2.3.13.0",
    "net_if2":          f"{GUD_CCDC_BASE}.2.3.14.0",
    "net_if3":          f"{GUD_CCDC_BASE}.2.3.15.0",
}

# -------------------------------------------------------------------
# 终端模块表 (GUD-CCDCCPU-MIB: targetModuleTable)
# targetModuleEntry = 1.3.6.1.4.1.32828.3.257.16.1.2.2.3.1000.1
# 列号对应关系（基于 MIB 文件分析）
# -------------------------------------------------------------------
ENDPOINT_TABLE_ENTRY = f"{GUD_ENTERPRISE}.3.257.16.1.2.2.3.1000.1"

# 列号定义
ENDPOINT_COLUMNS = {
    "ep_index":          1,   # 行索引（内部使用）
    "ep_name":           2,   # 终端名称
    "ep_device_status":  3,   # 在线状态: 0=offline, 1=online, 2=ready
    "ep_power_status":   4,   # 电源: 0=off, 1=on
    "ep_keyboard_ps2":   5,   # PS/2 键盘: 0=disconnected, 1=connected
    "ep_mouse_ps2":      6,   # PS/2 鼠标
    "ep_keyboard_usb":   7,   # USB 键盘
    "ep_mouse_usb":      8,   # USB 鼠标
    "ep_video1_status":  9,   # 视频1状态: 0=none, 1=connected
    "ep_video2_status":  10,  # 视频2状态
    "ep_video1_type":    11,  # 视频1类型: 1=VGA,2=DVI-SL,3=DVI-DL,4=DP,5=HDMI
    "ep_video2_type":    12,  # 视频2类型
    "ep_access_status":  13,  # 访问状态: 0=none,1=local,2=remote,3=localExclusive,4=remoteExclusive
    "ep_sfp_type":       14,  # SFP 类型
    "ep_sfp_tx_power":   15,  # SFP 发送功率 (dBm * 100)
    "ep_sfp_rx_power":   16,  # SFP 接收功率 (dBm * 100)
}

def get_endpoint_column_oid(col_name: str, row_index: int) -> str:
    """获取终端表特定行特定列的 OID"""
    col_num = ENDPOINT_COLUMNS[col_name]
    return f"{ENDPOINT_TABLE_ENTRY}.{col_num}.{row_index}"

def get_endpoint_table_base_oid(col_name: str) -> str:
    """获取终端表某列的基础 OID（用于 WALK）"""
    col_num = ENDPOINT_COLUMNS[col_name]
    return f"{ENDPOINT_TABLE_ENTRY}.{col_num}"


# -------------------------------------------------------------------
# 枚举值映射
# -------------------------------------------------------------------
ENUM_MAPS = {
    "power_status": {0: "off", 1: "on"},
    "device_status": {0: "offline", 1: "online", 2: "ready"},
    "connection_status": {0: "disconnected", 1: "connected"},
    "net_if_status": {0: "down", 1: "up"},
    "video_type": {
        0: "none", 1: "vga", 2: "dvisl", 3: "dvidl",
        4: "dmdp", 5: "dp", 6: "hdmi",
    },
    "access_status": {
        0: "none", 1: "local", 2: "remote",
        3: "localExclusive", 4: "remoteExclusive",
    },
}

# -------------------------------------------------------------------
# 初始化 OID 注册表的种子数据
# 格式: {name, oid, display_name, category, data_type, unit, enum_map_key,
#         is_table, table_base_oid, table_column,
#         alert_enabled, alert_gt, alert_lt, alert_eq_str, alert_ne_str, alert_severity,
#         display_order}
# -------------------------------------------------------------------
SEED_OID_REGISTRY = [
    # ── 设备基础信息（只读展示，不告警）──────────────────────────────
    {"name": "device_id",       "oid": DEVICE_OIDS["device_id"],       "display_name": "设备ID",     "category": "device", "data_type": "string", "display_order": 1},
    {"name": "device_type",     "oid": DEVICE_OIDS["device_type"],     "display_name": "设备类型",   "category": "device", "data_type": "string", "display_order": 2},
    {"name": "device_serial",   "oid": DEVICE_OIDS["device_serial"],   "display_name": "序列号",     "category": "device", "data_type": "string", "display_order": 3},
    {"name": "device_mac",      "oid": DEVICE_OIDS["device_mac"],      "display_name": "MAC地址",    "category": "device", "data_type": "string", "display_order": 4},
    {"name": "device_firmware", "oid": DEVICE_OIDS["device_firmware"], "display_name": "固件版本",   "category": "device", "data_type": "string", "display_order": 5},

    # ── 设备状态（告警关键项）────────────────────────────────────────
    {"name": "main_power",      "oid": DEVICE_OIDS["main_power"],      "display_name": "主电源",     "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": True,  "alert_ne_str": "on",    "alert_severity": "critical", "display_order": 10},
    {"name": "redundant_power", "oid": DEVICE_OIDS["redundant_power"], "display_name": "冗余电源",   "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": True,  "alert_ne_str": "on",    "alert_severity": "warning",  "display_order": 11},
    {"name": "temperature",     "oid": DEVICE_OIDS["temperature"],     "display_name": "温度",       "category": "device", "data_type": "float",   "unit": "°C",  "alert_enabled": True,  "alert_gt": 55.0, "alert_severity": "warning",  "display_order": 12},
    {"name": "current",         "oid": DEVICE_OIDS["current"],         "display_name": "电流",       "category": "device", "data_type": "float",   "unit": "A",   "alert_enabled": False, "display_order": 13},
    {"name": "voltage",         "oid": DEVICE_OIDS["voltage"],         "display_name": "电压",       "category": "device", "data_type": "float",   "unit": "V",   "alert_enabled": False, "display_order": 14},
    {"name": "fan1",            "oid": DEVICE_OIDS["fan1"],            "display_name": "风扇1",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 20},
    {"name": "fan2",            "oid": DEVICE_OIDS["fan2"],            "display_name": "风扇2",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 21},
    {"name": "fan3",            "oid": DEVICE_OIDS["fan3"],            "display_name": "风扇3",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 22},
    {"name": "fan4",            "oid": DEVICE_OIDS["fan4"],            "display_name": "风扇4",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 23},
    {"name": "fan5",            "oid": DEVICE_OIDS["fan5"],            "display_name": "风扇5",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 24},
    {"name": "fan6",            "oid": DEVICE_OIDS["fan6"],            "display_name": "风扇6",      "category": "device", "data_type": "integer", "unit": "RPM", "alert_enabled": True,  "alert_lt": 500,  "alert_severity": "warning",  "display_order": 25},
    {"name": "net_if0",         "oid": DEVICE_OIDS["net_if0"],         "display_name": "网口0",      "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": True,  "alert_ne_str": "up",    "alert_severity": "warning",  "display_order": 30},
    {"name": "net_if1",         "oid": DEVICE_OIDS["net_if1"],         "display_name": "网口1",      "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": False, "display_order": 31},
    {"name": "net_if2",         "oid": DEVICE_OIDS["net_if2"],         "display_name": "网口2",      "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": False, "display_order": 32},
    {"name": "net_if3",         "oid": DEVICE_OIDS["net_if3"],         "display_name": "网口3",      "category": "device", "data_type": "enum",    "unit": "",    "enum_map": ENUM_MAPS["net_if_status"],     "alert_enabled": False, "display_order": 33},

    # ── 终端模块（SNMP Table）────────────────────────────────────────
    {"name": "ep_name",          "display_name": "终端名称",   "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_name"],          "alert_enabled": False, "display_order": 100},
    {"name": "ep_device_status", "display_name": "在线状态",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_device_status"], "enum_map": ENUM_MAPS["device_status"],     "alert_enabled": True,  "alert_ne_str": "online", "alert_severity": "warning",  "display_order": 101},
    {"name": "ep_power_status",  "display_name": "终端电源",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_power_status"],  "enum_map": ENUM_MAPS["power_status"],      "alert_enabled": True,  "alert_ne_str": "on",     "alert_severity": "warning",  "display_order": 102},
    {"name": "ep_keyboard_ps2",  "display_name": "PS/2键盘",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_keyboard_ps2"],  "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": False, "display_order": 103},
    {"name": "ep_mouse_ps2",     "display_name": "PS/2鼠标",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_mouse_ps2"],     "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": False, "display_order": 104},
    {"name": "ep_keyboard_usb",  "display_name": "USB键盘",    "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_keyboard_usb"],  "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": False, "display_order": 105},
    {"name": "ep_mouse_usb",     "display_name": "USB鼠标",    "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_mouse_usb"],     "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": False, "display_order": 106},
    {"name": "ep_video1_status", "display_name": "视频1状态",  "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_video1_status"], "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": True,  "alert_ne_str": "connected", "alert_severity": "info", "display_order": 110},
    {"name": "ep_video2_status", "display_name": "视频2状态",  "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_video2_status"], "enum_map": ENUM_MAPS["connection_status"], "alert_enabled": False, "display_order": 111},
    {"name": "ep_video1_type",   "display_name": "视频1类型",  "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_video1_type"],   "enum_map": ENUM_MAPS["video_type"],        "alert_enabled": False, "display_order": 112},
    {"name": "ep_video2_type",   "display_name": "视频2类型",  "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_video2_type"],   "enum_map": ENUM_MAPS["video_type"],        "alert_enabled": False, "display_order": 113},
    {"name": "ep_access_status", "display_name": "访问状态",   "category": "endpoint", "data_type": "enum",    "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_access_status"], "enum_map": ENUM_MAPS["access_status"],     "alert_enabled": False, "display_order": 114},
    {"name": "ep_sfp_type",      "display_name": "SFP类型",    "category": "endpoint", "data_type": "string",  "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_sfp_type"],      "alert_enabled": False, "display_order": 120},
    {"name": "ep_sfp_tx_power",  "display_name": "SFP发送功率","category": "endpoint", "data_type": "float",   "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_sfp_tx_power"],  "unit": "dBm", "alert_enabled": False, "display_order": 121},
    {"name": "ep_sfp_rx_power",  "display_name": "SFP接收功率","category": "endpoint", "data_type": "float",   "is_table": True, "table_base_oid": ENDPOINT_TABLE_ENTRY, "table_column": ENDPOINT_COLUMNS["ep_sfp_rx_power"],  "unit": "dBm", "alert_enabled": False, "display_order": 122},
]
