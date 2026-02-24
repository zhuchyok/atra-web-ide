"""
Универсальный скрипт для запуска оптимизированных бэктестов
Поддерживает разные периоды тестирования (30, 90, 365 дней)
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
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

# Оптимальный портфель на основе массового скрининга (2025-11-13)
# Топ-5 монет с Win Rate ≥ 50% и низкой просадкой
OPTIMIZED_SYMBOLS = [
    "AVAXUSDT",  # 61.90% WR, PF 1.15, MaxDD 5.04%
    "LINKUSDT",  # 61.11% WR, PF 1.38, MaxDD 3.50%
    "SOLUSDT",  # 60.00% WR, PF 1.56, MaxDD 3.65%
    "SUIUSDT",  # 50.00% WR, PF 1.46, MaxDD 3.70%
    "DOGEUSDT",  # 50.00% WR, PF 1.17, MaxDD 5.05%
]


async def run_backtest(days: int, symbols: List[str] = None):
    """
    Запуск бэктеста на указанный период

    Args:
        days: Количество дней для тестирования
        symbols: Список монет для тестирования (по умолчанию OPTIMIZED_SYMBOLS)
    """
    if symbols is None:
        symbols = OPTIMIZED_SYMBOLS

    logger.info("🚀 Запуск %d-ДНЕВНОГО ТЕСТА С ОПТИМИЗИРОВАННОЙ КОНФИГУРАЦИЕЙ...", days)
    logger.info("📊 Период: %d дней", days)
    logger.info(
        "🪙 Монеты: %s (Оптимальный портфель на основе массового скрининга)", ", ".join(symbols)
    )
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
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=days)
        eth_df = await loader.fetch_ohlcv("ETHUSDT", interval="1h", days=days)
        sol_df = await loader.fetch_ohlcv("SOLUSDT", interval="1h", days=days)

        if btc_df is not None:
            backtest.btc_df = btc_df
        if eth_df is not None:
            backtest.eth_df = eth_df
        if sol_df is not None:
            backtest.sol_df = sol_df

        logger.info("📥 Загрузка исторических данных для тестовых монет...")
        data_dict = await loader.load_multiple_symbols(symbols, interval="1h", days=days)

    results_by_symbol = []
    all_trades = []

    for symbol in symbols:
        df = data_dict.get(symbol)
        if df is None or df.empty:
            logger.warning("⚠️ Нет данных для %s, пропускаем", symbol)
            continue

        logger.info("📊 Запуск бэктеста для %s (%d свечей)", symbol, len(df))

        await backtest.run_backtest(symbol, df, btc_df, days=days)

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
            "test_type": "optimized_backtest",
            "symbols": symbols,
            "days": days,
            "xrpusdt_excluded": True,
            "xrpusdt_reason": "Большие убытки (-592.69 USDT за 30 дней, Win Rate 38.10%)",
            "rsi_config": {
                "oversold": 25,
                "overbought": 75,
                "note": "Восстановлен с параметрами 25-75",
            },
            "ai_score_config": {
                "soft_threshold": 5.0,
                "strict_threshold": 10.0,
                "note": "Ослаблены для увеличения количества сигналов",
            },
            "filters_changes": {
                "rsi": "ВОССТАНОВЛЕН с параметрами 25-75",
                "macd": "ОТКЛЮЧЕН (не улучшил качество)",
                "bb": "ОТКЛЮЧЕН (не улучшил качество)",
                "correlation_risk": "ВРЕМЕННО ОТКЛЮЧЕН для диагностики",
                "volume": "Порог снижен с 0.8 до 0.5",
                "ai_score": "Ослаблен: 5.0/10.0",
                "xrpusdt": "ИСКЛЮЧЕН из торговли",
            },
        },
        "overall_metrics": overall_metrics,
        "results_by_symbol": results_by_symbol,
        "trades": all_trades,
    }

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_file = report_dir / f"optimized_backtest_{days}d_{timestamp}.json"

    with open(json_report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("💾 JSON отчет сохранен: %s", json_report_file)

    print("\n" + "=" * 100)
    print(f"📊 РЕЗУЛЬТАТЫ {days}-ДНЕВНОГО ТЕСТА С ОПТИМИЗИРОВАННОЙ КОНФИГУРАЦИЕЙ")
    print("=" * 100)
    print(f"\n📅 Период: {days} дней")
    print(f"🪙 Монеты: {', '.join(symbols)} (XRPUSDT исключен)")
    print("✅ RSI фильтр: ВОССТАНОВЛЕН с параметрами 25-75")
    print("🔓 MACD фильтр: ОТКЛЮЧЕН")
    print("🔓 BB фильтр: ОТКЛЮЧЕН")

    print("\n💰 ОБЩИЕ ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    print(f"  Начальный баланс: {backtest.initial_balance:.2f} USDT")
    print(
        f"  Финальный баланс: {overall_metrics.get('final_balance', backtest.initial_balance):.2f} USDT"
    )
    print(
        f"  Общий PnL: {overall_metrics.get('total_pnl', 0):.2f} USDT ({overall_metrics.get('total_return', 0):.2f}%)"
    )
    print(f"  Максимальная просадка: {overall_metrics.get('max_drawdown', 0):.2f}%")

    print("\n📈 ОБЩАЯ СТАТИСТИКА СДЕЛОК:")
    print(f"  Всего сделок: {overall_metrics.get('total_trades', 0)}")
    print(f"  Win Rate: {overall_metrics.get('win_rate', 0):.2f}%")
    print(f"  Profit Factor: {overall_metrics.get('profit_factor', 0):.2f}")
    print(f"  Avg Win: {overall_metrics.get('avg_win', 0):.2f} USDT")
    print(f"  Avg Loss: {overall_metrics.get('avg_loss', 0):.2f} USDT")

    print("\n📊 РЕЗУЛЬТАТЫ ПО МОНЕТАМ:")
    for result in results_by_symbol:
        status = "✅" if result["total_pnl"] > 0 else "❌"
        print(
            f"  {status} {result['symbol']}: {result['total_trades']} сделок, "
            f"PnL: {result['total_pnl']:.2f} USDT, Win Rate: {result['win_rate']:.2f}%"
        )

    # Критерии успеха
    print("\n🎯 КРИТЕРИИ УСПЕХА:")
    if days == 30:
        target_pnl = 12.0
        target_wr = 42.0
        target_pf = 0.85
    elif days == 90:
        target_pnl = 15.0
        target_wr = 43.0
        target_pf = 0.9
    else:  # 365
        target_pnl = 50.0
        target_wr = 42.0
        target_pf = 1.0

    actual_pnl = overall_metrics.get("total_return", 0)
    actual_wr = overall_metrics.get("win_rate", 0)
    actual_pf = overall_metrics.get("profit_factor", 0)

    print(
        f"  PnL: {actual_pnl:.2f}% {'✅' if actual_pnl >= target_pnl else '❌'} (цель: {target_pnl}%)"
    )
    print(
        f"  Win Rate: {actual_wr:.2f}% {'✅' if actual_wr >= target_wr else '❌'} (цель: {target_wr}%)"
    )
    print(
        f"  Profit Factor: {actual_pf:.2f} {'✅' if actual_pf >= target_pf else '❌'} (цель: {target_pf})"
    )

    return report_data


async def main():
    parser = argparse.ArgumentParser(description="Запуск оптимизированного бэктеста")
    parser.add_argument(
        "--days", type=int, default=30, help="Количество дней для тестирования (30, 90, 365)"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Список монет через запятую (по умолчанию: BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT)",
    )

    args = parser.parse_args()

    symbols = OPTIMIZED_SYMBOLS
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]

    await run_backtest(args.days, symbols)


if __name__ == "__main__":
    asyncio.run(main())
