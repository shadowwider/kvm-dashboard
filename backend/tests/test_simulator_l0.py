import json
import socket
from types import SimpleNamespace

import pytest

from simulator.bridge import DashboardBridge
from simulator.l0_check import (
    _public_configuration,
    port_checks,
    resolve_configuration,
    snmp_get_checks,
    smoke_checks,
)
from simulator import main as simulator_main


def test_resolved_configuration_redacts_secrets_and_detects_community_drift(tmp_path):
    bridge_secret = "bridge-secret-must-not-leak"
    dashboard_community = "dashboard-community-must-not-leak"
    simulator_community = "simulator-community-must-not-leak"
    config, checks = resolve_configuration(
        {
            "SIMULATOR_BRIDGE_ENABLED": "true",
            "SIMULATOR_BRIDGE_TOKEN": bridge_secret,
            "SNMP_DEFAULT_COMMUNITY": dashboard_community,
            "SNMP_COMMUNITY": simulator_community,
            "SIM_TOPOLOGY": "all-profiles",
        },
        repo_root=tmp_path,
    )

    rendered = json.dumps(config)
    assert bridge_secret not in rendered
    assert dashboard_community not in rendered
    assert simulator_community not in rendered
    assert config["dashboard"]["bridge_token"] == "configured"
    assert config["simulator"]["community"] == "configured"
    assert any(
        item.name == "SNMP_COMMUNITY_ALIGNMENT" and item.status == "fail"
        for item in checks
    )


def test_doctor_fails_when_dashboard_and_simulator_trap_defaults_diverge(tmp_path):
    config, checks = resolve_configuration({}, repo_root=tmp_path)

    assert config["dashboard"]["trap_listen_port"] == 162
    assert config["simulator"]["trap_target_port"] == 10162
    assert any(
        item.name == "SNMP_TRAP_PORT_ALIGNMENT" and item.status == "fail"
        for item in checks
    )


def test_doctor_reports_exact_occupied_tcp_binding(tmp_path):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    try:
        config, _ = resolve_configuration(
            {
                "SIM_WEB_PORT": str(port),
                "SIM_TOPOLOGY": "custom-topology",
            },
            repo_root=tmp_path,
        )
        checks = port_checks(config, "simulator")
    finally:
        listener.close()

    occupied = next(item for item in checks if item.name == "simulator.http")
    assert occupied.status == "fail"
    assert f"tcp://127.0.0.1:{port}" in occupied.detail


def test_all_doctor_only_checks_separate_simulator_ui_port_in_dev_mode(tmp_path):
    built_config, _ = resolve_configuration(
        {"SIM_TOPOLOGY": "custom-topology"},
        repo_root=tmp_path,
    )
    built_checks = port_checks(built_config, "all")
    assert not [item for item in built_checks if item.name == "simulator-ui.http"]

    dev_config, _ = resolve_configuration(
        {
            "SIM_TOPOLOGY": "custom-topology",
            "SIMULATOR_UI_MODE": "dev",
        },
        repo_root=tmp_path,
    )
    dev_checks = port_checks(dev_config, "all")
    assert [item for item in dev_checks if item.name == "simulator-ui.http"]


def test_runtime_preflight_error_contains_exact_udp_binding(monkeypatch):
    occupied = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    occupied.bind(("127.0.0.1", 0))
    port = occupied.getsockname()[1]
    monkeypatch.setattr(simulator_main, "state", None)
    definition = SimpleNamespace(
        id="occupied",
        devices=[SimpleNamespace(host="127.0.0.1", snmp_port=port)],
    )
    try:
        with pytest.raises(OSError) as exc_info:
            simulator_main._preflight_bindings(definition)
    finally:
        occupied.close()

    assert f"127.0.0.1:{port}" in str(exc_info.value)


def test_bridge_status_remembers_success_without_exposing_token(monkeypatch):
    monkeypatch.setenv("SIMULATOR_BRIDGE_TOKEN", "never-print-this-token")
    bridge = DashboardBridge()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"bindings":[{"simulator_device_id":"d1"}]}'

    monkeypatch.setattr("simulator.bridge.request.urlopen", lambda *_args, **_kwargs: FakeResponse())
    result = bridge._request("PUT", "/test", {})
    status = bridge.status()

    assert result["ok"] is True
    assert status["binding_count"] == 1
    assert status["last_reconcile"]["ok"] is True
    assert "never-print-this-token" not in json.dumps(status)


