# import os
# import json
# from datetime import datetime
# from celery import shared_task
# from app.redis_client import redis_client  # use single shared redis instance
# from app.database import SessionLocal
# from app.models import EventModel

# QUEUE = os.getenv("EVENT_QUEUE_NAME", "event_queue")
# DLQ = os.getenv("DLQ_NAME", "event_queue_failed")
# BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))


# @shared_task
# def save_events_batch(batch_size: int = BATCH_SIZE):
#     """Bulk pop events from Redis, sort by timestamp, insert into DB, push failed ones to DLQ."""

#     r = redis_client
#     events = []

#     # 1️⃣ Pull events from Redis
#     for _ in range(batch_size):
#         item = r.rpop(QUEUE)
#         if not item:
#             break
#         try:
#             events.append(json.loads(item))
#         except Exception:
#             r.lpush(DLQ, item)  # malformed → send to DLQ
#             continue

#     if not events:
#         return {"saved": 0, "error": 0}

#     # 2️ Sort by received_at timestamp 
#     try:
#         events.sort(key=lambda x: datetime.fromisoformat(x["received_at"]))
#     except Exception:
#         pass  # if some events don't contain timestamp, keep original order

#     # 3️ Bulk insert into SQLite
#     db = SessionLocal()
#     saved, failed = 0, 0

#     try:
#         db.bulk_insert_mappings(EventModel, events)
#         db.commit()
#         saved = len(events)

#     except Exception as e:
#         db.rollback()
#         failed = len(events)
#         for e in events:
#             r.lpush(DLQ, json.dumps(e))  # Push all failed batch items to DLQ

#     finally:
#         db.close()

#     return {"saved": saved, "failed": failed}
import os
import json
import logging
from datetime import datetime
from celery import shared_task
from app.redis_client import redis_client  # use single shared redis instance
from app.database import SessionLocal
from app.models import EventModel
from sqlalchemy.exc import SQLAlchemyError, IntegrityError  # For better DB exception handling

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
    """Bulk pop events from Redis, sort by timestamp, insert into DB, push failed ones to DLQ."""
    r = redis_client
    events = []
    saved, failed = 0, 0

    # 1️⃣ Pull events from Redis
    for _ in range(batch_size):
        item = r.rpop(QUEUE)
        if not item:
            break
        try:
            events.append(json.loads(item))
        except json.JSONDecodeError:
            logger.warning(f"Malformed event data: {item}, sending to DLQ")
            r.lpush(DLQ, item)  # malformed → send to DLQ
            failed += 1
            continue

    if not events:
        logger.info("No events to process.")
        return {"saved": saved, "failed": failed}

    # 2️⃣ Sort by received_at timestamp (if possible)
    try:
        events.sort(key=lambda x: datetime.fromisoformat(x["received_at"]))
    except Exception:
        logger.warning("Failed to sort events by timestamp, keeping original order")

    # 3️⃣ Bulk insert into PostgreSQL
    db = SessionLocal()

    try:
        # Insert events into the database
        db.bulk_insert_mappings(EventModel, events)
        db.commit()
        saved = len(events)
        logger.info(f"Successfully saved {saved} events to the database.")
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error occurred while saving events: {str(e)}")
        # Push all events to the DLQ on failure
        for event in events:
            r.lpush(DLQ, json.dumps(event))
        failed = len(events)
        logger.info(f"Pushed {failed} events to DLQ due to IntegrityError.")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error occurred while saving events: {str(e)}")
        # Push all events to the DLQ on failure
        for event in events:
            r.lpush(DLQ, json.dumps(event))
        failed = len(events)
        logger.info(f"Pushed {failed} events to DLQ due to general DB failure.")
    finally:
        db.close()

    return {"saved": saved, "failed": failed}
