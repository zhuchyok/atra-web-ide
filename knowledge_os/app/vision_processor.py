"""
Vision Processor
Обработка изображений локальными моделями (Moondream 3 Preview с MLX)
"""

import asyncio
import logging
import httpx
import base64
import os
import io
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image as PILImage
else:
    PILImage = Any

# Попытка импортировать PIL (Pillow)
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore

logger = logging.getLogger(__name__)

# Config
MOONDREAM_STATION_URL = os.getenv('MOONDREAM_STATION_URL', 'http://localhost:2020')
MOONDREAM_STATION_ENABLED = os.getenv('MOONDREAM_STATION_ENABLED', 'true').lower() == 'true'
# Fallback на Ollama (старый способ)
MAC_LLM_URL = os.getenv('MAC_LLM_URL', 'http://localhost:11434')
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL', 'http://localhost:11434')
VISION_MODEL = os.getenv('VISION_MODEL', 'moondream')

# Попытка импортировать moondream (для прямого использования)
try:
    import moondream as md
    MOONDREAM_AVAILABLE = True
except ImportError:
    MOONDREAM_AVAILABLE = False
    logger.warning(
        "⚠️ [VISION] moondream не установлен, будет использоваться только API. "
        "Установить: pip install moondream-station (уже в knowledge_os/requirements.txt)"
    )

