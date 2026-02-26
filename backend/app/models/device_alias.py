"""
设备/终端别名映射模型。
用户可以为任何 device 或 endpoint 设置自定义显示名称。
前端展示时优先使用别名。
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from app.database import Base


class DeviceAlias(Base):
    __tablename__ = "device_aliases"

    # target_id 可以是 devices.id 或 endpoints.id
    target_id = Column(String(100), primary_key=True)
    # 对象类型: "device" 或 "endpoint"
    target_type = Column(String(20), nullable=False, default="device")
    # 用户自定义名称
    alias = Column(String(200), nullable=False)
    # 备注（可选）
    note = Column(Text, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
