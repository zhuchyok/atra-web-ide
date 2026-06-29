"""
Vision Processor
Обработка изображений локальными моделями (Moondream 3 Preview с MLX)
"""

import asyncio
import base64
import io
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

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
MOONDREAM_STATION_URL = os.getenv("MOONDREAM_STATION_URL", "http://host.docker.internal:2020")
MOONDREAM_STATION_ENABLED = os.getenv("MOONDREAM_STATION_ENABLED", "true").lower() == "true"
# Fallback на Ollama (старый способ)
MAC_LLM_URL = os.getenv("MAC_LLM_URL", "http://localhost:11434")
SERVER_LLM_URL = os.getenv("SERVER_LLM_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "moondream")

# Попытка импортировать moondream (клиент для Moondream Station).
# Зависимости устанавливаются на этапе setup, не в рантайме (12-Factor, reproducible builds).
try:
    import moondream as md

    MOONDREAM_AVAILABLE = True
except ImportError:
    MOONDREAM_AVAILABLE = False
    md = None  # type: ignore
    _vision_setup_hint = (
        "Установите зависимости: bash knowledge_os/scripts/setup_knowledge_os.sh "
        "(или pip install moondream)"
    )
    if MOONDREAM_STATION_ENABLED:
        logger.debug("[VISION] moondream не установлен, используется API. %s", _vision_setup_hint)
    else:
        logger.warning("⚠️ [VISION] moondream не установлен, только API. %s", _vision_setup_hint)


class VisionProcessor:
    """
    Обработка изображений локальными моделями.
    Приоритет: Moondream Station (MLX) → Ollama → Fallback
    """

    def __init__(self):
        self.moondream_station_url = MOONDREAM_STATION_URL
        self.moondream_station_enabled = MOONDREAM_STATION_ENABLED
        self.moondream_client = None

        # [SINGULARITY 21.10] Принудительно отключаем Moondream Station в контейнере,
        # так как он недоступен по сети и вызывает задержки/ошибки.
        # Используем Ollama (moondream:latest) напрямую.
        if os.path.exists("/.dockerenv"):
            logger.info("🐳 [VISION] Running in Docker, prioritizing Ollama over Moondream Station")
            self.moondream_station_enabled = False

        # Fallback узлы (Ollama на Mac Studio)
        self.fallback_nodes = [
            {
                "name": "Mac Studio (Ollama)",
                "url": "http://host.docker.internal:11434",
                "priority": 1,
            }
        ]
        self.model = VISION_MODEL
        self._last_failure_log_ts: Dict[str, float] = {}
        self._failure_counts: Dict[str, int] = {}

        # Инициализация Moondream клиента (если доступен)
        if MOONDREAM_AVAILABLE and self.moondream_station_enabled:
            try:
                self.moondream_client = md.vl(endpoint=f"{self.moondream_station_url}/v1")
                logger.info(
                    f"✅ [VISION] Moondream Station клиент инициализирован: {self.moondream_station_url}"
                )
            except Exception as e:
                logger.warning(f"⚠️ [VISION] Не удалось инициализировать Moondream клиент: {e}")
                self.moondream_client = None

    def _log_throttled_warning(self, key: str, message: str, interval_sec: float = 600.0) -> None:
        """Prevent noisy repeated warnings for expected transient vision failures."""
        now = time.monotonic()
        prev = self._last_failure_log_ts.get(key, 0.0)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        if now - prev >= interval_sec:
            count = self._failure_counts.get(key, 1)
            logger.warning("%s (count=%s, window=%.0fs)", message, count, interval_sec)
            self._last_failure_log_ts[key] = now
            self._failure_counts[key] = 0

    def _prepare_image(self, image_path: Optional[str] = None, image_base64: Optional[str] = None):
        """Подготавливает PIL Image из пути или base64"""
        if not PIL_AVAILABLE:
            logger.error(
                "❌ [VISION] PIL (Pillow) не установлен. "
                "Для локальной работы с картинками: bash knowledge_os/scripts/install_pillow.sh"
            )
            return None

        # [DEBUG] Логируем входные данные
        if not image_path and not image_base64:
            logger.debug("⏩ [VISION] _prepare_image called with no image_path and no image_base64")
            return None

        try:
            if image_path:
                logger.debug(f"🔍 [VISION] Loading image from path: {image_path}")
                # [SINGULARITY 21.9] Проверка на Git LFS заглушки
                try:
                    if os.path.exists(image_path):
                        with open(image_path, "rb") as f:
                            # Читаем больше байт для надежной проверки LFS (минимум 100)
                            header = f.read(128)
                            if b"git-lfs" in header or b"github.com/spec/v1" in header:
                                logger.debug(f"⏩ [VISION] Skipping Git LFS pointer: {image_path}")
                                return None
                    else:
                        logger.warning(f"⚠️ [VISION] Image path does not exist: {image_path}")
                        return None
                except Exception as e:
                    logger.debug(f"⚠️ [VISION] Error checking LFS for {image_path}: {e}")

                return Image.open(image_path)
            elif image_base64:
                logger.debug(f"🔍 [VISION] Loading image from base64 (length: {len(image_base64)})")
                # Декодируем base64
                if isinstance(image_base64, str):
                    # Убираем префикс data:image/...;base64, если есть
                    if "," in image_base64:
                        image_base64 = image_base64.split(",")[1]
                    image_data = base64.b64decode(image_base64)
                else:
                    image_data = image_base64
                return Image.open(io.BytesIO(image_data))
            return None
        except Exception as e:
            logger.error(f"❌ [VISION] Ошибка подготовки изображения: {e}")
            return None

    async def _process_with_moondream_station(self, image: PILImage, prompt: str) -> Optional[str]:
        """Обработка через Moondream Station (MLX) или Ollama (fallback)"""
        # [SINGULARITY 21.10] Пытаемся использовать Ollama как основной vision-процессор,
        # так как Moondream Station (MLX) может быть недоступен из контейнера.

        # 1. Пытаемся через Ollama (moondream:latest)
        try:
            import base64
            from io import BytesIO

            buffered = BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            async with httpx.AsyncClient(timeout=60.0) as client:
                # Используем host.docker.internal для Ollama
                ollama_url = "http://host.docker.internal:11434/api/generate"
                response = await client.post(
                    ollama_url,
                    json={
                        "model": "moondream:latest",
                        "prompt": prompt,
                        "images": [img_str],
                        "stream": False,
                    },
                )
                if response.status_code == 200:
                    res_json = response.json()
                    answer = res_json.get("response")
                    if answer:
                        logger.info("✅ [VISION] Processed with Ollama (moondream:latest)")
                        return str(answer)
        except Exception as e:
            logger.debug(f"Ollama vision failed: {e}")

        # 2. Пытаемся через Moondream Station (MLX) как fallback
        if not self.moondream_client:
            return None

        try:
            loop = asyncio.get_event_loop()
            logger.debug(f"🔄 [VISION] Moondream query with prompt: {prompt[:50]}...")

            def run_query():
                try:
                    res = self.moondream_client.query(image, prompt, stream=True)
                    if isinstance(res, dict) and "answer" in res:
                        gen = res["answer"]
                        if hasattr(gen, "__iter__") and not isinstance(gen, (str, dict)):
                            return "".join([str(chunk) for chunk in gen])
                        return str(gen)
                    return None
                except Exception as e:
                    logger.debug(f"Query failed, trying caption: {e}")
                    res = self.moondream_client.caption(image, stream=True)
                    if isinstance(res, dict) and "caption" in res:
                        gen = res["caption"]
                        if hasattr(gen, "__iter__") and not isinstance(gen, (str, dict)):
                            return "".join([str(chunk) for chunk in gen])
                        return str(gen)
                    return None

            answer = await loop.run_in_executor(None, run_query)
            if answer:
                logger.info("✅ [VISION] Processed with Moondream Station (MLX)")
                return str(answer)

        except Exception as e:
            logger.warning(f"⚠️ [VISION] Moondream Station failed: {e} (Type: {type(e).__name__})")

        return None

    async def _process_with_moondream_api(self, image: PILImage, prompt: str) -> Optional[str]:
        """Обработка через Moondream Station REST API"""
        try:
            # Конвертируем изображение в base64
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.moondream_station_url}/v1/query",
                    json={"image": image_base64, "prompt": prompt},
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
        self, image_base64: str, prompt: str, use_pdf_model: bool = False
    ) -> Optional[str]:
        """Fallback на Ollama с поддержкой разных моделей"""
        # [OMNI-RAG] Используем moondream как основную модель для Ollama
        models_to_try = ["minicpm-v:latest"]  # единственная vision-модель, moondream images не поддерживает

        for node in self.fallback_nodes:
            for model_name in models_to_try:
                try:
                    # [DEBUG]
                    logger.debug(f"Trying Ollama model {model_name} on {node['url']}")
                    node_url = f"{node['url']}/api/generate"

                    async with httpx.AsyncClient(timeout=60.0) as client:
                        response = await client.post(
                            node_url,
                            json={
                                "model": model_name,
                                "prompt": prompt,
                                "images": [image_base64],
                                "stream": False,
                            },
                        )

                        if response.status_code == 200:
                            result = response.json().get("response", "")
                            if result:
                                logger.info(
                                    f"✅ [VISION] Processed with Ollama {model_name} on {node['name']}"
                                )
                                return result
                except Exception as e:
                    logger.debug(f"⚠️ [VISION] Ollama {model_name} on {node['name']} failed: {e}")
                    continue

        return None

    async def process_image(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "Опиши это изображение",
    ) -> Optional[str]:
        """
        Обрабатывает изображение локальной vision моделью.
        Приоритет: Ollama (moondream:latest) → Moondream Station (MLX) → Fallback

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
            logger.debug("[VISION] Skipping vision call: no image payload")
            return None

        # [SINGULARITY 21.10] Приоритет 1: Ollama (moondream:latest) через host.docker.internal
        # Это самый надежный способ из контейнера.
        try:
            logger.debug("🔄 [VISION] Attempting Ollama vision on host.docker.internal...")
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            async with httpx.AsyncClient(timeout=120.0) as client:  # Увеличен таймаут
                ollama_url = "http://host.docker.internal:11434/api/generate"
                response = await client.post(
                    ollama_url,
                    json={
                        "model": "moondream:latest",
                        "prompt": prompt,
                        "images": [img_str],
                        "stream": False,
                    },
                )
                if response.status_code == 200:
                    res_json = response.json()
                    answer = res_json.get("response")
                    if answer:
                        logger.info("✅ [VISION] Processed with Ollama (moondream:latest)")
                        return str(answer)
                else:
                    logger.debug(
                        f"Ollama vision returned status {response.status_code}: {response.text}"
                    )
        except Exception as e:
            logger.debug(f"Ollama vision failed: {e} (Type: {type(e).__name__})")

        # Приоритет 2: Moondream Station (MLX) - прямой клиент
        if self.moondream_client:
            result = await self._process_with_moondream_station(image, prompt)
            if result:
                return result

        # Приоритет 3: Moondream Station REST API
        if self.moondream_station_enabled:
            result = await self._process_with_moondream_api(image, prompt)
            if result:
                return result

        # Приоритет 4: Fallback на Ollama (старый способ с перебором нод)
        # Подготавливаем base64 для Ollama
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = await self._process_with_ollama_fallback(
            image_base64_str, prompt, use_pdf_model=False
        )
        if result:
            return result

        self._log_throttled_warning("vision_all_failed", "⚠️ [VISION] All vision processors failed")
        return None

    async def analyze_code_screenshot(
        self, image_path: Optional[str] = None, image_base64: Optional[str] = None
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
        self, image_path: Optional[str] = None, image_base64: Optional[str] = None
    ) -> Optional[str]:
        """Извлекает текст из изображения"""
        prompt = "Извлеки весь текст из этого изображения. Верни только текст, без дополнительных комментариев."
        return await self.process_image(image_path, image_base64, prompt)

    async def process_pdf_page(
        self,
        image_path: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "Опиши содержимое этой страницы документа",
    ) -> Optional[str]:
        """Обрабатывает страницу PDF (использует vision model)"""
        # Подготавливаем изображение
        image = self._prepare_image(image_path, image_base64)
        if not image:
            logger.debug("[VISION] Skipping PDF vision call: no image payload")
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

        # Приоритет 3: Ollama vision model
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = await self._process_with_ollama_fallback(
            image_base64_str, prompt, use_pdf_model=True
        )
        if result:
            return result

        self._log_throttled_warning(
            "vision_all_failed_pdf", "⚠️ [VISION] All vision processors failed for PDF"
        )
        return None

    async def describe_image(
        self, image_path: Optional[str] = None, image_base64: Optional[str] = None
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
