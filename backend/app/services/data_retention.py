"""Bounded retention for high-volume operational data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import AsyncSessionLocal
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.status_metric import StatusMetric
from app.models.trap_event import TrapEvent


def _cutoff(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)


async def cleanup_expired_operational_data(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, int | bool]:
    """Delete only records whose configured operational retention has expired."""
    active_settings = settings or get_settings()
    if not active_settings.data_retention_cleanup_enabled:
        return {
            "enabled": False,
            "metrics": 0,
            "traps": 0,
            "alerts": 0,
            "audit_logs": 0,
        }

    reference_time = now or datetime.now(timezone.utc)
    metrics_result = await db.execute(
        delete(StatusMetric).where(
            StatusMetric.time
            < _cutoff(reference_time, active_settings.metrics_retention_days)
        )
    )
    traps_result = await db.execute(
        delete(TrapEvent).where(
            TrapEvent.created_at
            < _cutoff(reference_time, active_settings.trap_event_retention_days)
        )
    )
    audit_result = await db.execute(
        delete(AuditLog).where(
            AuditLog.created_at
            < _cutoff(reference_time, active_settings.audit_log_retention_days)
        )
    )

    # Unresolved alarms are operationally significant and are never removed by
    # this housekeeping task. Resolved alarms use the same audit horizon.
    expired_resolved_alerts = select(Alert.id).where(
        Alert.is_resolved.is_(True),
        Alert.resolved_at.is_not(None),
        Alert.resolved_at
        < _cutoff(reference_time, active_settings.audit_log_retention_days),
    )
    alert_result = await db.execute(
        delete(Alert).where(Alert.id.in_(expired_resolved_alerts))
    )
    await db.commit()

    return {
        "enabled": True,
        "metrics": metrics_result.rowcount or 0,
        "traps": traps_result.rowcount or 0,
        "alerts": alert_result.rowcount or 0,
        "audit_logs": audit_result.rowcount or 0,
    }


async def run_retention_cleanup() -> dict[str, int | bool]:
    async with AsyncSessionLocal() as db:
        return await cleanup_expired_operational_data(db)


def _sqlite_database_size_bytes(settings: Settings) -> int:
    database_path = Path(settings.resolved_sqlite_path)
    candidates = (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
    )
    return sum(path.stat().st_size for path in candidates if path.exists())


async def database_capacity_status(
    db: AsyncSession,
    *,
    settings: Settings | None = None,
) -> dict[str, int | bool | str]:
    """Return a compact DB-size signal suitable for health checks and alerts."""
    active_settings = settings or get_settings()
    if active_settings.is_sqlite:
        size_bytes = _sqlite_database_size_bytes(active_settings)
    else:
        size_bytes = int(
            await db.scalar(text("SELECT pg_database_size(current_database())"))
            or 0
        )

    warning_bytes = active_settings.database_size_warning_mb * 1024 * 1024
    return {
        "mode": active_settings.db_mode,
        "size_bytes": size_bytes,
        "warning_bytes": warning_bytes,
        "warning": size_bytes >= warning_bytes,
    }
