# stats/repositories/achievement_repository.py
"""Репозиторий для работы с достижениями."""

from typing import Optional, List, Dict, Any
from stats.models import Achievement, PlayerAchievement
from stats.repositories.base_repository import BaseRepository
from stats.data import connection_context
from datetime import datetime


class AchievementRepository(BaseRepository[Achievement]):
    """Репозиторий для шаблонов достижений."""

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.table_name = "achievements"

    def get(self, id: str) -> Optional[Achievement]:
        """Получить достижение по ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self._execute(query, (id,))
        if results:
            return Achievement.from_dict(results[0])
        return None

    def get_all(self) -> List[Achievement]:
        """Получить все шаблоны достижений."""
        query = f"SELECT * FROM {self.table_name}"
        results = self._execute(query)
        return [Achievement.from_dict(row) for row in results]

    def create(self, entity: Achievement) -> bool:
        """Создать новый шаблон достижения (используется при инициализации)."""
        data = entity.to_dict()
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        query = f"INSERT OR IGNORE INTO {self.table_name} ({columns}) VALUES ({placeholders})"

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error creating achievement: {e}")
            return False

    def update(self, id: str, data: Dict[str, Any]) -> bool:
        """Обновление шаблонов обычно не требуется, но метод обязателен."""
        return False

    def delete(self, id: str) -> bool:
        """Удаление шаблонов обычно не требуется."""
        return False


class PlayerAchievementRepository(BaseRepository[PlayerAchievement]):
    """Репозиторий для прогресса игроков."""

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.table_name = "player_achievements"

    def get(self, id: int) -> Optional[PlayerAchievement]:
        """Получить запись прогресса по ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self._execute(query, (id,))
        if results:
            return PlayerAchievement.from_dict(results[0])
        return None

    def get_by_player(self, player_id: str) -> List[PlayerAchievement]:
        """Получить все достижения игрока."""
        query = f"SELECT * FROM {self.table_name} WHERE player_id = ?"
        results = self._execute(query, (player_id,))
        return [PlayerAchievement.from_dict(row) for row in results]

    def get_player_achievement(self, player_id: str, achievement_id: str) -> Optional[PlayerAchievement]:
        """Получить прогресс конкретного достижения."""
        query = f"SELECT * FROM {self.table_name} WHERE player_id = ? AND achievement_id = ?"
        results = self._execute(query, (player_id, achievement_id))
        if results:
            return PlayerAchievement.from_dict(results[0])
        return None

    def create(self, entity: PlayerAchievement) -> bool:
        """Создать запись прогресса."""
        data = entity.to_dict()
        data.pop('id', None)  # ID автоинкрементный

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error creating player achievement: {e}")
            return False

    def update(self, id: int, data: Dict[str, Any]) -> bool:
        """Обновить прогресс."""
        if not data:
            return True

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [id]

        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?"

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating player achievement: {e}")
            return False

    def delete(self, id: str) -> bool:
        return False

    def update_progress(self, player_id: str, achievement_id: str, progress: int, unlocked: bool) -> bool:
        """Обновить или создать прогресс."""
        existing = self.get_player_achievement(player_id, achievement_id)

        update_data = {
            'progress': progress,
            'unlocked': unlocked
        }
        if unlocked:
            update_data['unlocked_at'] = datetime.now()

        if existing:
            return self.update(existing.id, update_data)
        else:
            # Создаем новую запись
            new_pa = PlayerAchievement(
                id=None,
                player_id=player_id,
                achievement_id=achievement_id,
                progress=progress,
                unlocked=unlocked,
                unlocked_at=update_data.get('unlocked_at')
            )
            return self.create(new_pa)