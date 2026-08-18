from __future__ import annotations
from typing import Dict, List, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class Player(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., max_length=10)
    score: int = 0
    round_score: int = 0
    is_admin: bool = False
    is_ready: bool = False
    called_cabo: bool = False

Rank = Literal[
    "A",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "J",
    "Q",
    "K"
]
Suit = Literal[
    "spade",
    "club",
    "diamond",
    "heart"
]
Color = Literal[
    "red",
    "black"
]

class Card(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    rank: Rank
    suit: Suit
    color: Color
    visible_to: List[UUID] = Field(default_factory=list)
    reveal_end_time: float | None = None

PendingAction = Literal[
    "none",
    "draw",
    "discard",
    "look_self",
    "look_other",
    "blind_swap",
    "look_and_swap",
    "discard_self",
    "sticky",
    "finished"
]

class TurnState(BaseModel):
    picked_card: Card | None = None
    drawn_from: Literal["deck", "discard", "none"] = "none"
    first_swap_target: UUID | None = None
    pending_action: PendingAction = "draw"
    power_used: bool = False

class StickyResolution(BaseModel):
    giver_id: UUID
    receiver_id: UUID

GamePhase = Literal[
    "lobby",
    "peeking",
    "playing",
    "cabo_round",
    "finished"
]

class LocalGame(BaseModel):
    room_id: str
    max_players: int = 6
    phase: GamePhase = "lobby"
    round_number: int = 1
    peek_end_time: float | None = None
    cabo_caller_index: int | None = None
    players: List[Player] = Field(default_factory=list)
    hands: Dict[UUID, List[Optional[Card]]] = Field(default_factory=dict)
    draw_pile: List[Card] = Field(default_factory=list)
    discard_pile: List[Card] = Field(default_factory=list)
    last_discard_was_sticky: bool = False
    active_resolutions: List[StickyResolution] = Field(default_factory=list)
    current_turn: int = 0
    turn: TurnState = Field(default_factory=TurnState)
    scores: Dict[UUID, int] = Field(default_factory=dict)
    last_action_log: str | None = None
    last_activity: float = Field(default_factory=lambda: __import__('time').time())


class GlobalGame(BaseModel):
    games: Dict[str, LocalGame] = Field(default_factory=dict)