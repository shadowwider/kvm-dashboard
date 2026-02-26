from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websocket.hub import ws_manager

router = APIRouter()


@router.websocket("/monitor")
async def websocket_monitor(websocket: WebSocket, token: str = Query(None)):
    """
    前端大屏 WebSocket 连接端点。
    接受连接后持续等待，后端通过 ws_manager.broadcast() 推送数据。
    支持简单 token 验证（可选）。
    """
    # 简单 token 校验（生产环境建议严格验证）
    if token:
        try:
            from app.auth.jwt import decode_token
            decode_token(token)
        except Exception:
            await websocket.close(code=4001)
            return

    await ws_manager.connect(websocket)
    try:
        while True:
            # 接收客户端消息（心跳 ping）
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(websocket)
