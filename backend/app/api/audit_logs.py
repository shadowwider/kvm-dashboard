from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_admin
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import redact_secrets


router = APIRouter()


class AuditActorOut(BaseModel):
    id: int | None
    username: str | None
    role: str | None


class AuditTargetOut(BaseModel):
    type: str | None
    id: str | None


class AuditLogOut(BaseModel):
    id: int
    actor: AuditActorOut | None
    action: str
    target: AuditTargetOut | None
    result: str
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    change_summary: dict[str, Any] | None
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


def _utc_boundary(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_filters(
    *,
    actor_id: int | None,
    action: str | None,
    target_type: str | None,
    target_id: str | None,
    result: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[Any]:
    date_from = _utc_boundary(date_from)
    date_to = _utc_boundary(date_to)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from must be earlier than or equal to date_to",
        )

    filters: list[Any] = []
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if action:
        filters.append(AuditLog.action == action)
    if target_type:
        filters.append(AuditLog.target_type == target_type)
    if target_id:
        filters.append(AuditLog.target_id == target_id)
    if result:
        filters.append(AuditLog.result == result)
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)
    return filters


def _serialize_log(entry: AuditLog) -> AuditLogOut:
    actor = None
    if (
        entry.actor_id is not None
        or entry.actor_username is not None
        or entry.actor_role is not None
    ):
        actor = AuditActorOut(
            id=entry.actor_id,
            username=entry.actor_username,
            role=entry.actor_role,
        )

    target = None
    if entry.target_type is not None or entry.target_id is not None:
        target = AuditTargetOut(type=entry.target_type, id=entry.target_id)

    return AuditLogOut(
        id=entry.id,
        actor=actor,
        action=entry.action,
        target=target,
        result=entry.result,
        request_id=entry.request_id,
        ip_address=entry.ip_address,
        user_agent=redact_secrets(entry.user_agent),
        change_summary=(
            redact_secrets(entry.change_summary)
            if entry.change_summary is not None
            else None
        ),
        created_at=entry.created_at,
    )


@router.get("", response_model=AuditLogPage)
async def list_audit_logs(
    actor_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, max_length=128),
    target_type: str | None = Query(None, max_length=64),
    target_id: str | None = Query(None, max_length=128),
    result: str | None = Query(None, max_length=16),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> AuditLogPage:
    filters = _build_filters(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        date_from=date_from,
        date_to=date_to,
    )
    total = await db.scalar(
        select(func.count(AuditLog.id)).where(*filters)
    )
    rows = await db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return AuditLogPage(
        items=[_serialize_log(entry) for entry in rows.all()],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


def _csv_safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        text = json.dumps(
            redact_secrets(value),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    elif isinstance(value, datetime):
        text = value.isoformat()
    else:
        text = str(redact_secrets(value))
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


@router.get("/export")
async def export_audit_logs_csv(
    actor_id: int | None = Query(None, ge=1),
    action: str | None = Query(None, max_length=128),
    target_type: str | None = Query(None, max_length=64),
    target_id: str | None = Query(None, max_length=128),
    result: str | None = Query(None, max_length=16),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    limit: int = Query(50000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> StreamingResponse:
    filters = _build_filters(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        date_from=date_from,
        date_to=date_to,
    )
    rows = await db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(limit)
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id",
        "created_at",
        "actor_id",
        "actor_username",
        "actor_role",
        "action",
        "target_type",
        "target_id",
        "result",
        "request_id",
        "ip_address",
        "user_agent",
        "change_summary",
    ])
    for entry in rows.all():
        writer.writerow([
            _csv_safe(entry.id),
            _csv_safe(entry.created_at),
            _csv_safe(entry.actor_id),
            _csv_safe(entry.actor_username),
            _csv_safe(entry.actor_role),
            _csv_safe(entry.action),
            _csv_safe(entry.target_type),
            _csv_safe(entry.target_id),
            _csv_safe(entry.result),
            _csv_safe(entry.request_id),
            _csv_safe(entry.ip_address),
            _csv_safe(entry.user_agent),
            _csv_safe(entry.change_summary),
        ])

    filename = f"audit_logs_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
