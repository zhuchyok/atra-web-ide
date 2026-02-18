import asyncio
import time
import logging
from typing import Callable, Any, Dict

logger = logging.getLogger("ShadowExecution")

class ShadowExecutionManager:
    """
    [SINGULARITY 14.0] Shadow Execution Manager
    Запускает новую версию кода параллельно с основной и сравнивает результаты.
    """
    
    def __init__(self):
        self.results = {}

    async def execute_shadow(self, 
                             task_id: str, 
                             primary_func: Callable, 
                             shadow_func: Callable, 
                             *args, **kwargs) -> Any:
        """
        Запускает обе функции. Возвращает результат основной, 
        но логирует производительность теневой.
        """
        start_time = time.perf_counter()
        
        # 1. Запуск основной функции
        primary_task = asyncio.create_task(primary_func(*args, **kwargs))
        
        # 2. Запуск теневой функции (в фоне, не блокируя основную)
        shadow_task = asyncio.create_task(shadow_func(*args, **kwargs))
        
        # Ждем основную
        primary_result = await primary_task
        primary_duration = time.perf_counter() - start_time
        
        # Ждем теневую (с таймаутом, чтобы не вешать систему)
        try:
            shadow_result = await asyncio.wait_for(shadow_task, timeout=primary_duration * 2)
            shadow_duration = time.perf_counter() - start_time
            
            self._compare_results(task_id, primary_result, shadow_result, primary_duration, shadow_duration)
        except Exception as e:
            logger.warning(f"⚠️ [SHADOW] Shadow task failed or timed out: {e}")
            
        return primary_result

    def _compare_results(self, task_id: str, p_res: Any, s_res: Any, p_dur: float, s_dur: float):
        """Сравнивает точность и скорость."""
        is_accurate = (p_res == s_res)
        speed_gain = (p_dur - s_dur) / p_dur * 100
        
        logger.info(f"📊 [SHADOW] Task {task_id} Comparison:")
        logger.info(f"   - Accuracy: {'✅ OK' if is_accurate else '❌ DIFF'}")
        logger.info(f"   - Speed Gain: {speed_gain:.2f}%")
        
        # В будущем: сохранение в базу для Recursive Learning
