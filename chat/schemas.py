from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class ConversationLogEvent(BaseModel):
    """Schema for individual event within a conversation log."""
    id: str
    event_type: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    received_at: Optional[str] = None


class ConversationLogBase(BaseModel):
    """Base schema for conversation log."""
    id: str
    user_id: str
    conversation_id: str
    customer: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None
    events: List[ConversationLogEvent]
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    is_evaluated: bool = False
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class ConversationLogOut(ConversationLogBase):
    """Response schema for a single conversation log."""
    pass


class ConversationLogListResponse(BaseModel):
    """Response schema for conversation log list."""
    items: List[ConversationLogOut]
    total: Optional[int] = Field(None, description="Total count of conversations (if available)")
    limit: int
    offset: int

