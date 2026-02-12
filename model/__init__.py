"""
Model — игровая модель пасьянса.
"""

from .card import Card, Suit, Rank
from .pile import Pile
from .state import GameState
from .move import Move
from .history import HistoryManager
from .engine import SolitaireEngine
from .player import Player, GameStats, PlayerManager

# Импортируем правила
from .rules import RuleSet, KlondikeRules, GameFactory, GameVariant

__all__ = [
    # Карты
    "Card", "Suit", "Rank",
    # Стопки
    "Pile",
    # Состояние
    "GameState", "Move",
    # История
    "HistoryManager",
    # Движок
    "SolitaireEngine",
    # Игроки
    "Player", "GameStats", "PlayerManager",
    # Правила
    "RuleSet", "KlondikeRules", "GameFactory", "GameVariant",
]

__version__ = "0.1.0"