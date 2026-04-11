#!/usr/bin/env python3
"""
watch_victoria_rebuild.py — Авто-пересборка victoria-agent при изменении кода.

Следит за:
  - src/agents/bridge/victoria_server.py
  - src/agents/tools/system_tools.py
  - knowledge_os/app/local_router.py

При изменении любого из файлов:
  1. Ждёт 5 сек (debounce — могут быть множественные saves)
  2. Запускает docker-compose --force-recreate victoria-agent
  3. Шлёт Telegram уведомление о пересборке

Запуск: python3 scripts/watch_victoria_rebuild.py
Launchd: com.atra.victoria-rebuild-watcher

[SINGULARITY 21.5] Автономность: victoria-agent всегда актуален без ручного --force-recreate.
"""

import asyncio
import hashlib
import httpx
import logging
import os
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("victoria_watcher")

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "knowledge_os" / "docker-compose.yml"

WATCH_FILES = [
    ROOT / "src" / "agents" / "bridge" / "victoria_server.py",
    ROOT / "src" / "agents" / "tools" / "system_tools.py",
    ROOT / "knowledge_os" / "app" / "local_router.py",
]

DEBOUNCE_SEC = 8   # ждём после последнего изменения
CHECK_INTERVAL = 3  # интервал проверки mtime (сек)

TG_TOKEN = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_USER_ID", "")


def file_hash(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


async def tg_send(text: str) -> None:
    if not (TG_TOKEN and TG_CHAT_ID):
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            await c.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            )
    except Exception as e:
        logger.debug("TG failed: %s", e)


def rebuild_victoria() -> bool:
    """docker-compose --force-recreate victoria-agent. Возвращает True если успешно."""
    logger.info("🔄 Пересборка victoria-agent...")
    try:
        result = subprocess.run(
            [
                "docker-compose", "-f", str(COMPOSE_FILE),
                "up", "-d", "--no-deps", "--force-recreate", "victoria-agent",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.info("✅ victoria-agent пересобран")
            return True
        else:
            logger.error("❌ Ошибка пересборки: %s", result.stderr[-500:])
            return False
    except Exception as e:
        logger.error("❌ Exception: %s", e)
        return False


async def wait_healthy(timeout: int = 60) -> bool:
    """Ждём /health victoria-agent до timeout сек."""
    url = os.getenv("VICTORIA_URL", "http://localhost:8010") + "/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(url)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    return True
        except Exception:
            pass
        await asyncio.sleep(3)
    return False


async def watch_loop() -> None:
    logger.info("👀 Victoria Rebuild Watcher запущен")
    logger.info("   Слежу за %d файлами", len(WATCH_FILES))
    for f in WATCH_FILES:
        logger.info("   • %s", f.relative_to(ROOT))

    hashes = {f: file_hash(f) for f in WATCH_FILES}
    last_change_time: float = 0
    rebuild_pending = False

    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        changed_files = []

        for f in WATCH_FILES:
            new_hash = file_hash(f)
            if new_hash and new_hash != hashes[f]:
                hashes[f] = new_hash
                changed_files.append(f.name)
                logger.info("📝 Изменён: %s", f.name)

        if changed_files:
            last_change_time = time.time()
            rebuild_pending = True

        # Debounce: запускаем пересборку только если прошло DEBOUNCE_SEC без новых изменений
        if rebuild_pending and (time.time() - last_change_time) >= DEBOUNCE_SEC:
            rebuild_pending = False
            ok = rebuild_victoria()
            if ok:
                healthy = await wait_healthy(60)
                status = "✅ healthy" if healthy else "⚠️ не ответил /health за 60 сек"
                logger.info("victoria-agent: %s", status)
                await tg_send(
                    f"🔄 *Victoria Auto-Rebuild*\n\n"
                    f"Изменены файлы: `{', '.join(changed_files)}`\n"
                    f"victoria-agent: {status}"
                )
            else:
                await tg_send(
                    f"❌ *Victoria Rebuild FAILED*\n\n"
                    f"Файлы: `{', '.join(changed_files)}`\n"
                    f"Проверь логи: `docker logs victoria-agent`"
                )


if __name__ == "__main__":
    # Загружаем .env если запущены не из launchd
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    asyncio.run(watch_loop())
