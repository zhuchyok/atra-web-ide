#!/usr/bin/env python3
"""
🔬 СКРИПТ ПОСЛЕДОВАТЕЛЬНОГО ТЕСТИРОВАНИЯ ФИЛЬТРОВ
Включает фильтры по одному, делает месячный тест и анализирует результаты
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импорты из основного скрипта
from scripts.backtest_5coins_intelligent import (
    RISK_PER_TRADE,
    START_BALANCE,
    TEST_SYMBOLS,
    get_intelligent_filter_system,
    load_yearly_data,
    run_backtest,
)

# ============================================================================
# СПИСОК ФИЛЬТРОВ ДЛЯ ТЕСТИРОВАНИЯ
# ============================================================================

# Список фильтров для последовательного добавления
FILTERS_TO_ADD = [
    {"name": "volume_profile", "description": "Volume Profile фильтр", "flag": "USE_VP_FILTER"},
    {"name": "vwap", "description": "VWAP фильтр", "flag": "USE_VWAP_FILTER"},
    {"name": "order_flow", "description": "Order Flow фильтр", "flag": "USE_ORDER_FLOW_FILTER"},
    {
        "name": "microstructure",
        "description": "Microstructure фильтр",
        "flag": "USE_MICROSTRUCTURE_FILTER",
    },
    {"name": "momentum", "description": "Momentum фильтр", "flag": "USE_MOMENTUM_FILTER"},
    {
        "name": "trend_strength",
        "description": "Trend Strength фильтр",
        "flag": "USE_TREND_STRENGTH_FILTER",
    },
    {"name": "amt", "description": "AMT фильтр", "flag": "USE_AMT_FILTER"},
    {
        "name": "market_profile",
        "description": "Market Profile (TPO) фильтр",
        "flag": "USE_MARKET_PROFILE_FILTER",
    },
]

# ============================================================================
# ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ФИЛЬТРАМИ
# ============================================================================


def set_filter_flags(enabled_filters: list):
    """Устанавливает флаги фильтров через переменные окружения
    enabled_filters - список имен фильтров, которые нужно включить
    """
    # Сбрасываем все флаги
    all_flags = [
        "USE_VP_FILTER",
        "USE_VWAP_FILTER",
        "USE_ORDER_FLOW_FILTER",
        "USE_MICROSTRUCTURE_FILTER",
        "USE_MOMENTUM_FILTER",
        "USE_TREND_STRENGTH_FILTER",
        "USE_AMT_FILTER",
        "USE_MARKET_PROFILE_FILTER",
    ]

    for flag_name in all_flags:
        os.environ[flag_name] = "False"

    # Устанавливаем включенные фильтры
    filter_flag_map = {f["name"]: f["flag"] for f in FILTERS_TO_ADD}
    for filter_name in enabled_filters:
        if filter_name in filter_flag_map:
            os.environ[filter_flag_map[filter_name]] = "True"

    # Включаем/отключаем дополнительные фильтры
    if enabled_filters:
        os.environ["DISABLE_EXTRA_FILTERS"] = "false"  # Включаем фильтры
    else:
        os.environ["DISABLE_EXTRA_FILTERS"] = "true"  # Отключаем фильтры

    # Перезагружаем модуль signals.core для применения изменений
    if "src.signals.core" in sys.modules:
        del sys.modules["src.signals.core"]
    if "src.signals" in sys.modules:
        del sys.modules["src.signals"]

    # Также перезагружаем config для применения флагов
    if "config" in sys.modules:
        del sys.modules["config"]


# ============================================================================
# ФУНКЦИИ АНАЛИЗА РЕЗУЛЬТАТОВ
# ============================================================================


def analyze_results(results: list, filter_name: str) -> dict:
    """Анализирует результаты бэктеста"""
    total_trades = sum(r.get("total_trades", 0) for r in results)
    total_return = sum(r.get("total_return", 0) for r in results)
    total_signals = sum(r.get("signals_generated", 0) for r in results)
    total_executed = sum(r.get("signals_executed", 0) for r in results)

    avg_win_rate = sum(r.get("win_rate", 0) for r in results) / len(results) if results else 0
    avg_profit_factor = (
        sum(r.get("profit_factor", 0) for r in results) / len(results) if results else 0
    )
    avg_sharpe = sum(r.get("sharpe_ratio", 0) for r in results) / len(results) if results else 0
    avg_max_drawdown = (
        sum(r.get("max_drawdown", 0) for r in results) / len(results) if results else 0
    )

    rejection_rate = (
        (total_signals - total_executed) / total_signals * 100 if total_signals > 0 else 0
    )
    return {
        "filter_name": filter_name,
        "total_trades": total_trades,
        "total_return": total_return,
        "total_signals": total_signals,
        "total_executed": total_executed,
        "rejection_rate": rejection_rate,
        "avg_win_rate": avg_win_rate,
        "avg_profit_factor": avg_profit_factor,
        "avg_sharpe": avg_sharpe,
        "avg_max_drawdown": avg_max_drawdown,
        "results": results,
    }


def compare_with_baseline(baseline: dict, current: dict) -> dict:
    """Сравнивает текущие результаты с базовыми"""
    return_diff = current["total_return"] - baseline["total_return"]
    return_diff_pct = (
        (return_diff / abs(baseline["total_return"]) * 100) if baseline["total_return"] != 0 else 0
    )
    return {
        "return_diff": return_diff,
        "return_diff_pct": return_diff_pct,
        "trades_diff": current["total_trades"] - baseline["total_trades"],
        "signals_diff": current["total_signals"] - baseline["total_signals"],
        "rejection_rate_diff": (current["rejection_rate"] - baseline["rejection_rate"]),
        "win_rate_diff": current["avg_win_rate"] - baseline["avg_win_rate"],
        "profit_factor_diff": (current["avg_profit_factor"] - baseline["avg_profit_factor"]),
        "sharpe_diff": current["avg_sharpe"] - baseline["avg_sharpe"],
    }


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================================


def main():
    """Главная функция тестирования фильтров"""
    print("=" * 80)
    print("🔬 ПОСЛЕДОВАТЕЛЬНОЕ ТЕСТИРОВАНИЕ ФИЛЬТРОВ")
    print("=" * 80)
    print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Символы: {', '.join(TEST_SYMBOLS)}")
    print("📅 Период: 30 дней (месячные данные)")
    print(f"💰 Начальный баланс: ${START_BALANCE:.2f}")
    print(f"📊 Размер позиции: {RISK_PER_TRADE * 100:.0f}%")
    print("=" * 80)
    print("")

    period_days = 30
    all_results = []
    baseline_result = None
    enabled_filters_list = []  # Список включенных фильтров (накапливаем)

    try:
        # Сначала baseline (без фильтров)
        print("\n" + "=" * 80)
        test_count = len(FILTERS_TO_ADD) + 1
        print(f"🔍 Тест 0/{test_count}: Baseline (без дополнительных фильтров)")
        print("=" * 80)

        set_filter_flags([])  # Никаких фильтров

        intelligent_system = get_intelligent_filter_system()
        filter_results = []

        for symbol in TEST_SYMBOLS:
            print(f"\n📈 Тестирование {symbol}...")
            df = load_yearly_data(symbol, limit_days=period_days)
            if df is None or len(df) < 50:
                print(f"❌ Недостаточно данных для {symbol}")
                continue

            stats = run_backtest(
                df, symbol=symbol, mode="soft", intelligent_system=intelligent_system
            )
            metrics = stats.get_metrics()
            metrics["symbol"] = symbol
            metrics["period_days"] = period_days
            metrics["filter_name"] = "baseline"
            metrics["enabled_filters"] = []
            filter_results.append(metrics)

        analysis = analyze_results(filter_results, "baseline")
        analysis["enabled_filters"] = []
        all_results.append(analysis)
        baseline_result = analysis

        print("\n📊 Результаты для Baseline:")
        print(f"   📈 Доходность: {analysis['total_return']:+.2f}%")
        print(f"   📊 Сделок: {analysis['total_trades']}")
        signals_info = f"исполнено: {analysis['total_executed']}"
        print(f"   🎯 Сигналов: {analysis['total_signals']} ({signals_info})")

        # Теперь добавляем фильтры по одному
        for idx, filter_config in enumerate(FILTERS_TO_ADD, 1):
            filter_name = filter_config["name"]
            filter_desc = filter_config["description"]

            # Добавляем фильтр в список включенных
            enabled_filters_list.append(filter_name)

            print("\n" + "=" * 80)
            print(f"🔍 Тест {idx}/{len(FILTERS_TO_ADD)}: Добавляем {filter_desc}")
            filters_str = ", ".join(enabled_filters_list)
            print(f"📋 Включенные фильтры: {filters_str}")
            print("=" * 80)

            # Устанавливаем флаги фильтров (все включенные до этого момента)
            set_filter_flags(enabled_filters_list)

            intelligent_system = get_intelligent_filter_system()
            filter_results = []

            for symbol in TEST_SYMBOLS:
                print(f"\n📈 Тестирование {symbol}...")
                df = load_yearly_data(symbol, limit_days=period_days)
                if df is None or len(df) < 50:
                    print(f"❌ Недостаточно данных для {symbol}")
                    continue

                stats = run_backtest(
                    df, symbol=symbol, mode="soft", intelligent_system=intelligent_system
                )
                metrics = stats.get_metrics()
                metrics["symbol"] = symbol
                metrics["period_days"] = period_days
                filter_name_full = f"baseline+{'+'.join(enabled_filters_list)}"
                metrics["filter_name"] = filter_name_full
                metrics["enabled_filters"] = enabled_filters_list.copy()
                filter_results.append(metrics)

            # Анализируем результаты
            test_name = f"baseline+{'+'.join(enabled_filters_list)}"
            analysis = analyze_results(filter_results, test_name)
            analysis["enabled_filters"] = enabled_filters_list.copy()
            all_results.append(analysis)

            # Выводим результаты
            print(f"\n📊 Результаты с фильтрами: {filters_str}")
            print(f"   📈 Доходность: {analysis['total_return']:+.2f}%")
            print(f"   📊 Сделок: {analysis['total_trades']}")
            executed_str = f"исполнено: {analysis['total_executed']}"
            print(f"   🎯 Сигналов: {analysis['total_signals']} ({executed_str})")
            print(f"   ❌ Отклонено: {analysis['rejection_rate']:.1f}%")
            print(f"   ✅ Win Rate: {analysis['avg_win_rate']:.1f}%")
            print(f"   💵 Profit Factor: {analysis['avg_profit_factor']:.2f}")
            print(f"   📊 Sharpe: {analysis['avg_sharpe']:.2f}")

            # Сравнение с предыдущим результатом
            if len(all_results) > 1:
                prev_result = all_results[-2]  # Предыдущий результат
                comparison = compare_with_baseline(prev_result, analysis)
                prev_name = prev_result["filter_name"]
                print(f"\n   📊 Сравнение с предыдущим ({prev_name}):")
                return_diff_str = f"{comparison['return_diff']:+.2f}%"
                return_pct_str = f"({comparison['return_diff_pct']:+.1f}%)"
                print(f"      Доходность: {return_diff_str} {return_pct_str}")
                print(f"      Сделок: {comparison['trades_diff']:+d}")
                print(f"      Win Rate: {comparison['win_rate_diff']:+.1f}%")
                pf_diff = comparison["profit_factor_diff"]
                print(f"      Profit Factor: {pf_diff:+.2f}")
                print(f"      Sharpe: {comparison['sharpe_diff']:+.2f}")

            # Сравнение с baseline
            if baseline_result:
                comparison = compare_with_baseline(baseline_result, analysis)
                print("\n   📊 Сравнение с baseline:")
                return_diff_str = f"{comparison['return_diff']:+.2f}%"
                return_pct_str = f"({comparison['return_diff_pct']:+.1f}%)"
                print(f"      Доходность: {return_diff_str} {return_pct_str}")
                print(f"      Сделок: {comparison['trades_diff']:+d}")

            # Сохраняем промежуточные результаты
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filter_suffix = "+".join(enabled_filters_list)
            output_file = f"backtests/filter_test_{filter_suffix}_{timestamp}.json"
            os.makedirs("backtests", exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Результаты сохранены в {output_file}")

            # Если фильтр ухудшает результаты, логируем, но продолжаем
            baseline_return = baseline_result["total_return"]
            threshold = baseline_return * 0.5
            if baseline_result and analysis["total_return"] < threshold:
                print(f"\n⚠️  ВНИМАНИЕ: Фильтр {filter_name} значительно ухудшает результаты!")
                current_return = analysis["total_return"]
                baseline_str = f"vs baseline {baseline_return:+.2f}%"
                print(f"   Доходность: {current_return:+.2f}% {baseline_str}")
                print("   Продолжаем тестирование для сбора статистики...")

    finally:
        # Восстанавливаем исходное состояние
        set_filter_flags([])

    # Финальный отчет
    print("\n" + "=" * 80)
    print("📊 ФИНАЛЬНЫЙ ОТЧЕТ")
    print("=" * 80)
    print()

    # Сортируем по доходности
    sorted_results = sorted(all_results, key=lambda x: x["total_return"], reverse=True)

    print("🏆 ТОП-3 ФИЛЬТРА ПО ДОХОДНОСТИ:")
    for i, result in enumerate(sorted_results[:3], 1):
        print(f"\n{i}. {result['filter_name']}: {result['total_return']:+.2f}%")
        if baseline_result and result["filter_name"] != "baseline":
            comparison = compare_with_baseline(baseline_result, result)
            return_diff_str = f"{comparison['return_diff']:+.2f}%"
            return_pct_str = f"({comparison['return_diff_pct']:+.1f}%)"
            print(f"   vs baseline: {return_diff_str} {return_pct_str}")

    # Сохраняем сводный отчет
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_file = f"backtests/filter_test_summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "baseline": baseline_result,
                "all_results": all_results,
                "sorted_by_return": sorted_results,
                "timestamp": timestamp,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\n✅ Сводный отчет сохранен в {summary_file}")
    print("\n🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")


if __name__ == "__main__":
    main()
