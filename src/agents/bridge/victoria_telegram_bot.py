#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Victoria Telegram Bot - Интеграция Victoria с Telegram
Аналог Clawdbot для Victoria Agent

Использование:
    python -m src.agents.bridge.victoria_telegram_bot
"""

import os
import sys
import asyncio
import logging
import httpx
import base64
import io
import time
from typing import Optional, List, Any, Dict, Set
from datetime import datetime, timezone
from pydantic import BaseModel

# Глобальный реестр для Health Check
_bot_health = {
    "last_heartbeat": None,
    "status": "starting",
    "errors": 0,
    "last_error": None,
    "processed_messages": 0
}

async def notify_victoria_heartbeat():
    """Уведомление Victoria о пульсе"""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(f"{VICTORIA_URL}/api/telegram/heartbeat", json=_bot_health)
    except Exception:
        pass

def update_heartbeat():
    """Обновление пульса бота для Health Check"""
    _bot_health["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
    _bot_health["status"] = "running"
    # Запускаем уведомление в фоне
    asyncio.create_task(notify_victoria_heartbeat())

def record_bot_error(error_msg: str):
    """Запись ошибки бота"""
    _bot_health["errors"] += 1
    _bot_health["last_error"] = f"{datetime.now(timezone.utc).isoformat()}: {error_msg}"
    _bot_health["status"] = "error"

def record_bot_message():
    """Запись обработанного сообщения"""
    _bot_health["processed_messages"] += 1

class BotHealthReport(BaseModel):
    last_heartbeat: Optional[str]
    status: str
    errors: int
    last_error: Optional[str]
    processed_messages: int
    up_since: str = datetime.now(timezone.utc).isoformat()

# Инициализация logger в начале файла
logger = logging.getLogger(__name__)

# Какой Python запускает бота — в него и ставить пакеты (иначе после перезапуска снова «не установлен»)
_PIP_CMD = f"{sys.executable} -m pip install Pillow pypdf"

# Попытка импортировать PIL для работы с изображениями
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("⚠️ PIL (Pillow) не установлен. Установите в окружении бота: %s", _PIP_CMD)

# PDF: только pypdf (легкая и достаточная для извлечения текста)
pypdf: Optional[Any] = None
try:
    import pypdf as _pypdf_mod  # type: ignore[reportMissingImports]
    pypdf = _pypdf_mod
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("⚠️ pypdf не установлен. Установите в окружении бота: %s", _PIP_CMD)

# Загрузка переменных из .env файла
def load_env_file():
    """Загружает переменные из .env файла"""
    env_path = os.path.join(os.path.dirname(__file__), "../../../.env")
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    # Удаляем комментарии после значения (всё после #)
                    if '#' in line:
                        line = line.split('#')[0].strip()
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value

# Загружаем .env перед использованием переменных
load_env_file()

# Telegram конфигурация
# Используем токен из telegram_simple.py или из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", "")
# Используем ID из telegram_simple.py или из переменных окружения
TELEGRAM_USER_ID = os.getenv("TELEGRAM_USER_ID") or os.getenv("ALLOWED_USER_ID", "")
# Chat ID группы Bikos_Corporation (если указан, бот будет работать в группе)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# Victoria URL: приоритет localhost (как для простых, так и для сложных запросов)
# Явно заданный VICTORIA_URL имеет приоритет, иначе — localhost, не 185
VICTORIA_LOCAL_URL = os.getenv("VICTORIA_LOCAL_URL", "http://localhost:8010")
VICTORIA_REMOTE_URL = os.getenv("VICTORIA_REMOTE_URL", "http://185.177.216.15:8010")
VICTORIA_URL = os.getenv("VICTORIA_URL") or VICTORIA_LOCAL_URL  # localhost по умолчанию, не 185
# Таймаут ожидания ответа Victoria (сек). Для сложных задач (проверка RAM, анализ кода) — увеличьте.
VICTORIA_POLL_TIMEOUT_SEC = int(os.getenv("VICTORIA_POLL_TIMEOUT_SEC", "900"))  # 15 мин по умолчанию
# Таймаут первого POST /run?async_mode=true: Victoria возвращает 202 после стратегии и understand_goal (1–3 мин).
# Если меньше — бот не получает 202, уходит в долгий sync и кажется что «завис».
VICTORIA_POST_RUN_TIMEOUT_SEC = int(os.getenv("VICTORIA_POST_RUN_TIMEOUT_SEC", "300"))  # 5 мин до 202

# Сессии чата: project_context и история per chat_id
_chat_sessions: Dict[str, dict] = {}
# Pending approvals (для будущего approval flow): approval_id -> {chat_id, action, created_at}
_pending_approvals: Dict[str, dict] = {}


def _get_session(chat_id: str) -> dict:
    if chat_id not in _chat_sessions:
        _chat_sessions[chat_id] = {"project_context": "atra-web-ide", "chat_history": []}
    return _chat_sessions[chat_id]


async def _set_bot_commands() -> bool:
    """Установить меню команд бота (появляется при нажатии /)"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "start", "description": "Начать / справка"},
        {"command": "help", "description": "Справка по командам"},
        {"command": "status", "description": "Статус Victoria"},
        {"command": "health", "description": "Проверка здоровья"},
        {"command": "project", "description": "Проект: /project atra-web-ide"},
        {"command": "models", "description": "Доступные модели MLX/Ollama"},
        {"command": "clear", "description": "Очистить историю чата"},
    ]
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={"commands": commands})
            if r.status_code == 200 and r.json().get("ok"):
                logger.info("✅ Меню команд бота установлено")
                return True
            logger.warning(f"⚠️ setMyCommands: {r.status_code} {r.text[:200]}")
    except Exception as e:
        logger.warning(f"⚠️ setMyCommands: {e}")
    return False

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в переменных окружения!")
    logger.info("💡 Получите токен у @BotFather в Telegram")
    logger.info("💡 Добавьте в .env: TELEGRAM_BOT_TOKEN=your_token_here")

