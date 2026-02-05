"""
MLX API Server для Mac Studio M4 Max
FastAPI сервер для обслуживания запросов от агентов через MLX модели
Устойчивый сервер с защитой от перегрузки, мониторингом памяти и автоматическим восстановлением
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import json
import os
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from mlx_lm import load, generate
import sys
import gc

# Добавляем путь к mlx_router для импорта
sys.path.insert(0, os.path.dirname(__file__))

# Настройка логирования в файл
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "mlx_api_server.log")

# Настройка логирования: и в консоль, и в файл
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"📝 Логирование MLX API Server: {log_file}")

# Импорт psutil с обработкой ошибок (после инициализации logger)
try:
    import psutil
except ImportError:
    psutil = None
    logger.warning("⚠️ psutil не установлен, мониторинг памяти будет ограничен")


@asynccontextmanager
async def _mlx_lifespan(app: FastAPI):
    """Startup: предзагрузка моделей и очистка кэша. Shutdown: очистка кэша (мировая практика: lifespan вместо on_event)."""
    asyncio.create_task(preload_models())
    if _cache_cleanup_interval_sec > 0:
        asyncio.create_task(periodic_cache_cleanup())
        logger.info(
            "🔄 Периодическая очистка кэша моделей каждые %ds (макс %d в кэше)",
            _cache_cleanup_interval_sec,
            _max_cached_models,
        )
    yield
    _models_cache.clear()
    logger.info("✅ Кэш моделей очищен (shutdown)")


app = FastAPI(title="MLX Model Server", version="2.0.0", lifespan=_mlx_lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Кэш загруженных моделей
# Структура: {model_key: {"model": model, "tokenizer": tokenizer, "loaded_at": datetime, "last_used": datetime, "use_count": int}}
_models_cache = {}

# Защита от перегрузки (настраивается через env — меньше 429, чаще успешные запросы)
_active_requests = 0
_max_concurrent_requests = int(os.getenv("MLX_MAX_CONCURRENT", "5"))
# Семафор: запросы ждут слот вместо немедленного 503 (дожидаются очереди)
_concurrent_semaphore = asyncio.Semaphore(_max_concurrent_requests)
# Таймаут ожидания слота: из env или макс по оценкам моделей (загрузка + инференс + запас)
_queue_wait_timeout = None  # задаётся через _max_queue_wait_timeout() после определения MODEL_TIME_ESTIMATES
_request_lock = threading.Lock()
_request_times = defaultdict(list)  # Для rate limiting
_rate_limit_window = int(os.getenv("MLX_RATE_LIMIT_WINDOW", "90"))  # секунд (увеличено окно — реже упираемся в лимит)
_rate_limit_max = int(os.getenv("MLX_RATE_LIMIT_MAX", "150"))  # макс запросов в окне (увеличено — меньше 429)

# Очередь запросов с приоритетами
try:
    from app.mlx_request_queue import get_request_queue, RequestPriority
    REQUEST_QUEUE_AVAILABLE = True
except ImportError:
    REQUEST_QUEUE_AVAILABLE = False
    logger.debug("ℹ️ MLX Request Queue не доступна, используем прямую обработку")

# Отслеживание активных запросов к моделям (защита от выгрузки используемых моделей)
_active_model_requests = defaultdict(int)  # {model_key: count} - сколько запросов обрабатывается для каждой модели
_model_locks = defaultdict(threading.Lock)  # Блокировки для каждой модели
_loading_models = set()  # Модели, которые сейчас загружаются

# Мониторинг памяти (можно задать через env, если 95% — норма для вашей нагрузки)
_memory_warning_threshold = float(os.getenv("MLX_MEMORY_WARNING_PERCENT", "85")) / 100.0
_memory_critical_threshold = float(os.getenv("MLX_MEMORY_CRITICAL_PERCENT", "95")) / 100.0
_last_memory_check = 0
_memory_check_interval = 10  # секунд

# Максимум моделей в кэше одновременно (остальные выгружаются по LRU) — снижает пиковое потребление RAM
# Одна большая модель (70b) ~40–50GB, 32b ~20GB; при 2 моделях в кэше пик существенно ниже
_max_cached_models = int(os.getenv("MLX_MAX_CACHED_MODELS", "2"))
# Интервал фоновой очистки кэша по LRU (секунды); 0 = отключить
_cache_cleanup_interval_sec = int(os.getenv("MLX_CACHE_CLEANUP_INTERVAL_SEC", "600"))

# Модели для предзагрузки при старте (можно изменить через MLX_PRELOAD_MODELS)
# По умолчанию только "fast" (~2.5GB), чтобы не держать 32b (~20GB) в памяти постоянно
# Пустое значение = без предзагрузки; "default,fast" = как раньше (больше RAM)
_preload_models_env = os.getenv("MLX_PRELOAD_MODELS", "fast")
_preload_models = [m.strip() for m in _preload_models_env.split(",") if m.strip()]

# Конфигурация моделей (пути к MLX моделям)
# Используем реальные имена директорий из ~/mlx-models/
MLX_BASE = os.path.expanduser("~/mlx-models")
MODEL_PATHS = {
    # Категории (для обратной совместимости)
    "reasoning": os.path.join(MLX_BASE, "deepseek-r1-distill-llama-70b"),
    "coding": os.path.join(MLX_BASE, "qwen2.5-coder-32b"),
    "fast": os.path.join(MLX_BASE, "phi3.5-mini-4k"),
    "tiny": os.path.join(MLX_BASE, "tinyllama-1.1b-chat"),
    "qwen_3b": os.path.join(MLX_BASE, "qwen2.5-3b"),
    "phi3_mini": os.path.join(MLX_BASE, "phi3-mini-4k"),
    "default": os.path.join(MLX_BASE, "qwen2.5-coder-32b"),
    # Модели из PLAN.md (Ollama имена → реальные директории)
    "command-r-plus:104b": os.path.join(MLX_BASE, "command-r-plus"),
    "deepseek-r1-distill-llama:70b": os.path.join(MLX_BASE, "deepseek-r1-distill-llama-70b"),
    "llama3.3:70b": os.path.join(MLX_BASE, "llama3.3-70b"),
    "qwen2.5-coder:32b": os.path.join(MLX_BASE, "qwen2.5-coder-32b"),
    "phi3.5:3.8b": os.path.join(MLX_BASE, "phi3.5-mini-4k"),
    "phi3:mini-4k": os.path.join(MLX_BASE, "phi3-mini-4k"),
    "qwen2.5:3b": os.path.join(MLX_BASE, "qwen2.5-3b"),
    "tinyllama:1.1b-chat": os.path.join(MLX_BASE, "tinyllama-1.1b-chat"),
}

# Можно также использовать переменную окружения
# По умолчанию используем ~/mlx-models/ (найденные модели)
MLX_MODELS_DIR = os.getenv('MLX_MODELS_DIR', os.path.expanduser("~/mlx-models"))

# Mapping категорий к моделям
CATEGORY_TO_MODEL = {
    "reasoning": "reasoning",
    "coding": "coding",
    "code": "coding",
    "fast": "fast",
    "tiny": "tiny",
    "default": "default"
}

# Маппинг категорий на реальные модели для предзагрузки
PRELOAD_MODEL_MAP = {
    "default": "qwen2.5-coder:32b",  # Основная модель по умолчанию
    "fast": "phi3.5:3.8b",  # Быстрая модель для общих задач
    # "tiny": "tinyllama:1.1b-chat",  # Исключена - только для внутренней коммуникации агентов
    "coding": "qwen2.5-coder:32b",  # Для кодинга
}

# Маппинг имен моделей из PLAN.md (Ollama формат) в MLX ключи
OLLAMA_TO_MLX_MAP = {
    "command-r-plus:104b": "command-r-plus:104b",
    "deepseek-r1-distill-llama:70b": "deepseek-r1-distill-llama:70b",
    "llama3.3:70b": "llama3.3:70b",
    "qwen2.5-coder:32b": "qwen2.5-coder:32b",
    "phi3.5:3.8b": "phi3.5:3.8b",
    "phi3:mini-4k": "phi3:mini-4k",
    "qwen2.5:3b": "qwen2.5:3b",
    "tinyllama:1.1b-chat": "tinyllama:1.1b-chat",
}

# Оценки времени по моделям: загрузка (сек), инференс (сек на 1k токенов), запас (сек).
# Таймаут запроса = load_sec + (max_tokens/1000 * inference_sec_per_1k) + margin_sec.
# Для неизвестной модели — fallback по размеру (104b/70b/32b/3b/1b) или default.
MODEL_TIME_ESTIMATES = {
    "default": {"load_sec": 60, "inference_sec_per_1k": 40, "margin_sec": 60},
    "command-r-plus:104b": {"load_sec": 180, "inference_sec_per_1k": 180, "margin_sec": 120},
    "deepseek-r1-distill-llama:70b": {"load_sec": 120, "inference_sec_per_1k": 120, "margin_sec": 120},
    "llama3.3:70b": {"load_sec": 120, "inference_sec_per_1k": 120, "margin_sec": 120},
    "reasoning": {"load_sec": 120, "inference_sec_per_1k": 120, "margin_sec": 120},
    "qwen2.5-coder:32b": {"load_sec": 60, "inference_sec_per_1k": 40, "margin_sec": 60},
    "coding": {"load_sec": 60, "inference_sec_per_1k": 40, "margin_sec": 60},
    "phi3.5:3.8b": {"load_sec": 25, "inference_sec_per_1k": 15, "margin_sec": 30},
    "phi3:mini-4k": {"load_sec": 25, "inference_sec_per_1k": 15, "margin_sec": 30},
    "fast": {"load_sec": 25, "inference_sec_per_1k": 15, "margin_sec": 30},
    "qwen2.5:3b": {"load_sec": 20, "inference_sec_per_1k": 12, "margin_sec": 25},
    "qwen_3b": {"load_sec": 20, "inference_sec_per_1k": 12, "margin_sec": 25},
    "tinyllama:1.1b-chat": {"load_sec": 10, "inference_sec_per_1k": 5, "margin_sec": 20},
    "tiny": {"load_sec": 10, "inference_sec_per_1k": 5, "margin_sec": 20},
}


def _get_estimates_for_model(model_key: str) -> dict:
    """Возвращает оценку времени для модели (exact или по размеру 104b/70b/32b/3b/1b)."""
    if model_key in MODEL_TIME_ESTIMATES:
        return MODEL_TIME_ESTIMATES[model_key].copy()
    # Fallback по размеру из имени (например llama3.3:70b уже есть, но на случай новых 70b)
    key_lower = model_key.lower()
    if "104b" in key_lower or "104" in key_lower:
        return {"load_sec": 180, "inference_sec_per_1k": 180, "margin_sec": 120}
    if "70b" in key_lower or "70" in key_lower:
        return {"load_sec": 120, "inference_sec_per_1k": 120, "margin_sec": 120}
    if "32b" in key_lower or "32" in key_lower:
        return {"load_sec": 60, "inference_sec_per_1k": 40, "margin_sec": 60}
    if "3b" in key_lower or "3.8" in key_lower or "4k" in key_lower:
        return {"load_sec": 25, "inference_sec_per_1k": 15, "margin_sec": 30}
    if "1b" in key_lower or "1.1" in key_lower:
        return {"load_sec": 10, "inference_sec_per_1k": 5, "margin_sec": 20}
    return MODEL_TIME_ESTIMATES["default"].copy()


def get_model_timeout_estimate(
    model_key: str,
    max_tokens: int,
    load_time_actual: Optional[float] = None,
) -> float:
    """
    Оценка полного таймаута запроса: загрузка модели + инференс + запас.
    load_time_actual — фактическое время последней загрузки (если модель уже в кэше).
    """
    est = _get_estimates_for_model(model_key)
    load = load_time_actual if load_time_actual is not None else est["load_sec"]
    inference = (max_tokens / 1000.0) * est["inference_sec_per_1k"]
    total = load + inference + est["margin_sec"]
    return max(60.0, total)  # минимум 1 минута


def _max_queue_wait_timeout() -> float:
    """Максимальный таймаут ожидания слота: из env или макс по всем моделям (загрузка + инференс 2k + запас)."""
    env_val = os.getenv("MLX_QUEUE_WAIT_TIMEOUT")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            pass
    max_sec = 300.0
    for key in MODEL_TIME_ESTIMATES:
        t = get_model_timeout_estimate(key, max_tokens=2048, load_time_actual=None)
        if t > max_sec:
            max_sec = t
    return max_sec


def _get_queue_wait_timeout() -> float:
    """Таймаут ожидания слота в middleware (ленивая инициализация)."""
    global _queue_wait_timeout
    if _queue_wait_timeout is None:
        _queue_wait_timeout = _max_queue_wait_timeout()
        logger.info("⏱️ Таймаут ожидания слота: %s с (модели: загрузка + инференс + запас)", _queue_wait_timeout)
    return _queue_wait_timeout


class GenerateRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    category: Optional[str] = None
    max_tokens: int = 512
    temperature: float = 0.7
    stream: bool = False


# Anthropic-compatible API models
class AnthropicMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str


class AnthropicMessagesRequest(BaseModel):
    model: str
    messages: List[AnthropicMessage]
    max_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False


class ChatMessage(BaseModel):
    """Сообщение для Ollama Chat API (/api/chat)"""
    role: str  # "user", "assistant", "system"
    content: str


class ChatRequest(BaseModel):
    """Запрос для Ollama Chat API (/api/chat)"""
    model: str
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    options: Optional[Dict] = None  # temperature, num_predict и др.


def check_memory() -> Dict[str, float]:
    """Проверка использования памяти"""
    if psutil is None:
        return {"used_percent": 0.0, "available_percent": 1.0, "total_gb": 0.0, "available_gb": 0.0}
    try:
        memory = psutil.virtual_memory()
        return {
            "total_gb": memory.total / (1024**3),
            "available_gb": memory.available / (1024**3),
            "used_percent": memory.percent / 100,
            "available_percent": memory.available / memory.total
        }
    except Exception as e:
        logger.warning(f"⚠️ Ошибка проверки памяти: {e}")
        return {"used_percent": 0.0, "available_percent": 1.0, "total_gb": 0.0, "available_gb": 0.0}


def evict_lru_to_limit(keep_max: int):
    """Выгружает наименее недавно используемые модели, пока в кэше не останется не более keep_max.
    Не трогает активные и недавно использованные (30 с). Вызывается перед загрузкой новой модели.
    """
    if keep_max < 1:
        keep_max = 1
    try:
        cache_keys = list(_models_cache.keys())
    except (RuntimeError, AttributeError):
        cache_keys = []
    if len(cache_keys) <= keep_max:
        return
    with _request_lock:
        active_models = {k for k, v in _active_model_requests.items() if v > 0}
        loading_models = _loading_models.copy()
    protected = active_models | loading_models
    now = datetime.now()
    for key in cache_keys:
        if key in protected:
            continue
        model_data = _models_cache.get(key)
        if not model_data:
            continue
        last_used = model_data.get("last_used")
        if isinstance(last_used, datetime) and (now - last_used).total_seconds() < 30:
            protected.add(key)
    candidates = [
        (k, _models_cache.get(k, {}).get("last_used") or datetime.min)
        for k in cache_keys
        if k not in protected and k in _models_cache
    ]
    candidates.sort(key=lambda x: x[1])
    evicted = 0
    while len(_models_cache) > keep_max and candidates:
        key = candidates.pop(0)[0]
        if key not in _models_cache:
            continue
        with _request_lock:
            if _active_model_requests.get(key, 0) > 0:
                continue
        del _models_cache[key]
        evicted += 1
        logger.info(f"🗑️ LRU выгрузка модели {key} (лимит кэша {keep_max})")
    if evicted:
        gc.collect()


def cleanup_unused_models(aggressive: bool = False, keep_count: int = 1):
    """Очистка неиспользуемых моделей при нехватке памяти (LRU стратегия)
    НЕ выгружает модели, которые используются прямо сейчас!
    
    Args:
        aggressive: Если True, выгружает ВСЕ неиспользуемые модели (экстренная очистка)
        keep_count: Сколько моделей оставить (по умолчанию 1 - самая используемая)
    """
    memory_info = check_memory()
    initial_used = memory_info["used_percent"]
    
    if memory_info["used_percent"] > _memory_critical_threshold or aggressive:
        logger.warning(f"🚨 Критическая нехватка памяти: {memory_info['used_percent']*100:.1f}%")
        
        # Проверяем, какие модели используются прямо сейчас
        with _request_lock:
            active_models = {k for k, v in _active_model_requests.items() if v > 0}
            loading_models = _loading_models.copy()
        
        protected_models = active_models | loading_models
        
        # КРИТИЧНО: Также защищаем модели, которые недавно использовались (в последние 30 секунд)
        # Это предотвращает выгрузку модели сразу после завершения генерации (конфликт Metal)
        now = datetime.now()
        # КРИТИЧНО: Создаем копию списка ключей, чтобы избежать RuntimeError при изменении словаря во время итерации
        try:
            cache_keys = list(_models_cache.keys())
        except (RuntimeError, AttributeError) as e:
            logger.warning(f"⚠️ Ошибка при получении ключей кэша: {e}")
            cache_keys = []
        
        for key in cache_keys:
            try:
                model_data = _models_cache.get(key)
                if not model_data:
                    continue
                last_used = model_data.get("last_used")
                if last_used and isinstance(last_used, datetime):
                    time_since_use = (now - last_used).total_seconds()
                    if time_since_use < 30:  # Защищаем модели, использованные в последние 30 секунд
                        protected_models.add(key)
            except (KeyError, AttributeError, TypeError) as e:
                logger.warning(f"⚠️ Ошибка при проверке модели {key}: {e}, пропускаем")
                continue
        
        if protected_models:
            logger.info(f"🛡️ Защищены от выгрузки (используются/недавно использовались): {protected_models}")
        
        if aggressive or memory_info["used_percent"] > 0.98:  # 98% - экстренная ситуация
            # Экстренная очистка: выгружаем только НЕИСПОЛЬЗУЕМЫЕ модели
            logger.error(f"🚨 ЭКСТРЕННАЯ ОЧИСТКА: выгружаем неиспользуемые модели из памяти")
            keys_to_remove = [k for k in _models_cache.keys() if k not in protected_models]
            
            if not keys_to_remove and protected_models:
                logger.warning(f"⚠️ Все модели используются! Нельзя выгрузить ни одну модель. Активные: {protected_models}")
                return  # Не можем ничего выгрузить
            
            for key in keys_to_remove:
                # КРИТИЧНО: Проверяем, нет ли активных генераций для этой модели
                try:
                    with _request_lock:
                        active_count = _active_model_requests.get(key, 0)
                        if active_count > 0:
                            logger.warning(f"⚠️ Пропускаем выгрузку модели {key} - есть активные генерации ({active_count})")
                            continue
                    
                    # КРИТИЧНО: Проверяем, что модель все еще в кэше перед удалением
                    if key in _models_cache:
                        del _models_cache[key]
                        logger.info(f"🗑️ Модель {key} выгружена из памяти (экстренная очистка)")
                except (KeyError, RuntimeError) as e:
                    logger.warning(f"⚠️ Ошибка при выгрузке модели {key}: {e}, пропускаем")
                    continue
        elif len(_models_cache) > keep_count:
            # LRU очистка: оставляем самые часто используемые модели + защищенные
            # Сортируем по use_count (по убыванию), затем по last_used (по убыванию)
            # КРИТИЧНО: Создаем копию items() для безопасной итерации
            try:
                cache_items = list(_models_cache.items())
            except (RuntimeError, AttributeError) as e:
                logger.warning(f"⚠️ Ошибка при получении items кэша: {e}")
                cache_items = []
            
            sorted_models = sorted(
                cache_items,
                key=lambda x: (x[1].get("use_count", 0) if x[1] else 0, x[1].get("last_used", datetime.min) if x[1] else datetime.min),
                reverse=True
            )
            
            # Оставляем keep_count самых используемых + все защищенные
            models_to_keep_keys = set()
            for k, v in sorted_models:
                if k in protected_models:
                    models_to_keep_keys.add(k)
                elif len(models_to_keep_keys) < keep_count:
                    models_to_keep_keys.add(k)
            
            keys_to_remove = [k for k in _models_cache.keys() if k not in models_to_keep_keys]
            
            if not keys_to_remove:
                logger.info(f"✅ Все модели защищены или необходимы, очистка не требуется")
                return
            
            for key in keys_to_remove:
                # КРИТИЧНО: Проверяем, нет ли активных генераций для этой модели
                try:
                    with _request_lock:
                        active_count = _active_model_requests.get(key, 0)
                        if active_count > 0:
                            logger.warning(f"⚠️ Пропускаем выгрузку модели {key} - есть активные генерации ({active_count})")
                            continue
                    
                    # КРИТИЧНО: Проверяем, что модель все еще в кэше перед удалением
                    if key in _models_cache:
                        model_data = _models_cache[key]
                        use_count = model_data.get('use_count', 0)
                        use_info = f" (использована {use_count} раз)" if use_count > 0 else ""
                        del _models_cache[key]
                        logger.info(f"🗑️ Модель {key} выгружена из памяти{use_info}")
                except (KeyError, RuntimeError) as e:
                    logger.warning(f"⚠️ Ошибка при выгрузке модели {key}: {e}, пропускаем")
                    continue
            
            logger.info(f"✅ Оставлены модели: {list(models_to_keep_keys)} (защищены: {list(protected_models)})")
        
        # Принудительная сборка мусора
        gc.collect()
        
        # Проверяем результат
        memory_info_after = check_memory()
        freed_percent = (initial_used - memory_info_after["used_percent"]) * 100
        logger.info(f"✅ Очистка памяти выполнена: освобождено {freed_percent:.1f}%, теперь {memory_info_after['used_percent']*100:.1f}%")


def get_model(model_key: str):
    """Получает или загружает модель с защитой от OOM и защитой от выгрузки"""
    model_lock = _model_locks[model_key]
    
    # КРИТИЧНО: Проверяем кэш ПЕРЕД блокировкой (быстрая проверка)
    if model_key in _models_cache:
        with model_lock:
            # Обновляем время последнего использования и счетчик
            _models_cache[model_key]["last_used"] = datetime.now()
            _models_cache[model_key]["use_count"] = _models_cache[model_key].get("use_count", 0) + 1
            logger.debug(f"📦 Модель {model_key} уже в кэше (использована {_models_cache[model_key]['use_count']} раз)")
            return _models_cache[model_key]
    
    with model_lock:
        # Проверяем кэш еще раз после получения блокировки (на случай, если модель загрузилась пока ждали)
        if model_key in _models_cache:
            _models_cache[model_key]["last_used"] = datetime.now()
            _models_cache[model_key]["use_count"] = _models_cache[model_key].get("use_count", 0) + 1
            logger.debug(f"📦 Модель {model_key} появилась в кэше пока ждали блокировку")
            return _models_cache[model_key]
        
        # Проверяем, не загружается ли модель уже другим запросом
        if model_key in _loading_models:
            # Модель уже загружается другим запросом - ждем
            logger.warning(f"⏳ Модель {model_key} уже загружается другим запросом, ожидание...")
            # Освобождаем блокировку и ждем
            max_wait = 60  # Максимум 60 секунд ожидания
            waited = 0
            while model_key in _loading_models and waited < max_wait:
                model_lock.release()
                time.sleep(0.5)  # time уже импортирован в начале файла
                waited += 0.5
                model_lock.acquire()
                # Проверяем, появилась ли модель в кэше
                if model_key in _models_cache:
                    _models_cache[model_key]["last_used"] = datetime.now()
                    _models_cache[model_key]["use_count"] = _models_cache[model_key].get("use_count", 0) + 1
                    logger.info(f"✅ Модель {model_key} загружена другим запросом, используем из кэша")
                    return _models_cache[model_key]
            
            # Если модель все еще не загружена, проверяем еще раз
            if model_key in _models_cache:
                _models_cache[model_key]["last_used"] = datetime.now()
                _models_cache[model_key]["use_count"] = _models_cache[model_key].get("use_count", 0) + 1
                return _models_cache[model_key]
            
            if model_key in _loading_models:
                raise RuntimeError(f"Модель {model_key} не загрузилась за {max_wait} секунд")
        
        # КРИТИЧНО: Metal (Apple GPU) не поддерживает одновременную загрузку и генерацию
        # Проверяем, нет ли активных генераций ДРУГИХ моделей (не той, которую загружаем)
        # Если активная генерация использует ту же модель - это нормально (модель уже загружена)
        with _request_lock:
            # Активные генерации ДРУГИХ моделей (не той, которую загружаем)
            other_models_active = {
                k: v for k, v in _active_model_requests.items() 
                if k != model_key and v > 0
            }
            active_other_count = sum(other_models_active.values())
            
            if active_other_count > 0:
                # Есть активные генерации ДРУГИХ моделей - откладываем загрузку
                other_models = list(other_models_active.keys())
                logger.warning(
                    f"⏳ Активные генерации других моделей ({active_other_count}: {other_models}), "
                    f"откладываем загрузку модели {model_key} для предотвращения конфликта Metal"
                )
                # Освобождаем блокировку и ждем
                max_wait_metal = 120  # Максимум 2 минуты ожидания
                waited_metal = 0
                while active_other_count > 0 and waited_metal < max_wait_metal:
                    model_lock.release()
                    time.sleep(1.0)
                    waited_metal += 1.0
                    model_lock.acquire()
                    # Проверяем кэш еще раз
                    if model_key in _models_cache:
                        _models_cache[model_key]["last_used"] = datetime.now()
                        _models_cache[model_key]["use_count"] = _models_cache[model_key].get("use_count", 0) + 1
                        logger.info(f"✅ Модель {model_key} появилась в кэше пока ждали")
                        return _models_cache[model_key]
                    # Обновляем счетчик активных генераций других моделей
                    other_models_active = {
                        k: v for k, v in _active_model_requests.items() 
                        if k != model_key and v > 0
                    }
                    active_other_count = sum(other_models_active.values())
                
                if active_other_count > 0:
                    other_models = list(other_models_active.keys())
                    raise RuntimeError(
                        f"Не удалось загрузить модель {model_key}: активные генерации других моделей "
                        f"({other_models}) не завершились за {max_wait_metal}с"
                    )
        
        # Перед загрузкой новой модели — выгружаем по LRU, чтобы в кэше было не больше MLX_MAX_CACHED_MODELS
        evict_lru_to_limit(_max_cached_models - 1)
        
        # Отмечаем, что модель загружается (защита от выгрузки и от параллельной загрузки)
        _loading_models.add(model_key)
        
        try:
            # Проверка памяти перед загрузкой
            memory_info = check_memory()
            if memory_info["used_percent"] > _memory_warning_threshold:
                logger.warning(f"⚠️ Высокое использование памяти: {memory_info['used_percent']*100:.1f}%")
                cleanup_unused_models()
            
            model_path = MODEL_PATHS.get(model_key)
            if not model_path:
                # Пробуем найти в MLX_MODELS_DIR
                model_path = os.path.join(MLX_MODELS_DIR, model_key)
            
            if not model_path or not os.path.exists(model_path):
                logger.error(f"❌ Модель {model_key} не найдена по пути {model_path}")
                raise ValueError(f"Model {model_key} not found at {model_path}")
            
            # Проверка памяти перед загрузкой новой модели
            memory_info = check_memory()
            if memory_info["used_percent"] > _memory_critical_threshold:
                cleanup_unused_models()
                memory_info = check_memory()
                if memory_info["used_percent"] > _memory_critical_threshold:
                    raise RuntimeError(f"Недостаточно памяти для загрузки модели: {memory_info['used_percent']*100:.1f}% используется")
            
            logger.info(f"🔄 Загрузка модели: {model_key} из {model_path} (память: {memory_info['used_percent']*100:.1f}%)")
            load_start = time.time()
            model, tokenizer = load(model_path)
            load_duration = time.time() - load_start
            
            _models_cache[model_key] = {
                "model": model,
                "tokenizer": tokenizer,
                "loaded_at": datetime.now(),
                "last_used": datetime.now(),
                "use_count": 1,
                "load_time_seconds": load_duration
            }
            
            logger.info(f"✅ Модель загружена: {model_key} (загрузка заняла {load_duration:.2f}с)")
            return _models_cache[model_key]
        except MemoryError as e:
            logger.error(f"❌ Нехватка памяти при загрузке модели {model_key}: {e}")
            # Экстренная очистка при MemoryError
            cleanup_unused_models(aggressive=True)
            memory_info = check_memory()
            raise HTTPException(
                status_code=503, 
                detail=f"Insufficient memory to load model: {str(e)}. Memory usage: {memory_info['used_percent']*100:.1f}%"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при получении модели {model_key}: {e}", exc_info=True)
            raise
        finally:
            # Убираем из списка загружающихся
            _loading_models.discard(model_key)


# Middleware для rate limiting и мониторинга
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting и мониторинг запросов"""
    global _active_requests, _request_times
    
    # Проверка rate limit
    now = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    with _request_lock:
        # Очистка старых запросов
        _request_times[client_ip] = [
            t for t in _request_times[client_ip] 
            if now - t < _rate_limit_window
        ]
        
        # Проверка лимита
        if len(_request_times[client_ip]) >= _rate_limit_max:
            logger.warning(f"⚠️ Rate limit превышен для {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"error": f"Rate limit exceeded. Max {_rate_limit_max} requests per {_rate_limit_window} seconds"}
            )
        
        _request_times[client_ip].append(now)
    
    # Health/read-only не занимают слот генерации — иначе при одной долгой генерации 70b все проверки ждут и падают по таймауту
    path = request.url.path or ""
    skip_semaphore = path in ("/", "/health", "/api/tags") or path.rstrip("/") in ("", "/health", "/api/tags")
    
    if skip_semaphore:
        return await call_next(request)
    
    queue_wait = _get_queue_wait_timeout()
    try:
        await asyncio.wait_for(_concurrent_semaphore.acquire(), timeout=queue_wait)
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ Ожидание слота превысило {queue_wait}с, отклоняем запрос")
        return JSONResponse(
            status_code=503,
            content={"error": f"Server overloaded. Waited {int(queue_wait)}s for slot. Max {_max_concurrent_requests} concurrent requests"}
        )
    with _request_lock:
        _active_requests += 1
    try:
        response = await call_next(request)
        return response
    finally:
        with _request_lock:
            _active_requests -= 1
        _concurrent_semaphore.release()


