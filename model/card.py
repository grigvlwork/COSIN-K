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
    # ... KING = 13


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank
    face_up: bool = False

    # Только данные, никакого отображения!
    @property
    def color(self) -> str:
        return "red" if self.suit in (Suit.HEARTS, Suit.DIAMONDS) else "black"