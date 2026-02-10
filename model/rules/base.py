"""
RuleSet — абстрактный базовый класс для правил пасьянса.
Определяет контракт, который должны реализовать конкретные игры.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from model import GameState, Pile, Card, Move


class RuleSet(ABC):
    """
    Набор правил конкретного пасьянса.
    Определяет:
    - Как раздавать карты
    - Как строить стопки
    - Какие ходы валидны
    - Условие победы
    """

    def __init__(self, game_type: str):
        self.game_type = game_type

        # Функции проверки построения для разных типов стопок
        self.build_rules: Dict[str, Callable[["Pile", List["Card"]], bool]] = {}

        # Дополнительные валидаторы ходов
        self.move_validators: List[Callable[["GameState", "Move"], bool]] = []

        # Условие победы
        self._win_condition: Callable[["GameState"], bool] = lambda s: False

    # === Построение стопок ===

    def can_drop(self, target_pile: "Pile", cards: List["Card"]) -> bool:
        """
        Проверить, можно ли положить карты на стопку.
        Использует специфичные правила построения.
        """
        # Определяем тип стопки по имени
        pile_type = self._get_pile_type(target_pile.name)

        # Получаем правило для этого типа
        rule = self.build_rules.get(pile_type)
        if rule is None:
            return False

        return rule(target_pile, cards)

    @abstractmethod
    def _get_pile_type(self, pile_name: str) -> str:
        """
        Определить тип стопки по имени.
        Например: "tableau_0" → "tableau", "foundation_HEARTS" → "foundation"
        """
        pass

    # === Валидация ходов ===

    def validate_move(self, state: "GameState", move: "Move") -> bool:
        """
        Проверить валидность хода всеми правилами.
        """
        # Проверяем базовые ограничения
        if not self._basic_validation(state, move):
            return False

        # Проверяем специфичные валидаторы
        for validator in self.move_validators:
            if not validator(state, move):
                return False

        # Проверяем построение на целевой стопке
        target = state.get_pile(move.to_pile)
        if target is None:
            return False

        return self.can_drop(target, move.cards)

    def _basic_validation(self, state: "GameState", move: "Move") -> bool:
        """
        Базовые проверки: существование стопок, доступность карт.
        """
        source = state.get_pile(move.from_pile)
        target = state.get_pile(move.to_pile)

        # Стопки существуют
        if source is None or target is None:
            return False

        # Источник не пуст
        if source.is_empty():
            return False

        # Достаточно карт в источнике
        if len(move.cards) > len(source):
            return False

        # Все перемещаемые карты открыты
        if not all(c.face_up for c in move.cards):
            return False

        # Нельзя переместить на ту же стопку
        if move.from_pile == move.to_pile:
            return False

        return True

    # === Условие победы ===

    def check_win(self, state: "GameState") -> bool:
        """Проверить выполнено ли условие победы."""
        return self._win_condition(state)

    # === Раздача карт ===

    @abstractmethod
    def deal(self, deck: List["Card"]) -> Dict[str, "Pile"]:
        """
        Раздать колоду по стопкам.
        Возвращает словарь начальных стопок (кроме stock).
        """
        pass

    def stock_size(self, deck: List["Card"], dealt: Dict[str, "Pile"]) -> int:
        """
        Сколько карт остаётся в колоде после раздачи.
        По умолчанию — все оставшиеся.
        """
        dealt_count = sum(len(p) for p in dealt.values())
        return len(deck) - dealt_count

    # === Счёт ===

    def score_move(self, state: "GameState", move: "Move") -> int:
        """
        Подсчитать изменение счёта за ход.
        По умолчанию — 0.
        """
        return 0

    def score_recycle(self, state: "GameState") -> int:
        """
        Штраф за перебор колоды (stock → waste).
        """
        return 0

    # === Строковое представление ===

    def __repr__(self) -> str:
        return f"RuleSet({self.game_type!r})"