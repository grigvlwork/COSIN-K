# stats/services/player_identity.py
"""Сервис идентификации игроков."""

import uuid
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from stats.models import Player
from stats.repositories.player_repository import PlayerRepository
from stats.data import get_db_path


class PlayerIdentity:
    """
    Сервис для управления идентификацией игроков.

    Работает в двух режимах:
    - Клиентский: хранит UUID в файле, общается с сервером
    - Серверный: проверяет UUID в БД, создаёт новых игроков

    Пример использования на клиенте:
        >>> identity = PlayerIdentity(storage_path="./client_data")
        >>> player_id = identity.get_or_create_client_identity()
        >>> # Отправляем player_id на сервер

    Пример использования на сервере:
        >>> identity = PlayerIdentity()  # без storage_path
        >>> player = identity.authenticate(player_id)
        >>> if player:
        ...     print(f"Добро пожаловать, {player.name}!")
    """

    # Имя файла для хранения identity на клиенте
    CLIENT_ID_FILE = "player.identity"

    def __init__(self, storage_path: Optional[str] = None):
        """
        Инициализация сервиса идентификации.

        Args:
            storage_path: Путь для хранения файла identity (для клиента)
                         Если None - работаем в серверном режиме
        """
        self.storage_path = storage_path
        self.current_player: Optional[Player] = None
        self._repo = PlayerRepository(get_db_path())

    # ===== Клиентские методы =====

    def get_or_create_client_identity(self) -> str:
        """
        Получить существующий UUID клиента или создать новый.
        Вызывается на клиенте при запуске.

        Returns:
            str: UUID игрока

        Пример:
            >>> identity = PlayerIdentity("./data")
            >>> player_id = identity.get_or_create_client_identity()
            >>> print(f"Мой ID: {player_id}")
        """
        if not self.storage_path:
            raise RuntimeError(
                "storage_path не указан. Этот метод предназначен для клиента."
            )

        id_path = Path(self.storage_path) / self.CLIENT_ID_FILE

        # Пробуем прочитать существующий UUID
        if id_path.exists():
            try:
                with open(id_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    player_id = data.get('player_id')

                    # Проверяем, что UUID валидный
                    if player_id and self._validate_uuid(player_id):
                        return player_id
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка чтения файла identity: {e}")

        # Создаём новый UUID
        return self._create_new_identity(id_path)

    def save_client_identity(self, player_id: str) -> bool:
        """
        Сохранить UUID в файл на клиенте.

        Args:
            player_id: UUID для сохранения

        Returns:
            bool: True если успешно сохранено
        """
        if not self.storage_path:
            raise RuntimeError("storage_path не указан")

        id_path = Path(self.storage_path) / self.CLIENT_ID_FILE

        try:
            # Создаём директорию, если нужно
            id_path.parent.mkdir(parents=True, exist_ok=True)

            with open(id_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'player_id': player_id,
                    'created_at': datetime.now().isoformat(),
                    'last_access': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Ошибка сохранения identity: {e}")
            return False

    def clear_client_identity(self) -> bool:
        """
        Удалить файл identity (для сброса игрока).

        Returns:
            bool: True если успешно удалён
        """
        if not self.storage_path:
            raise RuntimeError("storage_path не указан")

        id_path = Path(self.storage_path) / self.CLIENT_ID_FILE

        if id_path.exists():
            try:
                id_path.unlink()
                return True
            except IOError as e:
                print(f"Ошибка удаления identity: {e}")
                return False
        return True

    # ===== Серверные методы =====

    def authenticate(self, player_id: str) -> Optional[Player]:
        """
        Аутентифицировать игрока на сервере.

        Args:
            player_id: UUID игрока от клиента

        Returns:
            Player: объект игрока если найден, иначе None

        Пример:
            >>> identity = PlayerIdentity()
            >>> player = identity.authenticate("123e4567-e89b-12d3-a456-426614174000")
            >>> if player:
            ...     print(f"Добро пожаловать, {player.name}!")
            ... else:
            ...     print("Игрок не найден")
        """
        player = self._repo.get(player_id)

        if player:
            self.current_player = player
            # Обновляем время последнего входа
            self._repo.update_last_played(player_id)
            return player

        return None

    def get_or_create_server_player(self, player_id: str,
                                    default_name: Optional[str] = None) -> Player:
        """
        Получить игрока по ID или создать нового с этим ID.

        Args:
            player_id: UUID игрока (может быть сгенерирован клиентом)
            default_name: Имя по умолчанию (если None - генерируется)

        Returns:
            Player: объект игрока (существующий или новый)

        Пример:
            >>> identity = PlayerIdentity()
            >>> # Клиент прислал новый UUID
            >>> player = identity.get_or_create_server_player(
            ...     "new-uuid-123",
            ...     default_name="Игрок_123"
            ... )
        """
        # Проверяем, существует ли игрок
        player = self._repo.get(player_id)

        if player:
            self.current_player = player
            self._repo.update_last_played(player_id)
            return player

        # Создаём нового игрока
        new_player = Player(
            id=player_id,
            name=default_name or self._generate_default_name(),
            created_at=datetime.now(),
            last_played=datetime.now()
        )

        if self._repo.create(new_player):
            self.current_player = new_player
            return new_player

        raise RuntimeError(f"Не удалось создать игрока с ID {player_id}")

    def rename_player(self, player_id: str, new_name: str) -> bool:
        """
        Сменить имя игрока.

        Args:
            player_id: UUID игрока
            new_name: Новое имя

        Returns:
            bool: True если успешно переименован
        """
        # Валидация имени
        if not self._validate_name(new_name):
            return False

        success = self._repo.update(player_id, {'name': new_name})

        if success and self.current_player and self.current_player.id == player_id:
            self.current_player.name = new_name

        return success

    def get_player(self, player_id: str) -> Optional[Player]:
        """
        Получить информацию об игроке.

        Args:
            player_id: UUID игрока

        Returns:
            Player: объект игрока или None
        """
        return self._repo.get(player_id)

    # ===== Вспомогательные методы =====

    def _create_new_identity(self, id_path: Path) -> str:
        """
        Создать новый identity и сохранить в файл.
        """
        new_id = str(uuid.uuid4())

        try:
            # Создаём директорию, если нужно
            id_path.parent.mkdir(parents=True, exist_ok=True)

            with open(id_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'player_id': new_id,
                    'created_at': datetime.now().isoformat(),
                    'last_access': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)

            return new_id
        except IOError as e:
            print(f"Ошибка создания identity: {e}")
            # В крайнем случае возвращаем UUID без сохранения
            return new_id

    def _generate_default_name(self) -> str:
        """
        Сгенерировать имя по умолчанию для нового игрока.

        Returns:
            str: Имя вида "Игрок_1234" или "Player_1234"
        """
        # Генерируем случайное 4-значное число
        import random
        suffix = random.randint(1000, 9999)

        # Можно добавить забавные префиксы
        prefixes = ["Игрок", "Player", "CardMaster", "Solitaire", "Пасьянсер"]
        prefix = random.choice(prefixes)

        return f"{prefix}_{suffix}"

    def _validate_uuid(self, uuid_str: str) -> bool:
        """
        Проверить, что строка является валидным UUID.
        """
        try:
            uuid.UUID(uuid_str)
            return True
        except (ValueError, AttributeError):
            return False

    def _validate_name(self, name: str) -> bool:
        """
        Проверить, что имя игрока допустимо.
        """
        if not name or not name.strip():
            return False

        if len(name) > 50:
            return False

        # Запрещаем специальные символы, которые могут навредить
        forbidden = [';', '--', '<', '>', '&', '"', "'"]
        if any(char in name for char in forbidden):
            return False

        return True

    # ===== Утилиты =====

    def get_current_player(self) -> Optional[Player]:
        """
        Получить текущего аутентифицированного игрока.
        """
        return self.current_player

    def logout(self):
        """
        Выйти из текущей сессии (очистить текущего игрока).
        """
        self.current_player = None

    @staticmethod
    def generate_uuid() -> str:
        """
        Сгенерировать новый UUID (для клиента).

        Returns:
            str: Новый UUID
        """
        return str(uuid.uuid4())