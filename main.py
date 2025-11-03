from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from authentication.routes.users import user_router
from authentication.routes.auth import auth_router
from authentication.routes.roles import role_router
from authentication.routes.permissions import permission_router
from chat import routes as ws_routes
from common.config import settings


app = FastAPI(
    title=settings.APP_NAME,
    description="Mediverse Backend APIs",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with prefix
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(role_router, prefix="/api")
app.include_router(permission_router, prefix="/api")
app.include_router(ws_routes.router)