"""
Prometheus метрики для мониторинга ATRA Web IDE (День 5).
RAG, Plan Cache, LLM, запросы, ошибки.
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# === Основные метрики ===

USER_REQUESTS = Counter(
    "chat_requests_total",
    "Total user requests",
    ["mode", "endpoint"],
)

REQUEST_DURATION = Histogram(
    "chat_request_duration_seconds",
    "Request duration in seconds",
    ["mode", "endpoint"],
)

# === RAG метрики ===

RAG_REQUESTS = Counter(
    "rag_requests_total",
    "Total RAG requests",
    ["mode", "type", "path"],
)

RAG_DURATION = Histogram(
    "rag_duration_seconds",
    "RAG processing duration",
    ["mode", "type"],
)

RAG_CACHE_HITS = Counter(
    "rag_cache_hits_total",
    "RAG cache hits",
    ["cache_type"],
)

RAG_CHUNKS_RETURNED = Histogram(
    "rag_chunks_returned",
    "Number of chunks returned by RAG",
    buckets=[1, 2, 3, 5, 10, 20],
)

# === Plan метрики ===

PLAN_REQUESTS = Counter(
    "plan_requests_total",
    "Total plan requests",
)

PLAN_DURATION = Histogram(
    "plan_duration_seconds",
    "Plan generation duration",
)

PLAN_CACHE_HITS = Counter(
    "plan_cache_hits_total",
    "Plan cache hits",
)

PLAN_STEPS_COUNT = Histogram(
    "plan_steps_count",
    "Number of steps in generated plans",
    buckets=[1, 3, 5, 10, 15, 20],
)

# === Embedding метрики ===

EMBEDDING_REQUESTS = Counter(
    "embedding_requests_total",
    "Total embedding requests",
    ["source"],
)

EMBEDDING_DURATION = Histogram(
    "embedding_duration_seconds",
    "Embedding generation duration",
    ["source"],
)

EMBEDDING_BATCH_SIZE = Histogram(
    "embedding_batch_size",
    "Size of embedding batches",
    buckets=[1, 2, 5, 10, 20],
)

# === LLM метрики ===

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM requests",
    ["provider", "model"],
)

LLM_DURATION = Histogram(
    "llm_duration_seconds",
    "LLM response duration",
    ["provider"],
)

LLM_TOKENS = Counter(
    "llm_tokens_total",
    "Total tokens processed",
    ["provider", "direction"],
)

# === Системные метрики ===

ACTIVE_REQUESTS = Gauge(
    "active_requests",
    "Number of active requests",
)

QUEUE_SIZE = Gauge(
    "queue_size",
    "Size of processing queues",
    ["queue_name"],
)

CACHE_SIZE = Gauge(
    "cache_size",
    "Cache sizes",
    ["cache_type"],
)

ERROR_COUNTER = Counter(
    "errors_total",
    "Total errors",
    ["error_type", "component"],
)

# === Telegram Bot метрики ===

TELEGRAM_BOT_STATUS = Gauge(
    "telegram_bot_online",
    "Telegram bot online status (1 = online, 0 = offline)",
)

TELEGRAM_BOT_MESSAGES = Counter(
    "telegram_bot_messages_total",
    "Total messages processed by Telegram bot",
)

TELEGRAM_BOT_ERRORS = Counter(
    "telegram_bot_errors_total",
    "Total errors in Telegram bot",
)

TELEGRAM_BOT_HEARTBEAT_AGE = Gauge(
    "telegram_bot_heartbeat_age_seconds",
    "Seconds since last Telegram bot heartbeat",
)

# П.4 PRINCIPLE_EXPERTS_FIRST: метрика «ответил эксперт» vs fallback
CHAT_EXPERT_ANSWER_TOTAL = Counter(
    "chat_expert_answer_total",
    "Chat responses from designated expert path (Victoria or expert_name)",
    ["source"],  # victoria | fallback_llm | direct | template
)
CHAT_FALLBACK_TOTAL = Counter(
    "chat_fallback_total",
    "Chat responses without expert (generic model path)",
    [],
)


class MetricsCollector:
    """Коллектор метрик с контекстными менеджерами и декораторами."""

    @staticmethod
    def track_request(mode: str, endpoint: str):
        """Декоратор для отслеживания запросов."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                USER_REQUESTS.labels(mode=mode, endpoint=endpoint).inc()
                ACTIVE_REQUESTS.inc()
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    REQUEST_DURATION.labels(mode=mode, endpoint=endpoint).observe(duration)
                    return result
                except Exception as e:
                    ERROR_COUNTER.labels(
                        error_type=type(e).__name__,
                        component=endpoint,
                    ).inc()
                    raise
                finally:
                    ACTIVE_REQUESTS.dec()

            return wrapper

        return decorator

    @staticmethod
    def track_rag(mode: str, rag_type: str):
        """Декоратор для отслеживания RAG запросов."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                RAG_REQUESTS.labels(mode=mode, type=rag_type, path="processing").inc()
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    RAG_DURATION.labels(mode=mode, type=rag_type).observe(duration)
                    if result is not None and hasattr(result, "__len__"):
                        RAG_CHUNKS_RETURNED.observe(min(len(result), 20))
                    elif result is not None:
                        RAG_CHUNKS_RETURNED.observe(1)
                    return result
                except Exception as e:
                    ERROR_COUNTER.labels(
                        error_type=type(e).__name__,
                        component=f"rag_{rag_type}",
                    ).inc()
                    raise

            return wrapper

        return decorator

    @staticmethod
    def track_embedding(source: str):
        """Декоратор для отслеживания эмбеддингов."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                EMBEDDING_REQUESTS.labels(source=source).inc()
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration = time.time() - start_time
                    EMBEDDING_DURATION.labels(source=source).observe(duration)
                    return result
                except Exception as e:
                    ERROR_COUNTER.labels(
                        error_type=type(e).__name__,
                        component="embedding",
                    ).inc()
                    raise

            return wrapper

        return decorator


metrics = MetricsCollector()


# === Утилиты ===

def record_cache_hit(cache_type: str) -> None:
    """Запись попадания в кэш."""
    RAG_CACHE_HITS.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Запись промаха кэша (резерв под отдельный счётчик)."""
    pass


def record_llm_request(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """Запись запроса к LLM."""
    LLM_REQUESTS.labels(provider=provider, model=model).inc()
    if input_tokens > 0:
        LLM_TOKENS.labels(provider=provider, direction="input").inc(input_tokens)
    if output_tokens > 0:
        LLM_TOKENS.labels(provider=provider, direction="output").inc(output_tokens)


def update_queue_size(queue_name: str, size: int) -> None:
    """Обновление размера очереди."""
    QUEUE_SIZE.labels(queue_name=queue_name).set(size)


def update_cache_size(cache_type: str, size: int) -> None:
    """Обновление размера кэша."""
    CACHE_SIZE.labels(cache_type=cache_type).set(size)


def get_metrics() -> bytes:
    """Получение метрик в формате Prometheus."""
    return generate_latest(REGISTRY)
