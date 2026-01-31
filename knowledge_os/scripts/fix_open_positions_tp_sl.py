#!/usr/bin/env python3
import asyncio
import logging
from typing import Optional, Dict, Any, List, Set

from acceptance_database import AcceptanceDatabase
from src.execution.exchange_adapter import ExchangeAdapter
from order_audit_log import get_audit_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_open_positions")


async def place_missing_tp_sl_for_user(user_id: int) -> None:
    db = AcceptanceDatabase()
    audit = get_audit_log()

    # Ключи биржи
    keys = await db.get_active_exchange_keys(user_id, exchange_name='bitget')
    if not keys:
        logger.warning("user %s: нет активных ключей bitget — пропуск", user_id)
        return

    adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode='futures')
    if not adapter.client:
        logger.error("user %s: ccxt клиент не инициализирован", user_id)
        return

    # Позиции из БД для данного пользователя
    try:
        db_positions = await db.get_active_positions_by_user(str(user_id))
        positions = [
            (p.get('symbol'), p.get('direction'), p.get('entry_price'))
            for p in db_positions
        ]
    except Exception:
        positions = []

    if not positions:
        logger.info("user %s: активных позиций нет", user_id)
        return

    # Ордера на бирже (для проверки существующих TP/SL)
    try:
        open_orders = await adapter.client.fetch_open_orders()
    except Exception:
        open_orders = []

    def has_any_tp_sl_for_symbol(sym: str) -> bool:
        for o in open_orders or []:
            if (o.get('symbol', '').replace('/', '').upper() == sym.upper() and
                ((o.get('type') or '').lower() in ('limit', 'takeprofit', 'stop') or 'plan' in str(o.get('info') or '').lower())):
                return True
        return False

    # Получаем фактические размеры позиций с биржи
    exch_positions = []
    try:
        exch_positions = await adapter.fetch_positions()
    except Exception:
        pass

    for row in positions:
        symbol, direction, entry_price = row
        symbol = (symbol or '').upper()
        direction = (direction or '').upper()
        entry_price = float(entry_price or 0.0)
        if not symbol or entry_price <= 0:
            continue

        # Если уже есть TP/SL ордера — пропуск
        if has_any_tp_sl_for_symbol(symbol):
            logger.info("user %s: %s — TP/SL уже существуют, пропуск", user_id, symbol)
            continue

        # Найдём размер позиции
        position_size = 0.0
        for ep in exch_positions or []:
            psym = (ep.get('symbol') or '').replace('/', '').replace(':USDT', '')
            if psym.upper() == symbol.upper():
                position_size = float(ep.get('contracts') or ep.get('size') or 0.0)
                if position_size > 0:
                    break
        if position_size <= 0:
            logger.info("user %s: %s — позиция отсутствует на бирже, пропуск", user_id, symbol)
            continue

        # Fallback уровни
        if direction in ("BUY", "LONG"):
            sl_price = entry_price * 0.984
            tp1_price = entry_price * 1.018
            tp2_price = entry_price * 1.036
        else:
            sl_price = entry_price * 1.016
            tp1_price = entry_price * 0.982
            tp2_price = entry_price * 0.964

        # Ставим SL
        try:
            sl_order = await adapter.place_stop_loss_order(symbol, direction, position_amount=position_size, stop_price=sl_price, reduce_only=True)
            logger.info("user %s: %s SL выставлен по цене %.8f (size=%.6f)", user_id, symbol, sl_price, position_size)
            try:
                sl_order_id = (sl_order or {}).get('id')
                sl_side = "buy" if direction in ("SELL","SHORT") else "sell"
                await audit.log_order(int(user_id), symbol, sl_side, "plan_sl", float(position_size), float(sl_price), sl_order_id, "created", "bitget")
            except Exception:
                pass
        except Exception as e:
            logger.error("user %s: %s SL ошибка: %s", user_id, symbol, e)

        # Делим на TP1/TP2 50/50
        tp1_amount = max(position_size * 0.5, 0.0)
        tp2_amount = max(position_size - tp1_amount, 0.0)
        if tp2_amount <= 0:
            tp2_amount = tp1_amount

        # Ставим TP1/TP2
        try:
            tp1_order = await adapter.place_take_profit_order(symbol, direction, position_amount=tp1_amount, take_profit_price=tp1_price, reduce_only=True, client_tag="tp1_fix")
            logger.info("user %s: %s TP1 выставлен по цене %.8f (size=%.6f)", user_id, symbol, tp1_price, tp1_amount)
            try:
                tp1_order_id = (tp1_order or {}).get('id')
                tp1_side = "buy" if direction in ("SELL","SHORT") else "sell"
                await audit.log_order(int(user_id), symbol, tp1_side, "plan_tp1", float(tp1_amount), float(tp1_price), tp1_order_id, "created", "bitget")
            except Exception:
                pass
        except Exception as e:
            logger.error("user %s: %s TP1 ошибка: %s", user_id, symbol, e)

        try:
            tp2_order = await adapter.place_take_profit_order(symbol, direction, position_amount=tp2_amount, take_profit_price=tp2_price, reduce_only=True, client_tag="tp2_fix")
            logger.info("user %s: %s TP2 выставлен по цене %.8f (size=%.6f)", user_id, symbol, tp2_price, tp2_amount)
            try:
                tp2_order_id = (tp2_order or {}).get('id')
                tp2_side = "buy" if direction in ("SELL","SHORT") else "sell"
                await audit.log_order(int(user_id), symbol, tp2_side, "plan_tp2", float(tp2_amount), float(tp2_price), tp2_order_id, "created", "bitget")
            except Exception:
                pass
        except Exception as e:
            logger.error("user %s: %s TP2 ошибка: %s", user_id, symbol, e)


async def main():
    import sqlite3
    db = AcceptanceDatabase()
    
    # Получаем список пользователей с активными позициями
    try:
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT accepted_by FROM active_positions WHERE UPPER(IFNULL(status,'open')) LIKE 'OPEN%' AND accepted_by IS NOT NULL"
            )
            rows = cursor.fetchall()
    except Exception as e:
        logger.error("Ошибка получения пользователей: %s", e)
        return
    
    user_ids: Set[int] = set()
    for r in rows or []:
        try:
            uid = int((r[0] or "").strip())
            user_ids.add(uid)
        except Exception:
            continue

    if not user_ids:
        logger.info("Активных позиций нет")
        return

    for uid in user_ids:
        try:
            await place_missing_tp_sl_for_user(uid)
        except Exception as e:
            logger.error("Ошибка обработки пользователя %s: %s", uid, e)


if __name__ == "__main__":
    asyncio.run(main())
