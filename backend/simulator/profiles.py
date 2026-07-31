from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.snmp.oid_map import CON_COLUMNS, DEVICE_OIDS, ENDPOINT_COLUMNS, PORT_COLUMNS

from .models import EvidenceStatus, ProfileId
from .profile_catalog import (
    PROFILE_CATALOG,
    PROFILE_ID_ALIASES,
    get_profile,
    normalize_catalog_profile_id,
    profile_schema_metadata,
)
from .profile_fixture import (
    DEFAULT_FIXTURES,
    FixtureRow,
)
from .profile_model import ColumnDef, ProfileDef, ScalarDef, TableDef


FORMAL_TRAP = {
    "notification_oid": "1.3.6.1.4.1.32828.2.1.0.4",
    "level_oid": "1.3.6.1.4.1.32828.2.1.0.2",
    "message_oid": "1.3.6.1.4.1.32828.2.1.0.3",
}

# L4 owns correction of the historical notification OID.  L2 preserves the
# transport constant while keeping it outside all vendor Profile definitions.
LEGACY_TRAP = {
    "notification_oid": "1.3.6.1.4.1.32828.5.1.0.4",
    "level_oid": "1.3.6.1.4.1.32828.5.1.0.2",
    "message_oid": "1.3.6.1.4.1.32828.5.1.0.3",
}


@dataclass(frozen=True)
class RenderedValue:
    value: Any
    snmp_type: str = "auto"


# Existing API/Bridge transport values are intentionally retained until L6/L7.
PROFILE_ALIASES = {
    "ccdc_legacy": ProfileId.CCDC_LEGACY.value,
    "ccdc_legacy_unverified": ProfileId.CCDC_LEGACY.value,
    "dp12_mux_atc": ProfileId.DP12_MUX.value,
    "dp12_mux_atc_readonly": ProfileId.DP12_MUX.value,
}


def normalize_profile_id(profile: str | ProfileId) -> str:
    value = profile.value if isinstance(profile, ProfileId) else str(profile)
    canonical = normalize_catalog_profile_id(value)
    if canonical == "ccdc_legacy":
        return ProfileId.CCDC_LEGACY.value
    if canonical == "dp12_mux_atc":
        return ProfileId.DP12_MUX.value
    return canonical


def _snmp_type(item: ScalarDef | ColumnDef) -> str:
    if item.enum is not None or item.syntax in {
        "Integer",
        "Integer32",
        "Unsigned32",
        "Gauge32",
        "Counter32",
        "Counter64",
        "TimeTicks",
    }:
        return "integer"
    if item.syntax == "OBJECT IDENTIFIER":
        return "object_identifier"
    return "string"


def _compat_leaf(item: ScalarDef | ColumnDef) -> dict[str, Any]:
    result = {
        "name": item.canonical_field,
        "vendor_name": item.vendor_name,
        "qualified_vendor_name": item.qualified_vendor_name,
        "oid": item.instance_oid if isinstance(item, ScalarDef) else item.oid,
        "type": _snmp_type(item),
        "default": None,
        "mutable": True,
        "syntax": item.syntax,
        "max_access": item.max_access,
        "enum": item.enum.value_map if item.enum is not None else None,
        "range": (
            {
                "min": item.value_range.minimum,
                "max": item.value_range.maximum,
            }
            if item.value_range is not None
            else None
        ),
        "unit": item.unit.value if item.unit is not None else None,
        "compliance": item.compliance,
        "optional_group": item.optional_group,
    }
    if isinstance(item, ColumnDef):
        result["column"] = item.column
    if item.max_access == "read-write":
        result["snmp_access"] = "read-write-disabled"
    return result


def _compat_profile(profile: ProfileDef) -> dict[str, Any]:
    tables = [
        {
            "name": table.canonical_field,
            "vendor_name": table.vendor_name,
            "qualified_vendor_name": table.qualified_vendor_name,
            "base_oid": table.entry_oid,
            "indexes": [
                {
                    "name": index.canonical_field,
                    "vendor_name": index.vendor_name,
                    "position": index.position,
                    "range": (
                        {
                            "min": index.value_range.minimum,
                            "max": index.value_range.maximum,
                        }
                        if index.value_range is not None
                        else None
                    ),
                }
                for index in table.indexes
            ],
            "columns": [_compat_leaf(column) for column in table.columns],
            "row_source": "fixture-explicit",
        }
        for table in profile.tables
    ]
    transport_aliases = [
        alias
        for alias, canonical in PROFILE_ID_ALIASES.items()
        if canonical == profile.profile_id and alias != profile.profile_id
    ]
    return {
        "system_oid": profile.sys_object_id,
        "canonical_profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "evidence_version": profile.evidence_version,
        "display_name": profile.product,
        "aliases": transport_aliases,
        "evidence": (
            EvidenceStatus.LEGACY_COMPATIBILITY
            if profile.evidence_status == "legacy-unverified"
            else EvidenceStatus.VENDOR_BACKED
        ),
        "description": (
            "Typed L2 Profile generated from the Accepted L1 local curated "
            "device dictionary snapshot."
        ),
        "scalars": [_compat_leaf(item) for item in profile.scalars],
        "tables": tables,
    }


