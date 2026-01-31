#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Victoria Telegram Bot - Интеграция Victoria с Telegram
Аналог Clawdbot для Victoria Agent

Использование:
    python -m src.agents.bridge.victoria_telegram_bot
"""

import os
import asyncio
import logging
import httpx
import base64
import io
from typing import Optional, List, Any
from datetime import datetime

# Инициализация logger в начале файла
logger = logging.getLogger(__name__)

# Попытка импортировать PIL для работы с изображениями
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("⚠️ PIL (Pillow) не установлен. Установите: pip install Pillow")

# PDF: только pypdf (легкая и достаточная для извлечения текста)
pypdf: Optional[Any] = None
try:
    import pypdf as _pypdf_mod  # type: ignore[reportMissingImports]
    pypdf = _pypdf_mod
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("⚠️ pypdf не установлен. Установите: pip install pypdf")

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
# Victoria URL - приоритет: из .env, затем удаленный сервер, затем localhost
VICTORIA_URL = os.getenv("VICTORIA_URL") or os.getenv("VICTORIA_REMOTE_URL", "http://localhost:8010")
# Альтернативные URL для fallback
VICTORIA_REMOTE_URL = os.getenv("VICTORIA_REMOTE_URL", "http://185.177.216.15:8010")  # Удаленный сервер
VICTORIA_LOCAL_URL = os.getenv("VICTORIA_LOCAL_URL", "http://localhost:8010")  # Локальный сервер

if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в переменных окружения!")
    logger.info("💡 Получите токен у @BotFather в Telegram")
    logger.info("💡 Добавьте в .env: TELEGRAM_BOT_TOKEN=your_token_here")

if not TELEGRAM_USER_ID:
    logger.error("❌ TELEGRAM_USER_ID не установлен в переменных окружения!")
    logger.info("💡 Узнайте свой ID: отправьте сообщение @userinfobot в Telegram")
    logger.info("💡 Добавьте в .env: TELEGRAM_USER_ID=your_user_id_here")


async def send_telegram_message(chat_id: str, text: str, parse_mode: Optional[str] = None) -> bool:
    """Отправка сообщения в Telegram с безопасной обработкой Markdown"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        # Используем Markdown только для коротких сообщений без проблемных символов
        if parse_mode == "Markdown" and len(text) < 1000:
            # Простое экранирование проблемных символов
            safe_text = text.replace("_", "\\_").replace("*", "\\*").replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)").replace("~", "\\~").replace("`", "\\`").replace(">", "\\>").replace("#", "\\#").replace("+", "\\+").replace("-", "\\-").replace("=", "\\=").replace("|", "\\|").replace("{", "\\{").replace("}", "\\}")
            payload["text"] = safe_text
            payload["parse_mode"] = "Markdown"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                return True
            else:
                # Если ошибка Markdown, пробуем без parse_mode
                if response.status_code == 400 and parse_mode:
                    logger.warning(f"⚠️ Ошибка Markdown, пробуем без parse_mode")
                    payload.pop("parse_mode", None)
                    payload["text"] = text  # Возвращаем оригинальный текст
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        return True
                
                logger.error(f"❌ Ошибка отправки в Telegram: {response.status_code} - {response.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return False


async def get_telegram_updates(offset: int = 0) -> tuple[int, list]:
    """Получение обновлений из Telegram"""
    if not TELEGRAM_BOT_TOKEN:
        return offset, []
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                params={
                    "offset": offset,
                    "timeout": 20
                }
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
        logger.debug(f"⏱️ Таймаут получения обновлений (это нормально)")
    except httpx.RequestError as e:
        logger.warning(f"⚠️ Ошибка сети при получении обновлений: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения обновлений: {type(e).__name__}: {e}", exc_info=True)
    
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
    
    return await send_to_victoria(enhanced_goal, project_context, chat_id)


async def send_to_victoria(goal: str, project_context: str = "atra-web-ide", chat_id: Optional[str] = None) -> Optional[str]:
    """Отправка задачи Victoria через API с автоматическим fallback и индикацией прогресса"""
    logger.info(f"📤 Отправка в Victoria ({VICTORIA_URL}): {goal[:100]}...")
    
    # Список URL для попыток (с fallback)
    urls_to_try = [
        VICTORIA_URL,
        VICTORIA_REMOTE_URL,
        VICTORIA_LOCAL_URL,
        "http://185.177.216.15:8010",  # Удаленный atra
        "http://185.177.216.15:8020",  # Удаленный atra-web-ide
    ]
    
    # Одно сообщение о старте на всю операцию (не при каждой попытке URL)
    if chat_id:
        await send_telegram_message(chat_id, "⏳ Отправляю запрос в Victoria...")
    
    # Одна задача прогресса на всю операцию — отменяется при первом ответе
    progress_task = None
    if chat_id:
        async def send_progress_updates():
            await asyncio.sleep(30)  # Одно обновление через 30 сек
            await send_telegram_message(chat_id, "⏳ Victoria обрабатывает запрос...")
            await asyncio.sleep(60)  # Второе обновление через 90 сек от старта
            await send_telegram_message(chat_id, "⏳ Еще работаю над задачей...")
        progress_task = asyncio.create_task(send_progress_updates())
    
    async def try_one_url(url: str) -> Optional[str]:
        """Один запрос к URL без своих сообщений в Telegram."""
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{url}/run",
                    json={
                        "goal": goal,
                        "project_context": project_context,
                        "max_steps": 500
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("output", "Задача выполнена")
                logger.error(f"❌ Victoria API ({url}): {response.status_code}")
                return None
        except httpx.TimeoutException:
            logger.error(f"⏱️ Таймаут при обращении к Victoria ({url}, 180 сек)")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка Victoria ({url}): {type(e).__name__}: {e}")
            return None
    
    try:
        for url in urls_to_try:
            if url == VICTORIA_URL:
                continue
            result = await try_one_url(url)
            if result:
                if progress_task:
                    progress_task.cancel()
                logger.info(f"📥 Ответ Victoria ({url}, первые 200 символов): {result[:200]}...")
                return result
        
        result = await try_one_url(VICTORIA_URL)
        if result:
            if progress_task:
                progress_task.cancel()
            return result
        
        if chat_id:
            await send_telegram_message(chat_id, "⏱️ Victoria недоступна или не ответила вовремя.")
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
    
    # Отправляем в Victoria
    project_context = "atra-web-ide"
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
        help_text = """
🤖 Victoria Telegram Bot

Доступные команды:
• /start или /help - показать это сообщение
• /status - статус Victoria
• /health - проверка здоровья системы

Или просто напишите задачу, и Victoria её выполнит!

Поддержка медиа:
• 📷 Фото - анализ через moondream
• 📄 PDF - обработка через llava:7b

Примеры:
• "Создай файл test.py"
• "Покажи список файлов"
• "Виктория, помоги с кодом"
• Отправь фото/PDF для анализа
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
            await send_telegram_message(chat_id, f"❌ Ошибка: {e}")
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
            await send_telegram_message(chat_id, f"❌ Ошибка: {e}")
        return
    
    # Обычное сообщение — отправляем в Victoria (одно сообщение о старте внутри send_to_victoria)
    # Извлекаем имя эксперта если есть
    project_context = "atra-web-ide"
    goal = text
    
    if text_lower.startswith("виктория"):
        goal = text[8:].strip(", ").strip()
    elif text_lower.startswith("вероника"):
        goal = text[8:].strip(", ").strip()
        project_context = "atra-web-ide"
    
    # Отправляем в Victoria с индикацией прогресса
    result = await send_to_victoria(goal, project_context, chat_id)
    
    if result:
        # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
        if len(result) > 4000:
            result = result[:4000] + "\n\n... (сообщение обрезано)"
        await send_telegram_message(chat_id, f"✅ Результат:\n\n{result}")
    else:
        await send_telegram_message(
            chat_id, 
            "❌ Не удалось выполнить задачу.\n\n"
            "Возможные причины:\n"
            "• Victoria недоступна (проверьте: curl http://localhost:8010/health)\n"
            "• Таймаут выполнения задачи\n"
            "• Ошибка в коде Victoria\n\n"
            "Проверьте логи: tail -f victoria_bot.log"
        )


async def telegram_bridge():
    """Главный цикл Telegram бота"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен! Бот не может работать.")
        return
    
    if not TELEGRAM_USER_ID:
        logger.error("❌ TELEGRAM_USER_ID не установлен! Бот не может работать.")
        return
    
    logger.info(f"🚀 Victoria Telegram Bot запущен")
    if TELEGRAM_USER_ID:
        logger.info(f"   👤 Пользователь: {TELEGRAM_USER_ID}")
    if TELEGRAM_CHAT_ID:
        logger.info(f"   💬 Группа: {TELEGRAM_CHAT_ID} (Bikos_Corporation)")
    logger.info(f"   🔗 Victoria URL: {VICTORIA_URL}")
    
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
                        asyncio.create_task(handle_telegram_message(user_id, chat_id, text, chat_type))
                    
                    # Обработка медиа (фото, документы)
                    elif "photo" in message or "document" in message:
                        logger.info(f"📷 Получено медиа от {user_id} в {chat_type} {chat_id}")
                        asyncio.create_task(handle_telegram_media(user_id, chat_id, message, chat_type))
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"❌ Ошибка в главном цикле: {e}")
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
