"""
Move — описание хода для истории.
Чистые данные, никакой логики!
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple, Optional
from .card import Card


@dataclass(frozen=True)
class Move:
    """
    Описание хода для истории.
    IMMUTABLE — после создания не изменяется.
    """

    # Откуда и куда
    from_pile: str
    to_pile: str

    # Какие карты и откуда именно
    cards: List[Card] = field(default_factory=list)
    from_index: int = -1  # -1 = с конца стопки

    # Побочные эффекты
    flipped_cards: List[Tuple[str, int]] = field(default_factory=list)

    # Метаданные
    score_delta: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Валидация после создания."""
        if not isinstance(self.cards, list):
            raise TypeError("cards must be a list")
        if not all(isinstance(c, Card) for c in self.cards):
            raise TypeError("All cards must be Card instances")

    @property
    def card_count(self) -> int:
        """Количество перемещённых карт."""
        return len(self.cards)

    @property
    def is_single_card(self) -> bool:
        """Перемещается одна карта."""
        return len(self.cards) == 1

    @property
    def is_multiple_cards(self) -> bool:
        """Перемещается несколько карт."""
        return len(self.cards) > 1

    def __repr__(self) -> str:
        cards_str = " ".join(str(c) for c in self.cards[:3])
        if len(self.cards) > 3:
            cards_str += f"...({len(self.cards)})"
        return f"Move({self.from_pile}->{self.to_pile}, [{cards_str}])"