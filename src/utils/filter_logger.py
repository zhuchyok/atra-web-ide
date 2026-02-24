#!/usr/bin/env python3
"""
Утилита для логирования проверок фильтров и отклоненных сигналов.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

from config import DATABASE
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


def log_filter_check(
    symbol: str,
    filter_type: str,
    passed: bool,
    reason: Optional[str] = None,
    signal_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    МАКСИМАЛЬНО НАДЕЖНАЯ ЗАПИСЬ (ОТКРЫЛ-ЗАПИСАЛ-ЗАКРЫЛ)
    """
    if passed:
        return True

    try:
        # Прямое соединение без кэширования в потоках
        conn = sqlite3.connect(DATABASE, timeout=30.0)
        cursor = conn.cursor()

        now = get_utc_now().isoformat()
        # Гарантируем, что JSON корректный и не содержит Decimal
        if signal_data:
            signal_data = {
                k: float(v) if hasattr(v, "__float__") else v for k, v in signal_data.items()
            }
        signal_data_json = json.dumps(signal_data) if signal_data else None

        entry_price = None
        if signal_data:
            entry_price = signal_data.get("entry_price") or signal_data.get("price")

        query = """
            INSERT INTO rejected_signals (
                symbol, entry_price, signal_time, rejection_reason,
                filter_name, filter_result, signal_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        cursor.execute(
            query, (symbol, entry_price, now, reason, filter_type, "REJECTED", signal_data_json)
        )
        conn.commit()
        conn.close()

        # ЛОГ ДЛЯ ДИАГНОСТИКИ (виден в консоли сервера)
        logger.info("📉 [REJECTED] %s заблокирован фильтром %s: %s", symbol, filter_type, reason)
        return True
    except Exception as e:
        logger.error("❌ FilterLogger Error for %s: %s", symbol, e, exc_info=True)
        return False


async def log_filter_check_async(
    symbol: str,
    filter_type: str,
    passed: bool,
    reason: Optional[str] = None,
    signal_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Асинхронная обертка"""
    return await asyncio.to_thread(
        log_filter_check, symbol, filter_type, passed, reason, signal_data
    )


def get_filter_stats(hours: int = 24) -> dict:
    """Получает статистику отклонений за последние N часов"""
    try:
        conn = sqlite3.connect(DATABASE)
        query = """
            SELECT filter_name, count(*) as count
            FROM rejected_signals
            WHERE created_at >= datetime('now', ?)
            GROUP BY filter_name
            ORDER BY count DESC
        """
        cursor = conn.cursor()
        cursor.execute(query, (f"-{hours} hours",))
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows} if rows else {}
    except Exception:
        return {}
