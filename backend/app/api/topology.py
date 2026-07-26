from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.database import get_db
from app.models.device import Device
from app.models.endpoint import Endpoint
from app.models.simulator_run import SimulatorRun

router = APIRouter()

@router.get("/{device_id}", response_model=dict)
async def get_device_topology(device_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    """
    获取指定 KVM 设备的拓扑结构图数据。
    返回的结构为标准的节点(nodes)和连线(links)格式，可以直接用于 ECharts 等渲染库。
    """
    # 1. 查找主机
    device = await db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="KVM设备未找到")

    nodes = []
    links = []

    # 根节点：KVM 交换机主机
    nodes.append({
        "id": device.id,
        "name": device.name or device.id,
        "type": "kvm_switch",
        "status": device.last_status or "offline",
        "symbolSize": 60,
        "category": 0,
        "detail": {
            "ip": device.host,
            "model": device.model_name
        }
    })

    # 2. 查找该主机下的所有终端
    result = await db.execute(select(Endpoint).where(Endpoint.device_id == device_id))
    endpoints = result.scalars().all()

    for ep in endpoints:
        status_dict = ep.last_status or {}

        if ep.module_type == "con":
            ep_status = status_dict.get("con_device_status", "offline")
            ep_video   = status_dict.get("con_display_conn", "notConnected")
            node_status = ep_status
            if ep_status == "online" and status_dict.get("con_freeze") == "true":
                node_status = "warning"
            detail = {
                "temperature":  status_dict.get("con_temperature"),
                "display_conn": status_dict.get("con_display_conn"),
                "display_type": status_dict.get("con_display_type"),
                "freeze":       status_dict.get("con_freeze"),
                "sfp_tx_power": status_dict.get("con_sfp_tx_power"),
                "sfp_rx_power": status_dict.get("con_sfp_rx_power"),
            }
        else:  # cpu / port
            ep_status = status_dict.get("ep_device_status", "offline")
            ep_video   = status_dict.get("ep_target_video_cable", "notConnected")
            node_status = ep_status
            if ep_status == "online" and status_dict.get("ep_target_power") == "off":
                node_status = "warning"
            detail = {
                "temperature":  status_dict.get("ep_temperature"),
                "video_signal": status_dict.get("ep_target_video_signal", "none"),
                "sfp_tx_power": status_dict.get("ep_sfp_tx_power"),
                "sfp_rx_power": status_dict.get("ep_sfp_rx_power"),
            }

        nodes.append({
            "id": ep.id,
            "name": ep.name or ep.id,
            "type": "endpoint",
            "module_type": ep.module_type,
            "status": node_status,
            "symbolSize": 40,
            "category": 1,
            "detail": detail,
        })

        line_style = {"type": "solid", "color": "#5470c6"}
        label = "Connected"
        if ep_video != "connected":
            line_style = {"type": "dashed", "color": "#ee6666"}
            label = "Disconnected"

        links.append({
            "source": device.id,
            "target": ep.id,
            "value": ep_video,
            "label": {"show": ep_video != "connected", "formatter": label},
            "lineStyle": line_style
        })

    simulation = None
    if device.model_name and device.model_name.startswith("SIMULATION /"):
        runs = await db.execute(select(SimulatorRun))
        for run in runs.scalars():
            for simulator_device in run.manifest.get("scenario", {}).get("devices", []):
                expected_id = f"sim_{run.id}_{simulator_device['id']}"[:64]
                if expected_id != device.id:
                    continue
                route_links = []
                for route in simulator_device.get("routes", []):
                    source = next((item for item in simulator_device.get("endpoints", []) if item["id"] == route["source_endpoint_id"]), None)
                    target = next((item for item in simulator_device.get("endpoints", []) if item["id"] == route["target_endpoint_id"]), None)
                    if not source or not target:
                        continue
                    route_links.append({
                        "id": route["id"],
                        "source": f"{device.id}_{source['module_type']}_{source['row']}",
                        "target": f"{device.id}_{target['module_type']}_{target['row']}",
                        "state": route["state"],
                        "label": route.get("label") or "Simulation route",
                        "evidence": "simulation-declared",
                    })
                simulation = {
                    "run_id": run.id,
                    "revision": run.revision,
                    "profile": simulator_device["profile"],
                    "evidence": simulator_device.get("evidence", "simulation-declared"),
                    "routes": route_links,
                }
                break
            if simulation:
                break

    return {
        "device_id": device.id,
        "nodes": nodes,
        "links": links,
        "simulation": simulation,
        "categories": [
            {"name": "KVM 交换机"},
            {"name": "终端节点"}
        ]
    }
