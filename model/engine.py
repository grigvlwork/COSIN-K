"""
GameEngine — игровая логика и управление ходами.
"""

from typing import List, Callable, Optional, Dict, Any
import random
from dataclasses import dataclass, field

from .card import Card, Suit, Rank
from .pile import Pile
from .state import GameState
from .move import Move
from .history import HistoryManager
from .rules.base import RuleSet


class SolitaireEngine:
    """
    Движок пасьянса.
    Связывает правила, состояние и историю.
    """

    def __init__(self, rules: RuleSet, player_id: str = "player1"):
        self.rules = rules
        self.player_id = player_id
        self._state: Optional[GameState] = None
        self.history = HistoryManager(limit=5000)
        self._listeners: List[Callable[[str, Dict[str, Any]], None]] = []

    # === Свойства ===

    @property
    def state(self) -> Optional[GameState]:
        """Текущее состояние игры."""
        return self._state

    @property
    def is_game_active(self) -> bool:
        """Идёт ли игра."""
        return self._state is not None

    # === Управление игрой ===

    def new_game(self, seed: Optional[int] = None) -> None:
        """Начать новую игру."""
        # 1. Создаём перемешанную колоду
        deck = self._create_shuffled_deck(seed)

        # 2. Раздаём карты через правила
        dealt_piles = self.rules.deal(deck)

        # 3. Оставшиеся карты в колоду
        dealt_count = sum(len(p) for p in dealt_piles.values())
        stock_cards = deck[dealt_count:]

        # 4. Создаём начальное состояние
        self._state = GameState(
            piles=dealt_piles,
            stock=Pile("stock", stock_cards),
            waste=Pile("waste"),
            score=0,
            moves_count=0,
            time_elapsed=0
        )

        # 5. Сохраняем в истории
        self.history.clear()
        self.history.push(self._state.copy(), move=None)

        # 6. Уведомляем
        self._notify("game_started", {"seed": seed})

    def _create_shuffled_deck(self, seed: Optional[int]) -> List[Card]:
        """Создать перемешанную колоду."""
        rng = random.Random(seed)
        cards = [Card(suit, rank, face_up=False)
                 for suit in Suit
                 for rank in Rank]
        rng.shuffle(cards)
        return cards

    # === Ходы ===

    def draw(self) -> bool:
        """Взять карту(ы) из колоды."""
        if not self._state:
            return False

        if not self.rules.can_draw(self._state):
            return False

        new_state = self._state.copy()
        draw_count = self.rules.get_draw_count()

        # Recycle если колода пуста
        if new_state.stock.is_empty():
            if not self._recycle_stock(new_state):
                return False
            # После recycle обновляем состояние и берём карты
            self._state = new_state
            return self.draw()

        # Нормальное взятие карт
        actual_count = min(draw_count, len(new_state.stock))
        cards = new_state.stock.take(actual_count)
        cards = [card.make_face_up() for card in cards]
        new_state.waste.add(cards)
        new_state.moves_count += 1

        # Создаём Move
        move = Move(
            from_pile="stock",
            to_pile="waste",
            cards=cards,
            from_index=len(new_state.stock),
            flipped_cards=[],
            score_delta=self.rules.score_draw(self._state, cards)
        )

        # Применяем
        self._state = new_state
        self.history.push(self._state.copy(), move)
        self._notify("draw", {"count": actual_count})

        return True

    def move(self, from_pile: str, to_pile: str, count: int = 1) -> bool:
        """
        Переместить карты из одной стопки в другую.
        Возвращает True если ход успешен.
        """
        if not self._state:
            return False
        print(f"\n🔍 ENGINE MOVE DEBUG:")
        print(f"  from: {from_pile}")
        print(f"  to: {to_pile}")
        print(f"  count: {count}")


        # 1. Проверяем валидность через правила
        # Создаём move без cards
        move = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=[],  # будут заполнены при выполнении
            from_index=-1
        )

        if not self.rules.can_move(self._state, move):  # ← только state и move
            return False

        # 2. Выполняем ход
        try:
            new_state, executed_move = self._execute_move(from_pile, to_pile, count)
        except ValueError:
            return False

        # 3. Сохраняем новое состояние
        self._state = new_state
        self.history.push(self._state.copy(), executed_move)

        # 4. Проверяем победу
        if self.rules.check_win(self._state):
            self._notify("game_won", {"score": self._state.score})

        # 5. Уведомляем
        self._notify("move_made", {
            "from": from_pile,
            "to": to_pile,
            "count": count,
            "score": self._state.score
        })

        return True

    def _execute_move(self, from_pile: str, to_pile: str, count: int) -> tuple[GameState, Move]:
        """
        Реальное выполнение хода.
        Возвращает (новое_состояние, объект Move).
        """
        # Копируем состояние
        new_state = self._state.copy()

        # Получаем стопки
        source = new_state.get_pile(from_pile)
        target = new_state.get_pile(to_pile)

        if not source or not target:
            raise ValueError(f"Invalid piles: {from_pile} or {to_pile}")

        # Берём карты
        from_index = len(source) - count  # индекс первой карты
        cards = source.take(count)

        # Добавляем в целевую стопку
        target.add(cards)

        # Обновляем счётчики
        move_for_score = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=cards,
            from_index=from_index
        )
        score_delta = self.rules.calculate_score(self._state, move_for_score)
        new_state.score += score_delta
        new_state.moves_count += 1

        # Создаём объект хода
        move = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=cards,
            from_index=from_index,
            flipped_cards=[],  # правила могут добавить перевёрнутые карты
            score_delta=score_delta
        )

        return new_state, move

    # === Отмена/повтор ===

    def undo(self) -> bool:
        """Отменить последний ход."""
        if not self._state or not self.history.can_undo():
            return False

        prev_state = self.history.undo()
        if prev_state:
            self._state = prev_state
            self._notify("undo", {
                "can_undo": self.history.can_undo(),
                "can_redo": self.history.can_redo()
            })
            return True
        return False

    def redo(self) -> bool:
        """Повторить отменённый ход."""
        if not self._state or not self.history.can_redo():
            return False

        next_state = self.history.redo()
        if next_state:
            self._state = next_state
            self._notify("redo", {
                "can_undo": self.history.can_undo(),
                "can_redo": self.history.can_redo()
            })
            return True
        return False

    # === Проверки ===

    def check_win(self) -> bool:
        """Проверить, выиграна ли игра."""
        if not self._state:
            return False
        return self.rules.check_win(self._state)

    def get_hint(self) -> Optional[Move]:
        """Получить подсказку от правил."""
        if not self._state:
            return None
        return self.rules.get_hint(self._state)

    def _recycle_stock(self, new_state: GameState) -> bool:
        """Перебор колоды: waste → stock."""
        if new_state.waste.is_empty():
            return False

        cards = new_state.waste.take(len(new_state.waste))
        cards = [card.make_face_down() for card in cards]
        new_state.stock.add(cards)

        move = Move(
            from_pile="waste",
            to_pile="stock",
            cards=cards,
            from_index=0,
            flipped_cards=[("waste", i) for i in range(len(cards))],
            score_delta=self.rules.score_recycle(self._state)
        )

        # НЕ обновляем self._state здесь — это сделает draw()
        self.history.push(new_state.copy(), move)  # сохраняем recycle в историю
        self._notify("recycle", {"count": len(cards)})

        return True

    # === События ===

    def add_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Подписаться на события движка."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Отписаться от событий."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Уведомить слушателей о событии."""
        data = data or {}
        data["engine"] = self
        for listener in self._listeners:
            listener(event, data)