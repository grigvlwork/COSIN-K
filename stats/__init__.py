# stats/__init__.py
"""Модуль статистики и достижений пасьянса."""

from stats.models import Player, Game, SavedGame
from stats.api.stats_api import StatsAPI
from stats.models import Achievement, PlayerAchievement

__all__ = ['Player', 'Game', 'SavedGame', 'StatsAPI',
           'Achievement', 'PlayerAchievement']