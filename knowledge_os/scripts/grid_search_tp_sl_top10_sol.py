#!/usr/bin/env python3
"""
Грид-поиск TP1/TP2/SL для годового бектеста по TOP-10 SOL_HIGH монетам.

Использует AdvancedBacktest с жёстким оверрайдом TP/SL (tp_sl_override),
чтобы оценить, какие комбинации TP1/TP2/SL дают лучшую доходность портфеля.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# pylint: disable=wrong-import-position
from scripts.run_advanced_backtest import AdvancedBacktest

# Для грид-поиска уменьшаем уровень логирования до WARNING, чтобы не захламлять вывод
logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Финальный TOP-10 портфель из SOL_HIGH по результатам годового бектеста
TOP10_SOL_PORTFOLIO: List[str] = [
    "BONKUSDT",
    "NEIROUSDT",
    "SUIUSDT",
    "POLUSDT",
    "WIFUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "CRVUSDT",
    "OPUSDT",
]


def load_csv_data(symbol: str, data_dir: Optional[Path] = None) -> Optional[pd.DataFrame]:
    """Загружает OHLCV-данные из CSV для символа."""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"

    csv_file = data_dir / f"{symbol}.csv"
    if not csv_file.exists():
        logger.warning("⚠️ Файл не найден: %s", csv_file)
        return None

    try:
        df = pd.read_csv(csv_file)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
        elif df.index.name == "timestamp" or df.index.dtype == "object":
            df.index = pd.to_datetime(df.index)

        required_cols = ["open", "high", "low", "close", "volume"]
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Не все необходимые колонки найдены для %s", symbol)
            return None

        return df
    except Exception as exc:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, exc)
        return None


async def run_portfolio_with_params(
    symbols: List[str],
    tp1_pct: float,
    tp2_pct: float,
    sl_pct: float,
    days: int = 365,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Запускает годовой бектест по портфелю с фиксированными TP1/TP2/SL.

    Возвращает агрегированные метрики по портфелю и список результатов по монетам.
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    # Загружаем BTC для тренда (как в годовом бектесте)
    logger.info("📥 Загрузка данных BTCUSDT для фильтров...")
    btc_df = load_csv_data("BTCUSDT", data_dir)
    if btc_df is None:
        logger.error("❌ Не удалось загрузить BTCUSDT для фильтров")
        return {}, []

    portfolio_results: List[Dict[str, Any]] = []
    total_trades = 0
    total_pnl = 0.0
    total_winning_trades = 0
    total_losing_trades = 0

    logger.info(
        "🚀 Грид-поиск: TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%% на портфеле из %d монет",
        tp1_pct,
        tp2_pct,
        sl_pct,
        len(symbols),
    )

    for idx, symbol in enumerate(symbols, start=1):
        logger.info("[%d/%d] Тестируем %s...", idx, len(symbols), symbol)
        df = load_csv_data(symbol, data_dir)
        if df is None or df.empty:
            logger.warning("⚠️ Пропускаем %s - нет данных", symbol)
            continue

        try:
            backtest = AdvancedBacktest(
                initial_balance=10000.0,
                risk_per_trade=2.0,
                leverage=2.0,
                tp_sl_override={
                    "tp1_pct": tp1_pct,
                    "tp2_pct": tp2_pct,
                    "sl_pct": sl_pct,
                },
            )

            await backtest.run_backtest(symbol, df, btc_df, days=days)
            metrics = backtest.calculate_metrics()

            result = {
                "symbol": symbol,
                "total_trades": metrics.get("total_trades", 0),
                "win_rate": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "total_pnl": metrics.get("total_pnl", 0.0),
                "total_pnl_pct": metrics.get("total_return", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            }
            portfolio_results.append(result)

            total_trades += result["total_trades"]
            total_pnl += result["total_pnl"]
            if result["total_trades"] > 0:
                wins = int(result["total_trades"] * result["win_rate"] / 100.0)
                total_winning_trades += wins
                total_losing_trades += result["total_trades"] - wins

            logger.info(
                "  ✅ %s: %d сделок, WR: %.2f%%, PF: %.2f, PnL: %.2f USDT",
                symbol,
                result["total_trades"],
                result["win_rate"],
                result["profit_factor"],
                result["total_pnl"],
            )
        except Exception as exc:
            logger.error("❌ Ошибка бектеста для %s: %s", symbol, exc)
            portfolio_results.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                    "total_pnl": 0.0,
                }
            )

    # Агрегированные метрики портфеля (по аналогии с финальным годовым бектестом)
    portfolio_win_rate = (total_winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
    capital = 10000.0 * max(len(symbols), 1)
    total_pnl_pct = (total_pnl / capital * 100.0) if capital > 0 else 0.0

    portfolio_summary: Dict[str, Any] = {
        "symbols": symbols,
        "total_symbols": len(symbols),
        "total_trades": total_trades,
        "total_winning_trades": total_winning_trades,
        "total_losing_trades": total_losing_trades,
        "portfolio_win_rate": portfolio_win_rate,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "results_by_symbol": portfolio_results,
    }

    return portfolio_summary, portfolio_results


async def main() -> None:
    """Главная функция грид-поиска TP/SL для TOP-10 SOL монет."""
    # Сетка параметров (оставляем разумно компактной, чтобы не перегружать API)
    tp1_grid = [1.5, 2.0, 2.5]
    tp2_grid = [3.0, 4.0, 5.0]
    sl_grid = [1.5, 2.0, 2.5]

    all_results: List[Dict[str, Any]] = []

    for sl_pct in sl_grid:
        for tp1_pct in tp1_grid:
            for tp2_pct in tp2_grid:
                # Простая защита от абсурдных конфигураций
                if tp2_pct <= tp1_pct:
                    continue

                summary, _ = await run_portfolio_with_params(
                    TOP10_SOL_PORTFOLIO,
                    tp1_pct=tp1_pct,
                    tp2_pct=tp2_pct,
                    sl_pct=sl_pct,
                    days=365,
                )
                if not summary:
                    continue

                combo_result: Dict[str, Any] = {
                    "tp1_pct": tp1_pct,
                    "tp2_pct": tp2_pct,
                    "sl_pct": sl_pct,
                    "total_trades": summary["total_trades"],
                    "portfolio_win_rate": summary["portfolio_win_rate"],
                    "total_pnl": summary["total_pnl"],
                    "total_pnl_pct": summary["total_pnl_pct"],
                }
                all_results.append(combo_result)

    if not all_results:
        logger.error("❌ Не удалось получить результаты грид-поиска")
        return

    # Сортируем комбинации по доходности портфеля
    all_results_sorted = sorted(all_results, key=lambda r: r["total_pnl_pct"], reverse=True)

    logger.info("")
    logger.info("📊 ТОП-10 комбинаций TP1/TP2/SL по доходности портфеля:")
    logger.info("=" * 80)
    for res in all_results_sorted[:10]:
        logger.info(
            "TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%% | trades=%d, WR=%.2f%%, PnL=%.2f USDT, PnL%%=%.2f%%",
            res["tp1_pct"],
            res["tp2_pct"],
            res["sl_pct"],
            res["total_trades"],
            res["portfolio_win_rate"],
            res["total_pnl"],
            res["total_pnl_pct"],
        )

    # Сохраняем полный отчёт в JSON
    output_file = (
        PROJECT_ROOT
        / "data"
        / "reports"
        / f"tp_sl_grid_search_top10_sol_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(all_results_sorted, f, indent=2, ensure_ascii=False)

    logger.info("💾 Результаты грид-поиска сохранены в %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())
