import asyncio
import os
import subprocess
from datetime import datetime

import asyncpg
import httpx

# Настройки
SERVICES = [
    "knowledge_os_api.service",
    "knowledge_os_telegram.service",
    "knowledge_os_dashboard.service",
    "knowledge_os_worker.service",
]
TG_TOKEN = "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU"
CHAT_ID = 556251171
LOG_PATH = "/root/knowledge_os/logs/guardian.log"


async def send_tg_alert(message: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "text": f"🛡️ *GUARDIAN ALERT*\n\n{message}",
                    "parse_mode": "Markdown",
                },
            )
        except Exception as e:
            print(f"Failed to send TG alert: {e}")


def run_cursor_agent(prompt: str):
    try:
        result = subprocess.run(
            ["/root/.local/bin/cursor-agent", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"


async def check_and_heal():
    print(f"[{datetime.now()}] Guardian: Monitoring systems...")

    for service in SERVICES:
        # 1. Проверяем статус
        check = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True)
        if check.stdout.strip() != "active":
            print(f"⚠️ Service {service} is DOWN!")

            # 2. Читаем логи
            logs = subprocess.run(
                ["journalctl", "-u", service, "-n", "50", "--no-pager"],
                capture_output=True,
                text=True,
            ).stdout

            # 3. Просим исцеления у ИИ
            prompt = f"""
            Ты - Инженер-Спасатель (Self-Healing System). Сервис {service} упал.
            ЛОГИ ОШИБКИ:
            {logs}

            ЗАДАЧА:
            1. Проанализируй причину падения.
            2. Если это программная ошибка, предложи исправление кода (если можешь).
            3. Если это проблема окружения, предложи команду для исправления.
            4. В любом случае, дай краткий вердикт.
            """

            diagnosis = run_cursor_agent(prompt)

            # 4. Пытаемся перезапустить
            subprocess.run(["systemctl", "restart", service])

            # 5. Уведомляем владельца
            alert = f"Сервис *{service}* был неактивен.\n\n*Диагноз ИИ:*\n{diagnosis}\n\n♻️ Сервис перезапущен."
            await send_tg_alert(alert)

            with open(LOG_PATH, "a") as f:
                f.write(f"[{datetime.now()}] Healed {service}. Diagnosis: {diagnosis[:200]}...\n")


if __name__ == "__main__":
    asyncio.run(check_and_heal())
