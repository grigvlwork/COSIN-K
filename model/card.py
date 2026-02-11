# model/card.py
from dataclasses import dataclass
from enum import Enum


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
    face_up: bool = False

    def flip(self) -> 'Card':
        """ИММУТАБЕЛЬНОЕ переворачивание"""
        return Card(self.suit, self.rank, not self.face_up)

    def make_face_up(self) -> 'Card':
        return Card(self.suit, self.rank, True) if not self.face_up else self

    def make_face_down(self) -> 'Card':
        return Card(self.suit, self.rank, False) if self.face_up else self

    # Только данные, никакого отображения!
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
        """Проверка, что карты противоположного цвета"""
        return self.is_red != other.is_red

    def is_same_suit(self, other: 'Card') -> bool:
        """Проверка на одинаковую масть"""
        return self.suit == other.suit

    def rank_difference(self, other: 'Card') -> int:
        """Разница в рангах (важно для правил типа 'карта должна быть на 1 меньше')"""
        return self.rank.value - other.rank.value

    def __str__(self) -> str:
        """Для пользовательского отображения"""
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
        """Для отладки и логирования"""
        return f"Card(suit={self.suit.name}, rank={self.rank.name}, face_up={self.face_up})"