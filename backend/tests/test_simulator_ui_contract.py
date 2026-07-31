from simulator.models import RuntimeStatePatch, TopologyDefinition, TrapRequest


def test_ui_topology_payload_matches_backend_schema():
    payload = {
        "id": "ui-contract",
        "title": "UI Contract",
        "devices": [
            {
                "id": "ccdc-1",
                "name": "CCDC 1",
                "profile": "ccdc_legacy",
                "host": "127.0.0.1",
                "snmp_port": 11161,
                "ports": [{"index": 1, "status": "up"}],
                "endpoints": [],
                "routes": [],
                "profile_state": {},
                "position": {"x": 10, "y": 20},
            }
        ],
        "edges": [{"id": "edge-1", "source": "ccdc-1", "target": "ccdc-1", "kind": "route", "label": "simulation-declared"}],
    }

    topology = TopologyDefinition.model_validate(payload)

    assert topology.devices[0].profile.value == "ccdc_legacy_unverified"
    assert topology.devices[0].ports[0].index == 1


def test_ui_runtime_patch_payload_matches_backend_schema():
    patch = RuntimeStatePatch.model_validate({
        "patches": [{"path": "scalars.temperature1", "value": "61.5"}],
        "emit_trap": False,
    })

    assert patch.patches[0].path == "scalars.temperature1"


def test_ui_trap_payload_matches_backend_schema():
    trap = TrapRequest.model_validate({
        "device_ids": ["sim-ccdc-01"],
        "level": 3,
        "message": "Display connection state changed",
        "layout": "formal",
    })

    assert trap.level == 3
    assert trap.device_ids == ["sim-ccdc-01"]
