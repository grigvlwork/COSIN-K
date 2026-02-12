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

    def move(self, from_pile: str, to_pile: str, count: int = 1) -> bool:
        """
        Переместить карты из одной стопки в другую.
        Возвращает True если ход успешен.
        """
        if not self._state:
            return False

        # 1. Проверяем валидность через правила
        move = Move(
            from_pile=from_pile,
            to_pile=to_pile,
            cards=[],  # будут заполнены при выполнении
            from_index=-1  # по умолчанию с конца
        )

        if not self.rules.can_move(self._state, move, count):
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
        score_delta = self.rules.calculate_score(self._state, from_pile, to_pile, cards)
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