from __future__ import annotations

import json
import os
import threading
import uuid
from ipaddress import ip_address
from pathlib import Path

from fastapi import HTTPException

from .models import (
    EvidenceStatus,
    ScenarioDefinition,
    ScenarioDevice,
    TopologyDefinition,
    TopologyDevice,
    TopologyNodePosition,
)
from .profiles import PROFILE_DEFINITIONS
from .scenarios import built_in_scenarios

TOPOLOGY_DIR = Path(__file__).with_name("topologies")
ADDRESS_MODE = os.environ.get("SIM_ADDRESS_MODE", "port").lower()
DEFAULT_PORT_BASE = int(os.environ.get("SIM_SNMP_PORT_BASE", "11161"))


def _host_is_allowed(host: str) -> bool:
    """Default to loopback-only topology bindings to avoid simulator SSRF."""
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        configured = {
            item.strip().lower()
            for item in os.environ.get("SIM_ALLOWED_HOSTS", "").split(",")
            if item.strip()
        }
        return normalized in configured


def validate_topology_hosts(topology: TopologyDefinition) -> None:
    denied = sorted({
        device.host for device in topology.devices
        if device.host and not _host_is_allowed(device.host)
    })
    if denied:
        raise HTTPException(
            422,
            "Topology host is not allowed; use loopback or configure SIM_ALLOWED_HOSTS: "
            + ", ".join(denied),
        )


def _default_host(index: int) -> str:
    return f"127.0.1.{index}" if ADDRESS_MODE == "loopback" else "127.0.0.1"


def _default_port(index: int) -> int:
    return 161 if ADDRESS_MODE == "loopback" else DEFAULT_PORT_BASE + index - 1


def _default_trap_source_host(index: int, host: str) -> str:
    """Keep port-mode SNMP bindings while giving each local Trap a source IP.

    UDP Trap reception has no sender listening-port identity.  `127.0.1.x`
    remains loopback on Windows/Linux, so it is a safe simulator-only source
    address and does not change the device's SNMP polling host or MIB payload.
    """
    if ADDRESS_MODE == "port" and host == "127.0.0.1":
        return f"127.0.1.{index}"
    return host


def scenario_to_topology(scenario: ScenarioDefinition) -> TopologyDefinition:
    devices: list[TopologyDevice] = []
    edges = []
    for index, device in enumerate(scenario.devices, start=1):
        devices.append(TopologyDevice(
            id=device.id,
            name=device.name,
            profile=device.profile,
            host=device.host or _default_host(index),
            snmp_port=device.snmp_port or _default_port(index),
            trap_source_host=device.trap_source_host or _default_trap_source_host(
                index, device.host or _default_host(index)
            ),
            system_oid=device.system_oid,
            evidence=device.evidence,
            endpoints=device.endpoints,
            ports=device.ports,
            routes=device.routes,
            profile_state=device.profile_state,
            position=TopologyNodePosition(x=(index - 1) * 260, y=0),
        ))
        for route in device.routes:
            edges.append({
                "id": f"{device.id}-{route.id}",
                "source": route.source_endpoint_id,
                "target": route.target_endpoint_id,
                "kind": "route",
                "label": route.label,
            })
    return TopologyDefinition(
        id=scenario.id,
        title=scenario.title,
        devices=devices,
        edges=edges,
        read_only=True,
        source="preset",
        description="Compatibility preset converted from a built-in scenario.",
    )


def topology_to_scenario(topology: TopologyDefinition) -> ScenarioDefinition:
    validate_topology_hosts(topology)
    devices: list[ScenarioDevice] = []
    used = set()
    for index, device in enumerate(topology.devices, start=1):
        profile = PROFILE_DEFINITIONS[device.profile]
        host = device.host or _default_host(index)
        port = device.snmp_port or _default_port(index)
        address = (host, port)
        if address in used:
            raise HTTPException(400, f"Duplicate SNMP binding {host}:{port}")
        used.add(address)
        devices.append(ScenarioDevice(
            id=device.id,
            name=device.name,
            profile=device.profile,
            host=host,
            snmp_port=port,
            trap_source_host=device.trap_source_host or _default_trap_source_host(index, host),
            system_oid=device.system_oid or profile["system_oid"],
            evidence=device.evidence or profile["evidence"],
            endpoints=device.endpoints,
            ports=device.ports,
            routes=device.routes,
            profile_state=device.profile_state,
        ))
    return ScenarioDefinition(id=topology.id, title=topology.title, devices=devices, edges=[edge.model_dump(mode="json") for edge in topology.edges])


