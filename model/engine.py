# model/engine.py
from typing import List, Callable, Optional
from dataclasses import dataclass, field
import random
from model import Card, Suit, Rank, Pile, GameState, RuleSet, HistoryManager


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
    def __init__(self, rules: RuleSet, player_id: str):
        self.rules = rules
        self.player_id = player_id
        self.state: Optional[GameState] = None
        self.history = HistoryManager(limit=5000)

    @property
    def state(self) -> GameState:
        return self._state

    def new_game(self, seed: Optional[int] = None):
        """Начать новую игру."""
        # 1. Перемешиваем
        deck = self._create_shuffled_deck(seed)

        # 2. Раздаём через правила
        dealt_piles = self.rules.deal(deck)

        # 3. Остаток в колоду
        dealt_count = sum(len(p) for p in dealt_piles.values())
        stock_cards = deck[dealt_count:]

        # 4. Создаём состояние
        self.state = GameState(
            piles=dealt_piles,
            stock=Pile("stock", stock_cards),
            waste=Pile("waste"),
            score=0,
            moves_count=0
        )

        # 5. История для undo
        self.history.clear()
        self.history.push(self.state)  # сохраняем начальное состояние

        # 6. Уведомляем
        self.state.notify("game_started", {"seed": seed})

    def _create_shuffled_deck(self, seed: Optional[int]) -> List[Card]:
        """Создать перемешанную колоду."""
        rng = random.Random(seed)  # Фиксированное зерно для воспроизводимости

        cards = [
            Card(suit, rank, face_up=False)
            for suit in Suit
            for rank in Rank
        ]

        rng.shuffle(cards)
        return cards

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