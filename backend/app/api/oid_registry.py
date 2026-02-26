from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.oid_registry import OIDRegistry
from app.models.user import User
from app.auth.deps import get_current_user, require_admin

router = APIRouter()


class OIDOut(BaseModel):
    id: int
    oid: str
    name: str
    display_name: str
    description: Optional[str]
    category: str
    data_type: str
    unit: Optional[str]
    enum_map: Optional[dict]
    is_table: bool
    table_base_oid: Optional[str]
    table_column: Optional[int]
    alert_enabled: bool
    alert_gt: Optional[float]
    alert_lt: Optional[float]
    alert_eq_str: Optional[str]
    alert_ne_str: Optional[str]
    alert_severity: str
    poll_enabled: bool
    display_enabled: bool
    display_order: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class OIDCreate(BaseModel):
    oid: str
    name: str
    display_name: str
    description: Optional[str] = None
    category: str = "device"
    data_type: str = "string"
    unit: Optional[str] = None
    enum_map: Optional[dict] = None
    is_table: bool = False
    table_base_oid: Optional[str] = None
    table_column: Optional[int] = None
    alert_enabled: bool = False
    alert_gt: Optional[float] = None
    alert_lt: Optional[float] = None
    alert_eq_str: Optional[str] = None
    alert_ne_str: Optional[str] = None
    alert_severity: str = "warning"
    poll_enabled: bool = True
    display_enabled: bool = True
    display_order: int = 0


class OIDUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    enum_map: Optional[dict] = None
    alert_enabled: Optional[bool] = None
    alert_gt: Optional[float] = None
    alert_lt: Optional[float] = None
    alert_eq_str: Optional[str] = None
    alert_ne_str: Optional[str] = None
    alert_severity: Optional[str] = None
    poll_enabled: Optional[bool] = None
    display_enabled: Optional[bool] = None
    display_order: Optional[int] = None


@router.get("", response_model=list[OIDOut])
async def list_oids(
    category: Optional[str] = Query(None, description="device 或 endpoint"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(OIDRegistry).order_by(OIDRegistry.display_order)
    if category:
        stmt = stmt.where(OIDRegistry.category == category)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=OIDOut, status_code=201)
async def create_oid(
    body: OIDCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(OIDRegistry).where(OIDRegistry.name == body.name))
    if result.scalar_one_or_none():
        raise HTTPException(409, f"OID 名称 {body.name} 已存在")
    oid_entry = OIDRegistry(**body.model_dump())
    db.add(oid_entry)
    await db.commit()
    await db.refresh(oid_entry)
    return oid_entry


@router.patch("/{oid_id}", response_model=OIDOut)
async def update_oid(
    oid_id: int,
    body: OIDUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    oid_entry = await db.get(OIDRegistry, oid_id)
    if not oid_entry:
        raise HTTPException(404, "OID 不存在")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(oid_entry, field, value)
    await db.commit()
    await db.refresh(oid_entry)
    return oid_entry


@router.delete("/{oid_id}", status_code=204)
async def delete_oid(
    oid_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    oid_entry = await db.get(OIDRegistry, oid_id)
    if not oid_entry:
        raise HTTPException(404, "OID 不存在")
    await db.delete(oid_entry)
    await db.commit()
