# import asyncio, json, logging
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# from chat.socket import Connection, room_manager

# router = APIRouter()
# log = logging.getLogger("websocket")

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
#         except Exception:
#             pass

#     send_task = asyncio.create_task(sender())

#     try:
#         while True:
#             raw = await websocket.receive_text()
#             try:
#                 msg = json.loads(raw)
#             except Exception:
#                 msg = {"type": "invalid", "data": raw}
#             msg["meta"] = {"from": conn.role}
#             await room_manager.broadcast(user_id, msg)
#     except WebSocketDisconnect:
#         pass
#     finally:
#         send_task.cancel()
#         await room_manager.unregister(conn)


# import os
# import asyncio
# import json
# import logging
# from datetime import datetime
# import redis
# from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
# from sqlalchemy.orm import Session
# from sqlalchemy import func

# from chat.socket import Connection, room_manager
# from chat.models import EventModel
# from chat.dependencies import get_db

# router = APIRouter()
# log = logging.getLogger("websocket")

# # Setup Redis client (honor REDIS_URL to work in Docker)
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
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
#             if "received_at" not in msg:
#                 msg["received_at"] = datetime.utcnow().isoformat()

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


import os
import asyncio
import json
import logging
from datetime import datetime
import redis

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import func

from chat.socket import Connection, room_manager
from chat.models import EventModel
from chat.dependencies import get_db

router = APIRouter()
log = logging.getLogger("websocket")

# -------- REDIS SETUP --------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.getenv("EVENT_QUEUE_NAME", "event_queue")

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    print(f"\n Redis connected successfully at: {REDIS_URL}\n")
except Exception as e:
    redis_client = None
    print(f"\n❌ REDIS CONNECTION FAILED: {REDIS_URL}\nError: {e}\n")


#  Optional function you can call on FastAPI startup
def init_redis_check():
    if redis_client:
        try:
            redis_client.ping()
            print(f"Redis connection verified")
        except Exception as e:
            print(f"❌Redis lost connection: {e}")
    else:
        print(" Redis client not initialized!")


# -------- WEBSOCKET ENDPOINT --------
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
        except:
            pass

    send_task = asyncio.create_task(sender())

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except:
                msg = {"event_type": "invalid", "data": raw}

            msg["user_id"] = user_id
            if "received_at" not in msg:
                msg["received_at"] = datetime.utcnow().isoformat()

            # Health check ping
            if msg.get("event_type") == "health_ping":
                await room_manager.broadcast(user_id, msg)
                continue

            #  Push event into Redis queue if available
            if redis_client:
                try:
                    redis_client.lpush(QUEUE_NAME, json.dumps(msg))
                    print(f"Redis LPUSH success -> {QUEUE_NAME}")
                except redis.exceptions.ConnectionError as e:
                    print(f" Redis push error: {e}")
                    msg["error"] = "redis_unavailable"
            else:
                print("Redis not connected, message NOT queued!")

            # Broadcast message to WebSocket room
            await room_manager.broadcast(user_id, msg)

    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        await room_manager.unregister(conn)


# -------- HTTP ENDPOINTS --------

@router.get("/api/conversations")
def get_all_conversations(db: Session = Depends(get_db)):
    rows = (
        db.query(
            EventModel.user_id,
            EventModel.conversation_id,
            func.max(EventModel.received_at).label("last_event"),
        )
        .group_by(EventModel.user_id, EventModel.conversation_id)
        .order_by(func.max(EventModel.received_at).desc())
        .all()
    )

    return [
        {
            "user_id": r.user_id,
            "conversation_id": r.conversation_id,
            "last_event": r.last_event,
        }
        for r in rows
    ]


@router.get("/api/conversations/{conversation_id}")
def get_messages(conversation_id: str, db: Session = Depends(get_db)):
    msgs = (
        db.query(EventModel)
        .filter(EventModel.conversation_id == conversation_id)
        .order_by(EventModel.received_at.asc())
        .all()
    )

    return [
        {
            "user_id": m.user_id,
            "conversation_id": m.conversation_id,
            "event_type": m.event_type,
            "payload": m.payload,
            "received_at": m.received_at,
        }
        for m in msgs
    ]
