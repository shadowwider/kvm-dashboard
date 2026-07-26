from fastapi import APIRouter
from app.api import auth, devices, endpoints, oid_registry, alerts, metrics, stats, ws, topology, aliases, simulator

api_router = APIRouter()

api_router.include_router(auth.router,         prefix="/auth",     tags=["认证"])
api_router.include_router(devices.router,      prefix="/devices",  tags=["KVM设备"])
api_router.include_router(endpoints.router,    prefix="/endpoints",tags=["终端设备"])
api_router.include_router(topology.router,     prefix="/topology", tags=["拓扑展示"])
api_router.include_router(aliases.router,      prefix="/aliases",  tags=["别名管理"])
api_router.include_router(oid_registry.router, prefix="/oids",     tags=["OID配置"])
api_router.include_router(alerts.router,       prefix="/alerts",   tags=["告警管理"])
api_router.include_router(metrics.router,      prefix="/metrics",  tags=["历史指标"])
api_router.include_router(stats.router,        prefix="/stats",    tags=["大屏统计"])
api_router.include_router(ws.router,           prefix="/ws",       tags=["WebSocket"])
api_router.include_router(simulator.router,    prefix="/simulator", tags=["本地模拟器"])

