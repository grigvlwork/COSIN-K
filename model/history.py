"""
HistoryManager — управление историей ходов (undo/redo).
Реализует паттерн Memento для сохранения состояний игры.
"""

from typing import List, Optional, Callable
from dataclasses import dataclass, field
from .state import GameState, Move


@dataclass
class HistoryEntry:
    """Запись в истории: состояние + метаданные."""
    state: GameState
    move: Optional[Move] = None  # Какой ход привёл к этому состоянию
    timestamp: float = field(default_factory=lambda: __import__('time').time())


class HistoryManager:
    """
    Управляет undo/redo через хранение снимков состояния.
    Ограничивает глубину истории для экономии памяти.
    """

    def __init__(self, limit: int = 100):
        """
        Args:
            limit: Максимальное количество сохранённых состояний
        """
        self._entries: List[HistoryEntry] = []
        self._current: int = -1  # Индекс текущего состояния
        self._limit = limit

        # Слушатели событий истории
        self._on_change: List[Callable] = []

    # === Основные операции ===

    def push(self, state: GameState, move: Optional[Move] = None) -> None:
        """
        Сохранить новое состояние.
        Удаляет "будущее" при ветвлении истории.
        """
        # Удаляем всё после текущего (при новом ходе после undo)
        self._entries = self._entries[:self._current + 1]

        # Добавляем новое состояние
        entry = HistoryEntry(
            state=state.copy(),
            move=move
        )
        self._entries.append(entry)
        self._current += 1

        # Ограничиваем размер
        if len(self._entries) > self._limit:
            self._entries.pop(0)
            self._current -= 1

        self._notify_change()

    def undo(self) -> Optional[GameState]:
        """
        Откат на один ход назад.
        Returns: Предыдущее состояние или None
        """
        if not self.can_undo():
            return None

        self._current -= 1
        self._notify_change()

        # Возвращаем копию чтобы не испортить историю
        return self._entries[self._current].state.copy()

    def redo(self) -> Optional[GameState]:
        """
        Повтор отменённого хода.
        Returns: Следующее состояние или None
        """
        if not self.can_redo():
            return None

        self._current += 1
        self._notify_change()

        return self._entries[self._current].state.copy()

    # === Проверки ===

    def can_undo(self) -> bool:
        """Есть ли куда откатываться."""
        return self._current > 0  # 0 — начальное состояние, его не откатываем

    def can_redo(self) -> bool:
        """Есть ли что повторять."""
        return self._current < len(self._entries) - 1

    # === Доступ к истории ===

    @property
    def current_index(self) -> int:
        """Текущая позиция в истории."""
        return self._current

    @property
    def total_states(self) -> int:
        """Общее количество сохранённых состояний."""
        return len(self._entries)

    def get_move_history(self) -> List[Move]:
        """Список всех ходов до текущего состояния."""
        return [
            e.move for e in self._entries[:self._current + 1]
            if e.move is not None
        ]

    def get_current_state(self) -> Optional[GameState]:
        """Текущее состояние без изменения позиции."""
        if self._current < 0:
            return None
        return self._entries[self._current].state.copy()

    # === События ===

    def add_listener(self, callback: Callable[[str, dict], None]) -> None:
        """Подписаться на изменения истории."""
        self._on_change.append(callback)

    def remove_listener(self, callback: Callable[[str, dict], None]) -> None:
        """Отписаться от событий."""
        if callback in self._on_change:
            self._on_change.remove(callback)

    def _notify_change(self) -> None:
        """Уведомить слушателей."""
        info = {
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "current": self._current,
            "total": len(self._entries)
        }
        for listener in self._on_change:
            listener("history_changed", info)

    # === Служебное ===

    def clear(self) -> None:
        """Очистить всю историю."""
        self._entries.clear()
        self._current = -1
        self._notify_change()

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"HistoryManager({self._current + 1}/{len(self._entries)}, limit={self._limit})"