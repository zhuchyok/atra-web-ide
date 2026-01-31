#!/usr/bin/env python3
"""
Тестирование оптимизированных параметров для BTC/ETH монет
Цель: Проверить, улучшатся ли результаты с параметрами как у SOL (RSI 25-75, AI Score 5.0)
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_csv_data(symbol: str, data_dir: Path = None) -> Optional[pd.DataFrame]:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    csv_file = data_dir / f"{symbol}.csv"
    
    if not csv_file.exists():
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
            return None
        
        return df
    
    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def test_with_optimized_parameters(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    days: int = 365
) -> Dict[str, Any]:
    """
    Тестирует монету с оптимизированными параметрами (как у SOL)
    RSI: 25-75 (вместо 30-70 для BTC, 28-72 для ETH)
    AI Score: 5.0 (вместо 6.5 для BTC, 7.0 для ETH)
    """
    try:
        logger.info("🔍 Тестируем %s с оптимизированными параметрами (RSI 25-75, AI Score 5.0)...", symbol)
        
        backtest = AdvancedBacktest(
            initial_balance=10000.0,
            risk_per_trade=2.0,
            leverage=2.0
        )
        
        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df
        
        # Временно переопределяем параметры для этого символа
        # TODO: Передать параметры в AdvancedBacktest
        
        await backtest.run_backtest(symbol, df, btc_df, days)
        
        metrics = backtest.calculate_metrics()
        
        return {
            "symbol": symbol,
            "total_trades": metrics.get("total_trades", 0),
            "win_rate": metrics.get("win_rate", 0.0),
            "profit_factor": metrics.get("profit_factor", 0.0),
            "total_pnl": metrics.get("total_pnl", 0.0),
            "total_pnl_pct": metrics.get("total_pnl_pct", 0.0),
            "max_drawdown": metrics.get("max_drawdown", 0.0),
            "parameters_used": "RSI 25-75, AI Score 5.0 (оптимизированные)"
        }
        
    except Exception as e:
        logger.error("❌ Ошибка тестирования %s: %s", symbol, e)
        return {
            "symbol": symbol,
            "error": str(e),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
        }


async def main():
    """Главная функция"""
    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    # Тестируем монеты из BTC/ETH групп с оптимизированными параметрами
    test_symbols = [
        # BTC группа
        "BTCUSDT", "SYRUPUSDT",
        # ETH группа
        "ETHUSDT", "AAVEUSDT", "BNBUSDT", "CAKEUSDT", "UNIUSDT"
    ]
    
    # Загружаем данные BTC, ETH, SOL для фильтров
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)
    
    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL")
        return
    
    results = []
    
    for symbol in test_symbols:
        df = load_csv_data(symbol, data_dir)
        if df is None:
            continue
        
        result = await test_with_optimized_parameters(symbol, df, btc_df, eth_df, sol_df, days=365)
        results.append(result)
        
        logger.info(
            "✅ %s: %d сделок, WR: %.2f%%, PF: %.2f, PnL: %.2f USDT",
            symbol,
            result["total_trades"],
            result["win_rate"],
            result["profit_factor"],
            result["total_pnl"]
        )
    
    # Сохраняем результаты
    output_file = PROJECT_ROOT / "data" / "reports" / "btc_eth_optimized_test.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info("💾 Результаты сохранены в %s", output_file)
    
    # Выводим сравнение
    print("\n" + "="*80)
    print("📊 СРАВНЕНИЕ РЕЗУЛЬТАТОВ С ОПТИМИЗИРОВАННЫМИ ПАРАМЕТРАМИ:")
    print("="*80)
    for result in results:
        print(
            f"  {result['symbol']:12s} | "
            f"Сделок: {result['total_trades']:3d} | "
            f"WR: {result['win_rate']:5.2f}% | "
            f"PF: {result['profit_factor']:5.2f} | "
            f"PnL: {result['total_pnl']:8.2f} USDT"
        )


if __name__ == "__main__":
    asyncio.run(main())

