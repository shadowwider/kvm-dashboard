from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.status_metric import StatusMetric
from app.models.trap_event import TrapEvent
from app.services.data_retention import cleanup_expired_operational_data


@pytest.mark.asyncio
async def test_retention_removes_only_expired_operational_records(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retention.db'}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    old = now - timedelta(days=400)

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    StatusMetric.__table__,
                    AuditLog.__table__,
                    Alert.__table__,
                    TrapEvent.__table__,
                ],
            )
        )

    async with factory() as db:
        expired_alert = Alert(
            device_id="old-device",
            alert_type="trap",
            severity="info",
            message="expired",
            is_resolved=True,
            resolved_at=old,
            created_at=old,
        )
        unresolved_alert = Alert(
            device_id="old-device",
            alert_type="offline",
            severity="critical",
            message="must remain",
            is_resolved=False,
            created_at=old,
        )
        current_alert = Alert(
            device_id="current-device",
            alert_type="trap",
            severity="info",
            message="current",
            is_resolved=True,
            resolved_at=now,
            created_at=now,
        )
        db.add_all([expired_alert, unresolved_alert, current_alert])
        await db.flush()
        db.add_all([
            StatusMetric(time=old, device_id="old-device", oid_name="old"),
            StatusMetric(time=now, device_id="current-device", oid_name="new"),
            AuditLog(action="old", result="success", created_at=old),
            AuditLog(action="new", result="success", created_at=now),
            TrapEvent(
                alert_id=expired_alert.id,
                device_id="old-device",
                source_ip="127.0.0.1",
                created_at=old,
            ),
            TrapEvent(
                alert_id=current_alert.id,
                device_id="current-device",
                source_ip="127.0.0.1",
                created_at=now,
            ),
        ])
        await db.commit()

    retention_settings = Settings(
        _env_file=None,
        data_retention_cleanup_enabled=True,
        metrics_retention_days=90,
        trap_event_retention_days=180,
        audit_log_retention_days=365,
    )
    async with factory() as db:
        result = await cleanup_expired_operational_data(
            db,
            settings=retention_settings,
            now=now,
        )
        assert result == {
            "enabled": True,
            "metrics": 1,
            "traps": 1,
            "alerts": 1,
            "audit_logs": 1,
        }
        alerts = (await db.execute(select(Alert).order_by(Alert.id))).scalars().all()
        assert [alert.message for alert in alerts] == ["must remain", "current"]
        assert len((await db.execute(select(StatusMetric))).scalars().all()) == 1
        assert len((await db.execute(select(AuditLog))).scalars().all()) == 1
        assert len((await db.execute(select(TrapEvent))).scalars().all()) == 1

    await engine.dispose()
