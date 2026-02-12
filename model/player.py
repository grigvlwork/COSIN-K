"""
Player — управление игроками и статистикой.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import json
from pathlib import Path


@dataclass
class GameStats:
    """Статистика по конкретному типу игры."""
    games_played: int = 0
    games_won: int = 0
    best_score: int = 0
    best_time: int = 999999  # секунды

    def win_rate(self) -> float:
        """Процент побед."""
        if self.games_played == 0:
            return 0.0
        return self.games_won / self.games_played

    def update(self, won: bool, score: int, time_elapsed: int = 0) -> None:
        """Обновить статистику после игры."""
        self.games_played += 1
        if won:
            self.games_won += 1
        if score > self.best_score:
            self.best_score = score
        if time_elapsed > 0 and time_elapsed < self.best_time:
            self.best_time = time_elapsed


@dataclass
class Player:
    """Игрок и его статистика."""
    player_id: str
    name: str
    stats: Dict[str, GameStats] = field(default_factory=dict)

    def get_stats(self, game_type: str) -> GameStats:
        """Получить статистику для игры (создаёт если нет)."""
        if game_type not in self.stats:
            self.stats[game_type] = GameStats()
        return self.stats[game_type]

    def finish_game(self, game_type: str, won: bool,
                    engine: "SolitaireEngine") -> None:
        """Завершить игру, обновить статистику."""
        stats = self.get_stats(game_type)
        stats.update(
            won=won,
            score=engine.state.score if engine.state else 0,
            time_elapsed=engine.state.time_elapsed if engine.state else 0
        )

    @property
    def games_played(self) -> int:
        """Общее количество игр по всем типам."""
        return sum(s.games_played for s in self.stats.values())

    @property
    def win_rate(self) -> float:
        """Общий процент побед."""
        total = self.games_played
        if total == 0:
            return 0.0
        won = sum(s.games_won for s in self.stats.values())
        return won / total


class PlayerManager:
    """Загрузка/сохранение игроков."""

    def __init__(self, filename: str = "players.json"):
        self.filename = filename
        self.players: Dict[str, Player] = {}
        self._load()

    def _load(self) -> None:
        """Загрузить игроков из JSON."""
        path = Path(self.filename)
        if not path.exists():
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for player_id, player_data in data.items():
                # Восстанавливаем статистику
                stats = {}
                for game, stat_data in player_data.get('stats', {}).items():
                    stats[game] = GameStats(**stat_data)

                self.players[player_id] = Player(
                    player_id=player_id,
                    name=player_data['name'],
                    stats=stats
                )
        except (json.JSONDecodeError, KeyError):
            # Файл повреждён — начинаем с чистого листа
            self.players = {}

    def _save(self) -> None:
        """Сохранить игроков в JSON."""
        data = {}
        for player_id, player in self.players.items():
            data[player_id] = {
                'name': player.name,
                'stats': {
                    game: asdict(stats)
                    for game, stats in player.stats.items()
                }
            }

        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_player(self, name: str) -> Player:
        """Создать нового игрока."""
        # Генерируем уникальный ID
        base_id = name.lower().replace(' ', '_')
        player_id = base_id
        counter = 1

        while player_id in self.players:
            player_id = f"{base_id}_{counter}"
            counter += 1

        player = Player(player_id=player_id, name=name)
        self.players[player_id] = player
        self._save()
        return player

    def get_player(self, player_id: str) -> Optional[Player]:
        """Получить игрока по ID."""
        return self.players.get(player_id)

    def delete_player(self, player_id: str) -> bool:
        """Удалить игрока."""
        if player_id in self.players:
            del self.players[player_id]
            self._save()
            return True
        return False

    def rename_player(self, player_id: str, new_name: str) -> bool:
        """Переименовать игрока."""
        if player_id in self.players:
            self.players[player_id].name = new_name
            self._save()
            return True
        return False

    def __repr__(self) -> str:
        return f"PlayerManager(players={len(self.players)})"