import json
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import (
    alerts as alerts_api,
    aliases as aliases_api,
    auth as auth_api,
    devices as devices_api,
    discovery as discovery_api,
    oid_registry as oid_registry_api,
)
from app.auth.deps import get_current_user, require_admin
from app.auth.jwt import hash_password
from app.database import Base, get_db
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.device_alias import DeviceAlias
from app.models.device_entity import DeviceEntity
from app.models.discovery import DiscoveryConfig, DiscoveryJob
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.user import User
from app.services.discovery import DiscoveryService


@pytest_asyncio.fixture
async def audit_app(tmp_path, monkeypatch):
    database_path = tmp_path / "admin-operation-audit.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    User.__table__,
                    Device.__table__,
                    Endpoint.__table__,
                    DeviceEntity.__table__,
                    OIDRegistry.__table__,
                    Alert.__table__,
                    DeviceAlias.__table__,
                    DiscoveryConfig.__table__,
                    DiscoveryJob.__table__,
                    AuditLog.__table__,
                ],
            )
        )

    async with sessions() as db:
        admin = User(
            username="admin",
            password_hash=hash_password("Admin123!"),
            role="admin",
            is_active=True,
        )
        db.add(admin)
        db.add_all([
            Alert(
                device_id="audit-device",
                alert_type="threshold",
                severity="warning",
                message="first alert",
            ),
            Alert(
                device_id="audit-device",
                alert_type="threshold",
                severity="critical",
                message="second alert",
            ),
        ])
        await db.commit()
        await db.refresh(admin)
        alert_ids = list(
            await db.scalars(select(Alert.id).order_by(Alert.id))
        )
        admin_identity = SimpleNamespace(
            id=admin.id,
            username=admin.username,
            role=admin.role,
        )

    async def fake_probe(*args, **kwargs):
        return None

    monkeypatch.setattr(
        discovery_api,
        "discovery_service",
        DiscoveryService(sessions, fake_probe),
    )

    async def fake_poll_device(*args, **kwargs):
        return None

    poller_module = ModuleType("app.snmp.poller")
    poller_module.poll_device = fake_poll_device
    monkeypatch.setitem(sys.modules, "app.snmp.poller", poller_module)

    app = FastAPI()
    app.include_router(auth_api.router, prefix="/api/v1/auth")
    app.include_router(devices_api.router, prefix="/api/v1/devices")
    app.include_router(discovery_api.router, prefix="/api/v1/discovery")
    app.include_router(oid_registry_api.router, prefix="/api/v1/oids")
    app.include_router(alerts_api.router, prefix="/api/v1/alerts")
    app.include_router(aliases_api.router, prefix="/api/v1/aliases")

    async def override_db():
        async with sessions() as db:
            try:
                yield db
            except Exception:
                await db.rollback()
                raise

    async def allow_admin():
        return admin_identity

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = allow_admin
    app.dependency_overrides[require_admin] = allow_admin

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "x-request-id": "audit-integration-request",
            "user-agent": "audit-integration-test",
        },
    ) as client:
        yield client, sessions, alert_ids

    await engine.dispose()


