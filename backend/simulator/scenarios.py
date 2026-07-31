import os

from .models import (
    AddressMode,
    EvidenceStatus,
    OnlineState,
    ProfileId,
    ScenarioDefinition,
    ScenarioDevice,
    ScenarioEndpoint,
    ScenarioPort,
    ScenarioRoute,
)
from .profiles import PROFILE_DEFINITIONS


def address_mode() -> AddressMode:
    raw_mode = os.environ.get("SIM_ADDRESS_MODE", AddressMode.PORT.value).strip().lower()
    try:
        return AddressMode(raw_mode)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in AddressMode)
        raise ValueError(f"Unsupported SIM_ADDRESS_MODE={raw_mode!r}; expected one of: {allowed}") from exc


def normalize_device_addresses(devices: list[ScenarioDevice], mode: AddressMode | str | None = None) -> list[ScenarioDevice]:
    selected_mode = AddressMode(mode or address_mode())
    normalized: list[ScenarioDevice] = []
    for index, device in enumerate(devices, start=1):
        if selected_mode == AddressMode.LOOPBACK:
            normalized.append(device.model_copy(update={"host": f"127.0.1.{index}", "snmp_port": 161}))
        else:
            normalized.append(device.model_copy(update={"host": device.host or "127.0.0.1"}))
    return normalized


def _device(profile: ProfileId, device_id: str, name: str, port: int, endpoints=None, ports=None, routes=None):
    spec = PROFILE_DEFINITIONS[profile]
    return ScenarioDevice(
        id=device_id,
        name=name,
        profile=profile,
        host="127.0.0.1",
        snmp_port=port,
        system_oid=spec["system_oid"],
        evidence=spec["evidence"],
        endpoints=endpoints or [],
        ports=ports or [],
        routes=routes or [],
    )


def built_in_scenarios() -> dict[str, ScenarioDefinition]:
    legacy_endpoints = [
        ScenarioEndpoint(id="CPU-1-001", module_type="cpu", row=1, port_index=1),
        ScenarioEndpoint(id="CPU-1-002", module_type="cpu", row=2, port_index=2),
        ScenarioEndpoint(id="CON-1-001", module_type="con", row=1, port_index=13),
        ScenarioEndpoint(id="CON-1-002", module_type="con", row=2, port_index=14),
    ]
    legacy = _device(
        ProfileId.CCDC_LEGACY,
        "sim-ccdc-01",
        "SIM / Legacy CCDC Matrix",
        11161,
        endpoints=legacy_endpoints,
        ports=[ScenarioPort(index=index) for index in (1, 2, 13, 14)],
        routes=[
            ScenarioRoute(id="route-1", source_endpoint_id="CPU-1-001", target_endpoint_id="CON-1-001"),
            ScenarioRoute(id="route-2", source_endpoint_id="CPU-1-002", target_endpoint_id="CON-1-002"),
        ],
    )
    ccdm = _device(
        ProfileId.CCDM_MATRIX,
        "sim-ccdm-01",
        "SIM / CCDM Matrix",
        11162,
        endpoints=[
            ScenarioEndpoint(id="CPU-CCDM-001", module_type="cpu", row=1, port_index=1),
            ScenarioEndpoint(id="CON-CCDM-001", module_type="con", row=1, port_index=25),
        ],
        ports=[ScenarioPort(index=1), ScenarioPort(index=25)],
        routes=[ScenarioRoute(id="ccdm-route-1", source_endpoint_id="CPU-CCDM-001", target_endpoint_id="CON-CCDM-001")],
    )
    vision_cpu = _device(ProfileId.VISIONXS_CPU, "sim-vision-cpu-01", "SIM / VisionXS CPU", 11163)
    vision_con = _device(ProfileId.VISIONXS_CON, "sim-vision-con-01", "SIM / VisionXS CON", 11164)
    dp = _device(ProfileId.DP12_MUX, "sim-dp12-01", "SIM / DP12 MUX", 11165)
    scenarios = {
        "ccdc-regression": ("Legacy dashboard regression", [legacy]),
        "ccdm-matrix-basic": ("Vendor-backed CCDM matrix fixture", [ccdm]),
        "visionxs-pair": ("Vendor-backed VisionXS CPU/CON fixtures", [vision_cpu, vision_con]),
        "dp12-readonly": ("Vendor-backed DP12 read-only fixture", [dp]),
        "all-profiles": ("All profile fixtures", [legacy, ccdm, vision_cpu, vision_con, dp]),
    }
    return {
        scenario_id: ScenarioDefinition(
            id=scenario_id,
            title=title,
            devices=normalize_device_addresses(devices),
        )
        for scenario_id, (title, devices) in scenarios.items()
    }
