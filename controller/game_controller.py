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

        # Состояние выбора для многошаговых операций (ТОЛЬКО В КОНТРОЛЛЕРЕ!)
        self._selected_pile: Optional[str] = None
        self._selected_count: int = 1

        # Подписываемся на события Engine
        self._setup_engine_listeners()

    def _setup_engine_listeners(self) -> None:
        """Подписаться на события от Engine."""
        self.engine.add_listener(self._on_engine_event)

    def _on_engine_event(self, event: str, data: Dict[str, Any]) -> None:
        """Обработчик событий от Engine."""
        handlers = {
            "game_started": self._on_game_started,
            "move_made": self._on_move_made,
            "draw": self._on_draw,
            "recycle": self._on_recycle,
            "game_won": self._on_game_won,
            "undo": self._on_undo,
            "redo": self._on_redo,
        }

        handler = handlers.get(event)
        if handler:
            handler(data)

    def _on_game_started(self, data: Dict[str, Any]) -> None:
        """Обработка начала игры."""
        self.view.show_message("New game started!", "info")
        self.update_view()

    def _on_move_made(self, data: Dict[str, Any]) -> None:
        """Обработка хода."""
        self._clear_selection()
        self.update_view()

    def _on_draw(self, data: Dict[str, Any]) -> None:
        """Обработка взятия карт."""
        count = data.get("count", 1)
        self.view.show_message(f"Drew {count} card(s)", "info")
        self.update_view()

    def _on_recycle(self, data: Dict[str, Any]) -> None:
        """Обработка перебора колоды."""
        count = data.get("count", 0)
        self.view.show_message(f"Recycled {count} card(s)", "info")
        self.update_view()

    def _on_game_won(self, data: Dict[str, Any]) -> None:
        """Обработка победы."""
        score = data.get("score", 0)
        self.view.show_message(f"🎉 You won! Final score: {score}", "win")
        self.update_view()

    def _on_undo(self, data: Dict[str, Any]) -> None:
        """Обработка отмены хода."""
        self.view.show_message("Undo successful", "success")
        self.update_view()

    def _on_redo(self, data: Dict[str, Any]) -> None:
        """Обработка повтора хода."""
        self.view.show_message("Redo successful", "success")
        self.update_view()

    # === Публичные методы для View ===
    def _parse_pile_name(self, name: str) -> str:
        """0 → tableau_0, h → foundation_HEARTS, w → waste, t3 → tableau_3"""
        name = name.lower().strip()

        # Цифры → tableau
        if name.isdigit():
            return f"tableau_{name}"

        # t0, t1 → tableau
        if name.startswith('t') and name[1:].isdigit():
            return f"tableau_{name[1:]}"

        # Масти → foundation
        suit_map = {
            'h': 'HEARTS', 'd': 'DIAMONDS',
            'c': 'CLUBS', 's': 'SPADES'
        }
        if name in suit_map:
            return f"foundation_{suit_map[name]}"

        # Специальные стопки
        if name in ('w', 'waste'):
            return 'waste'
        if name in ('st', 'stock'):
            return 'stock'

        # Полное имя — НЕ ИЗМЕНЯЕМ!
        return name  # ← уже полное имя, не трогаем

    def update_view(self) -> None:
        """Попросить View отобразить текущее состояние."""
        if self.engine.state:
            # Передаём в View дополнительно информацию о выбранной стопке
            self.view.display_state(
                self.engine.state,
                selected_pile=self._selected_pile,
                selected_count=self._selected_count
            )

    def handle_command(self, command: str) -> None:
        """Обработать команду от пользователя."""
        if not command:
            return

        parts = command.split()
        cmd = parts[0].lower()  # нормализуем регистр
        args = parts[1:]

        # 🔥 НОВОЕ: Супер-короткие команды типа "0h", "5d", "wh"
        if len(cmd) == 2 and cmd[0].isdigit() and cmd[1] in 'hdcs':
            # Передаём сырые "0" и "h" — _cmd_move сам преобразует
            return self._cmd_move([cmd[0], cmd[1], "1"])

        if len(cmd) == 2 and cmd[0] in 'wst' and cmd[1] in 'hdcs':
            return self._cmd_move([cmd[0], cmd[1], "1"])

        # Нормализация алиасов
        cmd_map = {
            's': 'select', 'select': 'select',
            'm': 'move', 'move': 'move',
            'd': 'draw', 'draw': 'draw',
            'u': 'undo', 'undo': 'undo',
            'r': 'redo', 'redo': 'redo',
            'n': 'new', 'new': 'new',
            'q': 'quit', 'quit': 'quit',
            'h': 'help', 'help': 'help',
        }

        normalized_cmd = cmd_map.get(cmd, cmd)
        handlers = {
            'select': self._cmd_select,
            'move': self._cmd_move,
            'draw': self._cmd_draw,
            'undo': self._cmd_undo,
            'redo': self._cmd_redo,
            'new': self._cmd_new,
            'quit': self._cmd_quit,
            'help': self._cmd_help,
        }

        handler = handlers.get(normalized_cmd, self._cmd_unknown)
        handler(args)

    # === Обработчики команд ===

    def _cmd_select(self, args: list) -> None:
        """Выбор стопки для многошагового хода."""
        if not args:
            self.view.show_message("Usage: select <pile_name> [count]", "error")
            return

        # 🔥 ПРЕОБРАЗУЕМ КОРОТКОЕ ИМЯ
        pile_name = self._parse_pile_name(args[0])

        try:
            count = int(args[1]) if len(args) > 1 else 1
        except ValueError:
            self.view.show_message("Count must be a number", "error")
            return

        if not self.engine.state:
            return

        pile = self.engine.state.get_pile(pile_name)
        if pile is None:
            self.view.show_message(f"Unknown pile: {pile_name}", "error")
            return

        # Если нет выбранной — выбираем источник
        if self._selected_pile is None:
            if pile.is_empty():
                self.view.show_message("Cannot select empty pile", "error")
                return

            face_up = pile.face_up_count()
            if count > face_up:
                self.view.show_message(f"Only {face_up} cards available", "error")
                return

            self._selected_pile = pile_name
            self._selected_count = count
            self.view.show_message(f"Selected {pile_name} ({count} card(s))", "info")
            self.update_view()

        # Иначе — выбираем назначение и выполняем ход
        else:
            success = self.engine.move(self._selected_pile, pile_name, self._selected_count)

            if not success:
                self.view.show_message(
                    f"Cannot move {self._selected_count} card(s) "
                    f"from {self._selected_pile} to {pile_name}",
                    "error"
                )

            self._clear_selection()
            # View обновится по событию от Engine

    def _cmd_move(self, args: list) -> None:
        """Прямой ход: from to [count]."""
        if len(args) < 2:
            self.view.show_message("Usage: move <from_pile> <to_pile> [count]", "error")
            return
        from_pile = self._parse_pile_name(args[0])
        to_pile = self._parse_pile_name(args[1])
        try:
            count = int(args[2]) if len(args) > 2 else 1
        except ValueError:
            self.view.show_message("Count must be a number", "error")
            return

        success = self.engine.move(from_pile, to_pile, count)

        if not success:
            self.view.show_message("Invalid move!", "error")

        self._clear_selection()
        # View обновится по событию от Engine

    def _cmd_draw(self, args: list) -> None:
        """Взять карту из колоды."""
        if not self.engine.state:
            return

        success = self.engine.draw()

        if not success:
            self.view.show_message("Cannot draw more cards", "error")

        self._clear_selection()
        # View обновится по событию от Engine

    def _cmd_undo(self, args: list) -> None:
        """Отменить последний ход."""
        success = self.engine.undo()
        if not success:
            self.view.show_message("Nothing to undo", "error")
        self._clear_selection()
        # View обновится по событию от Engine

    def _cmd_redo(self, args: list) -> None:
        """Повторить отменённый ход."""
        success = self.engine.redo()
        if not success:
            self.view.show_message("Nothing to redo", "error")
        self._clear_selection()
        # View обновится по событию от Engine

    def _cmd_new(self, args: list) -> None:
        """Новая игра."""
        variant = args[0] if args else "klondike"

        # Проверяем существование варианта
        if not GameFactory.is_available(variant):
            self.view.show_message(f"Unknown variant: {variant}", "error")
            self.view.show_message(f"Available: {', '.join(GameFactory.available_games())}", "info")
            return

        if self.engine.state and self.engine.state.moves_count > 0:
            if not self.view.ask_confirm("Abandon current game?"):
                return

        self._clear_selection()
        self.engine.new_game(variant)  # ← передаём вариант!
        # View обновится по событию от Engine

    def _cmd_quit(self, args: list) -> None:
        """Выход из игры."""
        if self.engine.state and self.engine.state.moves_count > 0:
            if self.view.ask_confirm("Save game before quitting?"):
                # TODO: реализовать сохранение
                pass

        self.view.stop()

    def _cmd_help(self, args: list) -> None:
        """Показать справку."""
        variants = ", ".join(GameFactory.available_games())
        help_text = f"""
=== Solitaire Game Controller ===

Commands:
  select <pile> [n]  — select source pile (then click destination)
  move <from> <to> [n] — move cards directly
  draw              — draw card(s) from stock
  undo              — undo last move
  redo              — redo undone move
  new [variant]     — start new game (variants: {variants})
  quit              — exit game
  help              — this help

Pile names:
  stock, waste
  tableau_0 ... tableau_6
  foundation_HEARTS, foundation_DIAMONDS, etc.

Examples:
  select tableau_0 2  — select 2 cards from first column
  move waste foundation_HEARTS  — move top waste card to hearts foundation
  draw               — draw from stock
  new klondike-3     — start Klondike with 3-card draw
"""
        self.view.show_message(help_text, "info")

    def _cmd_unknown(self, args: list) -> None:
        """Неизвестная команда."""
        self.view.show_message("Unknown command. Type 'help' for available commands.", "error")

    # === Вспомогательные методы ===

    def _clear_selection(self) -> None:
        """Сбросить выбор стопки."""
        self._selected_pile = None
        self._selected_count = 1
        # self.update_view()  # показываем снятие выделения
