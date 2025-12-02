
# import os
# from dotenv import load_dotenv
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from .db_base import Base

# load_dotenv()

# # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # os.makedirs(BASE_DIR, exist_ok=True)

# # DB_PATH = os.path.join(BASE_DIR, "events.db")
# # DATABASE_URL = f"sqlite:///{DB_PATH}"

# DATABASE_URL = os.getenv(
#     "DATABASE_URL",
#     "sqlite:////app/conversation_db/events.db"
# )


# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
# SessionLocal = sessionmaker(bind=engine)

# Base.metadata.create_all(engine)
  

# def save_many_events(events: list):
#     """Save events to the database."""
#     if not events:
#         return

#     from .models import EventModel  
#     session = SessionLocal()
#     try:
#         for ev in events:
#             row = EventModel(
#                 user_id=ev.get("user_id"),
#                 ws_conversation_id=ev.get("ws_conversation_id"),
#                 call_id=ev.get("call_id"),
#                 event_type=ev.get("event_type") or ev.get("type"),
#                 payload=ev
#             )
#             session.add(row)

#         session.commit()
#         print(f" Saved {len(events)} events")
#     except Exception as e:
#         session.rollback()
#         print(f" DB Error: {e}")
#     finally:
#         session.close()


import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .db_base import Base

load_dotenv()

# Use sync Postgres (not asyncpg)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "+asyncpg" in DATABASE_URL:
    # Celery uses a sync engine; switch to psycopg2 driver
    DATABASE_URL = DATABASE_URL.replace("+asyncpg", "+psycopg2")

# Create sync engine for Celery workers
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"options": "-csearch_path=ghostagent,public"},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Do not create tables here; use Alembic migrations to manage schema


def save_many_events(events: list):
    """Save events to the database (used by Celery tasks)."""
    if not events:
        return

    from .models import EventModel
    session = SessionLocal()
    try:
        for ev in events:
            row = EventModel(
                user_id=ev.get("user_id"),
                conversation_id=ev.get("conversation_id") or ev.get("ws_conversation_id"),
                
                event_type=ev.get("event_type") or ev.get("type"),
                payload=ev,
            )
            session.add(row)

        session.commit()
        print(f" [CELERY] Saved {len(events)} events")

    except Exception as e:
        session.rollback()
        print(f" [CELERY] DB Error:", e)

    finally:
        session.close()
