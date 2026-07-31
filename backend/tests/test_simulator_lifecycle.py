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
