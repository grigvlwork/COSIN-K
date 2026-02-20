"""
ConsoleView — консольная реализация отображения.
"""

import os
import sys
import re
from wcwidth import wcswidth
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from model import GameState, Card
    from controller import GameController

from .base import GameView

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def visible_length(text: str) -> int:
    clean = ANSI_RE.sub('', text)
    return wcswidth(clean)

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

    def _show_mini_help(self) -> None:
        """Показать минимальную справку (1-2 строки)."""
        print(f"\n{self._color('blue')}Commands:{self._reset()} (m)ove, (d)raw, (u)ndo, (n)ew, (q)uit, (h)elp")
        print(f"{self._color('blue')}Quick:{self._reset()} 0-6(auto), w(waste), 0h/5d/wh/t3s")

    def display_state(self,
                      state: "GameState",
                      selected_pile: Optional[str] = None,
                      selected_count: int = 1) -> None:
        """Отобразить текущее состояние игры."""
        self._last_state = state
        self.clear()

        # Заголовок
        print(f"{self._color('bold')}=== SOLITAIRE ==={self._reset()}")
        print(f"{self._color('bold')}Score: {state.score} | Moves: {state.moves_count}{self._reset()}")
        print("=" * 50)

        # Stock и Waste
        if state.stock:
            count = len(state.stock)
            stock_str = f"[{self.SYMBOLS['BACK']}×{count}]" if count > 1 else f"[{self.SYMBOLS['BACK']}]"
        else:
            stock_str = f"[ ]"

        if state.waste and len(state.waste) > 0:
            waste_cards = state.waste[-3:]
            waste_str = " ".join(self.card_to_str(card) for card in waste_cards)
        else:
            waste_str = "[ ]"

        print(f"Stock: {stock_str}  Waste: {waste_str}")
        print()

        # Foundations
        print("Foundations:")
        from model import Suit
        for suit in Suit:
            pile = state.piles.get(f"foundation_{suit.name}")
            top_card = pile.top() if pile else None
            pile_str = self.card_to_str(top_card) if top_card else "[ ]"
            suit_symbol = self.SYMBOLS[suit.name]
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
        COL_WIDTH = 5

        # Заголовки
        headers = " ".join(f"{i:>{COL_WIDTH - 1}}" for i in range(7))
        print(f"     {headers}")

        # Разделитель
        print("    " + "-" * (COL_WIDTH * 7))

        # Строки
        for row in range(max_height):
            line = f"{row:>2} |"
            for pile in tableau_piles:
                if row < len(pile):
                    card_str = self.card_to_str(pile[row])
                    visible_len = visible_length(card_str)
                    padding = COL_WIDTH - visible_len
                    line += " " * max(padding, 0) + card_str
                else:
                    line += " " * COL_WIDTH
            print(line)

        # 🔥 МИНИМАЛЬНАЯ СПРАВКА (ВСЕГДА)
        self._show_mini_help()

    def clear(self) -> None:
        """Очистить консоль."""
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_input(self, prompt: str = "") -> str:
        """Получить команду от пользователя."""
        try:
            if prompt:
                print(f"\n{prompt}", end="")
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
            # if self._controller:
            #     self._controller.update_view()

            command = self.get_input()

            if self._controller:
                self._controller.handle_command(command)

    def stop(self) -> None:
        """Остановить цикл."""
        self.running = False
        print(f"\n{self._color('green')}Thanks for playing!{self._reset()}")


if __name__ == "__main__":
    print("\n❌ ОШИБКА: Нельзя запускать console.py напрямую!")
    print("✅ Запустите main.py из корня проекта:\n")
    print("   python main.py\n")
    sys.exit(1)
