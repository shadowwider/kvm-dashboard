import threading

import pytest

from app.snmp import trap_receiver


@pytest.mark.asyncio
async def test_trap_receiver_startup_propagates_background_bind_failure(monkeypatch):
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
async def test_trap_receiver_startup_waits_for_running_state(monkeypatch):
    def successful_startup(_main_loop, ready_event: threading.Event):
        trap_receiver._set_receiver_status("running")
        ready_event.set()

    monkeypatch.setattr(trap_receiver, "_start_trap_receiver", successful_startup)

    status = await trap_receiver.start_trap_receiver(startup_timeout=0.5)

    assert status["state"] == "running"
    assert status["listen_port"] == trap_receiver.settings.snmp_trap_port