if not TELEGRAM_USER_ID:
    logger.error("❌ TELEGRAM_USER_ID не установлен в переменных окружения!")
    logger.info("💡 Узнайте свой ID: отправьте сообщение @userinfobot в Telegram")
    logger.info("💡 Добавьте в .env: TELEGRAM_USER_ID=your_user_id_here")


def _escape_telegram_plain(text: str) -> str:
    """Очистка текста от управляющих символов для надёжной отправки (plain text)"""
    if not text:
        return text
    # Убираем null bytes и другие недопустимые символы
    return "".join(c for c in text if c != "\x00")


async def send_telegram_message(chat_id: str, text: str, parse_mode: Optional[str] = None, timeout: float = 10.0) -> bool:
    """Отправка сообщения в Telegram. По умолчанию plain text — без parse_mode.
    Ответы Victoria (код, markdown) отправляются только как plain text."""
    if not TELEGRAM_BOT_TOKEN:
        return False
    if not isinstance(text, str):
        text = str(text)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    text = _escape_telegram_plain(text)
    # Лимит Telegram 4096 символов
    if len(text) > 4096:
        text = text[:4090] + "\n\n...(обрезано)"
    
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                return True
            logger.error(f"❌ Ошибка отправки в Telegram: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return False


async def send_telegram_message_with_retry(chat_id: str, text: str, retries: int = 2) -> bool:
    """Отправка с повтором (для длинных ответов Victoria)."""
    timeout = 30.0 if len(text) > 2000 else 10.0
    for attempt in range(retries):
        if await send_telegram_message(chat_id, text, timeout=timeout):
            return True
        if attempt < retries - 1:
            await asyncio.sleep(1.0)
    return False


async def get_telegram_updates(offset: int = 0) -> tuple[int, list]:
    """Получение обновлений из Telegram. Retry при DNS/сетевых ошибках."""
    if not TELEGRAM_BOT_TOKEN:
        return offset, []
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={"offset": offset, "timeout": 25}
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        new_offset = offset
                        if updates:
                            new_offset = max(u["update_id"] for u in updates) + 1
                        return new_offset, updates
        except httpx.TimeoutException:
            logger.debug("⏱️ Таймаут getUpdates (нормально)")
        except httpx.RequestError as e:
            err_str = str(e)
            if "nodename nor servname" in err_str or "Errno 8" in err_str:
                logger.warning(f"⚠️ DNS/сеть: api.telegram.org недоступна (попытка {attempt + 1}/3)")
            else:
                logger.warning(f"⚠️ Ошибка сети: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка получения обновлений: {type(e).__name__}: {e}")
        if attempt < 2:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s backoff
    return offset, []


async def download_telegram_file(file_id: str) -> Optional[bytes]:
    """Скачивание файла из Telegram по file_id"""
    if not TELEGRAM_BOT_TOKEN:
        return None
    
    try:
        # Получаем информацию о файле
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params={"file_id": file_id})
            if response.status_code != 200:
                return None
            
            data = response.json()
            if not data.get("ok"):
                return None
            
            file_path = data["result"]["file_path"]
            
            # Скачиваем файл
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            file_response = await client.get(file_url, timeout=60.0)
            if file_response.status_code == 200:
                return file_response.content
    
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания файла: {e}")
        return None
    
    return None


