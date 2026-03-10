# stats/services/stats_service.py
"""Сервис для работы со статистикой игр."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import json

from stats.models import Player, Game, SavedGame, PlayerStats
from stats.repositories.player_repository import PlayerRepository
from stats.repositories.game_repository import GameRepository
from stats.repositories.saved_game_repository import SavedGameRepository
from stats.data import get_db_path


class StatsService:
    """
    Сервис для сбора и анализа статистики игр.
    """

    def __init__(self):
        """Инициализация сервиса с репозиториями."""
        db_path = get_db_path()
        self.player_repo = PlayerRepository(db_path)
        self.game_repo = GameRepository(db_path)
        self.saved_game_repo = SavedGameRepository(db_path)

        # Кэш для текущих игр (активные сессии)
        self._active_games: Dict[int, Dict[str, Any]] = {}

    # ===== Управление игровыми сессиями =====

    def start_game(self, player_id: str, game_type: str = "klondike",
                   seed: Optional[int] = None) -> int:
        """
        Начать новую игру.

        Args:
            player_id: UUID игрока
            game_type: Тип пасьянса
            seed: Сид генерации (для переигровки)

        Returns:
            int: ID созданной игры
        """
        # Создаём запись в таблице games
        game = Game(
            player_id=player_id,
            game_type=game_type,
            seed=seed,  # Сохраняем сид сразу
            started_at=datetime.now()
        )

        game_id = self.game_repo.create(game)

        if game_id:
            # Сохраняем в активные игры
            self._active_games[game_id] = {
                'player_id': player_id,
                'game_type': game_type,
                'seed': seed,  # Сохраняем сид в сессии
                'started_at': datetime.now(),
                'moves': 0,
                'undos': 0,
                'hints': 0,
                'deck_cycles': 0
            }

            # Увеличиваем счётчик начатых игр
            self.player_repo.increment_stat(player_id, 'games_started')

        return game_id

    def end_game(self, game_id: int, result: str,
                 score: int = 0, game_state: Optional[Dict] = None,
                 suits_completed: Optional[List[str]] = None) -> bool:
        """
        Завершить игру и записать статистику.
        """
        session_data = None

        if game_id not in self._active_games:
            # Пробуем найти в БД
            game = self.game_repo.get(game_id)
            if not game:
                return False

            # Если игра есть в БД, восстанавливаем данные
            start_time = game.started_at
            player_id = game.player_id
            game_type = game.game_type
            seed = game.seed  # Берем сид из БД

            moves = game.moves_count
            undos = game.undos_used
            hints = game.hints_used
            deck_cycles = game.deck_cycles
        else:
            # Берём данные из активной сессии
            session_data = self._active_games.pop(game_id)

            start_time = session_data['started_at']
            player_id = session_data['player_id']
            game_type = session_data.get('game_type', 'klondike')
            seed = session_data.get('seed')  # Берем сид из сессии

            moves = session_data['moves']
            undos = session_data['undos']
            hints = session_data['hints']
            deck_cycles = session_data['deck_cycles']

        # Рассчитываем длительность
        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())

        # Определяем час и день
        hour = end_time.hour
        weekday = end_time.weekday()
        is_weekend = weekday >= 5

        # Создаём объект игры
        game = Game(
            id=game_id,
            player_id=player_id,
            game_type=game_type,
            seed=seed,  # Сохраняем сид в историю
            started_at=start_time,
            ended_at=end_time,
            result=result,
            score=score,
            duration_seconds=duration,
            moves_count=moves,
            undos_used=undos,
            hints_used=hints,
            deck_cycles=deck_cycles,
            suits_completed=suits_completed or [],
            first_suit=suits_completed[0] if suits_completed else None,
            was_perfect=self._check_perfect_game(game_state),
            hour_of_day=hour,
            day_of_week=weekday,
            is_weekend=is_weekend
        )

        # Обновляем запись в БД
        success = self.game_repo.update(game_id, game.to_dict())

        if success:
            # Обновляем статистику игрока
            self._update_player_stats(player_id, result, score, duration)

        return success

    def _update_player_stats(self, player_id: str, result: str,
                             score: int, duration: int):
        """Обновить статистику игрока после завершения игры."""
        if result == 'won':
            self.player_repo.increment_stat(player_id, 'games_won')
            self.player_repo.update_streak(player_id, won=True)
            self.player_repo.update_fastest_win(player_id, duration)
            self.player_repo.update_slowest_win(player_id, duration)

        elif result == 'lost':
            self.player_repo.increment_stat(player_id, 'games_lost')
            self.player_repo.update_streak(player_id, won=False)

        elif result == 'abandoned':
            self.player_repo.increment_stat(player_id, 'games_abandoned')

        if score > 0:
            self.player_repo.update_score(player_id, score)

        self.player_repo.update_play_time(player_id, duration)

    def update_game_progress(self, game_id: int, **kwargs):
        """Обновить прогресс текущей игры."""
        if game_id in self._active_games:
            for key, value in kwargs.items():
                if key in self._active_games[game_id]:
                    self._active_games[game_id][key] = value

    # ===== Работа с сохранёнными играми =====

    def save_game(self, player_id: str, game_type: str,
                  game_state: Dict[str, Any],
                  seed: Optional[int] = None,
                  save_type: str = 'autosave',
                  description: str = '',
                  score: int = 0,
                  moves_count: int = 0,
                  time_played_seconds: int = 0) -> Optional[int]:
        """
        Сохранить игру.
        """
        # Используем метод репозитория, который поддерживает seed
        return self.saved_game_repo.save_autosave(
            player_id=player_id,
            game_type=game_type,
            game_state=game_state,
            seed=seed,  # Передаем сид
            score=score,
            moves_count=moves_count,
            time_played_seconds=time_played_seconds
        )

    def load_saved_game(self, saved_game_id: int) -> Optional[SavedGame]:
        """Загрузить сохранённую игру."""
        saved = self.saved_game_repo.get(saved_game_id)
        if saved:
            self.saved_game_repo.update_last_played(saved_game_id)
        return saved

    def get_player_saves(self, player_id: str,
                         game_type: Optional[str] = None) -> List[SavedGame]:
        """Получить все сохранения игрока."""
        return self.saved_game_repo.get_by_player(player_id, game_type)

    def delete_saved_game(self, saved_game_id: int) -> bool:
        """Удалить сохранение."""
        return self.saved_game_repo.delete(saved_game_id)

    # ===== Статистика и аналитика =====

    def get_player_stats(self, player_id: str,
                         days: int = 30) -> Optional[PlayerStats]:
        """Получить расширенную статистику игрока."""
        player = self.player_repo.get(player_id)
        if not player:
            return None

        cutoff_date = datetime.now() - timedelta(days=days)
        recent_games = self.game_repo.get_by_player(
            player_id,
            limit=100,
            from_date=cutoff_date
        )

        best_game = None
        worst_game = None
        max_score = -1
        min_score = float('inf')

        for game in recent_games:
            if game.score > max_score:
                max_score = game.score
                best_game = game
            if game.score < min_score and game.score > 0:
                min_score = game.score
                worst_game = game

        return PlayerStats(
            player=player,
            recent_games=recent_games,
            best_game=best_game,
            worst_game=worst_game
        )

    def get_leaderboard(self, criterion: str = 'games_won',
                        limit: int = 10) -> List[Player]:
        """Получить таблицу лидеров."""
        return self.player_repo.get_top_players(limit, criterion)

    def get_game_history(self, player_id: str,
                         limit: int = 50) -> List[Game]:
        """Получить историю игр игрока."""
        return self.game_repo.get_by_player(player_id, limit)

    def get_statistics_summary(self, player_id: str) -> Dict[str, Any]:
        """Получить краткую сводку статистики."""
        player = self.player_repo.get(player_id)
        if not player:
            return {}

        win_rate = player.win_rate
        total_hours = player.total_hours

        recent = self.game_repo.get_by_player(player_id, limit=10)
        recent_wins = sum(1 for g in recent if g.result == 'won')

        return {
            'player_name': player.name,
            'games_played': player.games_started,
            'games_won': player.games_won,
            'win_rate': f"{win_rate:.1f}%",
            'current_streak': player.current_win_streak,
            'best_streak': player.best_win_streak,
            'total_score': player.total_score,
            'highest_score': player.highest_score,
            'total_hours': f"{total_hours:.1f}",
            'recent_form': f"{recent_wins}/{len(recent)}",
            'fastest_win': self._format_time(player.fastest_win_seconds),
            'slowest_win': self._format_time(player.slowest_win_seconds)
        }

    # ===== Достижения =====

    def check_achievements(self, player_id: str, game_result: Game) -> List[str]:
        """Проверить, получены ли новые достижения."""
        achievements = []
        player = self.player_repo.get(player_id)

        if not player:
            return achievements

        if player.games_won == 1 and game_result.result == 'won':
            achievements.append("first_win")

        if player.games_won == 10:
            achievements.append("ten_wins")

        if player.games_won == 100:
            achievements.append("hundred_wins")

        if game_result.was_perfect:
            achievements.append("perfect_game")

        if len(game_result.suits_completed) == 4:
            achievements.append("all_suits")

        if (game_result.result == 'won' and
                game_result.duration_seconds and
                game_result.duration_seconds < 120):
            achievements.append("speed_demon")

        return achievements

    # ===== Вспомогательные методы =====

    def _check_perfect_game(self, game_state: Optional[Dict]) -> bool:
        """Проверить, была ли игра идеальной."""
        if not game_state:
            return False
        return False

    def _format_time(self, seconds: Optional[int]) -> str:
        """Форматировать время для отображения."""
        if not seconds:
            return "—"

        minutes = seconds // 60
        secs = seconds % 60

        if minutes > 0:
            return f"{minutes} мин {secs} сек"
        return f"{secs} сек"

    # ===== Административные методы =====

    def reset_player_stats(self, player_id: str) -> bool:
        """Сбросить статистику игрока."""
        reset_data = {
            'games_started': 0,
            'games_won': 0,
            'games_lost': 0,
            'games_abandoned': 0,
            'current_win_streak': 0,
            'best_win_streak': 0,
            'current_loose_streak': 0,
            'best_loose_streak': 0,
            'total_score': 0,
            'highest_score': 0,
            'total_play_time_seconds': 0,
            'fastest_win_seconds': None,
            'slowest_win_seconds': None
        }

        return self.player_repo.update(player_id, reset_data)

    def cleanup_old_saves(self, days: int = 30) -> int:
        """Очистить старые автосохранения."""
        cutoff = datetime.now() - timedelta(days=days)
        return self.saved_game_repo.delete_old_autosaves(cutoff)