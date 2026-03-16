# stats/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class Player:
    """Модель игрока (соответствует таблице players)"""

    # Основные поля
    id: str
    name: str
    created_at: datetime
    last_played: Optional[datetime] = None

    # Базовая статистика
    games_started: int = 0
    games_won: int = 0
    games_lost: int = 0
    games_abandoned: int = 0

    # Серии
    current_win_streak: int = 0
    best_win_streak: int = 0
    current_loose_streak: int = 0
    best_loose_streak: int = 0

    # Очки
    total_score: int = 0
    highest_score: int = 0

    # Счетчики карт
    total_cards_moved: int = 0
    total_cards_flipped: int = 0

    # Счетчик совершенных игр
    total_perfect_wins: int = 0

    # Собранные масти
    completed_spades: int = 0
    completed_hearts: int = 0
    completed_diamonds: int = 0
    completed_clubs: int = 0

    # Время
    total_play_time_seconds: int = 0
    fastest_win_seconds: Optional[int] = None
    slowest_win_seconds: Optional[int] = None

    # Служебные
    version: int = 1

    @property
    def win_rate(self) -> float:
        """Процент побед"""
        if self.games_started == 0:
            return 0.0
        return round((self.games_won / self.games_started) * 100, 2)

    @property
    def total_hours(self) -> float:
        """Общее время в часах"""
        return round(self.total_play_time_seconds / 3600, 2)

    @property
    def avg_game_time(self) -> Optional[float]:
        """Среднее время игры (в секундах)"""
        completed = self.games_won + self.games_lost
        if completed == 0:
            return None
        return self.total_play_time_seconds / completed

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для БД"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Player':
        """Создание игрока из словаря (из БД)"""
        # Преобразуем строки в datetime
        if 'created_at' in data and isinstance(data['created_at'], str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'last_played' in data and isinstance(data['last_played'], str):
            data['last_played'] = datetime.fromisoformat(data['last_played']) if data['last_played'] else None

        return cls(**data)


@dataclass
class Game:
    """Модель завершённой игры (таблица games)"""

    id: Optional[int] = None
    player_id: str = ''
    game_type: str = 'klondike'

    # Сид для переигровки
    seed: Optional[int] = None

    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    result: Optional[str] = None  # 'won', 'lost', 'abandoned'

    score: int = 0
    duration_seconds: Optional[int] = None
    moves_count: int = 0
    undos_used: int = 0
    hints_used: int = 0
    deck_cycles: int = 0

    suits_completed: List[str] = field(default_factory=list)
    first_suit: Optional[str] = None
    was_perfect: bool = False

    hour_of_day: Optional[int] = None
    day_of_week: Optional[int] = None
    is_weekend: bool = False

    def __post_init__(self):
        """Автоматически заполняем временные поля если нужно"""
        if self.started_at and self.ended_at and not self.duration_seconds:
            delta = self.ended_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())

    @property
    def is_win(self) -> bool:
        """Победа?"""
        return self.result == 'won'

    @property
    def is_loss(self) -> bool:
        """Поражение?"""
        return self.result == 'lost'

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для БД"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            elif key == 'suits_completed':
                result[key] = json.dumps(value) if value else None
            elif isinstance(value, (list, dict)):
                result[key] = json.dumps(value) if value else None
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Game':
        """Создание игры из словаря (из БД)"""
        # Преобразуем строки в datetime
        for field in ['started_at', 'ended_at']:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field]) if data[field] else None

        # Преобразуем JSON строки в списки
        if 'suits_completed' in data and isinstance(data['suits_completed'], str):
            data['suits_completed'] = json.loads(data['suits_completed']) if data['suits_completed'] else []

        return cls(**data)