def _legacy_scalar_default(field: str) -> Any:
    values = {
        "device_id": "SIM-CCDC-01",
        "device_class": "0x0000CCDC",
        "device_type": "SIM / Legacy CCDC Matrix",
        "device_serial": "SIM-CCDC-0001",
        "device_mac0": "02:00:00:00:01:00",
        "device_mac1": "02:00:00:00:01:01",
        "device_firmware": "SIM-2026.07",
        "main_power": 1,
        "redundant_power": 1,
        "temperature": "42.0",
        "power_current": "1.2",
        "power_voltage": "12.0",
        "fan1": 3200,
        "fan2": 3150,
        "fan3": 3100,
        "fan4": 3050,
        "fan5": 3000,
        "fan6": 2950,
        "net_if0": 1,
        "net_if1": 1,
    }
    return values[field]


def _legacy_column(field: str, column: int) -> dict[str, Any]:
    is_string = any(
        token in field
        for token in ("_id", "_class", "_name", "temperature", "sfp_type", "display_type")
    )
    return {
        "name": field,
        "vendor_name": None,
        "column": column,
        "type": "string" if is_string else "integer",
        "default": None,
        "mutable": True,
    }


PROJECT_LEGACY_COMPATIBILITY_ADAPTER = MappingProxyType(
    {
        "adapter_id": "project-legacy-compatibility",
        "profile_id": "ccdc_legacy",
        "transport_profile_id": ProfileId.CCDC_LEGACY.value,
        "evidence_status": "project-legacy-compatibility",
        "vendor_object_count": 0,
        "system_oid": PROFILE_CATALOG["ccdc_legacy"].sys_object_id,
        "scalars": tuple(
            {
                "name": name,
                "vendor_name": None,
                "oid": oid,
                "type": (
                    "integer"
                    if name
                    in {
                        "main_power",
                        "redundant_power",
                        "fan1",
                        "fan2",
                        "fan3",
                        "fan4",
                        "fan5",
                        "fan6",
                        "net_if0",
                        "net_if1",
                    }
                    else "string"
                ),
                "default": None,
                "mutable": True,
            }
            for name, oid in DEVICE_OIDS.items()
        ),
        "tables": (
            {
                "name": "cpu_modules",
                "base_oid": "{sys_oid}.1.2.2.3.1000.1",
                "row_source": "endpoints:cpu",
                "columns": tuple(
                    _legacy_column(name, column)
                    for name, column in ENDPOINT_COLUMNS.items()
                ),
            },
            {
                "name": "con_modules",
                "base_oid": "{sys_oid}.1.1.2.3.1000.1",
                "row_source": "endpoints:con",
                "columns": tuple(
                    _legacy_column(name, column)
                    for name, column in CON_COLUMNS.items()
                ),
            },
            {
                "name": "port_table",
                "base_oid": "{sys_oid}.2.3.1000.1",
                "row_source": "ports",
                "columns": tuple(
                    _legacy_column(name, column)
                    for name, column in PORT_COLUMNS.items()
                ),
            },
        ),
    }
)


PROFILE_DEFINITIONS = {
    ProfileId.CCDC_LEGACY: {
        "system_oid": PROJECT_LEGACY_COMPATIBILITY_ADAPTER["system_oid"],
        "canonical_profile_id": "ccdc_legacy",
        "profile_version": PROFILE_CATALOG["ccdc_legacy"].profile_version,
        "evidence_version": PROFILE_CATALOG["ccdc_legacy"].evidence_version,
        "display_name": "CCDC legacy",
        "aliases": ["ccdc_legacy"],
        "evidence": EvidenceStatus.LEGACY_COMPATIBILITY,
        "description": (
            "Explicit project legacy compatibility adapter; not a vendor "
            "CCDC object schema."
        ),
        "adapter_id": "project-legacy-compatibility",
        "scalars": list(PROJECT_LEGACY_COMPATIBILITY_ADAPTER["scalars"]),
        "tables": list(PROJECT_LEGACY_COMPATIBILITY_ADAPTER["tables"]),
    },
    ProfileId.CCDM_MATRIX: _compat_profile(PROFILE_CATALOG["ccdm_matrix"]),
    ProfileId.VISIONXS_CPU: _compat_profile(PROFILE_CATALOG["visionxs_cpu"]),
    ProfileId.VISIONXS_CON: _compat_profile(PROFILE_CATALOG["visionxs_con"]),
    ProfileId.DP12_MUX: _compat_profile(PROFILE_CATALOG["dp12_mux_atc"]),
}


