"""
Диагностический тест для проверки исправлений фильтров.
Тестирует только 1-2 монеты за короткий период для быстрой проверки.
"""

import asyncio
import json
import logging

# Добавляем корневую директорию проекта в sys.path
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 🔧 ДИАГНОСТИЧЕСКИЕ ПАРАМЕТРЫ
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT"]  # Только 2 монеты для скорости
TEST_DAYS = 7  # Только 7 дней для быстрого теста
INITIAL_BALANCE = 10000.0
RISK_PER_TRADE = 2.0
LEVERAGE = 2.0


async def run_diagnostic_test():
    """Запускает диагностический тест с исправленными фильтрами."""
    logger.info("🚀 Запуск диагностического теста исправленных фильтров...")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"📊 Параметры: {len(TEST_SYMBOLS)} монет, {TEST_DAYS} дней")

    backtest = AdvancedBacktest(
        initial_balance=INITIAL_BALANCE,
        risk_per_trade=RISK_PER_TRADE,
        leverage=LEVERAGE,
    )

    # Загружаем данные BTC для тренд-фильтров
    async with HistoricalDataLoader(exchange="binance") as loader:
        logger.info("📥 Загрузка данных BTC, ETH, SOL...")
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=TEST_DAYS)
        eth_df = await loader.fetch_ohlcv("ETHUSDT", interval="1h", days=TEST_DAYS)
        sol_df = await loader.fetch_ohlcv("SOLUSDT", interval="1h", days=TEST_DAYS)

        if btc_df is not None:
            backtest.btc_df = btc_df
        if eth_df is not None:
            backtest.eth_df = eth_df
        if sol_df is not None:
            backtest.sol_df = sol_df

        logger.info("📥 Загрузка исторических данных для тестовых монет...")
        data_dict = await loader.load_multiple_symbols(TEST_SYMBOLS, interval="1h", days=TEST_DAYS)

    results_by_symbol = []
    all_trades = []

    for symbol in TEST_SYMBOLS:
        df = data_dict.get(symbol)
        if df is None or df.empty:
            logger.warning("⚠️ Нет данных для %s, пропускаем", symbol)
            continue

        logger.info("📊 Запуск бэктеста для %s (%d свечей)", symbol, len(df))

        # Запускаем бэктест
        await backtest.run_backtest(symbol, df, btc_df, days=TEST_DAYS)

        # Получаем метрики
        metrics = backtest.calculate_metrics()

        # Подсчитываем статистику по сделкам
        symbol_trades = [t for t in backtest.trades if t.get("symbol") == symbol]
        total_trades = len(symbol_trades)
        winning_trades = len([t for t in symbol_trades if t.get("pnl", 0) > 0])
        losing_trades = total_trades - winning_trades
        total_pnl = sum(t.get("pnl", 0) for t in symbol_trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        # Расчет Profit Factor
        gross_profit = sum(t.get("pnl", 0) for t in symbol_trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in symbol_trades if t.get("pnl", 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        results_by_symbol.append(
            {
                "symbol": symbol,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "total_pnl": total_pnl,
                "trades": symbol_trades,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
            }
        )
        all_trades.extend(symbol_trades)

    # Общие метрики
    overall_metrics = backtest.calculate_metrics()

    # Выводим результаты
    logger.info("\n" + "=" * 100)
    logger.info("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИЧЕСКОГО ТЕСТА")
    logger.info("=" * 100)
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"\n📅 Период: {TEST_DAYS} дней")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"🪙 Монеты: {', '.join(TEST_SYMBOLS)}")
    logger.info("🔧 Фильтры: Исправленные (RSI ослаблен, AI Score=10.0, AI Volatility отключен)")

    logger.info("\n💰 ОБЩИЕ ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Начальный баланс: {INITIAL_BALANCE:.2f} USDT")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Финальный баланс: {overall_metrics.get('final_balance', INITIAL_BALANCE):.2f} USDT")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Общий PnL: {overall_metrics.get('total_pnl', 0):.2f} USDT")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Максимальная просадка: {overall_metrics.get('max_drawdown', 0):.2f}%")

    logger.info("\n📈 ОБЩАЯ СТАТИСТИКА СДЕЛОК:")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Всего сделок: {overall_metrics.get('total_trades', 0)}")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Win Rate: {overall_metrics.get('win_rate', 0):.2f}%")
    # TODO: Convert f-string to %s formatting for performance
    logger.info(f"  Profit Factor: {overall_metrics.get('profit_factor', 0):.2f}")

    logger.info("\n📊 РЕЗУЛЬТАТЫ ПО МОНЕТАМ:")
    logger.info("-" * 100)
    for res in results_by_symbol:
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"\n  {res['symbol']}:")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"    Сделок: {res['total_trades']}")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"    Win Rate: {res['win_rate']:.2f}%")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"    PnL: {res['total_pnl']:.2f} USDT")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"    Profit Factor: {res['profit_factor']:.2f}")

    # Статистика по фильтрам
    filter_stats = overall_metrics.get("filter_statistics", {})
    if filter_stats:
        logger.info("\n🔍 СТАТИСТИКА БЛОКИРОВОК ПО ФИЛЬТРАМ:")
        logger.info("-" * 100)
        total_checked = filter_stats.get("total_signals_checked", 0)
        rejections = filter_stats.get("filter_rejections", {})
        percentages = filter_stats.get("rejection_percentages", {})

        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"\n  Всего проверено сигналов: {total_checked}")
        logger.info("\n  Блокировок по фильтрам (топ-5):")

        sorted_rejections = sorted(rejections.items(), key=lambda x: x[1], reverse=True)
        for filter_name, count in sorted_rejections[:5]:
            if count > 0:
                pct = percentages.get(filter_name, 0)
                filter_display_name = {
                    "rsi_filter": "RSI фильтр",
                    "macd_filter": "MACD фильтр",
                    "volume_filter": "Volume фильтр",
                    "ai_score_filter": "AI Score фильтр",
                    "ai_volatility_filter": "AI Volatility фильтр",
                }.get(filter_name, filter_name)

                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"    {filter_display_name}: {count} ({pct:.2f}%)")

    # Анализ результатов
    logger.info("\n🎯 АНАЛИЗ РЕЗУЛЬТАТОВ:")
    logger.info("-" * 100)
    total_trades = overall_metrics.get("total_trades", 0)
    if total_trades > 0:
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"  ✅ УСПЕХ! Появились сделки: {total_trades}")
        logger.info("  ✅ Проблема с RSI фильтром решена!")
        if total_trades >= 10:
            logger.info("  ✅ Количество сделок достаточное для анализа")
        else:
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"  ⚠️ Количество сделок низкое, но это нормально для {TEST_DAYS} дней")
    else:
        logger.info("  ❌ ПРОБЛЕМА: Все еще 0 сделок")
        logger.info("  ❌ Нужна дополнительная диагностика других фильтров")

    # Сохраняем отчет
    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_file = report_dir / f"diagnostic_test_{timestamp}.json"

    report_data = {
        "test_info": {
            "test_type": "diagnostic",
            "symbols": TEST_SYMBOLS,
            "days": TEST_DAYS,
            "filters_changes": {
                "rsi": "Убрана проверка prev_rsi - разрешено нахождение в зоне",
                "ai_score": "Порог снижен с 15.0 до 10.0",
                "ai_volatility": "Временно отключен",
            },
        },
        "overall_metrics": overall_metrics,
        "results_by_symbol": results_by_symbol,
        "trades": all_trades,
    }

    with open(json_report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("💾 Отчет сохранен: %s", json_report_file)

    logger.info("\n" + "=" * 100)
    logger.info("✅ Диагностический тест завершен!")
    logger.info("=" * 100)


if __name__ == "__main__":
    asyncio.run(run_diagnostic_test())