def image_to_base64(image_bytes: bytes) -> str:
    """Конвертация изображения в base64"""
    try:
        return base64.b64encode(image_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"❌ Ошибка конвертации изображения: {e}")
        return ""


async def process_pdf(pdf_bytes: bytes) -> Optional[str]:
    """Извлечение текста из PDF"""
    if not PDF_AVAILABLE:
        return None
    
    try:
        if pypdf is None:
            return None
        pdf_file = io.BytesIO(pdf_bytes)
        reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip() or None
    except Exception as e:
        logger.error(f"❌ Ошибка обработки PDF: {e}")
        return None
    
    return None


async def send_to_victoria_with_media(goal: str, images_base64: Optional[List[str]] = None, pdf_text: Optional[str] = None, project_context: str = "atra-web-ide", chat_id: Optional[str] = None) -> Optional[str]:
    """Отправка задачи Victoria с медиа"""
    # Формируем goal с медиа
    media_context = ""
    
    if images_base64:
        media_context += f"\n\n[Прикреплено {len(images_base64)} изображение(й). Используй moondream для анализа скриншотов.]"
    
    if pdf_text:
        # Ограничиваем длину текста PDF (чтобы не перегружать контекст)
        pdf_preview = pdf_text[:2000] + "..." if len(pdf_text) > 2000 else pdf_text
        media_context += f"\n\n[Прикреплен PDF документ. Содержимое:\n{pdf_preview}]"
    
    enhanced_goal = goal + media_context
    
    return await send_to_victoria(enhanced_goal, project_context, chat_id, images_base64=images_base64)


