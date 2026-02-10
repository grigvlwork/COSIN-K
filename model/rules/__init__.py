"""
Rules — правила различных пасьянсов.
"""

from .base import RuleSet
from .klondike import KlondikeRules
from .factory import GameFactory, GameVariant

__all__ = [
    "RuleSet",
    "KlondikeRules",
    "GameFactory",
    "GameVariant",  # ← добавлено
]

__version__ = "0.1.0"
