from __future__ import annotations
from secrets import SystemRandom
from uuid import UUID
from models import Card, LocalGame, Player
import time

_rng = SystemRandom()

class GameEngine:

    # Helpers
    
    @staticmethod
    def current_player(game: LocalGame) -> Player:
        return game.players[game.current_turn]

    @staticmethod
    def next_turn(game: LocalGame):
        # If the deck has run out of cards, finish the round immediately & reveal all cards!
        if len(game.draw_pile) == 0 and game.phase in ("playing", "cabo_round"):
            GameEngine.finish_game(game)
            game.last_action_log = "The deck has run out of cards! Round ended and all cards revealed!"
            return

        next_turn_index = (game.current_turn + 1) % len(game.players)
        
        # If in cabo round and we loop back to the player who called Cabo, game finishes!
        if game.phase == "cabo_round" and next_turn_index == game.cabo_caller_index:
            GameEngine.finish_game(game)
            return

        game.current_turn = next_turn_index
        game.turn.picked_card = None
        game.turn.first_swap_target = None
        game.turn.pending_action = "draw"
        game.turn.power_used = False

        # If the player whose turn it just became has 0 cards left:
        curr_player = game.players[game.current_turn]
        curr_hand = game.hands.get(curr_player.id, [])
        valid_cards = [c for c in curr_hand if c is not None]
        if len(valid_cards) == 0:
            if game.cabo_caller_index is None and game.phase in ("playing", "cabo_round"):
                curr_player.called_cabo = True
                game.cabo_caller_index = game.current_turn
                game.phase = "cabo_round"
                game.last_action_log = f"{curr_player.name} has 0 cards left! Cabo was automatically called!"
                GameEngine.next_turn(game)
            elif game.phase == "cabo_round":
                # Skip turn during cabo round if player has 0 cards
                GameEngine.next_turn(game)

    @staticmethod
    def card_value(card: Card) -> int:
        if card.rank == "A":
            return 1
        elif card.rank == "J":
            return 11
        elif card.rank == "Q":
            return 12
        elif card.rank == "K":
            return 13
        else:
            return int(card.rank)

    @staticmethod
    def finish_game(game: LocalGame):
        game.phase = "finished"
        game.turn.pending_action = "finished"
        game.turn.picked_card = None

        # Reveal all cards to everyone & calculate scores
        all_player_ids = [p.id for p in game.players]
        for player in game.players:
            player.is_ready = False  # Reset readiness for next round
            hand = game.hands.get(player.id, [])
            round_pts = sum(GameEngine.card_value(card) for card in hand if card is not None)
            for card in hand:
                if card is not None:
                    card.visible_to = list(all_player_ids)
            player.round_score = round_pts
            player.score += round_pts
            game.scores[player.id] = player.score

    # Deck
    
    @staticmethod
    def new_deck():
        deck = []
        suits = ["spade","club","diamond","heart"]
        ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K",]
        for suit in suits:
            color = ("red" if suit in ("heart", "diamond") else "black")
            for rank in ranks:
                deck.append(Card(rank=rank, suit=suit, color=color))
        return deck

    @staticmethod
    def shuffle(game: LocalGame):
        _rng.shuffle(game.draw_pile)

    # Start Game (or Next Round)
    @staticmethod
    def start(game: LocalGame):
        if len(game.players) < 2:
            raise ValueError("Need at least two players")
        
        non_admins = [p for p in game.players if not p.is_admin]
        if non_admins and not all(p.is_ready for p in non_admins):
            raise ValueError("All players must be ready before starting")
        
        if game.phase == "finished":
            game.round_number += 1
        else:
            game.round_number = 1
            for player in game.players:
                player.score = 0
                player.round_score = 0

        for player in game.players:
            player.called_cabo = False

        game.turn.picked_card = None
        game.turn.pending_action = "draw"
        game.turn.power_used = False

        game.draw_pile = GameEngine.new_deck()
        GameEngine.shuffle(game)
        game.hands.clear()
        for player in game.players:
            game.hands[player.id] = []
            for _ in range(4):
                game.hands[player.id].append(game.draw_pile.pop())
            
            # Reveal bottom two cards (indices 2 and 3) to the player
            game.hands[player.id][2].visible_to = [player.id]
            game.hands[player.id][3].visible_to = [player.id]

        game.discard_pile = []
        game.current_turn = _rng.randrange(len(game.players))
        game.phase = "peeking"
        game.peek_end_time = time.time() + 8.0  # 8s card memorization at round start
        game.cabo_caller_index = None

    @staticmethod
    def end_peeking(game: LocalGame):
        if game.phase != "peeking":
            return
        for player_id, hand in game.hands.items():
            for card in hand:
                if card is not None:
                    card.visible_to.clear()
        game.phase = "playing"
        game.peek_end_time = None

        # Check if starting player has 0 cards
        curr_player = game.players[game.current_turn]
        curr_hand = game.hands.get(curr_player.id, [])
        valid_cards = [c for c in curr_hand if c is not None]
        if len(valid_cards) == 0:
            curr_player.called_cabo = True
            game.cabo_caller_index = game.current_turn
            game.phase = "cabo_round"
            game.last_action_log = f"{curr_player.name} has 0 cards left! Cabo was automatically called!"
            GameEngine.next_turn(game)

    # Draw
    
    @staticmethod
    def draw_from_deck(game: LocalGame, player_id: UUID) -> Card | None:
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        if game.turn.picked_card is not None:
            raise ValueError("Already drew")
        if len(game.draw_pile) == 0:
            GameEngine.finish_game(game)
            game.last_action_log = "The deck has run out of cards! Round ended and all cards revealed!"
            return None
        card = game.draw_pile.pop()
        card.visible_to = [player_id]
        game.turn.picked_card = card
        game.turn.drawn_from = "deck"
        game.turn.pending_action = "discard"
        return card

    @staticmethod
    def draw_from_discard(game: LocalGame, player_id: UUID) -> Card:
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        if game.turn.picked_card is not None:
            raise ValueError("Already drew")
        card = game.discard_pile.pop()
        game.turn.picked_card = card
        game.turn.drawn_from = "discard"
        game.turn.pending_action = "discard"
        return card

    @staticmethod
    def get_cabo_caller_id(game: LocalGame) -> UUID | None:
        for p in game.players:
            if p.called_cabo:
                return p.id
        if game.cabo_caller_index is not None and 0 <= game.cabo_caller_index < len(game.players):
            return game.players[game.cabo_caller_index].id
        return None

    @staticmethod
    def has_valid_power_targets(game: LocalGame, rank: str, player_id: UUID) -> bool:
        cabo_caller_id = GameEngine.get_cabo_caller_id(game)
        
        own_hand = game.hands.get(player_id, [])
        valid_own_cards = [c for c in own_hand if c is not None]
        
        non_cabo_opponent_cards = []
        for p in game.players:
            if p.id != player_id and p.id != cabo_caller_id:
                hand = game.hands.get(p.id, [])
                non_cabo_opponent_cards.extend([c for c in hand if c is not None])
                
        if rank in ("7", "8"):
            return len(valid_own_cards) > 0
        elif rank in ("9", "10", "Q", "J"):
            return len(non_cabo_opponent_cards) > 0
        elif rank == "K":
            return len(valid_own_cards) > 0
        return True

    # Discard
    
    @staticmethod
    def discard_picked(game: LocalGame):
        if game.turn.picked_card is None:
            raise ValueError("Nothing picked")
        drawn_from = game.turn.drawn_from
        card = game.turn.picked_card
        card.visible_to = [p.id for p in game.players]
        game.discard_pile.append(card)
        game.last_discard_was_sticky = False
        game.turn.picked_card = None
        game.turn.drawn_from = "none"
        
        if drawn_from == "deck":
            rank = card.rank
            curr_player = GameEngine.current_player(game)
            if rank in ("7", "8", "9", "10", "J", "Q", "K"):
                if not GameEngine.has_valid_power_targets(game, rank, curr_player.id):
                    game.last_action_log = f"{curr_player.name} played {rank}, but no valid target cards are available. Power skipped!"
                    GameEngine.next_turn(game)
                    return

            if rank in ("7", "8"):
                game.turn.pending_action = "look_self"
                return
            elif rank in ("9", "10"):
                game.turn.pending_action = "look_other"
                return
            elif rank == "J":
                game.turn.pending_action = "blind_swap"
                return
            elif rank == "Q":
                game.turn.pending_action = "look_and_swap"
                return
            elif rank == "K":
                game.turn.pending_action = "discard_self"
                return

    # Swap
    
    @staticmethod
    def replace_card(game: LocalGame, player_id: UUID, hand_card_id: UUID):
        picked = game.turn.picked_card
        if picked is None:
            raise ValueError("No picked card")
        hand = game.hands[player_id]
        for i, card in enumerate(hand):
            if card is not None and card.id == hand_card_id:
                hand[i] = picked
                picked.visible_to = []  # card goes face-down in hand
                card.visible_to = [p.id for p in game.players]
                game.discard_pile.append(card)
                game.last_discard_was_sticky = False
                game.turn.picked_card = None
                return
        raise ValueError("Card not found")

    @staticmethod
    def sticky(game: LocalGame, player_id: UUID, card_id: UUID):
        if game.phase not in ("playing", "cabo_round"):
            raise ValueError("Game is not active")
        
        if not game.discard_pile:
            raise ValueError("Discard pile is empty")
            
        discard_top = game.discard_pile[-1]
        
        initiator_hand = game.hands.get(player_id, [])
        valid_cards = [c for c in initiator_hand if c is not None]
        if len(valid_cards) >= 8:
            raise ValueError("Cannot sticky when you have 8 or more cards")

        target_card = None
        target_index = -1
        owner_id = None
        target_hand = None
        
        # Search all hands for the card!
        for p_id, p_hand in game.hands.items():
            for i, card in enumerate(p_hand):
                if card is not None and card.id == card_id:
                    target_hand = p_hand
                    target_card = card
                    target_index = i
                    owner_id = p_id
                    break
            if target_card:
                break
                
        if not target_card:
            raise ValueError("Card not found in any hand")

        cabo_caller_id = GameEngine.get_cabo_caller_id(game)
        if cabo_caller_id and owner_id == cabo_caller_id and player_id != cabo_caller_id:
            raise ValueError("Cannot play sticky on cards of the player who called CABO! Their cards are frozen.")
            
        # Get player names
        player_name = next((p.name for p in game.players if p.id == player_id), "Player")
        owner_name = next((p.name for p in game.players if p.id == owner_id), "Player")
        
        card_str = f"{target_card.suit} {target_card.rank}"
        is_third_party = (owner_id != player_id)
            
        if target_card.rank == discard_top.rank and not game.last_discard_was_sticky:
            target_hand[target_index] = None
            target_card.visible_to = [p.id for p in game.players]
            game.discard_pile.append(target_card)
            game.last_discard_was_sticky = True
            
            if is_third_party:
                from models import StickyResolution
                game.active_resolutions.append(StickyResolution(giver_id=player_id, receiver_id=owner_id))
                game.last_action_log = f"{player_name} played {owner_name}'s {card_str} (Card {target_index + 1}) as Sticky successfully! {player_name} must now give {owner_name} a card."
            else:
                game.last_action_log = f"{player_name} played {card_str} (Card {target_index + 1}) as Sticky successfully!"
        else:
            reason = "but got there too late!" if target_card.rank == discard_top.rank else "but failed!"
            
            if is_third_party:
                game.last_action_log = f"{player_name} played {owner_name}'s {card_str} (Card {target_index + 1}) as Sticky {reason} {player_name} gets a penalty."
            else:
                game.last_action_log = f"{player_name} played {card_str} (Card {target_index + 1}) as Sticky {reason}"
                
            # Temporarily reveal the target card to everyone for 5 seconds
            target_card.visible_to = [p.id for p in game.players]
            target_card.reveal_end_time = time.time() + 5.0
            
            # Penalty always goes to the initiator
            if game.draw_pile:
                penalty_card = game.draw_pile.pop()
                penalty_card.visible_to = [] # hidden
                try:
                    empty_idx = initiator_hand.index(None)
                    initiator_hand[empty_idx] = penalty_card
                except ValueError:
                    initiator_hand.append(penalty_card)
            else:
                pass # Can't draw penalty if deck is completely empty

    @staticmethod
    def give_card(game: LocalGame, player_id: UUID, card_id: UUID):
        if not game.active_resolutions:
            raise ValueError("No active sticky resolutions")
            
        resolution = game.active_resolutions[0]
        if resolution.giver_id != player_id:
            raise ValueError("It is not your turn to give a card")
            
        giver_hand = game.hands.get(player_id, [])
        target_card = None
        target_index = -1
        for i, card in enumerate(giver_hand):
            if card is not None and card.id == card_id:
                target_card = card
                target_index = i
                break
                
        if not target_card:
            raise ValueError("Card not found in your hand")
            
        # Remove from giver
        giver_hand[target_index] = None
        
        # Give to receiver
        receiver_hand = game.hands.get(resolution.receiver_id, [])
        try:
            empty_idx = receiver_hand.index(None)
            receiver_hand[empty_idx] = target_card
        except ValueError:
            receiver_hand.append(target_card)
            
        # Hide it
        target_card.visible_to = []
        target_card.reveal_end_time = None
        
        # Clear resolution
        game.active_resolutions.pop(0)
        
        giver_name = next((p.name for p in game.players if p.id == player_id), "Player")
        receiver_name = next((p.name for p in game.players if p.id == resolution.receiver_id), "Player")
        game.last_action_log = f"{giver_name} gave a card to {receiver_name} to complete the Sticky."

    # Power Mechanisms
    
    @staticmethod
    def power_look(game: LocalGame, player_id: UUID, target_card_id: UUID):
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        pa = game.turn.pending_action
        if pa not in ("look_self", "look_other", "look_and_swap"):
            raise ValueError("No look power active")
            
        target_card = None
        target_owner_id = None
        for p_id, p_hand in game.hands.items():
            for card in p_hand:
                if card and card.id == target_card_id:
                    target_card = card
                    target_owner_id = p_id
                    break
            if target_card:
                break
                
        if not target_card:
            raise ValueError("Target card not found")

        cabo_caller_id = GameEngine.get_cabo_caller_id(game)
        if cabo_caller_id and target_owner_id == cabo_caller_id and player_id != cabo_caller_id:
            raise ValueError("Cannot peek at cards of the player who called CABO! Their cards are frozen.")

        # For look_other (9/10), ensure the target is NOT the player's own card
        if pa == "look_other":
            own_hand = game.hands.get(player_id, [])
            if any(c and c.id == target_card_id for c in own_hand):
                raise ValueError("Cannot peek at your own card with this power")
            
        # Give visibility to player for 5 seconds
        target_card.visible_to = [player_id]
        target_card.reveal_end_time = time.time() + 5.0
        
        player_name = next((p.name for p in game.players if p.id == player_id), "Player")
        
        if pa == "look_and_swap":
            game.turn.first_swap_target = target_card_id
            game.last_action_log = f"{player_name} peeked at a card and is deciding whether to swap."
            # Do not advance turn, wait for power_swap
        else:
            game.last_action_log = f"{player_name} used a power to peek at a card."
            GameEngine.next_turn(game)
            
    @staticmethod
    def power_swap(game: LocalGame, player_id: UUID, card1_id: UUID, card2_id: UUID):
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        pa = game.turn.pending_action
        if pa not in ("blind_swap", "look_and_swap"):
            raise ValueError("No swap power active")
            
        # Find card1
        hand1 = None
        card1 = None
        idx1 = -1
        p1_id = None
        for p_id, p_hand in game.hands.items():
            for i, c in enumerate(p_hand):
                if c and c.id == card1_id:
                    hand1 = p_hand
                    card1 = c
                    idx1 = i
                    p1_id = p_id
                    break
            if card1:
                break
                
        # Find card2
        hand2 = None
        card2 = None
        idx2 = -1
        p2_id = None
        for p_id, p_hand in game.hands.items():
            for i, c in enumerate(p_hand):
                if c and c.id == card2_id:
                    hand2 = p_hand
                    card2 = c
                    idx2 = i
                    p2_id = p_id
                    break
            if card2:
                break
                
        cabo_caller_id = GameEngine.get_cabo_caller_id(game)

        if not card1 or not card2:
            raise ValueError("Cards not found")
            
        if p1_id == p2_id:
            raise ValueError("Must swap cards between two different players")

        if cabo_caller_id and (p1_id == cabo_caller_id or p2_id == cabo_caller_id) and player_id != cabo_caller_id:
            raise ValueError("Cannot swap cards with the player who called CABO! Their cards are frozen.")
            
        # Swap
        hand1[idx1] = card2
        hand2[idx2] = card1
        
        # Reset visibility just in case
        card1.visible_to = []
        card1.reveal_end_time = None
        card2.visible_to = []
        card2.reveal_end_time = None
        game.turn.first_swap_target = None
        
        player_name = next((p.name for p in game.players if p.id == player_id), "Player")
        name1 = next((p.name for p in game.players if p.id == p1_id), "Player")
        name2 = next((p.name for p in game.players if p.id == p2_id), "Player")
        if name1 == name2:
            game.last_action_log = f"{player_name} swapped two cards of {name1}."
        else:
            game.last_action_log = f"{player_name} swapped a card between {name1} and {name2}."
        
        GameEngine.next_turn(game)

    @staticmethod
    def power_discard(game: LocalGame, player_id: UUID, card_id: UUID):
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        if game.turn.pending_action != "discard_self":
            raise ValueError("Discard power not active")
            
        my_hand = game.hands.get(player_id, [])
        target_card = None
        target_idx = -1
        for i, c in enumerate(my_hand):
            if c and c.id == card_id:
                target_card = c
                target_idx = i
                break
                
        if not target_card:
            raise ValueError("Card not found in your hand")
            
        my_hand[target_idx] = None
        target_card.visible_to = [p.id for p in game.players]
        game.discard_pile.append(target_card)
        game.last_discard_was_sticky = False
        
        player_name = next((p.name for p in game.players if p.id == player_id), "Player")
        game.last_action_log = f"{player_name} trashed one of their own cards."
        
        GameEngine.next_turn(game)

    # Visibility
    
    @staticmethod
    def reveal_to_player(card: Card, player_id: UUID):
        card.visible_to = [player_id]

    @staticmethod
    def reveal_to_all(game: LocalGame, card: Card):
        card.visible_to = [p.id for p in game.players]

    @staticmethod
    def hide(card: Card):
        card.visible_to.clear()

    # Cabo
    @staticmethod
    def call_cabo(game: LocalGame, player_id: UUID):
        if player_id != GameEngine.current_player(game).id:
            raise ValueError("Not your turn")
        if game.phase not in ("playing", "cabo_round"):
            raise ValueError("Cannot call Cabo right now")
        if game.cabo_caller_index is not None:
            raise ValueError("Cabo has already been called")

        caller_player = GameEngine.current_player(game)
        caller_player.called_cabo = True
        game.cabo_caller_index = game.current_turn
        game.phase = "cabo_round"

        # Advance turn so other players get their 1 final turn
        GameEngine.next_turn(game)