"""
Voice Processor
Обработка голосовых команд (Speech-to-Text и Text-to-Speech)
Singularity 8.0: New Capabilities
"""

import asyncio
import logging
import os
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

TG_TOKEN = os.getenv('TG_TOKEN', '8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU')

class VoiceProcessor:
    """
    Процессор голосовых команд.
    Обрабатывает голосовые сообщения и синтезирует речь.
    """
    
    def __init__(self):
        """Инициализация процессора голоса"""
        # Можно использовать OpenAI Whisper API или локальную модель
        self.use_openai_whisper = os.getenv('USE_OPENAI_WHISPER', 'false').lower() == 'true'
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
    
    async def transcribe_voice_message(self, file_path: str) -> Optional[str]:
        """
        Распознает речь из голосового сообщения.
        
        Args:
            file_path: Путь к аудио файлу
        
        Returns:
            Распознанный текст или None при ошибке
        """
        try:
            if self.use_openai_whisper and self.openai_api_key:
                # Используем OpenAI Whisper API
                return await self._transcribe_with_openai(file_path)
            else:
                # Используем локальную модель (если доступна)
                return await self._transcribe_with_local(file_path)
        except Exception as e:
            logger.error(f"❌ [VOICE PROCESSOR] Ошибка распознавания речи: {e}")
            return None
    
    async def _transcribe_with_openai(self, file_path: str) -> Optional[str]:
        """Распознавание через OpenAI Whisper API"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(file_path, 'rb') as audio_file:
                    files = {'file': audio_file}
                    data = {'model': 'whisper-1'}
                    headers = {'Authorization': f'Bearer {self.openai_api_key}'}
                    
                    response = await client.post(
                        'https://api.openai.com/v1/audio/transcriptions',
                        files=files,
                        data=data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result.get('text', '')
                    else:
                        logger.error(f"❌ [VOICE PROCESSOR] OpenAI API error: {response.status_code}")
                        return None
        except Exception as e:
            logger.error(f"❌ [VOICE PROCESSOR] Ошибка OpenAI API: {e}")
            return None
    
    async def _transcribe_with_local(self, file_path: str) -> Optional[str]:
        """Распознавание через локальную модель (если доступна)"""
        # Можно использовать локальную модель Whisper через Ollama или другую библиотеку
        # Пока возвращаем None (требует дополнительной настройки)
        logger.warning("⚠️ [VOICE PROCESSOR] Локальное распознавание речи не настроено")
        return None
    
    async def synthesize_speech(self, text: str, language: str = 'ru') -> Optional[bytes]:
        """
        Синтезирует речь из текста.
        
        Args:
            text: Текст для синтеза
            language: Язык (ru, en, etc.)
        
        Returns:
            Аудио данные в формате OGG или None при ошибке
        """
        # Можно использовать TTS API (например, Yandex TTS, Google TTS)
        # Пока возвращаем None (требует дополнительной настройки)
        logger.warning("⚠️ [VOICE PROCESSOR] Синтез речи не настроен")
        return None
    
    async def download_voice_file(self, file_id: str) -> Optional[str]:
        """
        Скачивает голосовое сообщение из Telegram.
        
        Args:
            file_id: ID файла в Telegram
        
        Returns:
            Путь к скачанному файлу или None при ошибке
        """
        try:
            # Получаем информацию о файле
            file_info_url = f"https://api.telegram.org/bot{TG_TOKEN}/getFile?file_id={file_id}"
            async with httpx.AsyncClient() as client:
                file_info_res = await client.get(file_info_url)
                if file_info_res.status_code == 200:
                    file_info = file_info_res.json()
                    file_path_tg = file_info.get('result', {}).get('file_path')
                    
                    if file_path_tg:
                        # Скачиваем файл
                        download_url = f"https://api.telegram.org/file/bot{TG_TOKEN}/{file_path_tg}"
                        download_res = await client.get(download_url)
                        
                        if download_res.status_code == 200:
                            # Сохраняем временный файл
                            import tempfile
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as tmp_file:
                                tmp_file.write(download_res.content)
                                return tmp_file.name
        except Exception as e:
            logger.error(f"❌ [VOICE PROCESSOR] Ошибка скачивания файла: {e}")
            return None
        
        return None

# Singleton instance
_voice_processor_instance: Optional[VoiceProcessor] = None

def get_voice_processor() -> VoiceProcessor:
    """Получить singleton экземпляр процессора голоса"""
    global _voice_processor_instance
    if _voice_processor_instance is None:
        _voice_processor_instance = VoiceProcessor()
    return _voice_processor_instance

