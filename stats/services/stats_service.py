# stats/services/stats_service.py
"""Сервис для работы со статистикой игр."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import json

from stats.models import Player, Game, SavedGame, PlayerStats
from stats.repositories.player_repository import PlayerRepository
from stats.repositories.game_repository import GameRepository
from stats.repositories.saved_game_repository import SavedGameRepository
from stats.repositories.achievement_repository import AchievementRepository, PlayerAchievementRepository
from stats.models import Achievement
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
        self.achievement_repo = AchievementRepository(db_path)
        self.player_achievement_repo = PlayerAchievementRepository(db_path)

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

    def init_achievements_on_startup(self):
        """Создает достижения в БД, если их нет."""
        default_achievements = [
            # --- Прогресс ---
            Achievement(id="first_win", name="Первая кровь", description="Выиграть первую игру", category="progress",
                        condition_type="wins", target=1),
            Achievement(id="ten_wins", name="Новичок", description="Выиграть 10 игр", category="progress",
                        condition_type="wins", target=10),
            Achievement(id="hundred_wins", name="Ветеран", description="Выиграть 100 игр", category="progress",
                        condition_type="wins", target=100),
            Achievement(id="immortal", name="Бессмертный", description="Выиграть 1000 игр", category="progress",
                        condition_type="wins", target=1000),

            # --- Ходы (Карты) ---
            Achievement(id="cards_100", name="Первые шаги", description="Переместить 100 карт", category="cards",
                        condition_type="cards_moved", target=100),
            Achievement(id="cards_1000", name="Тысяча перемещений", description="Переместить 1 000 карт",
                        category="cards", condition_type="cards_moved", target=1000),
            Achievement(id="cards_10000", name="Карточный магнат", description="Переместить 10 000 карт",
                        category="cards", condition_type="cards_moved", target=10000),
            Achievement(id="cards_100000", name="Карточный король", description="Переместить 100 000 карт",
                        category="cards", condition_type="cards_moved", target=100000),
            Achievement(id="cards_million", name="Миллионер", description="Переместить 1 000 000 карт",
                        category="cards", condition_type="cards_moved", target=1000000),

            # --- Масти (Suits) ---

            # ♠️ Пики
            Achievement(id="spades_10", name="Гроза Пик", description="Собрать 10 мастей Пик", category="suits",
                        condition_type="completed_spades", target=10),
            Achievement(id="spades_100", name="Владыка Тьмы", description="Собрать 100 мастей Пик", category="suits",
                        condition_type="completed_spades", target=100),
            Achievement(id="spades_1000", name="Император Пик", description="Собрать 1000 мастей Пик", category="suits",
                        condition_type="completed_spades", target=1000),
            Achievement(id="spades_5000", name="Легенда Пик", description="Собрать 5000 мастей Пик", category="suits",
                        condition_type="completed_spades", target=5000),

            # ♥️ Черви
            Achievement(id="hearts_10", name="Сердцеед", description="Собрать 10 мастей Черви", category="suits",
                        condition_type="completed_hearts", target=10),
            Achievement(id="hearts_100", name="Король Сердец", description="Собрать 100 мастей Черви", category="suits",
                        condition_type="completed_hearts", target=100),
            Achievement(id="hearts_1000", name="Повелитель Любви", description="Собрать 1000 мастей Черви",
                        category="suits", condition_type="completed_hearts", target=1000),
            Achievement(id="hearts_5000", name="Легенда Черви", description="Собрать 5000 мастей Черви",
                        category="suits", condition_type="completed_hearts", target=5000),

            # ♦️ Бубны
            Achievement(id="diamonds_10", name="Искатель Кладов", description="Собрать 10 мастей Бубны",
                        category="suits", condition_type="completed_diamonds", target=10),
            Achievement(id="diamonds_100", name="Золотой Магнат", description="Собрать 100 мастей Бубны",
                        category="suits", condition_type="completed_diamonds", target=100),
            Achievement(id="diamonds_1000", name="Алмазный Барон", description="Собрать 1000 мастей Бубны",
                        category="suits", condition_type="completed_diamonds", target=1000),
            Achievement(id="diamonds_5000", name="Легенда Бубны", description="Собрать 5000 мастей Бубны",
                        category="suits", condition_type="completed_diamonds", target=5000),

            # ♣️ Трефы
            Achievement(id="clubs_10", name="Хранитель Леса", description="Собрать 10 мастей Трефы", category="suits",
                        condition_type="completed_clubs", target=10),
            Achievement(id="clubs_100", name="Повелитель Треф", description="Собрать 100 мастей Трефы",
                        category="suits", condition_type="completed_clubs", target=100),
            Achievement(id="clubs_1000", name="Властелин Жезлов", description="Собрать 1000 мастей Трефы",
                        category="suits", condition_type="completed_clubs", target=1000),
            Achievement(id="clubs_5000", name="Легенда Трефы", description="Собрать 5000 мастей Трефы",
                        category="suits", condition_type="completed_clubs", target=5000),

            # --- Мастерство ---
            Achievement(id="speed_demon", name="Молния", description="Выиграть партию менее чем за 2 минуты",
                        category="skill", condition_type="time_lt", target=120, is_hidden=True),
            Achievement(id="perfect_game", name="Идеально",
                        description="Выиграть без использования подсказок и отмены ходов", category="skill",
                        condition_type="perfect", target=1),
            Achievement(id="streak_5", name="На кураже", description="Выиграть 5 игр подряд", category="streak",
                        condition_type="streak", target=5),
        ]

        for ach in default_achievements:
            if not self.achievement_repo.get(ach.id):
                self.achievement_repo.create(ach)
                # print(f"🏆 Достижение создано: {ach.name}")

    def end_game(self, game_id: int, result: str,
                 score: int = 0, game_state: Optional[Dict] = None,
                 suits_completed: Optional[List[str]] = None,
                 cards_moved: int = 0) -> Dict[str, Any]:
        """
        Завершить игру и записать статистику.

        Returns:
            Dict: {'success': bool, 'is_first_win': bool}
        """
        session_data = None
        is_first_win = False  # Флаг по умолчанию

        # ... (блок извлечения данных из сессии или БД) ...
        if game_id not in self._active_games:
            game = self.game_repo.get(game_id)
            if not game:
                return {'success': False}

            start_time = game.started_at
            player_id = game.player_id
            game_type = game.game_type
            seed = game.seed

            moves = game.moves_count
            undos = game.undos_used
            hints = game.hints_used
            deck_cycles = game.deck_cycles
        else:
            session_data = self._active_games.pop(game_id)

            start_time = session_data['started_at']
            player_id = session_data['player_id']
            game_type = session_data.get('game_type', 'klondike')
            seed = session_data.get('seed')

            moves = session_data['moves']
            undos = session_data['undos']
            hints = session_data['hints']
            deck_cycles = session_data['deck_cycles']

        # === НОВАЯ ЛОГИКА ПРОВЕРКИ СИДА ===
        # Если это победа, проверяем, была ли она ранее
        if result == 'won' and seed:
            already_won = self.game_repo.has_won_seed(player_id, seed)
            if not already_won:
                is_first_win = True
        # ==================================

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
            seed=seed,
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

        # Обновляем запись в БД (ВСЕГДА сохраняем попытку)
        success = self.game_repo.update(game_id, game.to_dict())
        if success:
            # Обновляем статистику игрока с учетом флага первой победы
            self._update_player_stats(player_id, result, score, duration, is_first_win)
            newly_unlocked = self.check_and_update_achievements(player_id, game)
            return {
                'success': True,
                'is_first_win': is_first_win,
                'unlocked_achievements': newly_unlocked  # Возвращаем список новых достижений
            }
        return {'success': False}

    def _update_player_stats(self, player_id: str, result: str,
                             score: int, duration: int, is_first_win: bool = False):
        """Обновить статистику игрока после завершения игры."""
        if result == 'won':
            # Увеличиваем счетчик побед ТОЛЬКО если это первая победа на этом сиде
            if is_first_win:
                self.player_repo.increment_stat(player_id, 'games_won')
                self.player_repo.update_streak(player_id, won=True)

            # Рекорды времени обновляем только для зачетных побед
            if is_first_win:
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

    # Метод проверки достижений:
    def check_and_update_achievements(self, player_id: str, game_result: Game) -> List[Dict]:
        """
        Проверяет условия достижений и обновляет прогресс.
        Возвращает список только что разблокированных достижений.
        """
        all_achievements = self.achievement_repo.get_all()
        player = self.player_repo.get(player_id)
        newly_unlocked = []

        if not player:
            return []

        for ach in all_achievements:
            # Пропускаем уже полученные
            pa = self.player_achievement_repo.get_player_achievement(player_id, ach.id)
            if pa and pa.unlocked:
                continue

            # Логика проверки условий
            current_progress = 0
            condition_met = False

            # 1. Счетчики (победы, серии)
            if ach.condition_type == 'wins':
                current_progress = player.games_won
                condition_met = current_progress >= ach.target

            elif ach.condition_type == 'streak':
                current_progress = player.current_win_streak
                condition_met = current_progress >= ach.target

            # 2. Разовые (время,完美 игра)
            elif ach.condition_type == 'time_lt':
                if game_result.result == 'won' and game_result.duration_seconds:
                    current_progress = game_result.duration_seconds
                    condition_met = game_result.duration_seconds < ach.target
                    # Для времени прогресс не накапливается, либо фиксируем лучший результат
                    if condition_met:
                        current_progress = ach.target  # Чтобы показать "выполнено"

            elif ach.condition_type == 'perfect':
                if game_result.result == 'won' and game_result.was_perfect:
                    condition_met = True
                    current_progress = 1

            # Обновляем прогресс
            unlocked_now = False
            if condition_met and not (pa and pa.unlocked):
                self.player_achievement_repo.update_progress(player_id, ach.id, ach.target, True)
                newly_unlocked.append(ach.to_dict())
                unlocked_now = True
                print(f"🏆 Достижение получено: {ach.name}")
            elif pa and pa.progress < current_progress and not pa.unlocked:
                # Обновляем прогресс для счетчиков, если еще не получено
                self.player_achievement_repo.update_progress(player_id, ach.id, current_progress, False)

        return newly_unlocked

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
            'current_win_streak': int(player.current_win_streak),
            'best_win_streak': int(player.best_win_streak),
            'current_loose_streak': int(player.current_loose_streak),
            'best_loose_streak': int(player.best_loose_streak),
            'total_score': player.total_score,
            'highest_score': player.highest_score,
            'total_hours': f"{total_hours:.1f}",
            'recent_form': f"{recent_wins}/{len(recent)}",
            'fastest_win': self._format_time(player.fastest_win_seconds),
            'slowest_win': self._format_time(player.slowest_win_seconds)
        }

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
