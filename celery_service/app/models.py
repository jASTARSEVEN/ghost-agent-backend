import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from .db_base import Base


class EventModel(Base):
    __tablename__ = "conversation_events"
    __table_args__ = (
        Index("idx_user_conversation", "user_id", "conversation_id"),
        {"schema": "testdb"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, index=True)
    event_type = Column(String)
    payload = Column(JSONB)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
