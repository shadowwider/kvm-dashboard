"""L0 environment doctor and live protocol checks for the KVM simulator.

The doctor and HTTP smoke paths intentionally use only the Python standard
library.  The optional ``snmp-get`` path lazily imports the project's pysnmp
poller so the environment checks remain usable when a higher simulator layer
(profile/state/SNMP/UI) is broken.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib import error, parse, request


_PLACEHOLDER_SECRETS = {
    "change_me",
    "change_me_simulator_token",
    "change_me_to_a_random_64_char_string",
    "local-only-change-me",
    "local_dev_simulator_token",
    "<replace_with_one_random_local_token>",
}
_PRESET_PORT_BINDINGS: dict[str, list[int]] = {
    "ccdc-regression": [11161],
    "ccdm-matrix-basic": [11162],
    "visionxs-pair": [11163, 11164],
    "dp12-readonly": [11165],
    "all-profiles": [11161, 11162, 11163, 11164, 11165],
}
_SYS_OBJECT_ID_OID = "1.3.6.1.2.1.1.2.0"


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _normalise_environment(values: Mapping[str, str]) -> dict[str, str]:
    return {str(key).upper(): str(value) for key, value in values.items()}


def _read_env_file(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[:1] == value[-1:] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.upper()] = value
    return values


def _secret_state(value: str | None, *, default_is_secret: bool = False) -> str:
    if not value:
        return "default" if default_is_secret else "not-configured"
    if value.strip().lower() in _PLACEHOLDER_SECRETS:
        return "default-placeholder"
    return "configured"


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_port(
    env: Mapping[str, str],
    key: str,
    default: int,
    checks: list[Check],
) -> int:
    raw = env.get(key, str(default))
    try:
        port = int(raw)
    except ValueError:
        checks.append(Check(key, "fail", f"{raw!r} is not an integer port"))
        return default
    if not 1 <= port <= 65535:
        checks.append(Check(key, "fail", f"{port} is outside 1..65535"))
        return default
    return port


def _valid_http_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _safe_url(value: str) -> str:
    """Remove userinfo, query and fragment before a URL reaches diagnostics."""
    parsed = parse.urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return "<invalid-url>"
    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    try:
        port = f":{parsed.port}" if parsed.port is not None else ""
    except ValueError:
        return "<invalid-url>"
    query = "<redacted>" if parsed.query else ""
    return parse.urlunsplit((parsed.scheme, f"{hostname}{port}", parsed.path, query, ""))


def _public_configuration(config: dict) -> dict:
    public = deepcopy(config)
    public["simulator"]["dashboard_url"] = _safe_url(
        public["simulator"]["dashboard_url"]
    )
    public["dashboard_ui"]["backend_target"] = _safe_url(
        public["dashboard_ui"]["backend_target"]
    )
    public["simulator_ui"]["simulator_target"] = _safe_url(
        public["simulator_ui"]["simulator_target"]
    )
    return public


def resolve_configuration(
    environment: Mapping[str, str] | None = None,
    *,
    env_file: Path | None = None,
    repo_root: Path | None = None,
) -> tuple[dict, list[Check]]:
    """Resolve L0 configuration without exposing any secret value."""

    source_environment = os.environ if environment is None else environment
    merged = _read_env_file(env_file)
    merged.update(_normalise_environment(source_environment))
    checks: list[Check] = []

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    backend_dir = root / "backend"
    simulator_ui_dist = root / "simulator-ui" / "dist"
    simulator_ui_built = (simulator_ui_dist / "index.html").is_file()

    backend_host = merged.get("BACKEND_HOST", "127.0.0.1")
    backend_port = _as_port(merged, "BACKEND_PORT", 8000, checks)
    dashboard_ui_host = merged.get("DASHBOARD_UI_HOST", "127.0.0.1")
    dashboard_ui_port = _as_port(merged, "DASHBOARD_UI_PORT", 3000, checks)
    simulator_host = merged.get("SIMULATOR_HOST", "127.0.0.1")
    simulator_port = _as_port(merged, "SIM_WEB_PORT", 8888, checks)
    simulator_ui_host = merged.get("SIMULATOR_UI_HOST", "127.0.0.1")
    simulator_ui_port = _as_port(merged, "SIMULATOR_UI_PORT", 13100, checks)
    simulator_ui_mode = merged.get("SIMULATOR_UI_MODE", "built").strip().lower()
    if "SNMP_TRAP_PORT" in merged:
        dashboard_trap_port = simulator_trap_port = _as_port(
            merged,
            "SNMP_TRAP_PORT",
            10162,
            checks,
        )
        checks.append(Check("SNMP_TRAP_PORT_ALIGNMENT", "pass", str(dashboard_trap_port)))
    else:
        dashboard_trap_port = 162
        simulator_trap_port = 10162
        checks.append(
            Check(
                "SNMP_TRAP_PORT_ALIGNMENT",
                "fail",
                "SNMP_TRAP_PORT is unset: Dashboard defaults to 162 but Simulator defaults to 10162",
            )
        )

    db_mode = merged.get("DB_MODE", "sqlite").strip().lower()
    if db_mode not in {"sqlite", "postgres"}:
        checks.append(Check("DB_MODE", "fail", f"unsupported mode {db_mode!r}"))
    else:
        checks.append(Check("DB_MODE", "pass", db_mode))

    sqlite_raw = merged.get("SQLITE_PATH", "kvm_test.db")
    sqlite_path = Path(sqlite_raw)
    if not sqlite_path.is_absolute():
        sqlite_path = backend_dir / sqlite_path

    address_mode = merged.get("SIM_ADDRESS_MODE", "port").strip().lower()
    if address_mode not in {"port", "loopback"}:
        checks.append(
            Check(
                "SIM_ADDRESS_MODE",
                "fail",
                f"unsupported mode {address_mode!r}; expected 'port' or 'loopback'",
            )
        )
    else:
        checks.append(Check("SIM_ADDRESS_MODE", "pass", address_mode))

    if simulator_ui_mode not in {"built", "dev"}:
        checks.append(
            Check(
                "SIMULATOR_UI_MODE",
                "fail",
                f"unsupported mode {simulator_ui_mode!r}; expected 'built' or 'dev'",
            )
        )
    elif simulator_ui_mode == "built" and not simulator_ui_built:
        checks.append(
            Check(
                "SIMULATOR_UI_MODE",
                "warn",
                "built mode selected but simulator-ui/dist/index.html is absent; build it before smoke",
            )
        )
    else:
        checks.append(Check("SIMULATOR_UI_MODE", "pass", simulator_ui_mode))

    dashboard_url = merged.get(
        "SIM_DASHBOARD_URL",
        "http://127.0.0.1:8000/api/v1",
    ).rstrip("/")
    parsed_dashboard_url = parse.urlsplit(dashboard_url)
    if not _valid_http_url(dashboard_url):
        checks.append(
            Check(
                "SIM_DASHBOARD_URL",
                "fail",
                f"invalid URL {_safe_url(dashboard_url)!r}",
            )
        )
    elif (
        parsed_dashboard_url.username
        or parsed_dashboard_url.password
        or parsed_dashboard_url.query
        or parsed_dashboard_url.fragment
    ):
        checks.append(
            Check(
                "SIM_DASHBOARD_URL",
                "fail",
                "embedded credentials, query parameters and fragments are forbidden",
            )
        )
    elif not dashboard_url.endswith("/api/v1"):
        checks.append(Check("SIM_DASHBOARD_URL", "warn", "URL should end with /api/v1"))
    else:
        checks.append(Check("SIM_DASHBOARD_URL", "pass", _safe_url(dashboard_url)))

    bridge_enabled = _as_bool(merged.get("SIMULATOR_BRIDGE_ENABLED"), False)
    bridge_token_state = _secret_state(merged.get("SIMULATOR_BRIDGE_TOKEN"))
    if bridge_enabled and bridge_token_state != "configured":
        checks.append(
            Check(
                "SIMULATOR_BRIDGE_TOKEN",
                "fail",
                "Dashboard bridge is enabled but token is missing or a placeholder",
            )
        )
    elif bridge_enabled:
        checks.append(Check("SIMULATOR_BRIDGE_TOKEN", "pass", "configured (value hidden)"))
    else:
        checks.append(Check("SIMULATOR_BRIDGE_ENABLED", "warn", "Dashboard bridge is disabled"))

    dashboard_community = merged.get("SNMP_DEFAULT_COMMUNITY", "public")
    simulator_community = merged.get("SNMP_COMMUNITY", "public")
    checks.append(
        Check(
            "SNMP_COMMUNITY_ALIGNMENT",
            "pass" if dashboard_community == simulator_community else "fail",
            "Dashboard SNMP_DEFAULT_COMMUNITY and Simulator SNMP_COMMUNITY "
            + ("match (values hidden)" if dashboard_community == simulator_community else "do not match"),
        )
    )

    topology = merged.get("SIM_TOPOLOGY", merged.get("SIM_SCENARIO", "ccdc-regression"))
    if topology not in _PRESET_PORT_BINDINGS:
        checks.append(
            Check(
                "SIM_TOPOLOGY",
                "warn",
                f"{topology!r} is custom; pass --expected-agents during smoke verification",
            )
        )
    else:
        checks.append(Check("SIM_TOPOLOGY", "pass", topology))

    if merged.get("SIM_SNMP_PORT_BASE") and topology in _PRESET_PORT_BINDINGS:
        checks.append(
            Check(
                "SIM_SNMP_PORT_BASE",
                "warn",
                "built-in presets currently keep explicit ports 11161..11165; this value does not remap them",
            )
        )

    config = {
        "dashboard": {
            "listen_host": backend_host,
            "listen_port": backend_port,
            "health_url": f"http://{_client_host(backend_host)}:{backend_port}/api/v1/health",
            "db_mode": db_mode,
            "sqlite_path": str(sqlite_path.resolve()),
            "bridge_enabled": bridge_enabled,
            "bridge_token": bridge_token_state,
            "community": _secret_state(
                merged.get("SNMP_DEFAULT_COMMUNITY"),
                default_is_secret=True,
            ),
            "trap_listen_host": "0.0.0.0",
            "trap_listen_port": dashboard_trap_port,
        },
        "dashboard_ui": {
            "listen_host": dashboard_ui_host,
            "listen_port": dashboard_ui_port,
            "backend_target": merged.get(
                "VITE_BACKEND_TARGET",
                f"http://{_client_host(backend_host)}:{backend_port}",
            ),
        },
        "simulator": {
            "listen_host": simulator_host,
            "listen_port": simulator_port,
            "base_url": f"http://{_client_host(simulator_host)}:{simulator_port}",
            "topology": topology,
            "address_mode": address_mode,
            "dashboard_url": dashboard_url,
            "run_id": merged.get("SIM_RUN_ID", "local-simulator"),
            "bridge_token": bridge_token_state,
            "community": _secret_state(
                merged.get("SNMP_COMMUNITY"),
                default_is_secret=True,
            ),
            "trap_target_host": merged.get("TRAP_TARGET_HOST", "127.0.0.1"),
            "trap_target_port": simulator_trap_port,
        },
        "simulator_ui": {
            "mode": simulator_ui_mode,
            "listen_host": simulator_ui_host,
            "listen_port": simulator_ui_port,
            "simulator_target": merged.get(
                "VITE_SIMULATOR_TARGET",
                f"http://{_client_host(simulator_host)}:{simulator_port}",
            ),
            "dist_path": str(simulator_ui_dist),
            "dist_built": simulator_ui_built,
        },
        "paths": {
            "repo_root": str(root),
            "backend": str(backend_dir),
            "logs": str(backend_dir / "logs"),
            "env_file": str(env_file.resolve()) if env_file and env_file.exists() else None,
        },
    }
    return config, checks


def _client_host(host: str) -> str:
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def _binding_is_free(host: str, port: int, kind: int) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, kind)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((host, port))
        if kind == socket.SOCK_STREAM:
            sock.listen(1)
        return True, "available"
    except OSError as exc:
        return False, f"unavailable: {exc}"
    finally:
        sock.close()


def _preset_agent_bindings(config: dict) -> list[tuple[str, int]]:
    simulator = config["simulator"]
    topology = simulator["topology"]
    ports = _PRESET_PORT_BINDINGS.get(topology, [])
    if simulator["address_mode"] == "loopback":
        return [(f"127.0.1.{index}", 161) for index in range(1, len(ports) + 1)]
    return [("127.0.0.1", port) for port in ports]


def port_checks(config: dict, component: str) -> list[Check]:
    candidates: list[tuple[str, str, int, int]] = []
    checks: list[Check] = []
    if component in {"all", "dashboard"}:
        dashboard = config["dashboard"]
        candidates.extend(
            [
                (
                    "dashboard.http",
                    dashboard["listen_host"],
                    dashboard["listen_port"],
                    socket.SOCK_STREAM,
                ),
                (
                    "dashboard.trap",
                    dashboard["trap_listen_host"],
                    dashboard["trap_listen_port"],
                    socket.SOCK_DGRAM,
                ),
            ]
        )
    if component in {"all", "dashboard-ui"}:
        ui = config["dashboard_ui"]
        candidates.append(("dashboard-ui.http", ui["listen_host"], ui["listen_port"], socket.SOCK_STREAM))
    if component in {"all", "simulator"}:
        simulator = config["simulator"]
        candidates.append(
            (
                "simulator.http",
                simulator["listen_host"],
                simulator["listen_port"],
                socket.SOCK_STREAM,
            )
        )
        candidates.extend(
            (f"simulator.snmp[{index}]", host, port, socket.SOCK_DGRAM)
            for index, (host, port) in enumerate(_preset_agent_bindings(config), start=1)
        )
    if (
        component == "simulator-ui"
        or (component == "all" and config["simulator_ui"]["mode"] == "dev")
    ):
        ui = config["simulator_ui"]
        if ui["mode"] == "dev":
            candidates.append(("simulator-ui.http", ui["listen_host"], ui["listen_port"], socket.SOCK_STREAM))
        else:
            checks.append(
                Check(
                    "simulator-ui.http",
                    "warn",
                    "built mode is served by simulator.http; no separate UI listener is planned",
                )
            )

    seen: set[tuple[str, int, int]] = set()
    for name, host, port, kind in candidates:
        binding = (host, port, kind)
        if binding in seen:
            checks.append(Check(name, "fail", f"duplicate planned binding {host}:{port}"))
            continue
        seen.add(binding)
        free, detail = _binding_is_free(host, port, kind)
        protocol = "tcp" if kind == socket.SOCK_STREAM else "udp"
        checks.append(Check(name, "pass" if free else "fail", f"{protocol}://{host}:{port} {detail}"))
    return checks


def _http_json(url: str, timeout: float) -> object:
    req = request.Request(url, headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc)) from exc


def _post_json(url: str, timeout: float) -> object:
    req = request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(str(exc)) from exc


def _fetch_check(
    checks: list[Check],
    name: str,
    url: str,
    timeout: float,
    fetch_json: Callable[[str, float], object],
) -> object | None:
    public_url = _safe_url(url)
    try:
        payload = fetch_json(url, timeout)
    except Exception as exc:
        public_error = str(exc).replace(url, public_url)
        checks.append(Check(name, "fail", f"{public_url}: {public_error}"))
        return None
    checks.append(Check(name, "pass", public_url))
    return payload


def smoke_checks(
    config: dict,
    *,
    expected_topology: str,
    expected_agents: int | None,
    require_bridge: bool,
    require_ui: bool,
    timeout: float,
    fetch_json: Callable[[str, float], object] = _http_json,
    post_json: Callable[[str, float], object] = _post_json,
) -> list[Check]:
    checks: list[Check] = []
    dashboard_url = config["simulator"]["dashboard_url"]
    dashboard_root = dashboard_url.removesuffix("/api/v1")
    simulator_root = config["simulator"]["base_url"]

    simple_health = _fetch_check(
        checks,
        "dashboard.health",
        f"{dashboard_root}/health",
        timeout,
        fetch_json,
    )
    if isinstance(simple_health, dict) and simple_health.get("status") != "ok":
        checks.append(Check("dashboard.health.status", "fail", repr(simple_health.get("status"))))

    detailed_health = _fetch_check(
        checks,
        "dashboard.health_detailed",
        f"{dashboard_root}/api/v1/health",
        timeout,
        fetch_json,
    )
    if isinstance(detailed_health, dict):
        checks.append(
            Check(
                "dashboard.database",
                "pass" if detailed_health.get("database") == "connected" else "fail",
                str(detailed_health.get("database")),
            )
        )
        checks.append(
            Check(
                "dashboard.scheduler",
                "pass" if detailed_health.get("scheduler") is True else "fail",
                str(detailed_health.get("scheduler")),
            )
        )
        trap_receiver = detailed_health.get("trap_receiver")
        trap_running = (
            isinstance(trap_receiver, dict)
            and trap_receiver.get("state") == "running"
        )
        trap_port = (
            trap_receiver.get("listen_port")
            if isinstance(trap_receiver, dict)
            else None
        )
        expected_trap_port = config["dashboard"]["trap_listen_port"]
        checks.append(
            Check(
                "dashboard.trap_receiver",
                "pass"
                if trap_running and trap_port == expected_trap_port
                else "fail",
                "expected_running=True "
                f"expected_port={expected_trap_port} "
                f"actual_state={trap_receiver.get('state') if isinstance(trap_receiver, dict) else None!r} "
                f"actual_port={trap_port}",
            )
        )

    if require_bridge:
        _fetch_check(
            checks,
            "simulator.bridge_reconcile",
            f"{simulator_root}/api/v1/bridge/reconcile",
            timeout,
            post_json,
        )

    status = _fetch_check(
        checks,
        "simulator.status",
        f"{simulator_root}/api/v1/status",
        timeout,
        fetch_json,
    )
    topologies = _fetch_check(
        checks,
        "simulator.topologies",
        f"{simulator_root}/api/v1/topologies",
        timeout,
        fetch_json,
    )
    state = _fetch_check(
        checks,
        "simulator.state",
        f"{simulator_root}/api/v1/state",
        timeout,
        fetch_json,
    )

    topology_ids = {
        item.get("id")
        for item in topologies
        if isinstance(topologies, list) and isinstance(item, dict)
    } if isinstance(topologies, list) else set()
    checks.append(
        Check(
            "simulator.expected_topology_available",
            "pass" if expected_topology in topology_ids else "fail",
            expected_topology,
        )
    )

    actual_topology = None
    state_devices: list = []
    if isinstance(state, dict):
        scenario = state.get("scenario")
        if isinstance(scenario, dict):
            actual_topology = scenario.get("id")
            if isinstance(scenario.get("devices"), list):
                state_devices = scenario["devices"]
    checks.append(
        Check(
            "simulator.active_topology",
            "pass" if actual_topology == expected_topology else "fail",
            f"expected={expected_topology!r} actual={actual_topology!r}",
        )
    )

    if expected_agents is None:
        expected_agents = len(_PRESET_PORT_BINDINGS.get(expected_topology, [])) or None
    if expected_agents is None:
        checks.append(
            Check(
                "simulator.agent_count",
                "warn",
                "custom topology requires --expected-agents for an exact assertion",
            )
        )
    else:
        running_agents = None
        expected_from_status = None
        if isinstance(status, dict) and isinstance(status.get("agents"), dict):
            running_agents = status["agents"].get("running")
            expected_from_status = status["agents"].get("expected")
            agent_bindings = status["agents"].get("bindings")
        else:
            agent_bindings = None
        state_bindings = {
            (
                item.get("id"),
                item.get("host", "127.0.0.1"),
                item.get("snmp_port"),
            )
            for item in state_devices
            if isinstance(item, dict)
        }
        status_bindings = {
            (item.get("device_id"), item.get("host"), item.get("port"))
            for item in agent_bindings
            if isinstance(agent_bindings, list) and isinstance(item, dict)
        } if isinstance(agent_bindings, list) else set()
        healthy_binding_count = sum(
            1
            for item in agent_bindings or []
            if (
                isinstance(item, dict)
                and item.get("thread_alive") is True
                and item.get("ready") is True
                and item.get("error_type") is None
            )
        )
        checks.extend(
            [
                Check(
                    "simulator.state_device_count",
                    "pass" if len(state_devices) == expected_agents else "fail",
                    f"expected={expected_agents} actual={len(state_devices)}",
                ),
                Check(
                    "simulator.agent_count",
                    "pass"
                    if running_agents == expected_agents and expected_from_status == expected_agents
                    else "fail",
                    f"expected={expected_agents} running={running_agents} status_expected={expected_from_status}",
                ),
                Check(
                    "simulator.agent_bindings",
                    "pass"
                    if (
                        healthy_binding_count == expected_agents
                        and status_bindings == state_bindings
                    )
                    else "fail",
                    f"expected={expected_agents} healthy={healthy_binding_count} "
                    f"status_matches_state={status_bindings == state_bindings}",
                ),
            ]
        )

    bridge_status = status.get("bridge") if isinstance(status, dict) else None
    if isinstance(bridge_status, dict):
        bridge_enabled = bridge_status.get("enabled") is True
        last_result = bridge_status.get("last_reconcile")
        bridge_ok = isinstance(last_result, dict) and last_result.get("ok") is True
        if require_bridge:
            checks.append(
                Check(
                    "simulator.bridge",
                    "pass" if bridge_enabled and bridge_ok else "fail",
                    f"enabled={bridge_enabled} last_ok={bridge_ok} detail={bridge_status.get('detail')!r}",
                )
            )
            if expected_agents is not None:
                binding_count = bridge_status.get("binding_count")
                checks.append(
                    Check(
                        "simulator.bridge_bindings",
                        "pass" if binding_count == expected_agents else "fail",
                        f"expected={expected_agents} actual={binding_count}",
                    )
                )
        elif bridge_enabled and not bridge_ok:
            checks.append(
                Check(
                    "simulator.bridge",
                    "fail",
                    f"bridge is enabled but last reconcile failed: {bridge_status.get('detail')!r}",
                )
            )
        else:
            checks.append(
                Check(
                    "simulator.bridge",
                    "pass" if bridge_ok else "warn",
                    "optional for this smoke run",
                )
            )
    else:
        checks.append(Check("simulator.bridge", "fail", "status payload has no bridge diagnostics"))

    if isinstance(status, dict) and isinstance(status.get("trap"), dict):
        actual_trap_port = status["trap"].get("target_port")
        expected_trap_port = config["dashboard"]["trap_listen_port"]
        checks.append(
            Check(
                "trap.port_alignment",
                "pass" if actual_trap_port == expected_trap_port else "fail",
                f"dashboard={expected_trap_port} simulator_target={actual_trap_port}",
            )
        )
    else:
        checks.append(Check("trap.port_alignment", "fail", "simulator status has no Trap target"))

    if require_ui:
        try:
            req = request.Request(f"{simulator_root}/", headers={"Accept": "text/html"})
            with request.urlopen(req, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read(512).decode("utf-8", errors="replace").lower()
            ok = response.status == 200 and "text/html" in content_type and "<html" in body
            checks.append(
                Check(
                    "simulator.ui",
                    "pass" if ok else "fail",
                    f"status={response.status} content_type={content_type!r}",
                )
            )
        except Exception as exc:
            checks.append(Check("simulator.ui", "fail", str(exc)))

    return checks


async def snmp_get_checks(
    config: dict,
    *,
    community: str,
    timeout: float,
    query=None,
) -> list[Check]:
    """Issue a real sysObjectID.0 GET against each resolved preset binding."""

    if query is None:
        from app.snmp.poller import _snmp_get

        query = _snmp_get

    bindings = _preset_agent_bindings(config)
    if not bindings:
        return [
            Check(
                "snmp.sysObjectID",
                "fail",
                "custom topology has no preset bindings to query",
            )
        ]

    checks: list[Check] = []
    for host, port in bindings:
        try:
            returned_oid, value = await query(
                host,
                port,
                community,
                _SYS_OBJECT_ID_OID,
                timeout=timeout,
                retries=0,
            )
        except Exception as exc:
            public_error = f"{type(exc).__name__}: {exc}"
            if community:
                public_error = public_error.replace(community, "<redacted>")
            checks.append(
                Check(
                    f"snmp.sysObjectID[{host}:{port}]",
                    "fail",
                    f"{_SYS_OBJECT_ID_OID}: {public_error}",
                )
            )
            continue
        rendered_value = (
            value.prettyPrint()
            if value is not None and hasattr(value, "prettyPrint")
            else str(value) if value is not None else None
        )
        is_no_value = bool(
            value is not None
            and hasattr(value, "isNoValue")
            and value.isNoValue()
        )
        checks.append(
            Check(
                f"snmp.sysObjectID[{host}:{port}]",
                "pass" if rendered_value and not is_no_value else "fail",
                f"{returned_oid}={rendered_value or '<no-response>'}",
            )
        )
    return checks


def _render_text(config: dict, checks: Iterable[Check]) -> str:
    lines = [
        "KVM simulator L0 resolved configuration (secrets are never printed)",
        json.dumps(config, ensure_ascii=False, indent=2),
        "",
        "Checks:",
    ]
    for item in checks:
        lines.append(f"[{item.status.upper():4}] {item.name}: {item.detail}")
    return "\n".join(lines)


def _exit_code(checks: Iterable[Check]) -> int:
    return 1 if any(item.status == "fail" for item in checks) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KVM simulator L0 environment doctor and smoke verifier")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env") if Path(".env").is_file() else None,
        help="optional dotenv file; process environment always takes precedence",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="validate effective configuration and planned bindings")
    doctor.add_argument(
        "--component",
        choices=["all", "dashboard", "dashboard-ui", "simulator", "simulator-ui"],
        default="all",
    )
    doctor.add_argument(
        "--check-ports",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="require planned listener ports to be free",
    )

    smoke = subparsers.add_parser("smoke", help="verify an already-running Dashboard + Simulator chain")
    smoke.add_argument("--expected-topology", default=None)
    smoke.add_argument("--expected-agents", type=int, default=None)
    smoke.add_argument("--require-bridge", action="store_true")
    smoke.add_argument("--require-ui", action="store_true")
    smoke.add_argument("--timeout", type=float, default=3.0)

    snmp_get = subparsers.add_parser(
        "snmp-get",
        help="GET sysObjectID.0 from every resolved preset Agent binding",
    )
    snmp_get.add_argument("--timeout", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config, checks = resolve_configuration(env_file=args.env_file)
    if args.command == "doctor" and args.check_ports:
        checks.extend(port_checks(config, args.component))
    elif args.command == "smoke":
        checks.extend(
            smoke_checks(
                config,
                expected_topology=args.expected_topology or config["simulator"]["topology"],
                expected_agents=args.expected_agents,
                require_bridge=args.require_bridge,
                require_ui=args.require_ui,
                timeout=args.timeout,
            )
        )
    elif args.command == "snmp-get":
        env_values = _read_env_file(args.env_file)
        env_values.update(_normalise_environment(os.environ))
        checks.extend(
            asyncio.run(
                snmp_get_checks(
                    config,
                    community=env_values.get("SNMP_COMMUNITY", "public"),
                    timeout=args.timeout,
                )
            )
        )

    public_config = _public_configuration(config)
    if args.json:
        print(
            json.dumps(
                {
                    "configuration": public_config,
                    "checks": [item.to_dict() for item in checks],
                    "ok": _exit_code(checks) == 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(_render_text(public_config, checks))
    return _exit_code(checks)


if __name__ == "__main__":
    sys.exit(main())