_ENDPOINT_TABLES = {
    ("ccdm_matrix", "user_module_table"): "con",
    ("ccdm_matrix", "target_module_table"): "cpu",
}


def profile_definition(profile: str | ProfileId) -> dict[str, Any]:
    normalized = normalize_profile_id(profile)
    return PROFILE_DEFINITIONS[ProfileId(normalized)]


def _exact_system_oid(device: dict[str, Any], expected: str) -> str:
    configured = device.get("system_oid")
    if configured is not None and configured != expected:
        raise ValueError(
            f"device system_oid {configured!r} does not match exact Profile "
            f"sysObjectID {expected!r}"
        )
    return expected


def _fixture_rows(
    profile: ProfileDef,
    table: TableDef,
    device: dict[str, Any],
) -> tuple[FixtureRow, ...]:
    rows = DEFAULT_FIXTURES[profile.profile_id].table_map.get(
        table.canonical_field, ()
    )
    module_type = _ENDPOINT_TABLES.get(
        (profile.profile_id, table.canonical_field)
    )
    if module_type is None:
        return rows

    endpoints = {
        int(endpoint["row"]): endpoint
        for endpoint in device.get("endpoints", ())
        if endpoint.get("module_type") == module_type
    }
    selected: list[FixtureRow] = []
    for row in rows:
        index_value = row.indexes[0][1]
        endpoint = endpoints.get(index_value)
        if endpoint is None:
            continue
        values = row.value_map
        values.update(
            {
                "id": endpoint.get("id"),
                "name": endpoint.get("display_name") or endpoint.get("id"),
                "device_status": int(endpoint.get("status", 1)),
            }
        )
        selected.append(row.model_copy(update={"values": tuple(values.items())}))
    return tuple(selected)


def default_row_provenance(profile: str | ProfileId) -> dict[str, str]:
    """Describe default row sources without instantiating any index range."""

    canonical = normalize_catalog_profile_id(profile)
    if canonical == "ccdc_legacy":
        return {
            table["name"]: "project-legacy-scenario-entities"
            for table in PROJECT_LEGACY_COMPATIBILITY_ADAPTER["tables"]
        }
    fixture_tables = DEFAULT_FIXTURES[canonical].table_map
    return {
        table.canonical_field: (
            "explicit-static-fixture-filtered-by-scenario-endpoint"
            if (canonical, table.canonical_field) in _ENDPOINT_TABLES
            else "explicit-static-fixture"
            if table.canonical_field in fixture_tables
            else "no-default-rows"
        )
        for table in get_profile(canonical).tables
    }


def _legacy_row_value(
    field: str,
    device: dict[str, Any],
    row: dict[str, Any],
) -> Any:
    index = int(row.get("row", row.get("index", 1)))
    status = row.get("status", 1)
    if isinstance(status, str):
        status = {
            "offline": 0,
            "online": 1,
            "ready": 2,
            "noModule": 0,
            "moduleDeactivated": 1,
            "down": 2,
            "up": 3,
        }.get(status, 1)
    special = {
        "ep_port": row.get("port_index", index),
        "con_port": row.get("port_index", index),
        "ep_id": row.get("id", f"CPU-{index}"),
        "con_id": row.get("id", f"CON-{index}"),
        "ep_name": row.get("display_name") or row.get("id", f"CPU-{index}"),
        "con_name": row.get("display_name") or row.get("id", f"CON-{index}"),
        "ep_device_status": int(status),
        "con_device_status": int(status),
        "port_status": int(status),
    }
    if field in special:
        return special[field]
    if any(token in field for token in ("temperature", "sfp_type", "display_type")):
        return "40.0" if "temperature" in field else "SIM"
    if field.endswith(("_id", "_class", "_name")):
        return "SIM"
    if "sfp_tx_power" in field:
        return 500
    if "sfp_rx_power" in field:
        return 480
    if "fan" in field:
        return 3200
    return 1


