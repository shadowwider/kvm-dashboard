from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Device(Base):
    """KVM 交换机设备"""
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    host: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=161)
    community: Mapped[str] = mapped_column(String(64), default="public")
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_interval: Mapped[int] = mapped_column(Integer, default=60)  # 秒
    last_poll: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # online/offline/warning
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
