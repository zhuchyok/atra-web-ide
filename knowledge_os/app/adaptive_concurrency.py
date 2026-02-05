"""
Авто-расчёт параллелизма воркера по CPU/памяти и загрузке MLX/Ollama.
Согласовано с ADAPTIVE_WORKER_CONCURRENCY_PLAN.md, рекомендациями Backend/SRE/Performance.
Мировые практики: adaptive concurrency (Uber Cinnamon, Netflix), resource-based limits, backpressure.
"""
import asyncio
import os
import logging
import time
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Пороги (конфиг через env)
ADAPTIVE_HOST_RAM_THRESHOLD = float(os.getenv("ADAPTIVE_HOST_RAM_THRESHOLD", "0.85"))  # 85%
ADAPTIVE_HOST_CPU_THRESHOLD = float(os.getenv("ADAPTIVE_HOST_CPU_THRESHOLD", "0.85"))  # 85%
ADAPTIVE_RAM_CRITICAL = float(os.getenv("ADAPTIVE_RAM_CRITICAL", "0.90"))  # 90% — агрессивно снижать
ADAPTIVE_CALC_INTERVAL_SEC = int(os.getenv("ADAPTIVE_CALC_INTERVAL_SEC", "15"))
ADAPTIVE_OLLAMA_MAX = int(os.getenv("ADAPTIVE_OLLAMA_MAX", "10"))  # оценка слотов Ollama при здоровье
# Потолок одновременных запросов к MLX со стороны воркера (MLX нестабилен при высоком параллелизме — вылеты)
ADAPTIVE_MLX_SAFE_MAX = int(os.getenv("ADAPTIVE_MLX_SAFE_MAX", "2"))

# Кэш (не дёргать health на каждый цикл воркера)
_cache: Optional[Tuple[int, Dict]] = None


def _get_monitor():
    """Ленивый импорт resource_monitor (может быть недоступен в тестах)."""
    try:
        from resource_monitor import get_resource_monitor
        return get_resource_monitor()
    except ImportError:
        return None


