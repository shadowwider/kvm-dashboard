from datetime import datetime, timezone
from sqlalchemy import String, Boolean, Integer, DateTime, Text, JSON
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
    system_oid: Mapped[str | None] = mapped_column(String(256), nullable=True)  # 例如: 1.3.6.1.4.1.32828.3.257.16
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 例如: ControlCenter-Compact-8C
    profile_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    profile_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_evidence_version: Mapped[str | None] = mapped_column(String(160), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    mac_addresses: Mapped[list | None] = mapped_column(JSON, nullable=True)
    discovery_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_interval: Mapped[int] = mapped_column(Integer, default=60)  # 秒
    last_poll: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 最近一次轻量 sysObjectID 可达性探测；last_poll 只表示完整指标轮询。
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_health_latency_ms: Mapped[float | None] = mapped_column(nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # online/offline/warning
    last_full_poll_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # 存储最近一次轮询的设备指标及端口状态
    profile_scalar_states: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    endpoint_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
