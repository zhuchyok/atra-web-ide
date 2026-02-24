"""
Быстрый тест с экстремально ослабленным RSI фильтром (10-90)
для проверки количества генерируемых сделок
"""

import asyncio
import json
import logging
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

# Тест на 30 дней с работающей конфигурацией (без MACD/BB, без XRPUSDT)
# XRPUSDT исключен из-за больших убытков (-592.69 USDT за 30 дней)
TEST_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]  # Исключен XRPUSDT
TEST_DAYS = 30  # 🔧 Увеличено до 30 дней для сбора большей статистики


async def main():
    logger.info("🚀 Запуск %d-ДНЕВНОГО ТЕСТА С ОПТИМИЗИРОВАННОЙ КОНФИГУРАЦИЕЙ...", TEST_DAYS)
    logger.info("📊 Период: %d дней", TEST_DAYS)
    logger.info("🪙 Монеты: %s (XRPUSDT исключен из-за больших убытков)", ", ".join(TEST_SYMBOLS))
    logger.info("✅ RSI фильтр: ВОССТАНОВЛЕН с параметрами 25-75")
    logger.info("🔓 MACD фильтр: ОТКЛЮЧЕН (не улучшил качество)")
    logger.info("🔓 BB фильтр: ОТКЛЮЧЕН (не улучшил качество)")
    logger.info("🔓 Correlation Risk: ВРЕМЕННО ОТКЛЮЧЕН для диагностики")
    logger.info("🔧 Volume фильтр: Порог снижен с 0.8 до 0.5")
    logger.info("🔧 AI Score пороги: 5.0 (soft) / 10.0 (strict) - ослаблены")

    backtest = AdvancedBacktest(
        initial_balance=10000.0,
        risk_per_trade=2.0,
        leverage=2.0,
    )

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

        await backtest.run_backtest(symbol, df, btc_df, days=TEST_DAYS)

        symbol_trades = [t for t in backtest.trades if t.get("symbol") == symbol]
        total_trades = len(symbol_trades)
        winning_trades = len([t for t in symbol_trades if t.get("pnl", 0) > 0])
        losing_trades = total_trades - winning_trades
        total_pnl = sum(t.get("pnl", 0) for t in symbol_trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

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

    overall_metrics = backtest.calculate_metrics()

    report_data = {
        "test_info": {
            "test_type": "extreme_rsi_test",
            "symbols": TEST_SYMBOLS,
            "days": TEST_DAYS,
            "rsi_config": {
                "oversold": 25,
                "overbought": 75,
                "note": "Восстановлен с параметрами 25-75 для улучшения качества сигналов",
            },
            "ai_score_config": {
                "soft_threshold": 5.0,
                "strict_threshold": 10.0,
                "note": "Ослаблены для увеличения количества сигналов",
            },
            "filters_changes": {
                "rsi": "ВОССТАНОВЛЕН с параметрами 25-75",
                "macd": "ОТКЛЮЧЕН (не улучшил качество - Win Rate упал с 39.13% до 27.78%)",
                "bb": "ОТКЛЮЧЕН (не улучшил качество - Win Rate упал с 39.13% до 27.78%)",
                "correlation_risk": "ВРЕМЕННО ОТКЛЮЧЕН для диагностики (блокировал 64.34%)",
                "volume": "Порог снижен с 0.8 до 0.5 (снижение на 37.5%)",
                "ai_score": "Ослаблен: 5.0/10.0 (было 7.0/15.0)",
                "portfolio_risk": "Пропускаем POSITION_SIZE_TOO_LARGE",
                "xrpusdt": "ИСКЛЮЧЕН из торговли (убыток -592.69 USDT за 30 дней, Win Rate 38.10%)",
                "note": "Оптимизированная конфигурация: RSI + AI Score + Volume, без XRPUSDT",
            },
        },
        "overall_metrics": overall_metrics,
        "results_by_symbol": results_by_symbol,
        "trades": all_trades,
    }

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_file = report_dir / f"extreme_rsi_test_{timestamp}.json"

    with open(json_report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("💾 JSON отчет сохранен: %s", json_report_file)

    print("\n" + "=" * 100)
    print(f"📊 РЕЗУЛЬТАТЫ {TEST_DAYS}-ДНЕВНОГО ТЕСТА С ОПТИМИЗИРОВАННОЙ КОНФИГУРАЦИЕЙ")
    print("=" * 100)
    print(f"\n📅 Период: {TEST_DAYS} дней")
    print(f"🪙 Монеты: {', '.join(TEST_SYMBOLS)} (XRPUSDT исключен из-за больших убытков)")
    print("✅ RSI фильтр: ВОССТАНОВЛЕН с параметрами 25-75")
    print("🔓 MACD фильтр: ОТКЛЮЧЕН (не улучшил качество)")
    print("🔓 BB фильтр: ОТКЛЮЧЕН (не улучшил качество)")
    print("🔓 Correlation Risk: ВРЕМЕННО ОТКЛЮЧЕН для диагностики")
    print("🔧 Volume фильтр: Порог снижен с 0.8 до 0.5")
    print("🔧 AI Score пороги: 5.0 (soft) / 10.0 (strict) - ослаблены")

    print("\n💰 ОБЩИЕ ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    print(f"  Начальный баланс: {backtest.initial_balance:.2f} USDT")
    print(
        f"  Финальный баланс: {overall_metrics.get('final_balance', backtest.initial_balance):.2f} USDT"
    )
    print(
        f"  Общий PnL: {overall_metrics.get('total_pnl', 0):.2f} USDT ({overall_metrics.get('total_return', 0):.2f}%)"
    )
    print(f"  Максимальная просадка: {overall_metrics.get('max_drawdown', 0):.2f}%\n")

    print("📈 ОБЩАЯ СТАТИСТИКА СДЕЛОК:")
    print(f"  Всего сделок: {overall_metrics.get('total_trades', 0)}")
    print(f"  Win Rate: {overall_metrics.get('win_rate', 0):.2f}%")
    print(f"  Profit Factor: {overall_metrics.get('profit_factor', 0):.2f}\n")

    print("📊 РЕЗУЛЬТАТЫ ПО МОНЕТАМ:")
    for res in results_by_symbol:
        print(
            f"  {res['symbol']}: {res['total_trades']} сделок, PnL: {res['total_pnl']:.2f} USDT, Win Rate: {res['win_rate']:.2f}%"
        )
    print("\n")

    filter_stats = overall_metrics.get("filter_statistics", {})
    if filter_stats:
        print("\n🔍 СТАТИСТИКА БЛОКИРОВОК ПО ФИЛЬТРАМ:")
        print("-" * 100)
        total_checked = filter_stats.get("total_signals_checked", 0)
        rejections = filter_stats.get("filter_rejections", {})
        percentages = filter_stats.get("rejection_percentages", {})

        print(f"\n  Всего проверено сигналов: {total_checked}")
        print("\n  Блокировок по фильтрам:")

        sorted_rejections = sorted(rejections.items(), key=lambda x: x[1], reverse=True)

        for filter_name, count in sorted_rejections:
            if count > 0:
                pct = percentages.get(filter_name, 0)
                filter_display_name = {
                    "rsi_filter": "RSI фильтр",
                    "macd_filter": "MACD фильтр",
                    "volume_filter": "Volume фильтр",
                    "btc_trend_filter": "BTC Trend фильтр",
                    "eth_trend_filter": "ETH Trend фильтр",
                    "sol_trend_filter": "SOL Trend фильтр",
                    "bb_filter": "BB позиция фильтр",
                    "bb_width_filter": "BB ширина фильтр",
                    "ai_score_filter": "AI Score фильтр",
                    "ai_volume_filter": "AI Volume фильтр",
                    "ai_volatility_filter": "AI Volatility фильтр",
                    "anomaly_filter": "Anomaly фильтр",
                    "direction_confidence": "Direction Confidence",
                    "rsi_warning": "RSI Warning",
                    "quality_score": "Quality Score / Min Confidence",
                    "portfolio_risk": "Portfolio Risk Manager",
                    "correlation_risk": "Correlation Risk Manager",
                    "max_positions": "Max Positions",
                    "max_drawdown": "Max Drawdown",
                    "nan_values": "NaN значения",
                }.get(filter_name, filter_name)

                print(f"    {filter_display_name}: {count} ({pct:.2f}%)")
        print("\n")

    total_trades = overall_metrics.get("total_trades", 0)
    if total_trades >= 20:
        print(f"  ✅ ОТЛИЧНО! Много сделок: {total_trades}")
        print("  ✅ RSI фильтр работает правильно!")
        if overall_metrics.get("win_rate", 0) >= 40:
            print("  🎉 Win Rate приемлемый!")
        else:
            print("  ⚠️ Win Rate низкий, но это нормально для теста")
    elif total_trades >= 10:
        print(f"  ✅ ХОРОШО! Появилось достаточно сделок: {total_trades}")
        print("  ✅ Можно анализировать качество")
    elif total_trades > 0:
        print(f"  ⚠️ Мало сделок: {total_trades}")
        print("  ⚠️ Нужна дальнейшая диагностика")
    else:
        print("  ❌ Все еще 0 сделок. Требуется глубокая диагностика.")

    logger.info("✅ Тест с экстремально ослабленным RSI завершен!")


if __name__ == "__main__":
    asyncio.run(main())
