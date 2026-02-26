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
        
        # 提取终端状态和连接情况
        ep_status = status_dict.get("ep_device_status", "offline")
        ep_power = status_dict.get("ep_target_power", "off")
        ep_video = status_dict.get("ep_target_video_cable", "notConnected")
        
        node_status = ep_status
        if ep_status == "online" and ep_power == "off":
            node_status = "warning" # 在线但未通电等
        
        # 生成终端节点
        nodes.append({
            "id": ep.id,
            "name": ep.name or ep.id,
            "type": "endpoint",
            "status": node_status,
            "symbolSize": 40,
            "category": 1,
            "detail": {
                "temperature": status_dict.get("ep_temperature"),
                "video_signal": status_dict.get("ep_target_video_signal", "none"),
                "sfp_tx_power": status_dict.get("ep_sfp_tx_power"),
                "sfp_rx_power": status_dict.get("ep_sfp_rx_power"),
            }
        })

        # 生成与主机的连接线
        # 根据视频线连接状态改变线的颜色或样式
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
