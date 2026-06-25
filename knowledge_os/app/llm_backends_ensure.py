"""
Проверка и автоматический запуск Ollama и MLX API Server при получении задачи.
Вызывается в начале solve() в Victoria Enhanced: если бэкенды недоступны — поднимаем их, затем идём по цепочке.
Выбор модели из доступных в Ollama и MLX уже настроен в available_models_scanner и local_router.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
_LOCAL_ROUTER_SINGLETON = None

try:
    import httpx
except ImportError:
    httpx = None


def _get_llm_urls() -> Tuple[Optional[str], str]:
    """MLX (11435) и Ollama (11434) — с учётом Docker. При MLX_API_URL=disabled возвращает (None, ollama_url)."""
    is_docker = (
        os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true"
    )
    if is_docker:
        mlx_raw = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    else:
        mlx_raw = os.getenv("MLX_API_URL", "http://localhost:11435")
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if not mlx_raw or str(mlx_raw).strip().lower() in ("disabled", "false", "0"):
        return None, ollama_url
    return mlx_raw.strip(), ollama_url


async def _check_mlx_health(mlx_url: str, timeout: float = 2.0) -> bool:
    """Проверка доступности MLX API Server."""
    if not httpx:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{mlx_url}/health")
            if r.status_code == 200:
                data = r.json() if r.content else {}
                status = data.get("status", "ok")
                return status in ("healthy", "ok", "online")
            # Некоторые MLX серверы отдают 200 на /api/tags
            r2 = await client.get(f"{mlx_url}/api/tags")
            return r2.status_code == 200
    except Exception as e:
        logger.debug("MLX health check: %s", e)
        return False


async def _check_ollama_health(ollama_url: str, timeout: float = 2.0) -> bool:
    """Проверка доступности Ollama."""
    if not httpx:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{ollama_url}/api/tags")
            return r.status_code == 200
    except Exception as e:
        logger.debug("Ollama health check: %s", e)
        return False


def _try_start_ollama() -> bool:
    """Попытка запустить ollama serve в фоне (только не в Docker, если ollama в PATH)."""
    if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER", "false").lower() == "true":
        logger.debug("Ollama: в Docker не запускаем host-сервис")
        return False
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        logger.debug("Ollama: исполняемый файл не найден в PATH")
        return False
    try:
        subprocess.Popen(
            [ollama_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("🔄 Ollama serve запущен в фоне")
        return True
    except Exception as e:
        logger.warning("Не удалось запустить ollama serve: %s", e)
        return False


def _get_local_router_singleton():
    global _LOCAL_ROUTER_SINGLETON
    if _LOCAL_ROUTER_SINGLETON is None:
        from app.local_router import LocalAIRouter

        _LOCAL_ROUTER_SINGLETON = LocalAIRouter()
    return _LOCAL_ROUTER_SINGLETON


async def ensure_llm_backends_available(
    mlx_url: Optional[str] = None,
    ollama_url: Optional[str] = None,
    start_ollama_if_missing: bool = True,
    refresh_local_router_cache: bool = True,
) -> None:
    """
    Проверить доступность Ollama и MLX; при необходимости поднять их, затем обновить кэш роутера.
    Вызывать в начале solve() при получении задачи. При MLX_API_URL=disabled MLX не запускается.
    """
    if mlx_url is None or ollama_url is None:
        mlx_url, ollama_url = _get_llm_urls()

    mlx_started = False
    ollama_started = False

    # 1) MLX API Server — пропускаем, если MLX отключён (MLX_API_URL=disabled)
    if mlx_url and not await _check_mlx_health(mlx_url):
        try:
            from app.mlx_server_supervisor import get_mlx_supervisor

            supervisor = get_mlx_supervisor()
            if await supervisor.ensure_server_running():
                logger.info("✅ MLX API Server поднят по запросу задачи")
                mlx_started = True
            else:
                logger.warning("⚠️ Не удалось поднять MLX API Server")
        except ImportError as e:
            logger.debug("MLX Supervisor недоступен: %s", e)
        except Exception as e:
            logger.warning("Ошибка при запуске MLX: %s", e)
        # Даём серверу время подняться
        await asyncio.sleep(2)
    elif mlx_url:
        logger.debug("MLX API Server уже доступен")
    # при mlx_url is None (MLX_API_URL=disabled) блок MLX пропущен

    # 2) Ollama
    if not await _check_ollama_health(ollama_url):
        if start_ollama_if_missing:
            ollama_started = _try_start_ollama()
            await asyncio.sleep(3)
        if not await _check_ollama_health(ollama_url):
            logger.debug("Ollama недоступен (ожидайте следующей проверки или запустите вручную)")
    else:
        logger.debug("Ollama уже доступен")

    # Инвалидировать кэш списка моделей, чтобы выбор шёл по актуальным доступным (Ollama/MLX)
    if mlx_started or ollama_started:
        try:
            import app.available_models_scanner as scanner

            scanner._scan_cache = None
            logger.debug("Кэш доступных моделей сброшен после запуска бэкендов")
        except Exception:
            pass

    # 3) Обновить кэш LocalAIRouter (чтобы выбор модели шёл по актуальным узлам)
    if refresh_local_router_cache:
        try:
            router = _get_local_router_singleton()
            await router.check_health(force_refresh=True)
            logger.debug("Кэш LocalAIRouter обновлён")
        except Exception as e:
            logger.debug("Не удалось обновить кэш LocalAIRouter: %s", e)
