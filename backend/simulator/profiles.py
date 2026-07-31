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
    FixtureSpec,
    FixtureTable,
    validate_fixture_schema,
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

    endpoints: dict[int, dict[str, Any]] = {}
    for endpoint in device.get("endpoints", ()):
        if endpoint.get("module_type") != module_type:
            continue
        row = int(endpoint["row"])
        if row in endpoints:
            raise ValueError(
                f"duplicate {module_type} endpoint row {row} for "
                f"{table.canonical_field}"
            )
        endpoints[row] = endpoint
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


def scenario_runtime_fixture(
    device: dict[str, Any],
) -> FixtureSpec:
    """Materialize one validated L3 fixture without inventing any table row.

    CCDM endpoint rows are a deterministic filter over the L2 static fixture.
    Scenario overrides may replace only leaves that already exist after that
    filtering step; they cannot add rows, optional objects, or vendor aliases.
    """

    canonical = normalize_catalog_profile_id(device["profile"])
    profile = get_profile(canonical)
    _exact_system_oid(device, profile.sys_object_id)
    overrides = device.get("profile_state") or {}
    if not isinstance(overrides, dict):
        raise ValueError("profile_state must be an object")
    unknown_roots = set(overrides) - {"scalars", "tables"}
    if unknown_roots:
        raise ValueError(
            f"unknown profile_state roots: {sorted(unknown_roots)}"
        )

    if canonical == "ccdc_legacy":
        if overrides.get("scalars") or overrides.get("tables"):
            raise ValueError(
                "CCDC vendor Profile is empty; legacy values are not "
                "canonical runtime fields"
            )
        fixture = FixtureSpec(
            fixture_id="ccdc-legacy-empty",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            evidence_version=profile.evidence_version,
        )
        return validate_fixture_schema(profile, fixture)

    base = DEFAULT_FIXTURES[canonical]
    tables: list[FixtureTable] = []
    for table in profile.tables:
        rows = _fixture_rows(profile, table, device)
        if rows:
            tables.append(FixtureTable(table_id=table.canonical_field, rows=rows))

    scalar_values = dict(base.scalar_values)
    scalar_overrides = overrides.get("scalars", {})
    if not isinstance(scalar_overrides, dict):
        raise ValueError("profile_state.scalars must be an object")
    for field_id, value in scalar_overrides.items():
        if field_id not in scalar_values:
            raise ValueError(
                f"profile_state scalar {field_id!r} is unknown or disabled"
            )
        scalar_values[field_id] = value

    table_overrides = overrides.get("tables", {})
    if not isinstance(table_overrides, dict):
        raise ValueError("profile_state.tables must be an object")
    table_positions = {item.table_id: index for index, item in enumerate(tables)}
    for table_id, row_overrides in table_overrides.items():
        position = table_positions.get(table_id)
        if position is None:
            raise ValueError(
                f"profile_state table {table_id!r} is unknown or has no "
                "explicit rows"
            )
        if not isinstance(row_overrides, dict):
            raise ValueError(
                f"profile_state table {table_id!r} must be an object"
            )
        table = tables[position]
        row_positions = {
            ",".join(str(value) for _, value in row.indexes): index
            for index, row in enumerate(table.rows)
        }
        rows = list(table.rows)
        for row_key, values in row_overrides.items():
            row_position = row_positions.get(row_key)
            if row_position is None:
                raise ValueError(
                    f"profile_state row {table_id}[{row_key}] is unknown"
                )
            if not isinstance(values, dict):
                raise ValueError(
                    f"profile_state row {table_id}[{row_key}] must be an object"
                )
            row = rows[row_position]
            current_values = dict(row.values)
            for field_id, value in values.items():
                if field_id not in current_values:
                    raise ValueError(
                        f"profile_state column {table_id}[{row_key}]."
                        f"{field_id} is unknown or disabled"
                    )
                current_values[field_id] = value
            rows[row_position] = row.model_copy(
                update={"values": tuple(current_values.items())}
            )
        tables[position] = table.model_copy(update={"rows": tuple(rows)})

    fixture = FixtureSpec(
        fixture_id=base.fixture_id,
        profile_id=base.profile_id,
        profile_version=base.profile_version,
        evidence_version=base.evidence_version,
        enabled_optional_groups=base.enabled_optional_groups,
        scalar_values=tuple(scalar_values.items()),
        tables=tuple(tables),
    )
    return validate_fixture_schema(profile, fixture)


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
    """Render explicit canonical values; supplied runtime state has no fallback."""

    state = profile_state
    canonical = normalize_catalog_profile_id(device["profile"])
    if canonical == "ccdc_legacy":
        rendered = _render_legacy(device, state or {})
    else:
        profile = get_profile(canonical)
        sys_oid = _exact_system_oid(device, profile.sys_object_id)
        if state is None:
            # L2 standalone compatibility: materialize a complete, validated
            # explicit fixture before entering the renderer. ScenarioState
            # always supplies state and never takes this compatibility branch.
            fixture = scenario_runtime_fixture(device)
            state = {
                "scalars": fixture.scalar_map,
                "tables": {
                    table.table_id: {
                        ",".join(str(value) for _, value in row.indexes):
                            row.value_map
                        for row in table.rows
                    }
                    for table in fixture.tables
                },
            }
        rendered = {
            "1.3.6.1.2.1.1.2.0": RenderedValue(
                sys_oid, "object_identifier"
            )
        }
        scalar_state = state.get("scalars", {})
        if not isinstance(scalar_state, dict):
            raise ValueError("runtime scalars must be an object")
        scalar_defs = {
            scalar.canonical_field: scalar for scalar in profile.scalars
        }
        for field_id, value in scalar_state.items():
            scalar = scalar_defs.get(field_id)
            if scalar is None:
                raise ValueError(f"unknown canonical runtime scalar {field_id!r}")
            rendered[scalar.instance_oid] = RenderedValue(
                value, _snmp_type(scalar)
            )
        table_state = state.get("tables", {})
        if not isinstance(table_state, dict):
            raise ValueError("runtime tables must be an object")
        table_defs = {
            table.canonical_field: table for table in profile.tables
        }
        for table_id, rows in table_state.items():
            table = table_defs.get(table_id)
            if table is None:
                raise ValueError(f"unknown canonical runtime table {table_id!r}")
            if not isinstance(rows, dict):
                raise ValueError(f"runtime table {table_id!r} must be an object")
            column_defs = {
                column.canonical_field: column for column in table.columns
            }
            for row_key, current in rows.items():
                try:
                    index_values = tuple(
                        int(part) for part in row_key.split(",")
                    )
                except (AttributeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid canonical runtime row key {row_key!r}"
                    ) from exc
                table.validate_fixture_indexes(index_values)
                if not isinstance(current, dict):
                    raise ValueError(
                        f"runtime row {table_id}[{row_key}] must be an object"
                    )
                for field_id, value in current.items():
                    column = column_defs.get(field_id)
                    if column is None:
                        raise ValueError(
                            f"unknown canonical runtime column "
                            f"{table_id}[{row_key}].{field_id}"
                        )
                    rendered[
                        table.instance_oid(field_id, index_values)
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
    "scenario_runtime_fixture",
]
