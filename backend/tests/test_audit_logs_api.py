import csv
import io
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.audit_logs import router
from app.auth.deps import require_admin
from app.database import get_db
from app.models.audit_log import AuditLog


async def build_test_app():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(AuditLog.__table__.create)

    async with sessions() as session:
        session.add_all([
            AuditLog(
                actor_id=1,
                actor_username="admin",
                actor_role="admin",
                action="discovery.scan",
                target_type="discovery_job",
                target_id="42",
                result="success",
                request_id="req-2",
                ip_address="127.0.0.1",
                user_agent="pytest",
                change_summary={
                    "community": "must-not-leak",
                    "imported_devices": 5,
                },
                created_at=datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
            ),
            AuditLog(
                actor_id=1,
                actor_username="admin",
                actor_role="admin",
                action="device.update",
                target_type="device",
                target_id="CCDM-01",
                result="failure",
                request_id="req-1",
                ip_address="127.0.0.2",
                user_agent="pytest",
                change_summary={"reason": "timeout"},
                created_at=datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc),
            ),
            AuditLog(
                actor_id=2,
                actor_username="operator",
                actor_role="viewer",
                action="alert.resolve",
                target_type="alert",
                target_id="99",
                result="success",
                created_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
            ),
        ])
        await session.commit()

    app = FastAPI()
    app.include_router(router, prefix="/audit-logs")

    async def override_db():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    return app, engine


async def request(app: FastAPI, method: str, url: str):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, url)


@pytest.mark.asyncio
async def test_audit_routes_require_admin():
    app, engine = await build_test_app()

    async def deny_admin():
        raise HTTPException(status_code=403, detail="admin required")

    app.dependency_overrides[require_admin] = deny_admin
    try:
        response = await request(app, "GET", "/audit-logs")
    finally:
        await engine.dispose()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_audit_logs_filters_paginates_and_redacts_defensively():
    app, engine = await build_test_app()

    async def allow_admin():
        return SimpleNamespace(id=1, username="admin", role="admin")

    app.dependency_overrides[require_admin] = allow_admin
    try:
        response = await request(
            app,
            "GET",
            "/audit-logs?actor_id=1&result=success&target_type=discovery_job"
            "&target_id=42&date_from=2026-08-01T08:30:00Z"
            "&date_to=2026-08-01T09:30:00Z&page=1&page_size=1",
        )
    finally:
        await engine.dispose()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["actor"] == {"id": 1, "username": "admin", "role": "admin"}
    assert item["target"] == {"type": "discovery_job", "id": "42"}
    assert item["action"] == "discovery.scan"
    assert item["change_summary"] == {
        "community": "[REDACTED]",
        "imported_devices": 5,
    }


@pytest.mark.asyncio
async def test_list_audit_logs_rejects_inverted_date_range():
    app, engine = await build_test_app()

    async def allow_admin():
        return SimpleNamespace(id=1, username="admin", role="admin")

    app.dependency_overrides[require_admin] = allow_admin
    try:
        response = await request(
            app,
            "GET",
            "/audit-logs?date_from=2026-08-02T00:00:00Z"
            "&date_to=2026-08-01T00:00:00Z",
        )
    finally:
        await engine.dispose()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_export_audit_logs_csv_uses_filters_bom_and_redaction():
    app, engine = await build_test_app()

    async def allow_admin():
        return SimpleNamespace(id=1, username="admin", role="admin")

    app.dependency_overrides[require_admin] = allow_admin
    try:
        response = await request(
            app,
            "GET",
            "/audit-logs/export?action=discovery.scan&target_id=42",
        )
    finally:
        await engine.dispose()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "audit_logs_" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert len(rows) == 1
    assert rows[0]["action"] == "discovery.scan"
    assert rows[0]["target_id"] == "42"
    assert "must-not-leak" not in rows[0]["change_summary"]
    assert "[REDACTED]" in rows[0]["change_summary"]
