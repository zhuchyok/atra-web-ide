#!/usr/bin/env python3
"""
Анализ результатов бэктеста институциональных индикаторов

Анализирует JSON файлы с результатами бэктеста и создает подробный отчет.
"""

import glob
import json
import os
import sys
from datetime import datetime
from typing import Dict, List

import pandas as pd

# ============================================================================
# ФУНКЦИИ АНАЛИЗА
# ============================================================================


def load_backtest_results(results_file: str) -> List[Dict]:
    """Загружает результаты бэктеста из JSON"""
    try:
        with open(results_file) as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка загрузки {results_file}: {e}")
        return []


def analyze_results(results: List[Dict]) -> Dict:
    """Анализирует результаты бэктеста"""

    # Разделяем на baseline и с фильтрами
    baseline_results = [r for r in results if "Baseline" in r.get("name", "")]
    filtered_results = [r for r in results if "новыми фильтрами" in r.get("name", "")]

    analysis = {"baseline": {}, "filtered": {}, "improvements": {}, "symbols": []}

    # Группируем по символам
    symbols = set()
    for r in results:
        if "symbol" in r:
            symbols.add(r["symbol"])

    for symbol in symbols:
        symbol_baseline = [r for r in baseline_results if r.get("symbol") == symbol]
        symbol_filtered = [r for r in filtered_results if r.get("symbol") == symbol]

        if symbol_baseline and symbol_filtered:
            baseline = symbol_baseline[0]
            filtered = symbol_filtered[0]

            # Рассчитываем улучшения
            improvements = {
                "balance_change": filtered["final_balance"] - baseline["final_balance"],
                "balance_change_pct": (
                    (filtered["final_balance"] - baseline["final_balance"])
                    / baseline["final_balance"]
                    * 100
                )
                if baseline["final_balance"] > 0
                else 0,
                "trades_change": filtered["total_trades"] - baseline["total_trades"],
                "win_rate_change": filtered["win_rate"] - baseline["win_rate"],
                "profit_factor_change": filtered["profit_factor"] - baseline["profit_factor"],
                "drawdown_change": filtered["max_drawdown_pct"] - baseline["max_drawdown_pct"],
                "sharpe_change": filtered["sharpe_ratio"] - baseline["sharpe_ratio"],
            }

            analysis["symbols"].append(
                {
                    "symbol": symbol,
                    "baseline": baseline,
                    "filtered": filtered,
                    "improvements": improvements,
                }
            )

    # Агрегированная статистика
    if baseline_results and filtered_results:
        baseline_avg = {
            "total_trades": sum(r["total_trades"] for r in baseline_results)
            / len(baseline_results),
            "win_rate": sum(r["win_rate"] for r in baseline_results) / len(baseline_results),
            "profit_factor": sum(r["profit_factor"] for r in baseline_results)
            / len(baseline_results),
            "total_return": sum(r["total_return"] for r in baseline_results)
            / len(baseline_results),
            "max_drawdown_pct": sum(r["max_drawdown_pct"] for r in baseline_results)
            / len(baseline_results),
            "sharpe_ratio": sum(r["sharpe_ratio"] for r in baseline_results)
            / len(baseline_results),
        }

        filtered_avg = {
            "total_trades": sum(r["total_trades"] for r in filtered_results)
            / len(filtered_results),
            "win_rate": sum(r["win_rate"] for r in filtered_results) / len(filtered_results),
            "profit_factor": sum(r["profit_factor"] for r in filtered_results)
            / len(filtered_results),
            "total_return": sum(r["total_return"] for r in filtered_results)
            / len(filtered_results),
            "max_drawdown_pct": sum(r["max_drawdown_pct"] for r in filtered_results)
            / len(filtered_results),
            "sharpe_ratio": sum(r["sharpe_ratio"] for r in filtered_results)
            / len(filtered_results),
        }

        analysis["baseline"] = baseline_avg
        analysis["filtered"] = filtered_avg
        analysis["improvements"] = {
            "win_rate": filtered_avg["win_rate"] - baseline_avg["win_rate"],
            "profit_factor": filtered_avg["profit_factor"] - baseline_avg["profit_factor"],
            "total_return": filtered_avg["total_return"] - baseline_avg["total_return"],
            "drawdown": filtered_avg["max_drawdown_pct"] - baseline_avg["max_drawdown_pct"],
            "sharpe": filtered_avg["sharpe_ratio"] - baseline_avg["sharpe_ratio"],
            "trades": filtered_avg["total_trades"] - baseline_avg["total_trades"],
        }

    return analysis


