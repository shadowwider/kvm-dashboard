import socket

import pytest
from fastapi import HTTPException

from simulator.models import RuntimeDeviceAction, ScenarioDefinition, TopologyDefinition, TopologyDevice
from simulator.scenarios import built_in_scenarios
from simulator import main as simulator_main


def test_stop_runtime_clears_active_state():
    simulator_main.start_scenario("ccdc-regression")
    assert simulator_main.state is not None

    simulator_main.stop_runtime()

    assert simulator_main.state is None
    assert simulator_main.active_topology_id is None
    assert simulator_main.agents == {}
    with pytest.raises(HTTPException):
        simulator_main.current_state()


def test_topology_start_rolls_back_when_agent_bind_fails():
    scenario = built_in_scenarios()["ccdc-regression"]
    device = scenario.devices[0].model_copy(update={"host": "203.0.113.254", "snmp_port": 16161})
    bad_definition = ScenarioDefinition(id="bad-bind", title="Bad bind", devices=[device])

    with pytest.raises(RuntimeError):
        simulator_main._start_definition(bad_definition, "bad-bind")

    assert simulator_main.state is None
    assert simulator_main.agents == {}


def test_power_off_stops_agent_and_restore_restarts_agent():
    simulator_main.start_scenario("ccdc-regression")
    try:
        device_id = "sim-ccdc-01"
        assert device_id in simulator_main.agents

        simulator_main.runtime_device_action(device_id, type("Request", (), {"action": RuntimeDeviceAction.POWER_OFF})())
        assert device_id not in simulator_main.agents

        simulator_main.runtime_device_action(device_id, type("Request", (), {"action": RuntimeDeviceAction.RESTORE})())
        assert device_id in simulator_main.agents
    finally:
        simulator_main.stop_runtime()


def test_reachability_uses_transition_contract_and_lifecycle_intent():
    simulator_main.start_scenario("ccdc-regression")
    try:
        device_id = "sim-ccdc-01"
        simulator_main.runtime_device_action(
            device_id,
            type(
                "Request",
                (),
                {"action": RuntimeDeviceAction.POWER_OFF},
            )(),
        )
        assert device_id not in simulator_main.agents

        with pytest.raises(HTTPException) as exc_info:
            simulator_main.set_reachability(device_id, True)
        assert exc_info.value.status_code == 422

        response = simulator_main.set_reachability(device_id, False)
        assert response["idempotent"] is False
        assert response["lifecycle_intent"] == "ensure_agent_running"
        assert response["paused"] is False
        assert device_id in simulator_main.agents

        repeated = simulator_main.set_reachability(device_id, False)
        assert repeated["idempotent"] is True
        assert repeated["changed_paths"] == []
    finally:
        simulator_main.stop_runtime()


def test_reset_endpoint_suppresses_duplicate_reconcile_and_broadcast(monkeypatch):
    simulator_main.start_scenario("ccdc-regression")
    broadcasts = []
    reconciles = []
    monkeypatch.setattr(
        simulator_main,
        "_schedule_broadcast",
        lambda payload: broadcasts.append(payload),
    )
    monkeypatch.setattr(
        simulator_main.bridge,
        "reconcile",
        lambda runtime: reconciles.append(runtime.revision) or {"ok": True},
    )
    try:
        simulator_main.set_reachability("sim-ccdc-01", True)
        broadcasts.clear()
        reconciles.clear()

        changed = simulator_main.reset_scenario()
        assert changed["idempotent"] is False
        assert changed["changed_paths"]
        assert len(broadcasts) == 1
        assert len(reconciles) == 1

        broadcasts.clear()
        reconciles.clear()
        repeated = simulator_main.reset_scenario()
        assert repeated["idempotent"] is True
        assert repeated["changed_paths"] == []
        assert repeated["bridge"]["reconcile"] == {"skipped": "idempotent"}
        assert broadcasts == []
        assert reconciles == []
    finally:
        simulator_main.stop_runtime()


def test_trap_requires_known_non_empty_targets():
    simulator_main.start_scenario("ccdc-regression")
    try:
        with pytest.raises(HTTPException):
            simulator_main.send_trap(type("Request", (), {
                "device_ids": [],
                "device_id": None,
                "preset": None,
                "message": "test",
                "level": 3,
                "layout": "formal",
            })())
        with pytest.raises(HTTPException):
            simulator_main.send_trap(type("Request", (), {
                "device_ids": ["missing"],
                "device_id": None,
                "preset": None,
                "message": "test",
                "level": 3,
                "layout": "formal",
            })())
    finally:
        simulator_main.stop_runtime()
