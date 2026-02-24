"""
Enhanced Monitoring System for Knowledge OS
Расширенная система мониторинга с метриками VDS и автоматическими алертами
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List

import asyncpg
import httpx
import psutil

logger = logging.getLogger(__name__)

# Tunnel manager для мониторинга SSH tunnel
try:
    from tunnel_manager import get_tunnel_manager
except ImportError:
    get_tunnel_manager = None

# Настройки
DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
TG_TOKEN = os.getenv("TG_TOKEN", "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU")
CHAT_ID = os.getenv("CHAT_ID", "556251171")
LOG_PATH = "/root/knowledge_os/logs/monitor.log"

# Пороговые значения для алертов
THRESHOLDS = {
    "cpu_percent": 85.0,
    "ram_percent": 85.0,
    "disk_percent": 90.0,
    "db_connections": 80,  # из max_size=20
    "response_time_ms": 1000.0,
}


async def send_telegram_alert(message: str, priority: str = "medium"):
    """Отправка алерта в Telegram"""
    emoji = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "text": f"{emoji} *KNOWLEDGE OS MONITOR*\n\n{message}",
                    "parse_mode": "Markdown",
                },
                timeout=10.0,
            )
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")


def log_message(message: str):
    """Логирование в файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    with open(LOG_PATH, "a") as f:
        f.write(log_entry)
    print(log_entry.strip())


async def get_system_metrics() -> Dict:
    """Сбор системных метрик"""
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": cpu_percent,
            "count": psutil.cpu_count(),
        },
        "ram": {
            "total_gb": round(ram.total / (1024**3), 2),
            "used_gb": round(ram.used / (1024**3), 2),
            "available_gb": round(ram.available / (1024**3), 2),
            "percent": ram.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent": round((disk.used / disk.total) * 100, 2),
        },
    }


async def get_database_metrics() -> Dict:
    """Сбор метрик базы данных"""
    try:
        conn = await asyncpg.connect(DB_URL)

        # Количество подключений
        active_connections = await conn.fetchval(
            "SELECT count(*) FROM pg_stat_activity WHERE datname = 'knowledge_os'"
        )

        # Размер базы данных
        db_size = await conn.fetchval("SELECT pg_database_size('knowledge_os')")

        # Количество узлов знаний
        knowledge_nodes_count = await conn.fetchval("SELECT count(*) FROM knowledge_nodes")

        # Количество экспертов
        experts_count = await conn.fetchval("SELECT count(*) FROM experts")

        # Последняя активность
        last_activity = await conn.fetchval("SELECT max(created_at) FROM knowledge_nodes")

        await conn.close()

        return {
            "active_connections": active_connections,
            "db_size_gb": round(db_size / (1024**3), 2),
            "knowledge_nodes": knowledge_nodes_count,
            "experts": experts_count,
            "last_activity": last_activity.isoformat() if last_activity else None,
        }
    except Exception as e:
        log_message(f"❌ Error getting DB metrics: {e}")
        return {}


