from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from routers.room import router as room_router
from routers.game import router as game_router
<<<<<<< HEAD
from dependencies import game_manager, ws_manager
=======
from dependencies import game_manager
import os
>>>>>>> 3330243ce7168bca896bbef8bfa31dab31c0cd91

app = FastAPI(
    title="Cabo Backend",
    version="1.0.0",
)

<<<<<<< HEAD
import os

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS,
=======
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
>>>>>>> 3330243ce7168bca896bbef8bfa31dab31c0cd91
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(room_router, prefix="/room", tags=["Room"])
app.include_router(game_router, prefix="/game", tags=["Game"])

@app.middleware("http")
async def save_state_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        game_manager.save()
    return response

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    """WebSocket endpoint for real-time game state updates."""
    game = game_manager.get_game(room_id)
    if game is None:
        await websocket.close(code=4404)
        return

    await ws_manager.connect(room_id, websocket)

    # Send initial state immediately on connect
    try:
        await websocket.send_json(game.model_dump(mode="json"))
    except Exception:
        ws_manager.disconnect(room_id, websocket)
        return

    # Schedule any active timers (peek expiry, card reveal expiry)
    ws_manager.schedule_game_timers(room_id, game)

    # Keep connection alive — all game actions go through HTTP POST,
    # this loop just waits for client disconnect or ping messages.
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(room_id, websocket)

@app.get("/")
def root():
    return {
        "message": "Cabo Backend API",
        "status": "running",
    }