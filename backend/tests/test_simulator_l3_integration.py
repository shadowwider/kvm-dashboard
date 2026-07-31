import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from simulator.models import (
    EndpointStatePatch,
    OnlineState,
    RuntimeDeviceAction,
    RuntimeStatePatch,
    ScenarioDefinition,
)
from simulator.profiles import render_oid_map
from simulator.runtime_paths import RuntimeTransitionError
from simulator.scenarios import built_in_scenarios
from simulator.state import ScenarioState


def _runtime(name: str) -> ScenarioState:
    return ScenarioState(built_in_scenarios()[name])


def _definition_payload(name: str) -> dict:
    return built_in_scenarios()[name].model_dump(mode="json")


def test_vendor_init_materializes_complete_state_and_renderer_never_fills_supplied_state():
    runtime = _runtime("ccdm-matrix-basic")
    device = runtime.device("sim-ccdm-01")
    state = runtime.profile_state("sim-ccdm-01")
    assert state["scalars"]["switch_temperature"] == "41.0"
    assert state["tables"]["target_module_table"]["1"]["id"] == "CPU-CCDM-001"
    assert state["tables"]["user_module_table"]["1"]["id"] == "CON-CCDM-001"

    rendered = render_oid_map(device, {"scalars": {}, "tables": {}})
    assert rendered == {"1.3.6.1.2.1.1.2.0": device["system_oid"]}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda device: device.update(
                {"system_oid": "1.3.6.1.4.1.32828.999.1"}
            ),
            "exact Profile sysObjectID",
        ),
        (
            lambda device: device.update(
                {"profile_state": {"scalars": {"not_a_leaf": 1}}}
            ),
            "unknown or disabled",
        ),
        (
            lambda device: device.update(
                {"profile_state": {"scalars": {"main_power": True}}}
            ),
            "requires an integer",
        ),
        (
            lambda device: device.update(
                {"profile_state": {"scalars": {"selected_channel": 1}}}
            ),
            "unknown or disabled",
        ),
    ],
)
def test_init_rejects_wrong_identity_and_invalid_or_disabled_overrides(
    mutate, message
):
    payload = _definition_payload("dp12-readonly")
    mutate(payload["devices"][0])
    definition = ScenarioDefinition.model_validate(payload)
    with pytest.raises(ValueError, match=message):
        ScenarioState(definition)


def test_ccdm_endpoint_filter_never_invents_rows_or_child_fan_gpio_rows():
    payload = _definition_payload("ccdm-matrix-basic")
    endpoint = copy.deepcopy(payload["devices"][0]["endpoints"][0])
    endpoint.update({"id": "CPU-2-UNMATERIALIZED", "row": 2, "port_index": 2})
    payload["devices"][0]["endpoints"].append(endpoint)
    runtime = ScenarioState(ScenarioDefinition.model_validate(payload))
    tables = runtime.profile_state("sim-ccdm-01")["tables"]
    assert set(tables["target_module_table"]) == {"1"}
    for table_id in (
        "gud_ccdmcon_mib_fan_table",
        "gud_ccdmcon_mib_gpio_table",
        "gud_ccdmcpu_mib_fan_table",
        "gud_ccdmcpu_mib_gpio_table",
    ):
        assert table_id not in tables


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("scalars.main_power", True),
        ("scalars.main_power", "1"),
        ("scalars.main_power", 99),
        ("tables.fan_table[1].fan_speed", 10001),
        ("scalars.selected_channel", 1),
        ("identity.system_oid", "1.2.3"),
        ("tables.fan_table[2].fan_speed", 1),
        ("endpoints[CPU-1].status", 0),
        ("ports[1].status", "down"),
    ],
)
def test_public_patch_rejects_old_p0_payloads_without_mutation(path, value):
    runtime = _runtime("dp12-readonly")
    before = runtime.snapshot()
    patch = RuntimeStatePatch.model_validate(
        {"patches": [{"path": path, "value": value}]}
    )
    with pytest.raises(ValueError):
        runtime.patch_device_state("sim-dp12-01", patch)
    assert runtime.snapshot() == before


def test_batch_second_failure_is_atomic_and_table_composite_path_commits_once():
    runtime = _runtime("ccdm-matrix-basic")
    before = runtime.snapshot()
    invalid = RuntimeStatePatch.model_validate(
        {
            "patches": [
                {"path": "scalars.function_switch", "value": 0},
                {
                    "path": "tables.gud_ccdmdwc_mib_fan_table[1,1].fan_speed",
                    "value": 10001,
                },
            ]
        }
    )
    with pytest.raises(ValueError):
        runtime.patch_device_state("sim-ccdm-01", invalid)
    assert runtime.snapshot() == before

    valid = RuntimeStatePatch.model_validate(
        {
            "patches": [
                {
                    "path": "tables.gud_ccdmdwc_mib_fan_table[1,1].fan_speed",
                    "value": 3456,
                }
            ]
        }
    )
    result = runtime.patch_device_state("sim-ccdm-01", valid)
    assert result.revision == before["revision"] + 1
    assert result.changed_paths == (
        "tables.gud_ccdmdwc_mib_fan_table[1,1].fan_speed",
    )


