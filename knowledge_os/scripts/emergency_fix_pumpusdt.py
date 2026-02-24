#!/usr/bin/env python3
"""
Экстренный скрипт для исправления позиции PUMPUSDT
Синхронизирует позицию с биржи, добавляет в БД и устанавливает TP1/TP2/SL
"""

import asyncio
import logging
import sys
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("emergency_fix_pumpusdt")

# Добавляем путь к корню проекта
sys.path.insert(0, ".")

import pandas as pd
from acceptance_database import AcceptanceDatabase
from order_audit_log import get_audit_log
from shared_utils import get_dynamic_tp_levels

from src.execution.exchange_adapter import ExchangeAdapter


async def get_tp_sl_from_signal(
    symbol: str, entry_price: float, direction: str
) -> Dict[str, float]:
    """
    Получает TP1/TP2/SL из сигнала или рассчитывает динамически

    Для PUMPUSDT из сигнала:
    - Entry: 0.003241
    - TP1: 0.003175 (+1.69%)
    - TP2: 0.003110 (+3.37%)
    - SL: 0.003293 (-1.60%)
    """
    # Пробуем найти в accepted_signals по entry_price
    db = AcceptanceDatabase()
    try:
        import sqlite3

        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            # Ищем сигнал с близкой ценой входа (допуск 0.1%)
            cursor.execute(
                """
                SELECT tp1, tp2, sl, entry_price
                FROM accepted_signals
                WHERE symbol = ?
                  AND direction = ?
                  AND ABS(entry_price - ?) / ? < 0.001
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (symbol.upper(), direction.upper(), entry_price, entry_price),
            )
            row = cursor.fetchone()
            if row and row[0] and row[1] and row[2]:
                tp1, tp2, sl = float(row[0] or 0), float(row[1] or 0), float(row[2] or 0)
                if tp1 > 0 and tp2 > 0 and sl > 0:
                    logger.info("✅ Найден сигнал в БД: TP1=%.8f, TP2=%.8f, SL=%.8f", tp1, tp2, sl)
                    return {"tp1": tp1, "tp2": tp2, "sl": sl}
    except Exception as e:
        logger.debug("Ошибка поиска сигнала в БД: %s", e)

    # Если не нашли, используем значения из сигнала PUMPUSDT
    if symbol.upper() == "PUMPUSDT" and abs(entry_price - 0.003241) < 0.0001:
        logger.info("✅ Используем значения из сигнала PUMPUSDT")
        return {"tp1": 0.003175, "tp2": 0.003110, "sl": 0.003293}

    # Fallback: динамический расчет
    logger.warning("⚠️ Сигнал не найден, используем динамический расчет")
    try:
        # Получаем данные для расчета
        from signal_live import get_symbol_data

        df = await get_symbol_data(symbol)
        if df is not None and len(df) > 0:
            if isinstance(df, list):
                df = pd.DataFrame(df)
            current_index = len(df) - 1
            side = "long" if direction.upper() in ("BUY", "LONG") else "short"
            tp1_pct, tp2_pct = get_dynamic_tp_levels(
                df, current_index, side, "futures", adjust_for_fees=True
            )

            if direction.upper() in ("BUY", "LONG"):
                tp1 = entry_price * (1 + tp1_pct / 100)
                tp2 = entry_price * (1 + tp2_pct / 100)
                sl = entry_price * (1 - 1.6 / 100)  # -1.6% для SL
            else:
                tp1 = entry_price * (1 - tp1_pct / 100)
                tp2 = entry_price * (1 - tp2_pct / 100)
                sl = entry_price * (1 + 1.6 / 100)  # +1.6% для SL

            return {"tp1": tp1, "tp2": tp2, "sl": sl}
    except Exception as e:
        logger.error("Ошибка динамического расчета: %s", e)

    # Последний fallback: фиксированные проценты
    if direction.upper() in ("BUY", "LONG"):
        return {"tp1": entry_price * 1.018, "tp2": entry_price * 1.036, "sl": entry_price * 0.984}
    else:
        return {"tp1": entry_price * 0.982, "tp2": entry_price * 0.964, "sl": entry_price * 1.016}


async def fix_pumpusdt_position(user_id: int) -> Dict[str, Any]:
    """Исправляет позицию PUMPUSDT для пользователя"""
    db = AcceptanceDatabase()
    audit = get_audit_log()

    # Получаем ключи
    keys = await db.get_active_exchange_keys(user_id, exchange_name="bitget")
    if not keys:
        return {"error": "no_keys", "user_id": user_id}

    adapter = ExchangeAdapter("bitget", keys=keys, sandbox=False, trade_mode="futures")
    if not adapter.client:
        return {"error": "no_client", "user_id": user_id}

    # Получаем позиции с биржи
    exch_positions = await adapter.fetch_positions() or []
    pump_position = None

    for p in exch_positions:
        sym = (p.get("symbol") or "").replace("/", "").replace(":USDT", "").upper()
        if sym == "PUMPUSDT":
            size = float(p.get("contracts") or p.get("size") or 0.0)
            if size > 0:
                pump_position = p
                break

    if not pump_position:
        logger.warning("⚠️ PUMPUSDT позиция не найдена на бирже")
        return {"error": "position_not_found", "user_id": user_id}

    # Извлекаем данные позиции
    symbol = "PUMPUSDT"
    side = (pump_position.get("side") or "").lower()
    direction = "SELL" if side == "short" else "BUY"
    entry_price = float(pump_position.get("entryPrice") or pump_position.get("openPriceAvg") or 0.0)
    position_size = float(pump_position.get("contracts") or pump_position.get("size") or 0.0)

    logger.info(
        "🔍 Найдена позиция PUMPUSDT: %s @ %.8f, size=%.4f", direction, entry_price, position_size
    )

    # Получаем TP/SL
    tp_sl = await get_tp_sl_from_signal(symbol, entry_price, direction)
    tp1_price = tp_sl["tp1"]
    tp2_price = tp_sl["tp2"]
    sl_price = tp_sl["sl"]

    logger.info("📊 TP/SL: TP1=%.8f, TP2=%.8f, SL=%.8f", tp1_price, tp2_price, sl_price)

    # Проверяем, есть ли уже позиция в БД
    db_positions = await db.get_active_positions_by_user(str(user_id))
    pump_in_db = False
    for pos in db_positions:
        if (pos.get("symbol") or "").upper() == "PUMPUSDT":
            pump_in_db = True
            break

    # Добавляем в БД, если нет
    if not pump_in_db:
        logger.info("➕ Добавляем PUMPUSDT в БД...")
        ok = await db.create_active_position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            user_id=user_id,
            message_id=None,
            chat_id=None,
            signal_key=None,
        )
        if ok:
            logger.info("✅ PUMPUSDT добавлена в БД")
        else:
            logger.warning("⚠️ Не удалось добавить PUMPUSDT в БД")

    # Проверяем существующие план-ордера
    plan_orders = await adapter.fetch_plan_orders()
    has_tp1 = False
    has_tp2 = False
    has_sl = False

    for order in plan_orders or []:
        sym = str(order.get("symbol") or order.get("symbolId") or "").upper()
        if "PUMP" not in sym:
            continue
        client_oid = str(order.get("clientOid") or order.get("client_oid") or "").lower()
        if "tp1" in client_oid:
            has_tp1 = True
        elif "tp2" in client_oid:
            has_tp2 = True
        elif "sl" in client_oid:
            has_sl = True

    results = {"tp1_created": False, "tp2_created": False, "sl_created": False}

    # Устанавливаем SL, если нет
    if not has_sl:
        try:
            sl_order = await adapter.place_stop_loss_order(
                symbol,
                direction,
                position_amount=position_size,
                stop_price=sl_price,
                reduce_only=True,
            )
            if sl_order:
                logger.info("✅ SL установлен: %.8f", sl_price)
                results["sl_created"] = True
                sl_order_id = (sl_order or {}).get("id")
                sl_side = "buy" if direction in ("SELL", "SHORT") else "sell"
                await audit.log_order(
                    user_id,
                    symbol,
                    sl_side,
                    "plan_sl",
                    position_size,
                    sl_price,
                    sl_order_id,
                    "created",
                    "bitget",
                )
        except Exception as e:
            logger.error("❌ Ошибка установки SL: %s", e)
    else:
        logger.info("ℹ️ SL уже существует")

    # Делим на TP1/TP2 50/50
    tp1_amount = max(position_size * 0.5, 0.0)
    tp2_amount = max(position_size - tp1_amount, 0.0)
    if tp2_amount <= 0:
        tp2_amount = tp1_amount

    # Устанавливаем TP1, если нет
    if not has_tp1:
        try:
            tp1_order = await adapter.place_take_profit_order(
                symbol,
                direction,
                position_amount=tp1_amount,
                take_profit_price=tp1_price,
                reduce_only=True,
                client_tag="tp1_emergency",
            )
            if tp1_order:
                logger.info("✅ TP1 установлен: %.8f (size=%.4f)", tp1_price, tp1_amount)
                results["tp1_created"] = True
                tp1_order_id = (tp1_order or {}).get("id")
                tp1_side = "buy" if direction in ("SELL", "SHORT") else "sell"
                await audit.log_order(
                    user_id,
                    symbol,
                    tp1_side,
                    "plan_tp1",
                    tp1_amount,
                    tp1_price,
                    tp1_order_id,
                    "created",
                    "bitget",
                )
        except Exception as e:
            logger.error("❌ Ошибка установки TP1: %s", e)
    else:
        logger.info("ℹ️ TP1 уже существует")

    # Устанавливаем TP2, если нет
    if not has_tp2:
        try:
            tp2_order = await adapter.place_take_profit_order(
                symbol,
                direction,
                position_amount=tp2_amount,
                take_profit_price=tp2_price,
                reduce_only=True,
                client_tag="tp2_emergency",
            )
            if tp2_order:
                logger.info("✅ TP2 установлен: %.8f (size=%.4f)", tp2_price, tp2_amount)
                results["tp2_created"] = True
                tp2_order_id = (tp2_order or {}).get("id")
                tp2_side = "buy" if direction in ("SELL", "SHORT") else "sell"
                await audit.log_order(
                    user_id,
                    symbol,
                    tp2_side,
                    "plan_tp2",
                    tp2_amount,
                    tp2_price,
                    tp2_order_id,
                    "created",
                    "bitget",
                )
        except Exception as e:
            logger.error("❌ Ошибка установки TP2: %s", e)
    else:
        logger.info("ℹ️ TP2 уже существует")

    return {
        "user_id": user_id,
        "symbol": symbol,
        "entry_price": entry_price,
        "position_size": position_size,
        "tp1_price": tp1_price,
        "tp2_price": tp2_price,
        "sl_price": sl_price,
        **results,
    }


async def main():
    """Главная функция"""
    db = AcceptanceDatabase()

    # Получаем всех пользователей с auto-режимом
    auto_users = await db.get_users_by_mode("auto")
    if not auto_users:
        logger.warning("⚠️ Нет пользователей в auto-режиме")
        return

    logger.info("🚀 Начинаем исправление PUMPUSDT для %d пользователей", len(auto_users))

    for user_id in auto_users:
        try:
            result = await fix_pumpusdt_position(user_id)
            logger.info("📊 Результат для user %s: %s", user_id, result)
        except Exception as e:
            logger.error("❌ Ошибка для user %s: %s", user_id, e, exc_info=True)

    logger.info("✅ Исправление завершено")


if __name__ == "__main__":
    asyncio.run(main())
