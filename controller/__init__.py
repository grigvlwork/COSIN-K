"""
Controller — связующее звено между Model и View.
Обрабатывает пользовательский ввод и управляет игровым процессом.
"""

from .game_controller import GameController

__all__ = [
    "GameController",  # Главный контроллер игры
]

__version__ = "0.1.0"