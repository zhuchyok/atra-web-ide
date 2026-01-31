#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 Connection Pool для SQLite (Игорь - после обучения 30%)

Предотвращает множественные подключения к SQLite и улучшает производительность.
Использует singleton pattern для переиспользования соединений.
"""

import sqlite3
import threading
import logging
from typing import Optional, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class SQLiteConnectionPool:
    """
    Connection Pool для SQLite

    Переиспользует соединения вместо создания новых для каждого запроса.
    Это критично для производительности и предотвращения блокировок.
    """

    _instance: Optional['SQLiteConnectionPool'] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str, max_connections: int = 5):
        """
        Args:
            db_path: Путь к файлу БД
            max_connections: Максимальное количество соединений в пуле
        """
        if SQLiteConnectionPool._instance is not None:
            raise RuntimeError("SQLiteConnectionPool is singleton! Use get_instance()")

        self.db_path = db_path
        self.max_connections = max_connections
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._in_use: Dict[int, bool] = {}
        self._pool_lock = threading.RLock()
        self._connection_counter = 0

        # Настройки по умолчанию для всех соединений
        self._default_pragmas = [
            "PRAGMA journal_mode=WAL;",
            "PRAGMA synchronous=NORMAL;",
            "PRAGMA busy_timeout=30000;",
            "PRAGMA foreign_keys=ON;"
        ]

        logger.info("📊 SQLite Connection Pool создан: %s, max=%s", db_path, max_connections)

    @classmethod
    def get_instance(cls, db_path: str = None, max_connections: int = 5) -> 'SQLiteConnectionPool':
        """
        Получить singleton экземпляр пула

        Args:
            db_path: Путь к БД (используется только при первом вызове)
            max_connections: Максимальное количество соединений
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if db_path is None:
                        raise ValueError("db_path required for first call")
                    cls._instance = cls(db_path, max_connections)
        return cls._instance

    def _create_connection(self) -> sqlite3.Connection:
        """Создает новое соединение с настройками"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )

        # Применяем PRAGMA настройки
        for pragma in self._default_pragmas:
            try:
                conn.execute(pragma)
            except sqlite3.Error as e:
                logger.warning("⚠️ Не удалось применить %s: %s", pragma, e)

        return conn

    @contextmanager
    def get_connection(self):
        """
        Context manager для получения соединения из пула

        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn_id = None

        try:
            # Ищем свободное соединение
            with self._pool_lock:
                for cid, in_use in self._in_use.items():
                    if not in_use:
                        conn_id = cid
                        self._in_use[cid] = True
                        break

                # Если нет свободных и не достигнут лимит - создаем новое
                if conn_id is None and len(self._connections) < self.max_connections:
                    conn_id = self._connection_counter
                    self._connection_counter += 1
                    self._connections[conn_id] = self._create_connection()
                    self._in_use[conn_id] = True
                    logger.debug("📊 Создано новое соединение #%s (всего: %s)", conn_id, len(self._connections))

            if conn_id is None:
                # Все соединения заняты - создаем временное
                logger.warning("⚠️ Все соединения заняты, создаю временное")
                conn = self._create_connection()
                try:
                    yield conn
                finally:
                    conn.close()
            else:
                # Используем соединение из пула
                conn = self._connections[conn_id]
                try:
                    yield conn
                finally:
                    # Возвращаем соединение в пул
                    with self._pool_lock:
                        self._in_use[conn_id] = False
                        # Проверяем соединение (может быть закрыто)
                        try:
                            conn.execute("SELECT 1")
                        except sqlite3.Error:
                            # Соединение закрыто - удаляем из пула
                            logger.warning("⚠️ Соединение #%s закрыто, удаляю из пула", conn_id)
                            del self._connections[conn_id]
                            del self._in_use[conn_id]

        except Exception as e:
            logger.error("❌ Ошибка в connection pool: %s", e)
            raise

    def close_all(self):
        """Закрывает все соединения в пуле"""
        with self._pool_lock:
            for conn_id, conn in list(self._connections.items()):
                try:
                    conn.close()
                except Exception as e:
                    logger.warning("⚠️ Ошибка при закрытии соединения #%s: %s", conn_id, e)
            self._connections.clear()
            self._in_use.clear()
            logger.info("📊 Все соединения закрыты")

    def get_stats(self) -> Dict:
        """Возвращает статистику пула"""
        with self._pool_lock:
            return {
                'total_connections': len(self._connections),
                'in_use': sum(1 for in_use in self._in_use.values() if in_use),
                'available': sum(1 for in_use in self._in_use.values() if not in_use),
                'max_connections': self.max_connections
            }


# Глобальный экземпляр (будет создан при первом использовании)
_pool_instance: Optional[SQLiteConnectionPool] = None


def get_db_pool(db_path: str = None, max_connections: int = 5) -> SQLiteConnectionPool:
    """
    Получить глобальный connection pool

    Args:
        db_path: Путь к БД (требуется при первом вызове)
        max_connections: Максимальное количество соединений

    Returns:
        SQLiteConnectionPool instance
    """
    global _pool_instance

    if _pool_instance is None:
        if db_path is None:
            raise ValueError("db_path required for first call to get_db_pool()")
        _pool_instance = SQLiteConnectionPool.get_instance(db_path, max_connections)

    return _pool_instance


def get_connection(db_path: str = None, max_connections: int = 5):
    """
    Получить соединение из connection pool (context manager)

    Args:
        db_path: Путь к БД (требуется при первом вызове)
        max_connections: Максимальное количество соединений

    Returns:
        Context manager для соединения
    """
    pool = get_db_pool(db_path, max_connections)
    return pool.get_connection()
