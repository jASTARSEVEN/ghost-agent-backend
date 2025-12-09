import os
import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from celery import shared_task
from app.redis_client import redis_client
from app.database import SessionLocal
from app.models import EventModel, ConversationLog
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import select
import redis.exceptions

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Configuration from environment
QUEUE = os.getenv("EVENT_QUEUE_NAME", "event_queue")
DLQ = os.getenv("DLQ_NAME", "event_queue_failed")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))

# Logger for better tracking
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


@shared_task
def save_events_batch(batch_size: int = BATCH_SIZE):
    """Pop events from Redis in batches, normalize, and bulk insert to DB.
    When call_end/call_ended events are detected, aggregate and store complete conversation."""
    r = redis_client
    events: list[dict] = []
    saved, failed = 0, 0
    conversations_to_aggregate = set()  # Track conversation_ids that need aggregation

    # 1) Pull events from Redis
    try:
        for _ in range(batch_size):
            try:
                item = r.rpop(QUEUE)
                if not item:
                    break
                try:
                    event = json.loads(item)
                    events.append(event)
                    # Check if this is a call end event
                    event_type = event.get("event_type") or event.get("type")
                    if event_type in ["call_end", "call_ended"]:
                        conv_id = event.get("conversation_id") or event.get("ws_conversation_id")
                        if conv_id:
                            conversations_to_aggregate.add(conv_id)
                except json.JSONDecodeError:
                    logger.warning(f"Malformed event data: {item}, sending to DLQ")
                    try:
                        r.lpush(DLQ, item)
                        failed += 1
                    except redis.exceptions.RedisError as re:
                        logger.error(f"Failed to send to DLQ: {re}")
            except redis.exceptions.RedisError as re:
                logger.error(f"Redis connection error: {re}")
                break  # Stop processing if Redis is down
    except redis.exceptions.RedisError as re:
        logger.error(f"Redis connection error: {re}")
        return {"saved": 0, "failed": 0}

    if not events:
        logger.info("No events to process.")
        return {"saved": saved, "failed": failed}

    # 2) Sort by timestamp if present
    try:
        events.sort(key=lambda x: datetime.fromisoformat(str(x.get("received_at")).replace("Z", "+00:00")))
    except Exception:
        logger.debug("Skipping sort; timestamps missing or invalid.")

    # 3) Normalize and bulk insert events
    db = SessionLocal()
    try:
        records = []
        for ev in events:
            try:
                ts = ev.get("received_at")
                if ts:
                    try:
                        received_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                    except Exception:
                        received_at = datetime.now(timezone.utc)
                else:
                    received_at = datetime.now(timezone.utc)

                records.append(
                    {
                        "user_id": ev.get("user_id"),
                        "conversation_id": ev.get("conversation_id") or ev.get("ws_conversation_id"),
                        "event_type": ev.get("event_type") or ev.get("type"),
                        "payload": ev,
                        "received_at": received_at,
                    }
                )
            except Exception as e:
                logger.warning(f"Error normalizing event: {e}, sending to DLQ")
                r.lpush(DLQ, json.dumps(ev))
                failed += 1

        if records:
            # Use bulk_insert_mappings for efficient batch insert
            db.bulk_insert_mappings(EventModel, records)
            db.commit()
            saved = len(records)
            logger.info(f"✅ Saved {saved} events to DB")

        # 4) Aggregate and store complete conversations for ended calls
        # Use a separate session for aggregation to ensure isolation
        if conversations_to_aggregate:
            for conv_id in conversations_to_aggregate:
                try:
                    # Create a new session for aggregation to ensure transaction isolation
                    agg_db = SessionLocal()
                    try:
                        aggregate_and_store_conversation(agg_db, conv_id)
                    finally:
                        agg_db.close()
                except Exception as e:
                    logger.error(f"Error aggregating conversation {conv_id}: {e}", exc_info=True)

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {e}", exc_info=True)
        for event in events:
            try:
                r.lpush(DLQ, json.dumps(event))
            except Exception:
                pass
        failed = len(events)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB error: {e}", exc_info=True)
        for event in events:
            try:
                r.lpush(DLQ, json.dumps(event))
            except Exception:
                pass
        failed = len(events)
    except Exception as e:
        logger.error(f"Unexpected error in save_events_batch: {e}", exc_info=True)
        db.rollback()
        for event in events:
            try:
                r.lpush(DLQ, json.dumps(event))
            except Exception:
                pass
        failed = len(events)
    finally:
        db.close()

    return {"saved": saved, "failed": failed}