async def get_api_health() -> Dict:
    """Проверка здоровья API"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.now()
            response = await client.get("http://localhost:8000/health", timeout=5.0)
            response_time = (datetime.now() - start_time).total_seconds() * 1000

            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "status_code": response.status_code,
                "response_time_ms": round(response_time, 2),
            }
    except Exception as e:
        return {
            "status": "unreachable",
            "error": str(e),
        }


async def get_ab_test_metrics() -> Dict:
    """Получает метрики A/B тестирования ML-роутинга"""
    try:
        from ml_router_ab_test import get_ab_test

        ab_test = await get_ab_test()
        stats = await ab_test.get_ab_test_statistics(days=7)
        return stats
    except Exception as e:
        logger.error(f"Error getting AB test metrics: {e}")
        return {
            "ml": {"count": 0, "avg_performance": 0, "avg_tokens_saved": 0, "success_rate": 0},
            "heuristic": {
                "count": 0,
                "avg_performance": 0,
                "avg_tokens_saved": 0,
                "success_rate": 0,
            },
        }


async def get_adaptive_learning_metrics() -> Dict:
    """Получает метрики адаптивного обучения"""
    try:
        from adaptive_learner import AdaptiveLearner
        from feedback_collector import get_feedback_collector

        learner = AdaptiveLearner()
        collector = await get_feedback_collector()

        feedback_stats = await collector.get_feedback_statistics(days=7)

        return {
            "feedback_total": feedback_stats.get("total", 0),
            "feedback_positive_rate": feedback_stats.get("positive_rate", 0),
            "reroute_rate": feedback_stats.get("reroute_rate", 0),
            "improvement_trend": "analyzing",  # Будет вычисляться на основе истории
        }
    except Exception as e:
        logger.error(f"Error getting adaptive learning metrics: {e}")
        return {
            "feedback_total": 0,
            "feedback_positive_rate": 0,
            "reroute_rate": 0,
            "improvement_trend": "unknown",
        }


async def get_routing_metrics() -> Dict:
    """Сбор метрик гибридного роутинга из semantic_ai_cache"""
    try:
        conn = await asyncpg.connect(DB_URL)

        # Проверяем, есть ли колонки для метрик роутинга
        columns_exist = (
            await conn.fetchval("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'semantic_ai_cache'
            AND column_name IN ('routing_source', 'performance_score', 'tokens_saved')
        """)
            == 3
        )

        if not columns_exist:
            await conn.close()
            return {}

        # Статистика по источникам роутинга за последние 24 часа
        routing_stats = await conn.fetch("""
            SELECT
                routing_source,
                COUNT(*) as count,
                AVG(performance_score) as avg_performance,
                SUM(tokens_saved) as total_tokens_saved,
                AVG(tokens_saved) as avg_tokens_saved
            FROM semantic_ai_cache
            WHERE routing_source IS NOT NULL
            AND last_used_at > NOW() - INTERVAL '24 hours'
            GROUP BY routing_source
        """)

        # Общая статистика за сегодня
        today_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_requests,
                SUM(tokens_saved) as total_tokens_saved_today,
                AVG(performance_score) as avg_performance_today
            FROM semantic_ai_cache
            WHERE routing_source IS NOT NULL
            AND last_used_at > CURRENT_DATE
        """)

        # Статистика по узлам (Mac vs Server)
        node_stats = {}
        for stat in routing_stats:
            source = stat["routing_source"]
            if source:
                node_stats[source] = {
                    "count": stat["count"],
                    "avg_performance": round(float(stat["avg_performance"] or 0), 3),
                    "total_tokens_saved": stat["total_tokens_saved"] or 0,
                    "avg_tokens_saved": round(float(stat["avg_tokens_saved"] or 0), 0),
                }

        await conn.close()

        return {
            "nodes": node_stats,
            "today": {
                "total_requests": today_stats["total_requests"] or 0,
                "total_tokens_saved": today_stats["total_tokens_saved"] or 0,
                "avg_performance": round(float(today_stats["avg_performance"] or 0), 3),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        log_message(f"❌ Error getting routing metrics: {e}")
        return {}


async def check_thresholds(metrics: Dict) -> List[Dict]:
    """Проверка пороговых значений и генерация алертов"""
    alerts = []

    # CPU
    if metrics["system"]["cpu"]["percent"] > THRESHOLDS["cpu_percent"]:
        alerts.append(
            {
                "priority": "high",
                "metric": "CPU",
                "value": f"{metrics['system']['cpu']['percent']}%",
                "threshold": f"{THRESHOLDS['cpu_percent']}%",
                "message": f"⚠️ Высокая загрузка CPU: {metrics['system']['cpu']['percent']}%",
            }
        )

    # RAM
    if metrics["system"]["ram"]["percent"] > THRESHOLDS["ram_percent"]:
        alerts.append(
            {
                "priority": "high",
                "metric": "RAM",
                "value": f"{metrics['system']['ram']['percent']}%",
                "threshold": f"{THRESHOLDS['ram_percent']}%",
                "message": f"⚠️ Высокое использование RAM: {metrics['system']['ram']['percent']}% ({metrics['system']['ram']['used_gb']}GB / {metrics['system']['ram']['total_gb']}GB)",
            }
        )

    # Disk
    if metrics["system"]["disk"]["percent"] > THRESHOLDS["disk_percent"]:
        alerts.append(
            {
                "priority": "high",
                "metric": "Disk",
                "value": f"{metrics['system']['disk']['percent']}%",
                "threshold": f"{THRESHOLDS['disk_percent']}%",
                "message": f"⚠️ Мало места на диске: {metrics['system']['disk']['percent']}% ({metrics['system']['disk']['used_gb']}GB / {metrics['system']['disk']['total_gb']}GB)",
            }
        )

    # Database connections
    if metrics.get("database", {}).get("active_connections", 0) > THRESHOLDS["db_connections"]:
        alerts.append(
            {
                "priority": "medium",
                "metric": "DB Connections",
                "value": metrics["database"]["active_connections"],
                "threshold": THRESHOLDS["db_connections"],
                "message": f"⚠️ Много подключений к БД: {metrics['database']['active_connections']}",
            }
        )

    # API response time
    if metrics.get("api", {}).get("response_time_ms", 0) > THRESHOLDS["response_time_ms"]:
        alerts.append(
            {
                "priority": "medium",
                "metric": "API Response Time",
                "value": f"{metrics['api']['response_time_ms']}ms",
                "threshold": f"{THRESHOLDS['response_time_ms']}ms",
                "message": f"⚠️ Медленный ответ API: {metrics['api']['response_time_ms']}ms",
            }
        )

    # API unreachable
    if metrics.get("api", {}).get("status") == "unreachable":
        alerts.append(
            {
                "priority": "high",
                "metric": "API Status",
                "value": "unreachable",
                "threshold": "healthy",
                "message": f"❌ API недоступен: {metrics['api'].get('error', 'Unknown error')}",
            }
        )

    return alerts


async def save_metrics_to_db(metrics: Dict):
    """Сохранение метрик в БД для истории"""
    try:
        conn = await asyncpg.connect(DB_URL)

        # Создаем таблицу если нет
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT NOW(),
                metrics JSONB NOT NULL
            )
        """)

        # Сохраняем метрики
        await conn.execute(
            """
            INSERT INTO system_metrics (metrics)
            VALUES ($1)
        """,
            json.dumps(metrics),
        )

        # Очищаем старые метрики (оставляем последние 7 дней)
        await conn.execute("""
            DELETE FROM system_metrics
            WHERE timestamp < NOW() - INTERVAL '7 days'
        """)

        await conn.close()
        log_message("✅ Metrics saved to database")
    except Exception as e:
        log_message(f"❌ Error saving metrics to DB: {e}")