@dataclass
class SavedGame:
    """Модель сохранённой игры (таблица saved_games)"""

    id: Optional[int] = None
    player_id: str = ''
    game_type: str = 'klondike'

    # Сид для переигровки
    seed: Optional[int] = None

    game_state: Dict[str, Any] = field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_played: Optional[datetime] = None

    save_type: str = 'autosave'  # 'autosave', 'manual', 'checkpoint'

    preview_data: Optional[Dict[str, Any]] = None
    moves_count: int = 0
    time_played_seconds: int = 0
    score: int = 0

    is_favorite: bool = False
    description: str = ''

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для БД"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat() if value else None
            elif isinstance(value, dict):
                result[key] = json.dumps(value) if value else None
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SavedGame':
        """Создание сохранения из словаря (из БД)"""
        # Преобразуем строки в datetime
        for field in ['created_at', 'updated_at', 'last_played']:
            if field in data and isinstance(data[field], str):
                data[field] = datetime.fromisoformat(data[field]) if data[field] else None

        # Преобразуем JSON строки в dict
        for field in ['game_state', 'preview_data']:
            if field in data and isinstance(data[field], str):
                data[field] = json.loads(data[field]) if data[field] else {}

        return cls(**data)


@dataclass
class PlayerStats:
    """Агрегированная статистика игрока (для отображения)"""

    player: Player
    recent_games: List[Game] = field(default_factory=list)
    best_game: Optional[Game] = None
    worst_game: Optional[Game] = None

    @property
    def games_today(self) -> int:
        """Игр сегодня"""
        today = datetime.now().date()
        return sum(1 for g in self.recent_games
                   if g.started_at and g.started_at.date() == today)

    @property
    def win_streak_status(self) -> str:
        """Текущая серия в человекочитаемом виде"""
        if self.player.current_win_streak > 0:
            return f"🔥 {self.player.current_win_streak} побед подряд"
        elif self.player.current_loose_streak > 0:
            return f"💔 {self.player.current_loose_streak} поражений подряд"
        else:
            return "⚖️ Ничья"

    @property
    def favorite_suit(self) -> Optional[str]:
        """Любимая масть"""
        suits = []
        for game in self.recent_games:
            if game.suits_completed:
                suits.extend(game.suits_completed)
        if not suits:
            return None
        from collections import Counter
        return Counter(suits).most_common(1)[0][0]


@dataclass
class Achievement:
    """Модель достижения (шаблон)."""
    id: str
    name: str
    description: str
    icon: str = ""  # По умолчанию пустая строка (или None)
    category: str = "general"
    target: int = 1
    condition_type: str = ""  # 'wins', 'time_lt', 'moves_lt', 'suits', 'streak'
    is_hidden: bool = False

    def __post_init__(self):
        """Если иконка не указана явно, используем ID достижения."""
        if not self.icon:
            self.icon = self.id

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Achievement':
        # При загрузке из БД берем то, что записано (или дефолт)
        return cls(
            id=data['id'],
            name=data['name'],
            description=data['description'],
            icon=data.get('icon', data['id']), # Если в БД пусто, берем id
            category=data.get('category', 'general'),
            target=data.get('target', 1),
            condition_type=data.get('condition_type', ''),
            is_hidden=bool(data.get('is_hidden', 0))
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'category': self.category,
            'target': self.target,
            'condition_type': self.condition_type,
            'is_hidden': self.is_hidden
        }

@dataclass
class PlayerAchievement:
    """Модель прогресса достижения игрока."""
    id: Optional[int]
    player_id: str
    achievement_id: str
    progress: int = 0
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlayerAchievement':
        unlocked_at = data.get('unlocked_at')
        if isinstance(unlocked_at, str):
            unlocked_at = datetime.fromisoformat(unlocked_at)

        return cls(
            id=data.get('id'),
            player_id=data['player_id'],
            achievement_id=data['achievement_id'],
            progress=data.get('progress', 0),
            unlocked=bool(data.get('unlocked', 0)),
            unlocked_at=unlocked_at
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'player_id': self.player_id,
            'achievement_id': self.achievement_id,
            'progress': self.progress,
            'unlocked': self.unlocked,
            'unlocked_at': self.unlocked_at.isoformat() if self.unlocked_at else None
        }