import os
import json
import logging
from datetime import datetime
from celery import shared_task
from app.redis_client import redis_client
from app.database import SessionLocal
from app.models import EventModel
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

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
    for _ in range(batch_size):
        item = r.rpop(QUEUE)
        if not item:
            break
        try:
            events.append(json.loads(item))
        except json.JSONDecodeError:
            logger.warning(f"Malformed event data: {item}, sending to DLQ")
            r.lpush(DLQ, item)
            failed += 1

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
                        received_at = datetime.utcnow()
                else:
                    received_at = datetime.utcnow()

                records.append(
                    {
                        "user_id": ev.get("user_id"),
                        "conversation_id": ev.get("conversation_id") or ev.get("ws_conversation_id"),
                        "call_id": ev.get("call_id"),
                        "event_type": ev.get("event_type") or ev.get("type"),
                        "payload": ev,
                        "received_at": received_at,
                    }
                )
            except Exception:
                r.lpush(DLQ, json.dumps(ev))

        if not records:
            logger.info("No valid events after normalization.")
            return {"saved": saved, "failed": failed}

        db.bulk_insert_mappings(EventModel, records)
        db.commit()
        saved = len(records)
        logger.info(f"Saved {saved} events to DB.")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {e}")
        for event in events:
            r.lpush(DLQ, json.dumps(event))
        failed = len(events)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB error: {e}")
        for event in events:
            r.lpush(DLQ, json.dumps(event))
        failed = len(events)
    finally:
        db.close()

    return {"saved": saved, "failed": failed}

