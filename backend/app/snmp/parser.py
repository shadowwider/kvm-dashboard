"""
SNMP 响应值解析器。
将原始 pysnmp 返回值按 OIDRegistry 中的 data_type 和 enum_map 转换为业务值。
"""
from typing import Any


def parse_snmp_value(raw_value: Any, data_type: str, enum_map: dict | None = None) -> tuple[str | None, float | None]:
    """
    解析 SNMP 原始值，返回 (value_str, value_num) 元组。
    value_str: 字符串/枚举展示值；value_num: 数值型（用于图表）

    pysnmp 返回的 raw_value 可能是:
    - Integer32 / Gauge32 / Counter32 → int
    - DisplayString / OctetString → bytes 或 str
    - TimeTicks → int (hundredths of seconds)
    - Null → None
    """
    if raw_value is None:
        return None, None

    # pysnmp 对象转 Python 原生类型
    try:
        native = raw_value.prettyPrint()
    except AttributeError:
        native = str(raw_value)

    # noSuchObject / noSuchInstance 处理
    if native in ("No Such Object currently exists at this OID",
                  "No Such Instance currently exists at this OID"):
        return None, None

    value_str: str | None = None
    value_num: float | None = None

    if data_type == "string":
        value_str = native.strip()

    elif data_type in ("integer", "float"):
        try:
            num = float(native)
            value_num = num
            value_str = str(int(num)) if data_type == "integer" else f"{num:.2f}"
        except (ValueError, TypeError):
            value_str = native

    elif data_type == "enum":
        try:
            int_val = int(native)
            value_num = float(int_val)
            if enum_map:
                # enum_map 键可能是 int 或 str（来自 JSON）
                value_str = enum_map.get(int_val) or enum_map.get(str(int_val)) or native
            else:
                value_str = native
        except (ValueError, TypeError):
            value_str = native

    else:
        value_str = native

    return value_str, value_num


def is_alert_triggered(
    value_str: str | None,
    value_num: float | None,
    alert_gt: float | None = None,
    alert_lt: float | None = None,
    alert_eq_str: str | None = None,
    alert_ne_str: str | None = None,
) -> bool:
    """判断当前值是否触发告警"""
    if alert_gt is not None and value_num is not None and value_num > alert_gt:
        return True
    if alert_lt is not None and value_num is not None and value_num < alert_lt:
        return True
    if alert_eq_str is not None and value_str is not None and value_str == alert_eq_str:
        return True
    if alert_ne_str is not None and value_str is not None and value_str != alert_ne_str:
        return True
    return False
