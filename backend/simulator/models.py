from __future__ import annotations

from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    profile: ProfileId
    snmp_port: int = Field(ge=1024, le=65535)
    system_oid: str
    evidence: EvidenceStatus
    endpoints: list[ScenarioEndpoint] = []
    ports: list[ScenarioPort] = []
    routes: list[ScenarioRoute] = []

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

    @model_validator(mode="after")
    def validate_devices(self):
        identifiers = {device.id for device in self.devices}
        ports = {device.snmp_port for device in self.devices}
        if len(identifiers) != len(self.devices):
            raise ValueError("device IDs must be unique")
        if len(ports) != len(self.devices):
            raise ValueError("SNMP ports must be unique")
        return self


class EndpointStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OnlineState | None = None
    video_connected: bool | None = None
    display_connected: bool | None = None
    frozen: bool | None = None


class RouteStatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RouteState


class TrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: int = Field(ge=0, le=2147483647)
    message: str = Field(min_length=1, max_length=2048)
    state_backed: bool = False
