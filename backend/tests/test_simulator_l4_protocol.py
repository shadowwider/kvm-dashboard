"""L4 protocol and lifecycle acceptance tests.

Expected OIDs come from the independent L1 JSON Golden manifests.  These tests
send BER over a real loopback UDP socket; they do not invoke ``_respond`` as a
test shortcut.
"""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import pytest
from pyasn1.codec.ber import decoder as ber_decoder, encoder as ber_encoder
from pyasn1.type.univ import ObjectIdentifier
from pysnmp.proto import api as snmp_api
from fastapi.testclient import TestClient

from simulator import main as simulator_main
from simulator.models import RuntimeStatePatch, ScenarioDefinition
from simulator.scenarios import built_in_scenarios
from simulator.snmp_agent import SnmpAgent, SYS_OBJECT_ID, oid_tuple
from simulator.state import ScenarioState
from simulator.topology_store import TopologyStore


GOLDEN_DIR = Path(__file__).parent / "golden" / "simulator"
PROFILE_CASES = (
    ("ccdc_legacy", "ccdc-regression", "sim-ccdc-01", "ccdc_legacy.objects.json"),
    ("ccdm_matrix", "ccdm-matrix-basic", "sim-ccdm-01", "ccdm.objects.json"),
    ("visionxs_cpu", "visionxs-pair", "sim-vision-cpu-01", "visionxs_cpu.objects.json"),
    ("visionxs_con", "visionxs-pair", "sim-vision-con-01", "visionxs_con.objects.json"),
    ("dp12_mux_atc", "dp12-readonly", "sim-dp12-01", "dp12_mux_atc.objects.json"),
)


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _runtime_for(scenario_id: str, device_id: str) -> tuple[ScenarioState, object]:
    source = built_in_scenarios()[scenario_id]
    selected = next(item for item in source.devices if item.id == device_id)
    port = _free_udp_port()
    device = selected.model_copy(update={"snmp_port": port})
    definition = ScenarioDefinition(
        id=f"l4-{device_id}", title="L4 UDP test", devices=[device]
    )
    return ScenarioState(definition), device


def _request(
    host: str,
    port: int,
    oids: list[str],
    *,
    kind: str = "get",
    non_repeaters: int = 0,
    max_repetitions: int = 0,
):
    p_mod = snmp_api.protoModules[snmp_api.protoVersion2c]
    message = p_mod.Message()
    p_mod.apiMessage.setDefaults(message)
    p_mod.apiMessage.setCommunity(message, "public")
    pdu = {
        "get": p_mod.GetRequestPDU,
        "next": p_mod.GetNextRequestPDU,
        "bulk": p_mod.GetBulkRequestPDU,
        "set": p_mod.SetRequestPDU,
    }[kind]()
    p_mod.apiPDU.setDefaults(pdu)
    p_mod.apiPDU.setRequestID(pdu, 101)
    if kind == "bulk":
        p_mod.apiBulkPDU.setNonRepeaters(pdu, non_repeaters)
        p_mod.apiBulkPDU.setMaxRepetitions(pdu, max_repetitions)
    p_mod.apiPDU.setVarBinds(
        pdu,
        [(ObjectIdentifier(oid_tuple(oid)), p_mod.Null("")) for oid in oids],
    )
    p_mod.apiMessage.setPDU(message, pdu)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
        client.settimeout(2)
        client.sendto(ber_encoder.encode(message), (host, port))
        response, _ = client.recvfrom(65535)
    decoded, _ = ber_decoder.decode(response, asn1Spec=p_mod.Message())
    response_pdu = p_mod.apiMessage.getPDU(decoded)
    return p_mod, response_pdu, list(p_mod.apiPDU.getVarBinds(response_pdu))


def _golden_get_oid(document: dict) -> str | None:
    candidate = next((item for item in document["objects"] if item["gettable"]), None)
    if candidate is None:
        return None
    template = candidate["get_oid_template"]
    return re.sub(r"\{[^}]+\}", "1", template)


@pytest.mark.parametrize(("_profile", "scenario_id", "device_id", "golden_name"), PROFILE_CASES)
def test_all_profiles_real_udp_get_uses_independent_l1_golden(
    _profile, scenario_id, device_id, golden_name
):
    golden = json.loads((GOLDEN_DIR / golden_name).read_text(encoding="utf-8"))
    runtime, device = _runtime_for(scenario_id, device_id)
    agent = SnmpAgent(runtime, device.id)
    agent.start()
    try:
        requested = [SYS_OBJECT_ID]
        golden_oid = _golden_get_oid(golden)
        if golden_oid is not None:
            requested.append(golden_oid)
        p_mod, response, varbinds = _request(device.host, device.snmp_port, requested)
        assert int(p_mod.apiPDU.getErrorStatus(response)) == 0
        assert str(varbinds[0][0]).lstrip(".") == SYS_OBJECT_ID
        assert varbinds[0][1].prettyPrint() == golden["sys_object_id"]["oid"]
        if golden_oid is not None:
            assert str(varbinds[1][0]).lstrip(".") == golden_oid
            assert not varbinds[1][1].isSameTypeWith(p_mod.NoSuchObject())
    finally:
        assert agent.stop()


