from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_token
from app.database import get_db
from app.models.user import User
from app.websocket.hub import ws_manager

router = APIRouter()


@router.websocket("/monitor")
async def websocket_monitor(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    前端大屏 WebSocket 连接端点。
    接受连接后持续等待，后端通过 ws_manager.broadcast() 推送数据。
    仅允许持有有效 JWT 且账号已启用的用户建立连接。
    """
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not isinstance(username, str) or not username.strip():
            raise JWTError("missing subject")
    except (JWTError, AttributeError):
        await websocket.close(code=4001)
        return

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        await websocket.close(code=4001)
        return
    if not user.is_active:
        await websocket.close(code=4003)
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
