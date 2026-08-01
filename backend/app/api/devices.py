from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from pydantic import BaseModel
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_admin
from app.database import get_db
from app.models.device import Device
from app.models.device_entity import DeviceEntity
from app.models.endpoint import Endpoint
from app.models.oid_registry import OIDRegistry
from app.models.user import User
from app.serializers import (
    DeviceSummaryCounts,
    load_device_summary_counts,
    serialize_device_detail,
    serialize_device_summary,
    serialize_entity,
)
from app.services.audit import record_audit_log
from app.snmp.profile_runtime import profile_metadata
from kvm_profiles import PROFILE_CATALOG


router = APIRouter()
_REDACTED = object()


class ProfileOut(BaseModel):
    id: str
    version: str
    evidence_version: str
    product: str
    role: str
    system_oid: str
    label_key: str
    section_keys: list[str]


class ReachabilityOut(BaseModel):
    status: str
    last_check: datetime | None
    latency_ms: float | None = None


class DataFreshnessOut(BaseModel):
    status: str
    last_full_poll: datetime | None
    age_seconds: int | None


class HealthOut(BaseModel):
    status: str
    warning_count: int
    critical_count: int


class DeviceSummaryOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    location: str | None
    description: str | None
    profile: ProfileOut | None
    system_oid: str | None
    model_name: str | None
    serial_number: str | None
    credential_configured: bool
    is_active: bool
    poll_interval: int
    last_poll: datetime | None
    last_health_check: datetime | None
    last_status: str | None
    last_metrics: dict[str, Any] | None
    reachability: ReachabilityOut
    data_freshness: DataFreshnessOut
    health: HealthOut
    endpoint_count: int
    entity_count: int
    active_alert_count: int
    created_at: datetime
    updated_at: datetime


class DevicePage(BaseModel):
    items: list[DeviceSummaryOut]
    total: int
    page: int
    page_size: int


class DeviceDetailDeviceOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    location: str | None
    description: str | None
    profile: ProfileOut | None
    system_oid: str | None
    model_name: str | None
    serial_number: str | None
    credential_configured: bool
    is_active: bool
    reachability: ReachabilityOut
    data_freshness: DataFreshnessOut
    health: HealthOut


class EntityOut(BaseModel):
    profile_id: str
    table_id: str
    entity_key: str
    entity_type: str
    label: str | None
    index_key: list[dict[str, Any]]
    status: str
    present: bool
    stale: bool
    updated_at: datetime
    fields: list[dict[str, Any]]


class DetailSectionOut(BaseModel):
    key: str
    label_key: str
    order: int
    status: str
    fields: list[dict[str, Any]]
    entities: list[EntityOut]


class DeviceDetailOut(BaseModel):
    device: DeviceDetailDeviceOut
    sections: list[DetailSectionOut]


class EntityPage(BaseModel):
    items: list[EntityOut]
    total: int
    page: int
    page_size: int


class DeviceCreate(BaseModel):
    id: str
    name: str
    host: str
    port: int = 161
    community: str = "public"
    location: str | None = None
    description: str | None = None
    poll_interval: int = 60


class DeviceUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    community: str | None = None
    location: str | None = None
    description: str | None = None
    is_active: bool | None = None
    poll_interval: int | None = None


def _strip_community(value: Any) -> Any:
    if isinstance(value, dict):
        for identity_key in ("key", "field_key", "name", "label_key"):
            identity = value.get(identity_key)
            if (
                isinstance(identity, str)
                and "community" in identity.casefold()
            ):
                return _REDACTED
        result = {}
        for key, child in value.items():
            if "community" in str(key).casefold():
                continue
            sanitized = _strip_community(child)
            if sanitized is not _REDACTED:
                result[key] = sanitized
        return result
    if isinstance(value, (list, tuple)):
        result = []
        for child in value:
            sanitized = _strip_community(child)
            if sanitized is not _REDACTED:
                result.append(sanitized)
        return result
    return value


def _infer_profile(device: Device) -> dict[str, Any] | None:
    if device.profile_id in PROFILE_CATALOG:
        return profile_metadata(PROFILE_CATALOG[device.profile_id])
    if not device.system_oid:
        return None
    profile = next(
        (
            item
            for item in PROFILE_CATALOG.values()
            if item.sys_object_id == device.system_oid
        ),
        None,
    )
    return profile_metadata(profile) if profile is not None else None


async def _safe_device_summary(
    db: AsyncSession,
    device: Device,
    counts: DeviceSummaryCounts | None = None,
) -> DeviceSummaryOut:
    payload = await serialize_device_summary(db, device, counts=counts)
    if payload.get("profile") is None:
        payload["profile"] = _infer_profile(device)
    return DeviceSummaryOut.model_validate(_strip_community(payload))


