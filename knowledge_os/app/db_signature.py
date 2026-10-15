"""
Единая гарантия подписи БД-соединений (v149.54).

Проблема: десятки модулей создают asyncpg-пулы независимо; часть путей
теряла application_name → task_status_audit подписывал переходы пустым
app_name (детектив сбросчика задач слеп на этих путях).

Решение: обёртка поверх asyncpg.connect/create_pool — в каждое соединение
процесса подставляется server_settings={'application_name': <CONTAINER_NAME>}
(идёт в startup-пакет → pgbouncer track_extra_parameters трекает → сервер
видит подпись на ЛЮБОМ коннекте пула). Явно заданное приложение не трогаем.

Использование: install() один раз в точке входа процесса (idempotent).
"""
from __future__ import annotations

import functools
import logging
import os

logger = logging.getLogger(__name__)

_INSTALLED = False


def _signature() -> str | None:
    for var in ("CONTAINER_NAME", "APPLICATION_NAME"):
        val = (os.getenv(var) or "").strip()
        # "unknown" — мусорный дефолт из compose-анкора, подписью не считается
        if val and val.lower() != "unknown":
            return val
    return None


def _dsn_has_app_name(dsn) -> bool:
    return bool(dsn) and "application_name=" in str(dsn)


def install() -> bool:
    """Обернуть asyncpg.connect/create_pool гарантированной подписью. Идемпотентно."""
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        import asyncpg
    except ImportError:
        logger.warning("[DB-SIGNATURE] asyncpg недоступен — подпись не установлена")
        return False

    sig = _signature()
    if not sig:
        logger.info(
            "[DB-SIGNATURE] CONTAINER_NAME не задан — соединения идут как есть"
        )
        _INSTALLED = True
        return False

    orig_connect = asyncpg.connect
    orig_create_pool = asyncpg.create_pool

    def _ensure_settings(dsn, kwargs: dict) -> dict:
        # DSN уже несёт подпись — не вмешиваемся (никогда не перекрываем)
        if _dsn_has_app_name(dsn):
            return kwargs
        settings = kwargs.setdefault("server_settings", {}) or {}
        # Явное приложение из кода имеет приоритет (не перетираем)
        settings.setdefault("application_name", sig)
        kwargs["server_settings"] = settings
        return kwargs

    @functools.wraps(orig_connect)
    async def connect_sig(dsn=None, *args, **kwargs):
        return await orig_connect(dsn, *args, **_ensure_settings(dsn, kwargs))

    @functools.wraps(orig_create_pool)
    async def create_pool_sig(dsn=None, *args, **kwargs):
        return await orig_create_pool(dsn, *args, **_ensure_settings(dsn, kwargs))

    asyncpg.connect = connect_sig
    asyncpg.create_pool = create_pool_sig
    _INSTALLED = True
    logger.info("[DB-SIGNATURE] подпись '%s' установлена на asyncpg.connect/create_pool", sig)
    return True
