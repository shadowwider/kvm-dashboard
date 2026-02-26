from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class OIDRegistry(Base):
    """
    可配置的 OID 监控注册表。
    所有需要监控的 SNMP 字段都在此表中定义，
    Poller 动态读取此表构建 SNMP 查询，无需修改代码即可增删监控项。
    """
    __tablename__ = "oid_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # OID 标识
    oid: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)  # 完整数字 OID
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # 代码键名 'main_power'
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)       # 显示名 '主电源'
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 分类
    category: Mapped[str] = mapped_column(String(16), nullable=False)  # 'device' | 'endpoint'

    # 数据类型
    data_type: Mapped[str] = mapped_column(String(16), default="string")  # integer|float|string|enum
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)   # '°C','RPM','V','A'
    enum_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)   # {0:"off",1:"on"}

    # SNMP 表支持（终端模块是 SNMP Table）
    is_table: Mapped[bool] = mapped_column(Boolean, default=False)
    table_base_oid: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 表基础 OID
    table_column: Mapped[int | None] = mapped_column(Integer, nullable=True)         # 列号

    # 告警配置
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_gt: Mapped[float | None] = mapped_column(Float, nullable=True)       # 大于此值告警
    alert_lt: Mapped[float | None] = mapped_column(Float, nullable=True)       # 小于此值告警
    alert_eq_str: Mapped[str | None] = mapped_column(String(64), nullable=True) # 等于此枚举值告警
    alert_ne_str: Mapped[str | None] = mapped_column(String(64), nullable=True) # 不等于此枚举值告警（用于"非正常"）
    alert_severity: Mapped[str] = mapped_column(String(16), default="warning")  # info|warning|critical

    # 显示配置
    poll_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    display_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