async def run_adaptive_learning_cycle():
    """Запускает цикл адаптивного обучения"""
    try:
        from adaptive_learner import run_adaptive_learning_cycle

        updated, deleted = await run_adaptive_learning_cycle()
        logger.info(f"✅ [ADAPTIVE LEARNING] Cycle completed: {updated} updated, {deleted} deleted")
        return {"updated": updated, "deleted": deleted}
    except ImportError:
        logger.warning("⚠️ AdaptiveLearner not available")
        return {"updated": 0, "deleted": 0}
    except Exception as e:
        logger.error(f"❌ [ADAPTIVE LEARNING] Error: {e}")
        return {"updated": 0, "deleted": 0}


async def run_monitoring_cycle():
    """Основной цикл мониторинга"""
    log_message("🔍 Starting monitoring cycle...")

    # Сбор метрик
    system_metrics = await get_system_metrics()
    db_metrics = await get_database_metrics()
    api_health = await get_api_health()
    routing_metrics = await get_routing_metrics()

    metrics = {
        "system": system_metrics,
        "database": db_metrics,
        "api": api_health,
        "routing": routing_metrics,
    }

    # Сохранение метрик
    await save_metrics_to_db(metrics)

    # Проверка порогов
    alerts = await check_thresholds(metrics)

    # Self-Healing: проверка и исправление узлов
    try:
        from self_healing import SelfHealingManager

        manager = SelfHealingManager()
        nodes = [
            {"name": "MacBook (Normal)", "url": os.getenv("MAC_LLM_URL", "http://localhost:11434")},
            {
                "name": "Server (Light)",
                "url": os.getenv("SERVER_LLM_URL", "http://localhost:11434"),
            },
        ]
        healed_nodes = await manager.check_and_heal(nodes)

        # Добавляем алерты для оффлайн узлов
        for node in healed_nodes:
            if node.get("status") == "offline" and not node.get("healed"):
                alerts.append(
                    {
                        "priority": "high",
                        "metric": "Node Status",
                        "value": "offline",
                        "threshold": "online",
                        "message": f"❌ Узел {node['name']} оффлайн",
                    }
                )
    except Exception as e:
        log_message(f"⚠️ Self-healing check failed: {e}")

    # Сбор SLA метрик (улучшенная версия через sla_monitor)
    # Перенесено в секцию "Мониторинг SLA/SLO" ниже

    # Отправка алертов
    if alerts:
        for alert in alerts:
            await send_telegram_alert(alert["message"], alert["priority"])
            log_message(f"🚨 Alert sent: {alert['message']}")
    else:
        log_message("✅ All metrics within thresholds")

    # Логирование метрик
    log_message(
        f"📊 CPU: {system_metrics['cpu']['percent']}% | RAM: {system_metrics['ram']['percent']}% | Disk: {system_metrics['disk']['percent']}%"
    )
    if db_metrics:
        log_message(
            f"📊 DB: {db_metrics.get('knowledge_nodes', 0)} nodes | {db_metrics.get('experts', 0)} experts | {db_metrics.get('db_size_gb', 0)}GB"
        )
    if api_health:
        log_message(
            f"📊 API: {api_health.get('status', 'unknown')} | {api_health.get('response_time_ms', 0)}ms"
        )
    if routing_metrics:
        today = routing_metrics.get("today", {})
        log_message(
            f"📊 Routing: {today.get('total_requests', 0)} requests | {today.get('total_tokens_saved', 0)} tokens saved | Performance: {today.get('avg_performance', 0):.2f}"
        )
        nodes = routing_metrics.get("nodes", {})
        for node_name, node_data in nodes.items():
            log_message(
                f"   └─ {node_name}: {node_data.get('count', 0)} requests, {node_data.get('total_tokens_saved', 0)} tokens saved"
            )

    # Мониторинг SSH tunnel
    if get_tunnel_manager:
        try:
            tunnel_manager = get_tunnel_manager()
            if tunnel_manager:
                tunnel_status = tunnel_manager.check_tunnel()
                if tunnel_status:
                    log_message(f"✅ SSH Tunnel: активен (порт {tunnel_manager.tunnel_port})")
                else:
                    log_message("⚠️ SSH Tunnel: недоступен, пересоздаю...")
                    tunnel_manager.create_tunnel()
        except Exception as e:
            logger.debug(f"Tunnel monitoring failed: {e}")

    # Мониторинг SLA/SLO
    try:
        from sla_monitor import get_sla_monitor
        from telegram_alerter import get_telegram_alerter

        sla_monitor = get_sla_monitor()
        sla_compliance = await sla_monitor.check_sla_compliance()

        violations = []
        for metric_name, metric_data in sla_compliance.items():
            if not metric_data.get("compliant", True):
                value = metric_data.get("value", 0)
                target = metric_data.get("target", 0)
                unit = metric_data.get("unit", "")
                violations.append(f"{metric_name}: {value:.3f}{unit} (target: {target:.3f}{unit})")

        if violations:
            alert_msg = "🚨 SLA Violations detected:\n" + "\n".join(f"  • {v}" for v in violations)
            log_message(alert_msg)

            # Отправляем через централизованный Telegram Alerter
            alerter = get_telegram_alerter()
            await alerter.send_alert(alert_msg, priority="high", source="SLA Monitor")
        else:
            log_message("✅ Все SLA метрики соответствуют требованиям")

            # Логируем значения для мониторинга
            for metric_name, metric_data in sla_compliance.items():
                value = metric_data.get("value", 0)
                target = metric_data.get("target", 0)
                unit = metric_data.get("unit", "")
                log_message(
                    f"   • {metric_name}: {value:.3f}{unit} (target: {target:.3f}{unit}) ✅"
                )
    except Exception as e:
        logger.debug(f"SLA monitoring failed: {e}")

    # Мониторинг Disaster Recovery
    try:
        from disaster_recovery import get_disaster_recovery

        disaster_recovery = get_disaster_recovery()
        mode_info = disaster_recovery.get_mode_info()

        if mode_info["mode"] != "normal":
            alert_msg = f"🔄 Режим работы: {mode_info['mode']}"
            log_message(alert_msg)
            await send_telegram_alert(alert_msg, "medium")
    except Exception as e:
        logger.debug(f"Disaster recovery monitoring failed: {e}")

    # Мониторинг памяти моделей
    try:
        import os

        from model_memory_manager import get_memory_manager

        server_url = os.getenv("SERVER_LLM_URL", "http://localhost:11434")
        memory_manager = get_memory_manager(server_url)
        memory_stats = await memory_manager.get_memory_stats()

        available_mb = memory_stats.get("available_memory_mb", 0)
        actual_memory_usage = memory_stats.get("actual_memory_usage_mb", {})

        # Проверяем критическую нехватку памяти
        if available_mb < 200:
            alert_msg = f"⚠️ Критическая нехватка памяти на сервере: {available_mb}MB"
            log_message(alert_msg)
            await send_telegram_alert(alert_msg, "high")

        # Логируем реальное использование памяти моделями
        if actual_memory_usage:
            log_message("📊 Реальное использование памяти моделями:")
            for model_name, memory_mb in actual_memory_usage.items():
                log_message(f"   • {model_name}: {memory_mb:.2f} MB")

                # Предупреждение, если модель использует слишком много памяти
                if memory_mb > 1000:  # Больше 1GB
                    alert_msg = f"⚠️ Модель {model_name} использует {memory_mb:.2f}MB памяти"
                    await send_telegram_alert(alert_msg, "medium")
    except Exception as e:
        logger.debug(f"Memory monitoring failed: {e}")

    # Adaptive Learning: запуск цикла адаптивного обучения (ежедневно)
    # Проверяем, нужно ли запускать (например, раз в день)
    try:
        adaptive_result = await run_adaptive_learning_cycle()
        if adaptive_result.get("updated", 0) > 0 or adaptive_result.get("deleted", 0) > 0:
            log_message(
                f"🔄 [ADAPTIVE LEARNING] Updated {adaptive_result.get('updated', 0)} examples, deleted {adaptive_result.get('deleted', 0)}"
            )
    except Exception as e:
        logger.debug(f"Adaptive learning cycle failed: {e}")

    # Мониторинг Circuit Breaker событий
    try:
        conn = await asyncpg.connect(DB_URL)
        try:
            # Получаем открытые circuit breakers за последний час
            open_breakers = await conn.fetch("""
                SELECT breaker_name, COUNT(*) as event_count, MAX(created_at) as last_event
                FROM circuit_breaker_events
                WHERE new_state = 'open' AND created_at > NOW() - INTERVAL '1 hour'
                GROUP BY breaker_name
            """)

            if open_breakers:
                for breaker in open_breakers:
                    alert_msg = (
                        f"⚠️ Circuit Breaker '{breaker['breaker_name']}' в состоянии OPEN. "
                        f"Событий за час: {breaker['event_count']}. "
                        f"Последнее: {breaker['last_event']}"
                    )
                    log_message(alert_msg)
                    await send_telegram_alert(alert_msg, "high")

            # Получаем статистику по всем circuit breakers
            breaker_stats = await conn.fetch("""
                SELECT
                    breaker_name,
                    COUNT(*) FILTER (WHERE event_type = 'state_change' AND new_state = 'open') as open_count,
                    COUNT(*) FILTER (WHERE event_type = 'success') as success_count,
                    COUNT(*) FILTER (WHERE event_type = 'failure') as failure_count
                FROM circuit_breaker_events
                WHERE created_at > NOW() - INTERVAL '24 hours'
                GROUP BY breaker_name
            """)

            if breaker_stats:
                log_message("📊 Статистика Circuit Breaker за 24 часа:")
                for stat in breaker_stats:
                    log_message(
                        f"   • {stat['breaker_name']}: "
                        f"OPEN={stat['open_count']}, "
                        f"SUCCESS={stat['success_count']}, "
                        f"FAILURE={stat['failure_count']}"
                    )
        finally:
            await conn.close()
    except Exception as e:
        logger.debug(f"Circuit breaker monitoring failed: {e}")

    # Сбор реальных метрик производительности
    try:
        from metrics_collector import get_metrics_collector

        metrics_collector = get_metrics_collector()

        # Собираем системные метрики
        if system_metrics:
            cpu_percent = system_metrics.get("cpu", {}).get("percent", 0)
            ram_percent = system_metrics.get("ram", {}).get("percent", 0)

            # Сохраняем метрики (можно добавить температуру, если доступна)
            # await metrics_collector.collect_temperature(cpu_temp, 'cpu', 'system')

        # Принудительно сохраняем накопленные метрики
        await metrics_collector.flush()

        # Получаем статистику за последние 24 часа
        tokens_stats = await metrics_collector.get_metrics_stats("tokens_per_second", hours=24)
        if tokens_stats.get("count", 0) > 0:
            log_message(
                f"📊 Токенов/сек (24ч): avg={tokens_stats.get('avg', 0):.2f}, "
                f"min={tokens_stats.get('min', 0):.2f}, max={tokens_stats.get('max', 0):.2f}"
            )
    except Exception as e:
        logger.debug(f"Metrics collection failed: {e}")

    # Интеграция автономных компонентов Singularity 7.5
    try:
        # Auto Model Manager - оптимизация моделей по времени
        from auto_model_manager import get_auto_model_manager

        auto_model_mgr = get_auto_model_manager()
        if not auto_model_mgr._running:
            auto_model_mgr.start_monitoring()
            log_message("🔄 Auto Model Manager запущен")
    except Exception as e:
        logger.debug(f"Auto Model Manager integration failed: {e}")

    try:
        # Auto Backup Manager - автоматические бэкапы
        from auto_backup_manager import get_auto_backup_manager

        backup_mgr = get_auto_backup_manager()
        if not backup_mgr._running:
            backup_mgr.start_monitoring()
            log_message("💾 Auto Backup Manager запущен")
    except Exception as e:
        logger.debug(f"Auto Backup Manager integration failed: {e}")

    try:
        # Anomaly Detector - детектирование аномалий
        from anomaly_detector import get_anomaly_detector

        anomaly_detector = get_anomaly_detector()
        anomaly_stats = await anomaly_detector.get_anomaly_stats(hours=24)
        if anomaly_stats:
            log_message("🚨 Статистика аномалий за 24 часа:")
            for key, count in anomaly_stats.items():
                log_message(f"   • {key}: {count}")
    except Exception as e:
        logger.debug(f"Anomaly Detector integration failed: {e}")

    # Predictive Cache Warming - анализ паттернов и предсказание запросов
    try:
        from optimizers import PredictiveCache
        from semantic_cache import SemanticAICache

        cache_manager = SemanticAICache()
        pred_cache = PredictiveCache(cache_manager, db_url=DB_URL)

        # Анализируем паттерны за последние 24 часа
        patterns = await pred_cache.analyze_query_history(hours=24)

        if patterns:
            log_message("📊 Predictive Cache: Анализ паттернов за 24 часа:")

            # Топ ключевые слова
            if patterns.get("keywords"):
                top_keywords = sorted(
                    patterns["keywords"].items(), key=lambda x: x[1], reverse=True
                )[:5]
                log_message(
                    f"   🔑 Топ ключевые слова: {', '.join([f'{kw}({count})' for kw, count in top_keywords])}"
                )

            # Топ последовательности
            if patterns.get("sequences"):
                top_sequences = sorted(
                    patterns["sequences"].items(), key=lambda x: x[1], reverse=True
                )[:3]
                log_message(
                    f"   🔗 Топ последовательности: {', '.join([f'{seq}({count})' for seq, count in top_sequences])}"
                )

            # Топ категории
            if patterns.get("categories"):
                top_categories = sorted(
                    patterns["categories"].items(), key=lambda x: x[1], reverse=True
                )[:3]
                log_message(
                    f"   📂 Топ категории: {', '.join([f'{cat}({count})' for cat, count in top_categories])}"
                )

            # Временные паттерны
            if patterns.get("temporal"):
                top_temporal = sorted(
                    patterns["temporal"].items(), key=lambda x: x[1], reverse=True
                )[:3]
                log_message(
                    f"   🕐 Топ временные паттерны: {', '.join([f'{time}({count})' for time, count in top_temporal])}"
                )
        else:
            log_message("📊 Predictive Cache: Недостаточно данных для анализа паттернов")
    except Exception as e:
        logger.debug(f"Predictive Cache integration failed: {e}")

    try:
        # Model Validator - валидация моделей (раз в день)
        from datetime import datetime

        current_hour = datetime.now().hour
        if current_hour == 2:  # Запускаем в 2:00 ночи
            from model_validator import get_model_validator

            validator = get_model_validator()
            validation_results = await validator.validate_all_models()
            if validation_results:
                passed_count = sum(1 for r in validation_results if r.passed)
                log_message(
                    f"✅ Валидация моделей: {passed_count}/{len(validation_results)} прошли"
                )
    except Exception as e:
        logger.debug(f"Model Validator integration failed: {e}")

    try:
        # Auto Prompt Optimizer - анализ и предложения улучшений (раз в день)
        if current_hour == 3:  # Запускаем в 3:00 ночи
            from auto_prompt_optimizer import get_auto_prompt_optimizer

            optimizer = get_auto_prompt_optimizer()
            # Получаем текущий системный промпт (пример)
            current_prompt = "Ты - Виктория, Team Lead команды экспертов..."
            improvements = await optimizer.suggest_improvements(current_prompt, "Виктория")
            if improvements:
                log_message(f"💡 Найдено {len(improvements)} предложений по улучшению промптов")
                for imp in improvements[:3]:  # Показываем топ-3
                    log_message(f"   • {imp.improvement_reason} (impact: {imp.expected_impact})")
                    # Логируем улучшение в БД
                    await optimizer.log_improvement(imp, "Виктория", applied=False)
    except Exception as e:
        logger.debug(f"Auto Prompt Optimizer integration failed: {e}")

    log_message("✅ Monitoring cycle completed")


if __name__ == "__main__":
    asyncio.run(run_monitoring_cycle())
