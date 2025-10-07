from fastapi import FastAPI
from authentication import routes as auth_routes
from database import Base, engine
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from datetime import datetime
from chat.socket import manager

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ghost Agent Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow any domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            try:
                data_json = json.loads(data)
                print("Received message:", data_json)

                # Construct broadcast message
                if data_json.get("type") == "transcript" or data_json.get("speaker") or data_json.get("text"):
                    broadcast_message = {
                        "type": "transcript",
                        "speaker": data_json.get("speaker", "unknown"),
                        "text": data_json.get("text") or data_json.get("message", ""),
                        "isCustomer": data_json.get("isCustomer", False),
                        "conversationId": data_json.get("conversationId", "default"),
                        "timestamp": datetime.utcnow().isoformat(),
                        "source": "DataRippleAI"
                    }
                    print(f"Transcript data: [{broadcast_message['speaker']}] {broadcast_message['text']}")
                else:
                    broadcast_message = {
                        "type": "broadcast",
                        "originalMessage": data_json,
                        "timestamp": datetime.utcnow().isoformat(),
                        "server": "DataRippleAI WebSocket Server",
                        "clientCount": len(manager.active_connections)
                    }

                await manager.broadcast(broadcast_message)
                print(f"Broadcasted message to {len(manager.active_connections)} clients")

            except json.JSONDecodeError:
                print("Received raw message:", data)
                broadcast_message = {
                    "type": "broadcast",
                    "originalMessage": data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "server": "DataRippleAI WebSocket Server",
                    "clientCount": len(manager.active_connections)
                }
                await manager.broadcast(broadcast_message)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)