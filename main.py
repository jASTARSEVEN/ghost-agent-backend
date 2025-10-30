from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from authentication.routes import auth_router, user_router
from chat import routes as ws_routes



app = FastAPI(title="Ghost Agent Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(ws_routes.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Ghost Agent Backend Running"}