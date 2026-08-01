from fastapi import APIRouter
from app.api import (
    aliases,
    alerts,
    audit_logs,
    auth,
    devices,
    discovery,
    endpoints,
    metrics,
    oid_registry,
    profiles,
    simulator,
    stats,
    topology,
    ws,
)

api_router = APIRouter()

api_router.include_router(auth.router,         prefix="/auth",     tags=["认证"])
api_router.include_router(devices.router,      prefix="/devices",  tags=["KVM设备"])
api_router.include_router(profiles.router,     prefix="/profiles", tags=["设备Profile"])
api_router.include_router(endpoints.router,    prefix="/endpoints",tags=["终端设备"])
api_router.include_router(topology.router,     prefix="/topology", tags=["拓扑展示"])
api_router.include_router(aliases.router,      prefix="/aliases",  tags=["别名管理"])
api_router.include_router(oid_registry.router, prefix="/oids",     tags=["OID配置"])
api_router.include_router(alerts.router,       prefix="/alerts",   tags=["告警管理"])
api_router.include_router(metrics.router,      prefix="/metrics",  tags=["历史指标"])
api_router.include_router(stats.router,        prefix="/stats",    tags=["大屏统计"])
api_router.include_router(ws.router,           prefix="/ws",       tags=["WebSocket"])
api_router.include_router(simulator.router,    prefix="/simulator", tags=["本地模拟器"])
api_router.include_router(discovery.router,    prefix="/discovery", tags=["设备自动发现"])
api_router.include_router(audit_logs.router,   prefix="/audit-logs", tags=["操作审计"])

