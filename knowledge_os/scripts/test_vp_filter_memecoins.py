#!/usr/bin/env python3
"""
Тест Volume Profile фильтра на мемкойнах
Гипотеза: На мемкойнах с высокой волатильностью фильтр может работать лучше
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройки для теста
os.environ["USE_VP_FILTER"] = "True"
os.environ["DISABLE_EXTRA_FILTERS"] = "true"
os.environ["volume_profile_threshold"] = "0.6"

import logging

from scripts.backtest_5coins_intelligent import load_yearly_data, run_backtest
from src.signals.filters_volume_vwap import get_vp_filter_stats, reset_vp_filter_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Мемкойны для тестирования
MEMECOINS = [
    "DOGEUSDT",  # Dogecoin - классический мемкойн
    "SHIBUSDT",  # Shiba Inu - популярный мемкойн
    "PEPEUSDT",  # Pepe - новый мемкойн
    "FLOKIUSDT",  # Floki - еще один мемкойн
    "BONKUSDT",  # Bonk - Solana мемкойн
]

# Для сравнения - обычные монеты
REGULAR_COINS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
]


def test_vp_filter_on_symbols(symbols: list, category: str, period_days: int = 7):
    """Тестирует VP фильтр на списке символов"""
    print("=" * 80)
    print(f"📊 ТЕСТ VOLUME PROFILE ФИЛЬТРА НА {category.upper()}")
    print("=" * 80)
    print(f"📅 Период: {period_days} дней")
    print("🎯 Параметр: volume_profile_threshold = 0.6")
    print(f"📊 Символы: {', '.join(symbols)}")
    print("=" * 80)

    # Сбрасываем статистику перед тестом
    reset_vp_filter_stats()

    total_trades = 0
    total_return = 0.0
    successful_symbols = []
    failed_symbols = []

    for symbol in symbols:
        print(f"\n📊 Тестирование {symbol}...")
        try:
            df = load_yearly_data(symbol, limit_days=period_days)
            if df is None or len(df) < 100:
                print("   ❌ Недостаточно данных")
                failed_symbols.append(symbol)
                continue

            stats = run_backtest(df, symbol=symbol, mode="soft")
            metrics = stats.get_metrics()

            trades = metrics.get("total_trades", 0)
            ret = metrics.get("total_return", 0)

            if trades > 0:
                total_trades += trades
                total_return += ret
                successful_symbols.append(symbol)
                print(f"   ✅ {symbol}: {ret:+.2f}% ({trades} сделок)")
            else:
                print(f"   ⚠️ {symbol}: Нет сделок")
                failed_symbols.append(symbol)
        except Exception as e:
            print(f"   ❌ Ошибка для {symbol}: {e}")
            failed_symbols.append(symbol)

    # Получаем финальную статистику
    vp_stats = get_vp_filter_stats()

    print("\n" + "=" * 80)
    print(f"📊 СТАТИСТИКА VOLUME PROFILE ФИЛЬТРА ({category})")
    print("=" * 80)
    print(f"📈 Всего проверок: {vp_stats['total_checked']}")
    print(f"✅ Пропущено сигналов: {vp_stats['passed_count']} ({vp_stats['pass_rate_pct']:.1f}%)")
    print(
        f"❌ Заблокировано сигналов: {vp_stats['blocked_count']} ({vp_stats['block_rate_pct']:.1f}%)"
    )

    if vp_stats["blocked_by_reason"]:
        print("\n📋 Причины блокировок:")
        for reason, count in sorted(
            vp_stats["blocked_by_reason"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = (count / vp_stats["blocked_count"] * 100) if vp_stats["blocked_count"] > 0 else 0
            print(f"   {reason}: {count} ({pct:.1f}%)")

    print("\n" + "=" * 80)
    print(f"📊 РЕЗУЛЬТАТЫ ТОРГОВЛИ ({category})")
    print("=" * 80)
    print(f"📈 Общая доходность: {total_return:+.2f}%")
    print(f"📊 Всего сделок: {total_trades}")
    print(f"✅ Успешных символов: {len(successful_symbols)}/{len(symbols)}")
    if failed_symbols:
        print(f"❌ Проблемных символов: {', '.join(failed_symbols)}")

    return {
        "category": category,
        "stats": vp_stats,
        "trades": total_trades,
        "return": total_return,
        "successful_symbols": successful_symbols,
        "failed_symbols": failed_symbols,
    }


def compare_results(memecoin_results: dict, regular_results: dict):
    """Сравнивает результаты на мемкойнах и обычных монетах"""
    print("\n" + "=" * 80)
    print("🔬 СРАВНИТЕЛЬНЫЙ АНАЛИЗ")
    print("=" * 80)

    print("\n📊 МЕМКОЙНЫ:")
    print(f"   Блокировка: {memecoin_results['stats']['block_rate_pct']:.1f}%")
    print(f"   Доходность: {memecoin_results['return']:+.2f}%")
    print(f"   Сделок: {memecoin_results['trades']}")

    print("\n📊 ОБЫЧНЫЕ МОНЕТЫ:")
    print(f"   Блокировка: {regular_results['stats']['block_rate_pct']:.1f}%")
    print(f"   Доходность: {regular_results['return']:+.2f}%")
    print(f"   Сделок: {regular_results['trades']}")

    print("\n" + "=" * 80)
    print("💡 ВЫВОДЫ")
    print("=" * 80)

    memecoin_block_rate = memecoin_results["stats"]["block_rate_pct"]
    regular_block_rate = regular_results["stats"]["block_rate_pct"]

    if memecoin_block_rate > regular_block_rate * 2:
        print("✅ Фильтр работает ЛУЧШЕ на мемкойнах!")
        print(f"   Блокирует {memecoin_block_rate:.1f}% vs {regular_block_rate:.1f}% на обычных")
        print("   → Рекомендация: Использовать VP фильтр ТОЛЬКО для мемкойнов")
    elif memecoin_block_rate < regular_block_rate * 0.5:
        print("⚠️ Фильтр работает ХУЖЕ на мемкойнах")
        print(f"   Блокирует {memecoin_block_rate:.1f}% vs {regular_block_rate:.1f}% на обычных")
        print("   → Рекомендация: НЕ использовать VP фильтр для мемкойнов")
    else:
        print("➡️ Фильтр работает ОДИНАКОВО на мемкойнах и обычных монетах")
        print(f"   Блокирует {memecoin_block_rate:.1f}% vs {regular_block_rate:.1f}%")
        print("   → Рекомендация: Фильтр неэффективен везде")

    print("=" * 80)


if __name__ == "__main__":
    print("=" * 80)
    print("🧪 ТЕСТ VOLUME PROFILE ФИЛЬТРА НА МЕМКОЙНАХ")
    print("=" * 80)
    print("\n💡 ГИПОТЕЗА:")
    print("   На мемкойнах с высокой волатильностью Volume Profile фильтр")
    print("   может работать лучше, так как:")
    print("   1. Более выраженные зоны ликвидности")
    print("   2. Более четкие POC и Value Area")
    print("   3. Больше экстремальных движений")
    print("=" * 80)

    period_days = 7  # Быстрый тест

    # Тест на мемкойнах
    memecoin_results = test_vp_filter_on_symbols(MEMECOINS, "МЕМКОЙНЫ", period_days)

    # Тест на обычных монетах для сравнения
    print("\n\n")
    regular_results = test_vp_filter_on_symbols(REGULAR_COINS, "ОБЫЧНЫЕ МОНЕТЫ", period_days)

    # Сравнение
    compare_results(memecoin_results, regular_results)

    print("\n" + "=" * 80)
    print("💡 Для более точной оценки запустите на 30 днях:")
    print("   python3 scripts/test_vp_filter_memecoins.py --days 30")
    print("=" * 80)