async def send_to_victoria(goal: str, project_context: str = "atra-web-ide", chat_id: Optional[str] = None, chat_history: Optional[List[dict]] = None, images_base64: Optional[List[str]] = None) -> Optional[str]:
    """Отправка задачи Victoria через API с автоматическим fallback и индикацией прогресса"""
    # Обновляем пульс при активном взаимодействии
    update_heartbeat()
    logger.info(f"📤 Отправка в Victoria ({VICTORIA_URL}): {goal[:100]}...")

    # Список URL: сначала localhost (как простые), затем remote — чтобы и сложные шли через localhost
    _all = [VICTORIA_LOCAL_URL, VICTORIA_URL, VICTORIA_REMOTE_URL, "http://185.177.216.15:8010", "http://185.177.216.15:8020"]
    urls_to_try = list(dict.fromkeys(_all))  # порядок сохраняем, дубли убираем
    
    # Одно сообщение о старте на всю операцию (не при каждой попытке URL)
    # if chat_id:
    #     await send_telegram_message(chat_id, "⏳ Отправляю запрос в Victoria...")
    
    # Прогресс каждые 120 сек, отменяется при первом ответе
    progress_task = None
    poll_interval = 10  # Увеличено с 5 до 10, чтобы не спамить логи Victoria
    max_poll_time = max(300, VICTORIA_POLL_TIMEOUT_SEC)  # не менее 5 мин

    def _parse_run_output(data: dict) -> Optional[str]:
        """Извлечь output/response из ответа Victoria."""
        out = data.get("output") or data.get("response") or data.get("result")
        if out is not None:
            return str(out)
        if data.get("status") == "needs_clarification":
            qs = data.get("clarification_questions", [])
            return "Victoria уточняет: " + ("; ".join(qs) if qs else "Нужно уточнение.")
        return None

    async def try_one_url_async(url: str) -> Optional[str]:
        """Async mode: POST 202 → poll /run/status до completed. Fallback: 200 = sync ответ."""
        post_timeout = float(VICTORIA_POST_RUN_TIMEOUT_SEC)
        current_task_id = None
        try:
            async with httpx.AsyncClient(timeout=post_timeout) as client:
                max_steps = int(os.getenv("VICTORIA_MAX_STEPS", "50"))  # 50 — меньше «превышен лимит 500» на локальных моделях
                payload: dict = {
                    "goal": goal,
                    "project_context": project_context,
                    "max_steps": max_steps,
                }
                if chat_history:
                    payload["chat_history"] = [{"user": h.get("user", ""), "assistant": h.get("assistant", "")} for h in chat_history]
                if images_base64:
                    payload["images_base64"] = images_base64
                
                logger.info(f"POST {url}/run?async_mode=true")
                r = await client.post(f"{url}/run?async_mode=true", json=payload)
                # Fallback: Victoria без async_mode вернул 200 — сразу берём ответ
                if r.status_code == 200:
                    try:
                        data = r.json()
                        out = _parse_run_output(data)
                        if out:
                            logger.info(f"📥 Victoria sync 200 ({url}): ответ получен")
                            return out
                    except Exception as parse_e:
                        logger.warning(f"Victoria 200 parse error ({url}): {parse_e}")
                    return None
                if r.status_code != 202:
                    logger.error(f"❌ Victoria API async ({url}): {r.status_code}")
                    return None
                data = r.json()
                current_task_id = data.get("task_id")
                if not current_task_id:
                    return None
                if chat_id:
                    await send_telegram_message(
                        chat_id,
                        "⏳ Задача принята Victoria. Ответ обычно приходит в течение 1–3 мин (сложные запросы — дольше).",
                    )
            status_url = f"{url}/run/status/{current_task_id}"
            elapsed = 0
            while elapsed < max_poll_time:
                # ОБНОВЛЯЕМ ПУЛЬС ВО ВРЕМЯ ОЖИДАНИЯ
                update_heartbeat()
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                try:
                    async with httpx.AsyncClient(timeout=15.0) as c:
                        sr = await c.get(status_url)
                        if sr.status_code != 200:
                            continue
                        rec = sr.json()
                        st = rec.get("status", "")
                        if st == "completed":
                            return rec.get("output") or "Задача выполнена"
                        if st == "failed":
                            return rec.get("error") or "Ошибка выполнения"
                except Exception:
                    pass
            logger.error(f"⏱️ Victoria async ({url}): таймаут {max_poll_time}с")
            return None
        except Exception as e:
            # ConnectError при недоступном сервере — ожидаемо, логируем WARNING
            level = logger.warning if "Connect" in type(e).__name__ or "connection" in str(e).lower() else logger.error
            level("Victoria (%s): %s: %s", url, type(e).__name__, e)
            return None

    async def try_one_url_sync(url: str) -> Optional[str]:
        """Sync mode: POST без async_mode — для Victoria без поддержки async. Таймаут = VICTORIA_POLL_TIMEOUT_SEC."""
        try:
            max_steps = int(os.getenv("VICTORIA_MAX_STEPS", "50"))  # 50 — меньше «превышен лимит 500» на локальных моделях
            payload: dict = {
                "goal": goal,
                "project_context": project_context,
                "max_steps": max_steps,
            }
            if chat_history:
                payload["chat_history"] = [{"user": h.get("user", ""), "assistant": h.get("assistant", "")} for h in chat_history]
            if images_base64:
                payload["images_base64"] = images_base64
            async with httpx.AsyncClient(timeout=float(max_poll_time + 30)) as client:
                r = await client.post(f"{url}/run", json=payload)
                if r.status_code == 200:
                    data = r.json()
                    return _parse_run_output(data)
        except httpx.TimeoutException:
            logger.warning(f"⏱️ Victoria sync ({url}): таймаут {max_poll_time}с")
        except Exception as e:
            logger.warning("Victoria sync (%s): %s: %s", url, type(e).__name__, e)
        return None

    async def try_one_url(url: str) -> Optional[str]:
        """Сначала async, при неудаче — sync."""
        result = await try_one_url_async(url)
        if result:
            return result
        # Fallback: sync (если async не поддерживается или таймаут)
        return await try_one_url_sync(url)
    
    try:
        # Сначала пробуем основной URL (обычно localhost)
        result = await try_one_url(VICTORIA_URL)
        if result:
            if progress_task:
                progress_task.cancel()
            logger.info(f"📥 Ответ Victoria ({VICTORIA_URL}, первые 200 символов): {result[:200]}...")
            return result
        for url in urls_to_try:
            if url == VICTORIA_URL:
                continue
            result = await try_one_url(url)
            if result:
                if progress_task:
                    progress_task.cancel()
                logger.info(f"📥 Ответ Victoria ({url}, первые 200 символов): {result[:200]}...")
                return result

        # Не шлём сюда — вызывающий handle_telegram_message отправит одно итоговое сообщение при result is None
        return None
    finally:
        if progress_task:
            progress_task.cancel()


