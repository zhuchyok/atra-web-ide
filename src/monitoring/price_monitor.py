import time
#!/usr/bin/env python3
"""
Система мониторинга цен и автоматического закрытия позиций по TP1/TP2
"""

import asyncio
import logging
# 🔧 СТРУКТУРИРОВАННОЕ ЛОГИРОВАНИЕ: Используем централизованный логгер
from src.shared.utils.logger import get_logger
import sqlite3
from datetime import datetime, timedelta, timezone
from src.shared.utils.datetime_utils import get_utc_now
from typing import Optional, List, Dict, Any
from src.database.db import Database
from src.database.acceptance import AcceptanceDatabase
from src.execution.exchange_api import get_current_price_robust
from src.execution.trailing_stop import get_trailing_manager

try:
    from src.telegram.handlers import notify_user, notify_all
except ImportError:
    async def notify_user(*args, **kwargs): pass
    async def notify_all(*args, **kwargs): pass

try:
    from src.execution.trade_tracker import get_trade_tracker
except ImportError:
    def get_trade_tracker(): return None

logger = logging.getLogger(__name__)

class PriceMonitorSystem:
    """Система мониторинга цен и автоматического закрытия позиций"""

    def __init__(self):
        # Используем AcceptanceDatabase для всех операций с ретраями
        self.adb = AcceptanceDatabase()
        self.db = Database() # Оставляем для совместимости, но минимизируем использование
        self.running = False
        self.monitor_interval = 30
        self._sent_notifications = set()
        self._sent_user_notifications = set()
        self._last_cache_cleanup = 0
        self._notification_cache_cleanup_interval = 3600

    async def _calculate_trade_fees(self, entry_price: float, exit_price: float, quantity: float,
                                  trade_mode: str = 'futures', user_id: Optional[str] = None,
                                  symbol: Optional[str] = None, exchange_adapter=None) -> float:
        """Рассчитывает реальные комиссии для сделки"""
        try:
            fee_rate = 0.001 if trade_mode == 'spot' else 0.0005
            if user_id and symbol:
                try:
                    from exchange_fee_manager import get_real_fee_rate
                    fee_rate = await get_real_fee_rate(str(user_id), symbol, trade_mode, exchange_adapter)
                except Exception: pass
            
            entry_fee = entry_price * quantity * fee_rate
            exit_fee = exit_price * quantity * fee_rate
            return round(entry_fee + exit_fee, 2)
        except Exception:
            return round((entry_price + exit_price) * quantity * 0.001, 2)

    def calculate_breakeven_sl(self, entry_price: float, side: str, taker_fee: float = 0.001) -> float:
        """Рассчитывает SL в безубыток с учетом комиссий"""
        try:
            if side.upper() == "LONG":
                sl_price = entry_price + (entry_price * taker_fee * 2)
            else:
                sl_price = entry_price - (entry_price * taker_fee * 2)
            return round(sl_price, 4)
        except Exception:
            return entry_price

    def cleanup_notification_cache(self):
        """Очистка кэша уведомлений"""
        current_time = time.time()
        if current_time - self._last_cache_cleanup > self._notification_cache_cleanup_interval:
            self._sent_notifications.clear()
            self._sent_user_notifications.clear()
            self._last_cache_cleanup = current_time
            logger.info("🧹 Кэш уведомлений очищен")

    async def is_position_already_closed(self, symbol: str, entry_time: str, user_id: int = None) -> bool:
        """Проверяет, была ли позиция уже закрыта (через execute_with_retry)"""
        try:
            if user_id:
                query = """
                    SELECT result FROM signals_log
                    WHERE user_id = ? AND symbol = ? AND entry_time = ?
                    ORDER BY datetime(created_at) DESC LIMIT 1
                """
                params = (user_id, symbol, entry_time)
            else:
                query = """
                    SELECT result FROM signals_log
                    WHERE symbol = ? AND entry_time = ?
                    ORDER BY datetime(created_at) DESC LIMIT 1
                """
                params = (symbol, entry_time)

            rows = await self.adb.execute_with_retry(query, params, is_write=False)
            if rows and isinstance(rows[0][0], str):
                result = rows[0][0].upper()
                return result.startswith(("TP2", "SL", "CLOSED"))
            return False
        except Exception as e:
            logger.error("❌ Ошибка проверки статуса позиции: %s", e)
            return False

    async def start_price_monitoring(self):
        """Запуск мониторинга цен"""
        self.running = True
        logger.info("📊 Запуск системы мониторинга цен")
        while self.running:
            try:
                self.cleanup_notification_cache()
                await self.check_all_active_signals()
                await self.check_trailing_and_partial_tp()
                await asyncio.sleep(self.monitor_interval)
            except asyncio.CancelledError:
                self.running = False
                break
            except Exception as e:
                logger.error("❌ Ошибка в мониторинге цен: %s", e)
                await asyncio.sleep(60)

    async def check_all_active_signals(self):
        """Проверка всех активных сигналов и позиций (последние 7 дней)"""
        try:
            cutoff = (get_utc_now() - timedelta(days=7)).isoformat()
            
            # 1. Получаем активные сигналы
            query_signals = """
                SELECT symbol, entry_time, result
                FROM signals_log
                WHERE (UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%' OR UPPER(IFNULL(result, '')) LIKE 'TP1%')
                AND symbol NOT LIKE 'TEST%'
                AND created_at > ?
            """
            active_signals = await self.adb.execute_with_retry(query_signals, (cutoff,), is_write=False)

            # 2. Получаем активные позиции пользователей
            query_positions = """
                SELECT
                    s.user_id, s.symbol, s.entry, s.tp1, s.tp2, s.entry_time, s.result, s.net_profit,
                    s.created_at, s.quality_score, s.quality_meta
                FROM signals_log s
                JOIN (
                    SELECT user_id, symbol, MAX(datetime(created_at)) AS max_created
                    FROM signals_log
                    WHERE (UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%' OR UPPER(IFNULL(result, '')) LIKE 'TP1%')
                    AND symbol NOT LIKE 'TEST%'
                    AND created_at > ?
                    GROUP BY user_id, symbol
                ) last ON last.user_id = s.user_id AND last.symbol = s.symbol AND datetime(s.created_at) = last.max_created
                WHERE (UPPER(IFNULL(s.result, 'OPEN')) LIKE 'OPEN%' OR UPPER(IFNULL(s.result, '')) LIKE 'TP1%')
                AND s.symbol NOT LIKE 'TEST%'
                ORDER BY s.created_at DESC
                LIMIT 200
            """
            active_positions = await self.adb.execute_with_retry(query_positions, (cutoff,), is_write=False)

            if not active_signals and not active_positions:
                return

            logger.debug("🔍 Проверяем %d сигналов и %d позиций", len(active_signals or []), len(active_positions or []))

            for signal in (active_signals or []):
                symbol, entry_time, _ = signal
                await self.check_signal_tp_levels(f"{symbol}|{entry_time}", symbol, entry_time)

            for position in (active_positions or []):
                user_id, symbol, entry, tp1, tp2, entry_time, _, _, created_at, _, _ = position
                await self.check_user_position_tp_levels(user_id, symbol, entry, tp1, tp2, entry_time, created_at)
            
            # 3. Проверка позиций из таблицы active_positions (дополнительная проверка)
            await self.check_active_positions_table_tp_levels()
            
            # 4. Проверка Stop Loss для всех активных позиций
            # 3. Проверка позиций из таблицы active_positions (дополнительная проверка)
            await self.check_active_positions_table_tp_levels()

            await self.check_stop_loss_levels()

        except Exception as e:
            logger.error("❌ Ошибка при проверке сигналов и позиций: %s", e)

    async def check_signal_tp_levels(self, signal_key: str, symbol: str, entry_time: str):
        """Проверка TP для конкретного сигнала"""
        try:
            if not symbol and signal_key:
                symbol = signal_key.split('|')[0] if '|' in signal_key else None
            if not symbol: return

            if await self.is_position_already_closed(symbol, entry_time): return

            query = "SELECT entry, tp1, tp2, result FROM signals_log WHERE symbol = ? AND entry_time = ?"
            rows = await self.adb.execute_with_retry(query, (symbol, entry_time), is_write=False)
            if not rows: return

            entry_price, tp1, tp2, result = rows[0][0], rows[0][1], rows[0][2], rows[0][3]
            if isinstance(result, str) and result.upper().startswith(("TP2", "SL")): return

            current_price = await self.get_current_price_safe(symbol)
            if current_price is None: return

            if isinstance(result, str) and result.upper().startswith("TP1"):
                if current_price >= tp2:
                    await self.close_signal_at_tp2(signal_key, symbol, entry_time, current_price, tp2, entry_price)
            else:
                if current_price >= tp1:
                    await self.close_signal_at_tp1(signal_key, symbol, entry_time, current_price, tp1, entry_price)
                elif current_price >= tp2:
                    await self.close_signal_at_tp2(signal_key, symbol, entry_time, current_price, tp2, entry_price)
        except Exception as e:
            logger.error("❌ Ошибка check_signal_tp_levels %s: %s", signal_key, e)

    async def check_user_position_tp_levels(self, user_id: int, symbol: str, entry: float, tp1: float, tp2: float, entry_time: str, created_at: str):
        """Проверка TP для активной позиции пользователя"""
        try:
            if await self.is_position_already_closed(symbol, entry_time, user_id): return

            current_price = await self.get_current_price_safe(symbol)
            if current_price is None: return

            query = """
                SELECT result FROM signals_log WHERE user_id=? AND symbol=? AND entry_time=?
                ORDER BY datetime(created_at) DESC LIMIT 1
            """
            rows = await self.adb.execute_with_retry(query, (user_id, symbol, entry_time), is_write=False)
            result = rows[0][0] if rows else None
            
            if isinstance(result, str) and result.upper().startswith("TP1"):
                if current_price >= tp2:
                    await self.close_user_position_at_tp2(user_id, symbol, entry_time, current_price, tp2, created_at)
            else:
                if current_price >= tp1:
                    await self.close_user_position_at_tp1(user_id, symbol, entry_time, current_price, tp1, created_at)
                elif current_price >= tp2:
                    await self.close_user_position_at_tp2(user_id, symbol, entry_time, current_price, tp2, created_at)
        except Exception as e:
            logger.error("❌ Ошибка check_user_position_tp_levels %s: %s", symbol, e)

    async def get_current_price_safe(self, symbol: str) -> float:
        """Безопасное получение текущей цены"""
        try:
            return await get_current_price_robust(symbol)
        except Exception as e:
            logger.error("❌ Ошибка получения цены для %s: %s", symbol, e)
            return None

    async def close_signal_at_tp1(self, signal_key: str, symbol: str, entry_time: str, current_price: float, tp1: float, entry_price: float):
        """Автоматическое закрытие 50% позиции при достижении TP1"""
        try:
            check_query = "SELECT result, user_id, direction, stop FROM signals_log WHERE symbol=? AND entry_time=? ORDER BY created_at DESC LIMIT 1"
            rows = await self.adb.execute_with_retry(check_query, (symbol, entry_time), is_write=False)
            if not rows or (isinstance(rows[0][0], str) and rows[0][0].upper().startswith(("TP2", "TP1"))):
                return
            
            user_id, direction, current_sl = rows[0][1], rows[0][2], rows[0][3]
            
            # 1. Обновляем статус
            await self.adb.execute_with_retry("UPDATE active_signals SET status = 'tp1_reached', ts = datetime('now') WHERE signal_key = ?", (signal_key,))

            profit_50pct = (float(current_price) - float(entry_price)) * 0.5
            direction_str = (direction or "LONG").upper()
            breakeven_sl = self.calculate_breakeven_sl(float(entry_price), direction_str)
            
            # 🔧 НОВОЕ: Используем лучший стоп (между текущим и безубытком)
            final_sl = breakeven_sl
            if current_sl:
                if direction_str == "LONG":
                    final_sl = max(float(current_sl), breakeven_sl)
                else:
                    final_sl = min(float(current_sl), breakeven_sl)

            # 3. Обновляем результат и SL
            await self.adb.execute_with_retry("""
                UPDATE signals_log SET result = 'TP1_PARTIAL', exit_time = datetime('now'), net_profit = ?, stop = ?
                WHERE symbol = ? AND entry_time = ?
            """, (profit_50pct, final_sl, symbol, entry_time))
            
            await self.adb.execute_with_retry("UPDATE accepted_signals SET sl_price = ? WHERE symbol = ? AND signal_key LIKE ?", (final_sl, symbol, f"%{entry_time}%"))
            await self.adb.execute_with_retry("UPDATE active_positions SET sl_price = ? WHERE symbol = ? AND entry_time LIKE ?", (final_sl, symbol, f"%{entry_time}%"))

            logger.info("✅ TP1 достигнут: %s @ %s (SL -> %.4f)", symbol, current_price, final_sl)
            await self._update_exchange_sl(user_id, symbol, final_sl, direction_str)
        except Exception as e:
            logger.error("❌ Ошибка close_signal_at_tp1 %s: %s", signal_key, e)

    async def close_signal_at_tp2(self, signal_key: str, symbol: str, entry_time: str, current_price: float, tp2: float, entry_price: float):
        """Автоматическое закрытие 100% позиции при достижении TP2"""
        try:
            check_query = "SELECT result, user_id, direction FROM signals_log WHERE symbol=? AND entry_time=? ORDER BY created_at DESC LIMIT 1"
            rows = await self.adb.execute_with_retry(check_query, (symbol, entry_time), is_write=False)
            if not rows or (isinstance(rows[0][0], str) and rows[0][0].upper().startswith("TP2")):
                return
            
            user_id, direction = rows[0][1], rows[0][2]
            await self.adb.execute_with_retry("UPDATE active_signals SET status = 'tp2_reached', ts = datetime('now') WHERE signal_key = ?", (signal_key,))

            profit_100pct = (float(current_price) - float(entry_price)) * 1.0
            await self.adb.execute_with_retry("""
                UPDATE signals_log SET result = 'TP2_REACHED', exit_time = datetime('now'), net_profit = ?
                WHERE symbol = ? AND entry_time = ?
            """, (profit_100pct, symbol, entry_time))

            logger.info("🎯 TP2 достигнут: %s @ %s", symbol, current_price)
            if user_id and direction:
                try:
                    from ai_integration import AIIntegration
                    ai = AIIntegration()
                    profit_pct = ((current_price - entry_price) / entry_price) * 100.0
                    if direction.upper() == "SHORT": profit_pct = -profit_pct
                    await ai.update_pattern_from_closed_trade(symbol, direction, entry_price, current_price, "tp2", int(user_id), profit_pct)
                except Exception: pass
        except Exception as e:
            logger.error("❌ Ошибка close_signal_at_tp2 %s: %s", signal_key, e)

    async def close_user_position_at_tp1(self, user_id: int, symbol: str, entry_time: str, current_price: float, tp1: float, created_at: str):
        """Закрытие 50% позиции пользователя"""
        try:
            check_query = "SELECT result, entry, qty_added, direction, stop FROM signals_log WHERE user_id=? AND symbol=? AND entry_time=? ORDER BY created_at DESC LIMIT 1"
            rows = await self.adb.execute_with_retry(check_query, (user_id, symbol, entry_time), is_write=False)
            if not rows or (isinstance(rows[0][0], str) and rows[0][0].upper().startswith(("TP2", "TP1"))):
                return
            
            entry_price, qty_added, direction, current_sl = rows[0][1], rows[0][2], rows[0][3], rows[0][4]
            closed_qty = (qty_added or 0) * 0.5
            direction_str = (direction or "LONG").upper()
            # Правильный расчет PnL для LONG и SHORT
            if direction_str == "LONG":
                profit_50pct = (current_price - entry_price) * closed_qty
            else:  # SHORT
                profit_50pct = (entry_price - current_price) * closed_qty
            breakeven_sl = self.calculate_breakeven_sl(float(entry_price), direction_str)
            
            # 🔧 НОВОЕ: Используем лучший стоп
            final_sl = breakeven_sl
            if current_sl:
                if direction_str == "LONG":
                    final_sl = max(float(current_sl), breakeven_sl)
                else:
                    final_sl = min(float(current_sl), breakeven_sl)

            await self.adb.execute_with_retry("""
                UPDATE signals_log SET result = 'TP1_PARTIAL', exit_time = datetime('now'), net_profit = ?, stop = ?
                WHERE user_id = ? AND symbol = ? AND entry_time = ?
            """, (profit_50pct, final_sl, user_id, symbol, entry_time))
            
            await self.adb.execute_with_retry("UPDATE accepted_signals SET sl_price = ? WHERE user_id = ? AND symbol = ? AND signal_key LIKE ?", (final_sl, user_id, symbol, f"%{entry_time}%"))
            await self.adb.execute_with_retry("UPDATE active_positions SET sl_price = ? WHERE user_id = ? AND symbol = ? AND entry_time LIKE ?", (final_sl, user_id, symbol, f"%{entry_time}%"))

            logger.info("✅ User %s TP1: %s @ %s (SL -> %.4f)", user_id, symbol, current_price, final_sl)
            await self._update_exchange_sl(user_id, symbol, final_sl, direction_str)
        except Exception as e:
            logger.error("❌ Ошибка close_user_position_at_tp1 %s: %s", symbol, e)

    async def close_user_position_at_tp2(self, user_id: int, symbol: str, entry_time: str, current_price: float, tp2: float, created_at: str):
        """Закрытие 100% позиции пользователя"""
        try:
            check_query = "SELECT result, entry, qty_added, direction FROM signals_log WHERE user_id=? AND symbol=? AND entry_time=? ORDER BY created_at DESC LIMIT 1"
            rows = await self.adb.execute_with_retry(check_query, (user_id, symbol, entry_time), is_write=False)
            if not rows or (isinstance(rows[0][0], str) and rows[0][0].upper().startswith("TP2")):
                return
            
            entry_price, total_qty, direction = rows[0][1], rows[0][2], rows[0][3]
            direction_str = (direction or "LONG").upper()
            # Правильный расчет PnL для LONG и SHORT
            if direction_str == "LONG":
                profit_100pct = (current_price - entry_price) * (total_qty or 0)
            else:  # SHORT
                profit_100pct = (entry_price - current_price) * (total_qty or 0)

            await self.adb.execute_with_retry("""
                UPDATE signals_log SET result = 'TP2_REACHED', exit_time = datetime('now'), net_profit = ?
                WHERE user_id = ? AND symbol = ? AND entry_time = ?
            """, (profit_100pct, user_id, symbol, entry_time))

            logger.info("🎯 User %s TP2: %s @ %s", user_id, symbol, current_price)
            tracker = get_trade_tracker()
            if tracker:
                # Получаем entry_time как datetime
                from datetime import datetime
                try:
                    entry_time_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                except:
                    entry_time_dt = get_utc_now()
                
                # Рассчитываем position_size_usdt
                position_size_usdt = float(entry_price) * float(total_qty or 0)
                
                await tracker.record_trade(
                    symbol=symbol,
                    direction=direction or 'LONG',
                    entry_price=float(entry_price),
                    exit_price=float(current_price),
                    entry_time=entry_time_dt,
                    exit_time=get_utc_now(),
                    quantity=float(total_qty or 0),
                    position_size_usdt=position_size_usdt,
                    exit_reason='TP2',
                    user_id=str(user_id)
                )
        except Exception as e:
            logger.error("❌ Ошибка close_user_position_at_tp2 %s: %s", symbol, e)

    async def check_active_positions_table_tp_levels(self):
        """Проверка TP уровней для позиций из таблицы active_positions"""
        try:
            cutoff = (get_utc_now() - timedelta(days=7)).isoformat()
            
            # Получаем открытые позиции из active_positions
            query = """
                SELECT 
                    ap.id, ap.user_id, ap.symbol, ap.direction, ap.entry_price, ap.entry_time,
                    ap.signal_key, ap.current_price
                FROM active_positions ap
                WHERE (ap.status = 'open' OR ap.status IS NULL)
                AND ap.created_at > ?
                AND ap.symbol NOT LIKE 'TEST%'
                ORDER BY ap.created_at DESC
                LIMIT 200
            """
            positions = await self.adb.execute_with_retry(query, (cutoff,), is_write=False)
            
            if not positions:
                return
            
            logger.debug("🔍 Проверяем %d позиций из active_positions на TP уровни", len(positions))
            
            for pos in positions:
                pos_id, user_id, symbol, direction, entry_price, entry_time, signal_key, current_price = pos
                
                # Пропускаем если позиция уже закрыта
                if await self.is_position_already_closed(symbol, entry_time, user_id):
                    continue
                
                # Получаем TP1/TP2 из accepted_signals или signals_log
                tp1, tp2 = None, None
                
                # Пробуем получить из accepted_signals через signal_key
                if signal_key:
                    tp_query = "SELECT tp1_price, tp2_price FROM accepted_signals WHERE signal_key = ? LIMIT 1"
                    tp_rows = await self.adb.execute_with_retry(tp_query, (signal_key,), is_write=False)
                    if tp_rows:
                        tp1, tp2 = tp_rows[0][0], tp_rows[0][1]
                
                # Если не нашли, пробуем из signals_log
                if not tp1 or not tp2:
                    sl_query = "SELECT tp1, tp2 FROM signals_log WHERE symbol = ? AND entry_time = ? LIMIT 1"
                    sl_rows = await self.adb.execute_with_retry(sl_query, (symbol, entry_time), is_write=False)
                    if sl_rows:
                        tp1, tp2 = sl_rows[0][0], sl_rows[0][1]
                
                if not tp1 or not tp2:
                    continue
                
                # Получаем текущую цену
                if current_price is None:
                    current_price = await self.get_current_price_safe(symbol)
                    if current_price is None:
                        continue
                
                # Проверяем направление позиции
                direction_str = (direction or "LONG").upper()
                
                # Проверяем достижение TP1/TP2
                if direction_str == "LONG":
                    # Для LONG: цена должна быть >= TP
                    if current_price >= tp2:
                        await self.close_user_position_at_tp2(user_id, symbol, entry_time, current_price, tp2, entry_time)
                    elif current_price >= tp1:
                        await self.close_user_position_at_tp1(user_id, symbol, entry_time, current_price, tp1, entry_time)
                else:  # SHORT
                    # Для SHORT: цена должна быть <= TP
                    if current_price <= tp2:
                        await self.close_user_position_at_tp2(user_id, symbol, entry_time, current_price, tp2, entry_time)
                    elif current_price <= tp1:
                        await self.close_user_position_at_tp1(user_id, symbol, entry_time, current_price, tp1, entry_time)
                        
        except Exception as e:
            logger.error("❌ Ошибка при проверке TP уровней для active_positions: %s", e)

    async def _update_exchange_sl(self, user_id: int, symbol: str, breakeven_sl: float, direction_str: str):
        """Вспомогательный метод обновления SL на бирже"""
        if not user_id: return
        try:
            from src.execution.exchange_adapter import ExchangeAdapter
            keys = await self.adb.get_active_exchange_keys(int(user_id), exchange_name='bitget')
            if keys:
                async with ExchangeAdapter('bitget', keys=keys, trade_mode='futures') as adapter:
                    if adapter.client:
                        positions = await adapter.fetch_positions()
                        for pos in (positions or []):
                            if (pos.get('symbol') or '').replace('/', '').replace(':USDT', '').upper() == symbol.upper():
                                pos_size = float(pos.get('contracts') or pos.get('size') or 0.0)
                                if pos_size > 0:
                                    await adapter.place_stop_loss_order(symbol, "BUY" if direction_str == "SHORT" else "SELL", pos_size, breakeven_sl, True)
                                    logger.info("✅ SL ордер обновлен на бирже для %s", symbol)
                                    break
        except Exception as e:
            logger.warning("⚠️ Ошибка обновления SL на бирже: %s", e)

    async def check_stop_loss_levels(self):
        """Проверка Stop Loss для всех активных позиций"""
        try:
            cutoff = (get_utc_now() - timedelta(days=7)).isoformat()
            
            # Получаем активные позиции с SL из active_positions
            query = """
                SELECT user_id, symbol, entry_time, entry_price, direction, sl_price, created_at
                FROM active_positions
                WHERE status = 'open' 
                AND sl_price IS NOT NULL
                AND created_at > ?
            """
            rows = await self.adb.execute_with_retry(query, (cutoff,), is_write=False)
            
            if not rows:
                return
            
            logger.debug("🔍 Проверяем %d позиций на Stop Loss", len(rows))
            
            for row in rows:
                user_id, symbol, entry_time, entry_price, direction, sl_price, created_at = row
                
                # Проверяем, не закрыта ли уже позиция
                if await self.is_position_already_closed(symbol, entry_time, user_id):
                    continue
                
                # Получаем текущую цену
                current_price = await self.get_current_price_safe(symbol)
                if current_price is None:
                    continue
                
                # Проверяем условие SL
                should_close = False
                direction_upper = (direction or "LONG").upper()
                
                if direction_upper == "LONG" and current_price <= sl_price:
                    should_close = True
                elif direction_upper == "SHORT" and current_price >= sl_price:
                    should_close = True
                
                if should_close:
                    await self.close_position_at_sl(
                        user_id, symbol, entry_time, current_price, sl_price, 
                        entry_price, direction, created_at
                    )
                    
        except Exception as e:
            logger.error("❌ Ошибка check_stop_loss_levels: %s", e)

    async def close_position_at_sl(self, user_id: int, symbol: str, entry_time: str, 
                                    current_price: float, sl_price: float, entry_price: float,
                                    direction: str, created_at: str):
        """Закрытие позиции при срабатывании Stop Loss"""
        try:
            if await self.is_position_already_closed(symbol, entry_time, user_id):
                return
            
            # Получаем данные о позиции (количество)
            check_query = """
                SELECT qty_added, entry, direction 
                FROM signals_log 
                WHERE user_id=? AND symbol=? AND entry_time=? 
                ORDER BY created_at DESC LIMIT 1
            """
            rows = await self.adb.execute_with_retry(check_query, (user_id, symbol, entry_time), is_write=False)
            
            if not rows:
                logger.warning("⚠️ Не найдены данные позиции для %s %s", symbol, entry_time)
                return
            
            qty = rows[0][0] if rows[0][0] else 0
            entry = rows[0][1] if rows[0][1] else entry_price
            direction_from_db = rows[0][2] if rows[0][2] else direction
            direction_str = (direction_from_db or "LONG").upper()
            
            # Рассчитываем PnL
            if direction_str == "LONG":
                pnl = (current_price - entry) * qty if qty > 0 else (current_price - entry)
            else:
                pnl = (entry - current_price) * qty if qty > 0 else (entry - current_price)
            
            # Рассчитываем комиссии
            fees = await self._calculate_trade_fees(entry, current_price, qty if qty > 0 else 1.0, 'futures', user_id, symbol)
            net_pnl = pnl - fees
            
            # Рассчитываем PnL в процентах
            position_size = entry * qty if qty > 0 else entry
            pnl_percent = (net_pnl / position_size * 100) if position_size > 0 else 0
            
            # Обновляем статус позиции в active_positions
            await self.adb.execute_with_retry("""
                UPDATE active_positions 
                SET status = 'closed', 
                    current_price = ?, 
                    pnl_usd = ?, 
                    pnl_percent = ?, 
                    updated_at = datetime('now')
                WHERE user_id = ? AND symbol = ? AND entry_time LIKE ?
            """, (current_price, net_pnl, pnl_percent, user_id, symbol, f"%{entry_time}%"))
            
            # Сохраняем в trades таблицу
            try:
                from src.execution.trade_tracker import get_trade_tracker
                from datetime import datetime
                tracker = get_trade_tracker()
                if tracker:
                    exit_time = get_utc_now()
                    # Преобразуем entry_time из строки в datetime
                    try:
                        entry_time_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                    except:
                        entry_time_dt = exit_time
                    
                    # Рассчитываем position_size_usdt
                    position_size_usdt = float(entry) * float(qty) if qty > 0 else float(entry)
                    
                    await tracker.record_trade(
                        symbol=symbol,
                        direction=direction_str,
                        entry_price=float(entry),
                        exit_price=float(current_price),
                        entry_time=entry_time_dt,
                        exit_time=exit_time,
                        quantity=float(qty) if qty > 0 else 1.0,
                        position_size_usdt=position_size_usdt,
                        exit_reason='SL',
                        user_id=str(user_id)
                    )
            except Exception as e:
                logger.warning("⚠️ Ошибка сохранения в trades: %s", e)
            
            # Обновляем signals_log
            await self.adb.execute_with_retry("""
                UPDATE signals_log 
                SET result = 'SL_HIT', 
                    exit_time = datetime('now'), 
                    net_profit = ?
                WHERE user_id = ? AND symbol = ? AND entry_time = ?
            """, (net_pnl, user_id, symbol, entry_time))
            
            # Обновляем active_signals
            await self.adb.execute_with_retry("""
                UPDATE active_signals 
                SET status = 'closed', ts = datetime('now') 
                WHERE signal_key LIKE ?
            """, (f"%{symbol}|{entry_time}%",))
            
            # Уведомляем пользователя
            try:
                await notify_user(user_id, f"🛑 Stop Loss сработал: {symbol} @ {current_price:.8f}, PnL: {net_pnl:.2f} USDT ({pnl_percent:.2f}%)")
            except Exception:
                pass
            
            logger.info("🛑 SL сработал: %s @ %s (Entry: %s, SL: %s), PnL: %.2f USDT (%.2f%%)", 
                       symbol, current_price, entry, sl_price, net_pnl, pnl_percent)
            
        except Exception as e:
            logger.error("❌ Ошибка close_position_at_sl %s: %s", symbol, e)

    async def check_trailing_and_partial_tp(self):
        """Проверка и обновление trailing stop для активных позиций"""
        try:
            # Получаем все активные позиции из БД
            cutoff = (get_utc_now() - timedelta(days=7)).isoformat()
            query = """
                SELECT user_id, symbol, entry, tp1, tp2, stop, entry_time, direction
                FROM signals_log
                WHERE (UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%' OR UPPER(IFNULL(result, '')) LIKE 'TP1%')
                AND created_at > ?
            """
            active_trades = await self.adb.execute_with_retry(query, (cutoff,), is_write=False)
            
            if not active_trades:
                return

            trailing_manager = get_trailing_manager()

            for trade in active_trades:
                user_id, symbol, entry, tp1, tp2, current_sl, entry_time, direction = trade
                
                # 1. Получаем текущую цену
                current_price = await self.get_current_price_safe(symbol)
                if current_price is None: continue

                # 2. Инициализируем позицию в трейлинг-менеджере, если ее там нет
                pos_key = f"{user_id}_{symbol}"
                if pos_key not in trailing_manager.positions_tracking:
                    trailing_manager.setup_position(
                        symbol=pos_key,
                        entry_price=float(entry),
                        initial_sl=float(current_sl) if current_sl else float(entry) * 0.95,
                        side=direction.upper() if direction else "LONG",
                        tp1_price=float(tp1) if tp1 else None,
                        tp2_price=float(tp2) if tp2 else None  # 🆕 Передаем TP2
                    )

                # 3. Обновляем трейлинг
                # Для простоты передаем None вместо ATR (менеджер сам рассчитает или использует фикс)
                trail_result = trailing_manager.update_trailing_stop(
                    symbol=pos_key,
                    current_price=current_price,
                    regime="NEUTRAL"
                )

                if trail_result and trail_result.get('stop_moved'):
                    new_sl = trail_result['new_stop']
                    logger.info("🎯 [TRAILING] %s: Подтягиваем SL -> %.4f (Reason: %s)", 
                                symbol, new_sl, trail_result.get('reason'))
                    
                    # 4. Обновляем в БД
                    await self.adb.execute_with_retry(
                        "UPDATE signals_log SET stop = ? WHERE user_id = ? AND symbol = ? AND entry_time = ?",
                        (new_sl, user_id, symbol, entry_time)
                    )
                    await self.adb.execute_with_retry(
                        "UPDATE active_positions SET sl_price = ? WHERE accepted_by = ? AND symbol = ?",
                        (new_sl, str(user_id), symbol)
                    )

                    # 5. Обновляем на бирже
                    await self._update_exchange_sl(user_id, symbol, new_sl, (direction or "LONG").upper())

        except Exception as e:
            logger.error("❌ Ошибка в check_trailing_and_partial_tp: %s", e)

    def stop(self):
        self.running = False
        logger.info("🛑 Система мониторинга цен остановлена")

_price_monitor = None
def get_price_monitor():
    global _price_monitor
    if _price_monitor is None:
        _price_monitor = PriceMonitorSystem()
    return _price_monitor

price_monitor = get_price_monitor()

async def run_price_monitoring():
    await get_price_monitor().start_price_monitoring()
