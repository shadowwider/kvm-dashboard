from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.device import Device
from app.models.device_entity import DeviceEntity
from app.models.endpoint import Endpoint
from kvm_profiles import PROFILE_CATALOG
from kvm_profiles.profile_model import ColumnDef, ProfileDef, ScalarDef, TableDef


GetValue = Callable[..., Awaitable[tuple[str, Any]]]
WalkValues = Callable[..., Awaitable[dict[str, Any]]]

PROFILE_ROLES = {
    "ccdc_legacy": "matrix",
    "ccdm_matrix": "matrix",
    "dp12_mux_atc": "mux",
    "visionxs_con": "independent_con",
    "visionxs_cpu": "independent_cpu",
}

SECTION_ORDER = {
    "identity": 10,
    "health": 20,
    "power": 30,
    "environment": 40,
    "network": 50,
    "modules": 60,
    "video": 70,
    "usb_hid": 80,
    "links": 90,
    "cards_ports": 100,
    "errors": 110,
}

_NUMERIC_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
_FAULT_LABELS = {
    "absent",
    "crossed",
    "deactivated",
    "down",
    "failure",
    "inactive",
    "moduleDeactivated",
    "noModule",
    "notConnected",
    "off",
    "offline",
}


@dataclass
class ProfilePollResult:
    profile: ProfileDef
    scalar_states: dict[str, dict[str, Any]]
    entities: list[dict[str, Any]]
    status: str
    completed_tables: set[str]


def normalize_oid_value(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "asTuple"):
        return ".".join(str(arc) for arc in value.asTuple())
    rendered = str(value).lstrip(".")
    return rendered or None


def identify_profile(system_oid: Any) -> ProfileDef | None:
    normalized = normalize_oid_value(system_oid)
    if normalized is None:
        return None
    return next(
        (
            profile
            for profile in PROFILE_CATALOG.values()
            if profile.sys_object_id == normalized
        ),
        None,
    )


def profile_metadata(profile: ProfileDef) -> dict[str, Any]:
    sections = {
        section_for_field(item.canonical_field)
        for item in profile.scalars
    }
    sections.update(section_for_table(table.canonical_field) for table in profile.tables)
    return {
        "id": profile.profile_id,
        "version": profile.profile_version,
        "evidence_version": profile.evidence_version,
        "product": profile.product,
        "role": PROFILE_ROLES[profile.profile_id],
        "system_oid": profile.sys_object_id,
        "label_key": f"profiles.{profile.profile_id}",
        "section_keys": sorted(sections, key=lambda key: SECTION_ORDER[key]),
    }


def _raw_value(value: Any) -> Any:
    if value is None:
        return None
    if type(value).__name__ in {
        "NoSuchObject",
        "NoSuchInstance",
        "EndOfMibView",
    }:
        return None
    if hasattr(value, "prettyPrint"):
        return value.prettyPrint()
    return value


def _integer_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None


def _enum_label(item: ScalarDef | ColumnDef, raw: Any) -> str | None:
    if item.enum is None:
        return None
    number = _integer_value(raw)
    if number is None:
        return None
    return next(
        (label for label, value in item.enum.values if value == number),
        str(number),
    )


def _keyboard_mouse(label: str, source: str) -> dict[str, Any]:
    return {
        "keyboard": label in {"keyboard", "keyboardMouse"},
        "mouse": label in {"mouse", "keyboardMouse"},
        "source": source,
    }


def _status_for(item: ScalarDef | ColumnDef, value: Any) -> str:
    label = _enum_label(item, value)
    if label in _FAULT_LABELS:
        return "critical" if label in {"failure", "offline"} else "warning"
    if "fan" in item.canonical_field and _integer_value(value) == 0:
        return "critical"
    return "ok"


