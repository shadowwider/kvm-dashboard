"""Production loader and pure-schema API for the generated L2 catalog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable

from .profile_model import (
    ColumnDef,
    IndexDef,
    ProfileDef,
    ScalarDef,
    TableDef,
)


CATALOG_PATH = Path(__file__).with_name("catalog") / "l2_profiles.json"
CATALOG_SCHEMA_VERSION = 1

# Transport IDs remain unchanged until the Dashboard-aware layer is migrated.
# L2 schema identity always uses the canonical L1 IDs on the right.
PROFILE_ID_ALIASES = MappingProxyType(
    {
        "ccdc_legacy": "ccdc_legacy",
        "ccdc_legacy_unverified": "ccdc_legacy",
        "ccdm_matrix": "ccdm_matrix",
        "visionxs_cpu": "visionxs_cpu",
        "visionxs_con": "visionxs_con",
        "dp12_mux_atc": "dp12_mux_atc",
        "dp12_mux_atc_readonly": "dp12_mux_atc",
    }
)

ACCEPTED_L1_SHA256 = MappingProxyType(
    {
        "ccdc_legacy": (
            "f8027d3567ac23259718f20a63363be2391599652c2255cf532b603a6d52d858"
        ),
        "ccdm_matrix": (
            "dc2fa2a8ef223348be2a49cf2456094099680a54ad58ee60838294ec042a952d"
        ),
        "visionxs_cpu": (
            "1fa9a8c4ca001cc33ec7c9fe6d7949fe8bb31472f505e028acdbecf1b9d0a08a"
        ),
        "visionxs_con": (
            "d40bcf845ae091ef09071d335187bf8f49393b6226bc46c2be728f5581900b40"
        ),
        "dp12_mux_atc": (
            "8225e8ecc2d86c2a7c85ebd02040d2bdbbdd0e8b998880e25da77a128c1c81cf"
        ),
    }
)


def normalize_catalog_profile_id(profile_id: Any) -> str:
    value = getattr(profile_id, "value", profile_id)
    try:
        return PROFILE_ID_ALIASES[str(value)]
    except KeyError as exc:
        raise KeyError(f"Unknown simulator profile: {profile_id}") from exc


def _load_catalog() -> tuple[dict[str, ProfileDef], str]:
    raw = CATALOG_PATH.read_bytes()
    payload = json.loads(raw)
    if payload.get("catalog_schema_version") != CATALOG_SCHEMA_VERSION:
        raise RuntimeError("Unsupported L2 Profile catalog schema")

    profiles: dict[str, ProfileDef] = {}
    for item in payload.get("profiles", []):
        profile = ProfileDef.model_validate(item)
        accepted = ACCEPTED_L1_SHA256.get(profile.profile_id)
        if accepted is None or profile.source_manifest_sha256 != accepted:
            raise RuntimeError(
                f"Profile {profile.profile_id} is not pinned to the Accepted L1 digest"
            )
        if profile.profile_id in profiles:
            raise RuntimeError(f"Duplicate Profile ID {profile.profile_id}")
        profiles[profile.profile_id] = profile
    if set(profiles) != set(ACCEPTED_L1_SHA256):
        raise RuntimeError("L2 Profile catalog does not contain exactly five profiles")
    return profiles, hashlib.sha256(raw).hexdigest()


_LOADED_PROFILES, CATALOG_SHA256 = _load_catalog()
PROFILE_CATALOG = MappingProxyType(_LOADED_PROFILES)


def runtime_catalog_read_paths() -> tuple[Path, ...]:
    """Declare the only data file read by the production Profile loader."""

    return (CATALOG_PATH.resolve(),)


def get_profile(profile_id: Any, profile_version: str | None = None) -> ProfileDef:
    canonical = normalize_catalog_profile_id(profile_id)
    profile = PROFILE_CATALOG[canonical]
    if profile_version is not None and profile.profile_version != profile_version:
        raise KeyError(
            f"Unknown version {profile_version!r} for Profile {canonical!r}"
        )
    return profile


def iter_object_definitions(profile: ProfileDef) -> Iterable[Any]:
    """Yield immutable definitions in numeric OID order."""

    definitions: list[Any] = list(profile.scalars)
    for table in profile.tables:
        definitions.append(table)
        definitions.extend(index for index in table.indexes if index.defined_here)
        definitions.extend(table.columns)
    return tuple(
        sorted(
            definitions,
            key=lambda item: tuple(int(arc) for arc in item.oid.split(".")),
        )
    )


def _source(item: Any) -> dict[str, Any]:
    return item.source.model_dump(mode="json", exclude_none=True)


def _enum(item: ScalarDef | ColumnDef) -> dict[str, int] | None:
    return item.enum.value_map if item.enum is not None else None


def _range(item: Any) -> dict[str, int] | None:
    if item.value_range is None:
        return None
    return {
        "min": item.value_range.minimum,
        "max": item.value_range.maximum,
    }


def _optional_flag(compliance: str) -> bool | None:
    if compliance == "optional":
        return True
    if compliance == "mandatory":
        return False
    return None


def _leaf_projection(
    item: ScalarDef | ColumnDef,
    *,
    index_order: list[str],
) -> dict[str, Any]:
    scalar = isinstance(item, ScalarDef)
    template = item.instance_oid if scalar else (
        f"{item.oid}."
        + ".".join(f"{{{index}}}" for index in index_order)
    )
    return {
        "name": item.vendor_name,
        "qualified_name": item.qualified_vendor_name,
        "module": item.module,
        "oid": item.oid,
        "kind": item.kind,
        "syntax": item.syntax,
        "max_access": item.max_access,
        "enum": _enum(item),
        "range": _range(item),
        "unit": (
            item.unit.model_dump(mode="json") if item.unit is not None else None
        ),
        "default": None,
        "index_order": index_order,
        "compliance": item.compliance,
        "optional_group": _optional_flag(item.compliance),
        "gettable": True,
        "writable": item.max_access == "read-write",
        "instance_rule": "scalar-zero" if scalar else "index-suffix",
        "get_oid_template": template,
        "source": _source(item),
    }


def _structure_projection(
    *,
    name: str,
    module: str,
    oid: str,
    kind: str,
    index_order: list[str],
    source: dict[str, Any],
    syntax: str | None = None,
    value_range: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "qualified_name": f"{module}::{name}",
        "module": module,
        "oid": oid,
        "kind": kind,
        "syntax": syntax,
        "max_access": "not-accessible",
        "enum": None,
        "range": value_range,
        "unit": None,
        "default": None,
        "index_order": index_order,
        "compliance": "unlisted",
        "optional_group": None,
        "gettable": False,
        "writable": False,
        "instance_rule": "none",
        "get_oid_template": None,
        "source": source,
    }


def project_l1_manifest(profile: ProfileDef | Any) -> dict[str, Any]:
    """Project the typed schema back to all L1 object/table semantics."""

    definition = profile if isinstance(profile, ProfileDef) else get_profile(profile)
    objects: list[dict[str, Any]] = [
        _leaf_projection(scalar, index_order=[]) for scalar in definition.scalars
    ]
    tables: list[dict[str, Any]] = []
    for table in definition.tables:
        index_order = list(table.index_order)
        source = _source(table)
        objects.extend(
            [
                _structure_projection(
                    name=table.vendor_name,
                    module=table.module,
                    oid=table.oid,
                    kind="table",
                    index_order=index_order,
                    source=source,
                ),
                _structure_projection(
                    name=table.entry_vendor_name,
                    module=table.module,
                    oid=table.entry_oid,
                    kind="entry",
                    index_order=index_order,
                    source=source,
                ),
            ]
        )
        for index in table.indexes:
            if not index.defined_here:
                continue
            objects.append(
                _structure_projection(
                    name=index.vendor_name,
                    module=index.module,
                    oid=index.oid,
                    kind="index",
                    index_order=index_order,
                    source=_source(index),
                    syntax=index.syntax,
                    value_range=_range(index),
                )
            )
        objects.extend(
            _leaf_projection(column, index_order=index_order)
            for column in table.columns
        )
        tables.append(
            {
                "name": table.vendor_name,
                "qualified_name": table.qualified_vendor_name,
                "module": table.module,
                "oid": table.oid,
                "entry_name": table.entry_vendor_name,
                "entry_oid": table.entry_oid,
                "index_order": index_order,
                "index_ranges": {
                    index.vendor_name: _range(index) for index in table.indexes
                },
                "source": source,
            }
        )
    key = lambda item: tuple(int(arc) for arc in item["oid"].split("."))
    return {
        "profile_id": definition.profile_id,
        "product": definition.product,
        "evidence_status": definition.evidence_status,
        "sys_object_id": definition.sys_object_id,
        "source_manifest": definition.source_manifest,
        "source_manifest_sha256": definition.source_manifest_sha256,
        "tables": sorted(tables, key=key),
        "objects": sorted(objects, key=key),
    }


def profile_schema_metadata(profile: ProfileDef | Any) -> dict[str, Any]:
    definition = profile if isinstance(profile, ProfileDef) else get_profile(profile)
    return definition.schema_metadata()


__all__ = [
    "ACCEPTED_L1_SHA256",
    "CATALOG_PATH",
    "CATALOG_SCHEMA_VERSION",
    "CATALOG_SHA256",
    "PROFILE_CATALOG",
    "PROFILE_ID_ALIASES",
    "get_profile",
    "iter_object_definitions",
    "normalize_catalog_profile_id",
    "profile_schema_metadata",
    "project_l1_manifest",
    "runtime_catalog_read_paths",
]
