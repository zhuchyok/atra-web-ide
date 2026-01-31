#!/usr/bin/env python3
"""Автоматический импорт закрытых сделок из trading.db в систему обучения паттернов."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def sync_trades_to_patterns(
    db_path: str = "trading.db",
    hours: int = 24,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Синхронизирует закрытые сделки из trading.db в систему обучения паттернов."""
    try:
        from ai_integration import AIIntegration

        ai_integration = AIIntegration()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Получаем закрытые сделки за последние hours часов
        since = datetime.utcnow() - timedelta(hours=hours)

        # Проверяем наличие таблицы trades
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trades'
        """)
        if not cursor.fetchone():
            logger.warning("⚠️ Таблица trades не найдена в БД")
            conn.close()
            return {"synced": 0, "errors": 0, "message": "Таблица trades не найдена"}

        # Получаем закрытые сделки
        cursor = conn.execute("""
            SELECT 
                symbol,
                direction,
                entry_price,
                exit_price,
                entry_time,
                exit_time,
                exit_reason,
                net_pnl_usd,
                pnl_percent,
                user_id
            FROM trades
            WHERE datetime(exit_time) >= datetime(?)
              AND exit_time IS NOT NULL
            ORDER BY exit_time DESC
        """, (since.isoformat(),))

        trades = cursor.fetchall()
        conn.close()

        if not trades:
            logger.info("ℹ️ Нет новых закрытых сделок за последние %d часов", hours)
            return {"synced": 0, "errors": 0, "message": "Нет новых сделок"}

        logger.info("📊 Найдено %d закрытых сделок за последние %d часов", len(trades), hours)

        synced = 0
        errors = 0

        for trade in trades:
            try:
                symbol = trade["symbol"]
                direction = trade["direction"].upper()
                entry_price = float(trade["entry_price"])
                exit_price = float(trade["exit_price"])
                exit_reason = trade["exit_reason"] or "unknown"
                profit_pct = float(trade["pnl_percent"])
                user_id = int(trade.get("user_id", 0)) if trade.get("user_id") else 0

                if dry_run:
                    logger.info(
                        "🔍 [DRY RUN] Обновление паттерна: %s %s entry=%.8f exit=%.8f profit=%.2f%%",
                        symbol, direction, entry_price, exit_price, profit_pct
                    )
                    synced += 1
                else:
                    # Обновляем паттерн в системе обучения
                    await ai_integration.update_pattern_from_closed_trade(
                        symbol=symbol,
                        side=direction,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                        user_id=user_id,
                        profit_pct=profit_pct,
                    )
                    synced += 1
                    logger.debug(
                        "✅ Обновлён паттерн: %s %s (%.2f%%)",
                        symbol, direction, profit_pct
                    )

            except Exception as e:
                errors += 1
                logger.error("❌ Ошибка синхронизации сделки: %s", e)

        result = {
            "synced": synced,
            "errors": errors,
            "total": len(trades),
            "message": f"Синхронизировано {synced} из {len(trades)} сделок",
        }

        if not dry_run:
            logger.info("✅ Синхронизация завершена: %s", result["message"])
        else:
            logger.info("🔍 [DRY RUN] Будет синхронизировано: %d сделок", synced)

        return result

    except Exception as e:
        logger.error("❌ Критическая ошибка синхронизации: %s", e, exc_info=True)
        return {"synced": 0, "errors": 1, "message": f"Ошибка: {e}"}


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Синхронизация закрытых сделок в паттерны")
    parser.add_argument("--db", default="trading.db", help="Путь к БД")
    parser.add_argument("--hours", type=int, default=24, help="Период для синхронизации (часы)")
    parser.add_argument("--dry-run", action="store_true", help="Только показать, что будет сделано")
    args = parser.parse_args()

    logger.info("🔄 Запуск синхронизации закрытых сделок в паттерны...")
    result = await sync_trades_to_patterns(
        db_path=args.db,
        hours=args.hours,
        dry_run=args.dry_run,
    )

    logger.info("📊 Результат: %s", result["message"])
    return result


if __name__ == "__main__":
    asyncio.run(main())

