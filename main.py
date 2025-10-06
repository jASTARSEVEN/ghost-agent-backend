from fastapi import FastAPI
from authentication import routes as auth_routes
from database import Base, engine
from dotenv import load_dotenv

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ghost Agent Backend")

app.include_router(auth_routes.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Ghost Agent Backend Running"}