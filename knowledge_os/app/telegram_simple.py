#!/usr/bin/env python3
"""
ATRA Telegram Simple Gateway v5.0 (Restored & Improved)
Шлюз для связи с экспертами (Виктория, Владимир) и базой знаний.
"""

import asyncio
import logging
import os

import asyncpg
import httpx

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("telegram_simple.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Настройки: секреты только из переменных окружения (мировая практика)
TG_TOKEN = os.getenv("TG_TOKEN", "")
ALLOWED_USER_ID = int(os.getenv("TG_ALLOWED_USER_ID", "0")) or 556251171  # Илья (Владелец)
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
VECTOR_CORE_URL = "http://localhost:8001"
PID_FILE = "/tmp/telegram_simple_expert.pid"


def check_single_instance():
    """Проверка и создание PID файла"""
    import sys

    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error(f"Шлюз уже запущен (PID: {old_pid}). Выход.")
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            os.remove(PID_FILE)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


async def run_cursor_agent_async(prompt: str, max_timeout: int = 45):
    """Запуск Cursor Agent или прямого вызова ядра ИИ с оптимизированными таймаутами"""
    # Определяем безопасную рабочую директорию
    safe_cwd = "/root/knowledge_os/app"
    if not os.path.exists(safe_cwd):
        # Fallback на /tmp если основная директория недоступна
        safe_cwd = "/tmp"
        os.makedirs(safe_cwd, exist_ok=True)

    # Попытка 1: Прямой вызов ai_core (самый быстрый путь, таймаут 30 сек)
    try:
        from ai_core import run_smart_agent_async

        result = await asyncio.wait_for(
            run_smart_agent_async(prompt, expert_name="Виктория"), timeout=30
        )
        if result and str(result).strip():  # Проверка на пустую строку
            return result if isinstance(result, str) else result.get("response", str(result))
        else:
            logger.warning(f"⚠️ ai_core вернул пустой результат для промпта: {prompt[:100]}")
    except asyncio.TimeoutError:
        logger.warning("⏱️ ai_core timeout (30s), пробуем cursor-agent")
    except Exception as e:
        logger.error(f"Failed to run ai_core directly: {e}", exc_info=True)

    # Попытка 2: Через бинарный файл (таймаут 30 сек вместо 120)
    try:
        env = os.environ.copy()
        # Убеждаемся, что HOME установлен
        if "HOME" not in env:
            env["HOME"] = "/root"

        process = await asyncio.create_subprocess_exec(
            "/root/.local/bin/cursor-agent",
            "--print",
            prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=safe_cwd,
        )
        try:
            # Уменьшаем таймаут до 30 секунд для быстрого ответа
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                error_msg = stderr.decode()[:200]
                logger.error(f"⚠️ Ошибка мозга (code {process.returncode}): {error_msg}")
        except asyncio.TimeoutExpired:
            process.kill()
            logger.warning("⏱️ Agent timeout expired (30s)")
    except Exception as e:
        logger.error(f"Failed to run agent binary: {e}")

    # Попытка 3: Через внутренний оркестратор (таймаут 20 сек вместо 60)
    try:
        cmd = ["python3", "/root/knowledge_os/app/enhanced_orchestrator.py", "--prompt", prompt]
        env = os.environ.copy()
        if "HOME" not in env:
            env["HOME"] = "/root"

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=safe_cwd,
        )
        try:
            # Уменьшаем таймаут до 20 секунд
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                error_msg = stderr.decode()[:200]
                logger.error(f"⚠️ Ошибка оркестратора (code {process.returncode}): {error_msg}")
        except (asyncio.TimeoutError, TimeoutError):
            # asyncio.wait_for бросает asyncio.TimeoutError (не TimeoutExpired!)
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            logger.warning("⏱️ Orchestrator timeout expired (20s)")
    except Exception as e:
        logger.error(f"Failed to run orchestrator: {e}")

    return "⌛ Извините, я сейчас не могу связаться с ядром системы (Викторияией). Проверьте статус процессов на сервере."


