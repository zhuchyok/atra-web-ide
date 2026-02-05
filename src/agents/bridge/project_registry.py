"""
Реестр проектов корпорации: загрузка из БД (таблица projects) с fallback на env и хардкод.
Используется Victoria и Veronica для валидации project_context и детерминированного маппинга (безопасность).
"""
import os
import logging
from typing import Dict, List, Tuple, Any

logger = logging.getLogger(__name__)

# Fallback при недоступности БД или пустой таблице (безопасный маппинг, не пользовательский ввод)
DEFAULT_PROJECT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "atra-web-ide": {
        "name": "ATRA Web IDE",
        "description": "Браузерная оболочка для ИИ-корпорации",
        "workspace": "/workspace/atra-web-ide",
    },
    "atra": {
        "name": "ATRA Trading System",
        "description": "Торговая система с ИИ-агентами",
        "workspace": "/workspace/atra",
    },
}

_registry_cache: Tuple[List[str], Dict[str, Dict[str, Any]]] | None = None


async def load_projects_registry(database_url: str | None = None) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
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
                                "workspace": r["workspace_path"] or f"/workspace/{r['slug']}",
                            }
                            for r in rows
                        }
                        return (allowed, configs)
            finally:
                await conn.close()
        except Exception as e:
            logger.debug("Project registry: DB load failed, using fallback: %s", e)
    allowed_env = os.getenv("ALLOWED_PROJECTS", "atra-web-ide,atra").strip().split(",")
    allowed_env = [s.strip() for s in allowed_env if s.strip()]
    configs = {k: v for k, v in DEFAULT_PROJECT_CONFIGS.items() if k in allowed_env}
    for slug in allowed_env:
        if slug not in configs:
            configs[slug] = {
                "name": slug,
                "description": "",
                "workspace": f"/workspace/{slug}",
            }
    return (allowed_env, configs)


async def get_projects_registry(force_reload: bool = False) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    Возвращает кэшированный реестр (allowed_slugs, configs_by_slug).
    При первом вызове или force_reload загружает из БД с fallback на env/hardcoded.
    """
    global _registry_cache
    if _registry_cache is not None and not force_reload:
        return _registry_cache
    _registry_cache = await load_projects_registry()
    return _registry_cache


def get_main_project() -> str:
    """MAIN_PROJECT из env (fallback при неизвестном project_context)."""
    return os.getenv("MAIN_PROJECT", "atra-web-ide").strip()
