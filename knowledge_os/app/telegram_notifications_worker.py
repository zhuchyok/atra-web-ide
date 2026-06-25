"""
Воркер отправки уведомлений и отчётов в Telegram.
Запускается в Docker (telegram-notifications) или вручную.
- Каждые 60 с: отправляет записи из notifications (WHERE sent = FALSE) в Telegram.
- Ежедневно в 8:00 и еженедельно в понедельник в 9:00: генерирует и шлёт отчёты (Report Generator).

Переменные окружения (обязательные для отправки):
  TELEGRAM_BOT_TOKEN или TG_TOKEN — токен бота
  TELEGRAM_USER_ID или CHAT_ID — chat_id получателя (для личного чата = user id)
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

import httpx

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("telegram_notifications")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_USER_ID") or os.getenv("CHAT_ID", "")
TG_PROXY = os.getenv("TG_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY", "")
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh/atra_victoria_curator")
TG_FORCE_NTFY_PRIMARY = os.getenv("TG_FORCE_NTFY_PRIMARY", "false").lower() in (
    "1",
    "true",
    "yes",
)
NOTIFICATION_INTERVAL_SEC = int(
    os.getenv("TELEGRAM_NOTIFICATION_INTERVAL_SEC", "3600")
)  # по умолчанию раз в час
REPORTS_ENABLED = os.getenv("TELEGRAM_REPORTS_ENABLED", "true").lower() in ("1", "true", "yes")


async def send_telegram(text: str) -> bool:
    """Отправить сообщение в Telegram. Без parse_mode, чтобы избежать ошибок разбора."""
    if TG_FORCE_NTFY_PRIMARY:
        logger.info("TG_FORCE_NTFY_PRIMARY=true, Telegram send skipped")
        return False
    if not TG_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        client_kwargs = {"timeout": 15.0}
        proxy_url = TG_PROXY
        if proxy_url:
            # [SINGULARITY 26.10] Use socks5h:// for remote DNS resolution (world practice for TG)
            if proxy_url.startswith("socks5://"):
                proxy_url = proxy_url.replace("socks5://", "socks5h://")
            client_kwargs["proxy"] = proxy_url

        async with httpx.AsyncClient(**client_kwargs) as client:
            r = await client.post(
                url,
                json={"chat_id": str(CHAT_ID).strip(), "text": text[:4096]},
            )
        if r.is_success:
            return True
        logger.warning("Telegram sendMessage: %s %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.warning("Telegram send error: %s", e)
        return False


async def send_ntfy(text: str, title: str = "ATRA Notification") -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                NTFY_URL,
                content=text[:8000].encode("utf-8"),
                headers={"Title": title[:120], "Priority": "default"},
            )
        if r.is_success:
            return True
        logger.warning("NTFY send failed: %s %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        logger.warning("NTFY send error: %s", e)
        return False


async def process_pending_notifications():
    """Отправить все непрочитанные уведомления из БД в Telegram."""
    if not TG_TOKEN or not CHAT_ID:
        return
    try:
        import asyncpg
    except ImportError:
        logger.debug("asyncpg not available, skip notifications from DB")
        return
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            "SELECT id, message FROM notifications WHERE sent = FALSE ORDER BY created_at ASC LIMIT 50"
        )
        for row in rows:
            message = str(row["message"])
            if TG_FORCE_NTFY_PRIMARY:
                ok = await send_ntfy(message, title="ATRA DB Notification")
                if not ok:
                    ok = await send_telegram(message)
            else:
                ok = await send_telegram(message)
                if not ok:
                    ok = await send_ntfy(message, title="ATRA DB Notification (fallback)")
            if ok:
                await conn.execute("UPDATE notifications SET sent = TRUE WHERE id = $1", row["id"])
                logger.info("Sent notification id=%s", row["id"])
            else:
                break  # не помечаем остальные, попробуем в следующий раз
        await conn.close()
    except Exception as e:
        logger.warning("Error processing notifications: %s", e)


async def run_report_generator_loop():
    """Запуск периодической генерации отчётов (ежедневно 8:00, еженедельно понедельник 9:00)."""
    if not REPORTS_ENABLED or not TG_TOKEN or not CHAT_ID:
        logger.info("Reports disabled or Telegram not configured, skipping report loop")
        return
    try:
        from report_generator import get_report_generator
    except ImportError as e:
        logger.warning("Report generator not available: %s", e)
        return
    try:
        report_gen = get_report_generator()
        await report_gen.start_periodic_reports()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Report generator loop error: %s", e)


async def notification_loop():
    """Периодическая отправка уведомлений из БД."""
    while True:
        try:
            await process_pending_notifications()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Notification loop error: %s", e)
        await asyncio.sleep(NOTIFICATION_INTERVAL_SEC)


async def main():
    if not TG_TOKEN or not CHAT_ID:
        logger.warning(
            "TELEGRAM_BOT_TOKEN (или TG_TOKEN) и TELEGRAM_USER_ID (или CHAT_ID) не заданы. "
            "Уведомления и отчёты в Telegram не будут отправляться. "
            "Задайте их в .env или в docker-compose для сервиса telegram-notifications."
        )
    else:
        logger.info(
            "Telegram notifications worker started (chat_id=%s, interval=%ss)",
            CHAT_ID,
            NOTIFICATION_INTERVAL_SEC,
        )

    tasks = [asyncio.create_task(notification_loop())]
    if REPORTS_ENABLED and TG_TOKEN and CHAT_ID:
        tasks.append(asyncio.create_task(run_report_generator_loop()))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("Fatal: %s", e)
        sys.exit(1)