async def handle_telegram_media(user_id: str, chat_id: str, message: dict, chat_type: str = "private"):
    """Обработка медиа из Telegram (фото, документы)"""
    # Проверка авторизации (та же логика что и в handle_telegram_message)
    if chat_type == "private":
        if TELEGRAM_USER_ID and str(user_id) != str(TELEGRAM_USER_ID):
            return
    elif chat_type in ["group", "supergroup"]:
        if TELEGRAM_CHAT_ID and str(chat_id) != str(TELEGRAM_CHAT_ID):
            return
        if TELEGRAM_USER_ID and str(user_id) != str(TELEGRAM_USER_ID):
            return
    
    await send_telegram_message(chat_id, "⏳ Обрабатываю медиа...")
    
    text = message.get("caption", "") or "Проанализируй это изображение/документ"
    images_base64 = []
    pdf_text = None
    
    # Обработка фото
    if "photo" in message:
        photos = message["photo"]
        # Берем самое большое фото (последнее в списке)
        largest_photo = photos[-1]
        file_id = largest_photo.get("file_id")
        
        if file_id:
            logger.info(f"📷 Получено фото, file_id: {file_id}")
            file_bytes = await download_telegram_file(file_id)
            if file_bytes:
                base64_str = image_to_base64(file_bytes)
                if base64_str:
                    images_base64.append(base64_str)
                    logger.info(f"✅ Фото конвертировано в base64 ({len(base64_str)} символов)")
    
    # Обработка документов (PDF и другие)
    if "document" in message:
        document = message["document"]
        file_id = document.get("file_id")
        mime_type = document.get("mime_type", "")
        file_name = document.get("file_name", "")
        
        if file_id:
            logger.info(f"📄 Получен документ: {file_name} ({mime_type})")
            file_bytes = await download_telegram_file(file_id)
            
            if file_bytes:
                # Обработка PDF
                if mime_type == "application/pdf" or file_name.lower().endswith(".pdf"):
                    logger.info("📄 Обрабатываю PDF...")
                    pdf_text = await process_pdf(file_bytes)
                    if pdf_text:
                        logger.info(f"✅ Извлечен текст из PDF ({len(pdf_text)} символов)")
                    else:
                        await send_telegram_message(chat_id, "⚠️ Не удалось извлечь текст из PDF. Попробую обработать как изображение...")
                else:
                    await send_telegram_message(chat_id, f"⚠️ Файл {file_name} ({mime_type}) пока не поддерживается")
    
    session = _get_session(chat_id)
    project_context = session.get("project_context", "atra-web-ide")
    result = await send_to_victoria_with_media(text, images_base64, pdf_text, project_context, chat_id)
    
    if result:
        if len(result) > 4000:
            result = result[:4000] + "\n\n... (сообщение обрезано)"
        await send_telegram_message(chat_id, f"✅ Результат:\n\n{result}")
    else:
        await send_telegram_message(chat_id, "❌ Не удалось обработать медиа")


