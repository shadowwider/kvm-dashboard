import asyncio

import pytest
from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.snmp import poller
from app.snmp.trap_receiver import parse_trap_varbinds


class FakeDevice:
    def __init__(
        self,
        device_id="CCDC-01",
        model_name=None,
        profile_id="ccdc_legacy",
        system_oid=poller.CCDC_LEGACY_SYS_OBJECT_ID,
    ):
        self.id = device_id
        self.host = "192.0.2.10"
        self.port = 161
        self.community = "public"
        self.last_status = "online"
        self.model_name = model_name
        self.is_active = True
        self.poll_interval = 60
        self.last_poll = None
        self.profile_id = profile_id
        self.system_oid = system_oid


@pytest.fixture(autouse=True)
def clear_health_state():
    poller._health_failures.clear()
    poller._health_device_locks.clear()
    poller._pending_health_heartbeats.clear()
    poller._latest_health_successes.clear()
    poller._full_poll_retry_after.clear()
    poller._engine_pool.clear()
    poller._health_engine_pool.clear()
    poller._engine_creation_lock = asyncio.Lock()
    poller._health_engine_creation_lock = asyncio.Lock()


def test_fast_health_defaults_fit_one_second_probe_window():
    settings = Settings(_env_file=None)
    assert settings.snmp_health_poll_enabled is True
    assert settings.snmp_health_poll_interval == 1.0
    assert settings.snmp_health_timeout == 0.25
    assert settings.snmp_health_retries == 1
    assert settings.snmp_health_failure_threshold == 2
    assert settings.snmp_health_timeout * (settings.snmp_health_retries + 1) < 1.0


def test_full_poll_accepts_all_active_profiles():
    assert poller.is_full_poll_eligible(FakeDevice()) is True
    assert poller.is_full_poll_eligible(
        FakeDevice(model_name="SIMULATION / ccdc_legacy_unverified")
    ) is True
    assert poller.is_full_poll_eligible(
        FakeDevice(model_name="SIMULATION / ccdm_matrix")
    ) is True
    assert poller.is_full_poll_eligible(
        FakeDevice(model_name="SIMULATION / visionxs_cpu")
    ) is True


def test_full_poll_honors_each_device_interval():
    now = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    device = FakeDevice()
    assert poller.is_full_poll_due(device, now) is True

    device.last_poll = now - timedelta(seconds=59)
    assert poller.is_full_poll_due(device, now) is False

    device.last_poll = now - timedelta(seconds=60)
    assert poller.is_full_poll_due(device, now) is True


def test_failed_first_full_poll_is_backed_off_until_retry_window():
    now = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    device = FakeDevice()
    device.poll_interval = 1

    poller._defer_full_poll_retry(device, now)

    assert poller.is_full_poll_due(
        device,
        now + timedelta(seconds=4),
    ) is False
    assert poller.is_full_poll_due(
        device,
        now + timedelta(seconds=5),
    ) is True


def test_numeric_oid_identity_input_stays_on_direct_resolution_path():
    assert poller._numeric_oid_tuple(".1.3.6.1.2.1.1.2.0") == (
        1, 3, 6, 1, 2, 1, 1, 2, 0,
    )


@pytest.mark.asyncio
async def test_cold_engine_construction_is_serialized(monkeypatch):
    active_constructors = 0
    max_active_constructors = 0

    class FakeEngine:
        pass

    async def fake_to_thread(factory):
        nonlocal active_constructors, max_active_constructors
        assert factory is poller.SnmpEngine
        active_constructors += 1
        max_active_constructors = max(
            max_active_constructors,
            active_constructors,
        )
        await asyncio.sleep(0.01)
        active_constructors -= 1
        return FakeEngine()

    monkeypatch.setattr(poller.asyncio, "to_thread", fake_to_thread)

    engines = await asyncio.gather(
        *(poller._get_engine(health=True) for _ in range(4))
    )

    assert len(engines) == 4
    assert max_active_constructors == 1


