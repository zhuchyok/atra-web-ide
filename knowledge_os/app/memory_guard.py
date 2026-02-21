"""
MemoryGuard — защита от OOM (Out of Memory).
[SINGULARITY 14.3] Мониторинг RAM и предотвращение падения контейнеров.
"""
import logging
import os
from typing import Dict, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)


class MemoryGuard:
    """Система контроля памяти для предотвращения OOMKilled."""

    def __init__(self, threshold_percent: float = 90.0):
        self.threshold_percent = float(os.getenv("MEMORY_GUARD_THRESHOLD", str(threshold_percent)))
        if PSUTIL_AVAILABLE:
            logger.info("MemoryGuard: порог срабатывания %s%%", self.threshold_percent)
        else:
            logger.debug("MemoryGuard: psutil не установлен, проверка памяти отключена")

    def check_memory(self) -> Dict[str, Any]:
        """
        Проверяет текущее состояние памяти.

        Returns:
            Dict с метриками и флагом is_safe.
        """
        if not PSUTIL_AVAILABLE:
            return {"percent": 0.0, "available_gb": 0.0, "total_gb": 0.0, "is_safe": True, "threshold": self.threshold_percent}
        mem = psutil.virtual_memory()
        is_safe = mem.percent < self.threshold_percent
        if not is_safe:
            logger.warning("MemoryGuard: критический уровень памяти: %s%% (порог: %s%%)", mem.percent, self.threshold_percent)
        return {
            "percent": mem.percent,
            "available_gb": mem.available / (1024**3),
            "total_gb": mem.total / (1024**3),
            "is_safe": is_safe,
            "threshold": self.threshold_percent,
        }

    @staticmethod
    def get_container_memory_usage() -> Optional[float]:
        """Пытается получить лимит памяти контейнера из cgroups."""
        try:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                usage = int(f.read())
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                limit = int(f.read())
            return (usage / limit) * 100
        except Exception:
            return None

def should_pause_heavy_task() -> bool:
    """Удобная функция для проверки перед запуском тяжелой задачи."""
    guard = MemoryGuard()
    status = guard.check_memory()
    
    # Также проверяем лимит контейнера, если мы в Docker
    container_usage = MemoryGuard.get_container_memory_usage()
    if container_usage and container_usage > guard.threshold_percent:
        logger.warning(f"🚨 [MEMORY GUARD] Лимит контейнера близок к исчерпанию: {container_usage:.1f}%")
        return True
        
    return not status["is_safe"]
