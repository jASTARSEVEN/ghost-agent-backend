from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        client_ip = websocket.client.host
        print(f"New WebSocket connection established")
        print(f"Client IP: {client_ip}")
        print(f"Total connected clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print("WebSocket connection closed")
        print(f"Total connected clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        # Broadcast message to all connected clients
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Error sending to a client: {e}")
                self.active_connections.remove(connection)


manager = ConnectionManager()