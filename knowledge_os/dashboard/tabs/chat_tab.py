"""
Chat Tab Module - Modular chat interface for Victoria agent.
Follows Singularity 10.0 microservices standards.
"""
import streamlit as st
import httpx
import asyncio
import logging
import os
import sys
import json
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime, timezone

# Add app directory to path for RedisManager import
_DASHBOARD_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_KNOWLEDGE_OS_DIR = os.path.dirname(_DASHBOARD_DIR)
_APP_DIR = os.path.join(_KNOWLEDGE_OS_DIR, "app")

if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

try:
    from app.redis_manager import redis_manager
except ImportError:
    redis_manager = None
    logging.warning("RedisManager not available, using session state only")

logger = logging.getLogger(__name__)

# Victoria Agent URL (через Docker-сеть или localhost)
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://victoria-agent:8000")
# Fallback для локального запуска вне Docker
if not os.path.exists('/.dockerenv') and VICTORIA_URL == "http://victoria-agent:8000":
    VICTORIA_URL = "http://localhost:8010"

def _initialize_chat_session():
    """Инициализация состояния чата."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_session_id" not in st.session_state:
        import uuid
        st.session_state.chat_session_id = str(uuid.uuid4())

async def _send_message_to_victoria(message: str, history: List[Dict] = None) -> AsyncGenerator[str, None]:
    """Отправка сообщения в Victoria и получение потокового ответа."""
    payload = {
        "goal": message,
        "chat_history": history or [],
        "async_mode": False, # Для стриминга в UI используем синхронный вызов с генератором
        "project_context": "atra-web-ide"
    }
    
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            # Используем эндпоинт стриминга если он есть, иначе обычный /run
            # В текущей реализации victoria_server /run возвращает TaskResponse
            # Для реального стриминга нужен SSE эндпоинт /api/chat/stream
            response = await client.post(f"{VICTORIA_URL}/run", json=payload)
            if response.status_code == 200:
                data = response.json()
                yield data.get("output", "Нет ответа от агента.")
            else:
                yield f"❌ Ошибка агента: {response.status_code} - {response.text}"
    except Exception as e:
        logger.error(f"Error communicating with Victoria: {e}")
        yield f"❌ Ошибка связи с Victoria: {str(e)}"

def render_chat_tab():
    """Рендеринг вкладки чата."""
    st.header("💬 Чат с Викторией (Team Lead)")
    
    _initialize_chat_session()
    
    # Отображение истории
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Ввод сообщения
    if prompt := st.chat_input("Напишите задачу или вопрос для Виктории..."):
        # Добавляем сообщение пользователя
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Ответ ассистента
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            # Запуск асинхронного получения ответа
            async def get_response():
                nonlocal full_response
                # В данной версии используем упрощенный вызов (не SSE)
                async for chunk in _send_message_to_victoria(prompt, st.session_state.chat_messages[:-1]):
                    full_response += chunk
                    response_placeholder.markdown(full_response + "▌")
                response_placeholder.markdown(full_response)

            asyncio.run(get_response())
            
            # Сохраняем ответ
            st.session_state.chat_messages.append({"role": "assistant", "content": full_response})
            
            # Сохраняем в Redis для персистентности (опционально)
            if redis_manager:
                async def save_to_redis():
                    await redis_manager.set_cache(
                        f"chat_history:{st.session_state.chat_session_id}",
                        st.session_state.chat_messages,
                        ttl=3600*24
                    )
                try:
                    asyncio.run(save_to_redis())
                except Exception as e:
                    logger.warning(f"Failed to save chat to Redis: {e}")

    # Кнопка очистки
    if st.sidebar.button("🗑️ Очистить историю чата", key="clear_chat_sidebar"):
        st.session_state.chat_messages = []
        st.rerun()
