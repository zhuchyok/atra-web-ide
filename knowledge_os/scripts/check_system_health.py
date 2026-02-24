#!/usr/bin/env python3
"""
Скрипт для проверки здоровья системы на проде

Автор: Сергей (DevOps) + Елена (Monitor) - Priority 2
"""

import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def check_database() -> Dict[str, Any]:
    """Проверка базы данных"""
    results = {
        "status": "unknown",
        "signals_count": 0,
        "active_signals_count": 0,
        "recent_signals": [],
        "errors": [],
    }

    try:
        db_path = os.getenv("DATABASE", "trading.db")
        if not os.path.exists(db_path):
            results["status"] = "error"
            results["errors"].append(f"База данных не найдена: {db_path}")
            return results

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверка таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        if "signals" not in tables:
            results["status"] = "error"
            results["errors"].append("Таблица 'signals' не найдена")
            return results

        # Количество сигналов
        cursor.execute("SELECT COUNT(*) FROM signals")
        results["signals_count"] = cursor.fetchone()[0]

        # Активные сигналы
        if "active_signals" in tables:
            cursor.execute("SELECT COUNT(*) FROM active_signals")
            results["active_signals_count"] = cursor.fetchone()[0]

        # Последние сигналы (за последние 24 часа)
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]

        # Определяем доступные колонки
        available_cols = []
        if "symbol" in columns:
            available_cols.append("symbol")
        if "side" in columns:
            available_cols.append("side")
        elif "direction" in columns:
            available_cols.append("direction")
        if "entry_price" in columns:
            available_cols.append("entry_price")
        elif "price" in columns:
            available_cols.append("price")
        if "created_at" in columns:
            available_cols.append("created_at")
        elif "ts" in columns:
            available_cols.append("ts")

        # Формируем запрос с доступными колонками
        if len(available_cols) >= 2:
            cols_str = ", ".join(available_cols)
            time_col = "created_at" if "created_at" in available_cols else "ts"
            cursor.execute(f"""
                SELECT {cols_str}
                FROM signals
                WHERE datetime({time_col}) > datetime('now', '-1 day')
                ORDER BY {time_col} DESC
                LIMIT 10
            """)
            results["recent_signals"] = cursor.fetchall()
        else:
            results["recent_signals"] = []

        results["status"] = "ok"
        conn.close()

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Ошибка проверки БД: {e}")
        logger.error(f"❌ Ошибка проверки БД: {e}")

    return results


def check_ml_models() -> Dict[str, Any]:
    """Проверка ML моделей"""
    results = {"status": "unknown", "models_available": False, "models_path": None, "errors": []}

    try:
        # Проверяем наличие LightGBM
        try:
            import lightgbm as lgb

            results["lightgbm_available"] = True
        except ImportError:
            results["lightgbm_available"] = False
            results["errors"].append("LightGBM не установлен")

        # Проверяем наличие моделей
        models_path = Path("ai_learning_data/lightgbm_models")
        if models_path.exists():
            results["models_path"] = str(models_path)
            model_files = list(models_path.glob("*.txt"))
            results["models_count"] = len(model_files)
            results["models_available"] = len(model_files) > 0
        else:
            results["models_available"] = False
            results["errors"].append(f"Путь к моделям не найден: {models_path}")

        # Проверяем predictor
        try:
            # Пробуем разные варианты импорта
            try:
                from lightgbm_predictor import LightGBMPredictor
            except ImportError:
                # Пробуем альтернативный путь
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from lightgbm_predictor import LightGBMPredictor

            predictor = LightGBMPredictor()
            results["predictor_available"] = True
            results["predictor_trained"] = predictor.is_trained
        except Exception as e:
            results["predictor_available"] = False
            results["errors"].append(f"Ошибка загрузки predictor: {e}")
            logger.debug(f"⚠️ Predictor недоступен (не критично): {e}")

        results["status"] = "ok" if results.get("models_available", False) else "warning"

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Ошибка проверки ML: {e}")
        logger.error(f"❌ Ошибка проверки ML: {e}")

    return results


