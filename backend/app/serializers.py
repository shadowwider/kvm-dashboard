from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence, TypedDict

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.device import Device
from app.models.device_entity import DeviceEntity
from app.models.endpoint import Endpoint
from app.snmp.profile_runtime import (
    SECTION_ORDER,
    profile_metadata,
    section_for_field,
    section_for_table,
)
from kvm_profiles import PROFILE_CATALOG


class DeviceSummaryCounts(TypedDict):
    endpoint_count: int
    entity_count: int
    active_alert_count: int
    warning_count: int
    critical_count: int


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "device_id": alert.device_id,
        "endpoint_id": alert.endpoint_id,
        "entity_key": alert.entity_key,
        "oid_name": alert.oid_name,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "message": alert.message,
        "raw_value": alert.raw_value,
        "trap_level": alert.trap_level,
        "trap_oid": alert.trap_oid,
        "is_resolved": alert.is_resolved,
        "resolved_at": _iso(alert.resolved_at),
        "created_at": _iso(alert.created_at),
    }


def _freshness(device: Device) -> dict[str, Any]:
    last_poll = device.last_poll
    if last_poll is None:
        return {"status": "unknown", "last_full_poll": None, "age_seconds": None}
    if last_poll.tzinfo is None:
        last_poll = last_poll.replace(tzinfo=timezone.utc)
    age = max(0, int((datetime.now(timezone.utc) - last_poll).total_seconds()))
    status = "fresh" if age <= max(device.poll_interval * 2, 120) else "stale"
    if device.last_full_poll_status in {"failed", "unsupported"}:
        status = device.last_full_poll_status
    return {
        "status": status,
        "last_full_poll": _iso(last_poll),
        "age_seconds": age,
    }


def _empty_summary_counts() -> DeviceSummaryCounts:
    return {
        "endpoint_count": 0,
        "entity_count": 0,
        "active_alert_count": 0,
        "warning_count": 0,
        "critical_count": 0,
    }


async def load_device_summary_counts(
    db: AsyncSession,
    device_ids: Sequence[str],
) -> dict[str, DeviceSummaryCounts]:
    ids = list(dict.fromkeys(device_ids))
    counts = {
        device_id: _empty_summary_counts()
        for device_id in ids
    }
    if not ids:
        return counts

    entity_rows = await db.execute(
        select(
            DeviceEntity.device_id,
            func.count(DeviceEntity.id),
        )
        .where(
            DeviceEntity.device_id.in_(ids),
            DeviceEntity.is_present.is_(True),
        )
        .group_by(DeviceEntity.device_id)
    )
    for device_id, entity_count in entity_rows:
        counts[device_id]["entity_count"] = int(entity_count or 0)

    endpoint_rows = await db.execute(
        select(
            Endpoint.device_id,
            func.count(Endpoint.id),
        )
        .where(Endpoint.device_id.in_(ids))
        .group_by(Endpoint.device_id)
    )
    for device_id, endpoint_count in endpoint_rows:
        counts[device_id]["endpoint_count"] = int(endpoint_count or 0)

    alert_rows = await db.execute(
        select(
            Alert.device_id,
            func.count(Alert.id),
            func.sum(case((Alert.severity == "warning", 1), else_=0)),
            func.sum(case((Alert.severity == "critical", 1), else_=0)),
        )
        .where(
            Alert.device_id.in_(ids),
            Alert.is_resolved.is_(False),
        )
        .group_by(Alert.device_id)
    )
    for (
        device_id,
        active_alert_count,
        warning_count,
        critical_count,
    ) in alert_rows:
        counts[device_id].update({
            "active_alert_count": int(active_alert_count or 0),
            "warning_count": int(warning_count or 0),
            "critical_count": int(critical_count or 0),
        })
    return counts