def print_analysis_report(analysis: Dict):
    """Выводит отчет анализа"""
    print("\n" + "=" * 80)
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ БЭКТЕСТА ИНСТИТУЦИОНАЛЬНЫХ ИНДИКАТОРОВ")
    print("=" * 80)

    if not analysis["symbols"]:
        print("⚠️ Нет данных для анализа")
        return

    # Агрегированная статистика
    if analysis["baseline"] and analysis["filtered"]:
        print("\n" + "=" * 80)
        print("📈 АГРЕГИРОВАННАЯ СТАТИСТИКА")
        print("=" * 80)

        print("\n🔵 BASELINE (без новых фильтров):")
        print(f"   Средний Win Rate: {analysis['baseline']['win_rate']:.2f}%")
        print(f"   Средний Profit Factor: {analysis['baseline']['profit_factor']:.2f}")
        print(f"   Средняя доходность: {analysis['baseline']['total_return']:.2f}%")
        print(f"   Средняя просадка: {analysis['baseline']['max_drawdown_pct']:.2f}%")
        print(f"   Средний Sharpe Ratio: {analysis['baseline']['sharpe_ratio']:.2f}")
        print(f"   Среднее количество сделок: {analysis['baseline']['total_trades']:.1f}")

        print("\n🟢 С НОВЫМИ ФИЛЬТРАМИ:")
        print(f"   Средний Win Rate: {analysis['filtered']['win_rate']:.2f}%")
        print(f"   Средний Profit Factor: {analysis['filtered']['profit_factor']:.2f}")
        print(f"   Средняя доходность: {analysis['filtered']['total_return']:.2f}%")
        print(f"   Средняя просадка: {analysis['filtered']['max_drawdown_pct']:.2f}%")
        print(f"   Средний Sharpe Ratio: {analysis['filtered']['sharpe_ratio']:.2f}")
        print(f"   Среднее количество сделок: {analysis['filtered']['total_trades']:.1f}")

        print("\n📊 УЛУЧШЕНИЯ:")
        improvements = analysis["improvements"]
        print(f"   Win Rate: {improvements['win_rate']:+.2f}%")
        print(f"   Profit Factor: {improvements['profit_factor']:+.2f}")
        print(f"   Доходность: {improvements['total_return']:+.2f}%")
        print(f"   Просадка: {improvements['drawdown']:+.2f}% (меньше = лучше)")
        print(f"   Sharpe Ratio: {improvements['sharpe']:+.2f}")
        print(f"   Количество сделок: {improvements['trades']:+.1f}")

    # Детальная статистика по символам
    print("\n" + "=" * 80)
    print("📊 ДЕТАЛЬНАЯ СТАТИСТИКА ПО СИМВОЛАМ")
    print("=" * 80)

    for symbol_data in analysis["symbols"]:
        symbol = symbol_data["symbol"]
        baseline = symbol_data["baseline"]
        filtered = symbol_data["filtered"]
        improvements = symbol_data["improvements"]

        print(f"\n{'=' * 80}")
        print(f"📈 {symbol}")
        print(f"{'=' * 80}")

        print("\n🔵 Baseline:")
        print(f"   Баланс: ${baseline['final_balance']:.2f}")
        print(f"   Доходность: {baseline['total_return']:.2f}%")
        print(f"   Сделок: {baseline['total_trades']}")
        print(f"   Win Rate: {baseline['win_rate']:.2f}%")
        print(f"   Profit Factor: {baseline['profit_factor']:.2f}")
        print(f"   Просадка: {baseline['max_drawdown_pct']:.2f}%")
        print(f"   Sharpe: {baseline['sharpe_ratio']:.2f}")

        print("\n🟢 С фильтрами:")
        print(f"   Баланс: ${filtered['final_balance']:.2f}")
        print(f"   Доходность: {filtered['total_return']:.2f}%")
        print(f"   Сделок: {filtered['total_trades']}")
        print(f"   Win Rate: {filtered['win_rate']:.2f}%")
        print(f"   Profit Factor: {filtered['profit_factor']:.2f}")
        print(f"   Просадка: {filtered['max_drawdown_pct']:.2f}%")
        print(f"   Sharpe: {filtered['sharpe_ratio']:.2f}")

        print("\n📊 Улучшения:")
        print(
            f"   Баланс: ${improvements['balance_change']:+.2f} ({improvements['balance_change_pct']:+.2f}%)"
        )
        print(f"   Сделок: {improvements['trades_change']:+d}")
        print(f"   Win Rate: {improvements['win_rate_change']:+.2f}%")
        print(f"   Profit Factor: {improvements['profit_factor_change']:+.2f}")
        print(f"   Просадка: {improvements['drawdown_change']:+.2f}%")
        print(f"   Sharpe: {improvements['sharpe_change']:+.2f}")


