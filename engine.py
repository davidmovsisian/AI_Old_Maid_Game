import random
from typing import List, Tuple, Dict

class Card:
    def __init__(self, suit: str, rank: str):
        self.suit = suit
        self.rank = rank
        self.color = "Red" if suit in ["Hearts", "Diamonds"] else "Black"

    def __repr__(self):
        return f"{self.rank} of {self.suit}"

    def to_dict(self):
        return {"suit": self.suit, "rank": self.rank}
    
class GameEngine:
    def __init__(self, player_names: List[str], house_rules: str):
        self.player_names = player_names
        self.house_rules = house_rules
        self.hands: Dict[str, List[Card]] = {name: [] for name in player_names}
        self.turn_order = player_names.copy()
        self.current_turn_index = 0
        self.discarded_pairs: List[str] = []
        self._initialize_game()

    def _initialize_game(self):
        # create deck of cards
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'K', 'A']
        deck = [Card(suit, rank) for suit in suits for rank in ranks]

        deck.append(Card('Hearts', 'Q'))  # Adding the Queen of Hearts as a special card
        deck.append(Card('Diamonds', 'Q'))  # Adding the Queen of Diamonds as a special card
        deck.append(Card('Clubs', 'Q'))  # Adding the Queen of Clubs as a special card

        random.shuffle(deck)

        # deal cards to players
        for i, card in enumerate(deck):
            player_name = self.player_names[i % len(self.player_names)]
            self.hands[player_name].append(card)
        
        # remove pairs from hands
        for player_name in self.player_names:
            self.remove_pairs(player_name)
        
    def remove_pairs(self, player_name: str) -> List[str]:
        hand = self.hands[player_name]
        
        # Group actual Card objects by their rank
        from collections import defaultdict
        rank_groups = defaultdict(list)
        for card in hand:
            rank_groups[card.rank].append(card)

        new_hand = []
        removed_pairs = []

        for rank, cards in rank_groups.items():
            count = len(cards)
            pairs_count = count // 2
            
            # Track removed pairs for house rules / logs
            for _ in range(pairs_count):
                removed_pairs.append(f"Pair of {rank}s")
                self.discarded_pairs.append(f"Pair of {rank}s")
                
            # IF there's a remainder (1 or 3 cards originally), ONE card survives
            if count % 2 == 1:
                new_hand.append(cards[-1])

        # Update the engine's state with the clean hand
        self.hands[player_name] = new_hand

        return removed_pairs
    
    def get_next_player(self, current_player: str) -> str:
        idx = self.turn_order.index(current_player)
        next_idx = (idx + 1) % len(self.turn_order)
        return self.turn_order[next_idx]
    
    def execute_draw(self, current_player: str, target_player: str, card_index: int):
        if card_index < 0 or card_index >= len(self.hands[target_player]):
            raise IndexError("Card index out of range.")
        
        drawn_card = self.hands[target_player].pop(card_index)
        self.hands[current_player].append(drawn_card)
        
        # Remove pairs after drawing
        removed_pairs = self.remove_pairs(current_player)

        #check if target player has no cards left, if so, update state of the game
        if len(self.hands[target_player]) == 0:
            self.player_names.remove(target_player)
            self.hands.pop(target_player)
            self.turn_order = self.player_names.copy()

        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)

        return {
            "drawn_card_visible_to_drawer": drawn_card.to_dict(),
            "new_pairs_formed": removed_pairs
        }
