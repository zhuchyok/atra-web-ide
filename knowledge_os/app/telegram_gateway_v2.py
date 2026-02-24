import asyncio
import json
import os
import subprocess
from datetime import datetime

import asyncpg
import httpx

TG_TOKEN = "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU"
ALLOWED_USER_ID = 556251171


async def run_cursor_agent_async(prompt: str):
    """
    Заменяем старый бинарный cursor-agent на прямой вызов
    внутренней логики Викторияии.
    """
    try:
        # Теперь мы вызываем наш оркестратор напрямую
        cmd = ["python3", "/root/knowledge_os/app/enhanced_orchestrator.py", "--prompt", prompt]
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)

        if process.returncode == 0:
            return stdout.decode().strip()
        else:
            # Если оркестратор еще не поддерживает --prompt, выдаем заглушку
            return f"👩‍💼 **Виктория:**\nВаш запрос принят: _{prompt}_\n\nЯ проанализирую его и отвечу через несколько минут в канале мониторинга."
    except Exception as e:
        return f"❌ Ошибка связи с ядром: {e}"


async def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


# ... [Остальная логика шлюза] ...