def check_prometheus_metrics() -> Dict[str, Any]:
    """Проверка метрик Prometheus"""
    results = {
        "status": "unknown",
        "metrics_available": False,
        "metrics_endpoint": None,
        "errors": [],
    }

    try:
        # Проверяем наличие prometheus_metrics
        try:
            from prometheus_metrics import METRICS_SERVER_PORT

            results["metrics_available"] = True
            results["metrics_endpoint"] = f"http://localhost:{METRICS_SERVER_PORT}/metrics"
        except ImportError:
            results["metrics_available"] = False
            results["errors"].append("Prometheus metrics не доступны")

        # Проверяем доступность endpoint (если сервер запущен)
        if results["metrics_available"]:
            try:
                import requests

                response = requests.get(results["metrics_endpoint"], timeout=2)
                results["metrics_server_running"] = response.status_code == 200
            except Exception:
                results["metrics_server_running"] = False
                results["errors"].append("Метрики сервер не отвечает")

        results["status"] = "ok" if results.get("metrics_available", False) else "warning"

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Ошибка проверки метрик: {e}")
        logger.error(f"❌ Ошибка проверки метрик: {e}")

    return results


def check_logs() -> Dict[str, Any]:
    """Проверка логов"""
    results = {"status": "unknown", "log_files": [], "recent_errors": [], "errors": []}

    try:
        logs_dir = Path("logs")
        if logs_dir.exists():
            log_files = list(logs_dir.glob("*.log"))
            results["log_files"] = [str(f) for f in log_files]

            # Проверяем последние ошибки
            for log_file in log_files[:3]:  # Проверяем первые 3 файла
                try:
                    with open(log_file, encoding="utf-8") as f:
                        lines = f.readlines()
                        # Ищем ошибки в последних 100 строках
                        for line in lines[-100:]:
                            if "ERROR" in line or "❌" in line:
                                results["recent_errors"].append(
                                    {"file": str(log_file.name), "line": line.strip()}
                                )
                except Exception:
                    pass
        else:
            results["errors"].append("Директория logs не найдена")

        results["status"] = "ok"

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Ошибка проверки логов: {e}")
        logger.error(f"❌ Ошибка проверки логов: {e}")

    return results


def check_code_fixes() -> Dict[str, Any]:
    """Проверка исправлений кода"""
    results = {"status": "unknown", "fixes_checked": [], "errors": []}

    try:
        # Проверяем наличие новых функций
        signal_live_path = Path("signal_live.py")
        if signal_live_path.exists():
            content = signal_live_path.read_text(encoding="utf-8")

            # Проверяем set_smart_rsi_btc_alignment
            if "def set_smart_rsi_btc_alignment" in content:
                results["fixes_checked"].append(
                    {"name": "set_smart_rsi_btc_alignment", "status": "found"}
                )
            else:
                results["fixes_checked"].append(
                    {"name": "set_smart_rsi_btc_alignment", "status": "not_found"}
                )

            # Проверяем calculate_tp_prices_for_ml
            if "def calculate_tp_prices_for_ml" in content:
                results["fixes_checked"].append(
                    {"name": "calculate_tp_prices_for_ml", "status": "found"}
                )
            else:
                results["fixes_checked"].append(
                    {"name": "calculate_tp_prices_for_ml", "status": "not_found"}
                )

            # Проверяем отсутствие дублирования smart_rsi
            smart_rsi_blocks = content.count("smart_ctx = df.attrs.get('smart_rsi')")
            if smart_rsi_blocks <= 2:  # Должно быть не больше 2 (определение + использование)
                results["fixes_checked"].append(
                    {"name": "no_duplication_smart_rsi", "status": "ok"}
                )
            else:
                results["fixes_checked"].append(
                    {
                        "name": "no_duplication_smart_rsi",
                        "status": "warning",
                        "message": f"Найдено {smart_rsi_blocks} блоков (возможно дублирование)",
                    }
                )

        results["status"] = "ok"

    except Exception as e:
        results["status"] = "error"
        results["errors"].append(f"Ошибка проверки исправлений: {e}")
        logger.error(f"❌ Ошибка проверки исправлений: {e}")

    return results


