from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Alert(Base):
    """告警事件记录"""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    endpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    oid_name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 触发告警的 OID 名

    # 告警分类
    alert_type: Mapped[str] = mapped_column(String(16), nullable=False)  # threshold|trap|offline|recovery
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # info|warning|critical

    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 状态追踪
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
