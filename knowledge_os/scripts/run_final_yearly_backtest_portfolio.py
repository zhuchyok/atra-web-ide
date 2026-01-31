#!/usr/bin/env python3
"""
Финальный годовой бектест на выбранном портфеле из 14 монет SOL_HIGH
Включает все исправления: TP1 trailing SL, breakeven SL
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Финальный портфель: топ-14 прибыльных монет из SOL_HIGH
FINAL_PORTFOLIO = [
    "BONKUSDT",
    "WIFUSDT",
    "NEIROUSDT",
    "SOLUSDT",
    "SUIUSDT",
    "POLUSDT",
    "LINKUSDT",
    "PENGUUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "CRVUSDT",
    "OPUSDT"
]


def load_csv_data(symbol: str, data_dir: Path = None) -> Optional[pd.DataFrame]:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    csv_file = data_dir / f"{symbol}.csv"
    
    if not csv_file.exists():
        logger.warning("⚠️ Файл не найден: %s", csv_file)
        return None
    
    try:
        df = pd.read_csv(csv_file)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif df.index.name == 'timestamp' or df.index.dtype == 'object':
            df.index = pd.to_datetime(df.index)
        
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Не все необходимые колонки найдены для %s", symbol)
            return None
        
        return df
    
    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def run_portfolio_backtest(
    symbols: List[str],
    days: int = 365
) -> Dict[str, Any]:
    """
    Запускает годовой бектест на портфеле монет
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    # Загружаем данные для базовых активов (для фильтров)
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)
    
    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL")
        return {}
    
    # Результаты по каждой монете
    portfolio_results = []
    total_trades = 0
    total_pnl = 0.0
    total_winning_trades = 0
    total_losing_trades = 0
    
    logger.info("🚀 Запуск финального годового бектеста на портфеле из %d монет", len(symbols))
    logger.info("="*80)
    
    for i, symbol in enumerate(symbols, 1):
        logger.info("[%d/%d] Тестируем %s...", i, len(symbols), symbol)
        
        df = load_csv_data(symbol, data_dir)
        if df is None:
            logger.warning("⚠️ Пропускаем %s (данные не найдены)", symbol)
            continue
        
        try:
            backtest = AdvancedBacktest(
                initial_balance=10000.0,
                risk_per_trade=2.0,
                leverage=2.0
            )
            
            backtest.btc_df = btc_df
            backtest.eth_df = eth_df
            backtest.sol_df = sol_df
            
            await backtest.run_backtest(symbol, df, btc_df, days)
            
            metrics = backtest.calculate_metrics()
            
            result = {
                "symbol": symbol,
                "total_trades": metrics.get("total_trades", 0),
                "win_rate": metrics.get("win_rate", 0.0),
                "profit_factor": metrics.get("profit_factor", 0.0),
                "total_pnl": metrics.get("total_pnl", 0.0),
                "total_pnl_pct": metrics.get("total_pnl_pct", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "sortino_ratio": metrics.get("sortino_ratio", 0.0),
                "avg_win": metrics.get("avg_win", 0.0),
                "avg_loss": metrics.get("avg_loss", 0.0),
            }
            
            portfolio_results.append(result)
            
            total_trades += result["total_trades"]
            total_pnl += result["total_pnl"]
            
            if result["total_trades"] > 0:
                total_winning_trades += int(result["total_trades"] * result["win_rate"] / 100)
                total_losing_trades += result["total_trades"] - int(result["total_trades"] * result["win_rate"] / 100)
            
            logger.info(
                "  ✅ %s: %d сделок, WR: %.2f%%, PF: %.2f, PnL: %.2f USDT",
                symbol,
                result["total_trades"],
                result["win_rate"],
                result["profit_factor"],
                result["total_pnl"]
            )
            
        except Exception as e:
            logger.error("❌ Ошибка бектеста для %s: %s", symbol, e)
            portfolio_results.append({
                "symbol": symbol,
                "error": str(e),
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
            })
    
    # Агрегированные метрики портфеля
    portfolio_win_rate = (total_winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    portfolio_summary = {
        "portfolio_symbols": symbols,
        "total_symbols": len(symbols),
        "successful_backtests": len([r for r in portfolio_results if "error" not in r]),
        "total_trades": total_trades,
        "total_winning_trades": total_winning_trades,
        "total_losing_trades": total_losing_trades,
        "portfolio_win_rate": portfolio_win_rate,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / (10000.0 * len(symbols)) * 100) if len(symbols) > 0 else 0.0,
        "results_by_symbol": portfolio_results,
        "backtest_date": datetime.now().isoformat(),
        "days": days
    }
    
    # Сохраняем результаты
    output_file = PROJECT_ROOT / "data" / "reports" / f"final_portfolio_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(portfolio_summary, f, indent=2, ensure_ascii=False)
    
    logger.info("💾 Результаты сохранены в %s", output_file)
    
    return portfolio_summary


async def main():
    """Главная функция"""
    logger.info("🎯 ФИНАЛЬНЫЙ ГОДОВОЙ БЕКТЕСТ НА ПОРТФЕЛЕ SOL_HIGH")
    logger.info("="*80)
    logger.info("Портфель: %d монет", len(FINAL_PORTFOLIO))
    logger.info("Монеты: %s", ", ".join(FINAL_PORTFOLIO))
    logger.info("="*80)
    logger.info("")
    
    results = await run_portfolio_backtest(FINAL_PORTFOLIO, days=365)
    
    if results:
        print("\n" + "="*80)
        print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ ПОРТФЕЛЯ:")
        print("="*80)
        print(f"Монет в портфеле: {results['total_symbols']}")
        print(f"Успешных бектестов: {results['successful_backtests']}")
        print(f"Всего сделок: {results['total_trades']}")
        print(f"Win Rate портфеля: {results['portfolio_win_rate']:.2f}%")
        print(f"Общий PnL: {results['total_pnl']:.2f} USDT")
        print(f"Общий PnL %: {results['total_pnl_pct']:.2f}%")
        print("\n" + "-"*80)
        print("Результаты по монетам:")
        print("-"*80)
        
        for result in sorted(results['results_by_symbol'], key=lambda x: x.get('total_pnl', 0), reverse=True):
            if 'error' not in result:
                print(
                    f"{result['symbol']:12s} | "
                    f"Сделок: {result['total_trades']:3d} | "
                    f"WR: {result['win_rate']:5.2f}% | "
                    f"PF: {result['profit_factor']:5.2f} | "
                    f"PnL: {result['total_pnl']:8.2f} USDT"
                )
            else:
                print(f"{result['symbol']:12s} | ❌ Ошибка: {result.get('error', 'Unknown')}")


if __name__ == "__main__":
    asyncio.run(main())

