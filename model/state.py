"""
GameState — снимок состояния игры.
Move — описание хода для истории и отмены.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Callable, Optional, Any
from .pile import Pile


@dataclass
class Move:
    """
    Описание хода для истории и возможной отмены.
    Хранит достаточно информации чтобы восстановить состояние.
    """
    from_pile: str
    to_pile: str
    cards: List  # Карты которые переместились
    flipped: List[tuple] = field(default_factory=list)  # (pile_name, card_index) перевернутые карты
    score_delta: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        cards_str = " ".join(str(c) for c in self.cards)
        return f"Move({self.from_pile} -> {self.to_pile}, [{cards_str}])"


@dataclass
class GameState:
    """
    Полное состояние игры в один момент времени.
    Можно копировать для сохранения истории.
    """

    # Стопки игры
    piles: Dict[str, Pile] = field(default_factory=dict)
    stock: Pile = field(default_factory=lambda: Pile("stock"))
    waste: Pile = field(default_factory=lambda: Pile("waste"))

    # Счётчики
    score: int = 0
    moves_count: int = 0
    time_elapsed: int = 0  # секунды

    # Состояние UI (не влияет на логику, но удобно хранить здесь)
    selected_pile: Optional[str] = None

    # Приватное поле для событий (не копируется)
    _listeners: List[Callable[[str, Dict[str, Any]], None]] = field(
        default_factory=list,
        repr=False,
        compare=False
    )

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Подписаться на события состояния."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Отписаться от событий."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def notify(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Уведомить всех подписчиков о событии."""
        data = data or {}
        for listener in self._listeners:
            listener(event, data)

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

    def copy(self) -> "GameState":
        """
        Создать глубокую копию состояния.
        Используется для сохранения истории.
        """
        new_state = GameState(
            score=self.score,
            moves_count=self.moves_count,
            time_elapsed=self.time_elapsed,
            selected_pile=self.selected_pile,
        )

        # Копируем все стопки
        new_state.stock = self.stock.copy()
        new_state.waste = self.waste.copy()
        new_state.piles = {name: pile.copy() for name, pile in self.piles.items()}

        # Слушатели не копируются — новое состояние "чистое"

        return new_state

    def apply_move(self, move: Move) -> None:
        """
        Применить ход к состояниие.
        Не проверяет валидность — только исполняет.
        """
        source = self.get_pile(move.from_pile)
        target = self.get_pile(move.to_pile)

        if source is None or target is None:
            raise ValueError(f"Invalid piles: {move.from_pile} -> {move.to_pile}")

        # Перемещаем карты
        cards = source.take(len(move.cards))
        target.add(cards)

        # Обновляем счётчики
        self.score += move.score_delta
        self.moves_count += 1

    def revert_move(self, move: Move) -> None:
        """
        Отменить ход (обратное действие).
        """
        source = self.get_pile(move.from_pile)
        target = self.get_pile(move.to_pile)

        if source is None or target is None:
            raise ValueError(f"Invalid piles: {move.from_pile} -> {move.to_pile}")

        # Возвращаем карты обратно
        cards = target.take(len(move.cards))
        source.add(cards)

        # Переворачиваем карты обратно если нужно
        for pile_name, card_index in move.flipped:
            pile = self.get_pile(pile_name)
            if pile and card_index < len(pile):
                pile[card_index] = pile[card_index].flip()

        # Обновляем счётчики
        self.score -= move.score_delta
        self.moves_count -= 1

    def __repr__(self) -> str:
        pile_count = len(self.piles)
        return (
            f"GameState(piles={pile_count}, "
            f"stock={len(self.stock)}, "
            f"waste={len(self.waste)}, "
            f"score={self.score}, "
            f"moves={self.moves_count})"
        )