@pytest.mark.asyncio
async def test_health_probe_uses_only_sysobjectid_and_fast_budget(monkeypatch):
    calls = []

    async def fake_get(host, port, community, oid, **kwargs):
        calls.append((host, port, community, oid, kwargs))
        return oid, object()

    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(
        poller,
        "AsyncSessionLocal",
        lambda: pytest.fail("stable online probes must not open a DB session"),
    )

    reachable, transitioned, _ = await poller.probe_device_health(FakeDevice())

    assert reachable is True
    assert transitioned is False
    assert "CCDC-01" in poller._pending_health_heartbeats
    assert calls == [(
        "192.0.2.10", 161, "public", poller.SYS_OBJECT_ID_OID,
        {"timeout": 0.25, "retries": 1, "health": True},
    )]


@pytest.mark.asyncio
async def test_snmp_timeout_discards_engine(monkeypatch):
    engine = object()
    returned = []

    async def fake_get_engine(*, health=False):
        assert health is True
        return engine

    async def fake_get_cmd(*args, **kwargs):
        return "No SNMP response received before timeout", 0, 0, []

    async def fake_return_engine(candidate, discard=False, *, health=False):
        returned.append((candidate, discard, health))

    monkeypatch.setattr(poller, "_get_engine", fake_get_engine)
    monkeypatch.setattr(poller, "getCmd", fake_get_cmd)
    monkeypatch.setattr(poller, "_return_engine", fake_return_engine)

    oid, value = await poller._snmp_get(
        "192.0.2.10",
        161,
        "public",
        poller.SYS_OBJECT_ID_OID,
        timeout=0.01,
        retries=0,
        health=True,
    )

    assert oid == poller.SYS_OBJECT_ID_OID
    assert value is None
    assert returned == [(engine, True, True)]


@pytest.mark.asyncio
async def test_health_requires_consecutive_failures_before_offline(monkeypatch):
    device = FakeDevice()
    persisted = []

    async def fake_get(*args, **kwargs):
        return poller.SYS_OBJECT_ID_OID, None

    async def fake_persist(
        candidate,
        *,
        reachable,
        threshold_reached,
        elapsed_ms,
        now,
        not_newer_than=None,
    ):
        persisted.append((reachable, threshold_reached))
        return threshold_reached, {"id": 1} if threshold_reached else None

    async def fake_broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(poller, "_persist_health_transition", fake_persist)
    monkeypatch.setattr(poller, "_broadcast_health_transition", fake_broadcast)
    monkeypatch.setattr(
        poller,
        "_get_settings",
        lambda: Settings(
            _env_file=None,
            snmp_health_failure_threshold=2,
        ),
    )

    first = await poller.probe_device_health(device)
    second = await poller.probe_device_health(device)

    assert first[:2] == (False, False)
    assert second[:2] == (False, True)
    assert persisted == [(False, True)]


@pytest.mark.asyncio
async def test_health_failure_clears_buffered_success_and_defers_full_poll(
    monkeypatch,
):
    device = FakeDevice()
    now = datetime.now(timezone.utc)
    await poller._queue_health_heartbeat(device.id, now, 5.0)

    async def fake_get(*args, **kwargs):
        return poller.SYS_OBJECT_ID_OID, None

    async def fake_persist(*args, **kwargs):
        return True, {"id": 1}

    async def fake_broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(poller, "_persist_health_transition", fake_persist)
    monkeypatch.setattr(poller, "_broadcast_health_transition", fake_broadcast)
    monkeypatch.setattr(
        poller,
        "_get_settings",
        lambda: Settings(
            _env_file=None,
            snmp_health_failure_threshold=1,
        ),
    )

    await poller.probe_device_health(device)

    assert device.id not in poller._latest_health_successes
    assert device.id not in poller._pending_health_heartbeats
    assert poller.is_full_poll_due(device, now + timedelta(seconds=1)) is False


@pytest.mark.asyncio
async def test_blocked_heartbeat_flush_does_not_hold_health_cycle(monkeypatch):
    device = FakeDevice()
    health_session = _DeviceListSession([device])
    flush_started = asyncio.Event()
    release_flush = asyncio.Event()

    async def fake_get(*args, **kwargs):
        return poller.SYS_OBJECT_ID_OID, object()

    class _BlockedHeartbeatSession(_HealthSession):
        async def execute(self, statement):
            flush_started.set()
            await release_flush.wait()

    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: health_session)
    await poller.probe_device_health(device)

    monkeypatch.setattr(
        poller,
        "AsyncSessionLocal",
        lambda: _BlockedHeartbeatSession(),
    )
    flush_task = asyncio.create_task(poller.flush_health_heartbeats())
    await asyncio.wait_for(flush_started.wait(), timeout=0.2)

    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: health_session)
    await asyncio.wait_for(poller.run_health_probe_cycle(), timeout=0.2)

    release_flush.set()
    await asyncio.wait_for(flush_task, timeout=0.2)


