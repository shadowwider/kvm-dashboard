from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import devices as devices_api
from app.api import profiles as profiles_api
from app.auth.deps import get_current_user, require_admin
from app.database import Base, get_db
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.device import Device
from app.models.device_entity import DeviceEntity
from app.models.endpoint import Endpoint
from kvm_profiles import PROFILE_CATALOG


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def _field_state(key: str, value, *, status: str = "ok") -> dict:
    return {
        "key": key,
        "label_key": f"fields.{key}",
        "raw": value,
        "value": value,
        "unit": None,
        "status": status,
        "supported": True,
        "present": True,
        "stale": False,
        "updated_at": NOW.isoformat(),
    }


@pytest_asyncio.fixture
async def api_client(tmp_path):
    database_path = tmp_path / "devices-api.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    Device.__table__,
                    Endpoint.__table__,
                    DeviceEntity.__table__,
                    Alert.__table__,
                    AuditLog.__table__,
                ],
            )
        )

    async with factory() as db:
        ccdm = PROFILE_CATALOG["ccdm_matrix"]
        vision_cpu = PROFILE_CATALOG["visionxs_cpu"]
        db.add_all([
            Device(
                id="dev-ccdm",
                name="CCDM Matrix",
                host="127.0.0.1",
                port=11162,
                community="private-ccdm-secret",
                profile_id=ccdm.profile_id,
                profile_version=ccdm.profile_version,
                profile_evidence_version=ccdm.evidence_version,
                system_oid=ccdm.sys_object_id,
                model_name=ccdm.product,
                serial_number="CCDM-0001",
                last_status="online",
                last_health_check=NOW,
                last_poll=NOW,
                last_full_poll_status="success",
                last_metrics={
                    "summary": {"temperature": 31},
                    "community": "nested-secret",
                },
                profile_scalar_states={
                    "serial_number": _field_state(
                        "serial_number",
                        "CCDM-0001",
                    ),
                },
                created_at=NOW,
                updated_at=NOW,
            ),
            Device(
                id="dev-vcpu",
                name="VisionXS CPU",
                host="127.0.0.1",
                port=11163,
                community="private-vcpu-secret",
                system_oid=vision_cpu.sys_object_id,
                model_name=vision_cpu.product,
                serial_number="VCPU-0001",
                last_status="offline",
                last_health_check=NOW,
                created_at=NOW,
                updated_at=NOW,
            ),
        ])
        db.add(
            Endpoint(
                id="dev-ccdm_cpu_1",
                device_id="dev-ccdm",
                name="CPU 1",
                index=1,
                module_type="cpu",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.add_all([
            DeviceEntity(
                device_id="dev-ccdm",
                profile_id="ccdm_matrix",
                table_id="user_module_table",
                entity_type="user_module",
                entity_key="user_module_table:index=1",
                label="CON 1",
                index_key=[{"name": "index", "value": 1}],
                field_states={
                    "status": _field_state(
                        "status",
                        "warning",
                        status="warning",
                    ),
                },
                status="warning",
                is_present=True,
                is_stale=False,
                updated_at=NOW,
            ),
            DeviceEntity(
                device_id="dev-ccdm",
                profile_id="ccdm_matrix",
                table_id="user_module_table",
                entity_type="user_module",
                entity_key="user_module_table:index=2",
                label="CON 2",
                index_key=[{"name": "index", "value": 2}],
                field_states={
                    "status": _field_state(
                        "status",
                        "warning",
                        status="warning",
                    ),
                },
                status="warning",
                is_present=True,
                is_stale=False,
                updated_at=NOW,
            ),
            DeviceEntity(
                device_id="dev-ccdm",
                profile_id="ccdm_matrix",
                table_id="target_module_table",
                entity_type="target_module",
                entity_key="target_module_table:index=3",
                label="CPU 3",
                index_key=[{"name": "index", "value": 3}],
                field_states={
                    "community_state": {
                        **_field_state("community_state", "hidden"),
                        "community": "entity-secret",
                    },
                },
                status="stale",
                is_present=False,
                is_stale=True,
                updated_at=NOW,
            ),
        ])
        db.add_all([
            Alert(
                device_id="dev-ccdm",
                alert_type="threshold",
                severity="warning",
                message="warning",
                is_resolved=False,
                created_at=NOW,
            ),
            Alert(
                device_id="dev-ccdm",
                alert_type="threshold",
                severity="critical",
                message="resolved",
                is_resolved=True,
                created_at=NOW,
            ),
        ])
        await db.commit()

    app = FastAPI()
    app.include_router(devices_api.router, prefix="/api/v1/devices")
    app.include_router(profiles_api.router, prefix="/api/v1/profiles")

    async def override_db():
        async with factory() as db:
            yield db

    async def allow_user():
        return SimpleNamespace(id=1, username="admin", role="admin")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = allow_user
    app.dependency_overrides[require_admin] = allow_user

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        client.test_engine = engine
        client.test_session_factory = factory
        yield client

    await engine.dispose()


def _assert_no_community(response: httpx.Response) -> None:
    text = response.text.casefold()
    assert "community" not in text
    assert "private-" not in text
    assert "nested-secret" not in text
    assert "entity-secret" not in text


@pytest.mark.asyncio
async def test_device_list_supports_safe_legacy_and_paginated_responses(
    api_client,
):
    legacy = await api_client.get("/api/v1/devices")
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)
    assert [item["id"] for item in legacy.json()] == [
        "dev-ccdm",
        "dev-vcpu",
    ]
    _assert_no_community(legacy)

    paged = await api_client.get(
        "/api/v1/devices?page=1&page_size=1"
    )
    assert paged.status_code == 200
    payload = paged.json()
    assert payload["total"] == 2
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert len(payload["items"]) == 1
    device = payload["items"][0]
    assert device["profile"]["id"] == "ccdm_matrix"
    assert device["credential_configured"] is True
    assert device["endpoint_count"] == 1
    assert device["entity_count"] == 2
    assert device["active_alert_count"] == 1
    assert device["last_status"] == "online"
    _assert_no_community(paged)

    second_page = await api_client.get(
        "/api/v1/devices?page=2&page_size=1"
    )
    inferred = second_page.json()["items"][0]
    assert inferred["id"] == "dev-vcpu"
    assert inferred["profile"]["id"] == "visionxs_cpu"
    _assert_no_community(second_page)


@pytest.mark.asyncio
async def test_device_list_uses_constant_number_of_count_queries(api_client):
    statements = []

    def capture_selects(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(
        api_client.test_engine.sync_engine,
        "before_cursor_execute",
        capture_selects,
    )
    try:
        initial = await api_client.get("/api/v1/devices")
        initial_select_count = len(statements)

        async with api_client.test_session_factory() as db:
            db.add_all([
                Device(
                    id=f"scale-{index:03d}",
                    name=f"Scale Device {index}",
                    host=f"192.0.2.{index}",
                    port=161,
                    community="private",
                    created_at=NOW,
                    updated_at=NOW,
                )
                for index in range(1, 33)
            ])
            await db.commit()

        statements.clear()
        scaled = await api_client.get("/api/v1/devices")
        scaled_select_count = len(statements)
    finally:
        event.remove(
            api_client.test_engine.sync_engine,
            "before_cursor_execute",
            capture_selects,
        )

    assert initial.status_code == 200
    assert scaled.status_code == 200
    assert len(initial.json()) == 2
    assert len(scaled.json()) == 34
    assert initial_select_count == 4
    assert scaled_select_count == initial_select_count


@pytest.mark.asyncio
async def test_device_get_details_and_entity_filters_are_safe(api_client):
    response = await api_client.get("/api/v1/devices/dev-ccdm")
    assert response.status_code == 200
    assert response.json()["profile"]["id"] == "ccdm_matrix"
    _assert_no_community(response)

    details = await api_client.get(
        "/api/v1/devices/dev-ccdm/details"
    )
    assert details.status_code == 200
    detail_payload = details.json()
    assert detail_payload["device"]["id"] == "dev-ccdm"
    assert detail_payload["device"]["profile"]["id"] == "ccdm_matrix"
    assert {section["key"] for section in detail_payload["sections"]} == {
        "identity",
        "modules",
    }
    _assert_no_community(details)

    filtered = await api_client.get(
        "/api/v1/devices/dev-ccdm/entities"
        "?table_id=user_module_table"
        "&entity_type=user_module"
        "&status=warning"
        "&present=true"
        "&stale=false"
        "&page=2"
        "&page_size=1"
    )
    assert filtered.status_code == 200
    entity_page = filtered.json()
    assert entity_page["total"] == 2
    assert entity_page["page"] == 2
    assert entity_page["page_size"] == 1
    assert entity_page["items"][0]["label"] == "CON 2"
    _assert_no_community(filtered)

    stale = await api_client.get(
        "/api/v1/devices/dev-ccdm/entities"
        "?present=false&stale=true"
    )
    assert stale.status_code == 200
    assert stale.json()["total"] == 1
    assert stale.json()["items"][0]["status"] == "stale"
    _assert_no_community(stale)


@pytest.mark.asyncio
async def test_create_and_update_accept_community_but_return_safe_summary(
    api_client,
):
    created = await api_client.post(
        "/api/v1/devices",
        json={
            "id": "dev-new",
            "name": "New Device",
            "host": "192.0.2.10",
            "community": "create-secret",
        },
    )
    assert created.status_code == 201
    assert created.json()["credential_configured"] is True
    assert created.json()["name"] == "New Device"
    _assert_no_community(created)
    assert "create-secret" not in created.text

    updated = await api_client.patch(
        "/api/v1/devices/dev-new",
        json={
            "name": "Updated Device",
            "community": "update-secret",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Device"
    assert updated.json()["credential_configured"] is True
    _assert_no_community(updated)
    assert "update-secret" not in updated.text


@pytest.mark.asyncio
async def test_profiles_returns_exactly_five_safe_profile_metadata(api_client):
    response = await api_client.get("/api/v1/profiles")
    assert response.status_code == 200
    items = response.json()["items"]
    assert {item["id"] for item in items} == {
        "ccdc_legacy",
        "ccdm_matrix",
        "dp12_mux_atc",
        "visionxs_con",
        "visionxs_cpu",
    }
    assert len(items) == 5
    assert all(item["version"] == "1.0.0" for item in items)
    assert all(item["label_key"] == f"profiles.{item['id']}" for item in items)
    assert all(item["system_oid"] for item in items)
    _assert_no_community(response)