class VisionProcessor:
    """
    Обработка изображений локальными моделями.
    Приоритет: Moondream Station (MLX) → Ollama → Fallback
    """
    
    def __init__(self):
        self.moondream_station_url = MOONDREAM_STATION_URL
        self.moondream_station_enabled = MOONDREAM_STATION_ENABLED
        self.moondream_client = None
        
        # Fallback узлы (Ollama)
        self.fallback_nodes = [
            {"name": "MacBook", "url": MAC_LLM_URL, "priority": 1},
            {"name": "Server", "url": SERVER_LLM_URL, "priority": 2}
        ]
        self.model = VISION_MODEL
        
        # Инициализация Moondream клиента (если доступен)
        if MOONDREAM_AVAILABLE and self.moondream_station_enabled:
            try:
                self.moondream_client = md.vl(endpoint=f"{self.moondream_station_url}/v1")
                logger.info(f"✅ [VISION] Moondream Station клиент инициализирован: {self.moondream_station_url}")
            except Exception as e:
                logger.warning(f"⚠️ [VISION] Не удалось инициализировать Moondream клиент: {e}")
                self.moondream_client = None
    
    def _prepare_image(self, image_path: Optional[str] = None, image_base64: Optional[str] = None):
        """Подготавливает PIL Image из пути или base64"""
        if not PIL_AVAILABLE:
            logger.error("❌ [VISION] PIL (Pillow) не установлен. Установите: pip install Pillow")
            return None
        
        try:
            if image_path:
                return Image.open(image_path)
            elif image_base64:
                # Декодируем base64
                if isinstance(image_base64, str):
                    # Убираем префикс data:image/...;base64, если есть
                    if ',' in image_base64:
                        image_base64 = image_base64.split(',')[1]
                    image_data = base64.b64decode(image_base64)
                else:
                    image_data = image_base64
                return Image.open(io.BytesIO(image_data))
            return None
        except Exception as e:
            logger.error(f"❌ [VISION] Ошибка подготовки изображения: {e}")
            return None
    
    async def _process_with_moondream_station(
        self,
        image: PILImage,
        prompt: str
    ) -> Optional[str]:
        """Обработка через Moondream Station (MLX)"""
        if not self.moondream_client:
            return None
        
        try:
            # Используем синхронный клиент в async контексте
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.moondream_client.query(image, prompt)
            )
            
            if result and isinstance(result, dict):
                answer = result.get("answer", "")
                if answer:
                    logger.info("✅ [VISION] Processed with Moondream Station (MLX)")
                    return answer
        except Exception as e:
            logger.warning(f"⚠️ [VISION] Moondream Station failed: {e}")
        
        return None
    
    async def _process_with_moondream_api(
        self,
        image: PILImage,
        prompt: str
    ) -> Optional[str]:
        """Обработка через Moondream Station REST API"""
        try:
            # Конвертируем изображение в base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.moondream_station_url}/v1/query",
                    json={
                        "image": image_base64,
                        "prompt": prompt
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "")
                    if answer:
                        logger.info("✅ [VISION] Processed with Moondream Station API (MLX)")
                        return answer
        except Exception as e:
            logger.warning(f"⚠️ [VISION] Moondream Station API failed: {e}")
        
        return None
    
    async def _process_with_ollama_fallback(
        self,
        image_base64: str,
        prompt: str,
        use_pdf_model: bool = False
    ) -> Optional[str]:
        """Fallback на Ollama с поддержкой разных моделей"""
        # Выбираем модель в зависимости от задачи
        if use_pdf_model:
            models_to_try = ["llava:7b", "moondream"]  # llava лучше для PDF
        else:
            models_to_try = ["moondream", "llava:7b"]  # moondream быстрее для обычных изображений
        
        for node in self.fallback_nodes:
            for model_name in models_to_try:
                try:
                    node_url = f"{node['url']}/api/generate"
                    
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            node_url,
                            json={
                                "model": model_name,
                                "prompt": prompt,
                                "images": [image_base64],
                                "stream": False
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json().get("response", "")
                            if result:
                                logger.info(f"✅ [VISION] Processed with Ollama {model_name} on {node['name']}")
                                return result
                except Exception as e:
                    logger.debug(f"⚠️ [VISION] Ollama {model_name} on {node['name']} failed: {e}")
                    continue
        
        return None
    
    async def process_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "Опиши это изображение"
    ) -> Optional[str]:
        """
        Обрабатывает изображение локальной vision моделью.
        Приоритет: Moondream Station (MLX) → Ollama → Fallback
        
        Args:
            image_path: Путь к файлу изображения
            image_base64: Base64 encoded изображение
            prompt: Промпт для анализа изображения
        
        Returns:
            Описание изображения или None
        """
        # Подготавливаем изображение
        image = self._prepare_image(image_path, image_base64)
        if not image:
            logger.error("❌ [VISION] No image provided or failed to load")
            return None
        
        # Приоритет 1: Moondream Station (MLX) - прямой клиент
        if self.moondream_client:
            result = await self._process_with_moondream_station(image, prompt)
            if result:
                return result
        
        # Приоритет 2: Moondream Station REST API
        if self.moondream_station_enabled:
            result = await self._process_with_moondream_api(image, prompt)
            if result:
                return result
        
        # Приоритет 3: Fallback на Ollama
        # Подготавливаем base64 для Ollama
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        result = await self._process_with_ollama_fallback(image_base64_str, prompt, use_pdf_model=False)
        if result:
            return result
        
        logger.error("❌ [VISION] All vision processors failed")
        return None
    
    async def analyze_code_screenshot(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Анализирует скриншот кода"""
        prompt = """
        Это скриншот кода. Проанализируй код и опиши:
        1. Что делает этот код?
        2. Есть ли ошибки?
        3. Как можно улучшить?
        Верни структурированный анализ.
        """
        return await self.process_image(image_path, image_base64, prompt)
    
    async def extract_text_from_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Извлекает текст из изображения"""
        prompt = "Извлеки весь текст из этого изображения. Верни только текст, без дополнительных комментариев."
        return await self.process_image(image_path, image_base64, prompt)
    
    async def process_pdf_page(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "Опиши содержимое этой страницы документа"
    ) -> Optional[str]:
        """Обрабатывает страницу PDF (использует llava:7b для лучшего качества)"""
        # Подготавливаем изображение
        image = self._prepare_image(image_path, image_base64)
        if not image:
            logger.error("❌ [VISION] No image provided or failed to load")
            return None
        
        # Приоритет 1: Moondream Station (MLX)
        if self.moondream_client:
            result = await self._process_with_moondream_station(image, prompt)
            if result:
                return result
        
        # Приоритет 2: Moondream Station REST API
        if self.moondream_station_enabled:
            result = await self._process_with_moondream_api(image, prompt)
            if result:
                return result
        
        # Приоритет 3: Ollama с llava:7b (лучше для PDF)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        image_base64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        result = await self._process_with_ollama_fallback(image_base64_str, prompt, use_pdf_model=True)
        if result:
            return result
        
        logger.error("❌ [VISION] All vision processors failed for PDF")
        return None
    
    async def describe_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Описывает изображение"""
        prompt = "Опиши это изображение подробно. Что на нем изображено?"
        return await self.process_image(image_path, image_base64, prompt)

# Singleton instance
_vision_processor_instance = None

def get_vision_processor() -> VisionProcessor:
    """Получает singleton instance vision processor"""
    global _vision_processor_instance
    if _vision_processor_instance is None:
        _vision_processor_instance = VisionProcessor()
    return _vision_processor_instance