async def send_telegram_msg(chat_id, text, reply_markup=None):
    """Отправка сообщения в Telegram с опциональными inline кнопками"""
    if not TG_TOKEN or not TG_TOKEN.strip():
        return  # Секрет не задан — не вызываем API
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            data = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

            # Добавляем inline кнопки, если указаны
            if reply_markup:
                import json

                data["reply_markup"] = json.dumps(reply_markup)

            # Пытаемся отправить с Markdown
            res = await client.post(url, data=data, timeout=15)
            if not res.is_success:
                # Если Markdown сломан, отправляем как обычный текст
                data.pop("parse_mode", None)
                await client.post(url, data=data, timeout=15)
        except Exception as e:
            logger.error(f"Ошибка отправки TG: {e}")


async def get_expert_config(name):
    """Получение конфигурации эксперта из БД"""
    try:
        conn = await asyncpg.connect(DB_URL)
        row = await conn.fetchrow(
            "SELECT id, name, system_prompt, role, department FROM experts WHERE name ILIKE $1",
            name + "%",
        )
        await conn.close()
        return row
    except Exception as e:
        logger.error(f"БД ошибка при поиске эксперта {name}: {e}")
    return None


async def handle_message(target_name, user_text, chat_id, user_id):
    """Обработка входящего сообщения"""
    if user_id != ALLOWED_USER_ID:
        logger.warning(f"Игнорирую сообщение от неизвестного пользователя: {user_id}")
        return

    # Rate Limiting (Singularity 8.0)
    try:
        from rate_limiter import get_rate_limiter

        rate_limiter = get_rate_limiter()
        allowed, error_message = await rate_limiter.check_rate_limit(str(user_id))

        if not allowed:
            logger.warning(f"🚨 [RATE LIMITER] Запрос от {user_id} заблокирован: {error_message}")
            await send_telegram_msg(
                chat_id, error_message or "⚠️ Превышен лимит запросов. Подождите немного."
            )
            return
    except Exception as e:
        logger.debug(f"⚠️ [RATE LIMITER] Ошибка проверки rate limit: {e}")
        # Продолжаем обработку при ошибке (fail-open)

    if not target_name:
        target_name = "Виктория"  # По умолчанию Виктория координирует все

    expert = await get_expert_config(target_name)
    if not expert:
        logger.info(f"Эксперт {target_name} не найден в БД, использую Викторияию")
        expert = await get_expert_config("Виктория")
        if not expert:
            # Хардкод дефолта если БД пуста
            expert = {
                "name": "Виктория",
                "system_prompt": "Вы Виктория, Главный Координатор торговой системы ATRA. Отвечайте лаконично и по делу.",
                "role": "Team Lead",
                "id": 0,
            }

    logger.info(f"📨 Запрос от Ильи к {expert['name']}: {user_text}")

    # Получаем контекст сессии (Singularity 8.0)
    session_context = ""
    try:
        from session_context_manager import get_session_context_manager

        context_manager = get_session_context_manager()
        session_context = await context_manager.get_session_context(
            user_id=str(user_id), expert_name=expert["name"], current_query=user_text
        )
        if session_context:
            logger.debug("📝 [SESSION CONTEXT] Получен контекст из предыдущих запросов")
    except Exception as e:
        logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка получения контекста: {e}")

    # Формируем полный контекст для ИИ
    full_prompt = f"### ЭКСПЕРТ: {expert['name']} ({expert['role']})\n\n{expert['system_prompt']}\n\n{session_context}ЗАПРОС ВЛАДЕЛЬЦА: {user_text}"

    # Отправляем быстрый ответ "Обрабатываю запрос..."
    processing_msg = await send_telegram_msg(chat_id, "⏳ Обрабатываю запрос...")

    # Вызываем ядро ИИ с общим таймаутом 45 секунд
    try:
        response_text = await asyncio.wait_for(run_cursor_agent_async(full_prompt), timeout=45)
        logger.info(
            f"📤 Получен ответ от ядра ИИ (длина: {len(str(response_text)) if response_text else 0}): {str(response_text)[:100] if response_text else 'None'}..."
        )

        # Проверка на пустой ответ
        if not response_text or not str(response_text).strip():
            logger.warning(f"⚠️ Пустой ответ от ядра ИИ для запроса: {user_text[:100]}")
            response_text = "⌛ Извините, я сейчас не могу обработать ваш запрос. Попробуйте переформулировать вопрос или подождите несколько секунд."
    except asyncio.TimeoutError:
        logger.warning(f"⏱️ Общий таймаут обработки запроса (45s): {user_text[:100]}")
        response_text = "⌛ Запрос обрабатывается слишком долго. Попробуйте переформулировать вопрос или подождите несколько секунд."
    except Exception as e:
        logger.error(f"❌ Ошибка при получении ответа от ядра ИИ: {e}", exc_info=True)
        response_text = f"⌛ Ошибка обработки запроса: {str(e)[:100]}. Попробуйте позже."

    # Визуальное оформление
    icon = "👩‍💼" if "Викт" in expert["name"] else "👨‍💻" if "Дмитр" in expert["name"] else "💼"

    # Сохраняем в контекст сессии (Singularity 8.0)
    try:
        from session_context_manager import get_session_context_manager

        context_manager = get_session_context_manager()
        await context_manager.save_to_context(
            user_id=str(user_id),
            expert_name=expert["name"],
            query=user_text,
            response=response_text,
        )
    except Exception as e:
        logger.debug(f"⚠️ [SESSION CONTEXT] Ошибка сохранения контекста: {e}")

    # Формируем сообщение
    message_text = f"{icon} *{expert['name']}:*\n\n{response_text}"
    logger.info(f"📨 Отправляю сообщение (длина: {len(message_text)}): {message_text[:150]}...")

    # Создаем inline кнопки для feedback (Singularity 8.0)
    # Используем callback_data с информацией о запросе и ответе
    import hashlib
    import time

    feedback_id = hashlib.md5(
        f"{user_id}_{expert['name']}_{user_text}_{int(time.time())}".encode()
    ).hexdigest()[:16]

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "👍",
                    "callback_data": f"feedback_{feedback_id}_positive_{user_id}_{expert['name']}",
                },
                {
                    "text": "👎",
                    "callback_data": f"feedback_{feedback_id}_negative_{user_id}_{expert['name']}",
                },
            ]
        ]
    }

    # Сохраняем feedback_id для последующей обработки callback
    # (можно использовать временное хранилище или БД)
    try:
        # Сохраняем mapping feedback_id -> (query, response) для обработки callback
        # Для простоты используем in-memory cache (можно улучшить через БД)
        if not hasattr(send_telegram_msg, "_feedback_cache"):
            send_telegram_msg._feedback_cache = {}
        send_telegram_msg._feedback_cache[feedback_id] = {
            "query": user_text,
            "response": response_text,
            "expert_name": expert["name"],
            "user_id": str(user_id),
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.debug(f"⚠️ [FEEDBACK] Ошибка сохранения feedback_id: {e}")
        reply_markup = None  # Отправляем без кнопок при ошибке

    # Отправляем ответ владельцу с кнопками feedback
    await send_telegram_msg(chat_id, message_text, reply_markup=reply_markup)


async def telegram_bridge():
    """Главный цикл опроса Telegram обновлений"""
    if not TG_TOKEN or not TG_TOKEN.strip():
        logger.warning(
            "⚠️ TG_TOKEN не задан (переменная окружения TG_TOKEN). Telegram шлюз не будет опрашивать API."
        )
        while True:
            await asyncio.sleep(3600)
    logger.info(f"🚀 Telegram шлюз v5.0 (Restored) запущен для пользователя {ALLOWED_USER_ID}...")
    offset = 0

    async with httpx.AsyncClient(timeout=30) as client:
        # Отправляем уведомление о запуске
        await send_telegram_msg(
            ALLOWED_USER_ID,
            "🤖 **Шлюз связи с экспертами ATRA восстановлен.**\n\nЯ на связи и готова к командам!",
        )

        while True:
            try:
                url = (
                    f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?offset={offset}&timeout=20"
                )
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            offset = update["update_id"] + 1
                            msg = update.get("message")
                            if msg:
                                user_id = msg.get("from", {}).get("id")
                                chat_id = msg["chat"]["id"]

                                if user_id != ALLOWED_USER_ID:
                                    continue

                                # Обработка голосовых сообщений (Singularity 8.0)
                                voice = msg.get("voice")
                                user_text = msg.get("text", "")

                                if voice:
                                    try:
                                        from voice_processor import get_voice_processor

                                        voice_processor = get_voice_processor()
                                        file_id = voice.get("file_id")
                                        downloaded_file = await voice_processor.download_voice_file(
                                            file_id
                                        )
                                        if downloaded_file:
                                            transcribed_text = (
                                                await voice_processor.transcribe_voice_message(
                                                    downloaded_file
                                                )
                                            )
                                            if transcribed_text:
                                                user_text = transcribed_text
                                                logger.info(
                                                    f"🎤 [VOICE PROCESSOR] Распознан текст: {transcribed_text[:100]}..."
                                                )
                                            os.unlink(downloaded_file)
                                    except Exception as e:
                                        logger.error(f"❌ [VOICE PROCESSOR] Ошибка: {e}")

                                # Обработка файлов/документов (Singularity 8.0)
                                document = msg.get("document")
                                if document and not user_text:
                                    try:
                                        from pathlib import Path

                                        from file_processor import get_file_processor

                                        file_processor = get_file_processor()
                                        file_id = document.get("file_id")
                                        file_name = document.get("file_name", "unknown")
                                        file_info_url = f"https://api.telegram.org/bot{TG_TOKEN}/getFile?file_id={file_id}"
                                        async with httpx.AsyncClient() as client:
                                            file_info_res = await client.get(file_info_url)
                                            if file_info_res.status_code == 200:
                                                file_info = file_info_res.json()
                                                file_path_tg = file_info.get("result", {}).get(
                                                    "file_path"
                                                )
                                                if file_path_tg:
                                                    download_url = f"https://api.telegram.org/file/bot{TG_TOKEN}/{file_path_tg}"
                                                    download_res = await client.get(download_url)
                                                    if download_res.status_code == 200:
                                                        import tempfile

                                                        with tempfile.NamedTemporaryFile(
                                                            delete=False,
                                                            suffix=Path(file_name).suffix,
                                                        ) as tmp_file:
                                                            tmp_file.write(download_res.content)
                                                            tmp_path = tmp_file.name
                                                        processed = (
                                                            await file_processor.process_file(
                                                                tmp_path
                                                            )
                                                        )
                                                        if processed:
                                                            file_text = processed.get("text", "")
                                                            user_text = f"Обработай содержимое файла {file_name}:\n\n{file_text[:2000]}"
                                                            logger.info(
                                                                f"📄 [FILE PROCESSOR] Обработан файл {file_name}"
                                                            )
                                                        os.unlink(tmp_path)
                                    except Exception as e:
                                        logger.error(f"❌ [FILE PROCESSOR] Ошибка: {e}")

                                if not user_text:
                                    continue

                                lower_text = user_text.lower().strip()
                                target_name = None

                                # Определение эксперта по ключевым словам
                                if any(x in lower_text for x in ["виктория", "вика"]):
                                    target_name = "Виктория"
                                    user_text = (
                                        user_text.replace("Виктория", "")
                                        .replace("Вика", "")
                                        .strip(", ")
                                        .strip()
                                    )
                                elif any(x in lower_text for x in ["владимир", "вова"]):
                                    target_name = "Владимир"
                                    user_text = (
                                        user_text.replace("Владимир", "")
                                        .replace("Вова", "")
                                        .strip(", ")
                                        .strip()
                                    )
                                elif any(x in lower_text for x in ["дмитрий", "дима"]):
                                    target_name = "Дмитрий"
                                    user_text = (
                                        user_text.replace("Дмитрий", "")
                                        .replace("Дима", "")
                                        .strip(", ")
                                        .strip()
                                    )
                                elif any(x in lower_text for x in ["мария", "маша"]):
                                    target_name = "Мария"
                                    user_text = (
                                        user_text.replace("Мария", "")
                                        .replace("Маша", "")
                                        .strip(", ")
                                        .strip()
                                    )

                                # Если префикса нет - Виктория по умолчанию
                                if not target_name:
                                    target_name = "Виктория"

                                # Обработка запроса в отдельной задаче
                                asyncio.create_task(
                                    handle_message(target_name, user_text, chat_id, user_id)
                                )

            except Exception as e:
                logger.error(f"Ошибка в цикле шлюза: {e}")
                await asyncio.sleep(5)

            await asyncio.sleep(0.2)


if __name__ == "__main__":
    check_single_instance()
    try:
        asyncio.run(telegram_bridge())
    except KeyboardInterrupt:
        logger.info("Шлюз остановлен вручную.")
    except Exception as e:
        logger.critical(f"Критическая ошибка запуска: {e}")
