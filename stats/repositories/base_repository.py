# stats/repositories/base_repository.py
"""Базовый класс для всех репозиториев."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Dict, Any, List
from stats.data import connection_context

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Базовый репозиторий с общими методами."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @abstractmethod
    def get(self, id: str) -> Optional[T]:
        """Получить запись по ID."""
        pass

    @abstractmethod
    def create(self, entity: T) -> bool:
        """Создать новую запись."""
        pass

    @abstractmethod
    def update(self, id: str, data: Dict[str, Any]) -> bool:
        """Обновить запись."""
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Удалить запись."""
        pass

    def _execute(self, query: str, params: tuple = ()) -> Optional[List[Dict]]:
        """Выполнить запрос и вернуть результаты."""
        with connection_context() as conn:
            cursor = conn.execute(query, params)
            if cursor.description:  # Это SELECT
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            return None