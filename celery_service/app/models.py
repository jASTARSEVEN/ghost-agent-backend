import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from .db_base import Base


class EventModel(Base):
    __tablename__ = "conversation_events"
    __table_args__ = (
        Index("idx_user_conversation", "user_id", "conversation_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, index=True)
    event_type = Column(String, index=True)  # Add index for filtering
    payload = Column(JSONB)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class ConversationLog(Base):
    __tablename__ = "conversation_log"
    __table_args__ = (
        Index("idx_user_conversation_log", "user_id", "conversation_id"),
        Index("idx_conversation_log_ended_at", "ended_at"),
        Index("idx_conversation_log_is_evaluated", "is_evaluated"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, nullable=False, index=True, unique=True)
    
    # Customer data from call_started event
    customer = Column(JSONB, nullable=True)  # {name, email, customerId, phone_e164}
    
    # Agent/Employee data from call_started event
    agent = Column(JSONB, nullable=True)  # {id, email, company_id, company_name}
    
    # Conversation data
    events = Column(JSONB, nullable=False)  # Array of all events for this conversation

    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Compliance evaluation flag
    is_evaluated = Column(Boolean, nullable=False, default=False, server_default='false')
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
