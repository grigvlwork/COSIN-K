"""
Menu — интерфейс начала игры (выбор пасьянса, игрока, настроек).
"""

from typing import Optional, Callable
from dataclasses import dataclass
import sys
from pathlib import Path
from model import Player, PlayerManager, GameFactory
from view.base import GameView

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@dataclass
class MenuChoice:
    """Результат выбора в меню."""
    player: Player
    game_type: str
    seed: Optional[int]


class GameMenu:
    """Консольное меню настройки игры."""

    def __init__(self, player_manager: PlayerManager, view: "GameView"):
        self.players = player_manager
        self.view = view

    def show_welcome(self) -> None:
        """Приветственный экран."""
        self.view.clear()
        print(r"""
      ___           ___           ___                       ___           ___     
     /\  \         /\  \         /\  \          ___        /\__\         /\__\    
    /::\  \       /::\  \       /::\  \        /\  \      /::|  |       /:/  /    
   /:/\:\  \     /:/\:\  \     /:/\ \  \       \:\  \    /:|:|  |      /:/__/     
  /:/  \:\  \   /:/  \:\  \   _\:\~\ \  \      /::\__\  /:/|:|  |__   /::\__\____ 
 /:/__/ \:\__\ /:/__/ \:\__\ /\ \:\ \ \__\  __/:/\/__/ /:/ |:| /\__\ /:/\:::::\__\
 \:\  \  \/__/ \:\  \ /:/  / \:\ \:\ \/__/ /\/:/  /    \/__|:|/:/  / \/_|:|~~|~   
  \:\  \        \:\  /:/  /   \:\ \:\__\   \::/__/         |:/:/  /     |:|  |    
   \:\  \        \:\/:/  /     \:\/:/  /    \:\__\         |::/  /      |:|  |    
    \:\__\        \::/  /       \::/  /      \/__/         /:/  /       |:|  |    
     \/__/         \/__/         \/__/                     \/__/         \|__|    
        """)
        print("=" * 50)
        print("Welcome to Console Solitaire!")
        print()

    def select_player(self) -> Player:
        """Выбор или создание игрока."""
        # Показываем существующих
        existing = sorted(
            self.players.players.values(),
            key=lambda p: (p.games_played, p.win_rate),
            reverse=True
        )

        if existing:
            print("Existing players:")
            for i, p in enumerate(existing, 1):
                total_games = sum(s.games_played for s in p.stats.values())
                print(f"  {i}. {p.name} ({total_games} games)")
            print("  n. New player")

            choice = self._ask_input("Select player (number or n): ")

            if choice.lower() == 'n':
                return self._create_player()

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(existing):
                    return existing[idx]
            except ValueError:
                pass

            print("Invalid choice, creating new player...")
            return self._create_player()
        else:
            print("No existing players found.")
            return self._create_player()

    def _create_player(self) -> Player:
        """Создание нового игрока."""
        name = self._ask_input("Enter your name: ").strip()

        if not name:
            name = "Player"

        # Проверяем уникальность
        for p in self.players.players.values():
            if p.name.lower() == name.lower():
                print(f"Welcome back, {p.name}!")
                return p

        player = self.players.create_player(name)
        print(f"Welcome, {player.name}!")
        return player

    def select_game(self, player: Player) -> str:
        """Выбор типа пасьянса."""
        print("\n" + "=" * 50)
        print("Select game type:")

        variants = GameFactory.list_variants()

        for i, v in enumerate(variants, 1):
            # Показываем статистику если есть
            stats = player.get_stats(v.name)
            played = f" (played: {stats.games_played}, won: {stats.games_won})" if stats.games_played else " (new)"

            print(f"  {i}. {v.title}")
            if v.description:
                print(f"     {v.description}")
            print(f"     Stats: {played}")
            print()

        while True:
            choice = self._ask_input("Your choice (number): ")

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(variants):
                    selected = variants[idx]
                    print(f"Selected: {selected.title}")
                    return selected.name
            except ValueError:
                pass

            print("Invalid choice, try again.")

    def select_seed(self) -> Optional[int]:
        """Выбор зерна для раздачи."""
        print("\n" + "=" * 50)
        print("Game setup:")

        use_seed = self._ask_confirm("Use specific seed for deal?")

        if use_seed:
            while True:
                seed_str = self._ask_input("Enter seed number: ")
                try:
                    return int(seed_str)
                except ValueError:
                    print("Please enter a valid number.")

        return None

    def show_player_stats(self, player: Player) -> None:
        """Показать статистику игрока."""
        print("\n" + "=" * 50)
        print(f"Statistics for {player.name}:")

        if not player.stats:
            print("  No games played yet.")
            return

        for game_key, stats in player.stats.items():
            win_rate = stats.win_rate() * 100
            print(f"\n  {game_key}:")
            print(f"    Games: {stats.games_played}")
            print(f"    Won: {stats.games_won} ({win_rate:.1f}%)")
            print(f"    Best score: {stats.best_score}")
            if stats.best_time < 999999:
                print(f"    Best time: {stats.best_time}s")

    def confirm_start(self) -> bool:
        """Подтверждение начала игры."""
        print("\n" + "=" * 50)
        return self._ask_confirm("Start game?")

    def run(self) -> Optional[MenuChoice]:
        """
        ПОКАЗАТЬ меню и ВЕРНУТЬ выбор.
        НЕ запускает игру! Запуск делает main.py.
        """
        try:
            self.show_welcome()
            player = self.select_player()
            self.show_player_stats(player)
            game_type = self.select_game(player)
            seed = self.select_seed()

            if not self.confirm_start():
                print("Cancelled.")
                return None

            return MenuChoice(player, game_type, seed)

        except (EOFError, KeyboardInterrupt):
            self.view.show_message("Game cancelled", "warning")
            return None

    # === Вспомогательные методы ===

    def _ask_input(self, prompt: str) -> str:
        """Запросить ввод с защитой от Ctrl+C."""
        try:
            return self.view.get_input(prompt)  # делегируем View
        except (EOFError, KeyboardInterrupt):
            self.view.show_message("Game cancelled", "warning")
            raise  # пробрасываем для обработки в run()

    def _ask_confirm(self, question: str) -> bool:
        """Запросить подтверждение через View."""
        return self.view.ask_confirm(question)

if __name__ == "__main__":
    print("\n❌ ОШИБКА: Нельзя запускать menu.py напрямую!")
    print("✅ Запустите main.py из корня проекта:\n")
    print("   python main.py\n")
    sys.exit(1)