def test_udp_getnext_getbulk_end_of_mib_and_set_not_writable():
    runtime, device = _runtime_for("dp12-readonly", "sim-dp12-01")
    agent = SnmpAgent(runtime, device.id)
    agent.start()
    try:
        root = "1.3.6.1.4.1.32828.3.1792.17.2"
        p_mod, response, varbinds = _request(device.host, device.snmp_port, [root], kind="next")
        assert int(p_mod.apiPDU.getErrorStatus(response)) == 0
        assert oid_tuple(str(varbinds[0][0])) > oid_tuple(root)

        _, bulk_response, bulk_varbinds = _request(
            device.host, device.snmp_port, [root], kind="bulk", max_repetitions=3
        )
        assert int(p_mod.apiPDU.getErrorStatus(bulk_response)) == 0
        assert len(bulk_varbinds) == 3
        assert [oid_tuple(str(item[0])) for item in bulk_varbinds] == sorted(
            oid_tuple(str(item[0])) for item in bulk_varbinds
        )

        _, after_response, after = _request(
            device.host, device.snmp_port, ["1.3.6.1.9.999"], kind="next"
        )
        assert int(p_mod.apiPDU.getErrorStatus(after_response)) == 0
        assert after[0][1].isSameTypeWith(p_mod.EndOfMibView())

        _, set_response, _ = _request(device.host, device.snmp_port, [SYS_OBJECT_ID], kind="set")
        assert int(p_mod.apiPDU.getErrorStatus(set_response)) == 17
    finally:
        assert agent.stop()


def test_patch_is_observable_with_same_revision_over_real_udp():
    runtime, device = _runtime_for("ccdm-matrix-basic", "sim-ccdm-01")
    agent = SnmpAgent(runtime, device.id)
    agent.start()
    try:
        result = runtime.patch_device_state(
            device.id,
            RuntimeStatePatch.model_validate({
                "patches": [{"path": "scalars.switch_temperature", "value": "66.6"}]
            }),
        )
        oid = "1.3.6.1.4.1.32828.3.257.10.2.3.4.0"
        p_mod, response, varbinds = _request(device.host, device.snmp_port, [oid])
        assert int(p_mod.apiPDU.getErrorStatus(response)) == 0
        assert varbinds[0][1].prettyPrint() == "66.6"
        assert runtime.snapshot()["revision"] == result.revision
        assert agent._snapshot_revision == result.revision
    finally:
        assert agent.stop()


def test_protocol_render_failure_is_visible_and_agent_remains_alive(monkeypatch):
    runtime, device = _runtime_for("dp12-readonly", "sim-dp12-01")
    agent = SnmpAgent(runtime, device.id)
    agent.start()
    original = agent._oid_entries
    monkeypatch.setattr(agent, "_oid_entries", lambda: (_ for _ in ()).throw(ValueError("bad render")))
    with pytest.raises(socket.timeout):
        _request(device.host, device.snmp_port, [SYS_OBJECT_ID])
    assert agent.status()["protocol_error_count"] == 1
    assert agent.status()["last_protocol_error_type"] == "ValueError"
    assert agent.status()["thread_alive"] is True
    monkeypatch.setattr(agent, "_oid_entries", original)
    _, response, _ = _request(device.host, device.snmp_port, [SYS_OBJECT_ID])
    assert int(snmp_api.protoModules[snmp_api.protoVersion2c].apiPDU.getErrorStatus(response)) == 0
    assert agent.stop()


def test_overlapping_topology_candidate_failure_restores_old_udp_runtime(monkeypatch):
    simulator_main.stop_runtime()
    source = built_in_scenarios()["ccdc-regression"].devices[0]
    old_definition = ScenarioDefinition(
        id="l4-old",
        title="L4 old topology",
        devices=[source.model_copy(update={"snmp_port": _free_udp_port()})],
    )
    simulator_main._start_definition(old_definition, "l4-old")
    old_runtime = simulator_main.state
    old_topology = simulator_main.active_topology_id
    original_start = SnmpAgent.start

    def fail_only_candidate(self):
        if self.state is not old_runtime:
            raise RuntimeError("injected candidate start failure")
        return original_start(self)

    monkeypatch.setattr(SnmpAgent, "start", fail_only_candidate)
    try:
        with pytest.raises(RuntimeError, match="old topology restored"):
            simulator_main._start_definition(old_definition, "l4-candidate")
        assert simulator_main.state is old_runtime
        assert simulator_main.active_topology_id == old_topology
        binding = simulator_main.agents["sim-ccdc-01"].status()
        _, response, _ = _request(binding["host"], binding["port"], [SYS_OBJECT_ID])
        assert int(snmp_api.protoModules[snmp_api.protoVersion2c].apiPDU.getErrorStatus(response)) == 0
    finally:
        simulator_main.stop_runtime()


