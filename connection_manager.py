from __future__ import annotations
import asyncio
import time
from fastapi import WebSocket
from typing import Dict, List


class ConnectionManager:
    """Manages WebSocket connections per room and handles broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._scheduled_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(room_id, []).append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        conns = self.active_connections.get(room_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active_connections.pop(room_id, None)

    async def broadcast(self, room_id: str, data: dict):
        """Send JSON data to all WebSocket clients in a room."""
        dead: List[WebSocket] = []
        for ws in self.active_connections.get(room_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room_id, ws)

    async def broadcast_room_ended(self, room_id: str):
        """Notify all clients that the room has ended, then close connections."""
        for ws in list(self.active_connections.get(room_id, [])):
            try:
                await ws.send_json({"type": "room_ended", "room_id": room_id})
                await ws.close()
            except Exception:
                pass
        self.active_connections.pop(room_id, None)

    def schedule_broadcast(self, room_id: str, delay: float, task_key: str = ""):
        """Schedule a delayed broadcast of the current game state."""
        key = f"{room_id}:{task_key}" if task_key else room_id

        # Cancel existing task with same key
        existing = self._scheduled_tasks.pop(key, None)
        if existing:
            existing.cancel()

        async def _do():
            try:
                await asyncio.sleep(delay)
                from dependencies import game_manager
                game = game_manager.get_game(room_id)
                if game:
                    await self.broadcast(room_id, game.model_dump(mode="json"))
                    game_manager.save()
            except asyncio.CancelledError:
                pass
            finally:
                self._scheduled_tasks.pop(key, None)

        self._scheduled_tasks[key] = asyncio.create_task(_do())

    def schedule_game_timers(self, room_id: str, game):
        """Check for active timers in the game and schedule delayed broadcasts."""
        now = time.time()

        # Peek phase timer
        if game.phase == "peeking" and game.peek_end_time:
            delay = max(0.1, game.peek_end_time - now)
            self.schedule_broadcast(room_id, delay, "peek")

        # Card reveal timers
        for pid, hand in game.hands.items():
            for card in hand:
                if card and card.reveal_end_time and card.reveal_end_time > now:
                    delay = max(0.1, card.reveal_end_time - now)
                    self.schedule_broadcast(room_id, delay, f"reveal:{card.id}")

    def cancel_room_tasks(self, room_id: str):
        """Cancel all scheduled tasks for a room."""
        to_remove = [k for k in self._scheduled_tasks if k.startswith(room_id)]
        for key in to_remove:
            task = self._scheduled_tasks.pop(key, None)
            if task:
                task.cancel()
