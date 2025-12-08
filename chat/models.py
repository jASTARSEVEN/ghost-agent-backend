import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from database import Base


class EventModel(Base):
    __tablename__ = "conversation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    conversation_id = Column(String, index=True)
    event_type = Column(String, index=True)  # Add index for filtering
    payload = Column(JSONB)

    test_column = Column(String, nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("idx_user_conversation", "user_id", "conversation_id"),
    )

