# stats/repositories/saved_game_repository.py
"""
Репозиторий для работы с сохранёнными играми (таблица saved_games).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

from stats.models import SavedGame
from stats.repositories.base_repository import BaseRepository
from stats.data import connection_context


class SavedGameRepository(BaseRepository[SavedGame]):
    """
    Репозиторий для операций с таблицей saved_games.
    """

    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.table_name = "saved_games"

    # ===== БАЗОВЫЕ МЕТОДЫ =====

    def get(self, saved_id: int) -> Optional[SavedGame]:
        """Получить сохранение по ID."""
        query = f"SELECT * FROM {self.table_name} WHERE id = ?"
        results = self._execute(query, (saved_id,))

        if results and len(results) > 0:
            row = results[0]
            # === ИСПРАВЛЕНИЕ: Парсим JSON поля ===
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            # ====================================
            return SavedGame.from_dict(row)
        return None

    def create(self, saved_game: SavedGame) -> Optional[int]:
        """Создать новое сохранение."""
        data = saved_game.to_dict()

        # Убираем поля, которые будут auto-filled
        data.pop('id', None)
        data.pop('created_at', None)
        data.pop('updated_at', None)

        # Преобразуем JSON поля в строки для БД
        if 'game_state' in data and data['game_state']:
            data['game_state'] = json.dumps(data['game_state'])
        if 'preview_data' in data and data['preview_data']:
            data['preview_data'] = json.dumps(data['preview_data'])

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())

        query = f"""
            INSERT INTO {self.table_name} 
            ({columns}) VALUES ({placeholders})
        """

        try:
            with connection_context() as conn:
                cursor = conn.execute(query, tuple(values))
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating saved game: {e}")
            return None

    def update(self, saved_id: int, data: Dict[str, Any]) -> bool:
        """Обновить сохранение."""
        if not data:
            return True

        # Запрещаем менять некоторые поля
        forbidden = {'id', 'player_id', 'created_at'}
        update_data = {k: v for k, v in data.items() if k not in forbidden}

        if not update_data:
            return True

        # Преобразуем JSON поля в строки для БД
        if 'game_state' in update_data and update_data['game_state']:
            update_data['game_state'] = json.dumps(update_data['game_state'])
        if 'preview_data' in update_data and update_data['preview_data']:
            update_data['preview_data'] = json.dumps(update_data['preview_data'])

        # updated_at обновится автоматически триггером
        set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [saved_id]

        query = f"""
            UPDATE {self.table_name} 
            SET {set_clause} 
            WHERE id = ?
        """

        try:
            self._execute(query, tuple(values))
            return True
        except Exception as e:
            print(f"Error updating saved game: {e}")
            return False

    def delete(self, saved_id: int) -> bool:
        """Удалить сохранение."""
        query = f"DELETE FROM {self.table_name} WHERE id = ?"

        try:
            self._execute(query, (saved_id,))
            return True
        except Exception as e:
            print(f"Error deleting saved game: {e}")
            return False

    def update_last_played(self, saved_id: int) -> bool:
        """Обновить время последнего доступа к сохранению."""
        query = f"""
            UPDATE {self.table_name} 
            SET last_played = CURRENT_TIMESTAMP
            WHERE id = ?
        """

        try:
            self._execute(query, (saved_id,))
            return True
        except Exception as e:
            print(f"Error updating last_played: {e}")
            return False

    # ===== МЕТОДЫ ДЛЯ РАБОТЫ С АВТОСОХРАНЕНИЯМИ =====

    def get_autosave(self, player_id: str, game_type: str) -> Optional[SavedGame]:
        """Получить автосохранение для игрока и типа игры."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND game_type = ? AND save_type = 'autosave'
            ORDER BY updated_at DESC LIMIT 1
        """

        results = self._execute(query, (player_id, game_type))

        if results and len(results) > 0:
            row = results[0]
            # === ИСПРАВЛЕНИЕ: Парсим JSON поля ===
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            # ====================================
            return SavedGame.from_dict(row)
        return None

    def save_autosave(self, player_id: str, game_type: str,
                      game_state: Dict[str, Any],
                      seed: Optional[int] = None,
                      score: int = 0,
                      moves_count: int = 0,
                      time_played_seconds: int = 0) -> Optional[int]:
        """
        Сохранить или обновить автосохранение.
        """
        # Проверяем существующее автосохранение
        existing = self.get_autosave(player_id, game_type)

        if existing:
            # Обновляем существующее
            success = self.update(existing.id, {
                'game_state': game_state,
                'seed': seed,
                'score': score,
                'moves_count': moves_count,
                'time_played_seconds': time_played_seconds,
                'last_played': datetime.now()
            })
            return existing.id if success else None

        # Создаём новое
        saved = SavedGame(
            player_id=player_id,
            game_type=game_type,
            game_state=game_state,
            seed=seed,
            save_type='autosave',
            last_played=datetime.now(),
            score=score,
            moves_count=moves_count,
            time_played_seconds=time_played_seconds
        )
        return self.create(saved)

    # ===== МЕТОДЫ ДЛЯ РУЧНЫХ СОХРАНЕНИЙ =====

    def get_by_player(self, player_id: str,
                      game_type: Optional[str] = None) -> List[SavedGame]:
        """Получить все сохранения игрока."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ?
        """
        params = [player_id]

        if game_type:
            query += " AND game_type = ?"
            params.append(game_type)

        query += " ORDER BY updated_at DESC"

        results = self._execute(query, tuple(params))

        # === ИСПРАВЛЕНИЕ: Парсим JSON для каждого элемента ===
        items = []
        for row in results:
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            items.append(SavedGame.from_dict(row))
        return items

    def get_manual_saves(self, player_id: str) -> List[SavedGame]:
        """Получить только ручные сохранения игрока."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND save_type = 'manual'
            ORDER BY updated_at DESC
        """

        results = self._execute(query, (player_id,))
        # === ИСПРАВЛЕНИЕ ===
        items = []
        for row in results:
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            items.append(SavedGame.from_dict(row))
        return items

    def get_checkpoints(self, player_id: str) -> List[SavedGame]:
        """Получить точки сохранения (checkpoints)."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND save_type = 'checkpoint'
            ORDER BY updated_at DESC
        """

        results = self._execute(query, (player_id,))
        # === ИСПРАВЛЕНИЕ ===
        items = []
        for row in results:
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            items.append(SavedGame.from_dict(row))
        return items

    # ===== МЕТОДЫ ДЛЯ ИЗБРАННОГО =====

    def toggle_favorite(self, saved_id: int) -> bool:
        """Переключить статус избранного."""
        saved = self.get(saved_id)
        if not saved:
            return False

        return self.update(saved_id, {'is_favorite': not saved.is_favorite})

    def get_favorites(self, player_id: str) -> List[SavedGame]:
        """Получить избранные сохранения."""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE player_id = ? AND is_favorite = 1
            ORDER BY updated_at DESC
        """

        results = self._execute(query, (player_id,))
        # === ИСПРАВЛЕНИЕ ===
        items = []
        for row in results:
            if 'game_state' in row and isinstance(row['game_state'], str):
                row['game_state'] = json.loads(row['game_state'])
            if 'preview_data' in row and isinstance(row['preview_data'], str):
                row['preview_data'] = json.loads(row['preview_data'])
            items.append(SavedGame.from_dict(row))
        return items

    # ===== МЕТОДЫ ДЛЯ ПРЕВЬЮ =====

    def update_preview(self, saved_id: int, preview_data: Dict[str, Any]) -> bool:
        """Обновить данные для превью."""
        return self.update(saved_id, {'preview_data': preview_data})

    # ===== МЕТОДЫ ДЛЯ ОЧИСТКИ =====

    def delete_old_autosaves(self, days: int = 30) -> int:
        """Удалить старые автосохранения."""
        cutoff = datetime.now() - timedelta(days=days)
        query = f"""
            DELETE FROM {self.table_name} 
            WHERE save_type = 'autosave' AND updated_at < ?
        """

        try:
            with connection_context() as conn:
                cursor = conn.execute(query, (cutoff.isoformat(),))
                return cursor.rowcount
        except Exception as e:
            print(f"Error deleting old autosaves: {e}")
            return 0

    def delete_by_player(self, player_id: str) -> int:
        """Удалить все сохранения игрока."""
        query = f"DELETE FROM {self.table_name} WHERE player_id = ?"

        try:
            with connection_context() as conn:
                cursor = conn.execute(query, (player_id,))
                return cursor.rowcount
        except Exception as e:
            print(f"Error deleting player saves: {e}")
            return 0