@app.get("/")
async def root():
    """Health check с детальной информацией"""
    memory_info = check_memory()
    return {
        "status": "online",
        "server": "MLX Model Server",
        "version": "2.0.0",
        "device": "Mac Studio M4 Max",
        "models_loaded": len(_models_cache),
        "cached_models": [
            {
                "name": k,
                "use_count": v.get("use_count", 0),
                "last_used": v.get("last_used", v.get("loaded_at")).isoformat() if v.get("last_used") or v.get("loaded_at") else None,
                "load_time_seconds": v.get("load_time_seconds", 0)
            }
            for k, v in _models_cache.items()
        ],
        "available_models": list(MODEL_PATHS.keys()),
        "active_requests": _active_requests,
        "max_concurrent": _max_concurrent_requests,
        "memory": {
            "used_percent": round(memory_info["used_percent"] * 100, 1),
            "available_gb": round(memory_info["available_gb"], 2)
        }
    }


@app.get("/api/tags")
async def list_models():
    """Список доступных моделей (совместимость с Ollama API)"""
    try:
        return {
            "models": [
                {
                    "name": name,
                    "model": name,
                    "size": 0,
                    "format": "mlx",
                    "exists": os.path.exists(MODEL_PATHS.get(name, ""))
                }
                for name in MODEL_PATHS.keys()
            ]
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка моделей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@app.post("/api/generate")
async def generate_text(
    request: GenerateRequest,
    http_request: Request
):
    """
    Генерация текста (совместимость с Ollama API) с защитой от ошибок
    
    Поддерживает очередь с приоритетами:
    - high: Чат с Викторией (обрабатывается первым) - заголовок X-Request-Priority: high
    - medium: Task Distribution (может подождать) - по умолчанию
    - low: Фоновые задачи - заголовок X-Request-Priority: low
    """
    start_time = time.time()
    
    # Определяем приоритет из заголовка X-Request-Priority
    priority_header = http_request.headers.get("X-Request-Priority", "medium").lower()
    priority_map = {
        "high": RequestPriority.HIGH,
        "medium": RequestPriority.MEDIUM,
        "low": RequestPriority.LOW
    }
    request_priority = priority_map.get(priority_header, RequestPriority.MEDIUM)
    
    logger.debug(f"📥 Запрос на генерацию (приоритет: {request_priority.name}, модель: {request.model})")
    
    # Оценка таймаута по модели (загрузка + инференс + запас) для очереди и ожидания результата
    if request.model:
        _queue_model_key = OLLAMA_TO_MLX_MAP.get(request.model, request.model)
        if _queue_model_key not in MODEL_PATHS:
            _queue_model_key = CATEGORY_TO_MODEL.get(request.model, "default")
    elif request.category:
        _queue_model_key = CATEGORY_TO_MODEL.get(request.category, "default")
    else:
        _queue_model_key = "default"
    timeout_estimate = get_model_timeout_estimate(_queue_model_key, request.max_tokens, load_time_actual=None)
    
    # Если очередь доступна, используем её
    if REQUEST_QUEUE_AVAILABLE:
        queue = get_request_queue()
        
        # Создаем Future для получения результата
        result_future = asyncio.Future()
        
        async def _execute_generation():
            try:
                result = await _generate_text_internal(request, start_time)
                if not result_future.done():
                    result_future.set_result(result)
                return result
            except Exception as e:
                if not result_future.done():
                    result_future.set_exception(e)
                raise
        
        # Добавляем в очередь (таймаут по модели: загрузка + инференс + запас)
        success, request_id, queue_position = await queue.add_request(
            priority=request_priority,
            callback=_execute_generation,
            timeout=timeout_estimate,
            metadata={"model": request.model, "category": request.category}
        )
        
        if not success:
            raise HTTPException(
                status_code=503,
                detail="Queue is full. Please try again later."
            )
        
        # Если запрос выполняется сразу (queue_position = 0), ждем результат
        # Если в очереди (queue_position > 0), также ждем результат
        try:
            result = await asyncio.wait_for(result_future, timeout=timeout_estimate)
            return result
        except asyncio.TimeoutError:
            logger.error(f"❌ Таймаут ожидания результата для запроса {request_id} (лимит {timeout_estimate:.0f}с)")
            raise HTTPException(
                status_code=504,
                detail=f"Request timeout while waiting in queue (limit {timeout_estimate:.0f}s for this model)"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения запроса {request_id}: {e}")
            raise
    
    # Fallback: прямая обработка (старый способ)
    return await _generate_text_internal(request, start_time)


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    http_request: Request
):
    """
    Ollama Chat API (/api/chat) - совместимость с LocalAIRouter
    Преобразует messages в prompt и вызывает /api/generate
    """
    # Формируем prompt из messages
    system_parts = []
    user_parts = []
    for msg in request.messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        elif msg.role == "user":
            user_parts.append(msg.content)
        elif msg.role == "assistant":
            # Пропускаем assistant messages при формировании промпта
            pass
    
    # Объединяем system и user в один prompt
    prompt_parts = []
    if system_parts:
        prompt_parts.append("\n".join(system_parts))
    if user_parts:
        prompt_parts.append("\n".join(user_parts))
    
    prompt = "\n\n".join(prompt_parts)
    
    # Извлекаем параметры из options
    temperature = 0.7
    max_tokens = 512
    if request.options:
        temperature = request.options.get("temperature", 0.7)
        max_tokens = request.options.get("num_predict", 512)
    
    # Создаём GenerateRequest
    gen_request = GenerateRequest(
        prompt=prompt,
        model=request.model,
        max_tokens=max_tokens,
        temperature=temperature,
        stream=request.stream
    )
    
    # Вызываем /api/generate
    response = await generate_text(gen_request, http_request)
    
    # Преобразуем ответ в формат /api/chat
    if isinstance(response, dict) and "response" in response:
        return {
            "model": request.model,
            "created_at": response.get("created_at", datetime.now().isoformat()),
            "message": {
                "role": "assistant",
                "content": response["response"]
            },
            "done": True
        }
    elif isinstance(response, StreamingResponse):
        # Для stream=true возвращаем StreamingResponse как есть
        return response
    else:
        # Fallback
        return response


async def _generate_text_internal(request: GenerateRequest, start_time: float):
    """Внутренняя функция генерации текста"""
    try:
        # Проверка памяти перед генерацией
        memory_info = check_memory()
        if memory_info["used_percent"] > _memory_critical_threshold:
            cleanup_unused_models()
            memory_info = check_memory()
            if memory_info["used_percent"] > _memory_critical_threshold:
                raise HTTPException(
                    status_code=503,
                    detail=f"Insufficient memory: {memory_info['used_percent']*100:.1f}% used"
                )
        
        # Определяем модель
        if request.model:
            # Проверяем, есть ли маппинг из Ollama имени в MLX
            model_key = OLLAMA_TO_MLX_MAP.get(request.model, request.model)
            # Если не нашли в маппинге, пробуем использовать как есть
            if model_key not in MODEL_PATHS:
                # Пробуем найти по категории или использовать default
                model_key = CATEGORY_TO_MODEL.get(request.model, "default")
        elif request.category:
            model_key = CATEGORY_TO_MODEL.get(request.category, "default")
        else:
            model_key = "default"
        
        # Отмечаем, что модель используется (защита от выгрузки)
        with _request_lock:
            _active_model_requests[model_key] += 1
        
        try:
            # Получаем модель (с защитой от OOM)
            try:
                model_data = get_model(model_key)
                model = model_data["model"]
                tokenizer = model_data["tokenizer"]
            except (MemoryError, RuntimeError) as e:
                logger.error(f"❌ Ошибка загрузки модели {model_key}: {e}")
                raise HTTPException(status_code=503, detail=f"Model loading failed: {str(e)}")
            
            # Таймаут генерации: загрузка (факт или оценка) + инференс по max_tokens + запас
            gen_timeout = get_model_timeout_estimate(
                model_key,
                request.max_tokens,
                load_time_actual=model_data.get("load_time_seconds"),
            )
            
            # КРИТИЧНО: Metal не поддерживает одновременные операции с одним command buffer
            # Сериализуем все операции генерации для одной модели через блокировку
            # Разные модели могут работать параллельно, но одна модель - последовательно
            model_lock = _model_locks[model_key]
            
            # Генерация с таймаутом
            if request.stream:
                return StreamingResponse(
                    generate_stream(model, tokenizer, request.prompt, request.max_tokens, model_lock),
                    media_type="application/json"
                )
            else:
                # Используем executor для async с таймаутом
                # КРИТИЧНО: Блокировка модели гарантирует, что только одна генерация
                # для этой модели выполняется одновременно (защита от Metal конфликтов)
                loop = asyncio.get_event_loop()
                try:
                    def generate_with_lock():
                        """Генерация с блокировкой модели для защиты от Metal конфликтов"""
                        with model_lock:
                            return generate(model, tokenizer, prompt=request.prompt, max_tokens=request.max_tokens)
                    
                    response_text = await asyncio.wait_for(
                        loop.run_in_executor(None, generate_with_lock),
                        timeout=gen_timeout
                    )
                    
                    duration = time.time() - start_time
                    logger.info(f"✅ Генерация завершена за {duration:.2f}с (модель: {model_key}, токенов: {request.max_tokens})")
                    
                    return {
                        "model": model_key,
                        "response": response_text,
                        "done": True
                    }
                except asyncio.TimeoutError:
                    logger.error(f"❌ Таймаут генерации для модели {model_key} (лимит {gen_timeout:.0f}с)")
                    raise HTTPException(
                        status_code=504,
                        detail=f"Generation timeout (limit {gen_timeout:.0f}s for this model and max_tokens)"
                    )
                except MemoryError as e:
                    logger.error(f"❌ Нехватка памяти при генерации: {e}")
                    # Экстренная очистка при MemoryError
                    cleanup_unused_models(aggressive=True)
                    memory_info = check_memory()
                    raise HTTPException(
                        status_code=503, 
                        detail=f"Out of memory during generation: {str(e)}. Memory usage: {memory_info['used_percent']*100:.1f}%"
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка при работе с моделью {model_key}: {e}", exc_info=True)
            raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка генерации: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
    finally:
        # Убираем модель из активных запросов
        try:
            with _request_lock:
                current_count = _active_model_requests.get(model_key, 0)
                if current_count > 0:
                    _active_model_requests[model_key] = current_count - 1
                    if _active_model_requests[model_key] == 0:
                        _active_model_requests.pop(model_key, None)
                else:
                    # Если счетчик уже 0 или отсутствует, просто удаляем ключ
                    _active_model_requests.pop(model_key, None)
        except (KeyError, RuntimeError) as e:
            logger.warning(f"⚠️ Ошибка при обновлении счетчика активных запросов для {model_key}: {e}")


async def generate_stream(model, tokenizer, prompt: str, max_tokens: int, model_lock: threading.Lock = None):
    """Streaming генерация с защитой от Metal конфликтов"""
    # MLX не поддерживает streaming напрямую, эмулируем
    # КРИТИЧНО: Используем блокировку модели для защиты от Metal конфликтов
    if model_lock is None:
        # Если блокировка не передана, создаем временную (не должно происходить)
        logger.warning("⚠️ generate_stream вызван без блокировки модели, создаем временную")
        model_lock = threading.Lock()
    
    loop = asyncio.get_event_loop()
    
    def generate_with_lock():
        """Генерация с блокировкой модели"""
        with model_lock:
            return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens)
    
    response = await loop.run_in_executor(None, generate_with_lock)
    
    # Разбиваем на токены для эмуляции streaming
    for char in response:
        yield json.dumps({"response": char, "done": False}) + "\n"
    
    yield json.dumps({"response": "", "done": True}) + "\n"


@app.get("/api/models/{model_name}")
async def get_model_info(model_name: str):
    """Информация о модели"""
    if model_name not in MODEL_PATHS:
        raise HTTPException(status_code=404, detail="Model not found")
    
    model_path = MODEL_PATHS[model_name]
    exists = os.path.exists(model_path)
    
    return {
        "name": model_name,
        "path": model_path,
        "exists": exists,
        "loaded": model_name in _models_cache
    }


@app.get("/queue/stats")
async def queue_stats():
    """Статистика очереди запросов"""
    if REQUEST_QUEUE_AVAILABLE:
        queue = get_request_queue()
        stats = queue.get_stats()
        return stats
    else:
        return {
            "status": "queue_not_available",
            "message": "Request queue is not available, using direct processing"
        }


@app.post("/v1/messages")
async def anthropic_messages(request: AnthropicMessagesRequest):
    """
    Anthropic-compatible API endpoint для Claude Code и других Anthropic-совместимых клиентов
    
    Эмулирует Anthropic Messages API, позволяя Claude Code работать с MLX моделями
    """
    try:
        # Преобразуем Anthropic формат в Ollama формат
        # Объединяем все сообщения в один промпт
        prompt_parts = []
        for msg in request.messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")
        
        combined_prompt = "\n".join(prompt_parts)
        
        # Определяем модель (маппинг из Anthropic имен в MLX)
        model_key = request.model
        if model_key in OLLAMA_TO_MLX_MAP:
            model_key = OLLAMA_TO_MLX_MAP[model_key]
        
        # Создаем запрос в формате Ollama для внутренней функции
        internal_request = GenerateRequest(
            prompt=combined_prompt,
            model=model_key,
            max_tokens=request.max_tokens or 1024,
            temperature=request.temperature or 0.7,
            stream=request.stream or False
        )
        
        if request.stream:
            # Streaming response (эмулируем через разбиение ответа)
            async def generate_stream_response():
                try:
                    # Используем внутреннюю функцию генерации
                    result = await _generate_text_internal(internal_request, time.time())
                    response_text = result.get("response", "")
                    
                    # Форматируем в Anthropic streaming format
                    for char in response_text:
                        yield f"data: {json.dumps({'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': char}})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}})}\n\n"
                    yield f"data: {json.dumps({'type': 'message_stop'})}\n\n"
                except Exception as e:
                    logger.error(f"❌ Ошибка streaming генерации: {e}", exc_info=True)
                    yield f"data: {json.dumps({'type': 'error', 'error': {'message': str(e)}})}\n\n"
            
            return StreamingResponse(generate_stream_response(), media_type="text/event-stream")
        else:
            # Non-streaming response
            result = await _generate_text_internal(internal_request, time.time())
            response_text = result.get("response", "")
            
            # Форматируем в Anthropic format
            return {
                "id": f"msg_{int(time.time() * 1000)}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": response_text
                    }
                ],
                "model": request.model,
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {
                    "input_tokens": len(combined_prompt.split()),  # Примерная оценка
                    "output_tokens": len(response_text.split())   # Примерная оценка
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка Anthropic API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Anthropic API error: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint с детальной диагностикой и автоматической очисткой памяти"""
    try:
        memory_info = check_memory()
        
        # Автоматическая очистка при критической нехватке памяти
        if memory_info["used_percent"] > _memory_critical_threshold:
            logger.warning(f"⚠️ Health check: критическая нехватка памяти ({memory_info['used_percent']*100:.1f}%), запускаем очистку...")
            cleanup_unused_models(aggressive=memory_info["used_percent"] > 0.98)
            memory_info = check_memory()  # Обновляем после очистки
        
        is_healthy = (
            memory_info["used_percent"] < _memory_critical_threshold and
            _active_requests < _max_concurrent_requests
        )
        
        # Определяем статус
        status = "healthy"
        if memory_info["used_percent"] > _memory_critical_threshold:
            status = "critical"
        elif memory_info["used_percent"] > _memory_warning_threshold:
            status = "warning"
        elif not is_healthy:
            status = "degraded"
        
        warnings = []
        if memory_info["used_percent"] > _memory_warning_threshold:
            warnings.append(f"High memory usage: {memory_info['used_percent']*100:.1f}%")
        if _active_requests >= _max_concurrent_requests:
            warnings.append(f"Too many concurrent requests: {_active_requests}/{_max_concurrent_requests}")
        
        return {
            "status": status,
            "service": "MLX API Server",
            "version": "2.0.0",
            "models_cached": len(_models_cache),
            "cached_models": [
                {
                    "name": k,
                    "use_count": v.get("use_count", 0),
                    "last_used": v.get("last_used", v.get("loaded_at")).isoformat() if v.get("last_used") or v.get("loaded_at") else None,
                    "load_time_seconds": round(v.get("load_time_seconds", 0), 2),
                    "active_requests": _active_model_requests.get(k, 0),
                    "is_loading": k in _loading_models
                }
                for k, v in _models_cache.items()
            ],
            "active_model_requests": dict(_active_model_requests),
            "loading_models": list(_loading_models),
            "total_models": len(MODEL_PATHS),
            "active_requests": _active_requests,
            "max_concurrent": _max_concurrent_requests,
            "memory": {
                "used_percent": round(memory_info["used_percent"] * 100, 1),
                "available_gb": round(memory_info["available_gb"], 2),
                "total_gb": round(memory_info["total_gb"], 2),
                "warning_threshold": round(_memory_warning_threshold * 100, 1),
                "critical_threshold": round(_memory_critical_threshold * 100, 1)
            },
            "rate_limit": {
                "max_per_window": _rate_limit_max,
                "window_seconds": _rate_limit_window
            },
            "warnings": warnings,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Ошибка health check: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


async def periodic_cache_cleanup():
    """Периодически выгружает лишние модели по LRU (не более MLX_MAX_CACHED_MODELS в кэше)."""
    if _cache_cleanup_interval_sec <= 0:
        return
    while True:
        try:
            await asyncio.sleep(_cache_cleanup_interval_sec)
            evict_lru_to_limit(_max_cached_models)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"⚠️ Ошибка в периодической очистке кэша: {e}")


async def preload_models():
    """Предзагрузка основных моделей при старте сервера"""
    if not _preload_models:
        logger.info("ℹ️ Предзагрузка моделей отключена (MLX_PRELOAD_MODELS пусто)")
        return
    
    logger.info(f"🔄 Предзагрузка моделей: {_preload_models}")
    
    # Проверяем память перед предзагрузкой
    memory_info = check_memory()
    if memory_info["used_percent"] > 0.7:  # 70% - слишком много уже используется
        logger.warning(f"⚠️ Высокое использование памяти ({memory_info['used_percent']*100:.1f}%), пропускаем предзагрузку")
        return
    
    preloaded = []
    failed = []
    
    for model_key in _preload_models:
        # Маппинг категорий на реальные модели
        actual_model = PRELOAD_MODEL_MAP.get(model_key, model_key)
        
        # Пропускаем, если модель уже в кэше
        if actual_model in _models_cache:
            logger.info(f"✅ Модель {actual_model} уже в кэше, пропускаем")
            preloaded.append(actual_model)
            continue
        
        try:
            logger.info(f"🔄 Предзагрузка модели: {actual_model}...")
            start_time = time.time()
            
            # Загружаем модель
            model_data = get_model(actual_model)
            
            duration = time.time() - start_time
            logger.info(f"✅ Модель {actual_model} предзагружена за {duration:.2f}с")
            preloaded.append(actual_model)
            
            # Проверяем память после каждой загрузки
            memory_info = check_memory()
            if memory_info["used_percent"] > 0.75:  # 75% - останавливаем предзагрузку
                logger.warning(f"⚠️ Использование памяти достигло {memory_info['used_percent']*100:.1f}%, останавливаем предзагрузку")
                break
                
        except Exception as e:
            logger.error(f"❌ Ошибка предзагрузки модели {actual_model}: {e}")
            failed.append(actual_model)
    
    if preloaded:
        logger.info(f"✅ Предзагружено моделей: {len(preloaded)} ({', '.join(preloaded)})")
    if failed:
        logger.warning(f"⚠️ Не удалось предзагрузить: {len(failed)} ({', '.join(failed)})")
    
    # Финальная проверка памяти
    memory_info = check_memory()
    logger.info(f"📊 Использование памяти после предзагрузки: {memory_info['used_percent']*100:.1f}% ({memory_info['available_gb']:.1f}GB свободно)")


if __name__ == "__main__":
    import uvicorn
    import signal
    import sys
    
    # Обработка сигналов для graceful shutdown
    def signal_handler(sig, frame):
        logger.info("🛑 Получен сигнал завершения, выполняю graceful shutdown...")
        # Очистка кэша моделей
        _models_cache.clear()
        logger.info("✅ Кэш моделей очищен")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Исправление порта: 11435 вместо 11434 (критическая проблема!)
        PORT = int(os.getenv("MLX_API_PORT", 11435))
        WORKERS = int(os.getenv("MLX_API_WORKERS", 1))  # MLX не поддерживает multiprocessing
        
        logger.info(f"🚀 Запуск MLX API Server на порту {PORT} (workers: {WORKERS})")
        logger.info(f"📊 Лимиты: {_max_concurrent_requests} параллельных запросов, {_rate_limit_max} запросов/{_rate_limit_window}с")
        logger.info(f"📦 Предзагрузка моделей: {_preload_models if _preload_models else 'отключена'}")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=PORT,
            workers=WORKERS,
            timeout_keep_alive=120,  # Keep-alive для connection pooling
            limit_concurrency=_max_concurrent_requests + 5,  # Небольшой запас
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("🛑 Получен KeyboardInterrupt, выполняю graceful shutdown...")
        _models_cache.clear()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска сервера: {e}", exc_info=True)
        sys.exit(1)

