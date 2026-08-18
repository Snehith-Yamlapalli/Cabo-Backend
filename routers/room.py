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

    clean_name = req.player_name.strip()[:10]

    # Re-connection check: if a player with this name already exists in the room, re-attach them to their previous data
    existing_player = next((p for p in game.players if p.name.strip().lower() == clean_name.lower()), None)
    if existing_player:
        await ws_manager.broadcast(req.room_id, game.model_dump(mode="json"))
        return JoinRoomResponse(
            room_id=req.room_id,
            player_id=existing_player.id,
        )

    if len(game.players) >= game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Room {req.room_id} is full",
        )

    player = Player(name=clean_name)
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
    if game.phase not in ("lobby", "finished"):
        # During an active round, only sitting-out players (with 0 cards) can toggle ready for next round
        player_hand = game.hands.get(req.player_id, [])
        valid_cards = [c for c in player_hand if c is not None]
        if len(valid_cards) > 0:
            raise HTTPException(status_code=400, detail="Active players cannot toggle ready during a round")

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