@router.get("", response_model=DevicePage | list[DeviceSummaryOut])
async def list_devices(
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DevicePage | list[DeviceSummaryOut]:
    paginated = page is not None or page_size is not None
    resolved_page = page or 1
    resolved_page_size = page_size or 100

    statement = select(Device).order_by(Device.id)
    if paginated:
        statement = statement.offset(
            (resolved_page - 1) * resolved_page_size
        ).limit(resolved_page_size)

    devices = (await db.scalars(statement)).all()
    summary_counts = await load_device_summary_counts(
        db,
        [device.id for device in devices],
    )
    items = [
        await _safe_device_summary(
            db,
            device,
            summary_counts[device.id],
        )
        for device in devices
    ]
    if not paginated:
        return items

    total = await db.scalar(select(func.count(Device.id)))
    return DevicePage(
        items=items,
        total=int(total or 0),
        page=resolved_page,
        page_size=resolved_page_size,
    )


@router.post("", response_model=DeviceSummaryOut, status_code=201)
async def create_device(
    body: DeviceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
) -> DeviceSummaryOut:
    existing = await db.get(Device, body.id)
    if existing:
        raise HTTPException(409, f"设备 ID {body.id} 已存在")
    device = Device(**body.model_dump())
    db.add(device)
    await db.flush()
    await record_audit_log(
        db,
        action="device.create",
        actor=current,
        target_type="device",
        target_id=device.id,
        request=request,
        change_summary={
            "name": device.name,
            "host": device.host,
            "port": device.port,
            "poll_interval": device.poll_interval,
            "snmp_access_configured": bool(device.community),
        },
    )
    await db.commit()
    await db.refresh(device)
    return await _safe_device_summary(db, device)


@router.get("/{device_id}/details", response_model=DeviceDetailOut)
async def get_device_details(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DeviceDetailOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    payload = await serialize_device_detail(db, device)
    if payload["device"].get("profile") is None:
        payload["device"]["profile"] = _infer_profile(device)
    return DeviceDetailOut.model_validate(_strip_community(payload))


@router.get("/{device_id}/entities", response_model=EntityPage)
async def list_device_entities(
    device_id: str,
    table_id: str | None = Query(None, min_length=1, max_length=128),
    entity_type: str | None = Query(None, min_length=1, max_length=128),
    status: str | None = Query(None, min_length=1, max_length=16),
    present: bool | None = Query(None),
    stale: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> EntityPage:
    if await db.get(Device, device_id) is None:
        raise HTTPException(404, "设备不存在")

    filters = [DeviceEntity.device_id == device_id]
    if table_id:
        filters.append(DeviceEntity.table_id == table_id)
    if entity_type:
        filters.append(DeviceEntity.entity_type == entity_type)
    if status:
        filters.append(DeviceEntity.status == status)
    if present is not None:
        filters.append(DeviceEntity.is_present.is_(present))
    if stale is not None:
        filters.append(DeviceEntity.is_stale.is_(stale))

    total = await db.scalar(
        select(func.count(DeviceEntity.id)).where(*filters)
    )
    entities = (
        await db.scalars(
            select(DeviceEntity)
            .where(*filters)
            .order_by(DeviceEntity.table_id, DeviceEntity.entity_key)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return EntityPage(
        items=[
            EntityOut.model_validate(
                _strip_community(serialize_entity(entity))
            )
            for entity in entities
        ],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.get("/{device_id}", response_model=DeviceSummaryOut)
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DeviceSummaryOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    return await _safe_device_summary(db, device)


@router.patch("/{device_id}", response_model=DeviceSummaryOut)
async def update_device(
    device_id: str,
    body: DeviceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
) -> DeviceSummaryOut:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(device, field, value)
    changed_fields = [
        "snmp_access" if field == "community" else field
        for field in changes
    ]
    await record_audit_log(
        db,
        action="device.update",
        actor=current,
        target_type="device",
        target_id=device.id,
        request=request,
        change_summary={
            "changed_fields": changed_fields,
            "snmp_access_changed": "community" in changes,
        },
    )
    await db.commit()
    await db.refresh(device)
    return await _safe_device_summary(db, device)


@router.delete(
    "/{device_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
)
async def delete_device(
    device_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
) -> Response:
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    await db.execute(
        sql_delete(Endpoint).where(Endpoint.device_id == device_id)
    )
    await db.delete(device)
    await record_audit_log(
        db,
        action="device.delete",
        actor=current,
        target_type="device",
        target_id=device.id,
        request=request,
        change_summary={
            "name": device.name,
            "host": device.host,
            "port": device.port,
        },
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/{device_id}/poll", status_code=202)
async def trigger_poll(
    device_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(require_admin),
) -> dict[str, str]:
    """手动触发单台设备立即轮询。"""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    oids_result = await db.execute(
        select(OIDRegistry).where(OIDRegistry.poll_enabled.is_(True))
    )
    oid_configs = oids_result.scalars().all()

    from app.snmp.poller import poll_device

    await record_audit_log(
        db,
        action="device.poll",
        actor=current,
        target_type="device",
        target_id=device.id,
        request=request,
        change_summary={"trigger": "manual"},
        commit=True,
    )
    background_tasks.add_task(poll_device, device, oid_configs)
    return {"message": f"已触发设备 {device_id} 轮询"}
