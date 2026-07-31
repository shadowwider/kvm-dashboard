from simulator.models import EndpointStatePatch, OnlineState, RouteState, RouteStatePatch
from simulator.scenarios import built_in_scenarios
from simulator.snmp_agent import SYS_OBJECT_ID, endpoint_oid_map
from simulator.state import ScenarioState


def test_legacy_scenario_has_distinct_cpu_con_physical_ports():
    scenario = built_in_scenarios()["ccdc-regression"]
    device = scenario.devices[0]
    cpu_ports = {endpoint.port_index for endpoint in device.endpoints if endpoint.module_type == "cpu"}
    con_ports = {endpoint.port_index for endpoint in device.endpoints if endpoint.module_type == "con"}

    assert cpu_ports.isdisjoint(con_ports)
    assert {port.index for port in device.ports} == cpu_ports | con_ports


def test_state_backed_offline_transition_mutates_state_and_generates_trap():
    runtime = ScenarioState(built_in_scenarios()["ccdc-regression"])
    result = runtime.patch_endpoint(
        "sim-ccdc-01",
        "CPU-1-001",
        EndpointStatePatch(status=OnlineState.OFFLINE),
    )

    endpoint = next(item for item in runtime.device("sim-ccdc-01")["endpoints"] if item["id"] == "CPU-1-001")
    assert endpoint["status"] == OnlineState.OFFLINE
    assert result.trap is not None
    assert result.trap.state_backed is True
    assert result.trap.message == "CPU module CPU-1-001 went offline"


def test_route_updates_keep_explicit_simulation_provenance():
    runtime = ScenarioState(built_in_scenarios()["ccdc-regression"])
    runtime.patch_route("sim-ccdc-01", "route-1", RouteStatePatch(state=RouteState.DISCONNECTED))

    route = next(item for item in runtime.device("sim-ccdc-01")["routes"] if item["id"] == "route-1")
    assert route["state"] == RouteState.DISCONNECTED
    assert route["evidence"] == "simulation-declared"


def test_all_profiles_emit_profile_oid_tables():
    scenarios = built_in_scenarios()
    legacy = scenarios["ccdc-regression"].devices[0].model_dump(mode="json")
    ccdm = scenarios["ccdm-matrix-basic"].devices[0].model_dump(mode="json")

    legacy_map = endpoint_oid_map(legacy)
    ccdm_map = endpoint_oid_map(ccdm)

    assert legacy_map[SYS_OBJECT_ID] == legacy["system_oid"]
    assert any(".1.2.2.3.1000.1." in oid for oid in legacy_map)
    assert ccdm_map[SYS_OBJECT_ID] == ccdm["system_oid"]
    assert any(".2.3.1000.1." in oid for oid in ccdm_map)
    assert any(".1.2.2.3.1000.1." in oid for oid in ccdm_map)
