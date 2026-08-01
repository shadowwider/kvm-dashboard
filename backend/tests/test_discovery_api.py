from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import discovery as discovery_api
from app.database import Base, get_db
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.discovery import DiscoveryConfig, DiscoveryJob
from app.services.discovery import DiscoveryProbeResult, DiscoveryService
from kvm_profiles import PROFILE_CATALOG


@pytest_asyncio.fixture
async def discovery_api_client(tmp_path, monkeypatch):
    database_path = tmp_path / "discovery-api.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    Device.__table__,
                    DiscoveryConfig.__table__,
                    DiscoveryJob.__table__,
                    AuditLog.__table__,
                ],
            )
        )

    initial_poll_calls = []

    async def fake_probe(host, port, community, **kwargs):
        if host.endswith(".1"):
            return DiscoveryProbeResult(
                sys_object_id=(
                    PROFILE_CATALOG["visionxs_con"].sys_object_id
                ),
                identity={
                    "device_type": "VisionXS-CON",
                    "serial_number": "VISION-CON-API-01",
                    "ether_address0": "00-11-22-33-44-77",
                },
            )
        return None

    async def fake_initial_poll(device_id):
        initial_poll_calls.append(device_id)

    service = DiscoveryService(
        factory,
        fake_probe,
        fake_initial_poll,
    )
    monkeypatch.setattr(discovery_api, "discovery_service", service)

    app = FastAPI()
    app.include_router(
        discovery_api.router,
        prefix="/api/v1/discovery",
    )

    async def override_db():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[discovery_api.require_admin] = lambda: (
        SimpleNamespace(id=9, username="admin", role="admin")
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        client.discovery_sessions = factory
        client.initial_poll_calls = initial_poll_calls
        yield client

    await engine.dispose()


@pytest.mark.asyncio
async def test_discovery_api_contract_and_community_redaction(
    discovery_api_client,
):
    client = discovery_api_client
    secret = "private-api-value"
    update_response = await client.put(
        "/api/v1/discovery/config",
        json={
            "cidr": "192.0.2.0/30",
            "community": secret,
            "snmp_port": 161,
            "timeout_seconds": 0.2,
            "retries": 0,
            "concurrency": 2,
            "enabled": True,
            "scan_on_startup": False,
        },
    )

    assert update_response.status_code == 200
    assert update_response.json()["credential_configured"] is True
    assert "community" not in update_response.text
    assert secret not in update_response.text

    get_config_response = await client.get("/api/v1/discovery/config")
    assert get_config_response.status_code == 200
    assert "community" not in get_config_response.text
    assert secret not in get_config_response.text

    scan_response = await client.post("/api/v1/discovery/scan")
    assert scan_response.status_code == 202
    assert scan_response.json()["status"] == "queued"
    job_id = scan_response.json()["job_id"]

    list_response = await client.get("/api/v1/discovery/jobs")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["status"] == "completed"
    assert "community" not in list_response.text
    assert secret not in list_response.text

    detail_response = await client.get(
        f"/api/v1/discovery/jobs/{job_id}"
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["recognized_hosts"] == 1
    assert detail["imported_devices"] == 1
    assert detail["no_response_hosts"] == 1
    recognized = next(
        item for item in detail["results"]
        if item["status"] == "recognized"
    )
    assert recognized["profile_id"] == "visionxs_con"
    assert recognized["identity"] == {
        "device_type": "VisionXS-CON",
        "serial_number": "VISION-CON-API-01",
        "mac_addresses": ["00:11:22:33:44:77"],
    }
    assert recognized["identity_key"] == "serial:vision-con-api-01"
    assert recognized["initial_poll"] == "completed"
    assert client.initial_poll_calls == [recognized["device_id"]]
    assert "community" not in detail_response.text
    assert secret not in detail_response.text

    async with client.discovery_sessions() as db:
        audit_actions = list(
            await db.scalars(
                select(AuditLog.action).order_by(AuditLog.id)
            )
        )
    assert "discovery.host.recognized" in audit_actions
    assert "discovery.host.skipped" in audit_actions
    assert "discovery.device.imported" in audit_actions
    assert "discovery.device.initial_poll_completed" in audit_actions


@pytest.mark.asyncio
async def test_discovery_api_returns_structured_validation_and_not_found_errors(
    discovery_api_client,
):
    invalid_response = await discovery_api_client.put(
        "/api/v1/discovery/config",
        json={
            "cidr": "192.0.2.0/23",
            "community": "private-value",
            "snmp_port": 161,
            "timeout_seconds": 0.5,
            "retries": 0,
            "concurrency": 64,
            "enabled": True,
            "scan_on_startup": False,
        },
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["detail"]["code"] == "validation_error"
    assert invalid_response.json()["detail"]["fields"] == {
        "cidr": "Maximum 256 usable hosts"
    }

    missing_response = await discovery_api_client.get(
        "/api/v1/discovery/jobs/999"
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"]["code"] == "not_found"
