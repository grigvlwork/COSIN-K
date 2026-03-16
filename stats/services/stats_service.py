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
        """
        game = Game(
            player_id=player_id,
            game_type=game_type,
            seed=seed,
            started_at=datetime.now()
        )

        game_id = self.game_repo.create(game)

        if game_id:
            self._active_games[game_id] = {
                'player_id': player_id,
                'game_type': game_type,
                'seed': seed,
                'started_at': datetime.now(),
                'moves': 0,
                'undos': 0,
                'hints': 0,
                'deck_cycles': 0
            }
            self.player_repo.increment_stat(player_id, 'games_started')

        return game_id

    def init_achievements_on_startup(self):
        """Создает достижения в БД, если их нет."""
        default_achievements = [
            # --- Прогресс ---
            Achievement(id="first_win", name="Первая кровь", description="Выиграть первую игру", category="progress", condition_type="wins", target=1),
            Achievement(id="ten_wins", name="Новичок", description="Выиграть 10 игр", category="progress", condition_type="wins", target=10),
            Achievement(id="hundred_wins", name="Ветеран", description="Выиграть 100 игр", category="progress", condition_type="wins", target=100),
            Achievement(id="immortal", name="Бессмертный", description="Выиграть 1000 игр", category="progress", condition_type="wins", target=1000),

            # --- Ходы (Перемещение) ---
            Achievement(id="cards_100", name="Первые шаги", description="Переместить 100 карт", category="cards", condition_type="cards_moved", target=100),
            Achievement(id="cards_1000", name="Тысяча перемещений", description="Переместить 1 000 карт", category="cards", condition_type="cards_moved", target=1000),
            Achievement(id="cards_10000", name="Карточный магнат", description="Переместить 10 000 карт", category="cards", condition_type="cards_moved", target=10000),
            Achievement(id="cards_100000", name="Карточный король", description="Переместить 100 000 карт", category="cards", condition_type="cards_moved", target=100000),
            Achievement(id="cards_million", name="Миллионер", description="Переместить 1 000 000 карт", category="cards", condition_type="cards_moved", target=1000000),

            # --- Исследование (Переворот) ---
            Achievement(id="flipped_100", name="Любопытство", description="Перевернуть 100 карт", category="exploration", condition_type="cards_flipped", target=100),
            Achievement(id="flipped_1000", name="Первые открытия", description="Перевернуть 1 000 карт", category="exploration", condition_type="cards_flipped", target=1000),
            Achievement(id="flipped_10000", name="Картограф", description="Перевернуть 10 000 карт", category="exploration", condition_type="cards_flipped", target=10000),
            Achievement(id="flipped_100000", name="Исследователь", description="Перевернуть 100 000 карт", category="exploration", condition_type="cards_flipped", target=100000),
            Achievement(id="flipped_million", name="Покоритель тайн", description="Перевернуть 1 000 000 карт", category="exploration", condition_type="cards_flipped", target=1000000),

            # --- Масти (Suits) ---
            # ♠️ Пики
            Achievement(id="spades_10", name="Гроза Пик", description="Собрать 10 мастей Пик", category="suits", condition_type="completed_spades", target=10),
            Achievement(id="spades_100", name="Владыка Тьмы", description="Собрать 100 мастей Пик", category="suits", condition_type="completed_spades", target=100),
            Achievement(id="spades_1000", name="Император Пик", description="Собрать 1000 мастей Пик", category="suits", condition_type="completed_spades", target=1000),
            Achievement(id="spades_5000", name="Легенда Пик", description="Собрать 5000 мастей Пик", category="suits", condition_type="completed_spades", target=5000),

            # ♥️ Черви
            Achievement(id="hearts_10", name="Сердцеед", description="Собрать 10 мастей Черви", category="suits", condition_type="completed_hearts", target=10),
            Achievement(id="hearts_100", name="Король Сердец", description="Собрать 100 мастей Черви", category="suits", condition_type="completed_hearts", target=100),
            Achievement(id="hearts_1000", name="Повелитель Любви", description="Собрать 1000 мастей Черви", category="suits", condition_type="completed_hearts", target=1000),
            Achievement(id="hearts_5000", name="Легенда Черви", description="Собрать 5000 мастей Черви", category="suits", condition_type="completed_hearts", target=5000),

            # ♦️ Бубны
            Achievement(id="diamonds_10", name="Искатель Кладов", description="Собрать 10 мастей Бубны", category="suits", condition_type="completed_diamonds", target=10),
            Achievement(id="diamonds_100", name="Золотой Магнат", description="Собрать 100 мастей Бубны", category="suits", condition_type="completed_diamonds", target=100),
            Achievement(id="diamonds_1000", name="Алмазный Барон", description="Собрать 1000 мастей Бубны", category="suits", condition_type="completed_diamonds", target=1000),
            Achievement(id="diamonds_5000", name="Легенда Бубны", description="Собрать 5000 мастей Бубны", category="suits", condition_type="completed_diamonds", target=5000),

            # ♣️ Трефы
            Achievement(id="clubs_10", name="Хранитель Леса", description="Собрать 10 мастей Трефы", category="suits", condition_type="completed_clubs", target=10),
            Achievement(id="clubs_100", name="Повелитель Треф", description="Собрать 100 мастей Трефы", category="suits", condition_type="completed_clubs", target=100),
            Achievement(id="clubs_1000", name="Властелин Жезлов", description="Собрать 1000 мастей Трефы", category="suits", condition_type="completed_clubs", target=1000),
            Achievement(id="clubs_5000", name="Легенда Трефы", description="Собрать 5000 мастей Трефы", category="suits", condition_type="completed_clubs", target=5000),

            # --- Мастерство ---
            # Achievement(id="speed_demon", name="Молния", description="Выиграть партию менее чем за 2 минуты", category="skill", condition_type="time_lt", target=120, is_hidden=True),
            # Achievement(id="perfect_game", name="Идеально", description="Выиграть без подсказок и отмены", category="skill", condition_type="perfect", target=1),
            # Achievement(id="streak_5", name="На кураже", description="Выиграть 5 игр подряд", category="streak", condition_type="streak", target=5),

            # --- Стойкость (Проигрыши) ---
            Achievement(id="loss_1", name="Первый шрам", description="Проиграть первую игру", category="resilience",
                        condition_type="losses", target=1),
            Achievement(id="loss_10", name="Закалённый сталью", description="Проиграть 10 игр", category="resilience",
                        condition_type="losses", target=10),
            Achievement(id="loss_100", name="Ветеран битв", description="Проиграть 100 игр", category="resilience",
                        condition_type="losses", target=100),
            Achievement(id="loss_1000", name="Железная воля", description="Проиграть 1000 игр", category="resilience",
                        condition_type="losses", target=1000),
            Achievement(id="loss_10000", name="Неубиваемый", description="Проиграть 10000 игр", category="resilience",
                        condition_type="losses", target=10000),
            # --- Совершенство (Без подсказок и отмен) ---
            Achievement(id="perfect_1", name="Чистая работа", description="Выиграть партию без подсказок и отмен",
                        category="perfection", condition_type="perfect_wins", target=1),
            Achievement(id="perfect_10", name="Меткость", description="Выиграть 10 идеальных партий",
                        category="perfection", condition_type="perfect_wins", target=10),
            Achievement(id="perfect_100", name="Снайпер", description="Выиграть 100 идеальных партий",
                        category="perfection", condition_type="perfect_wins", target=100),
            Achievement(id="perfect_1000", name="Виртуоз", description="Выиграть 1000 идеальных партий",
                        category="perfection", condition_type="perfect_wins", target=1000),
            Achievement(id="perfect_5000", name="Абсолют", description="Выиграть 5000 идеальных партий",
                        category="perfection", condition_type="perfect_wins", target=5000),
            # --- Скорость ---
            Achievement(id="speed_3min", name="Быстрый как ветер", description="Выиграть партию менее чем за 3 минуты",
                        category="speed", condition_type="time_lt", target=180),
            Achievement(id="speed_2_5min", name="Спринтер", description="Выиграть партию менее чем за 2.5 минуты",
                        category="speed", condition_type="time_lt", target=150),
            Achievement(id="speed_demon", name="Молния", description="Выиграть партию менее чем за 2 минуты",
                        category="speed", condition_type="time_lt", target=120, is_hidden=True),
            Achievement(id="speed_90sec", name="Реактивный", description="Выиграть партию менее чем за 90 секунд",
                        category="speed", condition_type="time_lt", target=90, is_hidden=True),
            Achievement(id="speed_1min", name="Вне времени", description="Выиграть партию менее чем за 1 минуту",
                        category="speed", condition_type="time_lt", target=60, is_hidden=True),

            # --- Серии побед (Streak) ---
            Achievement(id="streak_5", name="На кураже", description="Выиграть 5 игр подряд", category="streak",
                        condition_type="streak", target=5),
            Achievement(id="streak_10", name="Непобедимый", description="Выиграть 10 игр подряд", category="streak",
                        condition_type="streak", target=10),
            Achievement(id="streak_50", name="Мастер серии", description="Выиграть 50 игр подряд", category="streak",
                        condition_type="streak", target=50, is_hidden=True),
            Achievement(id="streak_100", name="Легенда арены", description="Выиграть 100 игр подряд", category="streak",
                        condition_type="streak", target=100, is_hidden=True),
            Achievement(id="streak_500", name="Бог Войны", description="Выиграть 500 игр подряд", category="streak",
                        condition_type="streak", target=500, is_hidden=True),
        ]

        for ach in default_achievements:
            if not self.achievement_repo.get(ach.id):
                self.achievement_repo.create(ach)


    def end_game(self, game_id: int, result: str,
                 score: int = 0, game_state: Optional[Dict] = None,
                 suits_completed: Optional[List[str]] = None,
                 cards_moved: int = 0,
                 cards_flipped: int = 0,
                 was_perfect: bool = False) -> Dict[str, Any]:  # <--- Добавили аргумент
        """
        Завершить игру и записать статистику.

        Returns:
            Dict: {'success': bool, 'is_first_win': bool}
        """
        session_data = None
        is_first_win = False

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

        if result == 'won' and seed:
            already_won = self.game_repo.has_won_seed(player_id, seed)
            if not already_won:
                is_first_win = True

        end_time = datetime.now()
        duration = int((end_time - start_time).total_seconds())

        hour = end_time.hour
        weekday = end_time.weekday()
        is_weekend = weekday >= 5

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
            was_perfect=was_perfect,
            hour_of_day=hour,
            day_of_week=weekday,
            is_weekend=is_weekend
        )

        success = self.game_repo.update(game_id, game.to_dict())
        if success:
            # Передаем новые параметры в обновление статистики
            self._update_player_stats(
                player_id, result, score, duration, is_first_win,
                cards_moved=cards_moved,
                cards_flipped=cards_flipped,
                suits_completed=suits_completed,
                was_perfect=was_perfect
            )
            newly_unlocked = self.check_and_update_achievements(player_id, game)
            return {
                'success': True,
                'is_first_win': is_first_win,
                'unlocked_achievements': newly_unlocked
            }
        return {'success': False}

    def _update_player_stats(self, player_id: str, result: str,
                             score: int, duration: int, is_first_win: bool = False,
                             cards_moved: int = 0,
                             cards_flipped: int = 0,
                             suits_completed: Optional[List[str]] = None,
                             was_perfect: bool = False):
        """Обновить статистику игрока после завершения игры."""

        # 1. Результаты игры
        if result == 'won':
            if is_first_win:
                self.player_repo.increment_stat(player_id, 'games_won')
                self.player_repo.update_streak(player_id, won=True)
                self.player_repo.update_fastest_win(player_id, duration)
                self.player_repo.update_slowest_win(player_id, duration)
                if was_perfect:
                    self.player_repo.increment_stat(player_id, 'total_perfect_wins', 1)

        elif result == 'lost':
            self.player_repo.increment_stat(player_id, 'games_lost')
            self.player_repo.update_streak(player_id, won=False)

        elif result == 'abandoned':
            self.player_repo.increment_stat(player_id, 'games_abandoned')
            self.player_repo.update_streak(player_id, won=False)

        # 2. Очки и время
        if score > 0:
            self.player_repo.update_score(player_id, score)
        self.player_repo.update_play_time(player_id, duration)

        # 3. Карты (НОВОЕ)
        if cards_moved > 0:
            self.player_repo.increment_stat(player_id, 'total_cards_moved', cards_moved)
        if cards_flipped > 0:
            self.player_repo.increment_stat(player_id, 'total_cards_flipped', cards_flipped)

        # 4. Масти (НОВОЕ)
        if result == 'won' and suits_completed:
            # Маппинг названий мастей в поля БД
            suit_map = {
                'SPADES': 'completed_spades',
                'HEARTS': 'completed_hearts',
                'DIAMONDS': 'completed_diamonds',
                'CLUBS': 'completed_clubs'
            }
            for suit in suits_completed:
                col_name = suit_map.get(suit.upper())
                if col_name:
                    self.player_repo.increment_stat(player_id, col_name, 1)

    def update_game_progress(self, game_id: int, **kwargs):
        """Обновить прогресс текущей игры."""
        if game_id in self._active_games:
            for key, value in kwargs.items():
                if key in self._active_games[game_id]:
                    self._active_games[game_id][key] = value

    def check_and_update_achievements(self, player_id: str, game_result: Game) -> List[Dict]:
        """
        Проверяет условия достижений и обновляет прогресс.
        """
        all_achievements = self.achievement_repo.get_all()
        player = self.player_repo.get(player_id)
        newly_unlocked = []

        if not player:
            return []

        for ach in all_achievements:
            pa = self.player_achievement_repo.get_player_achievement(player_id, ach.id)
            if pa and pa.unlocked:
                continue

            current_progress = 0
            condition_met = False

            # --- Логика проверки ---

            # Счетчики (победы)
            if ach.condition_type == 'wins':
                current_progress = player.games_won
                condition_met = current_progress >= ach.target

            # Серии
            elif ach.condition_type == 'streak':
                current_progress = player.current_win_streak
                condition_met = current_progress >= ach.target

            # Перемещенные карты
            elif ach.condition_type == 'cards_moved':
                current_progress = player.total_cards_moved
                condition_met = current_progress >= ach.target

            # Перевернутые карты
            elif ach.condition_type == 'cards_flipped':
                current_progress = player.total_cards_flipped
                condition_met = current_progress >= ach.target

            # Масти (универсальная проверка для всех 4-х видов)
            elif ach.condition_type.startswith('completed_'):
                if hasattr(player, ach.condition_type):
                    current_progress = getattr(player, ach.condition_type)
                    condition_met = current_progress >= ach.target

            # Время (меньше чем)
            elif ach.condition_type == 'time_lt':
                if game_result.result == 'won' and game_result.duration_seconds:
                    current_progress = game_result.duration_seconds
                    # Условие: время игры МЕНЬШЕ целевого
                    condition_met = game_result.duration_seconds < ach.target
                    if condition_met:
                        # Для прогресс-бара заполняем полностью
                        current_progress = ach.target

            #             # Идеальная игра
            # elif ach.condition_type == 'perfect':
            #     if game_result.result == 'won' and game_result.was_perfect:
            #         condition_met = True
            #         current_progress = 1

            elif ach.condition_type == 'losses':
                current_progress = player.games_lost
                condition_met = current_progress >= ach.target

            elif ach.condition_type == 'perfect_wins':
                current_progress = player.total_perfect_wins
                condition_met = current_progress >= ach.target

            # --- Обновление статуса ---
            if condition_met and not (pa and pa.unlocked):
                self.player_achievement_repo.update_progress(player_id, ach.id, ach.target, True)
                newly_unlocked.append(ach.to_dict())
                print(f"🏆 Достижение получено: {ach.name}")
            elif pa and pa.progress < current_progress and not pa.unlocked:
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
        """Сохранить игру."""
        return self.saved_game_repo.save_autosave(
            player_id=player_id,
            game_type=game_type,
            game_state=game_state,
            seed=seed,
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

    def get_player_stats(self, player_id: str, days: int = 30) -> Optional[PlayerStats]:
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

    def get_leaderboard(self, criterion: str = 'games_won', limit: int = 10) -> List[Player]:
        """Получить таблицу лидеров."""
        return self.player_repo.get_top_players(limit, criterion)

    def get_game_history(self, player_id: str, limit: int = 50) -> List[Game]:
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
            'games_started': 0, 'games_won': 0, 'games_lost': 0, 'games_abandoned': 0,
            'current_win_streak': 0, 'best_win_streak': 0,
            'current_loose_streak': 0, 'best_loose_streak': 0,
            'total_score': 0, 'highest_score': 0,
            'total_play_time_seconds': 0,
            'fastest_win_seconds': None, 'slowest_win_seconds': None,
            'total_cards_moved': 0, 'total_cards_flipped': 0,
            'completed_spades': 0, 'completed_hearts': 0,
            'completed_diamonds': 0, 'completed_clubs': 0
        }
        return self.player_repo.update(player_id, reset_data)

    def cleanup_old_saves(self, days: int = 30) -> int:
        """Очистить старые автосохранения."""
        cutoff = datetime.now() - timedelta(days=days)
        return self.saved_game_repo.delete_old_autosaves(cutoff)