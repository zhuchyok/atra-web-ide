#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ SELF-HEALING SYSTEM (Autonomous Resilience)
Monitors system health and automatically fixes common issues:
1. Database locks/corruption.
2. Stale processes.
3. API connection failures.
4. Memory leaks (restart triggers).
"""

import logging
import asyncio
import os
import time
import sqlite3
import shutil
import glob
import psutil
from src.telegram.handlers import notify_user
from config import TELEGRAM_CHAT_IDS

# 🔧 СТРУКТУРИРОВАННОЕ ЛОГИРОВАНИЕ: Используем централизованный логгер
from src.shared.utils.logger import get_logger
logger = get_logger(__name__)

class SelfHealingManager:
    """
    Guardian of system stability.
    """
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.start_time = time.time()

    async def _send_admin_alert(self, message: str):
        """Sends alert to admin via Telegram"""
        try:
            if TELEGRAM_CHAT_IDS:
                # Превращаем строку ID в список если нужно
                chat_ids = TELEGRAM_CHAT_IDS.split(',') if isinstance(TELEGRAM_CHAT_IDS, str) else [TELEGRAM_CHAT_IDS]
                for chat_id in chat_ids:
                    await notify_user(chat_id.strip(), f"🏥 [SELF-HEALING] {message}")
        except Exception as e:
            logger.error("Failed to send self-healing alert: %s", e)

    async def monitor_health(self):
        """Continuous health check loop"""
        while True:
            try:
                # 1. Check Memory Usage
                mem_mb = self.process.memory_info().rss / (1024 * 1024)
                if mem_mb > 1500:  # Threshold 1.5GB
                    msg = f"🚨 High memory usage: {mem_mb:.2f} MB. Service restart recommended."
                    logger.warning(msg)
                    await self._send_admin_alert(msg)

                # 🆕 1.1 Check Total System CPU
                cpu_usage = psutil.cpu_percent(interval=1)
                if cpu_usage > 90:
                    msg = f"🔥 [VDS] High CPU Load: {cpu_usage}%"
                    logger.warning(msg)
                    await self._send_admin_alert(msg)

                # 🆕 1.2 Check System Memory
                system_mem = psutil.virtual_memory()
                if system_mem.percent > 90:
                    msg = f"🧨 [VDS] Low System Memory: {system_mem.percent}% used ({system_mem.available // (1024*1024)} MB free)"
                    logger.warning(msg)
                    await self._send_admin_alert(msg)
                    
                    # Критическая нехватка памяти - запускаем очистку
                    if system_mem.available < 100 * 1024 * 1024:  # Меньше 100MB
                        await self._emergency_memory_cleanup()

                # 2. Check Database Integrity
                await self._check_db_health("trading.db")

                # 3. Check for stale locks
                if os.path.exists("atra.lock"):
                    lock_age = time.time() - os.path.getmtime("atra.lock")
                    if lock_age > 3600:  # Lock older than 1 hour
                        logger.warning("🧹 Found stale lock file (1h+). Removing.")
                        os.remove("atra.lock")

                # 4. Check Disk Space
                await self._check_disk_space()

                # 🆕 5. Sync Positions with Exchange (To avoid stuck trades)
                await self._sync_positions_with_exchange()

            except Exception as e:
                logger.error("❌ Error in Self-Healing monitor: %s", e)

            await asyncio.sleep(300)  # Check every 5 minutes

    async def _sync_positions_with_exchange(self):
        """
        Periodically verifies that DB active_positions match actual exchange positions.
        Fixes discrepancies by adding missing or closing non-existent positions in DB.
        """
        logger.info("🔍 [SELF-HEALING] Starting Position Sync check...")
        try:
            from src.database.acceptance import AcceptanceDatabase
            from src.execution.exchange_adapter import ExchangeAdapter

            db = AcceptanceDatabase(db_path="trading.db")

            # Find all users with exchange keys
            query_users = "SELECT DISTINCT user_id FROM user_exchange_keys WHERE is_active = 1"
            user_rows = await db.execute_with_retry(query_users, (), is_write=False)
            user_ids = [row[0] for row in user_rows] if user_rows else []

            for user_id in user_ids:
                keys = await db.get_active_exchange_keys(user_id, 'bitget')
                if not keys:
                    continue

                async with ExchangeAdapter('bitget', keys=keys, trade_mode='futures') as adapter:
                    # Real positions
                    try:
                        exchange_positions = await adapter.fetch_positions()
                        active_ex_pos = [
                            p for p in exchange_positions
                            if float(p.get('contracts', 0) or p.get('size', 0) or 0) > 0
                        ]
                    except Exception as e:
                        logger.debug("Could not fetch positions for %s: %s", user_id, e)
                        continue

                    # DB positions
                    db_positions = await db.get_active_positions_by_user(user_id)
                    db_symbols = {
                        p.get('symbol').upper(): p for p in db_positions
                    } if db_positions else {}

                # 1. Exchange -> DB (Add missing)
                for ex_p in active_ex_pos:
                    symbol = ex_p['symbol'].replace('/USDT:USDT', 'USDT').replace(':', '').replace('/', '').upper()
                    if symbol not in db_symbols:
                        logger.warning("⚠️ [SYNC] Found position on Bitget NOT in DB: %s. Syncing.", symbol)
                        
                        entry_price = float(ex_p['entryPrice'] or ex_p.get('avgCost') or 0)
                        direction = ex_p['side'].upper()
                        position_size = float(ex_p.get('contracts', 0) or ex_p.get('size', 0) or 0)
                        
                        # Создаем позицию в БД
                        signal_key = f"AUTO_SYNC_{symbol}_{int(time.time())}"
                        await db.create_active_position(
                            symbol=symbol,
                            direction=direction,
                            entry_price=entry_price,
                            user_id=user_id,
                            chat_id=0, message_id=0,
                            signal_key=signal_key
                        )
                        
                        # 🛡️ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Устанавливаем SL/TP для синхронизированных позиций
                        # Проверяем, есть ли уже план-ордера на бирже
                        try:
                            open_orders = await adapter.client.fetch_open_orders(symbol=symbol) if adapter.client else []
                            has_sl_tp = any(
                                order.get('type', '').lower() in ('stop', 'tpsl', 'plan') or
                                'plan' in str(order.get('info', {})).lower()
                                for order in open_orders
                            )
                            
                            if not has_sl_tp and position_size > 0:
                                # Устанавливаем SL/TP если их нет
                                logger.info("🛡️ [SYNC] Устанавливаем SL/TP для синхронизированной позиции %s", symbol)
                                
                                # Получаем TP/SL уровни из БД или используем стандартные
                                tp1, tp2, sl_price = await self._get_tp_sl_levels(db, symbol, entry_price, direction)
                                
                                if tp1 and tp2 and sl_price:
                                    # Устанавливаем SL
                                    try:
                                        sl_order = await adapter.place_stop_loss_order(
                                            symbol=symbol,
                                            direction=direction,
                                            position_amount=position_size,
                                            stop_price=sl_price,
                                            reduce_only=True
                                        )
                                        if sl_order:
                                            logger.info("✅ [SYNC] SL установлен для %s: %.8f", symbol, sl_price)
                                        else:
                                            logger.warning("⚠️ [SYNC] Не удалось установить SL для %s", symbol)
                                    except Exception as sl_e:
                                        logger.error("❌ [SYNC] Ошибка установки SL для %s: %s", symbol, sl_e)
                                    
                                    # Устанавливаем TP1 (50% позиции)
                                    try:
                                        tp1_amount = position_size * 0.5
                                        tp1_order = await adapter.place_take_profit_order(
                                            symbol=symbol,
                                            direction=direction,
                                            position_amount=tp1_amount,
                                            take_profit_price=tp1,
                                            client_tag="tp1"
                                        )
                                        if tp1_order:
                                            logger.info("✅ [SYNC] TP1 установлен для %s: %.8f", symbol, tp1)
                                        else:
                                            logger.warning("⚠️ [SYNC] Не удалось установить TP1 для %s", symbol)
                                    except Exception as tp1_e:
                                        logger.error("❌ [SYNC] Ошибка установки TP1 для %s: %s", symbol, tp1_e)
                                else:
                                    logger.warning("⚠️ [SYNC] Не удалось получить TP/SL уровни для %s, используются стандартные", symbol)
                            else:
                                logger.debug("✅ [SYNC] SL/TP уже установлены для %s", symbol)
                        except Exception as e:
                            logger.error("❌ [SYNC] Ошибка проверки/установки SL/TP для %s: %s", symbol, e)

                # 2. DB -> Exchange (Close orphans)
                ex_symbols = {
                    p['symbol'].replace('/USDT:USDT', 'USDT').replace(':', '').replace('/', '').upper()
                    for p in active_ex_pos
                }
                for db_sym in db_symbols:
                    if db_sym not in ex_symbols:
                        logger.warning("⚠️ [SYNC] DB thinks %s is open, but it's not on Bitget. Closing in DB.", db_sym)
                        await db.close_active_position_by_symbol(user_id, db_sym)

        except Exception as e:
            logger.error("❌ Error in position sync: %s", e)

    async def _check_disk_space(self):
        """Monitors disk space and cleans up if low"""
        _, _, free = shutil.disk_usage("/")
        free_gb = free // (2**30)

        if free_gb < 2:  # Less than 2GB free
            msg = f"🚨 Low disk space: {free_gb}GB free. Triggering aggressive auto-cleanup."
            logger.warning(msg)
            await self._send_admin_alert(msg)
            
            # Агрессивная очистка для критических ситуаций
            await self._aggressive_disk_cleanup()

    def _cleanup_logs(self):
        """Removes old logs and temporary files"""
        # 1. Clear old logs
        log_files = glob.glob("logs/*.log.*") + glob.glob("*.log.*")
        for f in log_files:
            try:
                os.remove(f)
                logger.info("🧹 Removed old log file: %s", f)
            except Exception:
                pass

        # 2. Clear old reports
        report_files = glob.glob("ai_reports/auto_fix_*.md")
        if len(report_files) > 50:
            for f in report_files[:-10]: # Keep last 10
                try:
                    os.remove(f)
                except Exception:
                    pass

    async def _aggressive_disk_cleanup(self):
        """Агрессивная очистка диска для критических ситуаций"""
        logger.warning("🔥 [SELF-HEALING] Запуск агрессивной очистки диска...")
        base_path = "/root/atra"
        
        try:
            # 1. Вызываем AutonomousJanitor для глубокой очистки
            try:
                from src.infrastructure.self_healing.janitor import AutonomousJanitor
                janitor = AutonomousJanitor(base_path=base_path)
                janitor.perform_cleanup()
                logger.info("✅ [SELF-HEALING] AutonomousJanitor выполнен")
            except Exception as e:
                logger.warning("⚠️ [SELF-HEALING] Не удалось вызвать Janitor: %s", e)
            
            # 2. Агрессивная очистка логов (все кроме последних 3 дней)
            logger.info("🧹 [SELF-HEALING] Очистка старых логов...")
            from datetime import datetime, timedelta
            from src.shared.utils.datetime_utils import get_utc_now
            cutoff_time = get_utc_now() - timedelta(days=3)
            cutoff_timestamp = cutoff_time.timestamp()
            
            cleaned_logs = 0
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.endswith(".log") or ".log." in file:
                        file_path = os.path.join(root, file)
                        try:
                            if os.path.getmtime(file_path) < cutoff_timestamp:
                                os.remove(file_path)
                                cleaned_logs += 1
                        except Exception:
                            pass
            logger.info(f"✅ [SELF-HEALING] Удалено {cleaned_logs} старых логов")
            
            # 3. Очистка бэкапов (оставляем только последние 5)
            logger.info("🧹 [SELF-HEALING] Очистка старых бэкапов...")
            backup_path = os.path.join(base_path, "backups")
            if os.path.exists(backup_path):
                backup_files = [
                    os.path.join(backup_path, f) 
                    for f in os.listdir(backup_path) 
                    if os.path.isfile(os.path.join(backup_path, f))
                ]
                if len(backup_files) > 5:
                    backup_files.sort(key=os.path.getmtime, reverse=True)
                    for f in backup_files[5:]:
                        try:
                            os.remove(f)
                            logger.info(f"🗑️ [SELF-HEALING] Удален старый бэкап: {os.path.basename(f)}")
                        except Exception:
                            pass
            
            # 4. Очистка кэша
            logger.info("🧹 [SELF-HEALING] Очистка кэша...")
            cache_path = os.path.join(base_path, "cache")
            if os.path.exists(cache_path):
                for item in os.listdir(cache_path):
                    item_path = os.path.join(cache_path, item)
                    try:
                        if os.path.isfile(item_path):
                            os.remove(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                    except Exception:
                        pass
            
            # 5. Очистка __pycache__
            logger.info("🧹 [SELF-HEALING] Очистка __pycache__...")
            for root, dirs, _ in os.walk(base_path):
                if "__pycache__" in dirs:
                    try:
                        shutil.rmtree(os.path.join(root, "__pycache__"))
                    except Exception:
                        pass
            
            # 6. Очистка временных файлов
            logger.info("🧹 [SELF-HEALING] Очистка временных файлов...")
            temp_patterns = [
                os.path.join(base_path, "*.tmp"),
                os.path.join(base_path, "*.temp"),
                os.path.join(base_path, ".pytest_cache"),
            ]
            for pattern in temp_patterns:
                for f in glob.glob(pattern):
                    try:
                        if os.path.isfile(f):
                            os.remove(f)
                        elif os.path.isdir(f):
                            shutil.rmtree(f)
                    except Exception:
                        pass
            
            # 7. Проверяем результат
            _, _, new_free = shutil.disk_usage("/")
            new_free_gb = new_free // (2**30)
            logger.info(f"✅ [SELF-HEALING] Агрессивная очистка завершена. Свободно: {new_free_gb}GB")
            
            if new_free_gb < 1:
                msg = f"🚨 КРИТИЧНО: После очистки осталось только {new_free_gb}GB! Требуется ручное вмешательство."
                logger.error(msg)
                await self._send_admin_alert(msg)
                
        except Exception as e:
            logger.error(f"❌ [SELF-HEALING] Ошибка при агрессивной очистке: {e}")

    async def _emergency_memory_cleanup(self):
        """Экстренная очистка памяти"""
        logger.warning("🔥 [SELF-HEALING] Запуск экстренной очистки памяти...")
        
        try:
            # 1. Очистка кэша моделей Ollama (если есть)
            try:
                from knowledge_os.app.model_memory_manager import ModelMemoryManager
                model_manager = ModelMemoryManager()
                await model_manager.emergency_memory_cleanup()
                logger.info("✅ [SELF-HEALING] Кэш моделей Ollama очищен")
            except Exception as e:
                logger.debug("Модели Ollama не найдены или ошибка: %s", e)
            
            # 2. Принудительная сборка мусора Python
            import gc
            collected = gc.collect()
            logger.info(f"✅ [SELF-HEALING] Собрано {collected} объектов Python GC")
            
            # 3. Проверяем результат
            system_mem = psutil.virtual_memory()
            free_mb = system_mem.available // (1024 * 1024)
            logger.info(f"✅ [SELF-HEALING] После очистки памяти: {free_mb}MB свободно ({system_mem.percent}% использовано)")
            
            if free_mb < 50:
                msg = f"🚨 КРИТИЧНО: После очистки осталось только {free_mb}MB памяти! Требуется перезапуск сервисов."
                logger.error(msg)
                await self._send_admin_alert(msg)
                
        except Exception as e:
            logger.error(f"❌ [SELF-HEALING] Ошибка при экстренной очистке памяти: {e}")

    async def _get_tp_sl_levels(self, db: 'AcceptanceDatabase', symbol: str, entry_price: float, direction: str) -> tuple:
        """
        Получает TP/SL уровни из БД или использует стандартные.
        
        Returns:
            Tuple[tp1, tp2, sl_price] или (None, None, None) если не найдены
        """
        try:
            # Сначала пробуем найти в accepted_signals или signals_log
            # Пробуем через signal_key (AUTO_SYNC_*)
            signal_key_query = "SELECT tp1_price, tp2_price, sl_price FROM accepted_signals WHERE signal_key LIKE ? ORDER BY created_at DESC LIMIT 1"
            rows = await db.execute_with_retry(signal_key_query, (f"AUTO_SYNC_{symbol}_%",), is_write=False)
            
            if rows and rows[0][0] and rows[0][1]:
                tp1, tp2, sl = rows[0][0], rows[0][1], rows[0][2]
                if tp1 and tp2:
                    # Используем SL из БД или стандартный
                    if not sl:
                        if direction.upper() in ("BUY", "LONG"):
                            sl = entry_price * 0.984  # -1.6%
                        else:
                            sl = entry_price * 1.016  # +1.6%
                    return tp1, tp2, sl
            
            # Пробуем через signals_log
            signals_log_query = "SELECT tp1, tp2, stop FROM signals_log WHERE symbol = ? ORDER BY created_at DESC LIMIT 1"
            rows = await db.execute_with_retry(signals_log_query, (symbol,), is_write=False)
            
            if rows and rows[0][0] and rows[0][1]:
                tp1, tp2, sl = rows[0][0], rows[0][1], rows[0][2]
                if tp1 and tp2:
                    if not sl:
                        if direction.upper() in ("BUY", "LONG"):
                            sl = entry_price * 0.984
                        else:
                            sl = entry_price * 1.016
                    return tp1, tp2, sl
        except Exception as e:
            logger.debug("Ошибка получения TP/SL из БД для %s: %s", symbol, e)
        
        # Стандартные уровни (fallback)
        if direction.upper() in ("BUY", "LONG"):
            tp1 = entry_price * 1.018  # +1.8%
            tp2 = entry_price * 1.036  # +3.6%
            sl = entry_price * 0.984   # -1.6%
        else:  # SHORT
            tp1 = entry_price * 0.982  # -1.8%
            tp2 = entry_price * 0.964  # -3.6%
            sl = entry_price * 1.016   # +1.6%
        
        return tp1, tp2, sl

    async def _check_db_health(self, db_path: str):
        """Checks if SQLite DB is responsive"""
        if not os.path.exists(db_path):
            return
        try:
            conn = sqlite3.connect(db_path, timeout=60)
            # Включаем WAL и для проверки здоровья, чтобы не блокировать других
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            if result[0] != "ok":
                msg = f"🚨 DB Corruption detected in {db_path}: {result}"
                logger.error(msg)
                await self._send_admin_alert(msg)
        except Exception as e:
            msg = f"🚨 DB Not responding {db_path}: {e}"
            logger.error(msg)
            await self._send_admin_alert(msg)

async def run_self_healing():
    """Entry point for the self-healing system"""
    manager = SelfHealingManager()
    await manager.monitor_health()

