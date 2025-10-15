import asyncio, logging
from typing import Dict, Set, Any
from fastapi import APIRouter, WebSocket

log = logging.getLogger("websocket")
router = APIRouter()

class Connection:
    def __init__(self, websocket: WebSocket, user_id: str, role: str):
        self.ws = websocket
        self.user_id = user_id
        self.role = role
        self.send_q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Set[Connection]] = {}
        self.lock = asyncio.Lock()

    async def register(self, conn: Connection):
        async with self.lock:
            self.rooms.setdefault(conn.user_id, set()).add(conn)
            log.info(f"{conn.role} joined room {conn.user_id}")

    async def unregister(self, conn: Connection):
        async with self.lock:
            conns = self.rooms.get(conn.user_id)
            if conns and conn in conns:
                conns.remove(conn)
                if not conns:
                    self.rooms.pop(conn.user_id)
            log.info(f"{conn.role} left room {conn.user_id}")

    async def broadcast(self, user_id: str, message: dict[str, Any]):
        """Send message to all connections in the user's room."""
        if user_id not in self.rooms:
            return
        for conn in list(self.rooms[user_id]):
            try:
                conn.send_q.put_nowait(message)
            except asyncio.QueueFull:
                log.warning(f"Send queue full for {conn.role} in room {user_id}")

room_manager = RoomManager()