async def serialize_device_summary(
    db: AsyncSession,
    device: Device,
    *,
    counts: DeviceSummaryCounts | None = None,
) -> dict[str, Any]:
    if counts is None:
        counts = (await load_device_summary_counts(db, [device.id]))[device.id]
    entity_count = counts["entity_count"]
    endpoint_count = counts["endpoint_count"]
    active_alert_count = counts["active_alert_count"]
    warning_count = counts["warning_count"]
    critical_count = counts["critical_count"]
    profile = PROFILE_CATALOG.get(device.profile_id or "")
    profile_payload = profile_metadata(profile) if profile is not None else None
    reachability = device.last_status or "unknown"
    if reachability not in {"online", "offline"}:
        reachability = "online" if device.last_health_check else "unknown"
    health_status = (
        "critical" if critical_count
        else "warning" if warning_count
        else "ok" if reachability == "online"
        else reachability
    )
    return {
        "id": device.id,
        "name": device.name,
        "host": device.host,
        "port": device.port,
        "location": device.location,
        "description": device.description,
        "profile": profile_payload,
        "system_oid": device.system_oid,
        "model_name": device.model_name,
        "serial_number": device.serial_number,
        "credential_configured": bool(device.community),
        "is_active": device.is_active,
        "poll_interval": device.poll_interval,
        "last_poll": _iso(device.last_poll),
        "last_health_check": _iso(device.last_health_check),
        "last_status": device.last_status,
        "last_metrics": device.last_metrics,
        "reachability": {
            "status": reachability,
            "last_check": _iso(device.last_health_check),
            "latency_ms": device.last_health_latency_ms,
        },
        "data_freshness": _freshness(device),
        "health": {
            "status": health_status,
            "warning_count": warning_count or 0,
            "critical_count": critical_count or 0,
        },
        "endpoint_count": endpoint_count or device.endpoint_count or 0,
        "entity_count": entity_count or 0,
        "active_alert_count": active_alert_count or 0,
        "created_at": _iso(device.created_at),
        "updated_at": _iso(device.updated_at),
    }


def serialize_entity(entity: DeviceEntity) -> dict[str, Any]:
    return {
        "profile_id": entity.profile_id,
        "table_id": entity.table_id,
        "entity_key": entity.entity_key,
        "entity_type": entity.entity_type,
        "label": entity.label,
        "index_key": entity.index_key or [],
        "status": entity.status,
        "present": entity.is_present,
        "stale": entity.is_stale,
        "updated_at": _iso(entity.updated_at),
        "fields": list((entity.field_states or {}).values()),
    }


async def serialize_device_detail(db: AsyncSession, device: Device) -> dict[str, Any]:
    summary = await serialize_device_summary(db, device)
    device_payload = {
        key: summary[key]
        for key in (
            "id",
            "name",
            "host",
            "port",
            "location",
            "description",
            "profile",
            "system_oid",
            "model_name",
            "serial_number",
            "credential_configured",
            "is_active",
            "reachability",
            "data_freshness",
            "health",
        )
    }
    sections: dict[str, dict[str, Any]] = {}

    def ensure(key: str) -> dict[str, Any]:
        return sections.setdefault(key, {
            "key": key,
            "label_key": f"detail.sections.{key}",
            "order": SECTION_ORDER[key],
            "status": "ok",
            "fields": [],
            "entities": [],
        })

    for key, state in (device.profile_scalar_states or {}).items():
        ensure(section_for_field(key))["fields"].append(state)

    entities = (
        await db.execute(
            select(DeviceEntity)
            .where(DeviceEntity.device_id == device.id)
            .order_by(DeviceEntity.table_id, DeviceEntity.entity_key)
        )
    ).scalars().all()
    for entity in entities:
        ensure(section_for_table(entity.table_id))["entities"].append(
            serialize_entity(entity)
        )

    if not sections and device.last_metrics:
        fields = []
        for key, value in (device.last_metrics.get("summary") or {}).items():
            fields.append({
                "key": key,
                "label_key": f"fields.{key}",
                "raw": value,
                "value": value,
                "unit": None,
                "status": "stale" if device.last_status == "offline" else "ok",
                "supported": True,
                "present": value is not None,
                "stale": device.last_status == "offline",
                "updated_at": _iso(device.last_poll),
            })
        ensure("health")["fields"] = fields

    for section in sections.values():
        statuses = {
            field.get("status") for field in section["fields"]
        } | {entity.get("status") for entity in section["entities"]}
        for status in ("critical", "offline", "warning", "stale", "unknown"):
            if status in statuses:
                section["status"] = status
                break
    return {
        "device": device_payload,
        "sections": sorted(sections.values(), key=lambda item: item["order"]),
    }
