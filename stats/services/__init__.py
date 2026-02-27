# stats/services/__init__.py
"""
Сервисы бизнес-логики модуля статистики.

Этот пакет содержит сервисы, реализующие основную логику работы
со статистикой игроков, игр и достижений.

Доступные сервисы:
    - PlayerIdentity: управление идентификацией игроков
    - StatsService: сбор и анализ статистики игр
"""

from .player_identity import PlayerIdentity
from .stats_service import StatsService

__all__ = [
    'PlayerIdentity',  # Сервис идентификации игроков
    'StatsService',    # Сервис статистики игр
]

# Для удобства можно также импортировать модели, но лучше делать это явно
# from stats.models import Player, Game, SavedGame, PlayerStats