#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для исправления SL ордеров на открытых позициях
- Проверяет все открытые позиции
- Отменяет старые SL ордера (если нужно)
- Выставляет новые SL ордера с правильными параметрами
"""

import asyncio
import logging
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from acceptance_database import AcceptanceDatabase
from src.execution.exchange_adapter import ExchangeAdapter
from order_audit_log import get_audit_log
from trailing_stop_manager import get_trailing_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fix_sl_for_position(user_id: int, symbol: str, entry_price: float, 
                              direction: str, tp1_price: float = None, 
                              current_sl: float = None):
    """Исправляет SL ордер для одной позиции"""
    try:
        adb = AcceptanceDatabase()
        audit = get_audit_log()
        
        # Получаем ключи пользователя
        keys = await adb.get_active_exchange_keys(user_id, exchange_name='bitget')
        if not keys:
            logger.warning("⚠️ [%s] Ключи Bitget не найдены для user %s", symbol, user_id)
            return False
        
        adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode='futures')
        if not adapter.client:
            logger.warning("⚠️ [%s] Не удалось создать адаптер для user %s", symbol, user_id)
            return False
        
        # Получаем текущие позиции на бирже
        positions = await adapter.fetch_positions()
        position_size = 0.0
        pos_side = None
        
        for pos in positions or []:
            pos_symbol = (pos.get('symbol') or '').replace('/', '').replace(':USDT', '').upper()
            if pos_symbol == symbol.upper():
                pos_size = float(pos.get('contracts') or pos.get('size') or 0.0)
                if pos_size > 0:
                    position_size = pos_size
                    pos_side = (pos.get('side') or '').lower()
                    break
        
        if position_size <= 0:
            logger.warning("⚠️ [%s] Позиция не найдена на бирже для user %s", symbol, user_id)
            return False
        
        logger.info("📊 [%s] Найдена позиция: size=%.4f, side=%s", symbol, position_size, pos_side)
        
        # Получаем текущие план-ордера
        plan_orders = await adapter.fetch_plan_orders()
        logger.info("🔍 [%s] Найдено план-ордеров: %d", symbol, len(plan_orders or []))
        
        # Ищем SL ордера
        sl_orders = []
        for order in plan_orders or []:
            order_symbol = str(order.get('symbol') or order.get('symbolId') or '').upper()
            order_symbol_clean = order_symbol.replace('/', '').replace(':USDT', '').replace('_UMCBL', '').upper()
            client_oid = str(order.get('clientOid') or order.get('client_oid') or '').lower()
            plan_type = str(order.get('planType') or order.get('plan_type') or '').lower()
            
            if (order_symbol_clean == symbol.upper() and 
                ('sl' in client_oid or plan_type == 'pos_loss')):
                order_id = order.get('orderId') or order.get('order_id')
                if order_id:
                    sl_orders.append({
                        'order_id': order_id,
                        'symbol': order_symbol,
                        'client_oid': client_oid,
                        'plan_type': plan_type
                    })
        
        logger.info("🛡️ [%s] Найдено SL ордеров: %d", symbol, len(sl_orders))
        
        # Определяем новый SL
        direction_norm = (direction or "").upper()
        is_long = direction_norm in ("BUY", "LONG")
        side_str = "LONG" if is_long else "SHORT"
        
        # 🔧 НОВОЕ: Используем TrailingStopManager для пересчета SL с правильной логикой
        trailing_manager = get_trailing_manager()
        
        # Получаем текущую цену
        try:
            from exchange_base import get_ohlc_with_fallback
            ohlc = await get_ohlc_with_fallback(symbol, "1m", limit=1)
            current_price = ohlc[0]['close'] if ohlc and len(ohlc) > 0 else None
        except Exception as e:
            logger.warning("⚠️ [%s] Не удалось получить текущую цену: %s", symbol, e)
            current_price = None
        
        # Инициализируем позицию в trailing manager
        initial_sl = current_sl if current_sl else (entry_price * 0.98 if is_long else entry_price * 1.02)
        trailing_manager.setup_position(
            symbol=symbol,
            entry_price=float(entry_price),
            initial_sl=float(initial_sl),
            side=side_str,
            tp1_price=float(tp1_price) if tp1_price else None
        )
        
        # Если есть текущая цена, пересчитываем SL с правильной логикой
        if current_price:
            # Получаем ATR для расчета
            atr_value = None
            try:
                if ohlc and len(ohlc) >= 14:
                    highs = [c['high'] for c in ohlc[-14:]]
                    lows = [c['low'] for c in ohlc[-14:]]
                    closes = [c['close'] for c in ohlc[-14:]]
                    
                    tr_values = []
                    for i in range(1, len(highs)):
                        tr1 = highs[i] - lows[i]
                        tr2 = abs(highs[i] - closes[i-1])
                        tr3 = abs(lows[i] - closes[i-1])
                        tr_values.append(max(tr1, tr2, tr3))
                    
                    if tr_values:
                        atr_value = sum(tr_values) / len(tr_values)
            except Exception as e:
                logger.debug("⚠️ [%s] Не удалось рассчитать ATR: %s", symbol, e)
            
            # Пересчитываем SL с правильной логикой
            trail_result = trailing_manager.update_trailing_stop(
                symbol=symbol,
                current_price=current_price,
                atr_value=atr_value,
                regime="NEUTRAL"
            )
            
            if trail_result and trail_result.get('stop_moved'):
                new_sl = trail_result['new_stop']
                logger.info("🎯 [%s] SL пересчитан с правильной логикой: %.8f → %.8f (%s)", 
                           symbol, current_sl or initial_sl, new_sl, trail_result.get('reason', 'trailing'))
            else:
                # Если trailing не активирован, используем текущий SL или базовый расчет
                if current_sl:
                    new_sl = current_sl
                else:
                    # Базовый расчет
                    if is_long:
                        new_sl = entry_price * 0.98
                    else:
                        new_sl = entry_price * 1.02
                    logger.info("📊 [%s] Используем базовый SL: %.8f (2%% от входа)", symbol, new_sl)
        else:
            # Если не удалось получить цену, используем текущий SL или базовый расчет
            if current_sl:
                new_sl = current_sl
            else:
                if is_long:
                    new_sl = entry_price * 0.98
                else:
                    new_sl = entry_price * 1.02
                logger.info("📊 [%s] Используем базовый SL: %.8f (2%% от входа)", symbol, new_sl)
        
        # Отменяем старые SL ордера
        cancelled_count = 0
        for sl_order in sl_orders:
            try:
                cancelled = await adapter.cancel_order(str(sl_order['order_id']), symbol, is_plan_order=True)
                if cancelled:
                    logger.info("✅ [%s] Старый SL ордер отменен (order_id=%s)", symbol, sl_order['order_id'])
                    cancelled_count += 1
                else:
                    logger.warning("⚠️ [%s] Не удалось отменить SL ордер (order_id=%s)", symbol, sl_order['order_id'])
            except Exception as cancel_err:
                logger.warning("⚠️ [%s] Ошибка отмены SL ордера %s: %s", symbol, sl_order['order_id'], cancel_err)
        
        if cancelled_count == 0 and len(sl_orders) > 0:
            logger.warning("⚠️ [%s] Не удалось отменить ни одного SL ордера", symbol)
        
        # Выставляем новый SL ордер
        direction_for_sl = direction_norm if direction_norm in ('BUY', 'SELL') else ('BUY' if is_long else 'SELL')
        
        new_sl_order = await adapter.place_stop_loss_order(
            symbol,
            direction_for_sl,
            position_amount=position_size,
            stop_price=new_sl,
            reduce_only=True
        )
        
        if new_sl_order:
            logger.info("✅ [%s] Новый SL ордер выставлен: %.8f (size=%.4f)", symbol, new_sl, position_size)
            sl_order_id = (new_sl_order or {}).get('id')
            sl_side = "buy" if direction_for_sl == 'SELL' else "sell"
            await audit.log_order(
                user_id, symbol, sl_side, "plan_sl_fixed",
                position_size, new_sl, sl_order_id, "updated", "bitget"
            )
            return True
        else:
            logger.error("❌ [%s] Не удалось выставить новый SL ордер", symbol)
            return False
            
    except Exception as e:
        logger.error("❌ [%s] Ошибка исправления SL: %s", symbol, e, exc_info=True)
        return False


async def fix_all_open_positions_sl():
    """Исправляет SL ордера для всех открытых позиций"""
    try:
        adb = AcceptanceDatabase()
        
        # Получаем всех пользователей с активными позициями
        # Сначала получаем список всех пользователей из БД
        all_positions = []
        try:
            import sqlite3
            db_path = adb.db_path
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT accepted_by FROM active_positions WHERE status = 'open'
                """)
                user_ids = [row[0] for row in cursor.fetchall()]
            
            # Для каждого пользователя получаем его позиции
            for user_id in user_ids:
                user_positions = await adb.get_active_positions_by_user(str(user_id))
                # Добавляем user_id в каждую позицию
                for pos in user_positions:
                    pos['user_id'] = user_id
                all_positions.extend(user_positions)
        except Exception as e:
            logger.error("❌ Ошибка получения позиций: %s", e)
            return
        
        if not all_positions:
            logger.info("ℹ️ Открытых позиций не найдено")
            return
        
        logger.info("📊 Найдено открытых позиций: %d", len(all_positions))
        
        fixed_count = 0
        failed_count = 0
        
        for position in all_positions:
            user_id = position.get('user_id')
            symbol = position.get('symbol')
            entry_price = position.get('entry_price')
            direction = position.get('direction')
            # Получаем TP1 и SL из accepted_signals или signals_log
            tp1_price = None
            sl_price = None
            try:
                import sqlite3
                db_path = adb.db_path
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    # Ищем в accepted_signals
                    cursor.execute("""
                        SELECT tp1_price, sl_price FROM accepted_signals
                        WHERE user_id = ? AND symbol = ? AND status = 'open'
                        ORDER BY created_at DESC LIMIT 1
                    """, (str(user_id), symbol))
                    row = cursor.fetchone()
                    if row:
                        tp1_price = row['tp1_price']
                        sl_price = row['sl_price']
            except Exception as e:
                logger.debug("⚠️ Не удалось получить TP1/SL из БД: %s", e)
            
            if not all([user_id, symbol, entry_price, direction]):
                logger.warning("⚠️ Пропущена позиция с неполными данными: %s", position)
                continue
            
            logger.info("🔧 Обрабатываю позицию: %s (user=%s, entry=%.8f, direction=%s)", 
                       symbol, user_id, entry_price, direction)
            
            success = await fix_sl_for_position(
                int(user_id),
                symbol,
                float(entry_price),
                direction,
                float(tp1_price) if tp1_price else None,
                float(sl_price) if sl_price else None
            )
            
            if success:
                fixed_count += 1
            else:
                failed_count += 1
            
            # Небольшая задержка между позициями
            await asyncio.sleep(1)
        
        logger.info("✅ Обработка завершена: исправлено=%d, ошибок=%d", fixed_count, failed_count)
        
    except Exception as e:
        logger.error("❌ Критическая ошибка: %s", e, exc_info=True)


if __name__ == "__main__":
    asyncio.run(fix_all_open_positions_sl())

