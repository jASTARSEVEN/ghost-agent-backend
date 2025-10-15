import asyncio, json, logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from chat.socket import Connection, room_manager

router = APIRouter()
log = logging.getLogger("websocket")

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, role: str):
    await websocket.accept()
    conn = Connection(websocket, user_id, role)
    await room_manager.register(conn)

    async def sender():
        try:
            while True:
                msg = await conn.send_q.get()
                await websocket.send_json(msg)
        except Exception:
            pass

    send_task = asyncio.create_task(sender())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"type": "invalid", "data": raw}
            msg["meta"] = {"from": conn.role}
            await room_manager.broadcast(user_id, msg)
    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        await room_manager.unregister(conn)