from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class EvidenceStatus(str, Enum):
    VENDOR_BACKED = "vendor-backed"
    LEGACY_COMPATIBILITY = "legacy-compatibility"


class ProfileId(str, Enum):
    CCDC_LEGACY = "ccdc_legacy_unverified"
    CCDM_MATRIX = "ccdm_matrix"
    VISIONXS_CPU = "visionxs_cpu"
    VISIONXS_CON = "visionxs_con"
    DP12_MUX = "dp12_mux_atc_readonly"


class OnlineState(int, Enum):
    OFFLINE = 0
    ONLINE = 1
    READY = 2


class AddressMode(str, Enum):
    PORT = "port"
    LOOPBACK = "loopback"


class RouteState(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"
    UNKNOWN = "unknown"


class ScenarioEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    module_type: Literal["cpu", "con"]
    row: int = Field(ge=1, le=2000)
    port_index: int = Field(ge=1, le=4096)
    status: OnlineState = OnlineState.ONLINE
    display_name: str | None = None
    video_connected: bool = True
    display_connected: bool = True
    frozen: bool = False


class ScenarioPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=1, le=4096)
    status: Literal["noModule", "moduleDeactivated", "down", "up"] = "up"


class ScenarioRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    source_endpoint_id: str
    target_endpoint_id: str
    state: RouteState = RouteState.ACTIVE
    evidence: Literal["simulation-declared"] = "simulation-declared"
    label: str | None = None


class ScenarioDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("profile", mode="before")
    @classmethod
    def normalize_profile_aliases(cls, value):
        if value == "ccdc_legacy":
            return ProfileId.CCDC_LEGACY
        if value == "dp12_mux_atc":
            return ProfileId.DP12_MUX
        return value

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    profile: ProfileId
    host: str = Field(default="127.0.0.1", min_length=1, max_length=255)
    snmp_port: int = Field(ge=1, le=65535)
    # Port mode shares one SNMP host across devices.  Trap source identity is
    # deliberately separate so passive receivers can still attribute a
    # simulator-generated notification without changing its vendor varbinds.
    trap_source_host: str | None = Field(default=None, min_length=1, max_length=255)
    system_oid: str
    evidence: EvidenceStatus
    endpoints: list[ScenarioEndpoint] = Field(default_factory=list)
    ports: list[ScenarioPort] = Field(default_factory=list)
    routes: list[ScenarioRoute] = Field(default_factory=list)
    profile_state: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_entities(self):
        endpoint_ids = {endpoint.id for endpoint in self.endpoints}
        if len(endpoint_ids) != len(self.endpoints):
            raise ValueError("endpoint IDs must be unique")
        port_indexes = {port.index for port in self.ports}
        if len(port_indexes) != len(self.ports):
            raise ValueError("physical port indexes must be unique")
        for route in self.routes:
            if route.source_endpoint_id not in endpoint_ids or route.target_endpoint_id not in endpoint_ids:
                raise ValueError(f"route {route.id} references an unknown endpoint")
        return self


class ScenarioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    title: str
    devices: list[ScenarioDevice]
    edges: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_devices(self):
        identifiers = {device.id for device in self.devices}
        bindings = {(device.host, device.snmp_port) for device in self.devices}
        if len(identifiers) != len(self.devices):
            raise ValueError("device IDs must be unique")
        if len(bindings) != len(self.devices):
            raise ValueError("SNMP host/port bindings must be unique")
        return self


class TopologyNodePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = 0
    y: float = 0


class TopologyDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("profile", mode="before")
    @classmethod
    def normalize_profile_aliases(cls, value):
        if value == "ccdc_legacy":
            return ProfileId.CCDC_LEGACY
        if value == "dp12_mux_atc":
            return ProfileId.DP12_MUX
        return value

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    profile: ProfileId
    host: str | None = None
    snmp_port: int | None = Field(default=None, ge=1, le=65535)
    trap_source_host: str | None = Field(default=None, min_length=1, max_length=255)
    system_oid: str | None = None
    evidence: EvidenceStatus | None = None
    position: TopologyNodePosition = Field(default_factory=TopologyNodePosition)
    endpoints: list[ScenarioEndpoint] = Field(default_factory=list)
    ports: list[ScenarioPort] = Field(default_factory=list)
    routes: list[ScenarioRoute] = Field(default_factory=list)
    profile_state: dict[str, Any] = Field(default_factory=dict)


class TopologyEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=128)
    kind: Literal["port-link", "route"] = "port-link"
    source_port: int | None = Field(default=None, ge=1, le=4096)
    target_port: int | None = Field(default=None, ge=1, le=4096)
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TopologyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    title: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    devices: list[TopologyDevice]
    edges: list[TopologyEdge] = Field(default_factory=list)
    read_only: bool = False
    source: Literal["preset", "user"] = "user"
    description: str | None = None

    @model_validator(mode="after")
    def validate_topology(self):
        device_ids = {device.id for device in self.devices}
        if len(device_ids) != len(self.devices):
            raise ValueError("device IDs must be unique")
        edge_ids = {edge.id for edge in self.edges}
        if len(edge_ids) != len(self.edges):
            raise ValueError("edge IDs must be unique")
        endpoint_owner: dict[str, str] = {}
        ports_by_device: dict[str, set[int]] = {}
        for device in self.devices:
            for endpoint in device.endpoints:
                if endpoint.id in endpoint_owner:
                    raise ValueError(f"endpoint ID must be globally unique: {endpoint.id}")
                endpoint_owner[endpoint.id] = device.id
            ports_by_device[device.id] = {port.index for port in device.ports}
        occupied_ports: set[tuple[str, int]] = set()
        for edge in self.edges:
            if edge.source == edge.target:
                raise ValueError(f"edge {edge.id} must not be a self-loop")
            if edge.kind == "route":
                if edge.source not in endpoint_owner or edge.target not in endpoint_owner:
                    raise ValueError(f"route edge {edge.id} must connect existing endpoint IDs")
                if edge.source_port is not None or edge.target_port is not None:
                    raise ValueError(f"route edge {edge.id} must not declare physical ports")
            else:
                if edge.source not in device_ids or edge.target not in device_ids:
                    raise ValueError(f"physical edge {edge.id} must connect device IDs")
                if edge.source_port is None or edge.target_port is None:
                    raise ValueError(f"physical edge {edge.id} requires source_port and target_port")
                source = (edge.source, edge.source_port)
                target = (edge.target, edge.target_port)
                if edge.source_port not in ports_by_device[edge.source] or edge.target_port not in ports_by_device[edge.target]:
                    raise ValueError(f"physical edge {edge.id} references a missing fixture port")
                if source in occupied_ports or target in occupied_ports:
                    raise ValueError(f"physical edge {edge.id} reuses an occupied fixture port")
                occupied_ports.update((source, target))
        addresses = [(device.host, device.snmp_port) for device in self.devices if device.host and device.snmp_port]
        if len(set(addresses)) != len(addresses):
            raise ValueError("SNMP host/port bindings must be unique")
        return self


class EndpointStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OnlineState | None = None
    video_connected: StrictBool | None = None
    display_connected: StrictBool | None = None
    frozen: StrictBool | None = None

    @field_validator("status", mode="before")
    @classmethod
    def reject_boolean_status(cls, value):
        if isinstance(value, bool):
            raise ValueError("status must be an OnlineState integer, not boolean")
        return value


class RouteStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RouteState


class RuntimeFieldPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=256)
    value: Any


class RuntimeStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patches: list[RuntimeFieldPatch] = Field(min_length=1, max_length=100)
    emit_trap: bool = False
    expected_revision: int | None = Field(default=None, ge=1)


class RuntimeDeviceAction(str, Enum):
    DISCONNECT = "disconnect"
    PAUSE = "pause"
    POWER_OFF = "power_off"
    RESTORE = "restore"


class RuntimeDeviceActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RuntimeDeviceAction


class TrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=0, le=2147483647)
    message: str = Field(min_length=1, max_length=2048)
    state_backed: bool = False
    device_id: str | None = None
    device_ids: list[str] | None = None
    layout: Literal["formal", "legacy"] = "formal"
    preset: str | None = None
