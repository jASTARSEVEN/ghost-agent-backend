import os
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List
import redis

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, FastAPI, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from chat.socket import Connection, room_manager
from chat.models import EventModel, ConversationLog
from chat.schemas import ConversationLogOut, ConversationLogListResponse, ConversationLogEvent
from authentication.models import User
from authentication.utils import decode_token
from common.dependencies import get_db, require_permission
from common.response_handler import ResponseHandler
from vonage_connector.audio_websocket import tts_consumer, speech_to_text, create_wav_header


router = APIRouter()
log = logging.getLogger("websocket")

# -------- REDIS SETUP --------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = os.getenv("EVENT_QUEUE_NAME", "event_queue")

try:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    log.info(f"Redis connected successfully at: {REDIS_URL}")
except Exception as e:
    redis_client = None
    log.error(f"REDIS CONNECTION FAILED: {REDIS_URL}, Error: {e}")


#  Optional function you can call on FastAPI startup
def init_redis_check():
    if redis_client:
        try:
            redis_client.ping()
            log.info("Redis connection verified")
        except Exception as e:
            log.error(f"Redis lost connection: {e}")
    else:
        log.warning("Redis client not initialized!")


# -------- WEBSOCKET ENDPOINT --------
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket, 
    user_id: str,
    token: str = Query(...),
    role: str = Query("user")
):
    """WebSocket endpoint with authentication
    
    Connect with: ws://host/ws/{user_id}?token={jwt_token}&role={role}
    Token must be valid JWT and user_id must match token payload
    """
    # Validate token before accepting connection
    try:
        payload = decode_token(token)
        # Support both "sub" (JWT standard) and "user_id" (backward compatibility)
        token_user_id = str(payload.get("sub") or payload.get("user_id"))
        if token_user_id != user_id:
            await websocket.close(code=1008, reason="Unauthorized: user_id mismatch")
            return
    except Exception as e:
        log.error(f"WebSocket authentication failed: {e}")
        await websocket.close(code=1008, reason="Invalid token")
        return
    
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
 
    
    ELEVENLABS_API_KEY = os.getenv("ELEVEN_API_KEY")
    BUFFER_SIZE = 64000 
    VONAGE_SAMPLE_RATE = 16000  
    audio_buffer = bytearray()
    tts_queue = asyncio.Queue()

    try:
        tts_task = asyncio.create_task(tts_consumer(websocket, tts_queue))

        while True:
            message = await websocket.receive()
            
            # Check if the message indicates a disconnect
            if message.get("type") == "websocket.disconnect":
                break
 

            if "text" in message and message["text"] is not None:
                text_data = message["text"]
                print("Text message:", text_data) 


            elif "bytes" in message and message["bytes"] is not None:
                audio_data = message["bytes"]
                audio_buffer.extend(audio_data)
                if len(audio_buffer) >= BUFFER_SIZE:
                    wav_audio = create_wav_header(bytes(audio_buffer), sample_rate=VONAGE_SAMPLE_RATE)
                    
                    transcript = await speech_to_text(
                        wav_audio, 
                        ELEVENLABS_API_KEY
                    )
                    
                    if transcript and not '(' in transcript:
                        print(f"STT Result: {transcript}")
                        await websocket.send_text(json.dumps({
                            "type": "transcription",
                            "text": transcript
                        }))
                    
                    audio_buffer.clear() 

    # try:
    #     while True:
    #         raw = await websocket.receive_text()

    #         try:
    #             msg = json.loads(raw)
    #         except:
    #             msg = {"event_type": "invalid", "data": raw}

    #         msg["user_id"] = user_id
    #         if "received_at" not in msg:
    #             msg["received_at"] = datetime.now(timezone.utc).isoformat()

    #         # Health check ping
    #         if msg.get("event_type") == "health_ping":
    #             await room_manager.broadcast(user_id, msg)
    #             continue

    #         #  Push event into Redis queue if available
    #         if redis_client:
    #             try:
    #                 redis_client.lpush(QUEUE_NAME, json.dumps(msg))
    #                 log.debug(f"Redis LPUSH success -> {QUEUE_NAME}")
    #             except redis.exceptions.ConnectionError as e:
    #                 log.error(f"Redis push error: {e}")
    #                 msg["error"] = "redis_unavailable"
    #         else:
    #             log.warning("Redis not connected, message NOT queued!")

    #         # Broadcast message to WebSocket room
    #         await room_manager.broadcast(user_id, msg)

    except WebSocketDisconnect:
        pass
    finally:
        if 'tts_task' in locals():
            tts_task.cancel()
            try:
                await tts_task
            except asyncio.CancelledError:
                pass
        send_task.cancel()
        await room_manager.unregister(conn)


# -------- CONVERSATION LOG ROUTES --------

@router.get("/api/conversation-logs", response_model=List[ConversationLogOut])
async def get_conversation_logs(
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100000),
    is_evaluated: bool = Query(None, description="Filter by evaluation status")
):
    """
    Get all conversation logs for the current user.
    Returns complete conversations from conversation_log table.
    """
    stmt = select(ConversationLog).where(
        ConversationLog.user_id == str(user.id)
    )
    
    # Optional filter by evaluation status
    if is_evaluated is not None:
        stmt = stmt.where(ConversationLog.is_evaluated == is_evaluated)
    
    stmt = stmt.order_by(ConversationLog.ended_at.desc().nulls_last(), ConversationLog.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    logs = result.scalars().all()
    
    data = [
        ConversationLogOut(
            id=str(log.id),
            user_id=log.user_id,
            conversation_id=log.conversation_id,
            customer=log.customer,
            agent=log.agent,
            events=[
                ConversationLogEvent(**event) if isinstance(event, dict) else event
                for event in (log.events or [])
            ],
            started_at=log.started_at.isoformat() if log.started_at else None,
            ended_at=log.ended_at.isoformat() if log.ended_at else None,
            is_evaluated=log.is_evaluated,
            created_at=log.created_at.isoformat() if log.created_at else None,
            updated_at=log.updated_at.isoformat() if log.updated_at else None,
        )
        for log in logs
    ]
    return ResponseHandler.ok(message="Conversation logs retrieved successfully", data=data)


@router.get("/api/conversation-logs/{conversation_id}", response_model=ConversationLogOut)
async def get_conversation_log_by_id(
    conversation_id: str,
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific conversation log by conversation_id.
    Returns complete conversation data from conversation_log table.
    """
    stmt = select(ConversationLog).where(
        ConversationLog.conversation_id == conversation_id,
        ConversationLog.user_id == str(user.id)
    )
    
    result = await db.execute(stmt)
    log = result.scalar_one_or_none()
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation log not found or access denied"
        )
    
    data = ConversationLogOut(
        id=str(log.id),
        user_id=log.user_id,
        conversation_id=log.conversation_id,
        customer=log.customer,
        agent=log.agent,
        events=[
            ConversationLogEvent(**event) if isinstance(event, dict) else event
            for event in (log.events or [])
        ],
        started_at=log.started_at.isoformat() if log.started_at else None,
        ended_at=log.ended_at.isoformat() if log.ended_at else None,
        is_evaluated=log.is_evaluated,
        created_at=log.created_at.isoformat() if log.created_at else None,
        updated_at=log.updated_at.isoformat() if log.updated_at else None,
    )
    return ResponseHandler.ok(message="Conversation log retrieved successfully", data=data)