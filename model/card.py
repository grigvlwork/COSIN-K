# model/card.py
from dataclasses import dataclass, field
from uuid import uuid4
from enum import Enum
from typing import Dict, Any, Optional


class Suit(Enum):
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"


class Rank(Enum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank
    id: str = field(default_factory=lambda: str(uuid4()))
    face_up: bool = False

    def flip(self) -> 'Card':
        """ИММУТАБЕЛЬНОЕ переворачивание"""
        return Card(self.suit, self.rank, self.id, not self.face_up)

    def make_face_up(self) -> 'Card':
        if self.face_up:
            return self

        return Card(
            suit=self.suit,
            rank=self.rank,
            id=self.id,
            face_up=True
        )

    def make_face_down(self) -> 'Card':
        if not self.face_up:
            return self

        return Card(
            suit=self.suit,
            rank=self.rank,
            id=self.id,
            face_up=False
        )

    # === Сериализация ===

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "suit": self.suit.name,
            "rank": self.rank.value,
            "face_up": self.face_up
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        card_id = data.get("id") or str(uuid4())

        # rank
        rank_data = data["rank"]
        if isinstance(rank_data, str):
            try:
                rank = Rank[rank_data.upper()]
            except KeyError:
                rank = Rank(int(rank_data))
        else:
            rank = Rank(rank_data)

        # suit
        suit_data = data["suit"]
        if isinstance(suit_data, str):
            if len(suit_data) > 2:
                suit = Suit[suit_data.upper()]
            else:
                suit = Suit(suit_data)
        else:
            suit = Suit(suit_data)

        return cls(
            suit=suit,
            rank=rank,
            id=card_id,
            face_up=data.get("face_up", False)
        )

    @classmethod
    def from_str(cls, text: str, face_up: bool = True) -> Optional['Card']:
        if not text or len(text) < 2:
            return None

        text = text.strip()

        suit_symbol = text[-1]
        suit_map = {
            "♥": Suit.HEARTS, "H": Suit.HEARTS,
            "♦": Suit.DIAMONDS, "D": Suit.DIAMONDS,
            "♣": Suit.CLUBS, "C": Suit.CLUBS,
            "♠": Suit.SPADES, "S": Suit.SPADES
        }
        suit = suit_map.get(suit_symbol)
        if not suit:
            return None

        rank_str = text[:-1].upper()
        rank_map = {
            "A": Rank.ACE, "J": Rank.JACK, "Q": Rank.QUEEN, "K": Rank.KING
        }

        if rank_str in rank_map:
            rank = rank_map[rank_str]
        else:
            try:
                rank = Rank(int(rank_str))
            except ValueError:
                return None

        return cls(
            suit=suit,
            rank=rank,
            face_up=face_up
        )

    # === Свойства ===

    @property
    def color(self) -> str:
        return "red" if self.suit in (Suit.HEARTS, Suit.DIAMONDS) else "black"

    @property
    def is_red(self) -> bool:
        return self.suit in (Suit.HEARTS, Suit.DIAMONDS)

    @property
    def is_black(self) -> bool:
        return not self.is_red

    def is_opposite_color(self, other: 'Card') -> bool:
        return self.is_red != other.is_red

    def is_same_suit(self, other: 'Card') -> bool:
        return self.suit == other.suit

    def rank_difference(self, other: 'Card') -> int:
        return self.rank.value - other.rank.value

    # === Представление ===

    def __str__(self) -> str:
        if not self.face_up:
            return "[X]"

        rank_symbols = {
            Rank.ACE: 'A',
            Rank.JACK: 'J',
            Rank.QUEEN: 'Q',
            Rank.KING: 'K'
        }
        rank_str = rank_symbols.get(self.rank, str(self.rank.value))
        return f"{rank_str}{self.suit.value}"

    def __repr__(self) -> str:
        return (
            f"Card(id={self.id[:8]}..., "
            f"suit={self.suit.name}, "
            f"rank={self.rank.name}, "
            f"face_up={self.face_up})"
        )