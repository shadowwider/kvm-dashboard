from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Endpoint(Base):
    """终端设备（归属于某台 KVM 交换机）"""
    __tablename__ = "endpoints"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # '{device_id}_{module_type}_{index}'
    device_id: Mapped[str] = mapped_column(String(64), ForeignKey("devices.id"), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    index: Mapped[int] = mapped_column(Integer, nullable=False)  # SNMP 表行索引
    module_type: Mapped[str] = mapped_column(String(16), default="cpu", server_default="cpu")  # cpu | con | port
    last_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 最新状态摘要 JSON
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
