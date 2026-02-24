#!/usr/bin/env python3
"""
🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ INTELLIGENT FILTER SYSTEM ДЛЯ НОВЫХ 50 МОНЕТ (топ 51-100)
Оптимизирует volume_ratio и quality_score для каждой монеты отдельно
Использует исправленную формулу Sharpe Ratio
"""

import glob
import itertools
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, Optional

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 🔧 ВКЛЮЧАЕМ RUST УСКОРЕНИЕ
os.environ["USE_RUST"] = "true"
try:
    from src.infrastructure.performance.rust_accelerator import (
        get_rust_accelerator,
        is_rust_available,
    )

    if is_rust_available():
        print("✅ Rust acceleration доступен")
        rust_accelerator = get_rust_accelerator()
    else:
        print("⚠️ Rust acceleration недоступен, используем Python")
        rust_accelerator = None
except ImportError:
    print("⚠️ Rust модуль не найден, используем Python")
    rust_accelerator = None

from scripts.backtest_5coins_intelligent import (
    get_intelligent_filter_system,
    load_yearly_data,
    run_backtest,
)

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

PERIOD_DAYS = 30  # Месячные данные для оптимизации
# 🔧 НОВЫЕ 59 МОНЕТ (топ 101-159) ДЛЯ ОПТИМИЗАЦИИ
# Первая партия: 25 монет (топ 101-125) - ✅ ЗАВЕРШЕНА
# Вторая партия: 25 монет (топ 126-150) - 🔄 В ПРОЦЕССЕ
ALL_NEW_59_COINS_WITH_DATA = [
    "WIFUSDT",
    "BONKUSDT",
    "FLOKIUSDT",
    "BOMEUSDT",
    "SHIBUSDT",
    "JUPUSDT",
    "WLDUSDT",
    "SEIUSDT",
    "TIAUSDT",
    "ARBUSDT",
    "OPUSDT",
    "GRTUSDT",
    "CRVUSDT",
    "SUSHIUSDT",
    "1INCHUSDT",
    "ENSUSDT",
    "LDOUSDT",
    "ATOMUSDT",
    "INJUSDT",
    "APTUSDT",
    "TWTUSDT",
    "HBARUSDT",
    "STXUSDT",
    "FILUSDT",
    "LUNCUSDT",
    "LUNAUSDT",
    "USTCUSDT",
    "CAKEUSDT",
    "JTOUSDT",
    "PYTHUSDT",
    "RUNEUSDT",
    "WOOUSDT",
    "IDUSDT",
    "ARKMUSDT",
    "FETUSDT",
    "AIUSDT",
    "PHBUSDT",
    "XAIUSDT",
    "NMRUSDT",
    "ARDRUSDT",
    "ARKUSDT",
    "API3USDT",
    "BANDUSDT",
    "CTSIUSDT",
    "DATAUSDT",
    "DCRUSDT",
    "DGBUSDT",
    "PORTALUSDT",
    "PENDLEUSDT",
    "PIXELUSDT",
]

BATCH_SIZE = 25
BATCH_1 = ALL_NEW_59_COINS_WITH_DATA[:BATCH_SIZE]  # ✅ Завершена
BATCH_2 = ALL_NEW_59_COINS_WITH_DATA[BATCH_SIZE:]  # 🔄 Текущая партия

# Вторая партия (топ 126-150)
TEST_SYMBOLS = BATCH_2

# Диапазоны параметров для оптимизации
PARAMETER_GRID = {
    "volume_ratio": [0.3, 0.4, 0.5, 0.6, 0.7],
    "rsi_oversold": [35, 40, 45],
    "rsi_overbought": [55, 60, 65],
    "trend_strength": [0.1, 0.15, 0.2, 0.25],
    "quality_score": [0.6, 0.65, 0.7, 0.72],
    "momentum_threshold": [-10.0, -5.0, -3.0, 0.0],
}

