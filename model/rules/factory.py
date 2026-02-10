"""
GameFactory — создание правил для разных пасьянсов с поддержкой вариантов.
"""

from typing import Dict, Type, List
from dataclasses import dataclass
from .base import RuleSet
from .klondike import KlondikeRules


@dataclass
class GameVariant:
    """Вариант игры с параметрами."""
    name: str                    # Идентификатор: "klondike-3"
    base_game: str               # Базовый тип: "klondike"
    title: str                   # Отображаемое название
    params: dict                 # Параметры для конструктора
    description: str = ""


class GameFactory:
    """Фабрика с поддержкой вариантов."""

    # Базовые игры
    _base_games: Dict[str, Type[RuleSet]] = {
        "klondike": KlondikeRules,
    }

    # Варианты (инициализируются при первом вызове)
    _variants: Dict[str, GameVariant] = {}
    _initialized: bool = False

    @classmethod
    def _initialize(cls):
        """Инициализация стандартных вариантов."""
        if cls._initialized:
            return

        # Klondike 1 card (классика)
        cls._variants["klondike"] = GameVariant(
            name="klondike",
            base_game="klondike",
            title="Klondike (1 card)",
            params={"draw_three": False},
            description="Classic solitaire, draw 1 card from stock"
        )

        # Klondike 3 cards (сложнее)
        cls._variants["klondike-3"] = GameVariant(
            name="klondike-3",
            base_game="klondike",
            title="Klondike (3 cards)",
            params={"draw_three": True},
            description="Harder variant, draw 3 cards from stock"
        )

        cls._initialized = True

    @classmethod
    def create(cls, game_type: str, **override_params) -> RuleSet:
        """
        Создать правила с учётом вариантов.

        Args:
            game_type: Идентификатор варианта ("klondike", "klondike-3")
            **override_params: Переопределение параметров варианта

        Returns:
            Экземпляр RuleSet
        """
        cls._initialize()

        # Ищем вариант
        variant = cls._variants.get(game_type)

        if variant:
            # Базовая игра + параметры варианта + переопределения
            base_class = cls._base_games[variant.base_game]
            final_params = {**variant.params, **override_params}
            return base_class(**final_params)

        # Прямое создание базовой игры с параметрами по умолчанию
        base_class = cls._base_games.get(game_type)
        if base_class:
            return base_class(**override_params)

        # Неизвестная игра
        available = ", ".join(cls.available_games())
        raise ValueError(
            f"Unknown game type: {game_type!r}. "
            f"Available: {available}"
        )

    @classmethod
    def available_games(cls) -> List[str]:
        """Все доступные варианты."""
        cls._initialize()
        return list(cls._variants.keys())

    @classmethod
    def is_available(cls, game_type: str) -> bool:
        """Проверить доступность варианта."""
        cls._initialize()
        return game_type in cls._variants

    @classmethod
    def get_variant_info(cls, game_type: str) -> GameVariant:
        """Информация о варианте."""
        cls._initialize()
        return cls._variants.get(game_type)

    @classmethod
    def register_variant(cls, variant: GameVariant) -> None:
        """Добавить новый вариант."""
        cls._initialize()

        if variant.base_game not in cls._base_games:
            raise ValueError(f"Base game {variant.base_game} not found")

        cls._variants[variant.name] = variant

    @classmethod
    def list_variants(cls, base_game: str = None) -> List[GameVariant]:
        """Список вариантов, опционально фильтр по базовой игре."""
        cls._initialize()
        variants = list(cls._variants.values())

        if base_game:
            variants = [v for v in variants if v.base_game == base_game]

        return variants

    @classmethod
    def get_base_game(cls, game_type: str) -> str:
        """Получить базовый тип игры для варианта."""
        cls._initialize()
        variant = cls._variants.get(game_type)
        return variant.base_game if variant else game_type