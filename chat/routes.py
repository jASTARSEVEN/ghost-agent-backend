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

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
            except:
                msg = {"event_type": "invalid", "data": raw}

            msg["user_id"] = user_id
            if "received_at" not in msg:
                msg["received_at"] = datetime.now(timezone.utc).isoformat()

            # Health check ping
            if msg.get("event_type") == "health_ping":
                await room_manager.broadcast(user_id, msg)
                continue

            #  Push event into Redis queue if available
            if redis_client:
                try:
                    redis_client.lpush(QUEUE_NAME, json.dumps(msg))
                    log.debug(f"Redis LPUSH success -> {QUEUE_NAME}")
                except redis.exceptions.ConnectionError as e:
                    log.error(f"Redis push error: {e}")
                    msg["error"] = "redis_unavailable"
            else:
                log.warning("Redis not connected, message NOT queued!")

            # Broadcast message to WebSocket room
            await room_manager.broadcast(user_id, msg)

    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        await room_manager.unregister(conn)


# -------- HTTP ENDPOINTS --------

# @router.get("/api/conversations")
# def get_all_conversations(db: Session = Depends(get_db), user: User = Depends(require_permission("compliance.documents.upload"))):
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


# @router.get("/api/conversations/{conversation_id}")
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



# @router.get("/api/conversations")
# async def get_all_conversations(
#     user: User = Depends(require_permission("*")),
#     db: AsyncSession = Depends(get_db),
#     limit: int = 100,
#     offset: int = 0
# ):
#     """
#     Get all conversations for the current user.
#     Optimized with subquery to reduce data scanned.
#     """
#     # Subquery to get max received_at per conversation
#     max_dates_subq = (
#         select(
#             EventModel.user_id,
#             EventModel.conversation_id,
#             func.max(EventModel.received_at).label("last_event")
#         )
#         .filter(EventModel.user_id == str(user.id))
#         .group_by(EventModel.user_id, EventModel.conversation_id)
#         .subquery()
#     )
    
#     # Main query - already has aggregated data, just order and paginate
#     stmt = (
#         select(
#             max_dates_subq.c.user_id,
#             max_dates_subq.c.conversation_id,
#             max_dates_subq.c.last_event
#         )
#         .order_by(max_dates_subq.c.last_event.desc())
#         .limit(limit)
#         .offset(offset)
#     )
    
#     result = await db.execute(stmt)
#     rows = result.all()

#     return [
#         {
#             "user_id": r.user_id,
#             "conversation_id": r.conversation_id,
#             "last_event": r.last_event,
#         }
#         for r in rows
#     ]


# @router.get("/api/conversations/{conversation_id}")
# async def get_messages(
#     conversation_id: str,
#     user: User = Depends(require_permission("*")),
#     db: AsyncSession = Depends(get_db),
#     limit: int = 1000,
#     offset: int = 0
# ):
#     """
#     Get messages for a specific conversation.
#     Optimized to use composite index efficiently.
#     """
#     # This query already uses the composite index (user_id, conversation_id)
#     # Add limit to prevent loading too much data at once
#     stmt = (
#         select(EventModel)
#         .filter(
#             EventModel.conversation_id == conversation_id,
#             EventModel.user_id == str(user.id)
#         )
#         .order_by(EventModel.received_at.asc())
#         .limit(limit)
#         .offset(offset)
#     )
    
#     result = await db.execute(stmt)
#     msgs = result.scalars().all()

#     if not msgs:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Conversation not found or access denied"
#         )

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


@router.get("/api/conversations")
async def get_all_conversations(
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),  # Max 1000
    offset: int = Query(0, ge=0, le=100000)  # Max 100k offset
):
    """
    Get all conversations for the current user.
    Optimized with subquery to reduce data scanned.
    """
    max_dates_subq = (
        select(
            EventModel.user_id,
            EventModel.conversation_id,
            func.max(EventModel.received_at).label("last_event")
        )
        .where(EventModel.user_id == str(user.id))
        .group_by(EventModel.user_id, EventModel.conversation_id)
        .subquery()
    )

    stmt = (
        select(
            max_dates_subq.c.user_id,
            max_dates_subq.c.conversation_id,
            max_dates_subq.c.last_event
        )
        .order_by(max_dates_subq.c.last_event.desc())
        .limit(limit)
        .offset(offset)
    )

    rows = (await db.execute(stmt)).all()

    return [
        {
            "user_id": r.user_id,
            "conversation_id": r.conversation_id,
            "last_event": r.last_event,
        }
        for r in rows
    ]


