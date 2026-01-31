import asyncio
import os
import httpx
import subprocess
import asyncpg
from datetime import datetime
import json
import shutil

TG_TOKEN = "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU"
ALLOWED_USER_ID = 556251171
DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def handle_document(chat_id, document):
    file_name = document.get("file_name", "")
    file_id = document.get("file_id")
    
    if "brain_recovery_" not in file_name or not file_name.endswith(".tar.gz"):
        await send_telegram_msg(chat_id, "❌ Это не похоже на Recovery Bundle системы.")
        return

    await send_telegram_msg(chat_id, f"⏳ Начинаю загрузку файла восстановления: `{file_name}`...")
    
    async with httpx.AsyncClient() as client:
        # Get file path
        res = await client.get(f"https://api.telegram.org/bot{TG_TOKEN}/getFile?file_id={file_id}")
        file_path = res.json()["result"]["file_path"]
        
        # Download
        target_path = f"/tmp/{file_name}"
        async with client.stream("GET", f"https://api.telegram.org/file/bot{TG_TOKEN}/{file_path}") as response:
            with open(target_path, "wb") as f:
                async for chunk in response.iter_bytes():
                    f.write(chunk)
        
        await send_telegram_msg(chat_id, "✅ Файл загружен. Запускаю процесс восстановления...")
        
        # Execute restoration script
        try:
            restore_proc = await asyncio.create_subprocess_exec(
                "python3", "/root/knowledge_os/scripts/restore_brain.py", target_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await restore_proc.communicate()
            
            if restore_proc.returncode == 0:
                await send_telegram_msg(chat_id, "🎉 **СИСТЕМА УСПЕШНО ВОССТАНОВЛЕНА!**\n\nМозг перезапущен. Все эксперты на связи.")
            else:
                await send_telegram_msg(chat_id, f"❌ **ОШИБКА ВОССТАНОВЛЕНИЯ:**\n\n`{stderr.decode()}`")
        except Exception as e:
            await send_telegram_msg(chat_id, f"❌ Критическая ошибка скрипта: {e}")

async def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, data={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})

# ... [Остальная часть кода telegram_gateway.py будет интегрирована] ...
# Я привел только ключевые изменения для краткости, при деплое заменю весь файл.