def _render_legacy(
    device: dict[str, Any],
    profile_state: dict[str, Any],
) -> dict[str, RenderedValue]:
    sys_oid = _exact_system_oid(
        device, PROJECT_LEGACY_COMPATIBILITY_ADAPTER["system_oid"]
    )
    result = {
        "1.3.6.1.2.1.1.2.0": RenderedValue(sys_oid, "object_identifier")
    }
    scalar_state = profile_state.get("scalars", {})
    for field in PROJECT_LEGACY_COMPATIBILITY_ADAPTER["scalars"]:
        name = field["name"]
        value = scalar_state.get(name, _legacy_scalar_default(name))
        result[field["oid"].format(sys_oid=sys_oid)] = RenderedValue(
            value, field["type"]
        )
    table_state = profile_state.get("tables", {})
    for table in PROJECT_LEGACY_COMPATIBILITY_ADAPTER["tables"]:
        if table["row_source"] == "ports":
            rows = list(device.get("ports", ()))
        else:
            module_type = table["row_source"].split(":", 1)[1]
            rows = [
                item
                for item in device.get("endpoints", ())
                if item.get("module_type") == module_type
            ]
        for row in rows:
            suffix = str(row.get("row", row.get("index")))
            row_state = table_state.get(table["name"], {}).get(suffix, {})
            for column in table["columns"]:
                value = row_state.get(
                    column["name"],
                    _legacy_row_value(column["name"], device, row),
                )
                oid = (
                    f"{table['base_oid'].format(sys_oid=sys_oid)}."
                    f"{column['column']}.{suffix}"
                )
                result[oid] = RenderedValue(value, column["type"])
    return result


def render_oid_map(
    device: dict,
    profile_state: dict[str, Any] | None = None,
    include_metadata: bool = False,
) -> dict[str, Any]:
    """Render only explicitly declared fixture rows and values."""

    state = profile_state or {}
    canonical = normalize_catalog_profile_id(device["profile"])
    if canonical == "ccdc_legacy":
        rendered = _render_legacy(device, state)
    else:
        profile = get_profile(canonical)
        sys_oid = _exact_system_oid(device, profile.sys_object_id)
        rendered = {
            "1.3.6.1.2.1.1.2.0": RenderedValue(
                sys_oid, "object_identifier"
            )
        }
        fixture = DEFAULT_FIXTURES[canonical]
        scalar_state = state.get("scalars", {})
        for scalar in profile.scalars:
            if scalar.canonical_field not in fixture.scalar_map:
                continue
            value = scalar_state.get(
                scalar.canonical_field,
                scalar_state.get(
                    scalar.vendor_name,
                    fixture.scalar_map[scalar.canonical_field],
                ),
            )
            rendered[scalar.instance_oid] = RenderedValue(
                value, _snmp_type(scalar)
            )
        table_state = state.get("tables", {})
        for table in profile.tables:
            for row in _fixture_rows(profile, table, device):
                index_values = tuple(value for _, value in row.indexes)
                suffix = ".".join(str(value) for value in index_values)
                current = table_state.get(table.canonical_field, {}).get(
                    suffix, {}
                )
                for column in table.columns:
                    if column.canonical_field not in row.value_map:
                        continue
                    value = current.get(
                        column.canonical_field,
                        current.get(
                            column.vendor_name,
                            row.value_map[column.canonical_field],
                        ),
                    )
                    rendered[
                        table.instance_oid(column.canonical_field, index_values)
                    ] = RenderedValue(value, _snmp_type(column))

    if include_metadata:
        return rendered
    return {oid: item.value for oid, item in rendered.items()}


def profile_metadata() -> dict[str, Any]:
    """Return schema metadata only; fixture rows and runtime paths are excluded."""

    profiles = {
        profile_id: {
            **profile_schema_metadata(profile),
            "display_name": profile.product,
            "transport_aliases": sorted(
                alias
                for alias, canonical in PROFILE_ID_ALIASES.items()
                if canonical == profile_id and alias != profile_id
            ),
        }
        for profile_id, profile in PROFILE_CATALOG.items()
    }
    return {
        "schema_version": 1,
        "profiles": profiles,
        "aliases": dict(PROFILE_ID_ALIASES),
    }


def mutable_field_index(profile: str | ProfileId) -> dict[str, dict[str, Any]]:
    canonical = normalize_catalog_profile_id(profile)
    if canonical == "ccdc_legacy":
        return {
            f"scalars.{item['name']}": item
            for item in PROJECT_LEGACY_COMPATIBILITY_ADAPTER["scalars"]
        }
    definition = get_profile(canonical)
    return {
        f"scalars.{item.canonical_field}": _compat_leaf(item)
        for item in definition.scalars
    }


def expected_oids_for_device(device: dict) -> set[str]:
    return set(render_oid_map(device))


__all__ = [
    "DEFAULT_FIXTURES",
    "FORMAL_TRAP",
    "LEGACY_TRAP",
    "PROFILE_ALIASES",
    "PROFILE_CATALOG",
    "PROFILE_DEFINITIONS",
    "PROJECT_LEGACY_COMPATIBILITY_ADAPTER",
    "RenderedValue",
    "expected_oids_for_device",
    "default_row_provenance",
    "mutable_field_index",
    "normalize_profile_id",
    "profile_definition",
    "profile_metadata",
    "render_oid_map",
]
