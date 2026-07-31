from simulator.models import TopologyDefinition, TopologyDevice
from simulator.profiles import PROFILE_DEFINITIONS
from simulator.scenarios import built_in_scenarios
from simulator.topology_store import TopologyStore, scenario_to_topology, topology_to_scenario


def test_built_in_scenarios_convert_to_read_only_topology_presets():
    scenario = built_in_scenarios()["all-profiles"]
    topology = scenario_to_topology(scenario)

    assert topology.id == scenario.id
    assert topology.read_only is True
    assert topology.source == "preset"
    assert len(topology.devices) == len(scenario.devices)
    assert {device.id for device in topology.devices} == {device.id for device in scenario.devices}


def test_topology_to_scenario_fills_profile_defaults_and_addresses():
    topology = TopologyDefinition(
        id="unit-topology",
        title="Unit topology",
        devices=[TopologyDevice(id="dp", name="DP", profile="dp12_mux_atc")],
    )

    scenario = topology_to_scenario(topology)
    device = scenario.devices[0]

    assert device.profile.value == "dp12_mux_atc_readonly"
    assert device.host == "127.0.0.1"
    assert device.snmp_port >= 1
    assert device.system_oid == PROFILE_DEFINITIONS[device.profile]["system_oid"]


def test_user_topology_store_crud_round_trip(tmp_path):
    store = TopologyStore(tmp_path)
    topology = TopologyDefinition(
        id="custom-lab",
        title="Custom lab",
        devices=[TopologyDevice(id="ccdc", name="CCDC", profile="ccdc_legacy")],
    )

    created = store.create(topology)
    assert created.read_only is False
    assert store.get("custom-lab").title == "Custom lab"

    updated = created.model_copy(update={"title": "Custom lab updated"})
    store.update("custom-lab", updated)
    assert store.get("custom-lab").title == "Custom lab updated"

    listed_ids = {item.id for item in store.list()}
    assert "custom-lab" in listed_ids
    assert "ccdc-regression" in listed_ids

    store.delete("custom-lab")
    listed_ids = {item.id for item in store.list()}
    assert "custom-lab" not in listed_ids
