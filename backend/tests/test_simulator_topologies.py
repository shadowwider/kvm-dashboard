import pytest
from fastapi import HTTPException

from simulator.models import ScenarioPort, TopologyDefinition, TopologyDevice, TopologyEdge
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
    assert device.trap_source_host == "127.0.1.1"
    assert device.system_oid == PROFILE_DEFINITIONS[device.profile]["system_oid"]


def test_port_mode_presets_have_unique_manifested_trap_source_hosts():
    topology = scenario_to_topology(built_in_scenarios()["all-profiles"])

    sources = [device.trap_source_host for device in topology.devices]

    assert sources == ["127.0.1.1", "127.0.1.2", "127.0.1.3", "127.0.1.4", "127.0.1.5"]


def test_user_topology_store_crud_round_trip(tmp_path):
    store = TopologyStore(tmp_path)
    topology = TopologyDefinition(
        id="custom-lab",
        title="Custom lab",
        devices=[TopologyDevice(id="ccdc", name="CCDC", profile="ccdc_legacy")],
    )

    created = store.create(topology)
    assert created.read_only is False
    assert created.revision == 1
    assert store.get("custom-lab").title == "Custom lab"

    updated = created.model_copy(update={"title": "Custom lab updated"})
    store.update("custom-lab", updated)
    assert store.get("custom-lab").title == "Custom lab updated"
    assert store.get("custom-lab").revision == 2

    listed_ids = {item.id for item in store.list()}
    assert "custom-lab" in listed_ids
    assert "ccdc-regression" in listed_ids

    store.delete("custom-lab")
    listed_ids = {item.id for item in store.list()}
    assert "custom-lab" not in listed_ids


def test_topology_store_rejects_stale_revision_without_overwriting_saved_document(tmp_path):
    store = TopologyStore(tmp_path)
    created = store.create(TopologyDefinition(
        id="revision-check",
        title="First version",
        devices=[TopologyDevice(id="ccdc", name="CCDC", profile="ccdc_legacy")],
    ))
    current = store.update("revision-check", created.model_copy(update={"title": "Second version"}))

    with pytest.raises(HTTPException) as raised:
        store.update("revision-check", created.model_copy(update={"title": "Stale overwrite"}))

    assert raised.value.status_code == 409
    assert store.get("revision-check").title == "Second version"
    assert store.get("revision-check").revision == current.revision == 2


def test_topology_store_rejects_non_loopback_host_by_default(tmp_path):
    store = TopologyStore(tmp_path)
    topology = TopologyDefinition(
        id="remote-probe",
        title="Must not become an SSRF target",
        devices=[TopologyDevice(id="ccdc", name="CCDC", profile="ccdc_legacy", host="203.0.113.55", snmp_port=161)],
    )

    with pytest.raises(HTTPException) as raised:
        store.create(topology)

    assert raised.value.status_code == 422


def test_topology_requires_real_unoccupied_ports_for_physical_edges():
    devices = [
        TopologyDevice(id="left", name="Left", profile="ccdc_legacy", ports=[ScenarioPort(index=1)]),
        TopologyDevice(id="right", name="Right", profile="ccdc_legacy", ports=[ScenarioPort(index=2)]),
    ]
    topology = TopologyDefinition(
        id="physical-link",
        title="Physical link",
        devices=devices,
        edges=[TopologyEdge(id="edge-1", source="left", target="right", kind="port-link", source_port=1, target_port=2)],
    )
    assert topology.edges[0].source_port == 1

    with pytest.raises(ValueError, match="occupied fixture port"):
        TopologyDefinition(
            id="physical-link-duplicate",
            title="Duplicate physical link",
            devices=devices,
            edges=[
                TopologyEdge(id="edge-1", source="left", target="right", kind="port-link", source_port=1, target_port=2),
                TopologyEdge(id="edge-2", source="left", target="right", kind="port-link", source_port=1, target_port=2),
            ],
        )
