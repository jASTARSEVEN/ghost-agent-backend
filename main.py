from fastapi import FastAPI
from authentication import routes as auth_routes
from database import Base, engine
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from chat.socket import manager

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ghost Agent Backend")

app.include_router(auth_routes.router)

@app.get("/")
def health_check():
    return {"status": "ok", "message": "Ghost Agent Backend Running"}



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received: {data}")
            await manager.send_personal_message(f"Echo: {data}", websocket)
            await manager.broadcast(f"Broadcast: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)