@pytest.mark.asyncio
async def test_important_admin_operations_are_audited_without_secrets(
    audit_app,
):
    client, sessions, alert_ids = audit_app
    secret_values = [
        "Admin123!",
        "WrongAdminSecret!",
        "User123!",
        "Rotated123!",
        "create-community-secret",
        "update-community-secret",
        "discovery-community-secret",
        "Alias Display Name",
        "token=alias-note-secret",
    ]

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "Admin123!"},
    )
    assert login.status_code == 200

    failed_login = await client.post(
        "/api/v1/auth/login",
        data={"username": "unknown-user", "password": "WrongAdminSecret!"},
    )
    assert failed_login.status_code == 401

    created_user = await client.post(
        "/api/v1/auth/users",
        json={
            "username": "audit-user",
            "password": "User123!",
            "role": "viewer",
        },
    )
    assert created_user.status_code == 201
    user_id = created_user.json()["id"]
    assert (
        await client.patch(f"/api/v1/auth/users/{user_id}/toggle")
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/auth/users/{user_id}/reset-password",
            json={"new_password": "Rotated123!"},
        )
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/auth/users/{user_id}/role",
            json={"role": "admin"},
        )
    ).status_code == 200

    created_device = await client.post(
        "/api/v1/devices",
        json={
            "id": "audit-device",
            "name": "Audit Device",
            "host": "192.0.2.10",
            "community": "create-community-secret",
        },
    )
    assert created_device.status_code == 201
    assert (
        await client.patch(
            "/api/v1/devices/audit-device",
            json={
                "name": "Updated Audit Device",
                "community": "update-community-secret",
            },
        )
    ).status_code == 200
    assert (
        await client.post("/api/v1/devices/audit-device/poll")
    ).status_code == 202

    discovery_config = await client.put(
        "/api/v1/discovery/config",
        json={
            "cidr": "192.0.2.10/32",
            "community": "discovery-community-secret",
            "snmp_port": 161,
            "timeout_seconds": 0.1,
            "retries": 0,
            "concurrency": 1,
            "enabled": True,
            "scan_on_startup": False,
        },
    )
    assert discovery_config.status_code == 200
    assert (
        await client.post("/api/v1/discovery/scan")
    ).status_code == 202

    created_oid = await client.post(
        "/api/v1/oids",
        json={
            "oid": "1.3.6.1.4.1.32828.999.1",
            "name": "audit_metric",
            "display_name": "Audit Metric",
        },
    )
    assert created_oid.status_code == 201
    oid_id = created_oid.json()["id"]
    assert (
        await client.patch(
            f"/api/v1/oids/{oid_id}",
            json={"display_name": "Updated Audit Metric"},
        )
    ).status_code == 200

    assert (
        await client.patch(
            f"/api/v1/alerts/{alert_ids[0]}/resolve"
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/v1/alerts/resolve-all",
            params={"device_id": "audit-device"},
        )
    ).status_code == 200

    assert (
        await client.put(
            "/api/v1/aliases/audit-device",
            json={
                "alias": "Alias Display Name",
                "target_type": "device",
                "note": "token=alias-note-secret",
            },
        )
    ).status_code == 200
    assert (
        await client.delete("/api/v1/aliases/audit-device")
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/oids/{oid_id}")
    ).status_code == 204
    assert (
        await client.delete("/api/v1/devices/audit-device")
    ).status_code == 204

    async with sessions() as db:
        entries = list(
            await db.scalars(select(AuditLog).order_by(AuditLog.id))
        )

    assert len(entries) == 21
    assert {entry.action for entry in entries} == {
        "auth.login",
        "user.create",
        "user.toggle",
        "user.reset_password",
        "user.role_update",
        "device.create",
        "device.update",
        "device.poll",
        "device.delete",
        "discovery.config_update",
        "discovery.scan",
        "discovery.job.queued",
        "discovery.host.skipped",
        "oid.create",
        "oid.update",
        "oid.delete",
        "alert.resolve",
        "alert.resolve_all",
        "alias.set",
        "alias.delete",
    }
    login_results = [
        entry.result for entry in entries if entry.action == "auth.login"
    ]
    assert login_results == ["success", "failure"]
    failed_entry = next(
        entry
        for entry in entries
        if entry.action == "auth.login" and entry.result == "failure"
    )
    assert failed_entry.actor_id is None
    assert failed_entry.actor_username == "unknown-user"
    background_actions = {
        "discovery.job.queued",
        "discovery.host.skipped",
    }
    assert all(
        entry.request_id == "audit-integration-request"
        and entry.user_agent == "audit-integration-test"
        for entry in entries
        if entry.action not in background_actions
    )
    assert all(
        entry.request_id is None and entry.user_agent is None
        for entry in entries
        if entry.action in background_actions
    )

    summaries = json.dumps(
        [entry.change_summary for entry in entries],
        ensure_ascii=False,
    )
    for secret in secret_values:
        assert secret not in summaries
    assert "community" not in summaries.casefold()
    assert "token" not in summaries.casefold()

    device_update = next(
        entry for entry in entries if entry.action == "device.update"
    )
    assert device_update.change_summary == {
        "changed_fields": ["name", "snmp_access"],
        "snmp_access_changed": True,
    }
    password_reset = next(
        entry for entry in entries if entry.action == "user.reset_password"
    )
    assert password_reset.change_summary == {
        "username": "audit-user",
        "authentication_updated": True,
    }
