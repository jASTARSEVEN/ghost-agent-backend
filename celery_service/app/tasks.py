import os
import json
import logging
from datetime import datetime, timezone
from celery import shared_task
from app.redis_client import redis_client
from app.database import SessionLocal
from app.models import EventModel
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import redis.exceptions

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
    """Pop events from Redis in batches, normalize, and bulk insert to DB."""
    r = redis_client
    events: list[dict] = []
    saved, failed = 0, 0

    # 1) Pull events from Redis
    try:
        for _ in range(batch_size):
            try:
                item = r.rpop(QUEUE)
                if not item:
                    break
                try:
                    events.append(json.loads(item))
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

    # 3) Normalize and bulk insert
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

        if not records:
            logger.info("No valid events after normalization.")
            return {"saved": saved, "failed": failed}

        # Use bulk_insert_mappings for efficient batch insert
        db.bulk_insert_mappings(EventModel, records)
        db.commit()
        saved = len(records)
        logger.info(f"✅ Saved {saved} events to DB (schema: testdb)")
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

