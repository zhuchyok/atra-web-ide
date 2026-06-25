"""
ATRA Web IDE - FastAPI Backend (Улучшенная версия)
Браузерная оболочка для Singularity 31.2+
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys

from app.config import get_settings
from app.routers import chat, files, experts, preview
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
    logger.info("🚀 ATRA Web IDE запускается...")
    logger.info(f"   Victoria: {settings.victoria_url}")
    logger.info(f"   Ollama: {settings.ollama_url}")
    logger.info(f"   Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'N/A'}")
    logger.info(f"   Workspace: {settings.workspace_root}")
    logger.info(f"   Rate Limiting: {'enabled' if settings.rate_limit_enabled else 'disabled'}")

    # Проверка зависимостей при старте
    try:
        from app.services.victoria import get_victoria_client
        from app.services.ollama import get_ollama_client

        victoria = await get_victoria_client()
        ollama = await get_ollama_client()

        # Проверяем доступность сервисов
        victoria_health = await victoria.health()
        ollama_health = await ollama.health()

        if victoria_health.get("status") != "healthy":
            logger.warning(f"⚠️ Victoria недоступна: {victoria_health}")
        else:
            logger.info("✅ Victoria доступна")

        if ollama_health.get("status") != "healthy":
            logger.warning(f"⚠️ Ollama недоступна: {ollama_health}")
        else:
            logger.info("✅ Ollama доступна")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка проверки зависимостей: {e}")

    yield

    logger.info("👋 ATRA Web IDE остановлен")


# FastAPI приложение
app = FastAPI(
    title=settings.app_name,
    description="Браузерная оболочка для ИИ-корпорации Singularity 31.2+",
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


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "singularity": "31.2+",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat",
            "files": "/api/files",
            "experts": "/api/experts",
            "preview": "/api/preview",
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/health")
async def health():
    """Health check с проверкой зависимостей"""
    from app.services.victoria import get_victoria_client
    from app.services.ollama import get_ollama_client

    health_status = {
        "status": "healthy",
        "service": "atra-web-ide",
        "version": settings.api_version
    }

    # Проверка зависимостей
    try:
        victoria = await get_victoria_client()
        ollama = await get_ollama_client()

        victoria_health = await victoria.health()
        ollama_health = await ollama.health()

        health_status["dependencies"] = {
            "victoria": victoria_health.get("status", "unknown"),
            "ollama": ollama_health.get("status", "unknown")
        }

        # Если критичные зависимости недоступны
        if victoria_health.get("status") != "healthy" and ollama_health.get("status") != "healthy":
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
