"""
RuleSet — абстрактный базовый класс для правил пасьянса.
Определяет контракт, который должны реализовать конкретные игры.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Optional, Tuple, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from model import GameState, Pile, Card, Move


class PileType(Enum):
    """Типы стопок в пасьянсе."""
    STOCK = "stock"
    WASTE = "waste"
    TABLEAU = "tableau"
    FOUNDATION = "foundation"
    FREE_CELL = "freecell"
    RESERVE = "reserve"


class RuleSet(ABC):
    """
    Абстрактный базовый класс для правил пасьянса.
    Все конкретные игры должны наследоваться от этого класса.
    """

    def __init__(self, game_type: str):
        self.game_type = game_type

        # Правила построения для разных типов стопок
        self.build_rules: Dict[PileType, Callable] = {}

        # Дополнительные валидаторы ходов
        self.move_validators: List[Callable[["GameState", "Move"], bool]] = []

    # === АБСТРАКТНЫЕ МЕТОДЫ (обязательны к реализации) ===

    @abstractmethod
    def deal(self, deck: List["Card"]) -> Dict[str, "Pile"]:
        """Раздать колоду по стопкам."""
        pass

    @abstractmethod
    def check_win(self, state: "GameState") -> bool:
        """Проверить, выиграна ли игра."""
        pass

    @abstractmethod
    def get_pile_type(self, pile_name: str) -> PileType:
        """Определить тип стопки по имени."""
        pass

    # === ПРОВЕРКА ХОДОВ ===

    def can_move(self, state: "GameState", move: "Move") -> bool:
        """Полная проверка валидности хода."""
        if not self._validate_basic(state, move):
            return False

        if not self.can_take(state, move.from_pile, len(move.cards)):
            return False

        target = state.get_pile(move.to_pile)
        if not self.can_drop(target, move.cards, state):
            return False

        for validator in self.move_validators:
            if not validator(state, move):
                return False

        return True

    def _validate_basic(self, state: "GameState", move: "Move") -> bool:
        """Базовые проверки, общие для всех пасьянсов."""
        source = state.get_pile(move.from_pile)
        target = state.get_pile(move.to_pile)

        if source is None or target is None:
            return False
        if source.is_empty():
            return False
        if len(move.cards) > len(source):
            return False
        if move.from_pile == move.to_pile:
            return False

        return True

    # === КОЛОДА ===

    def can_draw(self, state: "GameState") -> bool:
        """Можно ли взять карту из колоды."""
        return not state.stock.is_empty() or not state.waste.is_empty()

    def get_draw_count(self) -> int:
        """Сколько карт вытягивать из колоды за раз."""
        return 1

    # === ВЗЯТИЕ КАРТ ===

    def can_take(self, state: "GameState", pile_name: str, count: int = 1) -> bool:
        """Можно ли взять count карт из указанной стопки."""
        pile = state.get_pile(pile_name)
        if not pile:
            return False

        pile_type = self.get_pile_type(pile_name)

        if pile_type in (PileType.FOUNDATION, PileType.STOCK):
            return False

        return pile.face_up_count() >= count

    # === ПОСТРОЕНИЕ СТОПОК ===

    def can_drop(self, target_pile: "Pile", cards: List["Card"],
                 state: "GameState") -> bool:
        """Проверить, можно ли положить карты на стопку."""
        pile_type = self.get_pile_type(target_pile.name)
        rule = self.build_rules.get(pile_type)

        if rule is None:
            return False
        try:
            return rule(target_pile, cards, state)
        except TypeError:
            return rule(target_pile, cards)

    # === ПОБОЧНЫЕ ЭФФЕКТЫ ===

    def get_flipped_cards(self, previous_state: "GameState", move: "Move") -> List[Tuple[str, int]]:
        """Какие карты нужно перевернуть после хода."""
        return []

    # === СЧЁТ ===

    def calculate_score(self, state: "GameState", move: "Move") -> int:
        """Очки за ход (перемещение карт)."""
        return 0

    def score_move(self, state: "GameState", move: "Move",
                   previous_state: Optional["GameState"] = None) -> int:
        """Очки за перемещение карт (для сложных правил)."""
        return self.calculate_score(state, move)

    def score_draw(self, previous_state: "GameState", cards: List["Card"]) -> int:
        """Очки за взятие карт из колоды."""
        return 0

    def score_recycle(self, state: "GameState") -> int:
        """Штраф за перебор колоды."""
        return 0

    # === ПОДСКАЗКИ ===

    def get_hint(self, state: "GameState") -> Optional["Move"]:
        """Вернуть возможный ход для подсказки."""
        return None

    # === СТРОКОВОЕ ПРЕДСТАВЛЕНИЕ ===

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.game_type!r})>"