import asyncio

import pytest
from fastapi import HTTPException

from app.api import simulator as simulator_api
from app.models.simulator_run import SimulatorRun


class _Session:
    def __init__(self, run):
        self.run = run
        self.executed = []
        self.deleted = []
        self.commits = 0

    async def get(self, model, identifier):
        return self.run if model is SimulatorRun and identifier == self.run.id else None

    async def execute(self, statement):
        self.executed.append(statement)

    async def delete(self, value):
        self.deleted.append(value)

    async def commit(self):
        self.commits += 1


class _SessionContext:
    def __init__(self, session):
        self.session = session
        self.entered = 0
        self.exited = 0

    async def __aenter__(self):
        self.entered += 1
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited += 1
        return False


def _run():
    return SimulatorRun(
        id="local-simulator",
        scenario_id="all-profiles",
        session_id="current-session",
        session_epoch="current-epoch",
        session_started_at=1,
        revision=2,
        manifest={},
    )


def test_bridge_cleanup_deletes_only_the_current_session_resources(monkeypatch):
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_enabled", True)
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_token", "bridge-token")
    session = _Session(_run())

    result = asyncio.run(
        simulator_api.cleanup_owned_session(
            "local-simulator",
            "current-session",
            simulator_api.SimulatorSessionProof(session_epoch="current-epoch"),
            x_simulator_token="bridge-token",
            db=session,
        )
    )

    assert result is None
    assert session.deleted == [session.run]
    assert len(session.executed) == 2  # endpoints then devices, both run-namespaced
    assert session.commits == 1


def test_bridge_cleanup_cannot_delete_a_run_taken_by_a_newer_session(monkeypatch):
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_enabled", True)
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_token", "bridge-token")
    session = _Session(_run())

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            simulator_api.cleanup_owned_session(
                "local-simulator",
                "old-session",
                simulator_api.SimulatorSessionProof(session_epoch="old-epoch"),
                x_simulator_token="bridge-token",
                db=session,
            )
        )

    assert raised.value.status_code == 409
    assert session.deleted == []
    assert session.executed == []


@pytest.mark.asyncio
async def test_expired_run_reaper_uses_dashboard_session_factory(monkeypatch):
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_enabled", True)
    session = object()
    context = _SessionContext(session)
    cleanup_calls = []

    async def cleanup_expired_runs(db):
        cleanup_calls.append(db)
        return 3

    monkeypatch.setattr(simulator_api, "AsyncSessionLocal", lambda: context)
    monkeypatch.setattr(simulator_api, "cleanup_expired_runs", cleanup_expired_runs)

    result = await simulator_api.reap_expired_simulator_runs()

    assert result == 3
    assert cleanup_calls == [session]
    assert context.entered == 1
    assert context.exited == 1


@pytest.mark.asyncio
async def test_expired_run_reaper_skips_session_when_bridge_is_disabled(monkeypatch):
    monkeypatch.setattr(simulator_api.settings, "simulator_bridge_enabled", False)

    def fail_if_opened():
        raise AssertionError("session factory must not be opened")

    monkeypatch.setattr(simulator_api, "AsyncSessionLocal", fail_if_opened)

    assert await simulator_api.reap_expired_simulator_runs() == 0
