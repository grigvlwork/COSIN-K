#!/usr/bin/env python3
"""
Solitaire — главный модуль.
"""

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from model import SolitaireEngine, GameFactory, PlayerManager
from view import ConsoleView
from view.menu import GameMenu, MenuChoice
from controller import GameController


def parse_args():
    """Парсинг аргументов для быстрого старта."""
    parser = argparse.ArgumentParser(
        description="Console Solitaire Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Quick start (skip menu):
  python main.py -g klondike -p Alice -s 42

Interactive menu (default):
  python main.py
        """
    )

    parser.add_argument(
        '-g', '--game',
        choices=GameFactory.available_games(),
        default=None,
        help='Skip menu: game type'
    )

    parser.add_argument(
        '-p', '--player',
        default=None,
        help='Skip menu: player name'
    )

    parser.add_argument(
        '-s', '--seed',
        type=int,
        default=None,
        help='Skip menu: seed for deal'
    )

    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colors'
    )

    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick mode: skip menu even without args (last player/game)'
    )

    return parser.parse_args()


def quick_start(args, players: PlayerManager) -> MenuChoice:
    """Быстрый старт без меню."""
    # Игрок
    if args.player:
        # Ищем по имени
        player = None
        for p in players.players.values():
            if p.name.lower() == args.player.lower():
                player = p
                break

        if not player:
            print(f"Creating player: {args.player}")
            player = players.create_player(args.player)
    else:
        # Последний игрок или новый
        player = list(players.players.values())[-1] if players.players else players.create_player("Player")

    # Игра
    game_type = args.game or "klondike"

    return MenuChoice(player, game_type, args.seed)


def interactive_menu(players: PlayerManager, view: ConsoleView) -> MenuChoice:
    """Интерактивное меню."""
    menu = GameMenu(players, view)
    return menu.run()


def main():
    """Главная функция."""
    args = parse_args()

    # Инициализация
    players = PlayerManager("players.json")
    view = ConsoleView()

    if args.no_color:
        view.COLORS = {k: '' for k in view.COLORS}

    # Получаем настройки игры
    if args.game and args.player:
        # Полный набор аргументов — быстрый старт
        choice = quick_start(args, players)
    elif args.quick:
        # Флаг --quick — быстрый старт с дефолтами
        choice = quick_start(args, players)
    else:
        # Интерактивное меню
        choice = interactive_menu(players, view)

    if choice is None:
        print("Goodbye!")
        return 0

    # Создаём компоненты игры
    rules = GameFactory.create(choice.game_type)
    engine = SolitaireEngine(rules, choice.player.player_id)

    # Настройка View и Controller
    view.controller = None  # Сброс для новой игры
    controller = GameController(engine, view)

    # Приветствие
    print(f"\n{'=' * 50}")
    print(f"Player: {choice.player.name}")
    print(f"Game: {GameFactory.get_variant_info(choice.game_type).title}")
    if choice.seed:
        print(f"Seed: {choice.seed}")
    print(f"{'=' * 50}\n")

    # Старт
    engine.new_game(seed=choice.seed)

    # Игровой цикл
    try:
        view.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
    finally:
        # Сохранение
        if engine.state and engine.state.moves_count > 0:
            won = engine.check_win()
            choice.player.finish_game(choice.game_type, won, engine)
            players._save()

            if won:
                print(f"\n🏆 Victory! Score: {engine.state.score}")
            else:
                print(f"\nGame saved. Score: {engine.state.score}")

        print("Goodbye!")

    return 0


if __name__ == "__main__":
    sys.exit(main())