def generate_report() -> str:
    """Генерирует отчёт о здоровье системы"""
    logger.info("🔍 Начинаем проверку здоровья системы...")

    db_results = check_database()
    ml_results = check_ml_models()
    metrics_results = check_prometheus_metrics()
    logs_results = check_logs()
    fixes_results = check_code_fixes()

    report = []
    report.append("=" * 60)
    report.append("🔍 ОТЧЁТ О ЗДОРОВЬЕ СИСТЕМЫ")
    report.append("=" * 60)
    report.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # База данных
    report.append("📊 БАЗА ДАННЫХ:")
    report.append(f"   Статус: {db_results['status']}")
    report.append(f"   Всего сигналов: {db_results['signals_count']}")
    report.append(f"   Активных сигналов: {db_results['active_signals_count']}")
    if db_results["recent_signals"]:
        report.append(f"   Последние сигналы (24ч): {len(db_results['recent_signals'])}")
        for signal in db_results["recent_signals"][:3]:
            report.append(f"      - {signal[0]} {signal[1]} @ {signal[2]} ({signal[3]})")
    if db_results["errors"]:
        for error in db_results["errors"]:
            report.append(f"   ⚠️ {error}")
    report.append("")

    # ML модели
    report.append("🤖 ML МОДЕЛИ:")
    report.append(f"   Статус: {ml_results['status']}")
    report.append(f"   Модели доступны: {ml_results.get('models_available', False)}")
    if ml_results.get("models_count"):
        report.append(f"   Количество моделей: {ml_results['models_count']}")
    if ml_results.get("predictor_trained"):
        report.append(f"   Predictor обучен: {ml_results['predictor_trained']}")
    if ml_results["errors"]:
        for error in ml_results["errors"]:
            report.append(f"   ⚠️ {error}")
    report.append("")

    # Метрики
    report.append("📈 МЕТРИКИ PROMETHEUS:")
    report.append(f"   Статус: {metrics_results['status']}")
    report.append(f"   Метрики доступны: {metrics_results.get('metrics_available', False)}")
    if metrics_results.get("metrics_endpoint"):
        report.append(f"   Endpoint: {metrics_results['metrics_endpoint']}")
    if metrics_results["errors"]:
        for error in metrics_results["errors"]:
            report.append(f"   ⚠️ {error}")
    report.append("")

    # Логи
    report.append("📝 ЛОГИ:")
    report.append(f"   Статус: {logs_results['status']}")
    report.append(f"   Файлов логов: {len(logs_results['log_files'])}")
    if logs_results["recent_errors"]:
        report.append(f"   Последние ошибки: {len(logs_results['recent_errors'])}")
        for error in logs_results["recent_errors"][:3]:
            report.append(f"      - {error['file']}: {error['line'][:80]}")
    report.append("")

    # Исправления
    report.append("🔧 ИСПРАВЛЕНИЯ КОДА:")
    report.append(f"   Статус: {fixes_results['status']}")
    for fix in fixes_results["fixes_checked"]:
        status_icon = "✅" if fix["status"] in ["found", "ok"] else "⚠️"
        report.append(f"   {status_icon} {fix['name']}: {fix['status']}")
        if "message" in fix:
            report.append(f"      {fix['message']}")
    report.append("")

    report.append("=" * 60)

    return "\n".join(report)


if __name__ == "__main__":
    try:
        report = generate_report()
        print(report)

        # Сохраняем отчёт
        report_path = Path("scripts/PROD_HEALTH_CHECK_REPORT.txt")
        report_path.write_text(report, encoding="utf-8")
        logger.info(f"✅ Отчёт сохранён: {report_path}")

    except Exception as e:
        logger.error(f"❌ Ошибка генерации отчёта: {e}")
        sys.exit(1)
