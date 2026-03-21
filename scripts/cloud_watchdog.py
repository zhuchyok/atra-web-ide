#!/usr/bin/env python3
"""
cloud_watchdog.py — автоматический переключатель STRICT_LOCAL.

Следит за доступностью облачных AI API (api.anthropic.com, api.openai.com).
Если все недоступны N раз подряд → STRICT_LOCAL=true + перезапуск Victoria + ntfy.
При восстановлении → STRICT_LOCAL=false + перезапуск + ntfy.
"""
import asyncio
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env"
KOS_ENV_FILE = ROOT / "knowledge_os" / ".env"

# Настройки
CHECK_INTERVAL = 30       # секунд между проверками в норме
OFFLINE_RECHECK = 60      # секунд между проверками в офлайн режиме
FAIL_THRESHOLD = 3        # неудач подряд → включить STRICT_LOCAL
RESTORE_THRESHOLD = 2     # успехов подряд → выключить STRICT_LOCAL
CONNECT_TIMEOUT = 5.0     # таймаут TCP соединения

# Хосты проверки: (host, port)
# Достаточно одного доступного → интернет есть
CLOUD_HOSTS = [
    ("api.anthropic.com", 443),
    ("api.openai.com", 443),
    ("1.1.1.1", 53),
]


def _get_ntfy_url() -> str:
    try:
        content = ENV_FILE.read_text()
        m = re.search(r"^NTFY_URL=(.+)$", content, re.MULTILINE)
        return m.group(1).strip() if m else "https://ntfy.sh/atra_victoria_curator"
    except Exception:
        return "https://ntfy.sh/atra_victoria_curator"


def _set_env_value(path: Path, key: str, value: str) -> None:
    if not path.exists():
        return
    content = path.read_text()
    if re.search(rf"^{key}=", content, re.MULTILINE):
        content = re.sub(rf"^{key}=.*$", f"{key}={value}", content, flags=re.MULTILINE)
    else:
        content += f"\n{key}={value}\n"
    path.write_text(content)


def get_strict_local() -> bool:
    try:
        m = re.search(r"^STRICT_LOCAL=(.+)$", ENV_FILE.read_text(), re.MULTILINE)
        return (m.group(1).strip().lower() in ("true", "1", "yes")) if m else False
    except Exception:
        return False


def set_strict_local(value: bool) -> None:
    val = "true" if value else "false"
    _set_env_value(ENV_FILE, "STRICT_LOCAL", val)
    _set_env_value(KOS_ENV_FILE, "STRICT_LOCAL", val)
    log.info("STRICT_LOCAL → %s", val)


def restart_victoria() -> None:
    log.info("Перезапускаем victoria-agent...")
    try:
        subprocess.run(
            ["docker", "compose", "-f", str(ROOT / "knowledge_os" / "docker-compose.yml"),
             "up", "-d", "--no-deps", "--force-recreate", "victoria-agent"],
            capture_output=True, timeout=60, cwd=str(ROOT),
        )
        log.info("victoria-agent перезапущен ✅")
    except Exception as e:
        log.warning("docker compose failed: %s — пробуем docker restart", e)
        try:
            subprocess.run(["docker", "restart", "victoria-agent"],
                           capture_output=True, timeout=30)
        except Exception as e2:
            log.error("docker restart тоже не удался: %s", e2)


async def notify(title: str, msg: str, priority: str = "default") -> None:
    ntfy = _get_ntfy_url()
    try:
        import urllib.request
        req = urllib.request.Request(
            ntfy,
            data=msg.encode(),
            headers={"Title": title, "Priority": priority},
            method="POST",
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, urllib.request.urlopen, req)
    except Exception as e:
        log.warning("ntfy уведомление не отправлено: %s", e)


async def check_cloud() -> bool:
    """True если хотя бы один облачный хост доступен."""
    for host, port in CLOUD_HOSTS:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=CONNECT_TIMEOUT,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return True
        except Exception:
            continue
    return False


async def main() -> None:
    log.info("🚀 cloud_watchdog запущен")
    log.info("   Хосты: %s", CLOUD_HOSTS)
    log.info("   Порог: %d неудач → STRICT_LOCAL=true | %d успехов → false",
             FAIL_THRESHOLD, RESTORE_THRESHOLD)

    fail_count = 0
    success_count = 0
    currently_offline = get_strict_local()

    if currently_offline:
        log.info("📌 Старт: STRICT_LOCAL уже true — режим офлайн")

    while True:
        cloud_ok = await check_cloud()

        if cloud_ok:
            fail_count = 0
            success_count += 1

            if currently_offline and success_count >= RESTORE_THRESHOLD:
                log.info("🌐 Интернет восстановлен! Выключаем STRICT_LOCAL...")
                set_strict_local(False)
                restart_victoria()
                currently_offline = False
                success_count = 0
                await notify(
                    "☁️ Victoria: онлайн режим",
                    "Доступ к облачным API восстановлён. STRICT_LOCAL=false. Victoria в нормальном режиме.",
                    "default",
                )

            await asyncio.sleep(CHECK_INTERVAL)

        else:
            success_count = 0
            fail_count += 1
            log.warning("⚠️  Облако недоступно (попытка %d/%d)", fail_count, FAIL_THRESHOLD)

            if not currently_offline and fail_count >= FAIL_THRESHOLD:
                log.info("🔒 Переключаемся в STRICT_LOCAL=true...")
                set_strict_local(True)
                restart_victoria()
                currently_offline = True
                fail_count = 0
                await notify(
                    "🔒 Victoria: офлайн режим",
                    (
                        "api.anthropic.com недоступен.\n"
                        "STRICT_LOCAL=true — Victoria работает только локально:\n"
                        "• Мозг: MLX (victoria-wisdom-v3.5)\n"
                        "• Руки: Ollama\n"
                        "• Поиск: SearXNG локальный"
                    ),
                    "high",
                )

            await asyncio.sleep(OFFLINE_RECHECK)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлен вручную")
        sys.exit(0)
