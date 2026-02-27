"""
Реестр проектов корпорации: загрузка из БД (таблица projects) с fallback на env и хардкод.
Используется Victoria и Veronica для валидации project_context и детерминированного маппинга (безопасность).
Проекты из dev/ автоматически подхватываются: папки в /workspace/dev считаются допустимыми проектами.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# TTL кэша реестра (сек): новые папки в dev/ подхватываются при следующем запросе после истечения
REGISTRY_CACHE_TTL_SEC = int(os.getenv("PROJECT_REGISTRY_CACHE_TTL", "300"))

# Допустимое имя проекта (slug): буквы, цифры, дефис. Без ., /, ..
_SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*$")

# Fallback при недоступности БД или пустой таблице (безопасный маппинг, не пользовательский ввод).
# Проекты из dev/ — workspace /workspace/dev/{slug}; главный проект — /workspace/atra-web-ide.
DEFAULT_PROJECT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "atra-web-ide": {
        "name": "ATRA Web IDE",
        "description": "Браузерная оболочка для ИИ-корпорации",
        "workspace": "/workspace/atra-web-ide",
    },
    "atra": {
        "name": "ATRA Trading System",
        "description": "Торговая система с ИИ-агентами",
        "workspace": "/workspace/dev/atra",
    },
    "setki-21": {
        "name": "Сетки 21",
        "description": "Проект Сетки 21 — корпорация ведёт",
        "workspace": "/workspace/dev/setki-21",
    },
}

DEV_WORKSPACE_ROOT = "/workspace/dev"

_registry_cache: Tuple[List[str], Dict[str, Dict[str, Any]]] | None = None
_registry_loaded_at: float = 0.0


def _merge_dev_discovery(
    allowed: List[str], configs: Dict[str, Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Добавляет в реестр проекты из /workspace/dev (каждая подпапка — проект). Без правки compose/env."""
    if not os.path.isdir(DEV_WORKSPACE_ROOT):
        return (allowed, configs)
    try:
        seen = set(allowed)
        for name in os.listdir(DEV_WORKSPACE_ROOT):
            if name.startswith(".") or not _SLUG_RE.match(name):
                continue
            path = os.path.join(DEV_WORKSPACE_ROOT, name)
            if not os.path.isdir(path):
                continue
            if name not in seen:
                allowed = list(allowed) + [name]
                seen.add(name)
            if name not in configs:
                configs = {**configs, name: {"name": name, "description": "", "workspace": path}}
        return (allowed, configs)
    except OSError as e:
        logger.debug("Project registry: dev discovery skipped: %s", e)
        return (allowed, configs)


async def load_projects_registry(
    database_url: str | None = None,
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    Загружает реестр проектов из БД (таблица projects, is_active=true).
    Возвращает (allowed_slugs, configs_by_slug).
    При ошибке или пустой таблице — fallback на ALLOWED_PROJECTS из env и DEFAULT_PROJECT_CONFIGS.
    """
    url = database_url or os.getenv("DATABASE_URL", "")
    if url:
        try:
            import asyncpg

            conn = await asyncpg.connect(url, timeout=5)
            try:
                row = await conn.fetchrow(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'projects'"
                )
                if row:
                    rows = await conn.fetch(
                        "SELECT slug, name, description, workspace_path FROM projects WHERE is_active = true"
                    )
                    if rows:
                        allowed = [r["slug"] for r in rows]
                        configs = {
                            r["slug"]: {
                                "name": r["name"] or r["slug"],
                                "description": r["description"] or "",
                                "workspace": r["workspace_path"]
                                or (
                                    f"{DEV_WORKSPACE_ROOT}/{r['slug']}"
                                    if r["slug"] != "atra-web-ide"
                                    else "/workspace/atra-web-ide"
                                ),
                            }
                            for r in rows
                        }
                        allowed, configs = _merge_dev_discovery(allowed, configs)
                        return (allowed, configs)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("Project registry: DB load failed, using fallback: %s", e)
    allowed_env = os.getenv("ALLOWED_PROJECTS", "atra-web-ide,atra,setki-21").strip().split(",")
    allowed_env = [s.strip() for s in allowed_env if s.strip()]
    configs = {k: v for k, v in DEFAULT_PROJECT_CONFIGS.items() if k in allowed_env}
    for slug in allowed_env:
        if slug not in configs:
            # Проекты из dev/ живут в /workspace/dev/{slug}
            configs[slug] = {
                "name": slug,
                "description": "",
                "workspace": f"{DEV_WORKSPACE_ROOT}/{slug}"
                if slug != "atra-web-ide"
                else f"/workspace/{slug}",
            }
    # Автоподхват: папки в /workspace/dev считаются проектами (новые — без правки compose/env)
    allowed_env, configs = _merge_dev_discovery(allowed_env, configs)
    return (allowed_env, configs)


async def get_projects_registry(
    force_reload: bool = False,
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    Возвращает кэшированный реестр (allowed_slugs, configs_by_slug).
    При первом вызове, force_reload или истечении TTL загружает из БД + сканирует dev/.
    """
    global _registry_cache, _registry_loaded_at
    now = time.monotonic()
    if (
        _registry_cache is not None
        and not force_reload
        and (now - _registry_loaded_at) < REGISTRY_CACHE_TTL_SEC
    ):
        return _registry_cache
    _registry_cache = await load_projects_registry()
    _registry_loaded_at = now
    return _registry_cache


def get_main_project() -> str:
    """MAIN_PROJECT из env (fallback при неизвестном project_context)."""
    return os.getenv("MAIN_PROJECT", "atra-web-ide").strip()
