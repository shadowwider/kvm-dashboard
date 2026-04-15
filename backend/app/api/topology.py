from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.database import get_db
from app.models.device import Device
from app.models.endpoint import Endpoint

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

    return {
        "device_id": device.id,
        "nodes": nodes,
        "links": links,
        "categories": [
            {"name": "KVM 交换机"},
            {"name": "终端节点"}
        ]
    }
