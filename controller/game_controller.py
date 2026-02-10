"""
GameController — посредник между Model и View.
Обрабатывает команды пользователя и обновляет состояние.
"""

from typing import Optional, Dict, Any
from model import SolitaireEngine, GameState, GameFactory
from view import GameView


class GameController:
    """
    Контроллер связывает Model (SolitaireEngine) и View (GameView).
    Получает события от View, управляет Model, уведомляет View об изменениях.
    """

    def __init__(self, engine: SolitaireEngine, view: GameView):
        self.engine = engine
        self.view = view

        # Связываем View с контроллером
        self.view.controller = self

        # Состояние выбора для многошаговых операций
        self._selected_pile: Optional[str] = None
        self._selected_count: int = 1

        # Подписываемся на события модели
        self._setup_model_listeners()

    def _setup_model_listeners(self) -> None:
        """Подписаться на события от Model."""
        if self.engine.state:
            self.engine.state.add_listener(self._on_model_event)

    def _on_model_event(self, event: str, data: Dict[str, Any]) -> None:
        """Обработчик событий от Model."""
        handlers = {
            "game_started": lambda d: self.view.show_message("New game started!", "info"),
            "move_made": self._on_move_made,
            "game_won": self._on_game_won,
            "undo": lambda d: self.view.show_message("Undo successful", "success"),
        }

        handler = handlers.get(event)
        if handler:
            handler(data)

    def _on_move_made(self, data: Dict[str, Any]) -> None:
        """Обработка события хода."""
        # View обновится сам при следующем цикле
        pass

    def _on_game_won(self, data: Dict[str, Any]) -> None:
        """Обработка победы."""
        score = data.get("score", 0)
        self.view.show_message(f"🎉 You won! Final score: {score}", "win")

    # === Публичные методы для View ===

    def update_view(self) -> None:
        """Попросить View отобразить текущее состояние."""
        if self.engine.state:
            self.view.display_state(self.engine.state)

    def handle_command(self, command: str) -> None:
        """
        Обработать команду от пользователя.
        Формат команд:
            s <pile> [count]     — выбрать стопку
            m <from> <to> [n]    — переместить карты
            d                    — взять карту из колоды
            u                    — отменить ход
            n                    — новая игра
            q                    — выход
        """
        if not command:
            return

        parts = command.split()
        cmd = parts[0]
        args = parts[1:]

        handlers = {
            's': self._cmd_select,
            'select': self._cmd_select,
            'm': self._cmd_move,
            'move': self._cmd_move,
            'd': self._cmd_draw,
            'draw': self._cmd_draw,
            'u': self._cmd_undo,
            'undo': self._cmd_undo,
            'n': self._cmd_new,
            'new': self._cmd_new,
            'q': self._cmd_quit,
            'quit': self._cmd_quit,
            'h': self._cmd_help,
            'help': self._cmd_help,
        }

        handler = handlers.get(cmd, self._cmd_unknown)
        handler(args)

    # === Обработчики команд ===

    def _cmd_select(self, args: list) -> None:
        """Выбор стопки для многошагового хода."""
        if not args:
            self.view.show_message("Usage: s <pile_name> [count]", "error")
            return

        pile_name = args[0]
        count = int(args[1]) if len(args) > 1 else 1

        # Проверяем существование стопки
        pile = self.engine.state.get_pile(pile_name) if self.engine.state else None
        if pile is None:
            self.view.show_message(f"Unknown pile: {pile_name}", "error")
            return

        # Если нет выбранной — выбираем источник
        if self._selected_pile is None:
            if pile.is_empty():
                self.view.show_message("Cannot select empty pile", "error")
                return

            # Проверяем что можно взять столько карт
            face_up = pile.face_up_count()
            if count > face_up:
                self.view.show_message(f"Only {face_up} cards available", "error")
                return

            self._selected_pile = pile_name
            self._selected_count = count
            self.engine.state.selected_pile = pile_name
            self.update_view()

        # Иначе — выбираем назначение и выполняем ход
        else:
            success = self.engine.move(self._selected_pile, pile_name, self._selected_count)

            if success:
                self._clear_selection()
            else:
                self.view.show_message(
                    f"Cannot move {self._selected_count} card(s) "
                    f"from {self._selected_pile} to {pile_name}",
                    "error"
                )
                self._clear_selection()
                self.update_view()

    def _cmd_move(self, args: list) -> None:
        """Прямой ход: from to [count]."""
        if len(args) < 2:
            self.view.show_message("Usage: m <from_pile> <to_pile> [count]", "error")
            return

        from_pile, to_pile = args[0], args[1]
        count = int(args[2]) if len(args) > 2 else 1

        success = self.engine.move(from_pile, to_pile, count)

        if not success:
            self.view.show_message("Invalid move!", "error")

        self._clear_selection()
        self.update_view()

    def _cmd_draw(self, args: list) -> None:
        """Взять карту из колоды (stock → waste)."""
        # Стандартная логика: 1 или 3 карты
        draw_count = 1  # Можно сделать настраиваемым

        if self.engine.state.stock.is_empty():
            # Перемещаем waste обратно в stock
            if not self.engine.state.waste.is_empty():
                cards = self.engine.state.waste.take(len(self.engine.state.waste))
                cards.reverse()
                for c in cards:
                    c = c.flip()  # Закрываем
                self.engine.state.stock.add(cards)
                self.engine.state.notify("recycle", {})
                self.update_view()
            else:
                self.view.show_message("No cards to draw", "error")
            return

        # Берём из stock
        actual_count = min(draw_count, len(self.engine.state.stock))
        cards = self.engine.state.stock.take(actual_count)

        # Переворачиваем и кладём в waste
        cards = [c.flip() for c in cards]
        self.engine.state.waste.add(cards)

        self.engine.state.moves_count += 1
        self.engine.state.notify("draw", {"count": actual_count})
        self.update_view()

    def _cmd_undo(self, args: list) -> None:
        """Отменить последний ход."""
        success = self.engine.undo()
        if not success:
            self.view.show_message("Nothing to undo", "error")
        self._clear_selection()
        self.update_view()

    def _cmd_new(self, args: list) -> None:
        """Новая игра."""
        if self.engine.state and self.engine.state.moves_count > 0:
            if not self.view.ask_confirm("Abandon current game?"):
                return

        self._clear_selection()
        self.engine.new_game()
        self._setup_model_listeners()
        self.update_view()

    def _cmd_quit(self, args: list) -> None:
        """Выход из игры."""
        if self.engine.state and self.engine.state.moves_count > 0:
            # Можно добавить сохранение
            pass

        self.view.stop()

    def _cmd_help(self, args: list) -> None:
        """Показать справку."""
        help_text = """
Commands:
  s <pile> [n]     — select pile (then select destination)
  m <from> <to> [n] — move cards directly
  d                — draw from stock
  u                — undo last move
  n                — new game
  q                — quit
  h                — this help

Pile names:
  stock, waste
  tableau_0 ... tableau_6
  foundation_HEARTS, foundation_DIAMONDS, etc.
"""
        self.view.show_message(help_text, "info")

    def _cmd_unknown(self, args: list) -> None:
        """Неизвестная команда."""
        self.view.show_message(f"Unknown command. Type 'h' for help.", "error")

    # === Вспомогательные методы ===

    def _clear_selection(self) -> None:
        """Сбросить выбор стопки."""
        self._selected_pile = None
        self._selected_count = 1
        if self.engine.state:
            self.engine.state.selected_pile = None