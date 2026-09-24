#!/usr/bin/env python3
"""
Анализ статистики работы Volume Profile фильтра
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Настройки
os.environ["USE_VP_FILTER"] = "True"
os.environ["DISABLE_EXTRA_FILTERS"] = "true"
os.environ["volume_profile_threshold"] = "0.6"

import logging

from scripts.backtest_5coins_intelligent import load_yearly_data, run_backtest
from src.signals.filters_volume_vwap import get_vp_filter_stats, reset_vp_filter_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_vp_filter_stats(period_days: int = 7):
    """Анализирует статистику работы VP фильтра"""
    logger.info("=" * 80)
    logger.info("📊 АНАЛИЗ СТАТИСТИКИ VOLUME PROFILE ФИЛЬТРА")
    logger.info("=" * 80)
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"📅 Период: {period_days} дней")
    logger.info("🎯 Параметр: volume_profile_threshold = 0.6")
    logger.info("=" * 80)

    # Сбрасываем статистику перед тестом
    reset_vp_filter_stats()

    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]
    total_trades = 0
    total_return = 0.0

    for symbol in symbols:
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"\n📊 Тестирование {symbol}...")
        df = load_yearly_data(symbol, limit_days=period_days)
        if df is None or len(df) < 100:
            logger.info("   ❌ Недостаточно данных")
            continue

        stats = run_backtest(df, symbol=symbol, mode="soft")
        metrics = stats.get_metrics()

        trades = metrics.get("total_trades", 0)
        ret = metrics.get("total_return", 0)

        total_trades += trades
        total_return += ret

        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"   ✅ {symbol}: {ret:+.2f}% ({trades} сделок)")

    # Получаем финальную статистику
    vp_stats = get_vp_filter_stats()

    logger.info("\n" + "=" * 80)
    logger.info("📊 СТАТИСТИКА VOLUME PROFILE ФИЛЬТРА")
    logger.info("=" * 80)
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"📈 Всего проверок: {vp_stats['total_checked']}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"✅ Пропущено сигналов: {vp_stats['passed_count']} ({vp_stats['pass_rate_pct']:.1f}%)")
    logger.info(
        f"❌ Заблокировано сигналов: {vp_stats['blocked_count']} ({vp_stats['block_rate_pct']:.1f}%)"
    )

    if vp_stats["blocked_by_reason"]:
        logger.info("\n📋 Причины блокировок:")
        for reason, count in sorted(
            vp_stats["blocked_by_reason"].items(), key=lambda x: x[1], reverse=True
        ):
            pct = (count / vp_stats["blocked_count"] * 100) if vp_stats["blocked_count"] > 0 else 0
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"   {reason}: {count} ({pct:.1f}%)")

    logger.info("\n" + "=" * 80)
    logger.info("📊 РЕЗУЛЬТАТЫ ТОРГОВЛИ")
    logger.info("=" * 80)
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"📈 Общая доходность: {total_return:+.2f}%")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"📊 Всего сделок: {total_trades}")

    # Анализ и рекомендации
    logger.info("\n" + "=" * 80)
    logger.info("💡 АНАЛИЗ И РЕКОМЕНДАЦИИ")
    logger.info("=" * 80)

    block_rate = vp_stats["block_rate_pct"]

    if block_rate < 10:
        logger.info("⚠️ Фильтр блокирует < 10% сигналов")
        logger.info("   → Фильтр слишком мягкий, практически не работает")
        logger.info("   → РЕКОМЕНДАЦИЯ: Отключить фильтр или ужесточить логику")
        decision = "DISABLE_OR_TIGHTEN"
    elif 10 <= block_rate < 30:
        logger.info("✅ Фильтр блокирует 10-30% сигналов")
        logger.info("   → Фильтр работает умеренно")
        logger.info("   → РЕКОМЕНДАЦИЯ: Проанализировать качество заблокированных сигналов")
        logger.info("   → Если Win Rate заблокированных < 50% → фильтр ПОЛЕЗЕН")
        decision = "ANALYZE_QUALITY"
    else:
        logger.info("✅ Фильтр блокирует > 30% сигналов")
        logger.info("   → Фильтр активно работает")
        logger.info("   → РЕКОМЕНДАЦИЯ: Провести 30-дневный тест для точной оценки")
        decision = "EXTENDED_TEST"

    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"\n🎯 Решение: {decision}")
    logger.info("=" * 80)

    return {"stats": vp_stats, "trades": total_trades, "return": total_return, "decision": decision}


if __name__ == "__main__":
    result = analyze_vp_filter_stats(period_days=7)

    # Можно также протестировать на 30 днях
    logger.info("\n" + "=" * 80)
    logger.info("💡 Для более точной оценки запустите на 30 днях:")
    logger.info("   python3 scripts/analyze_vp_filter_stats.py --days 30")
    logger.info("=" * 80)
