"""
GameState — чистое состояние игры.
Только данные, никакой логики перемещений!
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from .pile import Pile


@dataclass
class GameState:
    """
    Полное состояние игры в один момент времени.
    """

    # Стопки игры
    piles: Dict[str, Pile] = field(default_factory=dict)
    stock: Pile = field(default_factory=lambda: Pile("stock"))
    waste: Pile = field(default_factory=lambda: Pile("waste"))

    # Счётчики
    score: int = 0
    moves_count: int = 0
    time_elapsed: int = 0

    def __post_init__(self):
        """
        Гарантирует, что stock и waste никогда не None.
        Вызывается автоматически после __init__.
        """
        if self.stock is None:
            self.stock = Pile("stock")
        if self.waste is None:
            self.waste = Pile("waste")

    # === Доступ к стопкам ===

    def get_pile(self, name: str) -> Optional[Pile]:
        """Получить стопку по имени."""
        if name == "stock":
            return self.stock
        if name == "waste":
            return self.waste
        return self.piles.get(name)

    def set_pile(self, name: str, pile: Pile) -> None:
        """Установить стопку по имени."""
        pile.name = name
        if name == "stock":
            self.stock = pile
        elif name == "waste":
            self.waste = pile
        else:
            self.piles[name] = pile

    def all_piles(self) -> Dict[str, Pile]:
        """Все стопки включая stock и waste."""
        result = {"stock": self.stock, "waste": self.waste}
        result.update(self.piles)
        return result

    # === Копирование ===

    def copy(self) -> "GameState":
        """
        Создать безопасную глубокую копию.
        """
        # 1. Копируем словарь piles
        new_piles = {}
        if self.piles:
            for name, pile in self.piles.items():
                # Если pile вдруг None, создаем пустой
                new_piles[name] = pile.copy() if pile else Pile(name)

        # 2. Копируем stock и waste с защитой от None
        new_stock = self.stock.copy() if self.stock else Pile("stock")
        new_waste = self.waste.copy() if self.waste else Pile("waste")

        # 3. Возвращаем новый объект
        return GameState(
            piles=new_piles,
            stock=new_stock,
            waste=new_waste,
            score=self.score,
            moves_count=self.moves_count,
            time_elapsed=self.time_elapsed
        )

    def __repr__(self) -> str:
        return (
            f"GameState(piles={len(self.piles)}, "
            f"stock={len(self.stock)}, "
            f"waste={len(self.waste)}, "
            f"score={self.score}, "
            f"moves={self.moves_count})"
        )