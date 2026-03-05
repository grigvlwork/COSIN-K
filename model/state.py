# model/state.py
"""
GameState — чистое состояние игры.
Только данные, никакой логики перемещений!
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
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

    # === Сериализация ===

    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать состояние в словарь для JSON.
        """
        # Преобразуем словарь piles: {name: Pile} -> {name: dict}
        piles_dict = {}
        for name, pile in self.piles.items():
            piles_dict[name] = pile.to_dict()

        return {
            "piles": piles_dict,
            "stock": self.stock.to_dict(),
            "waste": self.waste.to_dict(),
            "score": self.score,
            "moves_count": self.moves_count,
            "time_elapsed": self.time_elapsed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameState":
        """
        Создать состояние из словаря (из JSON).
        """
        # Восстанавливаем словарь piles
        piles = {}
        piles_data = data.get("piles", {})
        for name, pile_data in piles_data.items():
            # pile_data может быть уже словарем или объектом Pile (при глубоком копировании)
            if isinstance(pile_data, Pile):
                piles[name] = pile_data
            elif isinstance(pile_data, dict):
                piles[name] = Pile.from_dict(pile_data)
            else:
                # На всякий случай создаем пустую стопку
                piles[name] = Pile(name)

        # Восстанавливаем stock
        stock_data = data.get("stock")
        if isinstance(stock_data, Pile):
            stock = stock_data
        elif isinstance(stock_data, dict):
            stock = Pile.from_dict(stock_data)
        else:
            stock = Pile("stock")

        # Восстанавливаем waste
        waste_data = data.get("waste")
        if isinstance(waste_data, Pile):
            waste = waste_data
        elif isinstance(waste_data, dict):
            waste = Pile.from_dict(waste_data)
        else:
            waste = Pile("waste")

        return cls(
            piles=piles,
            stock=stock,
            waste=waste,
            score=data.get("score", 0),
            moves_count=data.get("moves_count", 0),
            time_elapsed=data.get("time_elapsed", 0)
        )

    def __repr__(self) -> str:
        return (
            f"GameState(piles={len(self.piles)}, "
            f"stock={len(self.stock)}, "
            f"waste={len(self.waste)}, "
            f"score={self.score}, "
            f"moves={self.moves_count})"
        )