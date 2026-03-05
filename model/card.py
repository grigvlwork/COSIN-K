# model/card.py
from dataclasses import dataclass
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
    face_up: bool = False

    def flip(self) -> 'Card':
        """ИММУТАБЕЛЬНОЕ переворачивание"""
        return Card(self.suit, self.rank, not self.face_up)

    def make_face_up(self) -> 'Card':
        return Card(self.suit, self.rank, True) if not self.face_up else self

    def make_face_down(self) -> 'Card':
        return Card(self.suit, self.rank, False) if self.face_up else self

    # === Сериализация ===

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать карту в словарь для JSON.
        Сохраняем имена Enum'ов для надежности.
        """
        return {
            "suit": self.suit.name,
            "rank": self.rank.value,  # Сохраняем число (1-13)
            "face_up": self.face_up
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Card':
        """
        Создать карту из словаря.
        Ожидает: {"suit": "HEARTS", "rank": 1, "face_up": true}
        """
        # Если rank пришел как строка (например "ACE"), преобразуем
        rank_data = data["rank"]
        if isinstance(rank_data, str):
            # Пытаемся распарсить строку как имя Enum или значение
            try:
                rank = Rank[rank_data.upper()]
            except KeyError:
                # Если это число в строке "10"
                rank = Rank(int(rank_data))
        else:
            rank = Rank(rank_data)

        # Если suit пришел как символ "♥"
        suit_data = data["suit"]
        if isinstance(suit_data, str):
            # Если это длинное имя "HEARTS"
            if len(suit_data) > 2:
                suit = Suit[suit_data.upper()]
            else:
                # Если это символ "♥"
                suit = Suit(suit_data)
        else:
            suit = Suit(suit_data)

        return cls(
            suit=suit,
            rank=rank,
            face_up=data.get("face_up", False)
        )

    @classmethod
    def from_str(cls, text: str, face_up: bool = True) -> Optional['Card']:
        """
        Создать карту из строки вида "A♥", "10♠", "K♦".
        Используется для парсинга, если Godot пришлет строки.
        """
        if not text or len(text) < 2:
            return None

        text = text.strip()

        # Определяем масть (последний символ)
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

        # Определяем ранг (все символы кроме последнего)
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

        return cls(suit, rank, face_up)

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