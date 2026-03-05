# stats/api/stats_api.py
"""
API для взаимодействия Godot клиента с модулем статистики.

Этот модуль объединяет сервисы PlayerIdentity и StatsService
в единый удобный интерфейс для HTTP обработчиков.

Пример использования в godot_bridge.py:
    >>> stats_api = StatsAPI(storage_path="./client_data")
    >>>
    >>> # При подключении клиента
    >>> player = stats_api.connect(player_id)
    >>>
    >>> # При создании игры
    >>> game_id = stats_api.start_game(player_id, "klondike")
    >>>
    >>> # При завершении игры
    >>> stats_api.end_game(game_id, "won", score=150, moves=45)
"""

import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from stats.services.player_identity import PlayerIdentity
from stats.services.stats_service import StatsService
from stats.models import Player, Game, SavedGame, PlayerStats


class StatsAPI:
    """
    Единый API для всех операций со статистикой.

    Этот класс скрывает сложность взаимодействия между репозиториями
    и сервисами, предоставляя простые методы для HTTP обработчиков.

    Атрибуты:
        identity: Сервис идентификации игроков
        stats: Сервис статистики игр
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Инициализация API.

        Args:
            storage_path: Путь для хранения identity файлов на клиенте.
                         Если None - работаем в серверном режиме.
        """
        self.identity = PlayerIdentity(storage_path)
        self.stats = StatsService()

        # Кэш активных игр для быстрого доступа
        self._active_games: Dict[int, Dict[str, Any]] = {}

    # ===== ИДЕНТИФИКАЦИЯ =====
    # Методы для работы с identity игроков

    def init_client(self) -> Dict[str, Any]:
        """
        Инициализация на клиенте при первом запуске.

        Создаёт или загружает UUID игрока из файла.
        Вызывается Godot клиентом при старте.

        Returns:
            Dict с полями:
                - player_id: str - UUID игрока
                - is_new: bool - создан ли новый игрок
                - player_name: str - имя по умолчанию

        Пример:
            >>> api = StatsAPI("./client_data")
            >>> result = api.init_client()
            >>> print(f"Ваш ID: {result['player_id']}")
        """
        player_id = self.identity.get_or_create_client_identity()
        player = self.identity.get_current_player()

        return {
            'success': True,
            'player_id': player_id,
            'player_name': player.name if player else f"Player_{player_id[:8]}",
            'is_new': player is None  # Если нет в памяти - значит только создан
        }

    def connect(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Подключение клиента к серверу.

        Проверяет существование игрока с указанным UUID
        и обновляет время последнего входа.

        Args:
            player_id: UUID игрока от клиента

        Returns:
            Dict с данными игрока или None если не найден

        Пример:
            >>> player = api.connect("123e4567-e89b-12d3-a456-426614174000")
            >>> if player:
            ...     print(f"Добро пожаловать, {player['name']}!")
        """
        player = self.identity.authenticate(player_id)
        if player:
            return {
                'success': True,
                'player_id': player.id,
                'player_name': player.name,
                'games_played': player.games_started,
                'games_won': player.games_won,
                'total_score': player.total_score
            }
        return {
            'success': False,
            'error': 'Player not found'
        }

    def get_or_create_player(self, player_id: str) -> Dict[str, Any]:
        """
        Получить или создать игрока с указанным UUID.

        Используется когда клиент присылает UUID, но сервер его не знает.
        Создаёт нового игрока с этим UUID.

        Args:
            player_id: UUID от клиента

        Returns:
            Dict с данными игрока

        Пример:
            >>> # Клиент прислал новый UUID
            >>> player = api.get_or_create_player("new-uuid-123")
        """
        player = self.identity.get_or_create_server_player(player_id)
        return {
            'success': True,
            'player_id': player.id,
            'player_name': player.name,
            'is_new': True,
            'games_played': 0,
            'games_won': 0
        }

    def rename_player(self, player_id: str, new_name: str) -> Dict[str, Any]:
        """
        Сменить имя игрока.

        Args:
            player_id: UUID игрока
            new_name: Новое имя

        Returns:
            Dict с результатом операции

        Пример:
            >>> result = api.rename_player(player_id, "Алексей")
            >>> if result['success']:
            ...     print("Имя изменено")
        """
        success = self.identity.rename_player(player_id, new_name)
        if success:
            player = self.identity.get_player(player_id)
            return {
                'success': True,
                'player_id': player_id,
                'player_name': player.name if player else new_name,
                'message': 'Имя успешно изменено'
            }
        return {
            'success': False,
            'error': 'Не удалось изменить имя'
        }

    def get_player_info(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить информацию об игроке.

        Args:
            player_id: UUID игрока

        Returns:
            Dict с данными игрока или None
        """
        player = self.identity.get_player(player_id)
        if not player:
            return None

        return {
            'player_id': player.id,
            'player_name': player.name,
            'created_at': player.created_at.isoformat() if player.created_at else None,
            'last_played': player.last_played.isoformat() if player.last_played else None,
            'games_started': player.games_started,
            'games_won': player.games_won,
            'games_lost': player.games_lost,
            'games_abandoned': player.games_abandoned,
            'total_score': player.total_score,
            'highest_score': player.highest_score,
            'current_win_streak': player.current_win_streak,
            'best_win_streak': player.best_win_streak
        }

    # ===== УПРАВЛЕНИЕ ИГРАМИ =====
    # Методы для работы с игровыми сессиями

    def start_game(self, player_id: str, game_type: str = "klondike",
                   variant: str = "standard") -> Dict[str, Any]:
        """
        Начать новую игру.

        Создаёт запись в таблице games и возвращает ID игры.

        Args:
            player_id: UUID игрока
            game_type: Тип игры ('klondike', 'spider' и т.д.)
            variant: Вариант игры (для Клондайка: 'standard' или 'draw-three')

        Returns:
            Dict с ID игры и начальными данными

        Пример:
            >>> result = api.start_game(player_id, "klondike", "draw-three")
            >>> game_id = result['game_id']
        """
        # Определяем точный тип для статистики
        if game_type == "klondike" and variant == "draw-three":
            stats_game_type = "klondike_3"
        else:
            stats_game_type = game_type

        game_id = self.stats.start_game(player_id, stats_game_type)

        if game_id:
            # Сохраняем в кэш
            self._active_games[game_id] = {
                'player_id': player_id,
                'game_type': stats_game_type,
                'started_at': datetime.now(),
                'moves': 0,
                'undos': 0,
                'hints': 0,
                'deck_cycles': 0,
                'initial_state': None
            }

            return {
                'success': True,
                'game_id': game_id,
                'game_type': game_type,
                'variant': variant,
                'message': f'Игра {game_type} начата'
            }

        return {
            'success': False,
            'error': 'Не удалось создать игру'
        }

    def end_game(self, game_id: int, result: str, score: int = 0,
                 moves: int = 0, game_type: str = "klondike",
                 suits_completed: Optional[List[str]] = None,
                 was_perfect: bool = False) -> Dict[str, Any]:
        """
        Завершить игру и записать статистику.

        Args:
            game_id: ID игры
            result: Результат ('won', 'lost', 'abandoned')
            score: Набранные очки
            moves: Количество ходов
            game_type: Тип игры
            suits_completed: Какие масти собраны
            was_perfect: Была ли игра идеальной

        Returns:
            Dict с результатом записи статистики

        Пример:
            >>> result = api.end_game(
            ...     game_id=123,
            ...     result="won",
            ...     score=150,
            ...     moves=45,
            ...     suits_completed=["hearts", "spades"]
            ... )
        """
        # Получаем данные из кэша если есть
        session = self._active_games.pop(game_id, {})

        # Объединяем с переданными данными
        total_moves = moves or session.get('moves', 0)
        undos = session.get('undos', 0)
        hints = session.get('hints', 0)
        deck_cycles = session.get('deck_cycles', 0)

        # Определяем первую собранную масть
        first_suit = suits_completed[0] if suits_completed else None

        # Завершаем игру через сервис статистики
        success = self.stats.end_game(
            game_id=game_id,
            result=result,
            score=score,
            moves_count=total_moves,
            undos_used=undos,
            hints_used=hints,
            deck_cycles=deck_cycles,
            suits_completed=suits_completed,
            was_perfect=was_perfect
        )

        if success:
            # Получаем обновлённую статистику игрока
            player_id = session.get('player_id')
            if player_id:
                stats = self.stats.get_player_stats(player_id)
                if stats:
                    return {
                        'success': True,
                        'game_completed': True,
                        'result': result,
                        'score': score,
                        'moves': total_moves,
                        'suits_completed': suits_completed or [],
                        'first_suit': first_suit,
                        'was_perfect': was_perfect,
                        'player_stats': {
                            'games_won': stats.player.games_won,
                            'games_played': stats.player.games_started,
                            'total_score': stats.player.total_score,
                            'current_streak': stats.player.current_win_streak,
                            'best_streak': stats.player.best_win_streak
                        }
                    }

            return {
                'success': True,
                'game_completed': True,
                'result': result,
                'score': score
            }

        return {
            'success': False,
            'error': 'Не удалось завершить игру'
        }

    def update_game_progress(self, game_id: int, **kwargs) -> bool:
        """
        Обновить прогресс текущей игры.

        Args:
            game_id: ID игры
            **kwargs: Поля для обновления (moves, undos, hints, deck_cycles)

        Returns:
            bool: True если обновлено успешно
        """
        if game_id in self._active_games:
            for key, value in kwargs.items():
                if key in self._active_games[game_id]:
                    self._active_games[game_id][key] = value
            return True
        return False

    # ===== СОХРАНЕНИЯ =====
    # Методы для работы с сохранёнными играми

    def save_game(self, player_id: str, game_type: str,
                  game_state: Dict[str, Any],
                  save_type: str = 'autosave',
                  description: str = '') -> Dict[str, Any]:
        """
        Сохранить игру.

        Args:
            player_id: UUID игрока
            game_type: Тип игры
            game_state: Состояние игры
            save_type: Тип сохранения
            description: Описание

        Returns:
            Dict с ID сохранения
        """
        saved_id = self.stats.save_game(
            player_id=player_id,
            game_type=game_type,
            game_state=game_state,
            save_type=save_type,
            description=description
        )

        if saved_id:
            return {
                'success': True,
                'saved_game_id': saved_id,
                'message': 'Игра сохранена'
            }

        return {
            'success': False,
            'error': 'Не удалось сохранить игру'
        }

    def load_saved_game(self, saved_game_id: int) -> Optional[Dict[str, Any]]:
        """
        Загрузить сохранённую игру.

        Args:
            saved_game_id: ID сохранения

        Returns:
            Dict с состоянием игры или None
        """
        saved = self.stats.load_saved_game(saved_game_id)
        if saved:
            return {
                'success': True,
                'game_id': saved.id,
                'game_type': saved.game_type,
                'game_state': saved.game_state,
                'moves': saved.moves_count,
                'time': saved.time_played_seconds,
                'score': saved.score,
                'save_type': saved.save_type,
                'saved_at': saved.updated_at.isoformat() if saved.updated_at else None
            }

        return {
            'success': False,
            'error': 'Сохранение не найдено'
        }

    def get_player_saves(self, player_id: str,
                         game_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить список сохранений игрока.

        Args:
            player_id: UUID игрока
            game_type: Фильтр по типу игры

        Returns:
            List[Dict]: Список сохранений
        """
        saves = self.stats.get_player_saves(player_id, game_type)

        return [{
            'id': s.id,
            'game_type': s.game_type,
            'save_type': s.save_type,
            'moves': s.moves_count,
            'time': s.time_played_seconds,
            'score': s.score,
            'description': s.description,
            'is_favorite': s.is_favorite,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None
        } for s in saves]

    # ===== СТАТИСТИКА =====
    # Методы для получения статистики и аналитики

    def get_player_stats_summary(self, player_id: str) -> Dict[str, Any]:
        """
        Получить краткую сводку статистики игрока.

        Args:
            player_id: UUID игрока

        Returns:
            Dict со сводкой статистики

        Пример:
            >>> stats = api.get_player_stats_summary(player_id)
            >>> print(f"Побед: {stats['games_won']}")
            >>> print(f"Серия: {stats['current_streak']}")
        """
        summary = self.stats.get_statistics_summary(player_id)
        return {
            'success': True,
            **summary
        }

    def get_detailed_stats(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить детальную статистику игрока.

        Args:
            player_id: UUID игрока

        Returns:
            Dict с расширенной статистикой
        """
        stats = self.stats.get_player_stats(player_id)
        if not stats:
            return None

        # Получаем последние игры
        recent_games = []
        for game in stats.recent_games[:10]:  # Последние 10 игр
            recent_games.append({
                'id': game.id,
                'result': game.result,
                'score': game.score,
                'moves': game.moves_count,
                'date': game.ended_at.isoformat() if game.ended_at else None,
                'game_type': game.game_type
            })

        return {
            'success': True,
            'player': {
                'id': stats.player.id,
                'name': stats.player.name,
                'created': stats.player.created_at.isoformat() if stats.player.created_at else None
            },
            'overall': {
                'games_played': stats.player.games_started,
                'games_won': stats.player.games_won,
                'games_lost': stats.player.games_lost,
                'win_rate': stats.player.win_rate,
                'total_score': stats.player.total_score,
                'highest_score': stats.player.highest_score,
                'total_hours': stats.player.total_hours
            },
            'streaks': {
                'current_win': stats.player.current_win_streak,
                'best_win': stats.player.best_win_streak,
                'current_loose': stats.player.current_loose_streak,
                'best_loose': stats.player.best_loose_streak
            },
            'time': {
                'total_seconds': stats.player.total_play_time_seconds,
                'fastest_win': stats.player.fastest_win_seconds,
                'slowest_win': stats.player.slowest_win_seconds,
                'avg_game': stats.player.avg_game_time
            },
            'recent_games': recent_games,
            'streak_status': stats.win_streak_status,
            'favorite_suit': stats.favorite_suit
        }

    def get_leaderboard(self, criterion: str = 'games_won',
                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить таблицу лидеров.

        Args:
            criterion: Критерий сортировки
            limit: Количество игроков

        Returns:
            List[Dict]: Список лучших игроков
        """
        players = self.stats.get_leaderboard(criterion, limit)

        return [{
            'player_id': p.id,
            'player_name': p.name,
            'games_won': p.games_won,
            'games_played': p.games_started,
            'win_rate': p.win_rate,
            'total_score': p.total_score,
            'highest_score': p.highest_score,
            'current_streak': p.current_win_streak
        } for p in players]

    def get_game_history(self, player_id: str,
                         limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получить историю игр игрока.

        Args:
            player_id: UUID игрока
            limit: Максимальное количество игр

        Returns:
            List[Dict]: Список игр
        """
        games = self.stats.get_game_history(player_id, limit)

        return [{
            'id': g.id,
            'game_type': g.game_type,
            'result': g.result,
            'score': g.score,
            'moves': g.moves_count,
            'duration': g.duration_seconds,
            'date': g.ended_at.isoformat() if g.ended_at else None,
            'was_perfect': g.was_perfect,
            'suits_completed': g.suits_completed
        } for g in games]

    # ===== ДОСТИЖЕНИЯ =====
    # Методы для проверки достижений (заготовка)

    def check_achievements(self, player_id: str, game_result: Dict[str, Any]) -> List[str]:
        """
        Проверить полученные достижения после игры.

        Args:
            player_id: UUID игрока
            game_result: Данные завершённой игры

        Returns:
            List[str]: Список полученных достижений
        """
        # Создаём объект Game из данных
        from stats.models import Game
        game = Game(
            result=game_result.get('result'),
            score=game_result.get('score', 0),
            moves_count=game_result.get('moves', 0),
            was_perfect=game_result.get('was_perfect', False),
            suits_completed=game_result.get('suits_completed', [])
        )

        return self.stats.check_achievements(player_id, game)

    # ===== АДМИНИСТРИРОВАНИЕ =====
    # Методы для управления данными

    def reset_player_stats(self, player_id: str) -> Dict[str, Any]:
        """
        Сбросить статистику игрока.

        Args:
            player_id: UUID игрока

        Returns:
            Dict с результатом операции
        """
        success = self.stats.reset_player_stats(player_id)
        return {
            'success': success,
            'message': 'Статистика сброшена' if success else 'Ошибка сброса'
        }

    def cleanup_old_saves(self, days: int = 30) -> Dict[str, Any]:
        """
        Очистить старые автосохранения.

        Args:
            days: Удалять старше N дней

        Returns:
            Dict с количеством удалённых сохранений
        """
        count = self.stats.cleanup_old_saves(days)
        return {
            'success': True,
            'deleted_count': count,
            'message': f'Удалено {count} старых сохранений'
        }

    def delete_autosave(self, player_id: str, game_type: str) -> Dict[str, Any]:
        """
        Удалить автосохранение игрока для конкретного типа игры.

        Используется при:
        1. Победе (сохранение больше не нужно)
        2. Принудительном начале новой игры (игрок сдался)

        Args:
            player_id: UUID игрока
            game_type: Тип игры ('klondike', 'spider', и т.д.)

        Returns:
            Dict: {'success': True/False}
        """
        # Ищем существующее автосохранение через сервис
        saves = self.stats.get_player_saves(player_id, game_type)
        autosave = next((s for s in saves if s.save_type == 'autosave'), None)

        if autosave:
            success = self.stats.delete_saved_game(autosave.id)
            if success:
                print(f"🗑️ Автосохранение удалено: {player_id} / {game_type}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Failed to delete save'}

        # Если сохранения нет — это тоже успех (идемпотентность)
        return {'success': True}

    # ===== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====

    def get_available_games(self) -> List[str]:
        """
        Получить список доступных типов игр.

        Returns:
            List[str]: Список типов игр
        """
        # Можно импортировать из GameFactory
        return ['klondike', 'klondike_3', 'spider']

    def validate_player_id(self, player_id: str) -> bool:
        """
        Проверить корректность UUID.

        Args:
            player_id: UUID для проверки

        Returns:
            bool: True если UUID валидный
        """
        return self.identity._validate_uuid(player_id)

    def format_game_time(self, seconds: int) -> str:
        """
        Форматировать время игры для отображения.

        Args:
            seconds: Время в секундах

        Returns:
            str: Отформатированное время
        """
        minutes = seconds // 60
        secs = seconds % 60

        if minutes > 0:
            return f"{minutes}:{secs:02d}"
        return f"0:{secs:02d}"