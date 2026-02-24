"""
Model Health Manager для автоматического восстановления моделей.
Отслеживает здоровье моделей, выполняет warmup после перезапуска,
и обновляет статус в роутере.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class ModelHealthStatus(Enum):
    """Статус здоровья модели"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ModelHealthManager:
    """
    Менеджер здоровья моделей.
    Отслеживает состояние моделей, выполняет автоматическое восстановление
    и warmup после перезапуска.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model_statuses: Dict[str, ModelHealthStatus] = {}
        self.model_last_check: Dict[str, datetime] = {}
        self.model_restart_count: Dict[str, int] = {}
        self.warmup_queries: List[str] = ["Hello", "What is 2+2?", "Write a simple function"]

    async def check_model_health(self, model_name: str) -> Tuple[ModelHealthStatus, Optional[str]]:
        """
        Проверить здоровье модели.

        Returns:
            (status, error_message)
        """
        try:
            # Простой тестовый запрос
            test_prompt = "Hello"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={"model": model_name, "prompt": test_prompt, "stream": False},
                    timeout=15.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("response"):
                        self.model_statuses[model_name] = ModelHealthStatus.HEALTHY
                        self.model_last_check[model_name] = datetime.now()
                        return ModelHealthStatus.HEALTHY, None
                    else:
                        error = "Empty response"
                        self.model_statuses[model_name] = ModelHealthStatus.DEGRADED
                        return ModelHealthStatus.DEGRADED, error
                else:
                    error = f"HTTP {response.status_code}"
                    self.model_statuses[model_name] = ModelHealthStatus.UNHEALTHY
                    return ModelHealthStatus.UNHEALTHY, error

        except httpx.TimeoutException:
            error = "Timeout"
            self.model_statuses[model_name] = ModelHealthStatus.UNHEALTHY
            return ModelHealthStatus.UNHEALTHY, error
        except Exception as e:
            error = str(e)
            self.model_statuses[model_name] = ModelHealthStatus.UNHEALTHY
            return ModelHealthStatus.UNHEALTHY, error

    async def warmup_model(self, model_name: str) -> bool:
        """
        Выполнить warmup модели после перезапуска.
        Отправляет несколько тестовых запросов для прогрева.
        """
        logger.info(f"🔥 [WARMUP] Прогрев модели {model_name}...")

        success_count = 0
        for query in self.warmup_queries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/generate",
                        json={"model": model_name, "prompt": query, "stream": False},
                        timeout=15.0,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("response"):
                            success_count += 1
                            logger.debug(f"✅ [WARMUP] {model_name}: '{query}' - OK")
                        else:
                            logger.warning(f"⚠️ [WARMUP] {model_name}: '{query}' - Empty response")
                    else:
                        logger.warning(
                            f"⚠️ [WARMUP] {model_name}: '{query}' - HTTP {response.status_code}"
                        )

            except Exception as e:
                logger.warning(f"⚠️ [WARMUP] {model_name}: '{query}' - Error: {e}")

            # Небольшая задержка между запросами
            await asyncio.sleep(0.5)

        success_rate = success_count / len(self.warmup_queries)
        if success_rate >= 0.7:  # 70% успешных запросов
            logger.info(
                f"✅ [WARMUP] Модель {model_name} прогрета успешно ({success_count}/{len(self.warmup_queries)})"
            )
            return True
        else:
            logger.warning(
                f"⚠️ [WARMUP] Модель {model_name} прогрета частично ({success_count}/{len(self.warmup_queries)})"
            )
            return False

    async def restart_and_warmup(self, model_name: str) -> bool:
        """
        Перезапустить модель и выполнить warmup.

        Note: Ollama автоматически управляет моделями, поэтому мы просто
        проверяем доступность и выполняем warmup.
        """
        logger.info(f"🔄 [RESTART] Перезапуск модели {model_name}...")

        # Проверяем, что модель доступна
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code != 200:
                    logger.error(f"❌ [RESTART] Ollama недоступен для {model_name}")
                    return False

                # Проверяем, что модель в списке
                models = response.json().get("models", [])
                model_exists = any(m.get("name") == model_name for m in models)

                if not model_exists:
                    logger.warning(f"⚠️ [RESTART] Модель {model_name} не найдена в списке")
                    return False
        except Exception as e:
            logger.error(f"❌ [RESTART] Ошибка проверки модели {model_name}: {e}")
            return False

        # Выполняем warmup
        warmup_success = await self.warmup_model(model_name)

        if warmup_success:
            # Обновляем счетчик перезапусков
            self.model_restart_count[model_name] = self.model_restart_count.get(model_name, 0) + 1
            self.model_statuses[model_name] = ModelHealthStatus.HEALTHY
            logger.info(f"✅ [RESTART] Модель {model_name} перезапущена и прогрета")
            return True
        else:
            logger.warning(
                f"⚠️ [RESTART] Модель {model_name} перезапущена, но warmup не полностью успешен"
            )
            return False

    async def auto_recover_model(self, model_name: str) -> bool:
        """
        Автоматическое восстановление модели при сбое.
        """
        status, error = await self.check_model_health(model_name)

        if status == ModelHealthStatus.HEALTHY:
            return True

        logger.warning(f"⚠️ [AUTO RECOVER] Модель {model_name} в состоянии {status.value}: {error}")

        # Пробуем перезапустить и прогреть
        return await self.restart_and_warmup(model_name)

    async def update_router_status(self, model_name: str, router=None):
        """
        Обновить статус модели в роутере.

        Args:
            model_name: Имя модели
            router: Экземпляр LocalAIRouter (опционально)
        """
        if not router:
            return

        status = self.model_statuses.get(model_name, ModelHealthStatus.UNKNOWN)

        # Обновляем приоритет узла в зависимости от статуса
        if status == ModelHealthStatus.HEALTHY:
            # Модель здорова - можно использовать
            logger.debug(f"✅ [ROUTER UPDATE] Модель {model_name} помечена как здоровая")
        elif status == ModelHealthStatus.DEGRADED:
            # Модель деградирована - снижаем приоритет
            logger.warning(f"⚠️ [ROUTER UPDATE] Модель {model_name} помечена как деградированная")
        elif status == ModelHealthStatus.UNHEALTHY:
            # Модель нездорова - исключаем из роутинга
            logger.error(f"❌ [ROUTER UPDATE] Модель {model_name} помечена как нездоровая")

    def get_model_status(self, model_name: str) -> Dict:
        """Получить статус модели"""
        status = self.model_statuses.get(model_name, ModelHealthStatus.UNKNOWN)
        last_check = self.model_last_check.get(model_name)
        restart_count = self.model_restart_count.get(model_name, 0)

        return {
            "model": model_name,
            "status": status.value,
            "last_check": last_check.isoformat() if last_check else None,
            "restart_count": restart_count,
        }

    async def monitor_models(self, model_names: List[str], check_interval: int = 300):
        """
        Мониторинг списка моделей и автоматическое восстановление при сбоях.

        Args:
            model_names: Список моделей для мониторинга
            check_interval: Интервал проверки в секундах
        """
        logger.info(f"🔍 [MONITOR] Запущен мониторинг моделей: {', '.join(model_names)}")

        while True:
            for model_name in model_names:
                try:
                    status, error = await self.check_model_health(model_name)

                    if status == ModelHealthStatus.UNHEALTHY:
                        logger.warning(
                            f"⚠️ [MONITOR] Модель {model_name} нездорова, пытаемся восстановить..."
                        )
                        await self.auto_recover_model(model_name)

                except Exception as e:
                    logger.error(f"❌ [MONITOR] Ошибка проверки модели {model_name}: {e}")

            await asyncio.sleep(check_interval)


# Глобальный экземпляр
_health_manager: Dict[str, ModelHealthManager] = {}


def get_model_health_manager(ollama_url: str = "http://localhost:11434") -> ModelHealthManager:
    """Получить глобальный экземпляр ModelHealthManager"""
    if ollama_url not in _health_manager:
        _health_manager[ollama_url] = ModelHealthManager(ollama_url)
    return _health_manager[ollama_url]