# Быстрая сетка: только volume_ratio и quality_score (как для топ 5)
# Остальные параметры фиксированные (как у топ 5):
# rsi_oversold=40, rsi_overbought=60, trend_strength=0.15, momentum_threshold=-5.0
QUICK_PARAMETER_GRID = {
    "volume_ratio": [0.3, 0.4, 0.5, 0.6, 0.7],  # 5 значений
    "rsi_oversold": [40],  # Фиксировано (как у топ 5)
    "rsi_overbought": [60],  # Фиксировано (как у топ 5)
    "trend_strength": [0.15],  # Фиксировано (как у топ 5)
    "quality_score": [0.6, 0.65, 0.7, 0.72],  # 4 значения
    "momentum_threshold": [-5.0],  # Фиксировано (как у топ 5)
}
# Итого: 5 * 1 * 1 * 1 * 4 * 1 = 20 комбинаций на монету (вместо 144!)

# Используем быструю сетку для ускорения
USE_QUICK_GRID = True
PARAM_GRID = QUICK_PARAMETER_GRID if USE_QUICK_GRID else PARAMETER_GRID

# Многопоточность
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "20"))  # 🔧 Многопоточность: 20 потоков

# ============================================================================
# ФУНКЦИИ
# ============================================================================


def test_symbol_with_params(
    symbol: str, params: Dict[str, float], intelligent_system
) -> Optional[Dict[str, Any]]:
    """Тестирует символ с заданными параметрами"""
    try:
        # Используем monkey patching для временной подмены параметров
        import src.ai.intelligent_filter_system as ifs_module

        # Сохраняем оригинальную функцию
        original_func = ifs_module.get_symbol_specific_parameters

        # Создаем новую функцию с подменой параметров
        def mock_get_symbol_params(s, *args, **kwargs):
            if s == symbol:
                return params.copy()
            return original_func(s, *args, **kwargs)

        # Подменяем функцию
        ifs_module.get_symbol_specific_parameters = mock_get_symbol_params

        # Также обновляем кэш в intelligent_system если есть
        if hasattr(intelligent_system, "_symbol_params_cache"):  # pylint: disable=protected-access
            intelligent_system._symbol_params_cache = {}  # pylint: disable=protected-access

        try:
            # Загружаем данные
            df = load_yearly_data(symbol, limit_days=PERIOD_DAYS)
            if df is None or len(df) < 50:
                return None

            # Запускаем бэктест
            stats = run_backtest(
                df, symbol=symbol, mode="soft", intelligent_system=intelligent_system
            )
            metrics = stats.get_metrics()

            metrics["symbol"] = symbol
            metrics["params"] = params
            return metrics
        finally:
            # Всегда восстанавливаем функцию
            ifs_module.get_symbol_specific_parameters = original_func

    except Exception as e:
        print(f"    ❌ Ошибка для {symbol}: {e}")
        import traceback

        traceback.print_exc()
        # Восстанавливаем функцию при ошибке
        import src.ai.intelligent_filter_system as ifs_module

        if hasattr(ifs_module, "get_symbol_specific_parameters"):
            try:
                # Проверяем, что это не наша mock функция
                if callable(getattr(ifs_module, "get_symbol_specific_parameters", None)):
                    pass  # Функция уже правильная
            except Exception:  # pylint: disable=broad-except
                pass
        return None


def test_combination(args) -> Optional[Dict[str, Any]]:
    """Тестирует одну комбинацию параметров (для многопоточности)"""
    symbol, params, combo_num, _total_combos = args
    try:
        intelligent_system = get_intelligent_filter_system()
        metrics = test_symbol_with_params(symbol, params, intelligent_system)

        if metrics is None:
            return None

        # Вычисляем комбинированный скор
        sharpe = metrics.get("sharpe_ratio", 0)
        win_rate = metrics.get("win_rate", 0)
        profit_factor = metrics.get("profit_factor", 0)
        total_return = metrics.get("total_return", 0)
        trades = metrics.get("total_trades", 0)

        score = (
            total_return * 0.3
            + sharpe * 5.0 * 0.25
            + win_rate * 0.25
            + min(profit_factor, 5.0) * 10 * 0.15
            + min(trades / 50, 1.0) * 5 * 0.05
        )

        metrics["score"] = score
        metrics["params"] = params
        metrics["combo_num"] = combo_num

        return metrics
    except Exception as e:
        print(f"    ❌ Ошибка для {symbol} комбинация {combo_num}: {e}")
        return None


