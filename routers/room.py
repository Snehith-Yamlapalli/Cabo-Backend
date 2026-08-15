from fastapi import APIRouter, HTTPException
from dependencies import game_manager, ws_manager
from models import Player
from schemas import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    LeaveRoomRequest,
    ReadyRoomRequest,
)

router = APIRouter()

@router.post("/create", response_model=CreateRoomResponse)
def create_room(req: CreateRoomRequest | None = None):
    max_players = req.noOfPlayers if req and req.noOfPlayers else 6
    room_id = game_manager.create_room(max_players=max_players)
    return CreateRoomResponse(room_id=room_id)

@router.post("/join", response_model=JoinRoomResponse)
async def join_room(req: JoinRoomRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(
            status_code=404,
            detail=f"Room {req.room_id} has been closed or does not exist",
        )
    if game.phase != "lobby":
        raise HTTPException(
            status_code=400,
            detail=f"Game in room {req.room_id} has already started",
        )
    if len(game.players) >= game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Room {req.room_id} is full",
        )
    if any(p.name.strip().lower() == req.player_name.strip().lower() for p in game.players):
        raise HTTPException(
            status_code=400,
            detail=f"A player with the name '{req.player_name}' is already in this room",
        )

    player = Player(name=req.player_name)
    success = game_manager.join_room(req.room_id, player)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Room {req.room_id} has been closed or cannot be joined",
        )
    # Broadcast updated lobby state to all connected clients
    await ws_manager.broadcast(req.room_id, game.model_dump(mode="json"))
    return JoinRoomResponse(
        room_id=req.room_id,
        player_id=player.id,
    )

@router.post("/leave")
async def leave_room(req: LeaveRoomRequest):
    # Get game before leaving to check if room will be destroyed
    game = game_manager.get_game(req.room_id)
    success = game_manager.leave_room(
        req.room_id,
        req.player_id,
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Player or room not found",
        )
    # Broadcast updated state to remaining players (if room still exists)
    game_after = game_manager.get_game(req.room_id)
    if game_after:
        await ws_manager.broadcast(req.room_id, game_after.model_dump(mode="json"))
    return {
        "success": True,
        "message": "Player left room",
    }

@router.post("/ready")
async def toggle_ready(req: ReadyRoomRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if game.phase != "lobby":
        raise HTTPException(status_code=400, detail="Game already started")

    success = game_manager.toggle_ready(req.room_id, req.player_id, req.is_ready)
    if not success:
        raise HTTPException(status_code=404, detail="Player not found")

    await ws_manager.broadcast(req.room_id, game.model_dump(mode="json"))
    return {"success": True}

@router.get("/{room_id}")
def get_room(room_id: str):
    game = game_manager.get_game(room_id)
    if game is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )
    return game

@router.delete("/{room_id}")
async def destroy_room(room_id: str):
    # Notify all WebSocket clients that the room has ended BEFORE destroying
    await ws_manager.broadcast_room_ended(room_id)
    ws_manager.cancel_room_tasks(room_id)
    success = game_manager.destroy_room(room_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Room not found",
        )
    return {
        "success": True,
        "message": "Room destroyed",
    }