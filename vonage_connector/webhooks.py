import os
import logging
import random
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from authentication.utils import (
    create_access_token,
)
from authentication.models import User, Role, user_roles
from database import get_db
import json
from chat.socket import room_manager
import requests
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vonage", tags=["vonage"])

WEBSOCKET_BASE_URL = os.getenv("VONAGE_WEBSOCKET_URL")

def ws_event(
    *,
    event_type: str,
    user_id: str,
    call_uuid: str | None = None,
    media_uuid: str | None = None,
    data: dict | None = None,
):
    return {
        "event_type": event_type,
        "user_id": user_id,
        "call_uuid": call_uuid,
        "media_uuid": media_uuid,
        "data": data or {},
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

async def get_role_name_by_user_id(user_id: int, db: AsyncSession) -> Optional[str]: 
    stmt = select(user_roles.c.role_id).where(user_roles.c.user_id == user_id)
    result = await db.execute(stmt)
    role_id = result.scalars().first()
    
    if not role_id:
        logger.warning(f"No role found for user_id {user_id}")
        return None
    
    stmt = select(Role.name).where(Role.id == role_id)
    result = await db.execute(stmt)
    role_name = result.scalars().first()
    
    return role_name

@router.post("/answer")
async def answer_call(request: Request, db: AsyncSession = Depends(get_db)): 
    try:  
        data = await request.json()
        
        call_uuid = data.get("uuid")
        to_number = data.get("to")

        # 1. randomly choose a CSR
        stmt = select(User)
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        if not users:
            return JSONResponse(content=[
                {
                    "action": "talk",
                    "text": "We're sorry, no agents are available. Please try again later."
                }
            ])
        
        selected_user = random.choice(users)
        user_id = selected_user.id
        user = selected_user
        
        if not user:
            logger.error(f"User with id {user_id} not found")
            phone_number = None
            role = None
        else:
            phone_number = user.phone_number
            role = await get_role_name_by_user_id(user_id, db)
        
        #2. generate token
        token = create_access_token({"sub": str(user_id)}) 
        
        ws_uri = f"{WEBSOCKET_BASE_URL}/ws/{user_id}?token={token}&role={role}"
        # ws_uri = f"{WEBSOCKET_BASE_URL}/vonage/audio-stream"

        ncco = [
            {
                "action": "talk",
                "text": "Long time no see"
            },
            {
                "action": "connect",
                "endpoint": [
                    {
                        "type": "phone",
                        "number": phone_number
                    }
                ],
                "from": to_number
            },
            {
                "action": "connect",
                "endpoint": [
                    {
                        "type": "websocket",
                        "uri": f"{ws_uri}",
                        "content-type": "audio/l16;rate=16000",
                        "headers": {
                            "uuid": call_uuid
                        }
                    }
                ]
            }
        ]
        return JSONResponse(content=ncco)
 
    except Exception as e:
        logger.error(f"Error handling answer webhook: {e}")
        return JSONResponse(content=[
            {
                "action": "talk",
                "text": "We're sorry, an error occurred. Please try again later."
            }
        ])

@router.post("/event")
async def call_event(request: Request, db: AsyncSession = Depends(get_db)): 
    try:
        data = await request.json()
        uuid = data.get("uuid")
        status = data.get("status")
        direction = data.get("direction")
        to_number = data.get("to")

        vonage_numbers = os.getenv("VONAGE_NUMBERS", "").split(",")
        vonage_numbers = [num.strip() for num in vonage_numbers if num.strip()]
        
        if to_number and (to_number in vonage_numbers or "ws://" in to_number or "wss://" in to_number):
            pass
        else:
            event_map = {
                "started": "call.started",
                "ringing": "call.ringing",
                "answered": "call.answered",
                "completed": "call.ended",
                "failed": "call.failed",
            }
                
            event_type = event_map.get(status, "unknown")

            if(direction == "inbound"):
                phone_number = data.get("from")
            else:
                phone_number = data.get("to")

            stmt = select(User).where(User.phone_number == phone_number)
            result = await db.execute(stmt)
            user = result.scalars().first()
            if user:
                user_id_number = user.id
            else:
                user_id_number = None

            event_data = ws_event(   
                event_type=event_type,
                user_id=str(user_id_number),   
                call_uuid=uuid,
                data={
                    "role": "system",   
                    "direction": direction,
                    "raw_status": status,
                    "from": data.get("from"),
                    "to": to_number,
                    "duration": data.get("duration"),
                    "reason": data.get("reason"),
                    "error_code": data.get("error_code"),
                },
            )

            await room_manager.broadcast(user_id=str(user_id_number), message=event_data)
            return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling event webhook: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/answer")
async def answer_call_get(request: Request): 
    return await answer_call(request)

@router.post("/fallback")
async def fallback_answer(request: Request): 
    logger.warning("Fallback answer webhook triggered")
    
    ncco = [
        {
            "action": "talk",
            "text": "We're experiencing technical difficulties. Please call back later.",
            "language": "en-US"
        }
    ]
    
    return JSONResponse(content=ncco)
 