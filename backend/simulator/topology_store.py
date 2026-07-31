from __future__ import annotations

import json
import os
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


def _default_host(index: int) -> str:
    return f"127.0.1.{index}" if ADDRESS_MODE == "loopback" else "127.0.0.1"


def _default_port(index: int) -> int:
    return 161 if ADDRESS_MODE == "loopback" else DEFAULT_PORT_BASE + index - 1


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

    def presets(self) -> dict[str, TopologyDefinition]:
        return {key: scenario_to_topology(value) for key, value in built_in_scenarios().items()}

    def list(self) -> list[TopologyDefinition]:
        items = list(self.presets().values())
        for path in sorted(self.directory.glob("*.json")):
            try:
                items.append(TopologyDefinition.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return items

    def get(self, topology_id: str) -> TopologyDefinition:
        if topology_id in self.presets():
            return self.presets()[topology_id]
        path = self._path(topology_id)
        if not path.exists():
            raise HTTPException(404, f"Unknown topology: {topology_id}")
        return TopologyDefinition.model_validate_json(path.read_text(encoding="utf-8"))

    def create(self, topology: TopologyDefinition) -> TopologyDefinition:
        if topology.id in self.presets():
            raise HTTPException(409, "Cannot overwrite a read-only preset topology")
        path = self._path(topology.id)
        if path.exists():
            raise HTTPException(409, f"Topology already exists: {topology.id}")
        topology.read_only = False
        topology.source = "user"
        self._write(path, topology)
        return topology

    def update(self, topology_id: str, topology: TopologyDefinition) -> TopologyDefinition:
        if topology_id in self.presets():
            raise HTTPException(403, "Preset topologies are read-only")
        if topology.id != topology_id:
            raise HTTPException(400, "Topology ID in body must match path")
        path = self._path(topology_id)
        if not path.exists():
            raise HTTPException(404, f"Unknown topology: {topology_id}")
        topology.read_only = False
        topology.source = "user"
        self._write(path, topology)
        return topology

    def delete(self, topology_id: str) -> None:
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
        path.write_text(json.dumps(topology.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
