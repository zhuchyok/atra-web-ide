#!/usr/bin/env python3
"""Загрузка данных за месяц по топ 100 монет и бектест."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Импорты после sys.path (ленивая загрузка)
# pylint: disable=wrong-import-position
from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Используем продвинутый бектест из run_advanced_backtest.py


async def main():
    """Основная функция."""
    logger.info("🚀 Начало загрузки данных и бектеста")

    # Создаем загрузчик данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        # Получаем топ 100 монет
        logger.info("📊 Получение топ 100 монет...")
        top_symbols = await loader.get_top_symbols(limit=100)
        logger.info("✅ Получено %d монет", len(top_symbols))

        # Загружаем данные за месяц
        logger.info("📥 Загрузка данных за месяц...")
        data_dict = await loader.load_multiple_symbols(
            symbols=top_symbols,
            interval="1h",
            days=30,
        )

        # Фильтруем символы с достаточным количеством данных
        valid_data = {k: v for k, v in data_dict.items() if not v.empty and len(v) >= 100}
        logger.info(
            "✅ Загружено данных для %d символов (из %d)", len(valid_data), len(top_symbols)
        )

        # Сохраняем данные в CSV (опционально)
        data_dir = Path("data/backtest_data")
        loader.save_to_csv(valid_data, data_dir)
        logger.info("💾 Данные сохранены в %s", data_dir)

    # Запускаем продвинутый бектест (как вчера)
    logger.info("🧪 Запуск продвинутого бектеста...")
    backtest = AdvancedBacktest(
        initial_balance=10000.0,
        risk_per_trade=2.0,
        leverage=2.0,
    )

    # Получаем данные BTC для определения тренда
    btc_df = valid_data.get("BTCUSDT")
    if btc_df is None or btc_df.empty:
        logger.warning("⚠️ Данные BTC не найдены, используем первый доступный символ")
        btc_df = list(valid_data.values())[0] if valid_data else pd.DataFrame()

    # Запускаем бектест для каждого символа (асинхронно)
    for symbol, df in valid_data.items():
        if df.empty or len(df) < 100:
            continue
        logger.info("📊 Бектест для %s (%d свечей)", symbol, len(df))
        await backtest.run_backtest(symbol, df, btc_df)

    # Генерируем финальный отчет
    results = backtest.calculate_metrics()

    # Выводим результаты
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ БЕКТЕСТА (Топ 100 монет, 1 месяц)")
    print("=" * 80)
    print("\n💰 ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    print(f"  Начальный баланс: {backtest.initial_balance:.2f} USDT")
    print(f"  Финальный баланс: {results.get('final_balance', backtest.current_balance):.2f} USDT")
    print(
        f"  Общий PnL: {results.get('total_pnl', 0):.2f} USDT ({results.get('total_return', 0):.2f}%)"
    )
    print(f"  Максимальная прибыль: {results.get('max_profit', 0):.2f} USDT")
    print(f"  Максимальный убыток: {results.get('max_loss', 0):.2f} USDT")
    print(f"  Максимальная просадка: {results.get('max_drawdown', 0):.2f}%")

    print("\n📈 СТАТИСТИКА СДЕЛОК:")
    print(f"  Всего сделок: {results.get('total_trades', 0)}")
    print(f"  Прибыльных: {results.get('winning_trades', 0)} ({results.get('win_rate', 0):.2f}%)")
    print(f"  Убыточных: {results.get('losing_trades', 0)}")
    print(f"  Средняя прибыль: {results.get('avg_win', 0):.2f} USDT")
    print(f"  Средний убыток: {results.get('avg_loss', 0):.2f} USDT")
    print(f"  Profit Factor: {results.get('profit_factor', 0):.2f}")

    print("\n📊 МЕТРИКИ РИСКА:")
    print(f"  Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
    print(f"  Sortino Ratio: {results.get('sortino_ratio', 0):.2f}")

    print("\n🤖 ИСПОЛЬЗОВАНИЕ ИИ:")
    print(f"  Сделок с индивидуальными параметрами: {results.get('trades_with_symbol_params', 0)}")
    print(f"  Сделок с анализом паттернов: {results.get('trades_with_patterns_analysis', 0)}")
    print(f"  Всего паттернов в системе: {results.get('patterns_total', 0)}")

    # Сохраняем отчет
    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / f"backtest_top100_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    report_data = {
        "backtest_info": {
            "start_date": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "symbols_count": len(valid_data),
            "days": 30,
            "initial_balance": backtest.initial_balance,
            "risk_per_trade": backtest.risk_per_trade,
            "leverage": backtest.leverage,
        },
        "metrics": results,
        "trades": backtest.trades[:1000],  # Первые 1000 сделок
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("💾 Отчет сохранен: %s", report_file)

    print("\n" + "=" * 80)
    print("✅ Бектест завершен!")
    print(f"💾 Отчет сохранен: {report_file}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