def optimize_symbol_parameters(symbol: str) -> Dict[str, Any]:
    """Оптимизирует параметры для одного символа с многопоточностью"""
    print(f"\n{'=' * 80}")
    print(f"🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ ДЛЯ {symbol}")
    print(f"{'=' * 80}")

    # Генерируем все комбинации параметров
    param_names = list(PARAM_GRID.keys())
    param_values = list(PARAM_GRID.values())
    combinations = list(itertools.product(*param_values))

    # Фильтруем некорректные комбинации
    valid_combinations = []
    for combo in combinations:
        params = dict(zip(param_names, combo))
        if params["rsi_oversold"] < params["rsi_overbought"]:
            valid_combinations.append(params)

    print(f"📊 Тестируем {len(valid_combinations)} комбинаций параметров...")
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"🚀 Используем {MAX_WORKERS} потоков для ускорения")

    best_result = None
    best_params = None
    best_score = float("-inf")
    results = []

    # Подготавливаем аргументы для многопоточности
    test_args = [
        (symbol, params, i + 1, len(valid_combinations))
        for i, params in enumerate(valid_combinations)
    ]

    # Многопоточное тестирование
    completed = 0
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(valid_combinations))) as executor:
        futures = {executor.submit(test_combination, args): args[1] for args in test_args}

        for future in as_completed(futures):
            params = futures[future]
            completed += 1
            try:
                metrics = future.result(timeout=300)  # 5 минут таймаут

                if metrics is None:
                    continue

                results.append(metrics)
                score = metrics["score"]

                print(
                    f"  [{completed}/{len(valid_combinations)}] ✅ {symbol}: "
                    f"return={metrics['total_return']:+.2f}%, "
                    f"Sharpe={metrics['sharpe_ratio']:.2f}, "
                    f"WR={metrics['win_rate']:.1f}%, "
                    f"PF={metrics['profit_factor']:.2f}, "
                    f"Score={score:.2f}"
                )

                if score > best_score:
                    best_score = score
                    best_result = metrics
                    best_params = params
                    print(f"      🏆 НОВЫЙ ЛУЧШИЙ РЕЗУЛЬТАТ! Score: {score:.2f}")

            except Exception as e:
                print(f"    ❌ Ошибка выполнения: {e}")

    print(f"\n{'=' * 80}")
    print(f"✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА ДЛЯ {symbol}")
    print(f"{'=' * 80}")

    if best_result:
        print("🏆 ЛУЧШИЕ ПАРАМЕТРЫ:")
        for key, value in best_params.items():
            print(f"   {key}: {value}")
        print("\n📊 РЕЗУЛЬТАТЫ:")
        print(f"   Доходность: {best_result['total_return']:+.2f}%")
        print(f"   Sharpe Ratio: {best_result['sharpe_ratio']:.2f}")
        print(f"   Win Rate: {best_result['win_rate']:.1f}%")
        print(f"   Profit Factor: {best_result['profit_factor']:.2f}")
        print(f"   Сделок: {best_result['total_trades']}")
        print(f"   Score: {best_result['score']:.2f}")

    return {
        "symbol": symbol,
        "best_params": best_params,
        "best_result": best_result,
        "all_results": results,
    }


