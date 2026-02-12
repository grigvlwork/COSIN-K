"""
RuleSet — абстрактный базовый класс для правил пасьянса.
Определяет контракт, который должны реализовать конкретные игры.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Dict, Optional, Tuple
from enum import Enum

# TYPE_CHECKING остаётся как у вас
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
        # Сигнатура: (pile: Pile, cards: List[Card], state: GameState) -> bool
        self.build_rules: Dict[PileType, Callable] = {}

        # Дополнительные валидаторы ходов
        self.move_validators: List[Callable[["GameState", "Move"], bool]] = []

    # === АБСТРАКТНЫЕ МЕТОДЫ (обязательны к реализации) ===

    @abstractmethod
    def deal(self, deck: List["Card"]) -> Dict[str, "Pile"]:
        """
        Раздать колоду по стопкам.
        Возвращает словарь начальных стопок (кроме stock).
        """
        pass

    @abstractmethod
    def is_victory(self, state: "GameState") -> bool:
        """Проверить, выиграна ли игра."""
        pass

    @abstractmethod
    def get_pile_type(self, pile_name: str) -> PileType:
        """
        Определить тип стопки по имени.
        Например: "tableau_0" → PileType.TABLEAU
                 "foundation_HEARTS" → PileType.FOUNDATION
        """
        pass

    # === ПРОВЕРКА ХОДОВ ===

    def can_move(self, state: "GameState", move: "Move") -> bool:
        """
        Полная проверка валидности хода.
        Переопределяется в наследниках при необходимости.
        """
        # 1. Базовые проверки
        if not self._validate_basic(state, move):
            return False

        # 2. Проверка взятия карт
        if not self.can_take(state, move.from_pile, len(move.cards)):
            return False

        # 3. Проверка построения на целевой стопке
        target = state.get_pile(move.to_pile)
        if not self.can_drop(target, move.cards, state):
            return False

        # 4. Дополнительные валидаторы
        for validator in self.move_validators:
            if not validator(state, move):
                return False

        return True

    def _validate_basic(self, state: "GameState", move: "Move") -> bool:
        """Базовые проверки, общие для всех пасьянсов."""
        source = state.get_pile(move.from_pile)
        target = state.get_pile(move.to_pile)

        # Проверка существования стопок
        if source is None or target is None:
            return False

        # Проверка пустоты
        if source.is_empty():
            return False

        # Проверка количества карт
        if len(move.cards) > len(source):
            return False

        # Нельзя переместить на ту же стопку
        if move.from_pile == move.to_pile:
            return False

        return True

    # === ВЗЯТИЕ КАРТ ===

    def can_take(self, state: "GameState", pile_name: str, count: int = 1) -> bool:
        """
        Можно ли взять count карт из указанной стопки.
        По умолчанию: только открытые карты с конца.
        """
        pile = state.get_pile(pile_name)
        if not pile:
            return False

        pile_type = self.get_pile_type(pile_name)

        # Нельзя брать из foundation
        if pile_type == PileType.FOUNDATION:
            return False

        # Нельзя брать из stock (обычно)
        if pile_type == PileType.STOCK:
            return False

        # Только открытые карты
        return pile.face_up_count() >= count

    # === ПОСТРОЕНИЕ СТОПОК ===

    def can_drop(self, target_pile: "Pile", cards: List["Card"],
                 state: "GameState") -> bool:
        """
        Проверить, можно ли положить карты на стопку.
        Использует правила из build_rules.
        """
        pile_type = self.get_pile_type(target_pile.name)
        rule = self.build_rules.get(pile_type)

        if rule is None:
            return False

        try:
            return rule(target_pile, cards, state)
        except TypeError:
            # Fallback для старых правил без state
            return rule(target_pile, cards)

    # === ПОБОЧНЫЕ ЭФФЕКТЫ ===

    def get_flipped_cards(self, state: "GameState", move: "Move") -> List[Tuple[str, int]]:
        """
        Определить, какие карты нужно перевернуть после хода.
        Возвращает список (pile_name, index).
        """
        return []

    # === СЧЁТ ===

    def calculate_score(self, state: "GameState", move: "Move") -> int:
        """Подсчитать очки за ход."""
        return 0

    def calculate_recycle_penalty(self, state: "GameState") -> int:
        """Штраф за перебор колоды."""
        return 0

    # === КОЛОДА ===

    def get_stock_size(self, deck: List["Card"], dealt: Dict[str, "Pile"]) -> int:
        """Сколько карт остаётся в колоде после раздачи."""
        dealt_count = sum(len(p) for p in dealt.values())
        return len(deck) - dealt_count

    def get_draw_count(self) -> int:
        """
        Сколько карт вытягивать из колоды за раз.
        Для Клондайка: 1 или 3.
        """
        return 1

    # === ПОДСКАЗКИ ===

    def get_hint(self, state: "GameState") -> Optional["Move"]:
        """Вернуть возможный ход для подсказки."""
        return None

    # === СТРОКОВОЕ ПРЕДСТАВЛЕНИЕ ===

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.game_type!r})>"