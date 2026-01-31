import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from src.database.fetch_optimizer import fetch_all_optimized

logger = logging.getLogger(__name__)


class OrderAuditLog:
    """Журнал аудита всех операций с ордерами и ключами с поддержкой WAL и оптимизацией."""

    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        """Возвращает соединение с БД с оптимальными настройками."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_tables(self):
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Таблица ордеров
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS order_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        order_type TEXT NOT NULL,
                        amount REAL,
                        price REAL,
                        order_id TEXT,
                        status TEXT,
                        exchange TEXT,
                        error_msg TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Таблица операций с ключами
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS key_operations_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        operation TEXT NOT NULL,
                        exchange TEXT NOT NULL,
                        success INTEGER DEFAULT 1,
                        ip_address TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error("❌ Ошибка создания таблиц аудита: %s", e)

    def _insert_order(
        self,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float],
        order_id: Optional[str],
        status: str,
        exchange: str,
        error_msg: Optional[str],
    ) -> bool:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO order_audit_log(user_id, symbol, side, order_type, amount, price, order_id, status, exchange, error_msg)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(user_id),
                        symbol,
                        side,
                        order_type,
                        float(amount),
                        price,
                        order_id,
                        status,
                        exchange,
                        error_msg,
                    ),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.error("❌ Ошибка логирования ордера: %s", exc)
            return False

    async def log_order(
        self,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float],
        order_id: Optional[str],
        status: str,
        exchange: str = "bitget",
        error_msg: Optional[str] = None,
    ) -> bool:
        """Логирует операцию с ордером (async-совместимый интерфейс)."""
        return self._insert_order(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            order_id=order_id,
            status=status,
            exchange=exchange,
            error_msg=error_msg,
        )

    def log_order_sync(
        self,
        user_id: int,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float],
        order_id: Optional[str],
        status: str,
        exchange: str = "bitget",
        error_msg: Optional[str] = None,
    ) -> bool:
        """Синхронная запись операции с ордером."""
        return self._insert_order(
            user_id=user_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            order_id=order_id,
            status=status,
            exchange=exchange,
            error_msg=error_msg,
        )

    def order_exists(self, order_id: Optional[str], status: Optional[str] = None) -> bool:
        """Проверяет, существует ли запись в audit по order_id и (опционально) статусу."""
        if not order_id:
            return False
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if status:
                    cursor.execute(
                        """
                        SELECT 1 FROM order_audit_log WHERE order_id = ? AND status = ? LIMIT 1
                        """,
                        (order_id, status),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT 1 FROM order_audit_log WHERE order_id = ? LIMIT 1
                        """,
                        (order_id,),
                    )
                return cursor.fetchone() is not None
        except Exception as exc:
            logger.error("❌ Ошибка проверки order_exists: %s", exc)
            return False

    async def log_key_operation(self, user_id: int, operation: str, exchange: str, success: bool = True) -> bool:
        """Логирует операцию с ключами (save/delete/update)."""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO key_operations_log(user_id, operation, exchange, success)
                    VALUES(?, ?, ?, ?)
                """, (int(user_id), operation, exchange, 1 if success else 0))
                conn.commit()
                return True
        except Exception as e:
            logger.error("❌ Ошибка логирования операции с ключами: %s", e)
            return False


_audit_log_instance: Optional[OrderAuditLog] = None


def get_audit_log() -> OrderAuditLog:
    global _audit_log_instance
    if _audit_log_instance is None:
        _audit_log_instance = OrderAuditLog()
    return _audit_log_instance

