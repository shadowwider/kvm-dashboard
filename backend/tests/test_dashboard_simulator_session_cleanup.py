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
