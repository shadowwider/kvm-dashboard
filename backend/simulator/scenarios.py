from .models import (
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


def _device(profile: ProfileId, device_id: str, name: str, port: int, endpoints=None, ports=None, routes=None):
    spec = PROFILE_DEFINITIONS[profile]
    return ScenarioDevice(
        id=device_id,
        name=name,
        profile=profile,
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
    return {
        "ccdc-regression": ScenarioDefinition(id="ccdc-regression", title="Legacy dashboard regression", devices=[legacy]),
        "ccdm-matrix-basic": ScenarioDefinition(id="ccdm-matrix-basic", title="Vendor-backed CCDM matrix fixture", devices=[ccdm]),
        "visionxs-pair": ScenarioDefinition(id="visionxs-pair", title="Vendor-backed VisionXS CPU/CON fixtures", devices=[vision_cpu, vision_con]),
        "dp12-readonly": ScenarioDefinition(id="dp12-readonly", title="Vendor-backed DP12 read-only fixture", devices=[dp]),
        "all-profiles": ScenarioDefinition(id="all-profiles", title="All profile fixtures", devices=[legacy, ccdm, vision_cpu, vision_con, dp]),
    }
