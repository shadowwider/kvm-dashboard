from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import csv
import io

from app.database import get_db
from app.models.alert import Alert
from app.models.user import User
from app.api.audit_logs import _csv_safe
from app.auth.deps import get_current_user
from app.services.audit import record_audit_log

router = APIRouter()


class AlertOut(BaseModel):
    id: int
    device_id: str
    endpoint_id: Optional[str]
    entity_key: Optional[str]
    oid_name: Optional[str]
    alert_type: str
    severity: str
    message: str
    raw_value: Optional[str]
    trap_level: Optional[int]
    trap_oid: Optional[str]
    is_resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    device_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    is_resolved: Optional[bool] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    if is_resolved is not None:
        stmt = stmt.where(Alert.is_resolved == is_resolved)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/export")
async def export_alerts_csv(
    device_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(5000, le=50000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """导出告警日志为 CSV 文件（Admin 下载用）"""
    stmt = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    if severity:
        stmt = stmt.where(Alert.severity == severity)
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID",
        "时间",
        "设备ID",
        "终端ID",
        "实体键",
        "指标",
        "级别",
        "告警类型",
        "Trap Level",
        "Trap OID",
        "消息",
        "原始值",
        "是否已处理",
        "处理时间",
    ])
    for a in alerts:
        row = [
            a.id,
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
            a.device_id,
            a.endpoint_id or "",
            a.entity_key or "",
            a.oid_name or "",
            a.severity,
            a.alert_type,
            a.trap_level if a.trap_level is not None else "",
            a.trap_oid or "",
            a.message,
            a.raw_value or "",
            "是" if a.is_resolved else "否",
            a.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if a.resolved_at else "",
        ]
        writer.writerow([_csv_safe(value) for value in row])

    output.seek(0)
    filename = f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),  # BOM for Excel 中文兼容
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    was_resolved = alert.is_resolved
    alert.is_resolved = True
    alert.resolved_at = datetime.utcnow()
    await record_audit_log(
        db,
        action="alert.resolve",
        actor=current,
        target_type="alert",
        target_id=alert.id,
        request=request,
        change_summary={
            "device_id": alert.device_id,
            "already_resolved": was_resolved,
        },
    )
    await db.commit()
    await db.refresh(alert)
    return alert


@router.post("/resolve-all", status_code=200)
async def resolve_all_alerts(
    request: Request,
    device_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """批量确认所有未解决告警"""
    stmt = update(Alert).where(Alert.is_resolved == False).values(
        is_resolved=True, resolved_at=datetime.utcnow()
    )
    if device_id:
        stmt = stmt.where(Alert.device_id == device_id)
    result = await db.execute(stmt)
    await record_audit_log(
        db,
        action="alert.resolve_all",
        actor=current,
        target_type="device" if device_id else "alert",
        target_id=device_id or "all",
        request=request,
        change_summary={
            "device_id": device_id,
            "resolved_count": max(result.rowcount or 0, 0),
        },
    )
    await db.commit()
    return {"message": "已批量确认所有告警"}

