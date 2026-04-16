"""
Prometheus метрики для мониторинга ATRA Web IDE (День 5).
RAG, Plan Cache, LLM, запросы, ошибки.
"""

import logging
import time
from functools import wraps
from typing import Type, TypeVar

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest, CollectorRegistry

logger = logging.getLogger(__name__)

_M = TypeVar("_M")

# [SINGULARITY 24.3] Глобальная изоляция для воркеров
# Мы создаем метрики в НОВОМ реестре для каждого импорта, чтобы избежать конфликтов.

# Создаем изолированный реестр для этого модуля
_isolated_registry = CollectorRegistry()

def get_metric(metric_class: Type[_M], name: str, documentation: str, labelnames=(), **kwargs) -> _M:
    """
    Безопасное получение или создание метрики в изолированном реестре.
    """
    try:
        # Пытаемся создать в изолированном реестре
        return metric_class(name, documentation, labelnames, registry=_isolated_registry, **kwargs)
    except ValueError:
        # Если дубликат в изолированном реестре (что странно для одного импорта, но возможно при reload),
        # пытаемся найти его там.
        if hasattr(_isolated_registry, "_names_to_collectors") and name in _isolated_registry._names_to_collectors:
            return _isolated_registry._names_to_collectors[name]
        
        # Если совсем всё плохо, возвращаем заглушку
        class Dummy:
            def labels(self, *args, **kwargs): return self
            def inc(self, *args, **kwargs): pass
            def dec(self, *args, **kwargs): pass
            def set(self, *args, **kwargs): pass
            def observe(self, *args, **kwargs): pass
        return Dummy()

# === Основные метрики ===
USER_REQUESTS = get_metric(Counter, "chat_requests_total", "Total user requests", ["mode", "endpoint"])
REQUEST_DURATION = get_metric(Histogram, "chat_request_duration_seconds", "Request duration in seconds", ["mode", "endpoint"])

# === RAG метрики ===
RAG_REQUESTS = get_metric(Counter, "rag_requests_total", "Total RAG requests", ["mode", "type", "path"])
RAG_DURATION = get_metric(Histogram, "rag_duration_seconds", "RAG processing duration", ["mode", "type"])
RAG_CACHE_HITS = get_metric(Counter, "rag_cache_hits_total", "RAG cache hits", ["cache_type"])
RAG_CHUNKS_RETURNED = get_metric(Histogram, "rag_chunks_returned", "Number of chunks returned by RAG", buckets=[1, 2, 3, 5, 10, 20])

# === Plan метрики ===
PLAN_REQUESTS = get_metric(Counter, "plan_requests_total", "Total plan requests")
PLAN_DURATION = get_metric(Histogram, "plan_duration_seconds", "Plan generation duration")
PLAN_CACHE_HITS = get_metric(Counter, "plan_cache_hits_total", "Plan cache hits")
PLAN_STEPS_COUNT = get_metric(Histogram, "plan_steps_count", "Number of steps in generated plans", buckets=[1, 3, 5, 10, 15, 20])

# === Embedding метрики ===
EMBEDDING_REQUESTS = get_metric(Counter, "embedding_requests_total", "Total embedding requests", ["source"])
EMBEDDING_DURATION = get_metric(Histogram, "embedding_duration_seconds", "Embedding generation duration", ["source"])
EMBEDDING_BATCH_SIZE = get_metric(Histogram, "embedding_batch_size", "Size of embedding batches", buckets=[1, 2, 5, 10, 20])

# === [SINGULARITY 24.3] Advanced Caching Metrics ===
SEMANTIC_CACHE_HITS = get_metric(Counter, "semantic_cache_hits_total", "Total semantic cache hits", ["cache_type"])
EMBEDDING_COLLAPSED = get_metric(Counter, "embedding_requests_collapsed_total", "Total embedding requests collapsed")
EMBEDDING_BACKPRESSURE_THROTTLE = get_metric(Counter, "embedding_backpressure_throttle_total", "Total embedding requests delayed by backpressure")

# === [SINGULARITY 25.0] Ollama Backpressure Metrics ===
OLLAMA_BACKPRESSURE_SKIPS = get_metric(Counter, "ollama_backpressure_skips_total", "Ollama requests skipped due to global slot limit (Redis semaphore full)")

# === LLM метрики ===
LLM_REQUESTS = get_metric(Counter, "llm_requests_total", "Total LLM requests", ["provider", "model"])
LLM_DURATION = get_metric(Histogram, "llm_duration_seconds", "LLM response duration", ["provider"])
LLM_TOKENS = get_metric(Counter, "llm_tokens_total", "Total tokens processed", ["provider", "direction"])

# === Системные метрики ===
ACTIVE_REQUESTS = get_metric(Gauge, "active_requests", "Number of active requests")
QUEUE_SIZE = get_metric(Gauge, "queue_size", "Size of processing queues", ["queue_name"])
CACHE_SIZE = get_metric(Gauge, "cache_size", "Cache sizes", ["cache_type"])
ERROR_COUNTER = get_metric(Counter, "errors_total", "Total errors", ["error_type", "component"])

