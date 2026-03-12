# stats/repositories/game_repository.py
"""
Репозиторий для работы с завершёнными играми (таблица games).

Предоставляет методы для:
- Сохранения результатов игр
- Получения истории игр игрока
- Анализа статистики по играм
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

from stats.models import Game
from stats.repositories.base_repository import BaseRepository
from stats.data import connection_context


class GameRepository(BaseRepository[Game]):
    """
    Репозиторий для операций с таблицей games.

    Пример использования:
        >>> repo = GameRepository(db_path)
        >>>
        >>> # Создание игры
        >>> game = Game(player_id="123", game_type="klondike")
        >>> game_id = repo.create(game)
        >>>
        >>> # Завершение игры
        >>> repo.update(game_id, {"result": "won", "score": 150})
        >>>
        >>> # Получение истории
        >>> games = repo.get_by_player("123", limit=10)
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.table_name = "games"

    # ===== БАЗОВЫЕ МЕТОДЫ =====

    def get(self, game_id: int) -> Optional[Game]:
        """
        Получить игру по ID.

        Args:
            game_id: ID игры

        Returns:
            Game объект или None
        """
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self._execute(query, (game_id,))

        if results and len(results) > 0:
            return Game.from_dict(results[0])
        return None

    def create(self, game: Game) -> Optional[int]:
        """
        Создать новую запись об игре.

        Args:
            game: Game объект (без id)

        Returns:
            int: ID созданной игры или None если ошибка

        Пример:
            >>> game = Game(player_id="123", game_type="klondike")
            >>> game_id = repo.create(game)
        """
        data = game.to_dict()

        # Убираем поля, которые будут auto-filled
        data.pop('id', None)
        data.pop('started_at', None)  # БД сама поставит CURRENT_TIMESTAMP

        # Преобразуем списки в JSON
        if 'suits_completed' in data and data['suits_completed']:
            data['suits_completed'] = json.dumps(data['suits_completed'])

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        query = f"""
            INSERT INTO {self.table_name} 
            ({columns}) VALUES ({placeholders})
        """

        try:
            with connection_context() as conn:
                cursor = conn.execute(query, tuple(values))
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating game: {e}")
            return None

    def update(self, game_id: int, data: Dict[str, Any]) -> bool:
        """
        Обновить данные игры (например, при завершении).

        Args:
            game_id: ID игры
            data: Словарь с полями для обновления

        Returns:
            True если успешно
        """
        if not data:
            return True

        # Запрещаем менять некоторые поля
        forbidden = {'id', 'player_id', 'started_at'}
        update_data = {k: v for k, v in data.items() if k not in forbidden}

        if not update_data:
            return True

        # Преобразуем JSON поля
        if 'suits_completed' in update_data and update_data['suits_completed']:
            update_data['suits_completed'] = json.dumps(update_data['suits_completed'])

        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [game_id]

        query = f"""
            UPDATE {self.table_name} 
            SET {set_clause} 
            WHERE id = ?
        """

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating game: {e}")
            return False

    def delete(self, game_id: int) -> bool:
        """
        Удалить игру (осторожно!).

        Args:
            game_id: ID игры

        Returns:
            True если успешно
        """
        query = f"DELETE FROM {self.table_name} WHERE id = ?"

        try:
            self._execute(query, (game_id,))
            return True
        except Exception as e:
            print(f"Error deleting game: {e}")
            return False

    # ===== МЕТОДЫ ДЛЯ СТАТИСТИКИ =====

    def get_by_player(self, player_id: str, limit: int = 100,
                      from_date: Optional[datetime] = None) -> List[Game]:
        """
        Получить игры игрока.

        Args:
            player_id: UUID игрока
            limit: Максимальное количество игр
            from_date: Только игры после этой даты

        Returns:
            List[Game]: Список игр
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ?
        """
        params = [player_id]

        if from_date:
            query += " AND started_at >= ?"
            params.append(from_date.isoformat())

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        results = self._execute(query, tuple(params))

        games = []
        for row in results:
            game = Game.from_dict(row)
            games.append(game)

        return games

    def get_recent_games(self, player_id: str, days: int = 30) -> List[Game]:
        """
        Получить игры за последние N дней.

        Args:
            player_id: UUID игрока
            days: Количество дней

        Returns:
            List[Game]: Список игр
        """
        cutoff = datetime.now() - timedelta(days=days)
        return self.get_by_player(player_id, limit=1000, from_date=cutoff)

    def get_wins(self, player_id: str, limit: int = 100) -> List[Game]:
        """
        Получить только победы игрока.

        Args:
            player_id: UUID игрока
            limit: Максимальное количество

        Returns:
            List[Game]: Список побед
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND result = 'won'
            ORDER BY started_at DESC LIMIT ?
        """

        results = self._execute(query, (player_id, limit))
        return [Game.from_dict(row) for row in results]

    def get_losses(self, player_id: str, limit: int = 100) -> List[Game]:
        """
        Получить только поражения игрока.

        Args:
            player_id: UUID игрока
            limit: Максимальное количество

        Returns:
            List[Game]: Список поражений
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND result = 'lost'
            ORDER BY started_at DESC LIMIT ?
        """

        results = self._execute(query, (player_id, limit))
        return [Game.from_dict(row) for row in results]

    # ===== МЕТОДЫ ДЛЯ АНАЛИТИКИ =====

    def get_stats_summary(self, player_id: str) -> Dict[str, Any]:
        """
        Получить сводку по играм игрока.

        Args:
            player_id: UUID игрока

        Returns:
            Dict со сводкой:
                - total_games: всего игр
                - wins: побед
                - losses: поражений
                - abandoned: брошенных
                - total_score: сумма очков
                - avg_score: средний счёт
                - best_score: лучший счёт
                - total_time: общее время
                - avg_time: среднее время
        """
        query = f"""
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'lost' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'abandoned' THEN 1 ELSE 0 END) as abandoned,
                SUM(COALESCE(score, 0)) as total_score,
                AVG(COALESCE(score, 0)) as avg_score,
                MAX(COALESCE(score, 0)) as best_score,
                SUM(COALESCE(duration_seconds, 0)) as total_time,
                AVG(COALESCE(duration_seconds, 0)) as avg_time
            FROM {self.table_name}
            WHERE player_id = ?
        """

        results = self._execute(query, (player_id,))
        if results and len(results) > 0:
            row = results[0]
            return {
                'total_games': row['total_games'] or 0,
                'wins': row['wins'] or 0,
                'losses': row['losses'] or 0,
                'abandoned': row['abandoned'] or 0,
                'total_score': row['total_score'] or 0,
                'avg_score': round(row['avg_score'] or 0, 2),
                'best_score': row['best_score'] or 0,
                'total_time': row['total_time'] or 0,
                'avg_time': round(row['avg_time'] or 0, 2)
            }

        return {
            'total_games': 0, 'wins': 0, 'losses': 0, 'abandoned': 0,
            'total_score': 0, 'avg_score': 0, 'best_score': 0,
            'total_time': 0, 'avg_time': 0
        }

    def get_game_type_stats(self, player_id: str) -> Dict[str, Dict[str, int]]:
        """
        Получить статистику по типам игр.

        Args:
            player_id: UUID игрока

        Returns:
            Dict с статистикой по каждому типу:
                {
                    "klondike": {"played": 10, "won": 5},
                    "spider": {"played": 3, "won": 1}
                }
        """
        query = f"""
            SELECT 
                game_type,
                COUNT(*) as played,
                SUM(CASE WHEN result = 'won' THEN 1 ELSE 0 END) as won
            FROM {self.table_name}
            WHERE player_id = ?
            GROUP BY game_type
        """

        results = self._execute(query, (player_id,))

        stats = {}
        for row in results:
            stats[row['game_type']] = {
                'played': row['played'],
                'won': row['won'] or 0
            }

        return stats

    def get_time_stats(self, player_id: str) -> Dict[str, Any]:
        """
        Получить статистику по времени игры.

        Args:
            player_id: UUID игрока

        Returns:
            Dict с статистикой:
                - by_hour: распределение по часам
                - by_weekday: распределение по дням недели
                - weekend_games: игр в выходные
        """
        query = f"""
            SELECT 
                hour_of_day,
                COUNT(*) as games
            FROM {self.table_name}
            WHERE player_id = ? AND hour_of_day IS NOT NULL
            GROUP BY hour_of_day
            ORDER BY hour_of_day
        """

        hour_results = self._execute(query, (player_id,))

        by_hour = {}
        for row in hour_results:
            by_hour[int(row['hour_of_day'])] = row['games']

        query = f"""
            SELECT 
                day_of_week,
                COUNT(*) as games
            FROM {self.table_name}
            WHERE player_id = ? AND day_of_week IS NOT NULL
            GROUP BY day_of_week
            ORDER BY day_of_week
        """

        weekday_results = self._execute(query, (player_id,))

        by_weekday = {}
        for row in weekday_results:
            by_weekday[int(row['day_of_week'])] = row['games']

        query = f"""
            SELECT 
                COUNT(*) as weekend_games
            FROM {self.table_name}
            WHERE player_id = ? AND is_weekend = 1
        """

        weekend_results = self._execute(query, (player_id,))
        weekend_games = weekend_results[0]['weekend_games'] if weekend_results else 0

        return {
            'by_hour': by_hour,
            'by_weekday': by_weekday,
            'weekend_games': weekend_games
        }

    # ===== МЕТОДЫ ДЛЯ ТАБЛИЦЫ ЛИДЕРОВ =====

    def get_leaderboard(self, criterion: str = 'games_won',
                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить таблицу лидеров по играм.

        Args:
            criterion: Критерий ('games_won', 'total_score', 'fastest_win')
            limit: Количество игроков

        Returns:
            List[Dict]: Список с данными игроков
        """
        # Разные запросы для разных критериев
        if criterion == 'fastest_win':
            query = """
                SELECT 
                    p.id,
                    p.name,
                    MIN(g.duration_seconds) as best_time,
                    COUNT(CASE WHEN g.result = 'won' THEN 1 END) as wins
                FROM players p
                JOIN games g ON p.id = g.player_id
                WHERE g.result = 'won' AND g.duration_seconds > 0
                GROUP BY p.id
                ORDER BY best_time ASC
                LIMIT ?
            """
        elif criterion == 'total_score':
            query = """
                SELECT 
                    p.id,
                    p.name,
                    SUM(g.score) as total_score,
                    COUNT(CASE WHEN g.result = 'won' THEN 1 END) as wins
                FROM players p
                JOIN games g ON p.id = g.player_id
                GROUP BY p.id
                ORDER BY total_score DESC
                LIMIT ?
            """
        else:  # games_won (по умолчанию)
            query = """
                SELECT 
                    p.id,
                    p.name,
                    COUNT(CASE WHEN g.result = 'won' THEN 1 END) as wins,
                    SUM(g.score) as total_score
                FROM players p
                JOIN games g ON p.id = g.player_id
                GROUP BY p.id
                ORDER BY wins DESC
                LIMIT ?
            """

        results = self._execute(query, (limit,))

        leaderboard = []
        for row in results:
            entry = dict(row)
            leaderboard.append(entry)

        return leaderboard

    # ===== МЕТОДЫ ДЛЯ ДОСТИЖЕНИЙ =====

    def get_perfect_games(self, player_id: str) -> List[Game]:
        """
        Получить идеальные игры игрока.

        Args:
            player_id: UUID игрока

        Returns:
            List[Game]: Список идеальных игр
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND was_perfect = 1
            ORDER BY started_at DESC
        """

        results = self._execute(query, (player_id,))
        return [Game.from_dict(row) for row in results]

    def get_suits_completed_stats(self, player_id: str) -> Dict[str, int]:
        """
        Получить статистику по собранным мастям.

        Args:
            player_id: UUID игрока

        Returns:
            Dict: количество собранных мастей по типам
        """
        # Это сложнее, т.к. suits_completed хранится как JSON
        # Для простоты вернём пока заглушку
        return {
            'hearts': 0,
            'diamonds': 0,
            'clubs': 0,
            'spades': 0,
            'all_four': 0
        }

    # ===== МЕТОДЫ ДЛЯ ОЧИСТКИ =====

    def delete_old_games(self, days: int = 365) -> int:
        """
        Удалить старые игры (для экономии места).

        Args:
            days: Удалять игры старше N дней

        Returns:
            int: Количество удалённых игр
        """
        cutoff = datetime.now() - timedelta(days=days)
        query = f"""
            DELETE FROM {self.table_name} 
            WHERE started_at < ?
        """

        try:
            with connection_context() as conn:
                cursor = conn.execute(query, (cutoff.isoformat(),))
                return cursor.rowcount
        except Exception as e:
            print(f"Error deleting old games: {e}")
            return 0

    def has_won_seed(self, player_id: str, seed: int) -> bool:
        """
        Проверить, была ли уже победа с таким сидом у данного игрока.

        Args:
            player_id: UUID игрока
            seed: Сид расклада

        Returns:
            True если победа уже была, False если нет
        """
        if not seed:
            return False

        query = f"""
            SELECT COUNT(*) as count
            FROM {self.table_name}
            WHERE player_id = ? AND seed = ? AND result = 'won'
        """

        results = self._execute(query, (player_id, seed))
        if results and len(results) > 0:
            return results[0]['count'] > 0
        return False