def aggregate_and_store_conversation(db: "Session", conversation_id: str):
    """Aggregate all events for a conversation and store in conversation_log table."""
    try:
        # Fetch all events for this conversation, ordered by timestamp
        stmt = select(EventModel).where(
            EventModel.conversation_id == conversation_id
        ).order_by(EventModel.received_at.asc())
        
        result = db.execute(stmt)
        events = result.scalars().all()
        
        if not events:
            logger.warning(f"No events found for conversation {conversation_id}")
            return
        
        # Extract user_id from first event
        user_id = events[0].user_id
        if not user_id:
            logger.error(f"user_id is None for conversation {conversation_id}, skipping aggregation")
            return
        
        # Build events array with all event data
        events_data = []
        started_at = None
        ended_at = None
        
        # Variables to extract from call_started event
        customer = None
        agent = None
        
        for event in events:
            event_dict = {
                "id": str(event.id),
                "event_type": event.event_type,
                "payload": event.payload,
                "received_at": event.received_at.isoformat() if event.received_at else None,
            }
            events_data.append(event_dict)
            
            # Extract data from call_started event
            if event.event_type == "call_started" and event.payload:
                payload = event.payload
                
                # Extract customer data
                if "customer" in payload:
                    customer = payload["customer"]
                
                # Extract agent/employee data
                if "employee" in payload:
                    agent = payload["employee"]
                elif "agent" in payload:
                    agent = payload["agent"]
                
                # Extract started_at from payload if available
                if "started_at" in payload:
                    try:
                        started_at_str = payload["started_at"]
                        started_at = datetime.fromisoformat(str(started_at_str).replace("Z", "+00:00"))
                    except Exception:
                        pass
            
            # Track call lifecycle timestamps
            if event.event_type in ["call_started", "incoming_call_ringing"]:
                if not started_at:
                    started_at = event.received_at
            elif event.event_type in ["call_end", "call_ended"]:
                ended_at = event.received_at
        
        # Check if conversation_log already exists (update) or create new
        existing_log = db.query(ConversationLog).filter(
            ConversationLog.conversation_id == conversation_id
        ).first()
        
        if existing_log:
            # Update existing log
            existing_log.events = events_data
            existing_log.ended_at = ended_at or existing_log.ended_at
            existing_log.updated_at = datetime.now(timezone.utc)
            
            # Update customer/agent data if not already set (preserve existing if call_started wasn't in this batch)
            # Only update if we have new data and existing is empty
            if customer is not None and existing_log.customer is None:
                existing_log.customer = customer
            if agent is not None and existing_log.agent is None:
                existing_log.agent = agent
            if started_at is not None and existing_log.started_at is None:
                existing_log.started_at = started_at
                
            logger.info(f"✅ Updated conversation_log for {conversation_id}")
        else:
            # Create new log
            conversation_log = ConversationLog(
                user_id=user_id,
                conversation_id=conversation_id,
                customer=customer,
                agent=agent,
                events=events_data,
                started_at=started_at,
                ended_at=ended_at,
            )
            db.add(conversation_log)
            logger.info(f"✅ Created conversation_log for {conversation_id} with customer and agent data")
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in aggregate_and_store_conversation: {e}", exc_info=True)
        raise

