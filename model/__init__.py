"""
Solitaire Model — чистая логика игры (данные и правила).
"""

from .card import Card, Suit, Rank
from .pile import Pile
from .state import GameState, Move
from .history import HistoryManager, HistoryEntry  # ← добавлено
from .engine import SolitaireEngine
from .rules.base import RuleSet
from .rules.klondike import KlondikeRules
from .rules.factory import GameFactory, GameVariant

__all__ = [
    # Карты и стопки
    "Card",
    "Suit",
    "Rank",
    "Pile",

    # Состояние и история
    "GameState",
    "Move",
    "HistoryManager",   # ← добавлено
    "HistoryEntry",     # ← добавлено

    # Движок
    "SolitaireEngine",

    # Правила
    "RuleSet",
    "KlondikeRules",
    "GameFactory",
    "GameVariant",
]

__version__ = "0.1.0"