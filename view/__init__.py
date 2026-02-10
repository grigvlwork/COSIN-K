"""
View — отображение игры.
"""

from .base import GameView
from .console import ConsoleView

# Menu доступен через view.menu
from . import menu

__all__ = [
    "GameView",
    "ConsoleView",
    "menu",
]

__version__ = "0.1.0"