"""
KlondikeRules — классическая косынка (Solitaire/Patience).
"""

from typing import TYPE_CHECKING, List, Dict, Optional, Tuple

if TYPE_CHECKING:
    from model import Card, Pile, GameState, Move

from .base import RuleSet, PileType
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
            PileType.TABLEAU: self._can_build_tableau,
            PileType.FOUNDATION: self._can_build_foundation,
        }

        # Валидаторы ходов
        self.move_validators = [
            self._validate_tableau_sequence,
        ]

    # === ОСНОВНЫЕ МЕТОДЫ RULESET ===

    def check_win(self, state: "GameState") -> bool:
        """Проверить, выиграна ли игра."""
        return self._check_all_foundations_full(state)

    def get_pile_type(self, pile_name: str) -> PileType:
        """Определить тип стопки."""
        if pile_name.startswith("tableau_"):
            return PileType.TABLEAU
        if pile_name.startswith("foundation_"):
            return PileType.FOUNDATION
        if pile_name == "stock":
            return PileType.STOCK
        if pile_name == "waste":
            return PileType.WASTE
        return PileType.RESERVE

    def deal(self, deck: List["Card"]) -> Dict[str, "Pile"]:
        """Раздать 7 столбцов: 1, 2, 3... 7 карт."""
        piles = {}
        idx = 0

        for col in range(7):
            pile = Pile(f"tableau_{col}")

            for row in range(col + 1):
                card = deck[idx]
                is_last = (row == col)
                pile.put(Card(card.suit, card.rank, face_up=is_last))
                idx += 1

            piles[f"tableau_{col}"] = pile

        # Создаём пустые базы
        for suit in Suit:
            piles[f"foundation_{suit.name}"] = Pile(f"foundation_{suit.name}")

        return piles

    # === ПРАВИЛА ПОСТРОЕНИЯ ===

    def _can_build_tableau(self, pile: "Pile", cards: List["Card"]) -> bool:
        """Строим столбец: чередуем цвета, убываем рангом."""
        if not cards:
            return False

        if pile.is_empty():
            return cards[0].rank == Rank.KING

        top = pile.top()
        first = cards[0]

        return (
            top.color != first.color and
            top.rank.value == first.rank.value + 1
        )

    def _can_build_foundation(self, pile: "Pile", cards: List["Card"]) -> bool:
        """База: одна масть, возрастание от туза."""
        if len(pile) >= 13:
            return False

        if len(cards) != 1:
            return False

        card = cards[0]

        if pile.is_empty():
            return card.rank == Rank.ACE

        top = pile.top()

        return (
            top.suit == card.suit and
            card.rank.value == top.rank.value + 1
        )

    # === ВАЛИДАЦИЯ ХОДОВ ===

    def can_draw(self, state: "GameState") -> bool:
        """Можно ли взять карты из колоды."""
        return not state.stock.is_empty() or not state.waste.is_empty()

    def can_take(self, state: "GameState", pile_name: str, count: int = 1) -> bool:
        """Можно ли взять карты из стопки."""
        pile = state.get_pile(pile_name)
        if not pile:
            return False

        pile_type = self.get_pile_type(pile_name)

        if pile_type == PileType.TABLEAU:
            return pile.face_up_count() >= count

        if pile_type == PileType.WASTE:
            return not pile.is_empty() and count == 1

        return False  # stock и foundation нельзя

    def _validate_tableau_sequence(self, state: "GameState", move: "Move") -> bool:
        """Проверка, что из tableau берётся корректная последовательность."""
        if not move.from_pile.startswith("tableau_"):
            return True

        source = state.get_pile(move.from_pile)
        if source is None:
            return False

        # Проверяем, что берём открытые карты
        if len(move.cards) > source.face_up_count():
            return False

        cards_from_end = source.peek(len(move.cards))

        # Проверяем последовательность внутри
        for i in range(len(cards_from_end) - 1):
            curr = cards_from_end[i]
            next_card = cards_from_end[i + 1]

            if curr.color == next_card.color:
                return False
            if curr.rank.value != next_card.rank.value + 1:
                return False

        return True

    # === СЧЁТ ===

    def score_move(self, state: "GameState", move: "Move",
                   previous_state: Optional["GameState"] = None) -> int:
        """Подсчёт очков за ход."""
        score = 0

        # Открытие карт
        if previous_state:
            flipped = self.get_flipped_cards(previous_state, move)
            score += 5 * len(flipped)

        # На foundation
        if self.get_pile_type(move.to_pile) == PileType.FOUNDATION:
            score += 10
            # Штраф за обратный ход
            if self.get_pile_type(move.from_pile) == PileType.FOUNDATION:
                score = -15

        # С foundation на tableau
        elif (self.get_pile_type(move.from_pile) == PileType.FOUNDATION and
              self.get_pile_type(move.to_pile) == PileType.TABLEAU):
            score = -15

        return score

    def score_draw(self, previous_state: "GameState", cards: List["Card"]) -> int:
        """Очки за взятие карт из колоды."""
        return 0

    def score_recycle(self, state: "GameState") -> int:
        """Штраф за перебор колоды."""
        return -20 if self.draw_three else -10

    def get_draw_count(self) -> int:
        """Сколько карт вытягивать за раз."""
        return 3 if self.draw_three else 1

    # === ПОБОЧНЫЕ ЭФФЕКТЫ ===

    def get_flipped_cards(self, previous_state: "GameState", move: "Move") -> List[Tuple[str, int]]:
        """Какие карты перевернуть после хода."""
        flipped = []

        source_type = self.get_pile_type(move.from_pile)
        if source_type == PileType.TABLEAU:
            source = previous_state.get_pile(move.from_pile)
            if source and len(source) > len(move.cards):
                remaining = len(source) - len(move.cards)
                if remaining > 0:
                    top_card = source[remaining - 1]
                    if not top_card.face_up:
                        flipped.append((move.from_pile, remaining - 1))

        return flipped

    # === ПОБЕДА ===

    def _check_all_foundations_full(self, state: "GameState") -> bool:
        """Проверить, что все базы заполнены."""
        for suit in Suit:
            pile = state.piles.get(f"foundation_{suit.name}")
            if pile is None or len(pile) != 13:
                return False
        return True

    # === ПОДСКАЗКИ ===

    def get_available_moves(self, state: "GameState") -> List["Move"]:
        """Все возможные ходы в текущем состоянии."""
        # TODO: реализовать для подсказок и AI
        return []

    # === СТРОКОВОЕ ПРЕДСТАВЛЕНИЕ ===

    def __repr__(self) -> str:
        draw = "3" if self.draw_three else "1"
        return f"KlondikeRules(draw={draw})"