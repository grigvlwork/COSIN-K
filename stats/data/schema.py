# stats/data/schema.py
import sqlite3
import os
from pathlib import Path


def get_db_path() -> str:
    """Возвращает путь к файлу базы данных."""
    # База данных в папке data рядом со скриптом
    current_dir = Path(__file__).parent
    db_path = current_dir / "patience.db"
    return str(db_path)


def create_tables(conn: sqlite3.Connection) -> None:
    """Создаёт таблицы базы данных."""

    cursor = conn.cursor()

    # Таблица игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_played TIMESTAMP,

            -- Базовая статистика
            games_started INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            games_lost INTEGER DEFAULT 0,
            games_abandoned INTEGER DEFAULT 0,

            -- Серии
            current_win_streak INTEGER DEFAULT 0,
            best_win_streak INTEGER DEFAULT 0,
            current_loose_streak INTEGER DEFAULT 0,
            best_loose_streak INTEGER DEFAULT 0,

            -- Очки
            total_score INTEGER DEFAULT 0,
            highest_score INTEGER DEFAULT 0,

            -- Время
            total_play_time_seconds INTEGER DEFAULT 0,
            fastest_win_seconds INTEGER,
            slowest_win_seconds INTEGER,

            version INTEGER DEFAULT 1
        )
    """)

    # Таблица игр (завершённых)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL REFERENCES players(id),
            game_type TEXT DEFAULT 'klondike',  -- Какой пасьянс играли
            
             -- Сид для переигровки
            seed INTEGER,

            -- Время
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,

            -- Результат
            result TEXT CHECK(result IN ('won', 'lost', 'abandoned')),

            -- Метрики
            score INTEGER,
            duration_seconds INTEGER,
            moves_count INTEGER DEFAULT 0,
            undos_used INTEGER DEFAULT 0,
            hints_used INTEGER DEFAULT 0,
            deck_cycles INTEGER DEFAULT 0,

            -- Дополнительно для аналитики
            suits_completed TEXT,  -- JSON массив
            first_suit TEXT,
            was_perfect BOOLEAN DEFAULT 0,

            hour_of_day INTEGER,
            day_of_week INTEGER,
            is_weekend BOOLEAN
        )
    """)

    # Новая таблица: сохранённые игры (незавершённые)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            game_type TEXT NOT NULL,
            
            -- Сид для переигровки (сохраняем, чтобы можно было переиграть даже незавершенную)
            seed INTEGER,
                        
            game_state TEXT NOT NULL,  -- JSON с полным состоянием игры

            -- Временные метки
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Когда впервые сохранили
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Последнее обновление
            last_played TIMESTAMP,  -- Когда последний раз играли (загружали)

            -- Тип сохранения
            save_type TEXT DEFAULT 'autosave' 
                CHECK(save_type IN ('autosave', 'manual', 'checkpoint')),

            -- Метаданные для отображения в меню загрузки
            preview_data TEXT,  -- JSON с данными для превью (например, видимые карты)
            moves_count INTEGER DEFAULT 0,
            time_played_seconds INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,

            -- Для сортировки и фильтрации
            is_favorite BOOLEAN DEFAULT 0,
            description TEXT,  -- Пользовательское описание (для ручных сохранений)

            -- Ограничение: только одно автосохранение на игрока и тип игры
            UNIQUE(player_id, game_type, save_type) 
                ON CONFLICT REPLACE
        )
    """)

    # Индексы для таблицы games
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_games_player 
        ON games(player_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_games_player_date 
        ON games(player_id, started_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_games_type 
        ON games(game_type)
    """)

    # Индексы для таблицы saved_games
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_games_player 
        ON saved_games(player_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_games_updated 
        ON saved_games(player_id, updated_at DESC)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_games_type 
        ON saved_games(player_id, game_type)
    """)

    # Триггер для автоматического обновления updated_at
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_saved_games_timestamp 
        AFTER UPDATE ON saved_games
        BEGIN
            UPDATE saved_games SET updated_at = CURRENT_TIMESTAMP 
            WHERE id = NEW.id;
        END;
    """)

    conn.commit()


def init_database() -> None:
    """Инициализирует базу данных, создаёт если не существует."""
    db_path = get_db_path()

    # Создаём директорию если нужно
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        print(f"Database initialized: {db_path}")

        # Для отладки: показать структуру
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables created:", [table[0] for table in tables])

    finally:
        conn.close()


if __name__ == "__main__":
    init_database()