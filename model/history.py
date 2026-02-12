"""
HistoryManager — управление историей ходов (undo/redo).
Реализует паттерн Memento для сохранения состояний игры.
"""

from typing import List, Optional, Callable
from dataclasses import dataclass, field
from .state import GameState
from .move import Move
import weakref


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
        self._on_change: List[weakref.ref] = []

    # === Основные операции ===

    def push(self, state: GameState, move: Optional[Move] = None) -> None:
        # Удаляем будущее
        self._entries = self._entries[:self._current + 1]

        # Добавляем новое состояние
        entry = HistoryEntry(state=state.copy(), move=move)
        self._entries.append(entry)
        self._current += 1

        # Ограничиваем размер
        if len(self._entries) > self._limit:
            # Удаляем самый старый ЭЛЕМЕНТ (не по индексу, а по времени)
            self._entries.pop(0)
            # Если удалили элемент до текущего, сдвигаем индекс
            self._current = max(-1, self._current - 1)

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
        if self._current < 0:
            return None
        return self._entries[self._current].state.copy()  # ← Правильно!

    def go_to(self, index: int) -> Optional[GameState]:
        """Перейти к конкретному состоянию по индексу."""
        if 0 <= index < len(self._entries):
            self._current = index
            self._notify_change()
            return self.get_current_state()
        return None

    def truncate_future(self) -> None:
        """Удалить все состояния после текущего."""
        if self._current < len(self._entries) - 1:
            self._entries = self._entries[:self._current + 1]
            self._notify_change()

    def to_dict(self) -> dict:
        """Экспорт истории для сохранения."""
        return {
            "entries": [{
                "state": entry.state.to_dict(),  # нужен метод в GameState
                "move": entry.move.to_dict() if entry.move else None,
                "timestamp": entry.timestamp
            } for entry in self._entries],
            "current": self._current,
            "limit": self._limit
        }

    # === События ===

    def add_listener(self, callback):
        self._on_change.append(weakref.ref(callback))

    def remove_listener(self, callback: Callable[[str, dict], None]) -> None:
        """Отписаться от событий."""
        if callback in self._on_change:
            self._on_change.remove(callback)

    def _notify_change(self):
        info = {...}
        dead_refs = []
        for ref in self._on_change:
            listener = ref()
            if listener:
                listener("history_changed", info)
            else:
                dead_refs.append(ref)
        # Очищаем мёртвые ссылки
        for ref in dead_refs:
            self._on_change.remove(ref)

    # === Служебное ===

    def clear(self) -> None:
        self._entries.clear()
        self._current = -1  # ← -1, а не 0!
        self._notify_change()

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"HistoryManager({self._current + 1}/{len(self._entries)}, limit={self._limit})"
