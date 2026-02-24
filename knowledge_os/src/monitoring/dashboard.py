#!/usr/bin/env python3
"""
📊 МОНИТОРИНГ DASHBOARD ДЛЯ СИСТЕМЫ СИГНАЛОВ
Простой веб-интерфейс для мониторинга pipeline генерации сигналов
"""

import logging
from datetime import datetime

from flask import Flask, jsonify, render_template_string

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# Импортируем мониторинг из исправленной системы
try:
    from hybrid_data_manager import hybrid_data_manager
    from signal_live_hybrid_fixed import pipeline_monitor

    MONITORING_AVAILABLE = True
except ImportError as e:
    logger.error("Не удалось импортировать системы мониторинга: %s", e)
    MONITORING_AVAILABLE = False

app = Flask(__name__)

# HTML шаблон для dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATRA Signal Pipeline Monitor</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #333; }
        .stat-value { font-size: 24px; font-weight: bold; color: #667eea; }
        .stat-details { font-size: 14px; color: #666; margin-top: 5px; }
        .progress-bar { width: 100%; height: 20px; background: #e0e0e0; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #4CAF50, #8BC34A); transition: width 0.3s ease; }
        .error { color: #f44336; }
        .warning { color: #ff9800; }
        .success { color: #4caf50; }
        .refresh-btn { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 10px 0; }
        .refresh-btn:hover { background: #5a6fd8; }
        .timestamp { font-size: 12px; color: #999; text-align: center; margin-top: 20px; }
        .trace-history { max-height: 300px; overflow-y: auto; }
        .trace-item { padding: 5px; border-bottom: 1px solid #eee; font-size: 12px; }
        .trace-passed { color: #4caf50; }
        .trace-blocked { color: #f44336; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ATRA Signal Pipeline Monitor</h1>
            <p>Мониторинг генерации и отправки торговых сигналов</p>
            <button class="refresh-btn" onclick="location.reload()">🔄 Обновить</button>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">📊 Общая статистика</div>
                <div class="stat-value">{{ stats.total_signals }}</div>
                <div class="stat-details">Всего сигналов обработано</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {{ stats.success_rate }}%"></div>
                </div>
                <div class="stat-details">Успешность: {{ stats.success_rate }}%</div>
            </div>

            <div class="stat-card">
                <div class="stat-title">🎯 Фильтры</div>
                <div class="stat-value">{{ stats.filters_passed }}</div>
                <div class="stat-details">Прошли все фильтры</div>
                <div class="stat-details">Заблокировано: {{ stats.filters_blocked }}</div>
            </div>

            <div class="stat-card">
                <div class="stat-title">📱 Telegram</div>
                <div class="stat-value">{{ stats.telegram_sent }}</div>
                <div class="stat-details">Отправлено в Telegram</div>
                <div class="stat-details">Ошибки: {{ stats.telegram_errors }}</div>
            </div>

            <div class="stat-card">
                <div class="stat-title">⚡ Производительность</div>
                <div class="stat-value">{{ stats.avg_response_time }}с</div>
                <div class="stat-details">Среднее время ответа</div>
                <div class="stat-details">Cache hit rate: {{ stats.cache_hit_rate }}%</div>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-title">🔍 Детализация по этапам</div>
                {% for stage, data in stage_stats.items() %}
                <div style="margin: 10px 0;">
                    <strong>{{ stage.upper() }}:</strong> {{ data.passed }}/{{ data.total }} ({{ data.pass_rate }}%)
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {{ data.pass_rate }}%"></div>
                    </div>
                    {% if data.top_block_reasons %}
                    <div style="font-size: 12px; color: #666;">
                        Топ причины блокировки: {{ data.top_block_reasons[:2]|join(', ') }}
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            </div>

            <div class="stat-card">
                <div class="stat-title">📈 Топ символы</div>
                {% for symbol, count in top_symbols.items() %}
                <div style="margin: 5px 0;">
                    {{ symbol }}: {{ count }} запросов
                </div>
                {% endfor %}
            </div>
        </div>

        <div class="timestamp">
            Последнее обновление: {{ timestamp }}
        </div>
    </div>

    <script>
        // Автообновление каждые 30 секунд
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    """Главная страница dashboard"""
    if not MONITORING_AVAILABLE:
        return jsonify({"error": "Система мониторинга недоступна"}), 500

    try:
        # Получаем статистику из pipeline монитора
        pipeline_stats = pipeline_monitor.get_stats()

        # Получаем статистику из data manager
        data_stats = hybrid_data_manager.get_stats()

        # Формируем общую статистику
        total_signals = sum(stage["total"] for stage in pipeline_stats.values())
        passed_signals = sum(stage["passed"] for stage in pipeline_stats.values())
        success_rate = (passed_signals / total_signals * 100) if total_signals > 0 else 0

        filters_passed = pipeline_stats.get("risk_filter", {}).get("passed", 0)
        filters_blocked = sum(stage["blocked"] for stage in pipeline_stats.values())

        telegram_sent = pipeline_stats.get("telegram", {}).get("passed", 0)
        telegram_errors = pipeline_stats.get("telegram", {}).get("blocked", 0)

        avg_response_time = data_stats.get("data_manager", {}).get("average_response_time", 0)
        cache_hit_rate = data_stats.get("data_manager", {}).get("cache_hit_rate", 0)

        top_symbols = data_stats.get("performance", {}).get("top_symbols", {})

        return render_template_string(
            DASHBOARD_TEMPLATE,
            stats={
                "total_signals": total_signals,
                "success_rate": round(success_rate, 1),
                "filters_passed": filters_passed,
                "filters_blocked": filters_blocked,
                "telegram_sent": telegram_sent,
                "telegram_errors": telegram_errors,
                "avg_response_time": round(avg_response_time, 2),
                "cache_hit_rate": round(cache_hit_rate, 1),
            },
            stage_stats=pipeline_stats,
            top_symbols=top_symbols,
            timestamp=get_utc_now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    except Exception as e:
        logger.error("Ошибка в dashboard: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    """API endpoint для получения статистики"""
    if not MONITORING_AVAILABLE:
        return jsonify({"error": "Система мониторинга недоступна"}), 500

    try:
        pipeline_stats = pipeline_monitor.get_stats()
        data_stats = hybrid_data_manager.get_stats()

        return jsonify(
            {
                "pipeline": pipeline_stats,
                "data_manager": data_stats,
                "timestamp": get_utc_now().isoformat(),
            }
        )

    except Exception as e:
        logger.error("Ошибка в API stats: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset")
def api_reset():
    """API endpoint для сброса статистики"""
    if not MONITORING_AVAILABLE:
        return jsonify({"error": "Система мониторинга недоступна"}), 500

    try:
        pipeline_monitor.reset_stats()
        hybrid_data_manager.reset_performance_stats()

        return jsonify({"status": "success", "message": "Статистика сброшена"})

    except Exception as e:
        logger.error("Ошибка при сбросе статистики: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/trace/<trace_id>")
def api_trace(trace_id):
    """API endpoint для получения истории trace ID"""
    if not MONITORING_AVAILABLE:
        return jsonify({"error": "Система мониторинга недоступна"}), 500

    try:
        trace_history = pipeline_monitor.get_trace_history(trace_id)
        return jsonify(
            {"trace_id": trace_id, "history": trace_history, "timestamp": get_utc_now().isoformat()}
        )

    except Exception as e:
        logger.error("Ошибка при получении trace: %s", e)
        return jsonify({"error": str(e)}), 500


def run_monitoring_dashboard(host="0.0.0.0", port=8080, debug=False):
    """Запуск мониторинг dashboard"""
    logger.info("🚀 Запуск мониторинг dashboard на http://%s:%d", host, port)

    try:
        app.run(host=host, port=port, debug=debug, threaded=True)
    except Exception as e:
        logger.error("Ошибка запуска dashboard: %s", e)


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    run_monitoring_dashboard(debug=True)
