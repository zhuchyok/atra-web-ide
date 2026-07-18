"""
Compatibility shim for modules that import `app.redis_manager`.

The actual Redis manager lives in Knowledge OS runtime modules. Backend API
containers may execute codepaths that still reference `app.redis_manager`, so
we proxy those imports to the canonical module to avoid runtime import errors.
"""

from __future__ import annotations

import importlib


def _load_impl():
    # Preferred path when knowledge_os app directory is present in PYTHONPATH.
    try:
        return importlib.import_module("redis_manager")
    except Exception:
        # Fallback for explicit package style.
        return importlib.import_module("knowledge_os.app.redis_manager")


_impl = _load_impl()

# Re-export common public symbols used by legacy imports.
redis_manager = getattr(_impl, "redis_manager", None)
RedisManager = getattr(_impl, "RedisManager", None)


def __getattr__(name: str):
    return getattr(_impl, name)
