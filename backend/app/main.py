"""
ATRA Web IDE - FastAPI Backend (Улучшенная версия)
Браузерная оболочка для Singularity 10.0
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys

from app.config import get_settings
from app.routers import chat, files, experts, preview, domains, knowledge, editor, terminal, plan_cache, rag_optimization, metrics, ab_testing, quality_metrics, latency, cache_stats, auto_optimizer, data_retention, multimodal, system_metrics, sandbox
from app.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler
)
from app.middleware.rate_limiter import RateLimitMiddleware
from app.middleware.logging_middleware import StructuredLoggingMiddleware

# Настройка логирования
settings = get_settings()

if settings.log_format == "json":
    # Structured JSON logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
else:
    # Text logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle управление приложением"""
    import asyncpg

    logger.info("🚀 ATRA Web IDE запускается...")
    logger.info(f"   Victoria: {settings.victoria_url}")
    logger.info(f"   Ollama: {settings.ollama_url}")
    logger.info(f"   Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'N/A'}")
    logger.info(f"   Workspace: {settings.workspace_root}")
    logger.info(f"   Rate Limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}")

    app.state.knowledge_os_pool = None
    try:
        pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
        )
        app.state.knowledge_os_pool = pool
        logger.info("✅ Knowledge OS DB pool создан")
    except Exception as e:
        logger.warning(f"⚠️ Knowledge OS DB pool: {e}")

    try:
        from app.services.victoria import get_victoria_client
        from app.services.ollama import get_ollama_client
        from app.services.mlx import get_mlx_client

        victoria = await get_victoria_client()
        ollama = await get_ollama_client()
        mlx = await get_mlx_client()

        victoria_health = await victoria.health()
        ollama_health = await ollama.health()
        mlx_health = await mlx.health()

        if victoria_health.get("status") != "healthy":
            logger.warning(f"⚠️ Victoria недоступна: {victoria_health}")
        else:
            logger.info("✅ Victoria доступна")

        if ollama_health.get("status") != "healthy":
            logger.warning(f"⚠️ Ollama недоступна: {ollama_health}")
        else:
            logger.info("✅ Ollama доступна")

        if mlx_health.get("status") not in ("healthy", "degraded"):
            logger.warning(f"⚠️ MLX недоступен: {mlx_health}")
        else:
            logger.info("✅ MLX доступен")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка проверки зависимостей: {e}")

    # Фоновая проверка Ollama и MLX каждые health_check_interval сек (логирование; подъём — через скрипты/supervisor на хосте)
    async def _periodic_llm_health():
        import asyncio
        from app.services.ollama import get_ollama_client
        from app.services.mlx import get_mlx_client
        interval = getattr(settings, "health_check_interval", 30)
        while True:
            await asyncio.sleep(interval)
            try:
                o = await get_ollama_client()
                m = await get_mlx_client()
                oh = await o.health()
                mh = await m.health()
                o_ok = oh.get("status") == "healthy"
                m_ok = mh.get("status") in ("healthy", "degraded")
                if not o_ok:
                    logger.warning("[Health] Ollama недоступна — запустите Ollama или проверьте OLLAMA_URL")
                if not m_ok:
                    logger.warning("[Health] MLX недоступен — запустите MLX API Server или проверьте MLX_API_URL")
            except Exception as e:
                logger.debug(f"[Health] LLM check: {e}")

    _health_task = None
    if getattr(settings, "health_check_enabled", True):
        import asyncio
        _health_task = asyncio.create_task(_periodic_llm_health())
        logger.info(f"✅ Фоновая проверка Ollama/MLX каждые {getattr(settings, 'health_check_interval', 30)}с")

    # Прогрев embeddings при старте (P95 < 300ms)
    _warmup_pool = getattr(app.state, "knowledge_os_pool", None)

    async def _embedding_warmup():
        import asyncio
        if not getattr(settings, "rag_embedding_warmup_enabled", True):
            return
        if not _warmup_pool:
            return
        await asyncio.sleep(2)  # Даём health checks завершиться
        try:
            from app.services.knowledge_os import KnowledgeOSClient
            from app.services.rag_light import RAGLightService
            kos = KnowledgeOSClient(pool=_warmup_pool)
            kos._own_pool = False
            rag = RAGLightService(knowledge_os=kos)
            for q in ("сколько стоит", "документация", "поддержка"):
                try:
                    _ = await rag._get_embedding_optimized(q)
                except Exception:
                    pass
            logger.info("✅ Embedding warmup завершён")
        except Exception as e:
            logger.debug("Embedding warmup: %s", e)

    if _warmup_pool and getattr(settings, "rag_embedding_warmup_enabled", True):
        import asyncio
        asyncio.create_task(_embedding_warmup())

    _auto_optimizer_task = None
    if getattr(settings, "auto_optimizer_enabled", False):
        import asyncio
        from app.services.optimization.auto_optimizer import AutoOptimizer
        optimizer = AutoOptimizer()
        optimizer.thresholds["cycle_interval_sec"] = getattr(settings, "auto_optimizer_interval_sec", 300)
        app.state.auto_optimizer = optimizer
        _auto_optimizer_task = asyncio.create_task(optimizer.start())
        logger.info("✅ Auto-Optimizer запущен (интервал %s сек)", optimizer.thresholds["cycle_interval_sec"])
    else:
        app.state.auto_optimizer = None

    yield

    if _auto_optimizer_task and not _auto_optimizer_task.done():
        _auto_optimizer_task.cancel()
        try:
            await _auto_optimizer_task
        except asyncio.CancelledError:
            pass

    if _health_task and not _health_task.done():
        import asyncio
        _health_task.cancel()
        try:
            await _health_task
        except asyncio.CancelledError:
            pass

    if getattr(app.state, "knowledge_os_pool", None) is not None:
        await app.state.knowledge_os_pool.close()
        app.state.knowledge_os_pool = None
        logger.info("Knowledge OS DB pool закрыт")
    logger.info("👋 ATRA Web IDE остановлен")


