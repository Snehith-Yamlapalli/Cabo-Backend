from fastapi import APIRouter, HTTPException
from dependencies import game_manager, ws_manager
from engine.local_engine import GameEngine

from schemas import (
    StartGameRequest,
    DrawDeckRequest,
    DrawDiscardRequest,
    DiscardCardRequest,
    EndTurnRequest,
    CaboRequest,
    StickyRequest,
    GiveCardRequest,
    PowerLookRequest,
    PowerSwapRequest,
    PowerDiscardRequest,
)

router = APIRouter()


async def _broadcast(room_id: str, game):
    """Broadcast game state to all WebSocket clients and schedule any active timers."""
    await ws_manager.broadcast(room_id, game.model_dump(mode="json"))
    ws_manager.schedule_game_timers(room_id, game)


@router.post("/start")
async def start_game(req: StartGameRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.start(game)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/draw/deck")
async def draw_from_deck(req: DrawDeckRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        card = GameEngine.draw_from_deck(game, req.player_id)
        await _broadcast(req.room_id, game)
        return card
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/draw/discard")
async def draw_from_discard(req: DrawDiscardRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        card = GameEngine.draw_from_discard(game, req.player_id)
        await _broadcast(req.room_id, game)
        return card
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/discard")
async def discard(req: DiscardCardRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.replace_card(game, req.player_id, req.card_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/discard/picked")
async def discard_picked(req: EndTurnRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.discard_picked(game)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/turn/end")
async def end_turn(req: EndTurnRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.next_turn(game)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cabo")
async def call_cabo(req: CaboRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.call_cabo(game, req.player_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sticky")
async def call_sticky(req: StickyRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.sticky(game, req.player_id, req.card_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/give_card")
async def give_card(req: GiveCardRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.give_card(game, req.player_id, req.card_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/power/look")
async def power_look(req: PowerLookRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.power_look(game, req.player_id, req.target_card_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/power/swap")
async def power_swap(req: PowerSwapRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.power_swap(game, req.player_id, req.card1_id, req.card2_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/power/discard")
async def power_discard(req: PowerDiscardRequest):
    game = game_manager.get_game(req.room_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Room not found")
    try:
        GameEngine.power_discard(game, req.player_id, req.card_id)
        await _broadcast(req.room_id, game)
        return game
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))