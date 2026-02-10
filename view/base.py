"""
GameView — абстрактный базовый класс для всех видов отображения.
Определяет контракт, который должны реализовать конкретные View.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from model import GameState


class GameView(ABC):
    """
    Абстрактный интерфейс отображения игры.
    Может быть реализован как консоль, GUI, Web или тестовый mock.
    """

    def __init__(self):
        self._controller: Optional["GameController"] = None

    @property
    def controller(self) -> Optional["GameController"]:
        """Контроллер для обратной связи."""
        return self._controller

    @controller.setter
    def controller(self, controller: "GameController") -> None:
        """Установить контроллер."""
        self._controller = controller

    # === Отображение состояния ===

    @abstractmethod
    def display_state(self, state: "GameState") -> None:
        """
        Отобразить текущее состояние игры.
        Вызывается при каждом обновлении экрана.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Очистить экран/холст."""
        pass

    # === Взаимодействие с пользователем ===

    @abstractmethod
    def get_input(self) -> str:
        """
        Получить команду от пользователя.
        Блокирующий вызов до ввода.
        """
        pass

    @abstractmethod
    def show_message(self, message: str, msg_type: str = "info") -> None:
        """
        Показать сообщение пользователю.

        Args:
            message: Текст сообщения
            msg_type: Тип — "info", "error", "success", "warning", "win"
        """
        pass

    @abstractmethod
    def ask_confirm(self, question: str) -> bool:
        """Задать вопрос с ответом да/нет."""
        pass

    @abstractmethod
    def ask_choice(self, question: str, options: list) -> int:
        """
        Предложить выбор из списка.

        Returns:
            Индекс выбранного варианта
        """
        pass

    # === Жизненный цикл ===

    @abstractmethod
    def run(self) -> None:
        """
        Главный цикл отображения.
        Блокирует выполнение до завершения игры.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Остановить цикл и закрыть View."""
        pass

    # === Утилиты ===

    def update(self) -> None:
        """
        Запросить обновление отображения через контроллер.
        Удобный shortcut для self.controller.update_view()
        """
        if self._controller:
            self._controller.update_view()

    def handle(self, command: str) -> None:
        """
        Передать команду контроллеру.
        Удобный shortcut для self.controller.handle_command()
        """
        if self._controller:
            self._controller.handle_command(command)