# Must come BEFORE /api/conversations/{conversation_id}
@router.get("/api/conversations/formatted")
async def get_all_formatted_conversations(
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),  # Max 500
    offset: int = Query(0, ge=0, le=100000)  # Max 100k offset
):
    """
    Returns formatted conversations without the N+1 query problem.
    Uses ONE query for all events of all selected conversations.
    """

    # 1. Get conversation IDs ordered by latest event
    max_dates_subq = (
        select(
            EventModel.conversation_id,
            func.max(EventModel.received_at).label("last_event")
        )
        .where(EventModel.user_id == str(user.id))
        .group_by(EventModel.conversation_id)
        .subquery()
    )

    stmt = (
        select(max_dates_subq.c.conversation_id)
        .order_by(max_dates_subq.c.last_event.desc())
        .limit(limit)
        .offset(offset)
    )

    conversation_ids = [row.conversation_id for row in (await db.execute(stmt)).all()]

    if not conversation_ids:
        return []

    # 2. Fetch ALL events for those conversations in ONE single query
    events_stmt = (
        select(EventModel)
        .where(
            EventModel.user_id == str(user.id),
            EventModel.conversation_id.in_(conversation_ids)
        )
        .order_by(EventModel.conversation_id.asc(), EventModel.received_at.asc())
    )

    events = (await db.execute(events_stmt)).scalars().all()

    # 3. Group events by conversation_id
    grouped = {cid: [] for cid in conversation_ids}
    for evt in events:
        grouped[evt.conversation_id].append(evt)

    formatted = []

    # 4. Build formatted conversations
    for conv_id in conversation_ids:
        msgs = grouped[conv_id]
        if not msgs:
            continue

        # Detect call_started event
        call_started = next((m for m in msgs if m.event_type == "call_started"), None)

        customer = {}
        date = None
        user_id = user.id

        if call_started and call_started.payload:
            payload = call_started.payload
            customer = payload.get("customer", {})
            user_id = payload.get("user_id", call_started.user_id)
            date = payload.get("started_at") or payload.get("received_at") or str(call_started.received_at)
        else:
            # fallback
            first = msgs[0]
            user_id = first.user_id
            date = str(first.received_at)

        compliance = ""
        for m in msgs:
            if m.event_type and "compliance" in m.event_type.lower():
                compliance = (m.payload or {}).get("compliance_status", "")
                break

        formatted.append({
            "customer": customer,
            "user_id": str(user_id),
            "date": date,
            "compliance": compliance,
            "conversation_id": conv_id,
            "events": [
                {   "id": m.id,
                    "user_id": m.user_id,
                    "conversation_id": m.conversation_id,
                    "event_type": m.event_type,
                    "payload": m.payload,
                    "received_at": str(m.received_at),
                }
                for m in msgs
            ]
        })

    return formatted


@router.get("/api/conversations/{conversation_id}")
async def get_messages(
    conversation_id: str,
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(1000, ge=1, le=10000),  # Max 10k
    offset: int = Query(0, ge=0, le=100000)  # Max 100k offset
):
    """
    Get messages for a specific conversation (optimized).
    """

    stmt = (
        select(EventModel)
        .where(
            EventModel.conversation_id == conversation_id,
            EventModel.user_id == str(user.id)
        )
        .order_by(EventModel.received_at.asc())
        .limit(limit)
        .offset(offset)
    )

    msgs = (await db.execute(stmt)).scalars().all()

    if not msgs:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied"
        )

    return [
        {  
            "id": m.id,
            "user_id": m.user_id,
            "conversation_id": m.conversation_id,
            "event_type": m.event_type,
            "payload": m.payload,
            "received_at": m.received_at,
        }
        for m in msgs
    ]


@router.get("/api/conversations/{conversation_id}/formatted")
async def get_formatted_conversation(
    conversation_id: str,
    user: User = Depends(require_permission("*")),
    db: AsyncSession = Depends(get_db)
):
    """
    Single conversation formatted (no optimization needed).
    """

    stmt = (
        select(EventModel)
        .where(
            EventModel.conversation_id == conversation_id,
            EventModel.user_id == str(user.id)
        )
        .order_by(EventModel.received_at.asc())
    )

    msgs = (await db.execute(stmt)).scalars().all()

    if not msgs:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied"
        )

    call_started = next((m for m in msgs if m.event_type == "call_started"), None)

    customer = {}
    date = None
    user_id = user.id

    if call_started and call_started.payload:
        payload = call_started.payload
        customer = payload.get("customer", {})
        user_id = payload.get("user_id", call_started.user_id)
        date = payload.get("started_at") or payload.get("received_at") or str(call_started.received_at)
    else:
        first = msgs[0]
        user_id = first.user_id
        date = str(first.received_at)

    compliance = ""
    for m in msgs:
        if m.event_type and "compliance" in m.event_type.lower():
            compliance = (m.payload or {}).get("compliance_status", "")
            break

    return {
        "customer": customer,
        "user_id": str(user_id),
        "date": date,
        "compliance": compliance,
        "conversation_id": conversation_id,
        "events": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "conversation_id": m.conversation_id,
                "event_type": m.event_type,
                "payload": m.payload,
                "received_at": str(m.received_at),
            }
            for m in msgs
        ]
    }


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
    
    return [
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
    
    return ConversationLogOut(
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
