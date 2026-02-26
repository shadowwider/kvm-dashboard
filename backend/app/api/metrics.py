from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.status_metric import StatusMetric
from app.models.user import User
from app.auth.deps import get_current_user

router = APIRouter()


class MetricPoint(BaseModel):
    time: datetime
    value_str: Optional[str]
    value_num: Optional[float]


@router.get("/history")
async def get_metric_history(
    device_id: str = Query(...),
    oid_name: str = Query(...),
    endpoint_id: Optional[str] = Query(None),
    hours: int = Query(24, le=168),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取指定设备/终端某 OID 字段的历史数据（默认 24h）"""
    stmt = text("""
        SELECT time, value_str, value_num
        FROM status_metrics
        WHERE device_id = :device_id
          AND oid_name = :oid_name
          AND (:endpoint_id IS NULL OR endpoint_id = :endpoint_id)
          AND time >= NOW() - INTERVAL ':hours hours'
        ORDER BY time ASC
        LIMIT 2000
    """)
    # TimescaleDB 支持直接时间过滤，效率极高
    result = await db.execute(
        select(StatusMetric)
        .where(
            StatusMetric.device_id == device_id,
            StatusMetric.oid_name == oid_name,
            StatusMetric.endpoint_id == endpoint_id if endpoint_id else StatusMetric.endpoint_id.is_(None),
        )
        .where(text(f"time >= NOW() - INTERVAL '{hours} hours'"))
        .order_by(StatusMetric.time.asc())
        .limit(2000)
    )
    rows = result.scalars().all()
    return [MetricPoint(time=r.time, value_str=r.value_str, value_num=r.value_num) for r in rows]
