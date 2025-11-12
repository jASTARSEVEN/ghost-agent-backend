from celery import Celery
import os
import platform
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Celery configuration
app = Celery(
    "celery_app", 
    broker=os.getenv("REDIS_URL"),  # e.g., "redis://localhost:6379/0"
    backend=os.getenv("REDIS_URL"),  # Optional for result backend
)

app.config_from_object("app.celeryconfig")  # Celery Beat config (optional)
app.autodiscover_tasks(["app.tasks"])  # Automatically discover tasks in app.tasks

# On Windows, the default prefork pool is not supported reliably.
# Use a safe default pool, allowing overrides via environment variables.
if platform.system() == "Windows":
    app.conf.worker_pool = os.getenv("CELERY_WORKER_POOL", "solo")
    # Concurrency is ignored by solo, but respected by threads
    app.conf.worker_concurrency = int(os.getenv("CELERY_CONCURRENCY", "1"))