async def get_effective_concurrent(
    n_max: int,
    n_min: int = 1,
    force_refresh: bool = False,
) -> Tuple[int, Dict]:
    """
    Рекомендуемое число задач «в работе» одновременно (N) по CPU/памяти и MLX/Ollama.

    Входы: n_max (потолок из SMART_WORKER_MAX_CONCURRENT), n_min (обычно 1).
    Выход: (effective_N, metrics_dict) для логов/метрик.
    Кэш: TTL ADAPTIVE_CALC_INTERVAL_SEC сек (рекомендация SRE — не перегружать health).
    """
    global _cache
    now = time.time()
    if not force_refresh and _cache is not None:
        cached_n, cached_ts = _cache[0], _cache[1].get("_ts", 0)
        if (now - cached_ts) < ADAPTIVE_CALC_INTERVAL_SEC:
            return cached_n, {**_cache[1], "_cached": True}

    monitor = _get_monitor()
    if monitor is None:
        # Режим без адаптива: фиксированный n_max (Backend: fallback)
        return n_max, {"_reason": "no_resource_monitor", "_ts": now}

    try:
        # Параллельно запросить host + MLX + Ollama (Performance: минимум задержек)
        system, mlx_health, ollama_health = await asyncio.gather(
            monitor.get_system_resources(),
            monitor.get_mlx_health(),
            monitor.get_ollama_health(),
        )
    except Exception as e:
        logger.warning("Adaptive concurrency: health check failed, using n_max: %s", e)
        return n_max, {"_reason": "health_error", "_error": str(e), "_ts": now}

    ram = system.get("ram", {}) or {}
    cpu = system.get("cpu", {}) or {}
    ram_percent = ram.get("used_percent", 0) or 0
    cpu_percent = cpu.get("percent", 0) or 0
    # Процент может быть 0-100 или 0-1
    if ram_percent <= 1:
        ram_percent *= 100
    if cpu_percent <= 1:
        cpu_percent *= 100

    # Ограничение по хосту (resource-based, мировые практики)
    n_cap_host = n_max
    if ram_percent >= ADAPTIVE_RAM_CRITICAL * 100:
        n_cap_host = 1
    elif ram_percent >= ADAPTIVE_HOST_RAM_THRESHOLD * 100:
        n_cap_host = max(1, n_max // 2)
    if cpu_percent >= ADAPTIVE_HOST_CPU_THRESHOLD * 100:
        n_cap_host = min(n_cap_host, max(1, n_max // 2))

    # MLX: свободных слотов (ограничиваем SAFE_MAX — MLX вылетает при высоком параллелизме)
    mlx_active = mlx_health.get("active_requests", 0) or 0
    mlx_reported = mlx_health.get("max_concurrent", 5) or 5
    mlx_max = min(mlx_reported, ADAPTIVE_MLX_SAFE_MAX)
    if mlx_health.get("status") == "healthy" and not mlx_health.get("is_overloaded", False):
        mlx_free = max(0, mlx_max - mlx_active)
    else:
        mlx_free = 0

    # Ollama: при перегрузке не нагружать; иначе — оценка слотов
    ollama_active = ollama_health.get("active_processes", 0) or 0
    if ollama_health.get("status") == "healthy" and not ollama_health.get("is_overloaded", False):
        ollama_cap = max(0, ADAPTIVE_OLLAMA_MAX - ollama_active)
        ollama_cap = min(ADAPTIVE_OLLAMA_MAX, ollama_cap + 2)  # небольшой запас
    else:
        ollama_cap = 0

    # Итоговый N (Backpressure: не больше, чем могут принять бэкенды + хост)
    n_raw = min(n_max, n_cap_host, mlx_free + ollama_cap)
    effective_n = max(n_min, min(n_max, n_raw))

    metrics = {
        "effective_concurrent": effective_n,
        "host_ram_percent": round(ram_percent, 1),
        "host_cpu_percent": round(cpu_percent, 1),
        "mlx_active": mlx_active,
        "mlx_max": mlx_max,
        "mlx_reported": mlx_reported,
        "mlx_free": mlx_free,
        "ollama_active": ollama_active,
        "ollama_cap": ollama_cap,
        "n_cap_host": n_cap_host,
        "_ts": now,
    }
    _cache = (effective_n, metrics)
    return effective_n, metrics


def is_model_heavy(model_name: Optional[str]) -> bool:
    """
    Тяжёлая модель (70b, 104b, 32b для reasoning/coding) — учитывать лимиты ADAPTIVE_MAX_HEAVY_*.
    Лёгкие: 3.8b, 3b, tiny. По плану: комбинировать тяжёлую на одном бэкенде и лёгкую на другом.
    """
    if not model_name:
        return False
    m = (model_name or "").lower()
    if ":70b" in m or ":104b" in m or "70b" in m or "104b" in m:
        return True
    if ":32b" in m or "32b" in m:
        # 32b можно считать тяжёлой для ограничения одновременных
        return True
    return False


async def check_backends_overload() -> Tuple[bool, str]:
    """
    Проверка перегрузки MLX и Ollama для backpressure (SRE, Елена).
    
    Возвращает (is_overloaded, reason).
    Если ОБА бэкенда перегружены — воркер не должен брать новые задачи.
    
    Мировые практики: Netflix concurrency-limits, Uber backpressure.
    """
    monitor = _get_monitor()
    if monitor is None:
        return False, ""  # Нет монитора — продолжать работу
    
    try:
        mlx_health, ollama_health = await asyncio.gather(
            monitor.get_mlx_health(),
            monitor.get_ollama_health(),
        )
    except Exception as e:
        logger.debug("Backpressure check failed: %s", e)
        return False, ""  # При ошибке — продолжать работу
    
    # Проверяем MLX
    mlx_overloaded = False
    mlx_reason = ""
    if mlx_health.get("status") != "healthy":
        mlx_overloaded = True
        mlx_reason = "MLX недоступен"
    elif mlx_health.get("is_overloaded", False):
        mlx_overloaded = True
        mlx_reason = f"MLX перегружен ({mlx_health.get('active_requests', 0)}/{mlx_health.get('max_concurrent', 5)})"
    else:
        mlx_active = mlx_health.get("active_requests", 0) or 0
        mlx_max = mlx_health.get("max_concurrent", 5) or 5
        if mlx_active >= mlx_max:
            mlx_overloaded = True
            mlx_reason = f"MLX на пределе ({mlx_active}/{mlx_max})"
    
    # Проверяем Ollama
    ollama_overloaded = False
    ollama_reason = ""
    if ollama_health.get("status") != "healthy":
        ollama_overloaded = True
        ollama_reason = "Ollama недоступен"
    elif ollama_health.get("is_overloaded", False):
        ollama_overloaded = True
        ollama_reason = f"Ollama перегружен"
    else:
        ollama_active = ollama_health.get("active_processes", 0) or 0
        if ollama_active >= ADAPTIVE_OLLAMA_MAX:
            ollama_overloaded = True
            ollama_reason = f"Ollama на пределе ({ollama_active}/{ADAPTIVE_OLLAMA_MAX})"
    
    # Backpressure только если ОБА бэкенда перегружены
    if mlx_overloaded and ollama_overloaded:
        combined_reason = f"{mlx_reason}; {ollama_reason}"
        return True, combined_reason
    
    # Если хотя бы один бэкенд свободен — продолжать работу
    return False, ""
