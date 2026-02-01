#!/usr/bin/env python3
"""
Демон автосинхронизации employees.json при изменениях в БД.

Слушает PostgreSQL NOTIFY 'experts_changed' и запускает sync_employees_from_db.py.
Также поддерживает периодическую синхронизацию (fallback).

Запуск:
  python knowledge_os/app/employees_sync_daemon.py
  
  # Или через Docker/systemd/launchd для продакшена
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
SYNC_DEBOUNCE_SECONDS = int(os.getenv("SYNC_DEBOUNCE_SECONDS", "5"))  # Дебаунс: не чаще раз в 5 сек
PERIODIC_SYNC_MINUTES = int(os.getenv("PERIODIC_SYNC_MINUTES", "60"))  # Периодическая синхронизация раз в час

# Путь к скрипту синхронизации
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_employees_from_db.py"
PYTHON_VENV = REPO_ROOT / "backend" / ".venv" / "bin" / "python"


class EmployeesSyncDaemon:
    """Демон синхронизации employees.json из БД."""

    def __init__(self):
        self.last_sync_time = None
        self.pending_sync = False
        self._sync_lock = asyncio.Lock()

    async def run_sync(self, reason: str = "manual"):
        """Запустить sync_employees_from_db.py."""
        async with self._sync_lock:
            now = datetime.now()
            
            # Дебаунс: не запускать чаще SYNC_DEBOUNCE_SECONDS
            if self.last_sync_time:
                elapsed = (now - self.last_sync_time).total_seconds()
                if elapsed < SYNC_DEBOUNCE_SECONDS:
                    logger.debug("Debounce: sync skipped (%.1fs < %ds)", elapsed, SYNC_DEBOUNCE_SECONDS)
                    self.pending_sync = True
                    return False

            self.last_sync_time = now
            self.pending_sync = False

            logger.info("🔄 Запуск синхронизации (%s)...", reason)
            
            python_exe = str(PYTHON_VENV) if PYTHON_VENV.exists() else sys.executable
            try:
                result = subprocess.run(
                    [python_exe, str(SYNC_SCRIPT)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(REPO_ROOT),
                )
                if result.returncode == 0:
                    logger.info("✅ Синхронизация завершена")
                    # Парсим вывод для информации
                    for line in result.stdout.splitlines():
                        if "+" in line or "✅" in line:
                            logger.info("   %s", line.strip())
                else:
                    logger.warning("⚠️ Синхронизация завершена с кодом %d: %s", 
                                   result.returncode, result.stderr[:200])
                return True
            except subprocess.TimeoutExpired:
                logger.error("❌ Таймаут синхронизации (60s)")
                return False
            except Exception as e:
                logger.error("❌ Ошибка синхронизации: %s", e)
                return False

    async def handle_notification(self, payload: str):
        """Обработать NOTIFY от PostgreSQL."""
        try:
            data = json.loads(payload)
            operation = data.get("operation", "?")
            name = data.get("name", "?")
            logger.info("📬 Получено: %s expert '%s'", operation, name)
            await self.run_sync(reason=f"{operation} {name}")
        except json.JSONDecodeError:
            logger.warning("⚠️ Невалидный payload: %s", payload[:100])
            await self.run_sync(reason="notification")

    async def listen_notifications(self):
        """Слушать PostgreSQL NOTIFY 'experts_changed'."""
        try:
            import asyncpg
        except ImportError:
            logger.error("❌ asyncpg не установлен")
            return

        while True:
            try:
                conn = await asyncpg.connect(DB_URL)
                logger.info("🔌 Подключено к БД, слушаю 'experts_changed'...")

                async def callback(conn, pid, channel, payload):
                    await self.handle_notification(payload)

                await conn.add_listener("experts_changed", callback)

                # Держим соединение открытым
                while True:
                    await asyncio.sleep(1)
                    # Проверяем pending sync (после дебаунса)
                    if self.pending_sync:
                        await self.run_sync(reason="debounced")

            except asyncpg.PostgresError as e:
                logger.error("❌ Ошибка PostgreSQL: %s. Переподключение через 10s...", e)
                await asyncio.sleep(10)
            except Exception as e:
                logger.error("❌ Ошибка: %s. Переподключение через 10s...", e)
                await asyncio.sleep(10)

    async def periodic_sync(self):
        """Периодическая синхронизация (fallback)."""
        while True:
            await asyncio.sleep(PERIODIC_SYNC_MINUTES * 60)
            logger.info("⏰ Периодическая синхронизация...")
            await self.run_sync(reason="periodic")

    async def run(self):
        """Запустить демон."""
        logger.info("🚀 EmployeesSyncDaemon запущен")
        logger.info("   SYNC_DEBOUNCE_SECONDS=%d", SYNC_DEBOUNCE_SECONDS)
        logger.info("   PERIODIC_SYNC_MINUTES=%d", PERIODIC_SYNC_MINUTES)
        logger.info("   SYNC_SCRIPT=%s", SYNC_SCRIPT)

        # Начальная синхронизация
        await self.run_sync(reason="startup")

        # Запускаем listener и periodic sync параллельно
        await asyncio.gather(
            self.listen_notifications(),
            self.periodic_sync(),
        )


async def trigger_employees_sync(reason: str = "code_call"):
    """
    Функция для вызова из других модулей.
    Запускает синхронизацию асинхронно (fire-and-forget).
    
    Использование:
        from knowledge_os.app.employees_sync_daemon import trigger_employees_sync
        await trigger_employees_sync("after_hire")
    """
    daemon = EmployeesSyncDaemon()
    await daemon.run_sync(reason=reason)


def trigger_employees_sync_sync(reason: str = "code_call"):
    """
    Синхронная версия для вызова из не-async кода.
    
    Использование:
        from knowledge_os.app.employees_sync_daemon import trigger_employees_sync_sync
        trigger_employees_sync_sync("after_hire")
    """
    python_exe = str(PYTHON_VENV) if PYTHON_VENV.exists() else sys.executable
    try:
        subprocess.Popen(
            [python_exe, str(SYNC_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(REPO_ROOT),
        )
        logger.info("🔄 Синхронизация запущена в фоне (%s)", reason)
    except Exception as e:
        logger.warning("⚠️ Не удалось запустить синхронизацию: %s", e)


if __name__ == "__main__":
    daemon = EmployeesSyncDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("👋 Демон остановлен")
