# stats/repositories/player_repository.py
"""Репозиторий для работы с игроками."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from stats.models import Player
from stats.repositories.base_repository import BaseRepository
from stats.data import connection_context


class PlayerRepository(BaseRepository[Player]):
    """Репозиторий для операций с таблицей players."""

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.table_name = "players"

    def get(self, player_id: str) -> Optional[Player]:
        """
        Получить игрока по ID.

        Args:
            player_id: UUID игрока

        Returns:
            Player объект или None
        """
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self._execute(query, (player_id,))

        if results and len(results) > 0:
            return Player.from_dict(results[0])
        return None

    def get_by_name(self, name: str) -> List[Player]:
        """
        Найти игроков по имени (частичное совпадение).

        Args:
            name: Имя или часть имени

        Returns:
            Список подходящих игроков
        """
        query = f"SELECT * FROM {self.table_name} WHERE name LIKE ?"
        results = self._execute(query, (f"%{name}%",))

        return [Player.from_dict(row) for row in results]

    def create(self, player: Player) -> bool:
        """
        Создать нового игрока.

        Args:
            player: Player объект для сохранения

        Returns:
            True если успешно
        """
        data = player.to_dict()

        # Убираем поля, которых нет в БД
        data.pop('version', None)

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        query = f"""
            INSERT INTO {self.table_name} 
            ({columns}) VALUES ({placeholders})
        """

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error creating player: {e}")
            return False

    def update(self, player_id: str, data: Dict[str, Any]) -> bool:
        """
        Обновить данные игрока.

        Args:
            player_id: ID игрока
            data: Словарь с полями для обновления

        Returns:
            True если успешно
        """
        if not data:
            return True

        # Убираем поля, которые нельзя обновлять напрямую
        forbidden = {'id', 'created_at', 'version'}
        update_data = {k: v for k, v in data.items() if k not in forbidden}

        if not update_data:
            return True

        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [player_id]

        query = f"""
            UPDATE {self.table_name} 
            SET {set_clause} 
            WHERE id = ?
        """

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating player: {e}")
            return False

    def delete(self, player_id: str) -> bool:
        """
        Удалить игрока (осторожно!).

        Args:
            player_id: ID игрока

        Returns:
            True если успешно
        """
        query = f"DELETE FROM {self.table_name} WHERE id = ?"

        try:
            self._execute(query, (player_id,))
            return True
        except Exception as e:
            print(f"Error deleting player: {e}")
            return False

    # ===== Специализированные методы для статистики =====

    def update_last_played(self, player_id: str) -> bool:
        """Обновить время последнего входа."""
        return self.update(player_id, {
            'last_played': datetime.now().isoformat()
        })

    def increment_stat(self, player_id: str, stat_field: str,
                       increment: int = 1) -> bool:
        """
        Увеличить числовую статистику игрока.

        Пример:
            repo.increment_stat(player_id, 'games_won')
        """
        query = f"""
            UPDATE {self.table_name} 
            SET {stat_field} = {stat_field} + ? 
            WHERE id = ?
        """

        try:
            self._execute(query, (increment, player_id))
            return True
        except Exception as e:
            print(f"Error incrementing stat: {e}")
            return False

    def update_streak(self, player_id: str, won: bool) -> bool:
        """
        Обновить серии побед/поражений.

        Args:
            player_id: ID игрока
            won: True если победа, False если поражение
        """
        if won:
            # Победа: увеличиваем победную серию, сбрасываем серию поражений
            query = f"""
                UPDATE {self.table_name} 
                SET current_win_streak = current_win_streak + 1,
                    best_win_streak = MAX(best_win_streak, current_win_streak + 1),
                    current_loose_streak = 0
                WHERE id = ?
            """
        else:
            # Поражение: увеличиваем серию поражений, сбрасываем победную серию
            query = f"""
                UPDATE {self.table_name} 
                SET current_loose_streak = current_loose_streak + 1,
                    best_loose_streak = MAX(best_loose_streak, current_loose_streak + 1),
                    current_win_streak = 0
                WHERE id = ?
            """

        try:
            self._execute(query, (player_id,))
            return True
        except Exception as e:
            print(f"Error updating streak: {e}")
            return False

    def update_score(self, player_id: str, score: int) -> bool:
        """
        Обновить счёт игрока (total и highest).
        """
        query = f"""
            UPDATE {self.table_name} 
            SET total_score = total_score + ?,
                highest_score = MAX(COALESCE(highest_score, 0), ?)
            WHERE id = ?
        """

        try:
            self._execute(query, (score, score, player_id))
            return True
        except Exception as e:
            print(f"Error updating score: {e}")
            return False

    def update_play_time(self, player_id: str, seconds: int) -> bool:
        """Добавить время игры."""
        return self.increment_stat(player_id, 'total_play_time_seconds', seconds)

    def update_fastest_win(self, player_id: str, seconds: int) -> bool:
        """
        Обновить рекорд самой быстрой победы.
        """
        query = f"""
            UPDATE {self.table_name} 
            SET fastest_win_seconds = MIN(COALESCE(fastest_win_seconds, ?), ?)
            WHERE id = ? 
            AND (? < COALESCE(fastest_win_seconds, ?) OR fastest_win_seconds IS NULL)
        """

        try:
            self._execute(query, (seconds, seconds, player_id, seconds, seconds))
            return True
        except Exception as e:
            print(f"Error updating fastest win: {e}")
            return False

    def update_slowest_win(self, player_id: str, seconds: int) -> bool:
        """
        Обновить рекорд самой медленной победы.
        """
        query = f"""
            UPDATE {self.table_name} 
            SET slowest_win_seconds = MAX(COALESCE(slowest_win_seconds, 0), ?)
            WHERE id = ? 
            AND (? > COALESCE(slowest_win_seconds, 0) OR slowest_win_seconds IS NULL)
        """

        try:
            self._execute(query, (seconds, player_id, seconds))
            return True
        except Exception as e:
            print(f"Error updating slowest win: {e}")
            return False

    def get_all_players(self) -> List[Player]:
        """Получить всех игроков (для административных целей)."""
        query = f"""
            SELECT * FROM {self.table_name} 
            ORDER BY last_played DESC NULLS LAST
        """
        results = self._execute(query)
        return [Player.from_dict(row) for row in results]

    def get_top_players(self, limit: int = 10,
                        by: str = 'games_won') -> List[Player]:
        """
        Получить топ игроков по указанному критерию.

        Args:
            limit: Сколько игроков вернуть
            by: Поле для сортировки ('games_won', 'total_score', и т.д.)
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            ORDER BY {by} DESC 
            LIMIT ?
        """
        results = self._execute(query, (limit,))
        return [Player.from_dict(row) for row in results]