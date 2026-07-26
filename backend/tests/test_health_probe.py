import pytest

from app.config import Settings
from app.snmp import poller


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

    monkeypatch.setattr(poller, "_snmp_get", fake_get)
    monkeypatch.setattr(poller, "AsyncSessionLocal", _FailIfUsedSession)

    reachable, transitioned, _ = await poller.probe_device_health(FakeDevice())

    assert reachable is True
    assert transitioned is False
    assert calls == [(
        "192.0.2.10", 161, "public", poller.SYS_OBJECT_ID_OID,
        {"timeout": 0.25, "retries": 1},
    )]


class _FailIfUsedSession:
    def __init__(self, *args, **kwargs):
        raise AssertionError("steady healthy probe must not write the database")
