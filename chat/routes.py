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


# import os
# import asyncio
# import json
# import logging
# import redis
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
# from sqlalchemy.orm import Session
# from sqlalchemy import func

# from chat.socket import Connection, room_manager
# from celery_service.app.models import EventModel
# from chat.dependencies import get_db

# router = APIRouter()
# log = logging.getLogger("websocket")

# # Setup Redis client
# redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
# QUEUE_NAME = os.getenv("EVENT_QUEUE_NAME", "event_queue")

# # WebSocket endpoint for real-time communication
# @router.websocket("/ws/{user_id}")
# async def websocket_endpoint(websocket: WebSocket, user_id: str, role: str):
#     await websocket.accept()

#     conn = Connection(websocket, user_id, role)
#     await room_manager.register(conn)

#     async def sender():
#         try:
#             while True:
#                 msg = await conn.send_q.get()
#                 await websocket.send_json(msg)
#         except:
#             pass

#     send_task = asyncio.create_task(sender())

#     try:
#         while True:
#             raw = await websocket.receive_text()

#             try:
#                 msg = json.loads(raw)
#             except:
#                 msg = {"event_type": "invalid", "data": raw}

#             msg["user_id"] = user_id

#             # Special health_ping event for connection health check
#             if msg.get("event_type") == "health_ping":
#                 await room_manager.broadcast(user_id, msg)
#                 continue

#             # Push message to Redis for processing by Celery
#             redis_client.lpush("event_queue", json.dumps(msg))

#             # Broadcast the message to the room
#             await room_manager.broadcast(user_id, msg)

#     except WebSocketDisconnect:
#         pass
#     finally:
#         send_task.cancel()
#         await room_manager.unregister(conn)

# # Fetch all conversations from the database
# @router.get("/conversations")
# def get_all_conversations(db: Session = Depends(get_db)):
#     rows = (
#         db.query(
#             EventModel.user_id,
#             EventModel.conversation_id,
#             func.max(EventModel.received_at).label("last_event"),
#         )
#         .group_by(EventModel.user_id, EventModel.conversation_id)
#         .order_by(func.max(EventModel.received_at).desc())
#         .all()
#     )

#     return [
#         {
#             "user_id": r.user_id,
#             "conversation_id": r.conversation_id,
#             "last_event": r.last_event,
#         }
#         for r in rows
#     ]

# # Fetch all events in a specific conversation
# @router.get("/conversations/{conversation_id}")
# def get_messages(conversation_id: str, db: Session = Depends(get_db)):
#     msgs = (
#         db.query(EventModel)
#         .filter(EventModel.conversation_id == conversation_id)
#         .order_by(EventModel.received_at.asc())
#         .all()
#     )

#     return [
#         {
#             "user_id": m.user_id,
#             "conversation_id": m.conversation_id,
#             "event_type": m.event_type,
#             "payload": m.payload,
#             "received_at": m.received_at,
#         }
#         for m in msgs
#     ]
