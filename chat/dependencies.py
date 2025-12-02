# backend/chat/dependencies.py
from celery_service.app.database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
