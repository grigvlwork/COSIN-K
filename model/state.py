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
    IMMUTABLE по соглашению — никогда не изменяйте существующий GameState,
    всегда создавайте новый через copy() и модификаторы.
    """

    # Стопки игры
    piles: Dict[str, Pile] = field(default_factory=dict)
    stock: Pile = field(default_factory=lambda: Pile("stock"))
    waste: Pile = field(default_factory=lambda: Pile("waste"))

    # Счётчики
    score: int = 0
    moves_count: int = 0
    time_elapsed: int = 0  # секунды

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

    # === Копирование (единственный способ "изменения") ===

    def copy(self) -> "GameState":
        """
        Создать глубокую копию состояния.
        Используется для сохранения истории и модификации.
        """
        return GameState(
            piles={name: pile.copy() for name, pile in self.piles.items()},
            stock=self.stock.copy(),
            waste=self.waste.copy(),
            score=self.score,
            moves_count=self.moves_count,
            time_elapsed=self.time_elapsed
        )

    # === Вспомогательные методы для Engine ===

    def with_score(self, delta: int) -> "GameState":
        """Создать новое состояние с изменённым счётом."""
        new_state = self.copy()
        new_state.score += delta
        return new_state

    def with_move_count(self, delta: int = 1) -> "GameState":
        """Создать новое состояние с изменённым счётчиком ходов."""
        new_state = self.copy()
        new_state.moves_count += delta
        return new_state

    def with_pile_updated(self, name: str, new_pile: Pile) -> "GameState":
        """Создать новое состояние с обновлённой стопкой."""
        new_state = self.copy()
        new_state.set_pile(name, new_pile)
        return new_state

    # === Представление ===

    def __repr__(self) -> str:
        return (
            f"GameState(piles={len(self.piles)}, "
            f"stock={len(self.stock)}, "
            f"waste={len(self.waste)}, "
            f"score={self.score}, "
            f"moves={self.moves_count})"
        )