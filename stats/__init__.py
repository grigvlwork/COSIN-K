"""Модуль статистики и достижений пасьянса."""

from stats.models import Player, Game, SavedGame
from stats.api.stats_api import StatsAPI

__all__ = ['Player', 'Game', 'SavedGame', 'StatsAPI']