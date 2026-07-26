import pytest

from app.config import Settings
from app.snmp import poller
from app.snmp.trap_receiver import parse_trap_varbinds


class FakeDevice:
    def __init__(self, device_id="CCDC-01"):
        self.id = device_id
        self.host = "192.0.2.10"
        self.port = 161
        self.community = "public"
        self.last_status = "online"


@pytest.fixture(autouse=True)
def clear_health_state():
    poller._health_failures.clear()
    poller._health_device_locks.clear()


def test_fast_health_defaults_fit_one_second_probe_window():
    settings = Settings(_env_file=None)
    assert settings.snmp_health_poll_enabled is True
    assert settings.snmp_health_poll_interval == 1.0
    assert settings.snmp_health_timeout == 0.25
    assert settings.snmp_health_retries == 1
    assert settings.snmp_health_timeout * (settings.snmp_health_retries + 1) < 1.0


@pytest.mark.asyncio
async def test_health_probe_uses_only_sysobjectid_and_fast_budget(monkeypatch):
    calls = []

    async def fake_get(host, port, community, oid, **kwargs):
        calls.append((host, port, community, oid, kwargs))
        return oid, object()

    session = _HealthSession()
    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(poller, "AsyncSessionLocal", lambda: session)

    reachable, transitioned, _ = await poller.probe_device_health(FakeDevice())

    assert reachable is True
    assert transitioned is False
    assert session.committed is True
    assert len(session.executed) == 1
    assert calls == [(
        "192.0.2.10", 161, "public", poller.SYS_OBJECT_ID_OID,
        {"timeout": 0.25, "retries": 1},
    )]


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
