from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.endpoint import Endpoint
from app.models.user import User
from app.auth.deps import get_current_user, require_admin

router = APIRouter()


class EndpointOut(BaseModel):
    id: str
    device_id: str
    name: Optional[str]
    index: int
    module_type: str
    last_status: Optional[dict]
    updated_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[EndpointOut])
async def list_endpoints(
    device_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Endpoint).order_by(Endpoint.device_id, Endpoint.index)
    if device_id:
        stmt = stmt.where(Endpoint.device_id == device_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{endpoint_id}", response_model=EndpointOut)
async def get_endpoint(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "终端不存在")
    return ep


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(
    endpoint_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "终端不存在")
    await db.delete(ep)
    await db.commit()