class TopologyStore:
    def __init__(self, directory: Path = TOPOLOGY_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._invalid_documents: dict[str, str] = {}

    def presets(self) -> dict[str, TopologyDefinition]:
        return {key: scenario_to_topology(value) for key, value in built_in_scenarios().items()}

    def list(self) -> list[TopologyDefinition]:
        with self._lock:
            items = list(self.presets().values())
            self._invalid_documents = {}
            for path in sorted(self.directory.glob("*.json")):
                try:
                    items.append(TopologyDefinition.model_validate_json(path.read_text(encoding="utf-8")))
                except Exception as exc:
                    self._invalid_documents[path.name] = type(exc).__name__
            return items

    def invalid_documents(self) -> dict[str, str]:
        with self._lock:
            # Refresh before reporting, so a corruption is never silently
            # ignored just because no list operation happened first.
            self.list()
            return dict(self._invalid_documents)

    def get(self, topology_id: str) -> TopologyDefinition:
        with self._lock:
            if topology_id in self.presets():
                return self.presets()[topology_id]
            path = self._path(topology_id)
            if not path.exists():
                raise HTTPException(404, f"Unknown topology: {topology_id}")
            try:
                return TopologyDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._invalid_documents[path.name] = type(exc).__name__
                raise HTTPException(500, f"Topology document is invalid: {topology_id}") from exc

    def create(self, topology: TopologyDefinition) -> TopologyDefinition:
        with self._lock:
            validate_topology_hosts(topology)
            if topology.id in self.presets():
                raise HTTPException(409, "Cannot overwrite a read-only preset topology")
            path = self._path(topology.id)
            if path.exists():
                raise HTTPException(409, f"Topology already exists: {topology.id}")
            topology.read_only = False
            topology.source = "user"
            topology.revision = 1
            self._write(path, topology)
            return topology

    def update(self, topology_id: str, topology: TopologyDefinition) -> TopologyDefinition:
        with self._lock:
            validate_topology_hosts(topology)
            if topology_id in self.presets():
                raise HTTPException(403, "Preset topologies are read-only")
            if topology.id != topology_id:
                raise HTTPException(400, "Topology ID in body must match path")
            path = self._path(topology_id)
            if not path.exists():
                raise HTTPException(404, f"Unknown topology: {topology_id}")
            try:
                current = TopologyDefinition.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._invalid_documents[path.name] = type(exc).__name__
                raise HTTPException(500, f"Topology document is invalid: {topology_id}") from exc
            if topology.revision != current.revision:
                raise HTTPException(
                    409,
                    {
                        "code": "revision_conflict",
                        "message": "Topology was changed by another editor; reload before saving",
                        "current_revision": current.revision,
                        "retryable": True,
                    },
                )
            topology.read_only = False
            topology.source = "user"
            topology.revision = current.revision + 1
            self._write(path, topology)
            return topology

    def delete(self, topology_id: str) -> None:
        with self._lock:
            if topology_id in self.presets():
                raise HTTPException(403, "Preset topologies are read-only")
            path = self._path(topology_id)
            if not path.exists():
                raise HTTPException(404, f"Unknown topology: {topology_id}")
            path.unlink()

    def _path(self, topology_id: str) -> Path:
        safe = TopologyDefinition(id=topology_id, title="validation", devices=[]).id
        return self.directory / f"{safe}.json"

    @staticmethod
    def _write(path: Path, topology: TopologyDefinition) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(topology.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
