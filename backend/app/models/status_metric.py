from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class StatusMetric(Base):
    """
    TimescaleDB 超表（Hypertable）。
    存储所有设备和终端的历史状态数据点。
    每次轮询的每条 OID 读数写入一行。
    TimescaleDB 按 time 列自动分区（每天一个 chunk），7天后压缩。
    """
    __tablename__ = "status_metrics"

    # TimescaleDB 要求时间列在复合主键中
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc))
    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    endpoint_id: Mapped[str | None] = mapped_column(String(128), primary_key=True, nullable=True)
    oid_name: Mapped[str] = mapped_column(String(64), primary_key=True)

    value_str: Mapped[str | None] = mapped_column(String(256), nullable=True)   # 字符串/枚举值
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)        # 数值型（用于图表聚合）

    __table_args__ = (
        # 查询特定设备某字段的历史时间序列
        Index("ix_status_metrics_device_oid_time", "device_id", "oid_name", "time"),
        # 查询特定终端的历史
        Index("ix_status_metrics_endpoint_time", "endpoint_id", "oid_name", "time"),
    )
