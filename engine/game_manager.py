from __future__ import annotations
import secrets
from models import GlobalGame, LocalGame, Player

class GameManager:
    """
    Manages every active room/game on the server.
    """
    def __init__(self):
        self.games = GlobalGame()
        self.load()

    def save(self):
        try:
            with open("game_data.json", "w") as f:
                f.write(self.games.model_dump_json())
        except Exception as e:
            print(f"Failed to save game data: {e}")

    def load(self):
        import os
        if os.path.exists("game_data.json"):
            try:
                with open("game_data.json", "r") as f:
                    self.games = GlobalGame.model_validate_json(f.read())
            except Exception as e:
                print(f"Failed to load game data: {e}")

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------

    def _generate_room_id(self) -> str:
        while True:
            room = f"{secrets.randbelow(1_000_000):06d}"
            if room not in self.games.games:
                return room

    # -------------------------------------------------------
    # Room Management
    # -------------------------------------------------------

    def create_room(self, max_players: int = 6) -> str:
        room = self._generate_room_id()
        game = LocalGame(room_id=room, max_players=max_players)
        self.games.games[room] = game
        return room

    def destroy_room(self, room_id: str) -> bool:
        if room_id not in self.games.games:
            return False
        del self.games.games[room_id]
        return True

    # -------------------------------------------------------
    # Lookup
    # -------------------------------------------------------

    def get_game(self, room_id: str) -> LocalGame | None:
        import time
        game = self.games.games.get(room_id)
        if game is None:
            return None
        game.last_activity = time.time()
        self.cleanup_inactive(600)
        # Clean up expired card reveals
        now = time.time()
        for hand in game.hands.values():
            for card in hand:
                if card and card.reveal_end_time and now >= card.reveal_end_time:
                    card.visible_to.clear()
                    card.reveal_end_time = None
        if game.phase == "peeking":
            from engine.local_engine import GameEngine
            if game.peek_end_time and time.time() >= game.peek_end_time:
                GameEngine.end_peeking(game)
        return game

    # -------------------------------------------------------
    # Players
    # -------------------------------------------------------

    def join_room(self, room_id: str, player: Player) -> bool:
        game = self.get_game(room_id)
        if game is None:
            return False
        if len(game.players) >= game.max_players:
            return False
        # Reject duplicate player names (case-insensitive)
        if any(p.name.strip().lower() == player.name.strip().lower() for p in game.players):
            return False
        if not game.players:
            player.is_admin = True
            player.is_ready = True
        else:
            player.is_ready = False
        game.players.append(player)
        game.hands[player.id] = []
        return True

    def toggle_ready(self, room_id: str, player_id, is_ready: bool | None = None) -> bool:
        game = self.get_game(room_id)
        if game is None:
            return False
        for p in game.players:
            if str(p.id).lower() == str(player_id).lower():
                if is_ready is not None:
                    p.is_ready = is_ready
                else:
                    p.is_ready = not p.is_ready
                return True
        return False

    def leave_room(self, room_id: str, player_id) -> bool:
        game = self.get_game(room_id)
        if game is None:
            return False
        leaving_player = None
        for player in game.players:
            if str(player.id).lower() == str(player_id).lower():
                leaving_player = player
                break
        if leaving_player is None:
            return False

        # During active round: mark as left and auto-advance turn if it was their turn!
        if game.phase in ("peeking", "playing", "cabo_round"):
            leaving_player.is_ready = False
            leaving_player.has_left = True
            leaving_player.is_connected = False

            from engine.local_engine import GameEngine
            is_current_turn = False
            if 0 <= game.current_turn < len(game.players):
                is_current_turn = game.players[game.current_turn].id == leaving_player.id

            if is_current_turn:
                game.last_action_log = f"{leaving_player.name} left the game. Turn skipped!"
                GameEngine.next_turn(game)
            else:
                game.last_action_log = f"{leaving_player.name} left the game."

            # Check if active player count dropped to 1
            active_players = [p for p in game.players if getattr(p, "is_connected", True) and not getattr(p, "has_left", False)]
            if len(active_players) <= 1 and game.phase in ("playing", "cabo_round"):
                GameEngine.finish_game(game)
                game.last_action_log = "All opponents left the game! Match finished!"

            self.save()
            return True

        # In lobby or finished state: remove player from room
        game.players.remove(leaving_player)
        game.hands.pop(player_id, None)
        
        if leaving_player.is_admin and game.players:
            game.players[0].is_admin = True

        if not game.players:
            self.destroy_room(room_id)
        else:
            self.save()
        return True

    # -------------------------------------------------------
    # Utils
    # -------------------------------------------------------

    def room_exists(self, room_id: str) -> bool:
        return room_id in self.games.games

    def room_size(self, room_id: str) -> int:
        game = self.get_game(room_id)
        if game is None:
            return 0
        return len(game.players)

    def cleanup_inactive(self, timeout_seconds: float = 600):
        """Remove rooms with no activity for timeout_seconds (default 10 min)."""
        import time
        now = time.time()
        to_remove = [
            room_id for room_id, game in self.games.games.items()
            if now - game.last_activity > timeout_seconds
        ]
        for room_id in to_remove:
            print(f"Cleaning up inactive room {room_id}")
            del self.games.games[room_id]
        if to_remove:
            self.save()