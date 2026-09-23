"""
Error Budget для автономных циклов (план 2026-09-22, Фаза 4.1).

Практика Google SRE: каждому автономному циклу — бюджет неудач в сутки.
Исчерпан бюджет → цикл переходит в наблюдаемый режим (не делает LLM-работу,
пишет задачу в triage с флагом failed_requires_intervention-семантики).

Хранение: Redis-счётчики `errbudget:{cycle}:{YYYYMMDD}` (TTL 48ч).
KISS: без внешних зависимостей, Redis через redis_manager если доступен,
иначе локальный in-memory fallback (для тестов и host-процессов).

Использование в цикле:

    from error_budget import check_budget, record_failure, record_success

    allowed, remaining = await check_budget("evolution")
    if not allowed:
        logger.warning("[ERRBUDGET] evolution: бюджет исчерпан — наблюдаемый режим")
        return
    try:
        ...работа цикла...
        await record_success("evolution")
    except Exception:
        await record_failure("evolution")
"""

import logging
import os
from datetime import date
from typing import Optional, Tuple

logger = logging.getLogger("errbudget")

# Бюджеты по умолчанию (неудач/сутки). Переопределяется env ERRBUDGET_<CYCLE>_MAX.
_DEFAULT_MAX_FAILURES = int(os.getenv("ERRBUDGET_DEFAULT_MAX", "10"))
_CYCLE_MAX_ENV = {
    "evolution": "ERRBUDGET_EVOLUTION_MAX",
    "curiosity": "ERRBUDGET_CURIOSITY_MAX",
    "self_check": "ERRBUDGET_SELF_CHECK_MAX",
    "nightly": "ERRBUDGET_NIGHTLY_MAX",
}

_local_counters: dict[str, int] = {}
_redis_client = None
_redis_tried = False


def _max_for_cycle(cycle: str) -> int:
    env = _CYCLE_MAX_ENV.get(cycle)
    if env:
        try:
            return int(os.getenv(env, str(_DEFAULT_MAX_FAILURES)))
        except ValueError:
            return _DEFAULT_MAX_FAILURES
    return _DEFAULT_MAX_FAILURES


def _key(cycle: str) -> str:
    return f"errbudget:{cycle}:{date.today().strftime('%Y%m%d')}"


async def _get_redis():
    global _redis_client, _redis_tried
    if _redis_tried:
        return _redis_client
    _redis_tried = True
    try:
        try:
            from redis_manager import get_redis_manager  # type: ignore

            mgr = get_redis_manager()
            _redis_client = getattr(mgr, "client", None) or getattr(mgr, "_client", None)
        except Exception:  # noqa: BLE001
            _redis_client = None
        if _redis_client is None:
            import redis  # type: ignore

            url = os.getenv("REDIS_URL", "")
            if url and url.startswith("unix://"):
                _redis_client = redis.Redis(unix_socket_path=url.replace("unix://", ""), socket_timeout=2)
            elif url:
                _redis_client = redis.Redis.from_url(url, socket_timeout=2)
            else:
                host = os.getenv("REDIS_HOST", "host.docker.internal")
                port = int(os.getenv("REDIS_PORT", "6381"))
                _redis_client = redis.Redis(host=host, port=port, socket_timeout=2)
            _redis_client.ping()
    except Exception as e:  # noqa: BLE001
        logger.warning("[ERRBUDGET] Redis недоступен (%s) — локальные счётчики", e)
        _redis_client = None
    return _redis_client


async def _incr(cycle: str, delta: int) -> int:
    client = await _get_redis()
    key = _key(cycle)
    if client is not None:
        try:
            value = await _redis_call(client, "incr", key, delta)
            await _redis_call(client, "expire", key, 172800)
            return int(value or 0)
        except Exception:  # noqa: BLE001
            pass
    _local_counters[key] = _local_counters.get(key, 0) + delta
    return _local_counters[key]


async def _redis_call(client, method: str, *args):
    result = getattr(client, method)(*args)
    if hasattr(result, "__await__"):
        return await result
    return result


async def check_budget(cycle: str) -> Tuple[bool, int]:
    """(разрешено_ли_работать, сколько_неудач_осталось)."""
    client = await _get_redis()
    key = _key(cycle)
    failures: Optional[int] = None
    if client is not None:
        try:
            failures = int(await _redis_call(client, "get", key) or 0)
        except Exception:  # noqa: BLE001
            failures = None
    if failures is None:
        failures = _local_counters.get(key, 0)
    remaining = _max_for_cycle(cycle) - failures
    return remaining > 0, remaining


async def record_failure(cycle: str) -> int:
    """Зафиксировать неудачу. Возвращает счётчик неудач за сегодня."""
    count = await _incr(cycle, 1)
    if count == _max_for_cycle(cycle):
        logger.error(
            "🚨 [ERRBUDGET] %s: бюджет исчерпан (%d/%d) — цикл в наблюдаемый режим",
            cycle,
            count,
            _max_for_cycle(cycle),
        )
        await _create_triage_task(cycle, count)
    return count


async def record_success(cycle: str) -> None:
    """Успех снижает счётчик неудач на 1 (не ниже 0) — цикл может реабилитироваться."""
    client = await _get_redis()
    key = _key(cycle)
    if client is not None:
        try:
            value = int(await _redis_call(client, "get", key) or 0)
            if value > 0:
                await _redis_call(client, "decr", key)
        except Exception:  # noqa: BLE001
            pass
    else:
        current = _local_counters.get(key, 0)
        if current > 0:
            _local_counters[key] = current - 1


async def _create_triage_task(cycle: str, failures: int) -> None:
    """Задача в БД для ручного разбора (идемпотентно по dedup-контракту)."""
    title = f"🚨 ERRBUDGET: {cycle} исчерпал бюджет ({failures} неудач)"
    try:
        pool_module = None
        try:
            from db_pool import get_db_pool as _g  # type: ignore
        except ImportError:
            pool_module = None
        dsn = os.getenv("DATABASE_URL", "")
        if not dsn:
            logger.warning("[ERRBUDGET] DATABASE_URL не задан — triage-задача не создана")
            return
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM tasks WHERE title = $1 AND status IN ('pending','in_progress') LIMIT 1",
                title,
            )
            if not exists:
                await conn.execute(
                    """
                    INSERT INTO tasks (title, description, status, priority, metadata)
                    VALUES ($1, $2, 'pending', 8, $3::jsonb)
                    """,
                    title,
                    f"Автономный цикл «{cycle}» исчерпал error budget ({failures} неудач за сутки) — ручной разбор.",
                    '{"source":"error_budget","requires_intervention":true,"cycle":"%s","failures":%d,"diagnostic_path":true}'
                    % (cycle, failures),
                )
        finally:
            await conn.close()
        logger.error("🚨 [ERRBUDGET] triage-задача создана: %s", title)
    except Exception as e:  # noqa: BLE001
        logger.error("[ERRBUDGET] не удалось создать triage-задачу: %s", e)
