from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class StatusMetric(Base):
    """
    时序数据表。
    PostgreSQL 部署时将转换为 TimescaleDB 超表。
    SQLite 测试时作为普通表使用（无自动分区/压缩）。
    """
    __tablename__ = "status_metrics"

    # 使用 auto-increment id 作为主键（兼容 SQLite）
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    oid_name: Mapped[str] = mapped_column(String(64), nullable=False)

    value_str: Mapped[str | None] = mapped_column(String(256), nullable=True)
    value_num: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_status_metrics_device_oid_time", "device_id", "oid_name", "time"),
        Index("ix_status_metrics_endpoint_time", "endpoint_id", "oid_name", "time"),
    )
