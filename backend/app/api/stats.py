from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.alert import Alert
from app.models.user import User
from app.auth.deps import get_current_user
from app.websocket.hub import ws_manager

router = APIRouter()


class DashboardStats(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    warning_devices: int
    total_endpoints: int
    active_alerts: int
    critical_alerts: int
    ws_clients: int
    server_time: datetime


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """大屏顶部统计数据"""
    total_devices = (await db.execute(select(func.count()).select_from(Device).where(Device.is_active == True))).scalar()
    online_devices = (await db.execute(select(func.count()).select_from(Device).where(Device.last_status == "online"))).scalar()
    offline_devices = (await db.execute(select(func.count()).select_from(Device).where(Device.last_status == "offline"))).scalar()
    warning_devices = (await db.execute(select(func.count()).select_from(Device).where(Device.last_status == "warning"))).scalar()
    total_endpoints = (await db.execute(select(func.count()).select_from(Endpoint))).scalar()
    active_alerts = (await db.execute(select(func.count()).select_from(Alert).where(Alert.is_resolved == False))).scalar()
    critical_alerts = (await db.execute(select(func.count()).select_from(Alert).where(Alert.is_resolved == False, Alert.severity == "critical"))).scalar()

    return DashboardStats(
        total_devices=total_devices or 0,
        online_devices=online_devices or 0,
        offline_devices=offline_devices or 0,
        warning_devices=warning_devices or 0,
        total_endpoints=total_endpoints or 0,
        active_alerts=active_alerts or 0,
        critical_alerts=critical_alerts or 0,
        ws_clients=ws_manager.connection_count,
        server_time=datetime.utcnow(),
    )
