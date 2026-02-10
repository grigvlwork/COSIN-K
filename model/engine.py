# model/engine.py
from typing import List, Callable, Optional
from dataclasses import dataclass, field


@dataclass
class GameState:
    piles: dict
    stock: 'Pile'
    waste: 'Pile'
    score: int = 0
    moves: int = 0
    selected_pile: Optional[str] = None  # для UI

    # События для View
    _listeners: List[Callable] = field(default_factory=list, repr=False)

    def add_listener(self, callback: Callable):
        self._listeners.append(callback)

    def notify(self, event: str, data: dict = None):
        for listener in self._listeners:
            listener(event, data)


class SolitaireEngine:
    def __init__(self, rules, player_id: str):
        self.rules = rules
        self.player_id = player_id
        self._state: Optional[GameState] = None
        self._history: List[GameState] = []

    @property
    def state(self) -> GameState:
        return self._state

    def new_game(self, seed=None):
        # ... логика раздачи
        self._state = self._deal()
        self._history.clear()
        self._save_state()
        self._state.notify("game_started", {"seed": seed})

    def move(self, from_pile: str, to_pile: str, count: int = 1) -> bool:
        # ... валидация и выполнение
        success = self._execute_move(from_pile, to_pile, count)
        if success:
            self._save_state()
            self._state.notify("move_made", {
                "from": from_pile,
                "to": to_pile,
                "count": count
            })
            if self.check_win():
                self._state.notify("game_won", {"score": self._state.score})
        return success

    def undo(self) -> bool:
        if len(self._history) > 1:
            self._history.pop()
            self._state = self._history[-1].copy()
            self._state.notify("undo", {})
            return True
        return False