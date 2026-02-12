"""
KlondikeRules — классическая косынка (Solitaire/Patience).
"""

from typing import TYPE_CHECKING, List, Dict, Optional

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
            self._validate_tableau_sequence,  # Только последовательность можно взять
        ]

        # Условие победы — все базы полны
        self._win_condition = self._check_all_foundations_full

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
        return PileType.RESERVE  # или raise ValueError

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

    def get_available_moves(self, state: "GameState") -> List["Move"]:
        """Все возможные ходы в текущем состоянии."""
        # TODO: реализовать для подсказок и AI
        return []

    def _can_build_foundation(self, pile: "Pile", cards: List["Card"]) -> bool:
        """
        База: одна масть, возрастание от туза.
        Только по 1 карте за раз.
        """
        if len(pile) >= 13:
            return False

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

    def can_take(self, state: "GameState", pile_name: str, count: int = 1) -> bool:
        """
        Для Клондайка:
        - Из tableau: только открытые карты с конца
        - Из waste: только 1 карта
        - Из stock: нельзя брать (перебор через recycle)
        """
        pile = state.get_pile(pile_name)
        if not pile:
            return False

        pile_type = self.get_pile_type(pile_name)

        if pile_type == PileType.TABLEAU:
            return pile.face_up_count() >= count

        if pile_type == PileType.WASTE:
            return not pile.is_empty() and count == 1

        if pile_type == PileType.STOCK:
            return False  # stock не даёт брать карты, только перебор

        if pile_type == PileType.FOUNDATION:
            return False  # нельзя брать из foundation

        return False

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

    def score_move(self, state: "GameState", move: "Move",
                   previous_state: Optional["GameState"] = None) -> int:
        """Подсчёт очков с учётом открытых карт."""
        score = 0
        if previous_state:
            flipped = self.get_flipped_cards(previous_state, move)
            score += 5 * len(flipped)
        # На foundation
        if self.get_pile_type(move.to_pile) == PileType.FOUNDATION:
            score += 10

            # С foundation — штраф
            if self.get_pile_type(move.from_pile) == PileType.FOUNDATION:
                score = -15  # замена, не добавление!

        # С foundation на tableau
        elif (self.get_pile_type(move.from_pile) == PileType.FOUNDATION and
              self.get_pile_type(move.to_pile) == PileType.TABLEAU):
            score = -15

        return score

    def score_recycle(self, state: "GameState") -> int:
        """Штраф за перебор колоды."""
        return -20 if self.draw_three else -10

    def get_draw_count(self) -> int:
        """Сколько карт вытягивать из колоды за раз."""
        return 3 if self.draw_three else 1

    def get_flipped_cards(self, previous_state: "GameState", move: "Move") -> List[Tuple[str, int]]:
        """Определить карты для переворота на основе состояния ДО хода."""
        flipped = []

        source_type = self.get_pile_type(move.from_pile)
        if source_type == PileType.TABLEAU:
            source = previous_state.get_pile(move.from_pile)
            # Берём стопку ДО хода
            if source and len(source) > len(move.cards):
                # Индекс карты, которая станет верхней после взятия
                remaining = len(source) - len(move.cards)
                if remaining > 0:
                    top_card = source[remaining - 1]
                    if not top_card.face_up:
                        flipped.append((move.from_pile, remaining - 1))

        return flipped

    def recycle_stock(self, state: "GameState") -> Optional["Move"]:
        """
        Создать Move для перебора колоды, НЕ изменяя состояние.
        """
        if state.waste.is_empty():
            return None

        cards = state.waste.cards[:]  # копия списка карт
        cards = [card.make_face_down() for card in cards]

        from ..move import Move
        return Move(
            from_pile="waste",
            to_pile="stock",
            cards=cards,
            from_index=0,
            flipped_cards=[("waste", i) for i in range(len(cards))],
            score_delta=self.score_recycle(state)
        )

    # === Строковое представление ===

    def __repr__(self) -> str:
        draw = "3" if self.draw_three else "1"
        return f"KlondikeRules(draw={draw})"
