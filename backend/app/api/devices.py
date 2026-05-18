from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.user import User
from app.auth.deps import get_current_user, require_admin
from app.snmp.poller import poll_device, run_poll_cycle
from app.models.oid_registry import OIDRegistry

router = APIRouter()


class DeviceOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    community: str
    location: Optional[str]
    description: Optional[str]
    is_active: bool
    poll_interval: int
    last_poll: Optional[datetime]
    last_status: Optional[str]
    last_metrics: Optional[dict]
    endpoint_count: Optional[int] = 0
    created_at: datetime
    model_config = {"from_attributes": True}


class DeviceCreate(BaseModel):
    id: str
    name: str
    host: str
    port: int = 161
    community: str = "public"
    location: Optional[str] = None
    description: Optional[str] = None
    poll_interval: int = 60


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    community: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    poll_interval: Optional[int] = None


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Device).order_by(Device.id))
    return result.scalars().all()


@router.post("", response_model=DeviceOut, status_code=201)
async def create_device(
    body: DeviceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.get(Device, body.id)
    if existing:
        raise HTTPException(409, f"设备 ID {body.id} 已存在")
    device = Device(**body.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    return device


@router.patch("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: str,
    body: DeviceUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(device, field, value)
    await db.commit()
    await db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    await db.execute(sql_delete(Endpoint).where(Endpoint.device_id == device_id))
    await db.delete(device)
    await db.commit()


@router.post("/{device_id}/poll", status_code=202)
async def trigger_poll(
    device_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """手动触发单台设备立即轮询"""
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "设备不存在")
    oids_result = await db.execute(select(OIDRegistry).where(OIDRegistry.poll_enabled == True))
    oid_configs = oids_result.scalars().all()
    background_tasks.add_task(poll_device, device, oid_configs)
    return {"message": f"已触发设备 {device_id} 轮询"}