@pytest.mark.asyncio
async def test_stale_full_poll_timeout_observes_buffered_success(monkeypatch):
    device = FakeDevice()
    started_at = datetime.now(timezone.utc)
    await poller._queue_health_heartbeat(
        device.id,
        started_at + timedelta(milliseconds=10),
        5.0,
    )
    monkeypatch.setattr(
        poller,
        "AsyncSessionLocal",
        lambda: pytest.fail("stale timeout must be rejected before DB access"),
    )

    transitioned, alert = await poller._persist_health_transition(
        device,
        reachable=False,
        threshold_reached=True,
        elapsed_ms=500.0,
        now=started_at + timedelta(seconds=1),
        not_newer_than=started_at,
    )

    assert transitioned is False
    assert alert is None


@pytest.mark.asyncio
async def test_health_cycle_does_not_wait_for_endpoint_status_walks(monkeypatch):
    device = FakeDevice()
    session = _DeviceListSession([device])
    endpoint_probe_called = False

    async def fake_health_probe(candidate):
        assert candidate is device
        return True, False, 5.0

    async def blocked_endpoint_probe(candidate):
        nonlocal endpoint_probe_called
        endpoint_probe_called = True
        await asyncio.Event().wait()

    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(poller, "probe_device_health", fake_health_probe)
    monkeypatch.setattr(poller, "_probe_endpoint_statuses", blocked_endpoint_probe)

    await asyncio.wait_for(poller.run_health_probe_cycle(), timeout=0.2)

    assert endpoint_probe_called is False


@pytest.mark.asyncio
async def test_endpoint_status_cycle_only_probes_legacy_ccdc(monkeypatch):
    legacy = FakeDevice(device_id="legacy")
    vision = FakeDevice(
        device_id="vision",
        profile_id="visionxs_cpu",
        system_oid="1.3.6.1.4.1.32828.3.768.768",
    )
    session = _DeviceListSession([legacy])
    calls = []

    async def fake_endpoint_probe(device):
        calls.append(device.id)

    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(poller, "_probe_endpoint_statuses", fake_endpoint_probe)

    await poller.run_endpoint_status_probe_cycle()

    assert calls == ["legacy"]
    assert poller._supports_legacy_endpoint_probe(legacy) is True
    assert poller._supports_legacy_endpoint_probe(vision) is False


class _ScalarResult:
    def __init__(self, devices):
        self.devices = devices

    def scalars(self):
        return self

    def all(self):
        return self.devices


class _DeviceListSession:
    def __init__(self, devices):
        self.devices = devices

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, statement):
        return _ScalarResult(self.devices)


class _HealthSession:
    def __init__(self):
        self.committed = False
        self.executed = []
        self.device = FakeDevice()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, model, device_id):
        return self.device

    async def execute(self, statement):
        self.executed.append(statement)

    async def commit(self):
        self.committed = True


class _TrapValue:
    def __init__(self, value):
        self.value = value

    def prettyPrint(self):
        return str(self.value)


def test_observed_trap_layout_parses_level_and_message():
    raw_binds, level, message = parse_trap_varbinds([
        ("1.3.6.1.4.1.32828.5.1.0.2", _TrapValue(3)),
        ("1.3.6.1.4.1.32828.5.1.0.3", _TrapValue("CPU module CPU-2-001 went offline")),
    ])

    assert level == 3
    assert message == "CPU module CPU-2-001 went offline"
    assert raw_binds[0]["oid"] == "1.3.6.1.4.1.32828.5.1.0.2"


def test_legacy_trap_layout_remains_supported():
    _, level, message = parse_trap_varbinds([
        ("1.3.6.1.4.1.32828.2.1.0.2", _TrapValue(5)),
        ("1.3.6.1.4.1.32828.2.1.0.3", _TrapValue("CON module CON-1-003 came online")),
    ])

    assert level == 5
    assert message == "CON module CON-1-003 came online"
