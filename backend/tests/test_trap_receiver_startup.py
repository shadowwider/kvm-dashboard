import asyncio
import socket
import threading
from types import SimpleNamespace

import pytest

from app.snmp import trap_receiver


@pytest.fixture
def listen_settings(monkeypatch):
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    settings = SimpleNamespace(
        snmp_trap_listen_port=port,
        snmp_default_community="private-value",
    )
    monkeypatch.setattr(trap_receiver, "settings", settings)
    return settings


@pytest.mark.asyncio
async def test_trap_receiver_startup_propagates_background_bind_failure(
    monkeypatch,
    listen_settings,
):
    def fail_startup(_main_loop, ready_event: threading.Event):
        trap_receiver._set_receiver_status(
            "failed",
            detail="address already in use",
            error_type="OSError",
        )
        ready_event.set()

    monkeypatch.setattr(trap_receiver, "_start_trap_receiver", fail_startup)

    with pytest.raises(RuntimeError, match="address already in use"):
        await trap_receiver.start_trap_receiver(startup_timeout=0.5)


@pytest.mark.asyncio
async def test_trap_receiver_startup_waits_for_running_state(
    monkeypatch,
    listen_settings,
):
    def successful_startup(_main_loop, ready_event: threading.Event):
        trap_receiver._set_receiver_status("running")
        ready_event.set()

    monkeypatch.setattr(trap_receiver, "_start_trap_receiver", successful_startup)

    status = await trap_receiver.start_trap_receiver(startup_timeout=0.5)

    assert status["state"] == "running"
    assert status["listen_port"] == listen_settings.snmp_trap_listen_port


def test_background_receiver_binds_explicit_listen_port(
    monkeypatch,
    listen_settings,
):
    captured = {}

    class FakeTransport:
        def openServerMode(self, address):
            captured["address"] = address
            return self

    class FakeDispatcher:
        def jobStarted(self, count):
            captured["jobs"] = count

        def runDispatcher(self):
            captured["ran"] = True

        def closeDispatcher(self):
            captured["closed"] = True

    class FakeEngine:
        def __init__(self):
            self.transportDispatcher = FakeDispatcher()

    monkeypatch.setattr(trap_receiver, "SnmpEngine", FakeEngine)
    monkeypatch.setattr(trap_receiver.udp, "UdpTransport", FakeTransport)
    monkeypatch.setattr(
        trap_receiver.config,
        "addTransport",
        lambda snmp_engine, domain, transport: captured.update(
            transport=transport
        ),
    )
    monkeypatch.setattr(
        trap_receiver.config,
        "addV1System",
        lambda snmp_engine, area, community: captured.update(area=area),
    )
    monkeypatch.setattr(
        trap_receiver.ntfrcv,
        "NotificationReceiver",
        lambda snmp_engine, callback: captured.update(callback=callback),
    )

    main_loop = asyncio.new_event_loop()
    ready_event = threading.Event()
    thread = threading.Thread(
        target=trap_receiver._start_trap_receiver,
        args=(main_loop, ready_event),
    )
    thread.start()
    thread.join(timeout=2)
    main_loop.close()

    assert thread.is_alive() is False
    assert ready_event.is_set() is True
    assert captured["address"] == (
        "0.0.0.0",
        listen_settings.snmp_trap_listen_port,
    )
    assert captured["jobs"] == 1
    assert captured["ran"] is True
    assert captured["closed"] is True