def normalize_field(
    item: ScalarDef | ColumnDef,
    value: Any,
    *,
    updated_at: datetime,
    supported: bool = True,
    present: bool = True,
    stale: bool = False,
) -> dict[str, Any]:
    raw = _raw_value(value)
    if not supported:
        normalized = None
        status = "unsupported"
        present = False
    elif not present or raw is None:
        normalized = None
        status = "absent"
        present = False
    else:
        enum_label = _enum_label(item, raw)
        if item.syntax == "KeyboardMouseStatus" and enum_label is not None:
            normalized = _keyboard_mouse(enum_label, item.canonical_field)
        elif enum_label is not None:
            normalized = enum_label
        elif item.syntax in {
            "Integer",
            "Integer32",
            "Unsigned32",
            "Gauge32",
            "Counter32",
            "Counter64",
            "TimeTicks",
        }:
            normalized = _integer_value(raw)
        elif item.unit is not None:
            match = _NUMERIC_RE.search(str(raw))
            normalized = float(match.group(0)) if match else str(raw)
            if isinstance(normalized, float) and normalized.is_integer():
                normalized = int(normalized)
        else:
            normalized = str(raw)
        status = _status_for(item, raw)
    if stale and supported and present:
        status = "stale"
    return {
        "key": item.canonical_field,
        "label_key": f"fields.{item.canonical_field}",
        "raw": raw,
        "value": normalized,
        "unit": item.unit.value if item.unit is not None else None,
        "status": status,
        "supported": supported,
        "present": present,
        "stale": stale,
        "updated_at": updated_at.isoformat(),
    }


def section_for_field(field: str) -> str:
    lowered = field.casefold()
    if "error" in lowered:
        return "errors"
    if any(word in lowered for word in ("serial", "device_", "firmware", "ether_address")):
        return "identity"
    if any(word in lowered for word in ("temperature", "fan")):
        return "environment"
    if any(word in lowered for word in ("power", "voltage", "current", "raid", "function")):
        return "power"
    if any(word in lowered for word in ("network", "ether", "sfp", "tx_", "rx_")):
        return "network"
    if any(word in lowered for word in ("usb", "keyboard", "mouse", "ps2", "hid")):
        return "usb_hid"
    if any(word in lowered for word in ("video", "display", "freeze")):
        return "video"
    if any(word in lowered for word in ("link", "channel")):
        return "links"
    return "health"


def section_for_table(table_id: str) -> str:
    lowered = table_id.casefold()
    if any(word in lowered for word in ("card", "port", "gpio")):
        return "cards_ports"
    if any(word in lowered for word in ("fan", "power_supply")):
        return "environment"
    if "video" in lowered:
        return "video"
    if "link" in lowered:
        return "links"
    if any(word in lowered for word in ("cpu", "target", "user_module", "dynamic")):
        return "modules"
    return "health"


def _entity_type(table_id: str) -> str:
    return table_id.removesuffix("_table").removeprefix("gud_").removeprefix("ccdm_")


def _index_suffix(full_oid: str, column_oid: str, count: int) -> tuple[int, ...] | None:
    prefix = f"{column_oid}."
    if not full_oid.startswith(prefix):
        return None
    suffix = full_oid[len(prefix):].split(".")
    if len(suffix) != count:
        return None
    try:
        return tuple(int(value) for value in suffix)
    except ValueError:
        return None


def _entity_key(table: TableDef, indexes: tuple[int, ...]) -> str:
    parts = ",".join(
        f"{definition.canonical_field}={value}"
        for definition, value in zip(table.indexes, indexes)
    )
    return f"{table.canonical_field}:{parts}"


def _entity_label(table: TableDef, indexes: tuple[int, ...], fields: dict[str, dict]) -> str:
    for key in ("name", "id", "fan_name"):
        value = fields.get(key, {}).get("value")
        if value not in (None, ""):
            return str(value)
    suffix = ".".join(str(value) for value in indexes)
    return f"{_entity_type(table.canonical_field).replace('_', ' ').title()} {suffix}"


def _aggregate_status(states: list[dict[str, Any]]) -> str:
    statuses = {state.get("status", "unknown") for state in states}
    for status in ("critical", "offline", "warning", "stale", "unknown"):
        if status in statuses:
            return status
    return "ok"


