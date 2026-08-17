from uuid import UUID
from pydantic import BaseModel, Field

class CreateRoomRequest(BaseModel):
    name: str | None = None
    noOfPlayers: int | None = 6
    isAdmin: bool | None = True

class CreateRoomResponse(BaseModel):
    room_id: str

class JoinRoomRequest(BaseModel):
    room_id: str
    player_name: str = Field(..., max_length=30)

class JoinRoomResponse(BaseModel):
    player_id: UUID
    room_id: str

class LeaveRoomRequest(BaseModel):
    room_id: str
    player_id: UUID

class ReadyRoomRequest(BaseModel):
    room_id: str
    player_id: UUID
    is_ready: bool | None = None

class StartGameRequest(BaseModel):
    room_id: str

class DrawDeckRequest(BaseModel):
    room_id: str
    player_id: UUID

class DrawDiscardRequest(BaseModel):
    room_id: str
    player_id: UUID

class DiscardCardRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class EndTurnRequest(BaseModel):
    room_id: str
    player_id: UUID

class CaboRequest(BaseModel):
    room_id: str
    player_id: UUID

class LookSelfRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class LookOtherRequest(BaseModel):
    room_id: str
    player_id: UUID
    target_player: UUID
    card_id: UUID

class BlindSwapRequest(BaseModel):
    room_id: str
    player_id: UUID
    player1: UUID
    card1: UUID
    player2: UUID
    card2: UUID

class LookAndSwapRequest(BaseModel):
    room_id: str
    player_id: UUID
    player1: UUID
    card1: UUID
    player2: UUID
    card2: UUID
    look_at: UUID

class KingDiscardRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class StickyRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class GiveCardRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class PowerLookRequest(BaseModel):
    room_id: str
    player_id: UUID
    target_card_id: UUID

class PowerSwapRequest(BaseModel):
    room_id: str
    player_id: UUID
    card1_id: UUID
    card2_id: UUID

class PowerDiscardRequest(BaseModel):
    room_id: str
    player_id: UUID
    card_id: UUID

class SuccessResponse(BaseModel):
    success: bool
    message: str | None = None