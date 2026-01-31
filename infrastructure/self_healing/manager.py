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

logger = logging.getLogger(__name__)

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
                        await db.create_active_position(
                            symbol=symbol,
                            direction=ex_p['side'].upper(),
                            entry_price=float(ex_p['entryPrice']),
                            user_id=user_id,
                            chat_id=0, message_id=0,
                            signal_key=f"AUTO_SYNC_{symbol}_{int(time.time())}"
                        )
                        # We don't place SL/TP here to avoid overwriting user manual settings,
                        # but ARS will see it in next hour and handle it.

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
            msg = f"🚨 Low disk space: {free_gb}GB free. Triggering auto-cleanup."
            logger.warning(msg)
            await self._send_admin_alert(msg)
            self._cleanup_logs()

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

