"""
Simplified conversation processor for compliance evaluation.
Focuses on dialogue and successful tool calls only.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from chat.models import EventModel

logger = logging.getLogger(__name__)


class ConversationData:
    """Simplified conversation data for compliance evaluation"""
    
    def __init__(self):
        self.conversation_id: str = None
        self.user_id: str = None
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
        self.is_completed: bool = False
        self.duration_seconds: Optional[int] = None
        
        # Simplified data structures
        self.dialogue: List[Dict[str, Any]] = []  # CSR and customer statements
        self.tools_used: List[Dict[str, Any]] = []  # Successful tool calls only
        
        # Counts
        self.total_events: int = 0
        self.total_turns: int = 0
        self.total_tool_calls: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "metadata": {
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "ended_at": self.ended_at.isoformat() if self.ended_at else None,
                "is_completed": self.is_completed,
                "duration_seconds": self.duration_seconds,
                "total_events": self.total_events,
                "total_turns": self.total_turns,
                "total_tool_calls": self.total_tool_calls
            },
            "dialogue": self.dialogue,
            "tools_used": self.tools_used
        }


async def process_conversation_events(
    conversation_id: str,
    db: AsyncSession
) -> ConversationData:
    """
    Process conversation events into simplified evaluation-ready format.
    
    Args:
        conversation_id: The conversation ID to process
        db: Database session
        
    Returns:
        ConversationData object with dialogue and tools
        
    Raises:
        ValueError: If no events found or conversation is invalid
    """
    logger.info(f"Processing conversation: {conversation_id}")
    
    stmt = select(EventModel).where(
        EventModel.conversation_id == conversation_id
    ).order_by(EventModel.received_at.asc())
    
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    if not events:
        raise ValueError(f"No events found for conversation {conversation_id}")
    
    logger.info(f"Found {len(events)} events")
    
    conversation_data = ConversationData()
    conversation_data.conversation_id = conversation_id
    conversation_data.user_id = events[0].user_id
    conversation_data.total_events = len(events)
    
    dialogue_sequence = 0
    
    for event in events:
        event_type = event.event_type
        payload = event.payload or {}
        
        if event_type == "transcript_turn":
            speaker = _normalize_speaker(payload.get("speaker", "unknown"))
            text = _extract_text(payload)
            
            if text:  
                dialogue_sequence += 1
                conversation_data.dialogue.append({
                    "event_id": str(event.id),
                    "sequence": dialogue_sequence,
                    "speaker": speaker,
                    "text": text,
                    "timestamp": _format_timestamp(event.received_at)
                })
                conversation_data.total_turns += 1
        
        elif event_type == "mcp_tool_call":
            state = payload.get("state", "unknown")
            
            if state == "success":
                tool_name = payload.get("tool_name") or payload.get("name") or "unknown_tool"
                conversation_data.tools_used.append({
                    "event_id": str(event.id),
                    "tool_name": tool_name,
                    "timestamp": _format_timestamp(event.received_at),
                    "result": payload.get("result")
                })
                conversation_data.total_tool_calls += 1
        
        elif event_type in ["call_started", "incoming_call_ringing"]:
            if not conversation_data.started_at:
                conversation_data.started_at = event.received_at
        
        elif event_type in ["call_end", "call_ended"]:
            conversation_data.ended_at = event.received_at
            conversation_data.is_completed = True
    
    if not conversation_data.started_at and events:
        conversation_data.started_at = events[0].received_at
    
    if conversation_data.started_at and conversation_data.ended_at:
        conversation_data.duration_seconds = int(
            (conversation_data.ended_at - conversation_data.started_at).total_seconds()
        )
    
    logger.info(
        f"Processed: {conversation_data.total_turns} turns, "
        f"{conversation_data.total_tool_calls} tools, "
        f"completed={conversation_data.is_completed}"
    )
    
    return conversation_data


def _normalize_speaker(speaker: str) -> str:
    """Normalize speaker labels to 'CSR' or 'customer'"""
    speaker_lower = speaker.lower()
    
    if speaker_lower in ["agent", "csr", "representative", "rep"]:
        return "CSR"
    elif speaker_lower in ["customer", "caller", "user", "client"]:
        return "customer"
    else:
        return "unknown"


def _extract_text(payload: Dict) -> str:
    """Extract text from payload with multiple possible keys"""
    return (
        payload.get("text") or 
        payload.get("transcript") or 
        payload.get("content") or 
        ""
    ).strip()


def _format_timestamp(dt: datetime) -> str:
    """Format timestamp as HH:MM:SS"""
    return dt.strftime("%H:%M:%S")


async def validate_conversation_for_evaluation(
    conversation_data: ConversationData
) -> None:
    """
    Validate that conversation is ready for evaluation.
    
    Args:
        conversation_data: Processed conversation data
        
    Raises:
        ValueError: If conversation is not suitable for evaluation
    """
    if not conversation_data.is_completed:
        raise ValueError(
            f"Cannot evaluate ongoing conversation {conversation_data.conversation_id}. "
            "Please wait until call ends."
        )
    
    if conversation_data.total_turns == 0:
        raise ValueError(
            f"Conversation {conversation_data.conversation_id} has no dialogue turns. "
            "Nothing to evaluate."
        )
    
    if not conversation_data.started_at:
        raise ValueError(
            f"Conversation {conversation_data.conversation_id} has no start time. "
            "Cannot determine conversation boundaries."
        )
    
    logger.info(f"Conversation {conversation_data.conversation_id} validated for evaluation")
