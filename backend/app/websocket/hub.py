"""
WebSocket 连接管理器。
维护所有活跃的 WS 连接，并支持广播消息到所有客户端。
"""
import asyncio
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WS 客户端连接，当前连接数: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            try:
                self._connections.remove(websocket)
            except ValueError:
                pass
        logger.info(f"WS 客户端断开，当前连接数: {len(self._connections)}")

    async def broadcast(self, message: dict):
        """向所有连接广播 JSON 消息"""
        if not self._connections:
            return

        text = json.dumps(message, ensure_ascii=False, default=str)
        dead_connections = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead_connections.append(ws)

        # 清理断开的连接
        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    try:
                        self._connections.remove(ws)
                    except ValueError:
                        pass

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# 全局单例
ws_manager = ConnectionManager()