async def handle_telegram_message(user_id: str, chat_id: str, text: str, chat_type: str = "private"):
    """Обработка сообщения из Telegram"""
    # Проверка пользователя (для групп проверяем только если указан TELEGRAM_CHAT_ID)
    if chat_type == "private":
        # В личном чате проверяем user_id
        if TELEGRAM_USER_ID and str(user_id) != str(TELEGRAM_USER_ID):
            logger.warning(f"⚠️ Игнорирую сообщение от неизвестного пользователя: {user_id}")
            await send_telegram_message(chat_id, "❌ Доступ запрещен. Вы не авторизованы.")
            return
    elif chat_type in ["group", "supergroup"]:
        # В группе проверяем chat_id группы
        if TELEGRAM_CHAT_ID and str(chat_id) != str(TELEGRAM_CHAT_ID):
            logger.debug(f"ℹ️ Игнорирую сообщение из другой группы: {chat_id}")
            return
        # В группе также проверяем user_id (если указан)
        if TELEGRAM_USER_ID and str(user_id) != str(TELEGRAM_USER_ID):
            logger.debug(f"ℹ️ Игнорирую сообщение от пользователя {user_id} в группе")
            return
    
    # Обработка команд
    text_lower = text.lower().strip()
    
    if text_lower in ["/start", "/help"]:
        session = _get_session(chat_id)
        help_text = f"""
🤖 Victoria Telegram Bot

📋 Команды:
• /start, /help — эта справка
• /status — статус Victoria
• /health — проверка здоровья
• /project <имя> — сменить проект (сейчас: {session.get('project_context', 'atra-web-ide')})
• /models — доступные MLX/Ollama модели
• /clear — очистить историю чата

Или напишите задачу — Victoria выполнит!

📷 Медиа: фото, PDF — анализ

Примеры:
• Создай файл test.py
• Покажи список файлов
• Виктория, помоги с кодом
        """
        await send_telegram_message(chat_id, help_text)
        return
    
    if text_lower == "/status":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{VICTORIA_URL}/status")
                if response.status_code == 200:
                    status = response.json()
                    status_text = f"""
📊 Статус Victoria:

✅ Статус: {status.get('status', 'unknown')}
🤖 Агент: {status.get('agent', 'unknown')}
📚 Знаний: {status.get('knowledge_size', 0)}

Victoria Enhanced: {'✅ включен' if status.get('victoria_enhanced', {}).get('enabled') else '❌ выключен'}
                    """
                    await send_telegram_message(chat_id, status_text)
                else:
                    await send_telegram_message(chat_id, "❌ Не удалось получить статус Victoria")
        except Exception as e:
            logger.warning("Ошибка /status: %s", e)
            await send_telegram_message(chat_id, "❌ Victoria недоступна (сервер не отвечает)")
        return
    
    if text_lower == "/health":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{VICTORIA_URL}/health")
                if response.status_code == 200:
                    health = response.json()
                    health_text = f"""
🏥 Health Check:

Статус: {health.get('status', 'unknown')}
Агент: {health.get('agent', 'unknown')}
                    """
                    await send_telegram_message(chat_id, health_text)
                else:
                    await send_telegram_message(chat_id, "❌ Victoria недоступна")
        except Exception as e:
            logger.warning("Ошибка /health: %s", e)
            await send_telegram_message(chat_id, "❌ Victoria недоступна (сервер не отвечает)")
        return

    if text_lower.startswith("/project "):
        parts = text.split(None, 1)
        if len(parts) >= 2:
            new_project = parts[1].strip()
            session = _get_session(chat_id)
            session["project_context"] = new_project
            await send_telegram_message(chat_id, f"📁 Проект: {new_project}")
        else:
            session = _get_session(chat_id)
            await send_telegram_message(chat_id, f"📁 Текущий проект: {session.get('project_context', 'atra-web-ide')}\nИспользование: /project atra-web-ide")
        return

    if text_lower == "/models":
        urls_to_try = [VICTORIA_URL, VICTORIA_REMOTE_URL, VICTORIA_LOCAL_URL]
        for url in urls_to_try:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(f"{url}/api/available-models")
                    if r.status_code == 200:
                        data = r.json()
                        mlx = data.get("mlx", [])
                        ollama = data.get("ollama", [])
                        msg = "📦 Модели Victoria:\n\n"
                        if mlx:
                            msg += f"MLX ({len(mlx)}): {', '.join(mlx[:8])}" + ("..." if len(mlx) > 8 else "") + "\n"
                        else:
                            msg += "MLX: (нет)\n"
                        if ollama:
                            msg += f"Ollama ({len(ollama)}): {', '.join(ollama[:8])}" + ("..." if len(ollama) > 8 else "")
                        else:
                            msg += "Ollama: (нет)"
                        await send_telegram_message(chat_id, msg)
                        return
            except Exception:
                continue
        await send_telegram_message(chat_id, "❌ Victoria недоступна для /models")
        return

    if text_lower == "/clear":
        session = _get_session(chat_id)
        session["chat_history"] = []
        await send_telegram_message(chat_id, "🗑 История чата очищена")
        return

    if any(kw in text_lower for kw in ["как ты пришла", "почему такое решение", "раскрой логику", "покажи мысли"]):
        # [SUMMARY READER] Специальная команда для Telegram
        session_id = str(chat_id)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Пробуем получить скрытые мысли через API
                r = await client.get(f"{VICTORIA_URL}/api/hidden-thoughts/{session_id}")
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "success":
                        thoughts = data.get("thoughts", [])
                        msg = "🔓 **Внутренняя логика последнего решения:**\n\n"
                        for t in thoughts:
                            msg += f"🔹 *Шаг {t['step']}:* {t['thought']}\n"
                        await send_telegram_message(chat_id, msg)
                        return
        except Exception as e:
            logger.debug(f"Summary reader failed in TG: {e}")
        # Если не удалось получить через API, просто продолжаем (Victoria сама ответит через RAG)

    if text_lower.startswith("/approve_") or text_lower.startswith("/reject_"):
        action = "approve" if text_lower.startswith("/approve_") else "reject"
        pid = text_lower.split("_", 1)[-1].strip()
        if not pid:
            await send_telegram_message(chat_id, f"Использование: /{action}_<id>")
            return
        if pid not in _pending_approvals:
            await send_telegram_message(chat_id, "Нет ожидающих подтверждений (approval flow пока не активен)")
            return
        req = _pending_approvals.pop(pid)
        if action == "approve":
            await send_telegram_message(chat_id, f"✅ Подтверждено: {pid}")
        else:
            await send_telegram_message(chat_id, f"❌ Отклонено: {pid}")
        return

    # Обычное сообщение — отправляем в Victoria
    session = _get_session(chat_id)
    project_context = session.get("project_context", "atra-web-ide")
    goal = text

    if text_lower.startswith("виктория"):
        goal = text[8:].strip(", ").strip()
    elif text_lower.startswith("вероника"):
        goal = text[8:].strip(", ").strip()

    try:
        result = await send_to_victoria(goal, project_context, chat_id, session.get("chat_history"))
    except Exception as e:
        logger.exception("Ошибка при обращении к Victoria: %s", e)
        await send_telegram_message(
            chat_id,
            "❌ Внутренняя ошибка при обращении к Victoria. Проверьте victoria_bot.log"
        )
        return

    if result:
        if not isinstance(result, str):
            result = str(result)
        # Длинные ответы — разбиваем на части (лимит Telegram 4096, оставляем место под заголовок)
        chunk_size = 4000
        if len(result) <= chunk_size:
            result_trunc = result
            sent = await send_telegram_message_with_retry(chat_id, f"✅ Результат:\n\n{result_trunc}")
        else:
            parts = [result[i : i + chunk_size] for i in range(0, len(result), chunk_size)]
            sent = True
            for i, part in enumerate(parts[:5], 1):  # не более 5 сообщений
                prefix = f"✅ Результат ({i}/{len(parts)}):\n\n" if len(parts) > 1 else "✅ Результат:\n\n"
                if not await send_telegram_message_with_retry(chat_id, prefix + part):
                    sent = False
                    break
            if len(parts) > 5:
                await send_telegram_message(chat_id, f"... (ещё {len(parts) - 5} частей опущено)")
        if not sent:
            await send_telegram_message(chat_id, "⚠️ Результат получен, но не удалось отправить в Telegram. Попробуйте короче запрос или проверьте логи.")
        else:
            session["chat_history"].append({"user": goal, "assistant": result[:4000]})
            if len(session["chat_history"]) > 100:
                session["chat_history"].pop(0)
    else:
        await send_telegram_message(
            chat_id,
            "❌ Не удалось выполнить задачу.\n\n"
            "Возможные причины:\n"
            "• Victoria недоступна (сервер не отвечает — проверьте запущен ли victoria-agent)\n"
            f"• Таймаут выполнения (до {VICTORIA_POLL_TIMEOUT_SEC // 60} мин)\n"
            "• Ошибка в коде Victoria\n\n"
            "Для локальной проверки: curl http://localhost:8010/health"
        )