def test_doctor_and_bridge_status_redact_url_credentials_and_query(monkeypatch, tmp_path):
    marker = "must-not-leak"
    raw_url = f"http://user:{marker}@127.0.0.1:18002/api/v1?token={marker}"
    config, checks = resolve_configuration(
        {"SIM_DASHBOARD_URL": raw_url},
        repo_root=tmp_path,
    )
    rendered = json.dumps({
        "configuration": _public_configuration(config),
        "checks": [item.to_dict() for item in checks],
    })
    assert marker not in rendered
    assert any(
        item.name == "SIM_DASHBOARD_URL" and item.status == "fail"
        for item in checks
    )
    smoke = smoke_checks(
        config,
        expected_topology="ccdc-regression",
        expected_agents=1,
        require_bridge=False,
        require_ui=False,
        timeout=0.1,
        fetch_json=lambda url, _timeout: (_ for _ in ()).throw(
            RuntimeError(url)
        ),
    )
    assert marker not in json.dumps([item.to_dict() for item in smoke])

    monkeypatch.setenv("SIM_DASHBOARD_URL", raw_url)
    bridge = DashboardBridge()
    bridge._remember({
        "enabled": True,
        "ok": False,
        "detail": f"failed requesting {raw_url}",
    })
    status_rendered = json.dumps(bridge.status())
    assert marker not in status_rendered
    assert "user:" not in status_rendered


def test_status_payload_exposes_failed_bridge_and_redacts_runtime_secrets(monkeypatch):
    class FakeState:
        def snapshot(self):
            return {
                "revision": 7,
                "scenario": {
                    "id": "all-profiles",
                    "devices": [{"id": "d1"}, {"id": "d2"}],
                },
            }

    class FakeBridge:
        base_url = "http://127.0.0.1:18002/api/v1"
        token = "secret-value"

        @staticmethod
        def status():
            return {
                "enabled": True,
                "dashboard_url": FakeBridge.base_url,
                "run_id": "local-simulator",
                "session_established": False,
                "last_attempt_at": "2026-07-31T00:00:00+00:00",
                "last_reconcile": {"enabled": True, "ok": False, "detail": "connection refused"},
                "binding_count": 0,
                "detail": "connection refused",
            }

    class FakeAgent:
        def __init__(self, device_id, port):
            self.device_id = device_id
            self.port = port

        def status(self):
            return {
                "device_id": self.device_id,
                "host": "127.0.0.1",
                "port": self.port,
                "thread_alive": True,
                "ready": True,
                "error_type": None,
                "error": None,
            }

    monkeypatch.setattr(simulator_main, "state", FakeState())
    monkeypatch.setattr(simulator_main, "active_topology_id", "all-profiles")
    monkeypatch.setattr(
        simulator_main,
        "agents",
        {"d1": FakeAgent("d1", 11161), "d2": FakeAgent("d2", 11162)},
    )
    monkeypatch.setattr(simulator_main, "bridge", FakeBridge())

    status = simulator_main.get_status()

    assert status["status"] == "degraded"
    assert status["agents"]["expected"] == 2
    assert status["agents"]["running"] == 2
    assert status["agents"]["device_ids"] == ["d1", "d2"]
    assert len(status["agents"]["bindings"]) == 2
    assert status["bridge"]["detail"] == "connection refused"
    assert "secret-value" not in json.dumps(status)


