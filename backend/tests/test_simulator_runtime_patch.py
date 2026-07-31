import pytest

from simulator.models import RuntimeStatePatch
from simulator.scenarios import built_in_scenarios
from simulator.snmp_agent import endpoint_oid_map
from simulator.state import ScenarioState


def test_runtime_patch_is_atomic_when_later_path_fails():
    runtime = ScenarioState(built_in_scenarios()["ccdc-regression"])
    before = runtime.snapshot()
    before_oids = endpoint_oid_map(runtime.device("sim-ccdc-01"), runtime.profile_state("sim-ccdc-01"))

    patch = RuntimeStatePatch.model_validate({
        "patches": [
            {"path": "scalars.temperature", "value": 61.5},
            {"path": "ports[999].status", "value": "down"},
        ]
    })

    with pytest.raises(KeyError):
        runtime.patch_device_state("sim-ccdc-01", patch)

    assert runtime.snapshot() == before
    assert endpoint_oid_map(runtime.device("sim-ccdc-01"), runtime.profile_state("sim-ccdc-01")) == before_oids


def test_runtime_patch_rejects_unknown_profile_scalar():
    runtime = ScenarioState(built_in_scenarios()["ccdc-regression"])
    patch = RuntimeStatePatch.model_validate({"patches": [{"path": "scalars.not_a_real_field", "value": 1}]})

    with pytest.raises(ValueError):
        runtime.patch_device_state("sim-ccdc-01", patch)


def test_runtime_patch_updates_rendered_oid_value():
    runtime = ScenarioState(built_in_scenarios()["ccdc-regression"])
    patch = RuntimeStatePatch.model_validate({"patches": [{"path": "scalars.temperature", "value": 66.6}]})

    runtime.patch_device_state("sim-ccdc-01", patch)
    device = runtime.device("sim-ccdc-01")
    rendered = endpoint_oid_map(device, runtime.profile_state("sim-ccdc-01"))

    assert rendered[f"{device['system_oid']}.2.3.3.0"] == 66.6