async def collect_profile_snapshot(
    device: Device,
    profile: ProfileDef,
    get_value: GetValue,
    walk_values: WalkValues,
) -> ProfilePollResult:
    now = datetime.now(timezone.utc)
    scalar_states: dict[str, dict[str, Any]] = {}
    scalar_results = await asyncio.gather(
        *(
            get_value(device.host, device.port, device.community, item.instance_oid)
            for item in profile.scalars
        ),
        return_exceptions=True,
    )
    mandatory_missing = False
    for item, result in zip(profile.scalars, scalar_results):
        raw = None if isinstance(result, Exception) else result[1]
        raw_present = _raw_value(raw) is not None
        supported = not (not raw_present and item.optional_group is not None)
        state = normalize_field(
            item,
            raw,
            updated_at=now,
            supported=supported,
            present=raw_present,
        )
        scalar_states[item.canonical_field] = state
        mandatory_missing |= item.optional_group is None and not raw_present

    entities: list[dict[str, Any]] = []
    completed_tables: set[str] = set()
    for table in profile.tables:
        results = await asyncio.gather(
            *(
                walk_values(device.host, device.port, device.community, column.oid)
                for column in table.columns
            ),
            return_exceptions=True,
        )
        required_ok = all(
            not isinstance(result, Exception) and isinstance(result, dict)
            for column, result in zip(table.columns, results)
            if column.optional_group is None
        )
        if required_ok:
            completed_tables.add(table.canonical_field)
        rows: dict[tuple[int, ...], dict[str, Any]] = {}
        supported_columns: dict[str, bool] = {}
        for column, result in zip(table.columns, results):
            supported_columns[column.canonical_field] = not (
                isinstance(result, Exception)
                or (not result and column.optional_group is not None)
            )
            if isinstance(result, Exception) or not isinstance(result, dict):
                continue
            for oid, raw in result.items():
                indexes = _index_suffix(
                    str(oid).lstrip("."),
                    column.oid,
                    len(table.indexes),
                )
                if indexes is None:
                    continue
                try:
                    table.validate_fixture_indexes(indexes)
                except ValueError:
                    continue
                rows.setdefault(indexes, {})[column.canonical_field] = raw

        for indexes, raw_fields in rows.items():
            field_states: dict[str, dict[str, Any]] = {}
            for column in table.columns:
                raw = raw_fields.get(column.canonical_field)
                supported = supported_columns[column.canonical_field]
                field_states[column.canonical_field] = normalize_field(
                    column,
                    raw,
                    updated_at=now,
                    supported=supported,
                    present=raw is not None,
                )
            entities.append({
                "profile_id": profile.profile_id,
                "table_id": table.canonical_field,
                "entity_type": _entity_type(table.canonical_field),
                "entity_key": _entity_key(table, indexes),
                "label": _entity_label(table, indexes, field_states),
                "index_key": [
                    {"name": item.canonical_field, "value": value}
                    for item, value in zip(table.indexes, indexes)
                ],
                "raw_values": {
                    key: _raw_value(value) for key, value in raw_fields.items()
                },
                "normalized_values": {
                    key: state["value"] for key, state in field_states.items()
                },
                "field_states": field_states,
                "status": _aggregate_status(list(field_states.values())),
                "present": True,
                "stale": False,
                "updated_at": now,
            })
        mandatory_missing |= not required_ok

    return ProfilePollResult(
        profile=profile,
        scalar_states=scalar_states,
        entities=entities,
        status="partial" if mandatory_missing else "success",
        completed_tables=completed_tables,
    )