async def telegram_bridge():
    """Главный цикл Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен! Бот не может работать.")
        return
    
    if not TELEGRAM_USER_ID:
        logger.error("❌ TELEGRAM_USER_ID не установлен! Бот не может работать.")
        return
    
    # Регистрация в Victoria (если доступна)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{VICTORIA_URL}/api/telegram/register", json={"status": "online"})
    except Exception:
        pass

    logger.info(f"🚀 Victoria Telegram Bot запущен")
    if TELEGRAM_USER_ID:
        logger.info(f"   👤 Пользователь: {TELEGRAM_USER_ID}")
    if TELEGRAM_CHAT_ID:
        logger.info(f"   💬 Группа: {TELEGRAM_CHAT_ID} (Bikos_Corporation)")
    logger.info(f"   🔗 Victoria URL: {VICTORIA_URL}")

    await _set_bot_commands()
    update_heartbeat()

    # Отправляем приветственное сообщение
    try:
        # Если указан chat_id группы, отправляем туда, иначе в личный чат
        target_chat = TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else TELEGRAM_USER_ID
        if target_chat:
            await send_telegram_message(
                target_chat,
                "🤖 Victoria Telegram Bot запущен!\n\nЯ на связи и готова к командам!\n\nНапишите /help для списка команд."
            )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить приветственное сообщение: {e}")
    
    offset = 0
    
    while True:
        try:
            offset, updates = await get_telegram_updates(offset)
            
            for update in updates:
                update_heartbeat()
                message = update.get("message")
                if message:
                    user_id = str(message.get("from", {}).get("id", ""))
                    chat = message.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    chat_type = chat.get("type", "private")  # private, group, supergroup, channel
                    text = message.get("text", "")
                    
                    # Игнорируем сообщения из каналов
                    if chat_type == "channel":
                        continue
                    
                    # Обработка текстовых сообщений
                    if text:
                        logger.info(f"📨 Получено сообщение от {user_id} в {chat_type} {chat_id}: {text[:50]}...")
                        record_bot_message()
                        asyncio.create_task(handle_telegram_message(user_id, chat_id, text, chat_type))
                    
                    # Обработка медиа (фото, документы)
                    elif "photo" in message or "document" in message:
                        logger.info(f"📷 Получено медиа от {user_id} в {chat_type} {chat_id}")
                        record_bot_message()
                        asyncio.create_task(handle_telegram_media(user_id, chat_id, message, chat_type))
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в главном цикле: {e}")
            record_bot_error(str(e))
            await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        asyncio.run(telegram_bridge())
    except KeyboardInterrupt:
        logger.info("🛑 Victoria Telegram Bot остановлен")
