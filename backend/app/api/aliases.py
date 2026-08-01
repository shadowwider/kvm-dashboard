"""
设备/终端别名管理 API。
支持批量查询（用于前端一次性拉取所有别名）和 inline 编辑。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.device_alias import DeviceAlias
from app.models.user import User
from app.auth.deps import get_current_user
from app.services.audit import record_audit_log

router = APIRouter()


class AliasOut(BaseModel):
    target_id: str
    target_type: str
    alias: str
    note: Optional[str]
    updated_at: Optional[datetime]
    model_config = {"from_attributes": True}


class AliasUpsert(BaseModel):
    """创建或更新别名（前端 inline 编辑直接提交）"""
    alias: str
    target_type: str = "device"  # "device" 或 "endpoint"
    note: Optional[str] = None


@router.get("", response_model=list[AliasOut])
async def list_aliases(
    target_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取所有别名（可按类型筛选）"""
    stmt = select(DeviceAlias).order_by(DeviceAlias.target_id)
    if target_type:
        stmt = stmt.where(DeviceAlias.target_type == target_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/{target_id}", response_model=AliasOut)
async def upsert_alias(
    target_id: str,
    body: AliasUpsert,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """创建或更新别名（幂等操作，前端直接 PUT）"""
    existing = await db.get(DeviceAlias, target_id)
    operation = "update" if existing else "create"
    if existing:
        existing.alias = body.alias
        existing.target_type = body.target_type
        existing.note = body.note
    else:
        existing = DeviceAlias(
            target_id=target_id,
            target_type=body.target_type,
            alias=body.alias,
            note=body.note,
        )
        db.add(existing)
    await record_audit_log(
        db,
        action="alias.set",
        actor=current,
        target_type=body.target_type,
        target_id=target_id,
        request=request,
        change_summary={
            "operation": operation,
            "target_type": body.target_type,
            "alias_configured": bool(body.alias),
            "note_configured": bool(body.note),
        },
    )
    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/{target_id}", status_code=204)
async def delete_alias(
    target_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """删除别名（恢复 SNMP 原始名称）"""
    existing = await db.get(DeviceAlias, target_id)
    if not existing:
        raise HTTPException(404, "别名不存在")
    await db.delete(existing)
    await record_audit_log(
        db,
        action="alias.delete",
        actor=current,
        target_type=existing.target_type,
        target_id=target_id,
        request=request,
        change_summary={"target_type": existing.target_type},
    )
    await db.commit()
