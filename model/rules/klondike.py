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
        from model import Move
        moves = []

        # 1. ХОДЫ ИЗ STOCK/WASTE
        # Взять карты из колоды (если можно)
        # Не добавляем в moves, т.к. draw - отдельная команда

        # 2. ХОДЫ ИЗ TABLEAU
        for col in range(7):
            pile_name = f"tableau_{col}"
            pile = state.piles.get(pile_name)
            if not pile or pile.is_empty():
                continue

            # Сколько открытых карт можно взять
            face_up_count = pile.face_up_count()
            if face_up_count == 0:
                continue

            # Можно взять 1 карту или последовательность
            for take_count in range(1, face_up_count + 1):
                # Проверяем, что последовательность корректная
                cards = pile.peek(take_count)
                if not self._is_valid_sequence(cards):
                    continue

                # 2.1 ХОДЫ НА TABLEAU
                for target_col in range(7):
                    if target_col == col:
                        continue

                    target_name = f"tableau_{target_col}"
                    target_pile = state.piles.get(target_name)

                    # Создаем move для проверки
                    move = Move(
                        from_pile=pile_name,
                        to_pile=target_name,
                        cards=cards,
                        from_index=len(pile) - take_count
                    )

                    # Проверяем валидность хода
                    if self.can_move(state, move):
                        moves.append(move)

                # 2.2 ХОДЫ НА FOUNDATION
                for suit in Suit:
                    target_name = f"foundation_{suit.name}"
                    target_pile = state.piles.get(target_name)

                    # На foundation можно класть только 1 карту
                    if take_count != 1:
                        continue

                    move = Move(
                        from_pile=pile_name,
                        to_pile=target_name,
                        cards=cards,
                        from_index=len(pile) - 1
                    )

                    if self.can_move(state, move):
                        moves.append(move)

        # 3. ХОДЫ ИЗ FOUNDATION
        # (обратно на tableau - со штрафом, но разрешено в некоторых ситуациях)
        for suit in Suit:
            pile_name = f"foundation_{suit.name}"
            pile = state.piles.get(pile_name)
            if not pile or pile.is_empty():
                continue

            # Берем верхнюю карту
            cards = [pile.top()]

            # Ходы на tableau
            for target_col in range(7):
                target_name = f"tableau_{target_col}"

                move = Move(
                    from_pile=pile_name,
                    to_pile=target_name,
                    cards=cards,
                    from_index=len(pile) - 1
                )

                if self.can_move(state, move):
                    moves.append(move)

        # 4. ХОДЫ ИЗ WASTE
        if state.waste and not state.waste.is_empty():
            pile_name = "waste"
            cards = [state.waste.top()]

            # 4.1 На foundation
            for suit in Suit:
                target_name = f"foundation_{suit.name}"
                move = Move(
                    from_pile=pile_name,
                    to_pile=target_name,
                    cards=cards,
                    from_index=len(state.waste) - 1
                )
                if self.can_move(state, move):
                    moves.append(move)

            # 4.2 На tableau
            for target_col in range(7):
                target_name = f"tableau_{target_col}"
                move = Move(
                    from_pile=pile_name,
                    to_pile=target_name,
                    cards=cards,
                    from_index=len(state.waste) - 1
                )
                if self.can_move(state, move):
                    moves.append(move)

        # Удаляем дубликаты (если есть)
        unique_moves = []
        move_keys = set()
        for move in moves:
            key = (move.from_pile, move.to_pile, len(move.cards))
            if key not in move_keys:
                move_keys.add(key)
                unique_moves.append(move)

        return unique_moves

    def _is_valid_sequence(self, cards: List["Card"]) -> bool:
        """Проверка, что карты образуют правильную последовательность для перемещения."""
        if len(cards) <= 1:
            return True

        for i in range(len(cards) - 1):
            curr = cards[i]
            next_card = cards[i + 1]

            # Чередование цветов
            if curr.color == next_card.color:
                return False
            # Убывание ранга
            if curr.rank.value != next_card.rank.value + 1:
                return False

        return True

    def get_hint(self, state: "GameState") -> Optional["Move"]:
        """Вернуть один возможный ход для подсказки."""
        moves = self.get_available_moves(state)

        if not moves:
            return None

        # Приоритет: foundation > tableau > waste
        foundation_moves = []
        tableau_moves = []
        waste_moves = []

        for move in moves:
            if move.to_pile.startswith("foundation_"):
                foundation_moves.append(move)
            elif move.from_pile == "waste":
                waste_moves.append(move)
            else:
                tableau_moves.append(move)

        # Сначала ходы на foundation
        if foundation_moves:
            return foundation_moves[0]
        # Потом из waste
        if waste_moves:
            return waste_moves[0]
        # Потом остальные
        if tableau_moves:
            return tableau_moves[0]

        return moves[0] if moves else None

    def get_game_help(self) -> str:
        """Справка по правилам Косынки."""
        draw_mode = "3 cards" if self.draw_three else "1 card"
        return f"""
=== Klondike Solitaire ({draw_mode}) ===

Game rules:
  • Build tableau down in alternating colors
  • Build foundations up in same suit from Ace
  • Draw {self.get_draw_count()} card(s) from stock
  • Kings can be placed on empty tableau piles

Variants:
  • new           — Klondike (1 card draw)
  • new klondike-3 — Klondike (3 cards draw)
"""

    def get_shortcuts_text(self) -> str:
        """Шорткаты для Косынки."""
        return """
Move shortcuts:
  m 0 h        — move tableau_0 → hearts
  m 5 d        — move tableau_5 → diamonds
  m w c        — move waste → clubs
  m 3 4        — move tableau_3 → tableau_4
"""

    def get_quick_moves_text(self) -> str:
        """Быстрые команды для Косынки."""
        return """
Quick moves (no 'm'):
  0h           — tableau_0 → hearts
  5d           — tableau_5 → diamonds
  wh           — waste → hearts
  t3s          — tableau_3 → spades
  <n>          — auto-move from tableau_n (0-6)
                 (to foundation or rightmost tableau)
  w            — auto-move from waste
"""

    def validate_shortcut(self, command: str) -> Optional[Tuple[str, str, int]]:
        """
        Проверить, является ли команда шорткатом для Косынки.
        Возвращает (from_pile, to_pile, count) или None.
        """
        command = command.lower().strip()

        # Шорткаты вида "0h", "5d", "wc", "t3s"
        if len(command) == 2:
            source = command[0]
            dest = command[1]

            suit_map = {
                'h': 'HEARTS',
                'd': 'DIAMONDS',
                'c': 'CLUBS',
                's': 'SPADES'
            }

            if dest in suit_map:
                # Источник - цифра (tableau)
                if source.isdigit():
                    from_pile = f"tableau_{source}"
                    to_pile = f"foundation_{suit_map[dest]}"
                    return (from_pile, to_pile, 1)

                # Источник - waste
                elif source == 'w':
                    return ("waste", f"foundation_{suit_map[dest]}", 1)

        # Шорткаты вида "t3s" (tableau_3 → spades)
        if len(command) == 3 and command[0] == 't' and command[1].isdigit() and command[2] in 'hdcs':
            col = command[1]
            dest = command[2]
            suit_map = {'h': 'HEARTS', 'd': 'DIAMONDS', 'c': 'CLUBS', 's': 'SPADES'}
            from_pile = f"tableau_{col}"
            to_pile = f"foundation_{suit_map[dest]}"
            return (from_pile, to_pile, 1)

        # Авто-ход из tableau (одна цифра)
        if len(command) == 1 and command.isdigit():
            # Это обрабатывается отдельно в _cmd_quick_move
            return None

        # Авто-ход из waste (w)
        if command == 'w':
            # Это обрабатывается отдельно в _cmd_quick_waste
            return None

        return None

    # === СТРОКОВОЕ ПРЕДСТАВЛЕНИЕ ===

    def __repr__(self) -> str:
        draw = "3" if self.draw_three else "1"
        return f"KlondikeRules(draw={draw})"