def test_non_overlapping_handover_stop_failure_does_not_commit_candidate(monkeypatch):
    simulator_main.stop_runtime()
    source = built_in_scenarios()["ccdc-regression"].devices[0]
    old_definition = ScenarioDefinition(
        id="l4-old-stop",
        title="L4 old topology",
        devices=[source.model_copy(update={"snmp_port": _free_udp_port()})],
    )
    candidate_definition = old_definition.model_copy(
        update={
            "id": "l4-new-stop",
            "devices": [
                old_definition.devices[0].model_copy(
                    update={"snmp_port": _free_udp_port()}
                )
            ],
        }
    )
    simulator_main._start_definition(old_definition, "l4-old-stop")
    old_runtime = simulator_main.state
    old_agent = simulator_main.agents[source.id]
    original_stop = old_agent.stop
    calls = 0

    def stop_then_report_failure():
        nonlocal calls
        calls += 1
        original_stop()
        return calls != 1

    monkeypatch.setattr(old_agent, "stop", stop_then_report_failure)
    try:
        with pytest.raises(RuntimeError, match="previous topology failed to stop"):
            simulator_main._start_definition(candidate_definition, "l4-new-stop")
        assert simulator_main.state is old_runtime
        assert simulator_main.active_topology_id == "l4-old-stop"
        binding = simulator_main.agents[source.id].status()
        _, response, _ = _request(binding["host"], binding["port"], [SYS_OBJECT_ID])
        assert int(snmp_api.protoModules[snmp_api.protoVersion2c].apiPDU.getErrorStatus(response)) == 0
    finally:
        simulator_main.stop_runtime()


def test_store_atomic_replace_leaves_previous_document_and_reports_corruption(tmp_path, monkeypatch):
    store = TopologyStore(tmp_path)
    topology = simulator_main.store.presets()["ccdc-regression"].model_copy(
        update={"id": "atomic", "read_only": False, "source": "user"}
    )
    store.create(topology)
    before = (tmp_path / "atomic.json").read_bytes()
    monkeypatch.setattr("simulator.topology_store.os.replace", lambda *_: (_ for _ in ()).throw(OSError("injected")))
    with pytest.raises(OSError):
        store.update("atomic", topology.model_copy(update={"title": "new"}))
    assert (tmp_path / "atomic.json").read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert "broken.json" in store.invalid_documents()


def test_rest_websocket_and_udp_observe_one_patch_revision(monkeypatch):
    runtime, device = _runtime_for("ccdm-matrix-basic", "sim-ccdm-01")
    agent = SnmpAgent(runtime, device.id)
    agent.start()
    monkeypatch.setattr(simulator_main, "state", runtime)
    monkeypatch.setattr(simulator_main, "active_topology_id", "l4-rest-ws")
    monkeypatch.setattr(simulator_main, "agents", {device.id: agent})
    monkeypatch.setattr(simulator_main, "start_topology", lambda _identifier: runtime)
    monkeypatch.setattr(simulator_main, "stop_runtime", lambda: None)
    monkeypatch.setattr(simulator_main.bridge, "reconcile", lambda _runtime: {"enabled": False})
    try:
        with TestClient(simulator_main.app) as client:
            with client.websocket_connect("/api/v1/ws", headers={"origin": "http://testserver"}) as websocket:
                initial = websocket.receive_json()
                assert initial["type"] == "snapshot"
                assert initial["state"]["revision"] == runtime.revision
                assert initial["state"]["runtime_instances"]["devices"]
                response = client.patch(
                    f"/api/v1/runtime/devices/{device.id}/state",
                    json={
                        "expected_revision": runtime.revision,
                        "patches": [
                            {"path": "scalars.switch_temperature", "value": "66.6"}
                        ],
                    },
                )
                assert response.status_code == 200
                body = response.json()
                assert body["state"]["active_topology_id"] == "l4-rest-ws"
                instance = next(
                    item
                    for item in body["state"]["runtime_instances"]["devices"]
                    if item["device_id"] == device.id
                )
                assert "scalars.switch_temperature" in instance["path_registry"]["writable_paths"]
                event = websocket.receive_json()
                assert event["type"] == "runtime_state_patch"
                assert event["schema_version"] == 1
                assert event["event_id"] == body["event"]["event_id"]
                assert event["revision"] == body["revision"] == runtime.revision
                assert event["changed_paths"] == body["changed_paths"]
                oid = "1.3.6.1.4.1.32828.3.257.10.2.3.4.0"
                p_mod, udp_response, varbinds = _request(device.host, device.snmp_port, [oid])
                assert int(p_mod.apiPDU.getErrorStatus(udp_response)) == 0
                assert varbinds[0][1].prettyPrint() == "66.6"
                conflict = client.patch(
                    f"/api/v1/runtime/devices/{device.id}/state",
                    json={
                        "expected_revision": 1,
                        "patches": [
                            {"path": "scalars.switch_temperature", "value": "67.0"}
                        ],
                    },
                )
                assert conflict.status_code == 409
                assert conflict.json()["code"] == "revision_conflict"
                assert conflict.json()["current_revision"] == runtime.revision
    finally:
        assert agent.stop()
