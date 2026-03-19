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
    # ИЗМЕНЕНО: Добавлена колонка cosmetics
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

            -- Карты
            total_cards_moved INTEGER DEFAULT 0,
            total_cards_flipped INTEGER DEFAULT 0,

            -- Масти            
            completed_spades INTEGER DEFAULT 0,
            completed_hearts INTEGER DEFAULT 0,
            completed_diamonds INTEGER DEFAULT 0,
            completed_clubs INTEGER DEFAULT 0,

            -- Счетчик идеальных побед
            total_perfect_wins INTEGER DEFAULT 0,

            -- Время
            total_play_time_seconds INTEGER DEFAULT 0,
            fastest_win_seconds INTEGER,
            slowest_win_seconds INTEGER,

            -- НАСТРОЙКИ ВИДА (КОСМЕТИКА)
            -- Хранит JSON вида: {"deck": "classic", "back": "blue", "table": "wood"}
            cosmetics TEXT DEFAULT '{}',

            version INTEGER DEFAULT 1
        )
    """)

    # Таблица игр (завершённых)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL REFERENCES players(id),
            game_type TEXT DEFAULT 'klondike',
            seed INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            result TEXT CHECK(result IN ('won', 'lost', 'abandoned')),
            score INTEGER,
            duration_seconds INTEGER,
            moves_count INTEGER DEFAULT 0,
            undos_used INTEGER DEFAULT 0,
            hints_used INTEGER DEFAULT 0,
            deck_cycles INTEGER DEFAULT 0,
            suits_completed TEXT,
            first_suit TEXT,
            was_perfect BOOLEAN DEFAULT 0,
            hour_of_day INTEGER,
            day_of_week INTEGER,
            is_weekend BOOLEAN
        )
    """)

    # Таблица сохранённых игр
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            game_type TEXT NOT NULL,
            seed INTEGER,
            game_state TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_played TIMESTAMP,
            save_type TEXT DEFAULT 'autosave' 
                CHECK(save_type IN ('autosave', 'manual', 'checkpoint')),
            preview_data TEXT,
            moves_count INTEGER DEFAULT 0,
            time_played_seconds INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            is_favorite BOOLEAN DEFAULT 0,
            description TEXT,
            UNIQUE(player_id, game_type, save_type) 
                ON CONFLICT REPLACE
        )
    """)

    # Таблица достижений (Шаблоны)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT 'star',
                category TEXT DEFAULT 'general',
                target INTEGER DEFAULT 1,
                condition_type TEXT,
                is_hidden BOOLEAN DEFAULT 0
            )
        """)

    # Таблица прогресса игроков по достижениям
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                achievement_id TEXT NOT NULL REFERENCES achievements(id) ON DELETE CASCADE,
                progress INTEGER DEFAULT 0,
                unlocked BOOLEAN DEFAULT 0,
                unlocked_at TIMESTAMP,
                UNIQUE(player_id, achievement_id)
            )
        """)

    # Индексы
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_player_achievements_player ON player_achievements(player_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_player_achievements_unlocked ON player_achievements(player_id, unlocked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_player ON games(player_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_player_date ON games(player_id, started_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_type ON games(game_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_games_player ON saved_games(player_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_games_updated ON saved_games(player_id, updated_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_games_type ON saved_games(player_id, game_type)")

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
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        print(f"Database initialized: {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()