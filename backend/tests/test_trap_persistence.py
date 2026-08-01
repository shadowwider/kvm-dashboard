import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.alert import Alert
from app.models.device import Device
from app.models.device_alias import DeviceAlias
from app.models.endpoint import Endpoint
from app.models.simulator_run import SimulatorRun
from app.models.trap_event import TrapEvent
from app.api.alerts import AlertOut
from app.snmp import trap_receiver


STANDARD_TRAP_BINDING = "1.3.6.1.6.3.1.1.4.1.0"
STANDARD_NOTIFICATION = "1.3.6.1.4.1.32828.2.1.0.4"


class TrapValue:
    def __init__(self, value):
        self.value = value

    def prettyPrint(self):
        return str(self.value)


class TrapOidValue(TrapValue):
    def __init__(self, *parts):
        self.parts = parts

    def asTuple(self):
        return self.parts

    def prettyPrint(self):
        return ".".join(str(part) for part in self.parts)


@pytest_asyncio.fixture
async def trap_session_factory(tmp_path):
    database_path = tmp_path / "trap.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    Device.__table__,
                    Endpoint.__table__,
                    DeviceAlias.__table__,
                    SimulatorRun.__table__,
                    Alert.__table__,
                    TrapEvent.__table__,
                ],
            )
        )
    yield factory
    await engine.dispose()


@pytest.mark.parametrize(
    ("level_oid", "message_oid"),
    [
        (
            "1.3.6.1.4.1.32828.2.1.0.2",
            "1.3.6.1.4.1.32828.2.1.0.3",
        ),
        (
            "1.3.6.1.4.1.32828.5.1.0.2",
            "1.3.6.1.4.1.32828.5.1.0.3",
        ),
    ],
)
def test_parse_trap_details_supports_standard_and_compatibility_layouts(
    level_oid,
    message_oid,
):
    notification_parts = tuple(int(part) for part in STANDARD_NOTIFICATION.split("."))
    raw_binds, level, message, notification_oid = trap_receiver.parse_trap_details([
        (STANDARD_TRAP_BINDING, TrapOidValue(*notification_parts)),
        (level_oid, TrapValue(4)),
        (message_oid, TrapValue("Fan 1 stopped")),
    ])

    assert notification_oid == STANDARD_NOTIFICATION
    assert level == 4
    assert message == "Fan 1 stopped"
    assert raw_binds == [
        {"oid": STANDARD_TRAP_BINDING, "value": STANDARD_NOTIFICATION},
        {"oid": level_oid, "value": "4"},
        {"oid": message_oid, "value": "Fan 1 stopped"},
    ]


@pytest.mark.asyncio
async def test_save_trap_persists_alert_and_event_before_broadcast(
    monkeypatch,
    trap_session_factory,
):
    source_ip = "192.0.2.40"
    private_community = "private-community-must-not-leak"
    timestamp = datetime(2026, 8, 1, 4, 5, 6, tzinfo=timezone.utc)
    binds = [
        {"oid": STANDARD_TRAP_BINDING, "value": STANDARD_NOTIFICATION},
        {"oid": "1.3.6.1.4.1.32828.2.1.0.2", "value": "4"},
        {"oid": "1.3.6.1.4.1.32828.2.1.0.3", "value": "Fan 1 stopped"},
    ]
    broadcasts = []

    async with trap_session_factory() as db:
        db.add(Device(
            id="ccdm-01",
            name="Matrix A",
            host=source_ip,
            port=161,
            community=private_community,
        ))
        await db.commit()

    async def capture_broadcast(payload):
        broadcasts.append(payload)

    monkeypatch.setattr(trap_receiver, "AsyncSessionLocal", trap_session_factory)
    monkeypatch.setattr(
        trap_receiver.ws_manager,
        "broadcast",
        capture_broadcast,
    )

    await trap_receiver._save_trap(
        source_ip,
        "[WARNING] Fan 1 stopped",
        "warning",
        binds,
        timestamp,
        trap_level=4,
        trap_oid=STANDARD_NOTIFICATION,
        trap_message="Fan 1 stopped",
    )

    async with trap_session_factory() as db:
        alert = (await db.execute(select(Alert))).scalar_one()
        trap_event = (await db.execute(select(TrapEvent))).scalar_one()

    assert alert.id is not None
    assert alert.device_id == "ccdm-01"
    assert alert.alert_type == "trap"
    assert alert.trap_level == 4
    assert alert.trap_oid == STANDARD_NOTIFICATION
    assert json.loads(alert.raw_value) == binds
    historical_payload = AlertOut.model_validate(alert).model_dump()
    assert historical_payload["entity_key"] is None
    assert historical_payload["trap_level"] == 4
    assert historical_payload["trap_oid"] == STANDARD_NOTIFICATION

    assert trap_event.id is not None
    assert trap_event.alert_id == alert.id
    assert trap_event.device_id == alert.device_id
    assert trap_event.source_ip == source_ip
    assert trap_event.notification_oid == STANDARD_NOTIFICATION
    assert trap_event.raw_level == 4
    assert trap_event.message == "Fan 1 stopped"
    assert trap_event.varbinds == binds

    assert len(broadcasts) == 1
    event = broadcasts[0]
    assert event["type"] == "trap_received"
    assert event["event_id"] == f"trap:{trap_event.id}"
    assert event["alert_id"] == alert.id
    assert event["data"]["alert"]["id"] == alert.id
    assert event["data"]["alert"]["trap_level"] == 4
    assert event["data"]["alert"]["trap_oid"] == STANDARD_NOTIFICATION
    assert event["data"]["trap"]["id"] == trap_event.id
    assert event["data"]["trap"]["alert_id"] == alert.id
    assert event["data"]["trap"]["notification_oid"] == STANDARD_NOTIFICATION
    assert event["message"] == "Matrix A: [WARNING] Fan 1 stopped"
    assert event["original_message"] == "[WARNING] Fan 1 stopped"
    assert event["binds"] == binds

    serialized_event = json.dumps(event, ensure_ascii=False)
    assert private_community not in serialized_event
    assert "community" not in serialized_event.lower()
