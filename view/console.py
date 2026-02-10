"""
ConsoleView — консольная реализация отображения.
"""

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import GameState, Card
    from controller import GameController

from .base import GameView


class ConsoleView(GameView):
    """Консольный интерфейс для пасьянса."""

    # Символы для отображения карт
    SYMBOLS = {
        'HEARTS': '♥',
        'DIAMONDS': '♦',
        'CLUBS': '♣',
        'SPADES': '♠',
        'BACK': '🂠',
        'EMPTY': '  ',
    }

    # Цвета терминала (ANSI)
    COLORS = {
        'red': '\033[91m',
        'black': '\033[90m',
        'reset': '\033[0m',
        'bold': '\033[1m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
    }

    # Префиксы сообщений
    MSG_PREFIX = {
        'info': 'ℹ',
        'error': '✗',
        'success': '✓',
        'warning': '⚠',
        'win': '🏆',
    }

    def __init__(self):
        super().__init__()
        self.running = False
        self._last_state = None

    def _color(self, name: str) -> str:
        """Получить ANSI-код цвета."""
        return self.COLORS.get(name, '')

    def _reset(self) -> str:
        """Сброс цвета."""
        return self.COLORS['reset']

    def card_to_str(self, card: "Card") -> str:
        """Преобразовать карту в строку с цветом."""
        if not card.face_up:
            return f"[{self.SYMBOLS['BACK']}]"

        suit_symbol = self.SYMBOLS[card.suit.name]
        rank_str = (
            card.rank.name[0] if card.rank.value > 10
            else str(card.rank.value)
        )

        color = 'red' if card.color == 'red' else 'black'

        return f"{self._color(color)}{rank_str}{suit_symbol}{self._reset()}"

    def display_state(self, state: "GameState") -> None:
        """Отобразить текущее состояние игры."""
        self._last_state = state
        self.clear()

        # Заголовок
        print(f"{self._color('bold')}Score: {state.score} | Moves: {state.moves_count}{self._reset()}")
        print("=" * 50)

        # Stock и Waste
        stock_str = f"[{self.SYMBOLS['BACK']}]" if state.stock else f"[{self.SYMBOLS['EMPTY']}]"
        waste_card = state.waste.top()
        waste_str = self.card_to_str(waste_card) if waste_card else f"[{self.SYMBOLS['EMPTY']}]"

        print(f"Stock: {stock_str}  Waste: {waste_str}")
        print()

        # Foundations (4 базовые стопки)
        print("Foundations:")
        for suit_name in ['HEARTS', 'DIAMONDS', 'CLUBS', 'SPADES']:
            pile = state.piles.get(f"foundation_{suit_name}")
            top_card = pile.top() if pile else None
            pile_str = self.card_to_str(top_card) if top_card else "[  ]"
            suit_symbol = self.SYMBOLS[suit_name]
            print(f"  {suit_symbol}: {pile_str}", end="  ")
        print("\n")

        # Tableau (7 столбцов)
        print("Tableau:")

        # Находим максимальную высоту
        tableau_piles = [
            state.piles.get(f"tableau_{i}", [])
            for i in range(7)
        ]
        max_height = max((len(p) for p in tableau_piles), default=0)

        # Заголовки столбцов
        headers = "  ".join(f"{i:>4}" for i in range(7))
        print(f"     {headers}")
        print("    " + "-" * 35)

        # Строки карт
        for row in range(max_height):
            line = f"{row:>2} |"
            for pile in tableau_piles:
                if row < len(pile):
                    card_str = self.card_to_str(pile[row])
                    line += f" {card_str:>4}"
                else:
                    line += f" {'':>4}"
            print(line)

        # Выделение выбранной стопки
        if state.selected_pile:
            print(f"\n{self._color('yellow')}Selected: {state.selected_pile}{self._reset()}")

        # Подсказка команд
        print(f"\n{self._color('blue')}Commands:{self._reset()}")
        print("  (s)elect <pile> [count]  — выбрать стопку")
        print("  (m)ove <from> <to> [n]   — переместить")
        print("  (d)raw                   — взять из колоды")
        print("  (u)ndo                   — отменить ход")
        print("  (n)ew                    — новая игра")
        print("  (q)uit                   — выход")

    def clear(self) -> None:
        """Очистить консоль."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_input(self) -> str:
        """Получить команду от пользователя."""
        try:
            return input(f"\n{self._color('bold')}>{self._reset()} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 'q'

    def show_message(self, message: str, msg_type: str = "info") -> None:
        """Показать сообщение."""
        prefix = self.MSG_PREFIX.get(msg_type, '•')
        color = {
            'error': 'red',
            'success': 'green',
            'warning': 'yellow',
            'win': 'green',
        }.get(msg_type, 'reset')

        print(f"\n{self._color(color)}{prefix} {message}{self._reset()}")

        if msg_type in ('error', 'win', 'success'):
            input("Press Enter to continue...")

    def ask_confirm(self, question: str) -> bool:
        """Задать вопрос да/нет."""
        answer = input(f"{question} [y/N]: ").strip().lower()
        return answer in ('y', 'yes', 'да', 'д')

    def ask_choice(self, question: str, options: list) -> int:
        """Предложить выбор из списка."""
        print(f"\n{question}")
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")

        while True:
            try:
                choice = input("Choice (number): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return idx
                print("Invalid choice")
            except ValueError:
                print("Please enter a number")

    def run(self) -> None:
        """Главный цикл отображения."""
        self.running = True

        while self.running:
            if self._controller:
                self._controller.update_view()

            command = self.get_input()

            if self._controller:
                self._controller.handle_command(command)

    def stop(self) -> None:
        """Остановить цикл."""
        self.running = False
        print(f"\n{self._color('green')}Thanks for playing!{self._reset()}")