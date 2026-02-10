"""
KlondikeRules — классическая косынка (Solitaire/Patience).
"""

from typing import TYPE_CHECKING, List, Dict

if TYPE_CHECKING:
    from model import Card, Pile, GameState, Move

from .base import RuleSet
from model import Pile, Card, Rank, Suit


class KlondikeRules(RuleSet):
    """
    Классическая косынка:
    - 7 столбцов (tableau), строим по убыванию, чередуя цвета
    - 4 базы (foundation), строим по возрастанию, одна масть
    - Колода (stock) и сброс (waste)
    - Берём из колоды по 1 или 3 карты
    """

    def __init__(self, draw_three: bool = False):
        super().__init__("klondike")
        self.draw_three = draw_three  # Брать 3 или 1 карту из колоды

        # Настраиваем правила построения
        self.build_rules = {
            "tableau": self._can_build_tableau,
            "foundation": self._can_build_foundation,
        }

        # Валидаторы ходов
        self.move_validators = [
            self._validate_tableau_sequence,  # Только последовательность можно взять
        ]

        # Условие победы — все базы полны
        self._win_condition = self._check_all_foundations_full

    def _get_pile_type(self, pile_name: str) -> str:
        """Определить тип стопки."""
        if pile_name.startswith("tableau_"):
            return "tableau"
        if pile_name.startswith("foundation_"):
            return "foundation"
        if pile_name in ("waste", "stock"):
            return pile_name
        return "unknown"

    # === Правила построения ===

    def _can_build_tableau(self, pile: "Pile", cards: List["Card"]) -> bool:
        """
        Строим столбец: чередуем цвета, убываем рангом.
        Король (K) на пустое место.
        """
        if not cards:
            return False

        # На пустое место — только король
        if pile.is_empty():
            return cards[0].rank == Rank.KING

        top = pile.top()
        first = cards[0]

        # Чередование цветов и убывание ранга на 1
        return (
                top.color != first.color and
                top.rank.value == first.rank.value + 1
        )

    def _can_build_foundation(self, pile: "Pile", cards: List["Card"]) -> bool:
        """
        База: одна масть, возрастание от туза.
        Только по 1 карте за раз.
        """
        if len(cards) != 1:
            return False

        card = cards[0]

        # На пустую базу — только туз
        if pile.is_empty():
            return card.rank == Rank.ACE

        top = pile.top()

        # Одна масть, ранг +1
        return (
                top.suit == card.suit and
                card.rank.value == top.rank.value + 1
        )

    # === Валидация ходов ===

    def _validate_tableau_sequence(self, state: "GameState", move: "Move") -> bool:
        """
        Из tableau можно взять только последовательность открытых карт.
        """
        if not move.from_pile.startswith("tableau_"):
            return True  # Не из tableau — не проверяем

        source = state.get_pile(move.from_pile)
        if source is None:
            return False

        # Проверяем что берём подряд идущие открытые карты с конца
        face_up = source.face_up_count()
        cards_from_end = source.peek(len(move.cards))

        # Проверяем последовательность внутри
        for i in range(len(cards_from_end) - 1):
            curr = cards_from_end[i]
            next_card = cards_from_end[i + 1]

            # Должны чередоваться и убывать
            if curr.color == next_card.color:
                return False
            if curr.rank.value != next_card.rank.value + 1:
                return False

        return True

    # === Раздача ===

    def deal(self, deck: List["Card"]) -> Dict[str, "Pile"]:
        """
        Раздать 7 столбцов: 1, 2, 3... 7 карт.
        Последняя в каждом открыта.
        """
        piles = {}
        idx = 0

        for col in range(7):
            pile = Pile(f"tableau_{col}")

            for row in range(col + 1):
                card = deck[idx]
                # Последняя открыта, остальные закрыты
                is_last = (row == col)
                pile.put(Card(card.suit, card.rank, face_up=is_last))
                idx += 1

            piles[f"tableau_{col}"] = pile

        # Создаём пустые базы
        for suit in Suit:
            piles[f"foundation_{suit.name}"] = Pile(f"foundation_{suit.name}")

        return piles

    def stock_size(self, deck: List["Card"], dealt: Dict[str, "Pile"]) -> int:
        """Остаток колоды после раздачи."""
        dealt_count = sum(len(p) for p in dealt.values())
        return len(deck) - dealt_count

    # === Победа ===

    def _check_all_foundations_full(self, state: "GameState") -> bool:
        """Все 4 базы содержат по 13 карт (полные масти)."""
        for suit in Suit:
            pile = state.piles.get(f"foundation_{suit.name}")
            if pile is None or len(pile) != 13:
                return False
        return True

    # === Счёт ===

    def score_move(self, state: "GameState", move: "Move") -> int:
        """
        Стандартная система очков косынки:
        - waste → foundation: +10
        - tableau → foundation: +10
        - foundation → tableau: -15
        - открыть карту: +5
        """
        score = 0

        # Открыли карту в источнике
        source = state.get_pile(move.from_pile)
        if source and not source.is_empty():
            # Проверяем было ли открытие (это сложно без истории, упрощаем)
            pass

        # На foundation
        if move.to_pile.startswith("foundation_"):
            score += 10

            # С waste — бонус
            if move.from_pile == "waste":
                score += 0  # уже +10

            # С foundation — штраф
            if move.from_pile.startswith("foundation_"):
                score = -15

        # С foundation на tableau
        elif move.from_pile.startswith("foundation_") and move.to_pile.startswith("tableau_"):
            score = -15

        return score

    def score_recycle(self, state: "GameState") -> int:
        """Штраф за перебор колоды."""
        return -20 if self.draw_three else -10

    # === Строковое представление ===

    def __repr__(self) -> str:
        draw = "3" if self.draw_three else "1"
        return f"KlondikeRules(draw={draw})"