def test_smoke_requires_exact_topology_agents_bindings_and_trap_port(tmp_path):
    config, _ = resolve_configuration(
        {
            "BACKEND_PORT": "18002",
            "SIM_WEB_PORT": "18890",
            "SIM_DASHBOARD_URL": "http://127.0.0.1:18002/api/v1",
            "SIM_TOPOLOGY": "all-profiles",
            "SNMP_TRAP_PORT": "10162",
        },
        repo_root=tmp_path,
    )
    payloads = {
        "http://127.0.0.1:18002/health": {"status": "ok"},
        "http://127.0.0.1:18002/api/v1/health": {
            "status": "ok",
            "database": "connected",
            "scheduler": True,
            "trap_receiver": {
                "state": "running",
                "listen_port": 10162,
            },
        },
        "http://127.0.0.1:18890/api/v1/status": {
            "agents": {
                "running": 5,
                "expected": 5,
                "bindings": [
                    {
                        "device_id": f"d{index}",
                        "host": "127.0.0.1",
                        "port": 11161 + index,
                        "thread_alive": True,
                        "ready": True,
                        "error_type": None,
                    }
                    for index in range(5)
                ],
            },
            "bridge": {
                "enabled": True,
                "last_reconcile": {"ok": True},
                "binding_count": 5,
                "detail": None,
            },
            "trap": {"target_port": 10162},
        },
        "http://127.0.0.1:18890/api/v1/topologies": [{"id": "all-profiles"}],
        "http://127.0.0.1:18890/api/v1/state": {
            "scenario": {
                "id": "all-profiles",
                "devices": [
                    {
                        "id": f"d{index}",
                        "host": "127.0.0.1",
                        "snmp_port": 11161 + index,
                    }
                    for index in range(5)
                ],
            }
        },
    }

    checks = smoke_checks(
        config,
        expected_topology="all-profiles",
        expected_agents=5,
        require_bridge=True,
        require_ui=False,
        timeout=0.1,
        fetch_json=lambda url, _timeout: payloads[url],
        post_json=lambda _url, _timeout: {
            "enabled": True,
            "last_reconcile": {"ok": True},
            "binding_count": 5,
        },
    )

    assert not [item for item in checks if item.status == "fail"]
    assert {item.name for item in checks} >= {
        "dashboard.database",
        "dashboard.scheduler",
        "dashboard.trap_receiver",
        "simulator.active_topology",
        "simulator.agent_count",
        "simulator.agent_bindings",
        "simulator.bridge_reconcile",
        "simulator.bridge_bindings",
        "trap.port_alignment",
    }


@pytest.mark.asyncio
async def test_snmp_get_checks_query_every_preset_binding_without_printing_community(
    tmp_path,
):
    marker = "community-must-not-leak"
    config, _ = resolve_configuration(
        {
            "SIM_TOPOLOGY": "all-profiles",
            "SIM_ADDRESS_MODE": "port",
            "SNMP_TRAP_PORT": "10162",
        },
        repo_root=tmp_path,
    )
    calls = []

    class Value:
        @staticmethod
        def prettyPrint():
            return "SNMPv2-SMI::enterprises.32828.3.257.16"

    async def fake_query(host, port, community, oid, **options):
        calls.append((host, port, community, oid, options))
        return oid, Value()

    checks = await snmp_get_checks(
        config,
        community=marker,
        timeout=0.5,
        query=fake_query,
    )

    assert len(calls) == 5
    assert [call[1] for call in calls] == [11161, 11162, 11163, 11164, 11165]
    assert not [item for item in checks if item.status != "pass"]
    assert marker not in json.dumps([item.to_dict() for item in checks])


@pytest.mark.asyncio
async def test_snmp_get_checks_redacts_community_from_query_errors(tmp_path):
    marker = "community-error-must-not-leak"
    config, _ = resolve_configuration(
        {
            "SIM_TOPOLOGY": "ccdc-regression",
            "SIM_ADDRESS_MODE": "port",
            "SNMP_TRAP_PORT": "10162",
        },
        repo_root=tmp_path,
    )

    async def failing_query(*_args, **_options):
        raise RuntimeError(f"authentication failed for {marker}")

    checks = await snmp_get_checks(
        config,
        community=marker,
        timeout=0.5,
        query=failing_query,
    )

    assert len(checks) == 1
    assert checks[0].status == "fail"
    assert marker not in checks[0].detail
    assert "<redacted>" in checks[0].detail


@pytest.mark.asyncio
async def test_snmp_get_checks_rejects_snmp_no_value(tmp_path):
    config, _ = resolve_configuration(
        {
            "SIM_TOPOLOGY": "ccdc-regression",
            "SIM_ADDRESS_MODE": "port",
            "SNMP_TRAP_PORT": "10162",
        },
        repo_root=tmp_path,
    )

    class NoSuchObject:
        @staticmethod
        def prettyPrint():
            return "No Such Object currently exists at this OID"

        @staticmethod
        def isNoValue():
            return True

    async def fake_query(_host, _port, _community, oid, **_options):
        return oid, NoSuchObject()

    checks = await snmp_get_checks(
        config,
        community="public",
        timeout=0.5,
        query=fake_query,
    )

    assert len(checks) == 1
    assert checks[0].status == "fail"
