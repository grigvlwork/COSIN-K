# stats/data/__init__.py
"""
Модуль работы с базой данных статистики.

Предоставляет функции для инициализации БД и получения соединения.
"""

from .schema import init_database, get_db_path, create_tables
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

__all__ = [
    'init_database',
    'get_db_path',
    'create_tables',
    'get_connection',
    'connection_context',
    'get_db'
]


def get_connection() -> sqlite3.Connection:
    """
    Возвращает соединение с базой данных.

    Returns:
        sqlite3.Connection: Объект соединения с БД

    Example:
        >>> conn = get_connection()
        >>> cursor = conn.execute("SELECT * FROM players")
        >>> conn.close()
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Доступ по именам колонок
    return conn


@contextmanager
def connection_context() -> Generator[sqlite3.Connection, None, None]:
    """
    Контекстный менеджер для работы с БД.
    Автоматически закрывает соединение после использования.

    Example:
        >>> with connection_context() as conn:
        ...     cursor = conn.execute("SELECT * FROM players")
        ...     rows = cursor.fetchall()
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    """
    Упрощённый синоним для get_connection().

    Returns:
        sqlite3.Connection: Объект соединения с БД
    """
    return get_connection()


# Инициализация при импорте (опционально)
# Можно закомментировать, если нужен явный вызов
# init_database()


# Для удобства в интерактивной работе
def check_db() -> dict:
    """
    Проверяет состояние базы данных.
    Возвращает словарь с информацией о таблицах.

    Returns:
        dict: Информация о таблицах и записях
    """
    with connection_context() as conn:
        cursor = conn.cursor()

        # Получаем список таблиц
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        # Считаем записи в каждой таблице
        counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]

        return {
            'database': get_db_path(),
            'tables': tables,
            'records': counts,
            'status': 'ok'
        }


# Документация модуля
__doc__ = """
Модуль инициализации базы данных статистики.

Использование:
    >>> from stats.data import init_database, get_connection

    # Инициализация БД
    >>> init_database()

    # Получение соединения
    >>> conn = get_connection()
    >>> cursor = conn.execute("SELECT * FROM players")

    # Или через контекстный менеджер
    >>> with connection_context() as conn:
    ...     cursor = conn.execute("SELECT * FROM players")

    # Проверка состояния
    >>> from stats.data import check_db
    >>> print(check_db())
"""