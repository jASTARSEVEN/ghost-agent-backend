import os
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from authentication.routes.users import user_router
from authentication.routes.auth import auth_router
from authentication.routes.roles import role_router
from authentication.routes.permissions import permission_router
from chat import routes as ws_routes
from common.config import settings
from actions.routes import router as actions_router
from compliance.routes import router as compliance_router

from vonage_connector.webhooks import router as vonage_webhook_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description="GhostAgent Backend APIs",
    version="1.0.0"
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# CORS Middleware - Load allowed origins from environment
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# @app.on_event("startup")
# async def validate_config():
#     """Validate critical configuration on startup"""
#     errors = []
    
#     if not settings.DATABASE_URL:
#         errors.append("DATABASE_URL is required")
#     if not settings.SECRET_KEY:
#         errors.append("SECRET_KEY is required")
#     if len(settings.SECRET_KEY) < 32:
#         errors.append("SECRET_KEY must be at least 32 characters")
    
#     if errors:
#         raise RuntimeError(f"Configuration errors: {', '.join(errors)}")
    
#     logger.info("Configuration validated successfully")


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    from database import engine
    from sqlalchemy import text
    
    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    redis_status = "healthy"
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded",
        "database": db_status,
        "redis": redis_status,
    }

# Include routers with prefix
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(role_router, prefix="/api")
app.include_router(permission_router, prefix="/api")
app.include_router(ws_routes.router)
app.include_router(actions_router, prefix="/api")
app.include_router(compliance_router, prefix="/api") 
app.include_router(vonage_webhook_router)

# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)