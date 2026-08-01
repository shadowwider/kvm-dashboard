from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DiscoveryConfig(Base):
    __tablename__ = "discovery_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    cidr: Mapped[str] = mapped_column(String(64), default="192.168.1.0/24")
    community: Mapped[str] = mapped_column(String(128), default="public")
    snmp_port: Mapped[int] = mapped_column(Integer, default=161)
    timeout_seconds: Mapped[float] = mapped_column(Float, default=0.5)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    concurrency: Mapped[int] = mapped_column(Integer, default=64)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    scan_on_startup: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    snmp_port: Mapped[int] = mapped_column(Integer, default=161)
    total_hosts: Mapped[int] = mapped_column(Integer, default=0)
    scanned_hosts: Mapped[int] = mapped_column(Integer, default=0)
    responded_hosts: Mapped[int] = mapped_column(Integer, default=0)
    recognized_hosts: Mapped[int] = mapped_column(Integer, default=0)
    imported_devices: Mapped[int] = mapped_column(Integer, default=0)
    updated_devices: Mapped[int] = mapped_column(Integer, default=0)
    unsupported_devices: Mapped[int] = mapped_column(Integer, default=0)
    no_response_hosts: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[list | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
