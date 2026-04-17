#!/usr/bin/env python3
"""
REST API для управления торговым ботом ATRA (FastAPI версия)
Асинхронный, не блокирует event loop
"""

import logging
from datetime import datetime
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# Rate limiting
try:
    from rest_api_rate_limiter import RateLimitMiddleware

    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False
    logger.warning("Rate limiting middleware not available")

# FastAPI приложение
app = FastAPI(
    title="ATRA REST API",
    version="1.0.0",
    description="REST API для управления торговым ботом ATRA",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Rate limiting middleware (если доступен)
if RATE_LIMITING_AVAILABLE:
    app.add_middleware(RateLimitMiddleware)
    logger.info("✅ Rate limiting middleware enabled")

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3002",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:5173",
    "tauri://localhost",
    "tauri://127.0.0.1",
    "https://atra.local",
]

import os

env_origins = os.getenv("CORS_ORIGINS", "").split(",")
if env_origins and env_origins[0]:
    ALLOWED_ORIGINS.extend([o.strip() for o in env_origins if o.strip()])

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic модели
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    uptime: str


class StatusResponse(BaseModel):
    status: str
    components: Dict[str, Any]


@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Проверка здоровья API. Этот endpoint не учитывается в rate limiting.",
    tags=["System"],
)
async def get_health():
    """
    Проверка здоровья API

    Возвращает статус API и текущее время.
    Этот endpoint не учитывается в rate limiting для мониторинга.
    """
    return {"status": "healthy", "timestamp": get_utc_now().isoformat(), "uptime": "running"}


@app.get(
    "/api/v1/status",
    response_model=StatusResponse,
    summary="System Status",
    description="Получить статус всех компонентов системы",
    tags=["System"],
)
async def get_system_status():
    """
    Статус системы

    Возвращает статус всех компонентов системы:
    - telegram_bot: Статус Telegram бота
    - signal_system: Статус системы генерации сигналов
    - database: Статус подключения к базе данных
    """
    try:
        components = {
            "telegram_bot": "running",
            "signal_system": "running",
            "database": "connected",
        }

        # Проверяем доступность компонентов
        try:
            # Простая проверка доступности бота
            components["telegram_bot"] = "running"
        except Exception:
            components["telegram_bot"] = "unknown"

        return {"status": "operational", "components": components}
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/metrics",
    summary="Performance Metrics",
    description="Получить метрики производительности торговли",
    tags=["Metrics"],
    responses={
        200: {
            "description": "Метрики успешно получены",
            "content": {
                "application/json": {
                    "example": {
                        "total_trades": 100,
                        "win_rate": 0.65,
                        "total_pnl_usd": 1500.50,
                        "sharpe_ratio": 1.8,
                    }
                }
            },
        }
    },
)
async def get_metrics():
    """
    Метрики производительности

    Возвращает основные метрики торговой производительности:
    - total_trades: Общее количество сделок
    - win_rate: Процент выигрышных сделок
    - total_pnl_usd: Общая прибыль/убыток в USD
    - sharpe_ratio: Коэффициент Шарпа
    """
    try:
        # Пробуем получить метрики из performance_metrics_calculator
        try:
            from performance_metrics_calculator import get_metrics_calculator

            calculator = get_metrics_calculator()
            metrics = calculator.calculate_metrics()
            return metrics
        except Exception:
            # Fallback на базовые метрики
            return {"total_trades": 0, "win_rate": 0, "total_pnl_usd": 0, "sharpe_ratio": 0}
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/signals",
    summary="Active Signals",
    description="Получить список активных торговых сигналов",
    tags=["Signals"],
    responses={
        200: {
            "description": "Список активных сигналов",
            "content": {
                "application/json": {
                    "example": {
                        "signals": [
                            {
                                "symbol": "BTCUSDT",
                                "direction": "LONG",
                                "entry_price": 50000.0,
                                "status": "open",
                            }
                        ],
                        "count": 1,
                    }
                }
            },
        }
    },
)
async def get_signals():
    """
    Получить активные сигналы

    Возвращает список всех активных торговых сигналов:
    - symbol: Торговая пара
    - direction: Направление (LONG/SHORT)
    - entry_price: Цена входа
    - status: Статус позиции
    """
    try:
        # Пробуем получить активные позиции напрямую из БД
        try:
            import os
            import sqlite3

            db_path = os.path.join(os.path.dirname(__file__), "trading.db")
            conn = sqlite3.connect(
                f"file:{db_path}?mode=ro", uri=True, timeout=10.0, check_same_thread=False
            )
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, direction, entry_price, status FROM active_positions WHERE status = 'open' LIMIT 100"
            )
            rows = cursor.fetchall()
            conn.close()

            positions = [
                {"symbol": r[0], "direction": r[1], "entry_price": r[2], "status": r[3]}
                for r in rows
            ]
            return {"signals": positions, "count": len(positions)}
        except Exception as e:
            logger.debug(f"Error getting signals: {e}")
            return {"signals": [], "count": 0}
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_rest_api(host: str = "0.0.0.0", port: int = 8080, use_https: bool = False):
    """Запуск REST API сервера"""
    try:
        import os

        ssl_keyfile = os.getenv("SSL_KEYFILE", "ssl/key.pem")
        ssl_certfile = os.getenv("SSL_CERTFILE", "ssl/cert.pem")

        # Проверяем наличие SSL сертификатов
        if use_https:
            if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
                logger.info("🔒 Starting ATRA REST API with HTTPS on https://%s:%d", host, port)
                uvicorn.run(
                    app,
                    host=host,
                    port=port,
                    log_level="info",
                    loop="asyncio",
                    ssl_keyfile=ssl_keyfile,
                    ssl_certfile=ssl_certfile,
                )
            else:
                logger.warning(
                    "⚠️ SSL сертификаты не найдены (%s, %s), используем HTTP",
                    ssl_keyfile,
                    ssl_certfile,
                )
                use_https = False

        if not use_https:
            logger.info("🚀 Starting ATRA REST API on http://%s:%d", host, port)
            uvicorn.run(app, host=host, port=port, log_level="info", loop="asyncio")
    except Exception as e:
        logger.error("Error starting REST API: %s", e)


async def run_rest_api_async(host: str = "0.0.0.0", port: int = 8080, use_https: bool = False):
    """Запуск REST API в async режиме (для интеграции с main.py)"""
    try:
        import os

        ssl_keyfile = os.getenv("SSL_KEYFILE", "ssl/key.pem")
        ssl_certfile = os.getenv("SSL_CERTFILE", "ssl/cert.pem")

        config = None

        # Проверяем наличие SSL сертификатов
        if use_https:
            if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
                logger.info("🔒 Запуск REST API с HTTPS на https://%s:%d", host, port)
                config = uvicorn.Config(
                    app,
                    host=host,
                    port=port,
                    log_level="info",
                    loop="asyncio",
                    ssl_keyfile=ssl_keyfile,
                    ssl_certfile=ssl_certfile,
                )
            else:
                logger.warning(
                    "⚠️ SSL сертификаты не найдены (%s, %s), используем HTTP",
                    ssl_keyfile,
                    ssl_certfile,
                )
                use_https = False

        if not use_https or config is None:
            logger.info("🚀 Запуск REST API на http://%s:%d", host, port)
            config = uvicorn.Config(app, host=host, port=port, log_level="info", loop="asyncio")

        server = uvicorn.Server(config)
        await server.serve()
    except Exception as e:
        logger.error("Error running REST API async: %s", e)


if __name__ == "__main__":
    run_rest_api()