def main():
    """Главная функция"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"logs/optimize_50new_{timestamp}.log"
    os.makedirs("logs", exist_ok=True)

    # Настройка логирования
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )
    logger = logging.getLogger(__name__)

    print("=" * 80)
    print("🔧 ОПТИМИЗАЦИЯ ПАРАМЕТРОВ INTELLIGENT FILTER SYSTEM")
    print("📊 ДЛЯ НОВЫХ 50 МОНЕТ (топ 51-100)")
    print("=" * 80)
    print(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Монет для оптимизации: {len(TEST_SYMBOLS)}")
    print(f"📅 Период: {PERIOD_DAYS} дней")
    print(f"📁 Лог файл: {log_file}")
    print("=" * 80)
    logger.info("Начало оптимизации для %d монет", len(TEST_SYMBOLS))

    all_results = {}

    for idx, symbol in enumerate(TEST_SYMBOLS, 1):
        logger.info("[%d/%d] Начало оптимизации для %s", idx, len(TEST_SYMBOLS), symbol)
        print(f"\n{'=' * 80}")
        print(f"📈 [{idx}/{len(TEST_SYMBOLS)}] Оптимизация {symbol}")
        print(f"{'=' * 80}")
        result = optimize_symbol_parameters(symbol)
        all_results[symbol] = result
        logger.info("[%d/%d] ✅ ОПТИМИЗАЦИЯ ЗАВЕРШЕНА ДЛЯ %s", idx, len(TEST_SYMBOLS), symbol)
        if result.get("best_result"):
            best_res = result["best_result"]
            logger.info(
                "  Лучший результат: return=%.2f%%, Sharpe=%.2f",
                best_res.get("total_return", 0),
                best_res.get("sharpe_ratio", 0),
            )

    # Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"backtests/optimize_intelligent_params_{timestamp}.json"
    os.makedirs("backtests", exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)

    # Итоговая сводка
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)

    for symbol, result in all_results.items():
        if result.get("best_params"):
            print(f"\n{symbol}:")
            for key, value in result["best_params"].items():
                print(f"  {key}: {value}")
            if result.get("best_result"):
                print(f"  Доходность: {result['best_result']['total_return']:+.2f}%")
                print(f"  Sharpe: {result['best_result']['sharpe_ratio']:.2f}")
                print(f"  Win Rate: {result['best_result']['win_rate']:.1f}%")

    print(f"\n✅ Результаты сохранены в {output_file}")
    print("\n🎉 ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")


if __name__ == "__main__":
    import argparse

    opt_parser = argparse.ArgumentParser(description="Оптимизация параметров для монет")
    opt_parser.add_argument(
        "--symbol", type=str, help="Символ монеты для оптимизации (например, BTCUSDT)"
    )
    opt_parser.add_argument(
        "--period", type=int, default=30, help="Период оптимизации в днях (по умолчанию 30)"
    )
    opt_args = opt_parser.parse_args()

    # Если указан символ, оптимизируем только его
    if opt_args.symbol:
        PERIOD_DAYS = opt_args.period
        TEST_SYMBOLS = [opt_args.symbol]
        print(f"🎯 Оптимизация для одной монеты: {opt_args.symbol}")
        print(f"📅 Период: {PERIOD_DAYS} дней")

        opt_result = optimize_symbol_parameters(opt_args.symbol)

        # Сохраняем результат
        opt_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        opt_output_file = f"backtests/optimize_intelligent_params_{opt_timestamp}.json"
        os.makedirs("backtests", exist_ok=True)

        # Загружаем существующие результаты или создаем новые
        opt_all_results = {}
        opt_latest_file = (
            max(
                glob.glob("backtests/optimize_intelligent_params_*.json"),
                default=None,
                key=os.path.getmtime,
            )
            if glob.glob("backtests/optimize_intelligent_params_*.json")
            else None
        )
        if opt_latest_file:
            try:
                with open(opt_latest_file, encoding="utf-8") as opt_f:
                    opt_all_results = json.load(opt_f)
            except Exception:
                pass

        opt_all_results[opt_args.symbol] = opt_result

        with open(opt_output_file, "w", encoding="utf-8") as opt_f:
            json.dump(opt_all_results, opt_f, indent=2, default=str)

        print(f"\n✅ Результаты сохранены в {opt_output_file}")
        print("\n🎉 ОПТИМИЗАЦИЯ ЗАВЕРШЕНА!")
    else:
        main()
