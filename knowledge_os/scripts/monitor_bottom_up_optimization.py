#!/usr/bin/env python3
"""
Мониторинг прогресса Data-Driven Bottom-Up оптимизации
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PORTFOLIO_SYMBOLS = [
    "BONKUSDT",
    "WIFUSDT",
    "NEIROUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "POLUSDT",
    "LINKUSDT",
    "PENGUUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "CRVUSDT",
    "OPUSDT",
]

PARAMETER_VARIANTS_COUNT = 12
TOTAL_TESTS = len(PORTFOLIO_SYMBOLS) * PARAMETER_VARIANTS_COUNT


def check_log_progress() -> Dict[str, Any]:
    """Проверяет прогресс по лог-файлу"""
    log_file = Path("/tmp/bottom_up_optimization.log")

    if not log_file.exists():
        return {"status": "not_started", "message": "Лог-файл не найден"}

    try:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()

        completed_tests = 0
        current_symbol = None
        current_variant = None

        for line in lines:
            if "[Тестируем:" in line:
                completed_tests += 1
            if "Оптимизируем" in line:
                for symbol in PORTFOLIO_SYMBOLS:
                    if symbol in line:
                        current_symbol = symbol
                        break
            if "Тестируем:" in line:
                parts = line.split("Тестируем:")
                if len(parts) > 1:
                    current_variant = parts[1].strip()

        progress_pct = (completed_tests / TOTAL_TESTS) * 100 if TOTAL_TESTS > 0 else 0

        return {
            "status": "running",
            "completed_tests": completed_tests,
            "total_tests": TOTAL_TESTS,
            "progress_pct": progress_pct,
            "current_symbol": current_symbol,
            "current_variant": current_variant,
            "remaining_tests": TOTAL_TESTS - completed_tests,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_results_file() -> Dict[str, Any]:
    """Проверяет наличие файла результатов"""
    report_dir = PROJECT_ROOT / "data" / "reports"
    result_files = sorted(report_dir.glob("bottom_up_optimization_*.json"), reverse=True)

    if not result_files:
        return {"status": "not_found"}

    try:
        with open(result_files[0], encoding="utf-8") as f:
            data = json.load(f)

        best_params = data.get("best_params_by_symbol", {})
        profitable_count = sum(1 for v in best_params.values() if v.get("total_pnl", 0) > 0)
        total_pnl = sum(v.get("total_pnl", 0) for v in best_params.values())

        return {
            "status": "completed",
            "file": str(result_files[0]),
            "optimization_date": data.get("optimization_date", "N/A"),
            "profitable_count": profitable_count,
            "total_pnl": total_pnl,
            "best_params": best_params,
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    """Главная функция мониторинга"""
    print("=" * 80)
    print("📊 МОНИТОРИНГ DATA-DRIVEN BOTTOM-UP ОПТИМИЗАЦИИ")
    print("=" * 80)
    print()

    # Проверяем файл результатов
    results = check_results_file()
    if results.get("status") == "completed":
        print("✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
        print(f"📁 Файл: {results['file']}")
        print(f"📅 Дата: {results['optimization_date']}")
        print(f"💰 Прибыльных монет: {results['profitable_count']}/{len(PORTFOLIO_SYMBOLS)}")
        print(f"📈 Общий PnL: {results['total_pnl']:.2f} USDT")
        print()
        print("Топ-5 лучших монет:")
        best_params = results.get("best_params", {})
        sorted_symbols = sorted(
            best_params.items(), key=lambda x: x[1].get("total_pnl", 0), reverse=True
        )[:5]

        for symbol, data in sorted_symbols:
            pnl = data.get("total_pnl", 0)
            trades = data.get("total_trades", 0)
            variant = data.get("variant", "N/A")
            print(f"  {symbol}: {pnl:8.2f} USDT | {trades:3d} сделок | {variant}")

        return

    # Проверяем прогресс по логу
    progress = check_log_progress()

    if progress.get("status") == "running":
        print("⏳ ОПТИМИЗАЦИЯ В ПРОЦЕССЕ")
        print(
            f"📊 Прогресс: {progress['completed_tests']}/{progress['total_tests']} тестов ({progress['progress_pct']:.1f}%)"
        )
        print(f"⏱️  Осталось: ~{progress['remaining_tests']} тестов")

        if progress.get("current_symbol"):
            print(f"🔍 Текущая монета: {progress['current_symbol']}")
        if progress.get("current_variant"):
            print(f"📋 Текущий вариант: {progress['current_variant']}")

        # Оценка времени
        if progress["completed_tests"] > 0:
            # Примерная оценка: ~1 минута на тест
            estimated_minutes = (progress["remaining_tests"] * 1) / 60
            print(f"⏰ Примерное время до завершения: ~{estimated_minutes:.1f} часов")

    elif progress.get("status") == "not_started":
        print("⏳ Ожидание запуска оптимизации...")
        print("💡 Проверьте, что скрипт auto_optimize_all_portfolio_coins.py запущен")

    else:
        print(f"⚠️ Статус: {progress.get('status', 'unknown')}")
        if progress.get("message"):
            print(f"   {progress['message']}")

    print()
    print("=" * 80)
    print("💡 Для просмотра логов: tail -f /tmp/bottom_up_optimization.log")
    print("=" * 80)


if __name__ == "__main__":
    main()