async def persist_profile_snapshot(device_id: str, result: ProfilePollResult) -> Device:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
        if device is None:
            raise LookupError(f"device {device_id!r} no longer exists")
        profile = result.profile
        device.system_oid = profile.sys_object_id
        device.profile_id = profile.profile_id
        device.profile_version = profile.profile_version
        device.profile_evidence_version = profile.evidence_version
        device.profile_scalar_states = result.scalar_states
        device.last_poll = now
        device.last_full_poll_status = result.status
        device.last_status = "online"

        scalar_values = {
            key: state.get("value") for key, state in result.scalar_states.items()
        }
        device.serial_number = scalar_values.get("serial_number") or device.serial_number
        device.model_name = scalar_values.get("device_type") or profile.product
        macs = [
            str(value)
            for key, value in scalar_values.items()
            if key.startswith("ether_address") and value
        ]
        if macs:
            device.mac_addresses = macs

        existing = (
            await db.execute(
                select(DeviceEntity).where(
                    DeviceEntity.device_id == device.id,
                    DeviceEntity.profile_id == profile.profile_id,
                )
            )
        ).scalars().all()
        by_key = {(item.table_id, item.entity_key): item for item in existing}
        seen: set[tuple[str, str]] = set()
        for payload in result.entities:
            key = (payload["table_id"], payload["entity_key"])
            seen.add(key)
            entity = by_key.get(key)
            if entity is None:
                entity = DeviceEntity(
                    device_id=device.id,
                    profile_id=profile.profile_id,
                    table_id=payload["table_id"],
                    entity_type=payload["entity_type"],
                    entity_key=payload["entity_key"],
                    first_seen_at=now,
                )
                db.add(entity)
            entity.label = payload["label"]
            entity.index_key = payload["index_key"]
            entity.raw_values = payload["raw_values"]
            entity.normalized_values = payload["normalized_values"]
            entity.field_states = payload["field_states"]
            entity.status = payload["status"]
            entity.is_present = True
            entity.is_stale = False
            entity.last_seen_at = now
            entity.updated_at = now

        for entity in existing:
            key = (entity.table_id, entity.entity_key)
            if entity.table_id in result.completed_tables and key not in seen:
                entity.is_present = False
                entity.is_stale = False
                entity.status = "absent"
                entity.updated_at = now

        if profile.profile_id == "ccdm_matrix":
            await _write_ccdm_endpoint_projection(db, device, result.entities, now)

        device.endpoint_count = len([
            entity for entity in result.entities
            if entity["table_id"] in {
                "user_module_table",
                "target_module_table",
                "dynamic_user_module_table",
            }
        ])
        await db.commit()
        await db.refresh(device)
        return device


async def _write_ccdm_endpoint_projection(db, device: Device, entities: list[dict], now: datetime):
    projection = {
        "user_module_table": "con",
        "target_module_table": "cpu",
        "dynamic_user_module_table": "dwc",
    }
    for entity in entities:
        module_type = projection.get(entity["table_id"])
        if module_type is None:
            continue
        row_index = int(entity["index_key"][0]["value"])
        endpoint_id = f"{device.id}_{module_type}_{row_index}"
        endpoint = await db.get(Endpoint, endpoint_id)
        if endpoint is None:
            endpoint = Endpoint(
                id=endpoint_id,
                device_id=device.id,
                index=row_index,
                module_type=module_type,
                created_at=now,
            )
            db.add(endpoint)
        endpoint.name = (
            entity["normalized_values"].get("name")
            or entity["normalized_values"].get("id")
            or entity["label"]
        )
        endpoint.last_status = entity["normalized_values"]
        endpoint.updated_at = now


async def mark_profile_data_stale(device_id: str) -> None:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        device = await db.get(Device, device_id)
        if device is None:
            return
        scalar_states = dict(device.profile_scalar_states or {})
        for key, state in scalar_states.items():
            updated = dict(state)
            if updated.get("supported") and updated.get("present"):
                updated["stale"] = True
                updated["status"] = "stale"
            scalar_states[key] = updated
        device.profile_scalar_states = scalar_states
        entities = (
            await db.execute(
                select(DeviceEntity).where(DeviceEntity.device_id == device_id)
            )
        ).scalars().all()
        for entity in entities:
            entity.is_stale = True
            entity.status = "stale"
            states = dict(entity.field_states or {})
            for key, state in states.items():
                updated = dict(state)
                if updated.get("supported") and updated.get("present"):
                    updated["stale"] = True
                    updated["status"] = "stale"
                states[key] = updated
            entity.field_states = states
            entity.updated_at = now
        await db.commit()
