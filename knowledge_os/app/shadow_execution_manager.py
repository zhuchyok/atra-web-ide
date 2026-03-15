import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ShadowExecutionManager:
    """
    Shadow Execution Manager - система для фоновой проверки гипотез и оптимизаций.
    Позволяет запускать оптимизированный код параллельно с основным ("в тени")
    и сравнивать результаты по скорости и точности.
    """

    def __init__(self, redis_url: str = None):
        self.results = {}
        self.active_shadows = {}
        self._loop = asyncio.get_event_loop()

    async def run_shadow(
        self, task_id: str, original_func: Callable, shadow_func: Callable, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Запустить теневое выполнение.
        Возвращает результат оригинальной функции немедленно (или после выполнения),
        а теневая функция выполняется в фоне.
        """
        # 1. Запускаем оригинал
        start_orig = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(original_func):
                original_result = await original_func(*args, **kwargs)
            else:
                original_result = original_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"❌ [SHADOW] Ошибка в оригинальной функции: {e}")
            raise e
        orig_duration = time.perf_counter() - start_orig

        # 2. Запускаем тень в фоне
        shadow_task_id = f"shadow_{task_id}_{uuid.uuid4().hex[:8]}"
        asyncio.create_task(
            self._execute_and_compare(
                shadow_task_id, original_result, orig_duration, shadow_func, *args, **kwargs
            )
        )

        return original_result

    async def _execute_and_compare(
        self,
        shadow_id: str,
        original_result: Any,
        original_duration: float,
        shadow_func: Callable,
        *args,
        **kwargs,
    ):
        """Выполнить теневую функцию и сравнить с оригиналом."""
        start_shadow = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(shadow_func):
                shadow_result = await shadow_func(*args, **kwargs)
            else:
                shadow_result = shadow_func(*args, **kwargs)
            shadow_duration = time.perf_counter() - start_shadow

            # Сравнение результатов (базовое)
            # Для LLM ответов можно использовать семантическую близость, здесь — простое сравнение
            is_match = shadow_result == original_result

            comparison = {
                "shadow_id": shadow_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original": {"duration": original_duration, "status": "success"},
                "shadow": {
                    "duration": shadow_duration,
                    "status": "success",
                    "is_better_speed": shadow_duration < original_duration,
                    "is_match": is_match,
                },
                "improvement_percent": ((original_duration - shadow_duration) / original_duration)
                * 100
                if original_duration > 0
                else 0,
            }

            self.results[shadow_id] = comparison

            if comparison["shadow"]["is_better_speed"] and is_match:
                logger.info(
                    f"🚀 [SHADOW] Найдена оптимизация! {shadow_id} быстрее на {comparison['improvement_percent']:.1f}%"
                )
            elif not is_match:
                logger.warning(f"⚠️ [SHADOW] Результаты {shadow_id} не совпадают с оригиналом")

            # В будущем: запись в БД victoria_tasks для Mutation Engine
            await self._record_to_knowledge_base(comparison)

        except Exception as e:
            logger.error(f"❌ [SHADOW] Ошибка в теневой функции {shadow_id}: {e}")
            self.results[shadow_id] = {"status": "failed", "error": str(e)}

    async def _record_to_knowledge_base(self, comparison: Dict):
        """Записать результат сравнения в базу знаний для самообучения."""
        try:
            # Здесь будет интеграция с Knowledge OS
            pass
        except Exception:
            pass

    def get_results(self, limit: int = 10) -> List[Dict]:
        """Получить последние результаты теневых запусков."""
        return list(self.results.values())[-limit:]


_shadow_manager = None


def get_shadow_manager() -> ShadowExecutionManager:
    global _shadow_manager
    if _shadow_manager is None:
        _shadow_manager = ShadowExecutionManager()
    return _shadow_manager
