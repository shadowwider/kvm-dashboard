from types import SimpleNamespace

from app.snmp.trap_receiver import simulator_device_from_trap_source


def _run(run_id, devices):
    return SimpleNamespace(id=run_id, manifest={"scenario": {"devices": devices}})


def test_manifested_unique_loopback_source_attributes_the_right_simulator_device():
    run = _run("local", [
        {"id": "ccdc", "trap_source_host": "127.0.1.1"},
        {"id": "ccdm", "trap_source_host": "127.0.1.2"},
    ])

    assert simulator_device_from_trap_source([run], "127.0.1.2") == "sim_local_ccdm"


def test_missing_or_ambiguous_trap_source_never_selects_an_arbitrary_device():
    runs = [
        _run("one", [{"id": "a", "trap_source_host": "127.0.1.1"}]),
        _run("two", [{"id": "b", "trap_source_host": "127.0.1.1"}]),
    ]

    assert simulator_device_from_trap_source(runs, "127.0.1.1") is None
    assert simulator_device_from_trap_source(runs, "127.0.1.9") is None
