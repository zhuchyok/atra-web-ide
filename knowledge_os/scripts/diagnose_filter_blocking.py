#!/usr/bin/env python3
"""
Диагностика фильтров для 12 монет без сделок
Помогает понять, какие фильтры блокируют сигналы
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 12 монет без сделок
PROBLEM_SYMBOLS = [
    "NEIROUSDT", "SOLUSDT", "SUIUSDT", "POLUSDT", "LINKUSDT", "PENGUUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "CRVUSDT", "OPUSDT"
]

# Ультра-мягкие параметры для тестирования
ULTRA_SOFT_PARAMS = {
    "rsi_oversold": 15,
    "rsi_overbought": 85,
    "ai_score_threshold": 2.0,
    "min_confidence": 55
}


def load_csv_data(symbol: str, data_dir: Path = None) -> pd.DataFrame:
    """Загружает данные из CSV файла"""
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    csv_file = data_dir / f"{symbol}.csv"
    df = pd.read_csv(csv_file)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    else:
        df.index = pd.to_datetime(df.index)
    
    return df


async def diagnose_symbol_filters(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Диагностирует, какие фильтры блокируют сигналы"""
    from src.core.config import SYMBOL_SPECIFIC_CONFIG
    
    original_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, {}).copy()
    
    # Устанавливаем ультра-мягкие параметры
    test_params = {
        "optimal_rsi_oversold": int(params["rsi_oversold"]),
        "optimal_rsi_overbought": int(params["rsi_overbought"]),
        "ai_score_threshold": params["ai_score_threshold"],
        "min_confidence": int(params["min_confidence"]),
        "soft_volume_ratio": 1.0,  # Ослабляем volume фильтр
        "position_size_multiplier": 1.0,
        "filter_mode": "soft"
    }
    
    SYMBOL_SPECIFIC_CONFIG[symbol] = test_params.copy()
    
    # Создаем бектест с диагностикой
    backtest = AdvancedBacktest(
        initial_balance=10000.0,
        risk_per_trade=2.0,
        leverage=2.0
    )
    
    backtest.btc_df = btc_df
    backtest.eth_df = load_csv_data("ETHUSDT")
    backtest.sol_df = load_csv_data("SOLUSDT")
    
    if hasattr(backtest, '_symbol_params_cache'):
        backtest._symbol_params_cache.clear()
    
    # Включаем диагностику (если есть такая возможность)
    # Пока просто запускаем бектест
    await backtest.run_backtest(symbol, df, btc_df, days=365)
    
    metrics = backtest.calculate_metrics()
    
    # Восстанавливаем оригинальные параметры
    if original_params:
        SYMBOL_SPECIFIC_CONFIG[symbol] = original_params
    elif symbol in SYMBOL_SPECIFIC_CONFIG:
        del SYMBOL_SPECIFIC_CONFIG[symbol]
    
    return {
        "symbol": symbol,
        "total_trades": metrics.get("total_trades", 0),
        "win_rate": metrics.get("win_rate", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "total_pnl": metrics.get("total_pnl", 0.0),
        "parameters_used": params
    }


async def main():
    """Главная функция диагностики"""
    logger.info("🔍 ДИАГНОСТИКА ФИЛЬТРОВ ДЛЯ 12 МОНЕТ БЕЗ СДЕЛОК")
    logger.info("="*80)
    
    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    btc_df = load_csv_data("BTCUSDT", data_dir)
    
    results = {}
    
    for symbol in PROBLEM_SYMBOLS:
        logger.info("🔍 Диагностируем %s...", symbol)
        
        df = load_csv_data(symbol, data_dir)
        if df is None:
            logger.warning("⚠️ Данные для %s не найдены", symbol)
            continue
        
        result = await diagnose_symbol_filters(symbol, df, btc_df, ULTRA_SOFT_PARAMS)
        results[symbol] = result
        
        if result["total_trades"] > 0:
            logger.info("  ✅ С ультра-мягкими параметрами: %d сделок, PnL: %.2f USDT", 
                       result["total_trades"], result["total_pnl"])
        else:
            logger.warning("  ⚠️ Даже с ультра-мягкими параметрами: 0 сделок")
    
    # Сохраняем результаты
    output_file = PROJECT_ROOT / "data" / "reports" / f"filter_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Выводим результаты
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ДИАГНОСТИКИ:")
    print("="*80)
    
    unlocked_count = 0
    still_blocked = []
    
    for symbol, result in results.items():
        trades = result.get("total_trades", 0)
        if trades > 0:
            unlocked_count += 1
            print(f"\n✅ {symbol}: {trades} сделок, PnL: {result.get('total_pnl', 0):.2f} USDT")
        else:
            still_blocked.append(symbol)
            print(f"\n❌ {symbol}: Все еще 0 сделок (блокируется другими фильтрами)")
    
    print("\n" + "="*80)
    print(f"📈 Разблокировано: {unlocked_count}/{len(PROBLEM_SYMBOLS)} монет")
    print(f"❌ Все еще заблокировано: {len(still_blocked)} монет")
    
    if still_blocked:
        print("\n💡 Для заблокированных монет нужно:")
        print("   1. Проверить другие фильтры (Volume, EMA, BB, MTF)")
        print("   2. Рассмотреть отключение некоторых фильтров")
        print("   3. Попробовать другие стратегии")
    
    print("="*80)
    logger.info("💾 Результаты сохранены в %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())

