import asyncio
import logging
import time
import os
import sqlite3
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Optional

logger = logging.getLogger(__name__)

class SignalHeartbeat:
    """Мониторинг генерации сигналов (Signal Heartbeat) через БД"""
    
    def __init__(self, db_path: str = "/root/atra/trading.db", threshold_minutes: int = 60):
        self.db_path = db_path
        self.threshold_minutes = threshold_minutes
        self.running = False

    def _get_last_alert_time(self) -> float:
        """Получает время последнего алерта из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT last_time FROM system_monitoring WHERE key = 'heartbeat_alert'")
            row = cursor.fetchone()
            conn.close()
            if row:
                return datetime.fromisoformat(row[0]).timestamp()
        except Exception as e:
            logger.error(f"💓 [HEARTBEAT] Ошибка чтения метки из БД: {e}")
        return 0

    def _save_last_alert_time(self):
        """Сохраняет текущее время как время последнего алерта в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO system_monitoring (key, last_time) VALUES (?, ?)",
                ('heartbeat_alert', get_utc_now().isoformat())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"💓 [HEARTBEAT] Ошибка записи метки в БД: {e}")

    async def check_last_signal(self) -> Optional[datetime]:
        """Проверяет время последнего сигнала в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT created_at FROM signals_log ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                dt_str = result[0]
                try:
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None
            return None
        except Exception as e:
            return None

    async def run_heartbeat_monitor(self):
        """Запускает цикл мониторинга"""
        is_dev = os.getenv("TELEGRAM_TOKEN_DEV") is not None
        if is_dev:
            # В DEV режиме алерты полностью подавлены в коде ниже
            logger.info("💓 [HEARTBEAT] Режим DEV: монитор активен в тихом режиме")

        logger.info(f"💓 [HEARTBEAT] Запуск монитора сигналов (порог: {self.threshold_minutes} мин)")
        self.running = True
        
        while self.running:
            try:
                last_dt = await self.check_last_signal()
                now = get_utc_now()
                
                if last_dt:
                    diff = (now - last_dt).total_seconds() / 60
                    logger.info(f"💓 [HEARTBEAT] Последний сигнал: {int(diff)} мин назад")
                    
                    if diff > self.threshold_minutes:
                        last_alert = self._get_last_alert_time()
                        # Кулдаун 12 часов (43200 сек)
                        if time.time() - last_alert > 43200:
                            await self._trigger_alert(int(diff))
                            self._save_last_alert_time()
                        else:
                            logger.info("💓 [HEARTBEAT] Алерт подавлен (кулдаун 12ч)")
                
                await asyncio.sleep(300)
            except Exception as e:
                await asyncio.sleep(60)

    async def _trigger_alert(self, diff_minutes: int):
        """Отправляет уведомление (только для ПРОД)"""
        is_dev = os.getenv("TELEGRAM_TOKEN_DEV") is not None
        if is_dev:
            return

        try:
            from src.telegram.handlers import notify_all
            message = (
                f"🚨 *SIGNAL HEARTBEAT ALERT [SERVER: 185.177.216.15]*\n\n"
                f"⚠️ Система не генерировала сигналы более {diff_minutes} минут!\n"
                f"🕒 Последний сигнал: {diff_minutes} мин назад."
            )
            await notify_all(message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"💓 [HEARTBEAT] Ошибка алерта: {e}")

async def start_heartbeat_monitor(db_path: str = "/root/atra/trading.db"):
    hb = SignalHeartbeat(db_path=db_path)
    await hb.run_heartbeat_monitor()