def create_markdown_report(analysis: Dict, output_file: str):
    """Создает Markdown отчет"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# 📊 ОТЧЕТ: АНАЛИЗ БЭКТЕСТА ИНСТИТУЦИОНАЛЬНЫХ ИНДИКАТОРОВ\n\n")
        f.write(f"**Дата анализа:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")

        if analysis["baseline"] and analysis["filtered"]:
            f.write("## 📈 АГРЕГИРОВАННАЯ СТАТИСТИКА\n\n")

            f.write("### 🔵 Baseline (без новых фильтров)\n\n")
            f.write(f"- **Средний Win Rate:** {analysis['baseline']['win_rate']:.2f}%\n")
            f.write(f"- **Средний Profit Factor:** {analysis['baseline']['profit_factor']:.2f}\n")
            f.write(f"- **Средняя доходность:** {analysis['baseline']['total_return']:.2f}%\n")
            f.write(f"- **Средняя просадка:** {analysis['baseline']['max_drawdown_pct']:.2f}%\n")
            f.write(f"- **Средний Sharpe Ratio:** {analysis['baseline']['sharpe_ratio']:.2f}\n")
            f.write(
                f"- **Среднее количество сделок:** {analysis['baseline']['total_trades']:.1f}\n\n"
            )

            f.write("### 🟢 С новыми фильтрами\n\n")
            f.write(f"- **Средний Win Rate:** {analysis['filtered']['win_rate']:.2f}%\n")
            f.write(f"- **Средний Profit Factor:** {analysis['filtered']['profit_factor']:.2f}\n")
            f.write(f"- **Средняя доходность:** {analysis['filtered']['total_return']:.2f}%\n")
            f.write(f"- **Средняя просадка:** {analysis['filtered']['max_drawdown_pct']:.2f}%\n")
            f.write(f"- **Средний Sharpe Ratio:** {analysis['filtered']['sharpe_ratio']:.2f}\n")
            f.write(
                f"- **Среднее количество сделок:** {analysis['filtered']['total_trades']:.1f}\n\n"
            )

            f.write("### 📊 Улучшения\n\n")
            improvements = analysis["improvements"]
            f.write(f"- **Win Rate:** {improvements['win_rate']:+.2f}%\n")
            f.write(f"- **Profit Factor:** {improvements['profit_factor']:+.2f}\n")
            f.write(f"- **Доходность:** {improvements['total_return']:+.2f}%\n")
            f.write(f"- **Просадка:** {improvements['drawdown']:+.2f}% (меньше = лучше)\n")
            f.write(f"- **Sharpe Ratio:** {improvements['sharpe']:+.2f}\n")
            f.write(f"- **Количество сделок:** {improvements['trades']:+.1f}\n\n")

        f.write("---\n\n")
        f.write("## 📊 ДЕТАЛЬНАЯ СТАТИСТИКА ПО СИМВОЛАМ\n\n")

        for symbol_data in analysis["symbols"]:
            symbol = symbol_data["symbol"]
            baseline = symbol_data["baseline"]
            filtered = symbol_data["filtered"]
            improvements = symbol_data["improvements"]

            f.write(f"### 📈 {symbol}\n\n")

            f.write("#### 🔵 Baseline\n\n")
            f.write(f"- Баланс: ${baseline['final_balance']:.2f}\n")
            f.write(f"- Доходность: {baseline['total_return']:.2f}%\n")
            f.write(f"- Сделок: {baseline['total_trades']}\n")
            f.write(f"- Win Rate: {baseline['win_rate']:.2f}%\n")
            f.write(f"- Profit Factor: {baseline['profit_factor']:.2f}\n")
            f.write(f"- Просадка: {baseline['max_drawdown_pct']:.2f}%\n")
            f.write(f"- Sharpe: {baseline['sharpe_ratio']:.2f}\n\n")

            f.write("#### 🟢 С фильтрами\n\n")
            f.write(f"- Баланс: ${filtered['final_balance']:.2f}\n")
            f.write(f"- Доходность: {filtered['total_return']:.2f}%\n")
            f.write(f"- Сделок: {filtered['total_trades']}\n")
            f.write(f"- Win Rate: {filtered['win_rate']:.2f}%\n")
            f.write(f"- Profit Factor: {filtered['profit_factor']:.2f}\n")
            f.write(f"- Просадка: {filtered['max_drawdown_pct']:.2f}%\n")
            f.write(f"- Sharpe: {filtered['sharpe_ratio']:.2f}\n\n")

            f.write("#### 📊 Улучшения\n\n")
            f.write(
                f"- Баланс: ${improvements['balance_change']:+.2f} ({improvements['balance_change_pct']:+.2f}%)\n"
            )
            f.write(f"- Сделок: {improvements['trades_change']:+d}\n")
            f.write(f"- Win Rate: {improvements['win_rate_change']:+.2f}%\n")
            f.write(f"- Profit Factor: {improvements['profit_factor_change']:+.2f}\n")
            f.write(f"- Просадка: {improvements['drawdown_change']:+.2f}%\n")
            f.write(f"- Sharpe: {improvements['sharpe_change']:+.2f}\n\n")

            f.write("---\n\n")

        f.write("## ✅ ВЫВОДЫ\n\n")
        if analysis["improvements"]:
            improvements = analysis["improvements"]
            f.write("### Положительные изменения:\n\n")
            if improvements["win_rate"] > 0:
                f.write(f"- ✅ Win Rate увеличился на {improvements['win_rate']:.2f}%\n")
            if improvements["profit_factor"] > 0:
                f.write(f"- ✅ Profit Factor увеличился на {improvements['profit_factor']:.2f}\n")
            if improvements["total_return"] > 0:
                f.write(f"- ✅ Доходность увеличилась на {improvements['total_return']:.2f}%\n")
            if improvements["drawdown"] < 0:
                f.write(f"- ✅ Просадка уменьшилась на {abs(improvements['drawdown']):.2f}%\n")
            if improvements["sharpe"] > 0:
                f.write(f"- ✅ Sharpe Ratio увеличился на {improvements['sharpe']:.2f}\n")

            f.write("\n### Рекомендации:\n\n")
            f.write("1. Проанализировать влияние каждого фильтра отдельно\n")
            f.write("2. Оптимизировать параметры фильтров\n")
            f.write("3. Провести walk-forward анализ\n")
            f.write("4. Тестировать на разных рынках\n")


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция"""
    print("📊 АНАЛИЗ РЕЗУЛЬТАТОВ БЭКТЕСТА")
    print("=" * 80)

    # Ищем последний файл результатов
    results_files = glob.glob("backtests/institutional_indicators_backtest_*.json")

    if not results_files:
        print("❌ Файлы результатов не найдены")
        print("💡 Запустите сначала: python3 scripts/backtest_institutional_indicators.py")
        return

    # Берем последний файл
    latest_file = max(results_files, key=os.path.getctime)
    print(f"📁 Анализируем: {latest_file}")

    # Загружаем результаты
    results = load_backtest_results(latest_file)
    if not results:
        print("❌ Не удалось загрузить результаты")
        return

    print(f"✅ Загружено {len(results)} результатов")

    # Анализируем
    analysis = analyze_results(results)

    # Выводим отчет
    print_analysis_report(analysis)

    # Создаем Markdown отчет
    report_file = latest_file.replace(".json", "_analysis.md")
    create_markdown_report(analysis, report_file)
    print(f"\n✅ Markdown отчет сохранен: {report_file}")


if __name__ == "__main__":
    main()