# === Telegram Bot метрики ===
TELEGRAM_BOT_STATUS = get_metric(Gauge, "telegram_bot_online", "Telegram bot online status")
TELEGRAM_BOT_MESSAGES = get_metric(Counter, "telegram_bot_messages_total", "Total messages processed by Telegram bot")
TELEGRAM_BOT_ERRORS = get_metric(Counter, "telegram_bot_errors_total", "Total errors in Telegram bot")
TELEGRAM_BOT_HEARTBEAT_AGE = get_metric(Gauge, "telegram_bot_heartbeat_age_seconds", "Seconds since last Telegram bot heartbeat")

# П.4 PRINCIPLE_EXPERTS_FIRST
CHAT_EXPERT_ANSWER_TOTAL = get_metric(Counter, "chat_expert_answer_total", "Chat responses from designated expert path", ["source"])
CHAT_FALLBACK_TOTAL = get_metric(Counter, "chat_fallback_total", "Chat responses without expert")

# Singularity 15.0: ask_victoria tool
ASK_VICTORIA_TOTAL = get_metric(Counter, "ask_victoria_total", "Total ask_victoria API calls", ["status"])


class MetricsCollector:
    """Коллектор метрик с контекстными менеджерами и декораторами."""

    @staticmethod
    def track_request(mode: str, endpoint: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try: USER_REQUESTS.labels(mode=mode, endpoint=endpoint).inc()
                except: pass
                try: ACTIVE_REQUESTS.inc()
                except: pass
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    try: REQUEST_DURATION.labels(mode=mode, endpoint=endpoint).observe(duration)
                    except: pass
                    return result
                except Exception as e:
                    try:
                        ERROR_COUNTER.labels(
                            error_type=type(e).__name__,
                            component=endpoint,
                        ).inc()
                    except: pass
                    raise
                finally:
                    try: ACTIVE_REQUESTS.dec()
                    except: pass
            return wrapper
        return decorator

    @staticmethod
    def track_rag(mode: str, rag_type: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try: RAG_REQUESTS.labels(mode=mode, type=rag_type, path="processing").inc()
                except: pass
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    try: RAG_DURATION.labels(mode=mode, type=rag_type).observe(duration)
                    except: pass
                    if result is not None:
                        try:
                            if hasattr(result, "__len__"):
                                RAG_CHUNKS_RETURNED.observe(min(len(result), 20))
                            else:
                                RAG_CHUNKS_RETURNED.observe(1)
                        except: pass
                    return result
                except Exception as e:
                    try:
                        ERROR_COUNTER.labels(
                            error_type=type(e).__name__,
                            component=f"rag_{rag_type}",
                        ).inc()
                    except: pass
                    raise
            return wrapper
        return decorator

    @staticmethod
    def track_embedding(source: str):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try: EMBEDDING_REQUESTS.labels(source=source).inc()
                except: pass
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    try: EMBEDDING_DURATION.labels(source=source).observe(duration)
                    except: pass
                    return result
                except Exception as e:
                    try:
                        ERROR_COUNTER.labels(
                            error_type=type(e).__name__,
                            component="embedding",
                        ).inc()
                    except: pass
                    raise
            return wrapper
        return decorator

metrics = MetricsCollector()

# === Утилиты ===

def record_cache_hit(cache_type: str) -> None:
    try: RAG_CACHE_HITS.labels(cache_type=cache_type).inc()
    except: pass

def record_cache_miss(cache_type: str) -> None:
    pass

def record_llm_request(provider: str, model: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
    try: LLM_REQUESTS.labels(provider=provider, model=model).inc()
    except: pass
    if input_tokens > 0:
        try: LLM_TOKENS.labels(provider=provider, direction="input").inc(input_tokens)
        except: pass
    if output_tokens > 0:
        try: LLM_TOKENS.labels(provider=provider, direction="output").inc(output_tokens)
        except: pass
    if provider == "local":
        logger.debug(f"📊 [METRICS] Local LLM request: model={model}, in={input_tokens}, out={output_tokens}")

def update_queue_size(queue_name: str, size: int) -> None:
    try: QUEUE_SIZE.labels(queue_name=queue_name).set(size)
    except: pass

def update_cache_size(cache_type: str, size: int) -> None:
    try: CACHE_SIZE.labels(cache_type=cache_type).set(size)
    except: pass

def record_semantic_cache_hit(cache_type: str) -> None:
    try: SEMANTIC_CACHE_HITS.labels(cache_type=cache_type).inc()
    except: pass

def record_embedding_collapsed() -> None:
    try: EMBEDDING_COLLAPSED.inc()
    except: pass

def record_embedding_throttle() -> None:
    try: EMBEDDING_BACKPRESSURE_THROTTLE.inc()
    except: pass

def get_metrics() -> bytes:
    return generate_latest(_isolated_registry)