def test_endpoint_status_and_canonical_ccdm_row_commit_as_one_event():
    runtime = _runtime("ccdm-matrix-basic")
    result = runtime.patch_endpoint(
        "sim-ccdm-01",
        "CPU-CCDM-001",
        EndpointStatePatch(status=OnlineState.OFFLINE),
    )
    state = runtime.profile_state("sim-ccdm-01")
    assert state["tables"]["target_module_table"]["1"]["device_status"] == 0
    assert "endpoints[CPU-CCDM-001].status" in result.changed_paths
    assert "tables.target_module_table[1].device_status" in result.changed_paths
    assert len(runtime.snapshot()["events"]) == 1

    repeated = runtime.patch_endpoint(
        "sim-ccdm-01",
        "CPU-CCDM-001",
        EndpointStatePatch(status=OnlineState.OFFLINE),
    )
    assert repeated.idempotent is True
    assert repeated.trap is None
    assert repeated.revision == result.revision
    assert len(runtime.snapshot()["events"]) == 1


def test_endpoint_patch_is_strict_and_public_views_are_deep_copies():
    with pytest.raises(ValidationError):
        EndpointStatePatch.model_validate({"status": True})
    with pytest.raises(ValidationError):
        EndpointStatePatch.model_validate({"video_connected": 1})

    runtime = _runtime("ccdm-matrix-basic")
    device = runtime.device("sim-ccdm-01")
    profile_state = runtime.profile_state("sim-ccdm-01")
    snapshot = runtime.snapshot()
    renderable = runtime.renderable_snapshot()
    device["name"] = "leaked"
    profile_state["scalars"]["device_id"] = "leaked"
    snapshot["scenario"]["devices"][0]["name"] = "leaked"
    renderable["scenario"]["devices"][0]["name"] = "leaked"
    assert runtime.device("sim-ccdm-01")["name"] != "leaked"
    assert runtime.profile_state("sim-ccdm-01")["scalars"]["device_id"] != "leaked"


def test_action_is_availability_only_idempotent_and_invalid_transition_fails():
    runtime = _runtime("visionxs-pair")
    before_power = runtime.profile_state("sim-vision-cpu-01")["scalars"][
        "main_power"
    ]
    result = runtime.device_action(
        "sim-vision-cpu-01", RuntimeDeviceAction.POWER_OFF
    )
    assert result.lifecycle_intent == "stop_agent"
    assert result.changed_paths == ("runtime.availability",)
    assert (
        runtime.profile_state("sim-vision-cpu-01")["scalars"]["main_power"]
        == before_power
    )
    repeated = runtime.device_action(
        "sim-vision-cpu-01", RuntimeDeviceAction.POWER_OFF
    )
    assert repeated.idempotent is True
    assert repeated.trap is None
    with pytest.raises(RuntimeTransitionError):
        runtime.device_action(
            "sim-vision-cpu-01", RuntimeDeviceAction.DISCONNECT
        )


def test_scenario_reset_is_one_global_revision_and_event():
    runtime = _runtime("all-profiles")
    runtime.patch_endpoint(
        "sim-ccdm-01",
        "CPU-CCDM-001",
        EndpointStatePatch(status=OnlineState.OFFLINE),
    )
    runtime.device_action(
        "sim-vision-cpu-01", RuntimeDeviceAction.POWER_OFF
    )
    before_reset = runtime.revision
    result = runtime.reset()
    assert result.revision == before_reset + 1
    assert result.event["action"] == "reset"
    assert runtime.snapshot()["events"][-1]["revision"] == result.revision
    assert runtime.is_paused("sim-vision-cpu-01") is False
    assert next(
        endpoint
        for endpoint in runtime.device("sim-ccdm-01")["endpoints"]
        if endpoint["id"] == "CPU-CCDM-001"
    )["status"] == OnlineState.ONLINE


def test_concurrent_endpoint_writes_never_expose_half_synchronized_state():
    runtime = _runtime("ccdm-matrix-basic")

    def write(status: OnlineState):
        runtime.patch_endpoint(
            "sim-ccdm-01",
            "CPU-CCDM-001",
            EndpointStatePatch(status=status),
        )

    def read():
        snapshot = runtime.renderable_snapshot("sim-ccdm-01")["device"]
        endpoint = next(
            item
            for item in snapshot["endpoints"]
            if item["id"] == "CPU-CCDM-001"
        )
        canonical = snapshot["profile_state"]["tables"][
            "target_module_table"
        ]["1"]["device_status"]
        return int(endpoint["status"]), canonical

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = []
        for index in range(100):
            futures.append(
                pool.submit(
                    write,
                    OnlineState.OFFLINE if index % 2 else OnlineState.ONLINE,
                )
            )
            futures.append(pool.submit(read))
        results = [future.result() for future in futures]
        observations = [result for result in results if result is not None]
    assert observations
    assert all(endpoint == canonical for endpoint, canonical in observations)
