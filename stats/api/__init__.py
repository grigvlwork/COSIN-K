# stats/api/__init__.py
"""
API слой для взаимодействия с GUI клиентом (Godot).

Предоставляет единый интерфейс StatsAPI для всех операций
со статистикой, идентификацией и сохранениями.
"""

from .stats_api import StatsAPI

__all__ = ['StatsAPI']