# FastAPI приложение
app = FastAPI(
    title=settings.app_name,
    description="Браузерная оболочка для ИИ-корпорации Singularity 10.0",
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Middleware (порядок важен!)
app.add_middleware(StructuredLoggingMiddleware)
if settings.rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware)

# CORS - Безопасная конфигурация
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
    expose_headers=["X-Process-Time"]
)

# Обработчики ошибок
app.add_exception_handler(500, general_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Роутеры
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(experts.router, prefix="/api/experts", tags=["Experts"])
app.include_router(preview.router, prefix="/api/preview", tags=["Preview"])
app.include_router(domains.router, prefix="/api/domains", tags=["Domains"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
app.include_router(editor.router, prefix="/api/editor", tags=["Editor"])
app.include_router(terminal.router, prefix="/api/terminal", tags=["Terminal"])
app.include_router(plan_cache.router, prefix="/api/plan-cache")
app.include_router(rag_optimization.router, prefix="/api/rag-optimization")
app.include_router(metrics.router)
app.include_router(ab_testing.router, prefix="/api/ab-testing")
app.include_router(quality_metrics.router)
app.include_router(latency.router)
app.include_router(cache_stats.router)
app.include_router(auto_optimizer.router)
app.include_router(data_retention.router)
app.include_router(multimodal.router, prefix="/api/multimodal", tags=["Multimodal"])
app.include_router(system_metrics.router)
app.include_router(sandbox.router)


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "singularity": "9.0",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat",
            "system_metrics": "/api/system-metrics",
            "files": "/api/files",
            "experts": "/api/experts",
            "preview": "/api/preview",
            "domains": "/api/domains",
            "knowledge": "/api/knowledge",
            "editor": "/api/editor",
            "terminal": "/api/terminal",
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check с проверкой зависимостей (Victoria, Ollama, MLX). Цепочка чата: MLX → Ollama → Victoria."""
    from app.services.victoria import get_victoria_client
    from app.services.ollama import get_ollama_client
    from app.services.mlx import get_mlx_client

    health_status = {
        "status": "healthy",
        "service": "atra-web-ide",
        "version": settings.api_version
    }

    try:
        victoria = await get_victoria_client()
        ollama = await get_ollama_client()
        mlx = await get_mlx_client()

        victoria_health = await victoria.health()
        ollama_health = await ollama.health()
        mlx_health = await mlx.health()

        health_status["dependencies"] = {
            "victoria": victoria_health.get("status", "unknown"),
            "ollama": ollama_health.get("status", "unknown"),
            "mlx": mlx_health.get("status", "unknown")
        }

        # Деградация, если ни один из LLM-бэкендов (Ollama/MLX) и Victoria недоступны
        o_ok = ollama_health.get("status") == "healthy"
        m_ok = mlx_health.get("status") in ("healthy", "degraded")
        v_ok = victoria_health.get("status") == "healthy"
        if not v_ok and not o_ok and not m_ok:
            health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Health check error: {e}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)

    return health_status


@app.get("/api/health")
async def api_health():
    """API health check (для совместимости)"""
    return await health()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower()
    )
