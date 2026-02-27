# stats/repositories/__init__.py
"""Репозитории для доступа к данным."""

from .player_repository import PlayerRepository
from .game_repository import GameRepository
from .saved_game_repository import SavedGameRepository
from .base_repository import BaseRepository

__all__ = [
    'BaseRepository',
    'PlayerRepository',
    'GameRepository',
    'SavedGameRepository'
]