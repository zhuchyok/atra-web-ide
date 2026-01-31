#!/usr/bin/env python3
"""
Бэктест всех фильтров: Фазы 1, 2, 3
Сравнение: baseline vs с всеми фильтрами (Dominance + Interest Zone + Fibonacci + Volume Imbalance + Dynamic TP/SL)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest
from data.historical_data_loader import HistoricalDataLoader
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# TOP-10 SOL портфель (из config.py)
TOP10_SOL_PORTFOLIO = [
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

# Параметры бэктеста
INITIAL_BALANCE = 10000.0
RISK_PER_TRADE = 2.0
LEVERAGE = 2.0
BACKTEST_DAYS = 30  # 30 дней для MVP


async def run_backtest_with_all_filters(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    use_all_filters: bool = False,
) -> Dict[str, Any]:
    """
    Запускает бэктест для одного символа с указанными фильтрами
    
    Args:
        symbol: Торговый символ
        start_date: Начальная дата
        end_date: Конечная дата
        use_all_filters: Использовать ли все фильтры (Фазы 1, 2, 3)
    
    Returns:
        Dict с результатами бэктеста
    """
    try:
        logger.info("📊 Бэктест %s: %s -> %s (все фильтры: %s)",
                   symbol, start_date.date(), end_date.date(), "ВКЛ" if use_all_filters else "ВЫКЛ")
        
        # Временно устанавливаем переменные окружения для фильтров
        if use_all_filters:
            os.environ["USE_DOMINANCE_TREND_FILTER"] = "true"
            os.environ["USE_INTEREST_ZONE_FILTER"] = "true"
            os.environ["USE_FIBONACCI_ZONE_FILTER"] = "true"
            os.environ["USE_VOLUME_IMBALANCE_FILTER"] = "true"
            os.environ["USE_DYNAMIC_TP_SL_FROM_ZONES"] = "true"
        else:
            os.environ.pop("USE_DOMINANCE_TREND_FILTER", None)
            os.environ.pop("USE_INTEREST_ZONE_FILTER", None)
            os.environ.pop("USE_FIBONACCI_ZONE_FILTER", None)
            os.environ.pop("USE_VOLUME_IMBALANCE_FILTER", None)
            os.environ.pop("USE_DYNAMIC_TP_SL_FROM_ZONES", None)
        
        # Перезагружаем config для применения изменений
        import importlib
        import config
        importlib.reload(config)
        
        # Загружаем исторические данные
        async with HistoricalDataLoader(exchange="binance") as loader:
            # Загружаем данные для символа
            symbol_data = await loader.fetch_ohlcv(
                symbol=symbol,
                interval="1h",
                days=BACKTEST_DAYS
            )
            
            if symbol_data is None or len(symbol_data) == 0:
                logger.warning("⚠️ Недостаточно данных для %s", symbol)
                return {
                    "symbol": symbol,
                    "error": "Недостаточно данных",
                    "trades_count": 0,
                    "total_pnl": 0.0,
                    "win_rate": 0.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "max_drawdown": 0.0,
                }
            
            # Конвертируем в DataFrame
            df = pd.DataFrame(symbol_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Загружаем данные BTC (обязательно для фильтров)
            btc_data = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=BACKTEST_DAYS)
            if btc_data is None or len(btc_data) == 0:
                logger.warning("⚠️ Не удалось загрузить данные BTCUSDT")
                return {
                    "symbol": symbol,
                    "error": "Не удалось загрузить BTC данные",
                    "trades_count": 0,
                    "total_pnl": 0.0,
                    "win_rate": 0.0,
                    "sharpe_ratio": 0.0,
                    "sortino_ratio": 0.0,
                    "max_drawdown": 0.0,
                }
            
            btc_df = pd.DataFrame(btc_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            btc_df['timestamp'] = pd.to_datetime(btc_df['timestamp'], unit='ms')
            btc_df.set_index('timestamp', inplace=True)
        
        if len(df) < 100:
            logger.warning("⚠️ Недостаточно данных для %s (%d свечей)", symbol, len(df))
            return {
                "symbol": symbol,
                "error": f"Недостаточно данных ({len(df)} свечей)",
                "trades_count": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "max_drawdown": 0.0,
            }
        
        # Создаем экземпляр бэктеста
        backtest = AdvancedBacktest(
            initial_balance=INITIAL_BALANCE,
            risk_per_trade=RISK_PER_TRADE,
            leverage=LEVERAGE,
        )
        
        # Запускаем бэктест
        await backtest.run_backtest(
            symbol=symbol,
            df=df,
            btc_df=btc_df,
            days=BACKTEST_DAYS,
        )
        
        # Получаем метрики
        metrics = backtest.calculate_metrics()
        
        # Извлекаем метрики
        total_trades = metrics.get("total_trades", 0)
        win_rate = metrics.get("win_rate", 0.0)
        total_pnl = metrics.get("total_pnl", 0.0)
        total_pnl_pct = metrics.get("total_pnl_pct", 0.0)
        sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
        sortino_ratio = metrics.get("sortino_ratio", 0.0)
        max_drawdown = metrics.get("max_drawdown", 0.0)
        max_drawdown_pct = metrics.get("max_drawdown_pct", 0.0)
        profit_factor = metrics.get("profit_factor", 0.0)
        final_balance = backtest.current_balance
        
        winning_trades = metrics.get("winning_trades", 0)
        losing_trades = metrics.get("losing_trades", 0)
        
        return {
            "symbol": symbol,
            "trades_count": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "final_balance": final_balance,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "max_drawdown": max_drawdown,
            "max_drawdown_pct": max_drawdown_pct,
            "profit_factor": profit_factor,
        }
        
    except Exception as e:
        logger.error("❌ Ошибка бэктеста для %s: %s", symbol, e, exc_info=True)
        return {
            "symbol": symbol,
            "error": str(e),
            "trades_count": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
        }


async def run_comparison_backtest():
    """
    Запускает сравнительный бэктест: baseline vs со всеми фильтрами
    """
    logger.info("🚀 ЗАПУСК БЭКТЕСТА: Все фильтры (Фазы 1, 2, 3)")
    logger.info("=" * 70)
    logger.info("Портфель: TOP-10 SOL (%d монет)", len(TOP10_SOL_PORTFOLIO))
    logger.info("Период: последние %d дней", BACKTEST_DAYS)
    logger.info("Начальный баланс: %.2f USDT", INITIAL_BALANCE)
    logger.info("Риск на сделку: %.1f%%", RISK_PER_TRADE)
    logger.info("Плечо: %.1fx", LEVERAGE)
    logger.info("")
    logger.info("Фильтры:")
    logger.info("  • DominanceTrendFilter (BTC доминация)")
    logger.info("  • InterestZoneFilter (зоны интереса)")
    logger.info("  • FibonacciZoneFilter (уровни Фибоначчи)")
    logger.info("  • VolumeImbalanceFilter (имбалансы объема)")
    logger.info("  • Dynamic TP/SL from Zones (динамические TP/SL)")
    logger.info("")
    
    # Определяем даты
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=BACKTEST_DAYS)
    
    logger.info("📅 Период: %s -> %s", start_date.date(), end_date.date())
    logger.info("")
    
    # Результаты для baseline (без фильтров)
    logger.info("📊 ЭТАП 1: Бэктест БЕЗ фильтров (baseline)")
    logger.info("-" * 70)
    baseline_results = {}
    
    for symbol in TOP10_SOL_PORTFOLIO:
        result = await run_backtest_with_all_filters(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_all_filters=False,
        )
        baseline_results[symbol] = result
        
        if "error" not in result:
            logger.info(
                "  %s: %d сделок, PnL: %.2f USDT (%.2f%%), WR: %.1f%%, Sharpe: %.2f",
                symbol,
                result["trades_count"],
                result["total_pnl"],
                result["total_pnl_pct"],
                result["win_rate"],
                result["sharpe_ratio"],
            )
        else:
            logger.warning("  %s: Ошибка - %s", symbol, result.get("error", "Unknown"))
    
    logger.info("")
    logger.info("📊 ЭТАП 2: Бэктест СО ВСЕМИ ФИЛЬТРАМИ (Фазы 1, 2, 3)")
    logger.info("-" * 70)
    filtered_results = {}
    
    for symbol in TOP10_SOL_PORTFOLIO:
        result = await run_backtest_with_all_filters(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_all_filters=True,
        )
        filtered_results[symbol] = result
        
        if "error" not in result:
            logger.info(
                "  %s: %d сделок, PnL: %.2f USDT (%.2f%%), WR: %.1f%%, Sharpe: %.2f",
                symbol,
                result["trades_count"],
                result["total_pnl"],
                result["total_pnl_pct"],
                result["win_rate"],
                result["sharpe_ratio"],
            )
        else:
            logger.warning("  %s: Ошибка - %s", symbol, result.get("error", "Unknown"))
    
    # Агрегируем результаты
    def aggregate_results(results: Dict[str, Dict]) -> Dict[str, Any]:
        """Агрегирует результаты по всем символам"""
        total_trades = sum(r.get("trades_count", 0) for r in results.values() if "error" not in r)
        total_pnl = sum(r.get("total_pnl", 0) for r in results.values() if "error" not in r)
        total_pnl_pct = sum(r.get("total_pnl_pct", 0) for r in results.values() if "error" not in r)
        
        winning_trades = sum(r.get("winning_trades", 0) for r in results.values() if "error" not in r)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        # Средний Sharpe (взвешенный по количеству сделок)
        sharpe_values = [
            r.get("sharpe_ratio", 0) * r.get("trades_count", 0)
            for r in results.values()
            if "error" not in r and r.get("trades_count", 0) > 0
        ]
        avg_sharpe = sum(sharpe_values) / total_trades if total_trades > 0 else 0.0
        
        # Средний Sortino
        sortino_values = [
            r.get("sortino_ratio", 0) * r.get("trades_count", 0)
            for r in results.values()
            if "error" not in r and r.get("trades_count", 0) > 0
        ]
        avg_sortino = sum(sortino_values) / total_trades if total_trades > 0 else 0.0
        
        # Максимальная просадка (максимум из всех символов)
        max_dd = max(
            (r.get("max_drawdown_pct", 0) for r in results.values() if "error" not in r),
            default=0.0
        )
        
        # Profit Factor (средний)
        profit_factors = [
            r.get("profit_factor", 0) for r in results.values()
            if "error" not in r and r.get("profit_factor", 0) > 0
        ]
        avg_profit_factor = sum(profit_factors) / len(profit_factors) if profit_factors else 0.0
        
        return {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "win_rate": win_rate,
            "avg_sharpe_ratio": avg_sharpe,
            "avg_sortino_ratio": avg_sortino,
            "max_drawdown_pct": max_dd,
            "avg_profit_factor": avg_profit_factor,
        }
    
    baseline_agg = aggregate_results(baseline_results)
    filtered_agg = aggregate_results(filtered_results)
    
    # Сравнение
    logger.info("")
    logger.info("=" * 70)
    logger.info("📈 СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    logger.info("=" * 70)
    logger.info("")
    logger.info("BASELINE (без фильтров):")
    logger.info("  • Всего сделок: %d", baseline_agg["total_trades"])
    logger.info("  • Общий PnL: %.2f USDT (%.2f%%)", baseline_agg["total_pnl"], baseline_agg["total_pnl_pct"])
    logger.info("  • Win Rate: %.1f%%", baseline_agg["win_rate"])
    logger.info("  • Средний Sharpe: %.2f", baseline_agg["avg_sharpe_ratio"])
    logger.info("  • Средний Sortino: %.2f", baseline_agg["avg_sortino_ratio"])
    logger.info("  • Max Drawdown: %.2f%%", baseline_agg["max_drawdown_pct"])
    logger.info("  • Средний Profit Factor: %.2f", baseline_agg["avg_profit_factor"])
    logger.info("")
    logger.info("СО ВСЕМИ ФИЛЬТРАМИ (Фазы 1, 2, 3):")
    logger.info("  • Всего сделок: %d", filtered_agg["total_trades"])
    logger.info("  • Общий PnL: %.2f USDT (%.2f%%)", filtered_agg["total_pnl"], filtered_agg["total_pnl_pct"])
    logger.info("  • Win Rate: %.1f%%", filtered_agg["win_rate"])
    logger.info("  • Средний Sharpe: %.2f", filtered_agg["avg_sharpe_ratio"])
    logger.info("  • Средний Sortino: %.2f", filtered_agg["avg_sortino_ratio"])
    logger.info("  • Max Drawdown: %.2f%%", filtered_agg["max_drawdown_pct"])
    logger.info("  • Средний Profit Factor: %.2f", filtered_agg["avg_profit_factor"])
    logger.info("")
    logger.info("ИЗМЕНЕНИЯ:")
    trades_diff = filtered_agg["total_trades"] - baseline_agg["total_trades"]
    pnl_diff = filtered_agg["total_pnl"] - baseline_agg["total_pnl"]
    pnl_pct_diff = filtered_agg["total_pnl_pct"] - baseline_agg["total_pnl_pct"]
    wr_diff = filtered_agg["win_rate"] - baseline_agg["win_rate"]
    sharpe_diff = filtered_agg["avg_sharpe_ratio"] - baseline_agg["avg_sharpe_ratio"]
    sortino_diff = filtered_agg["avg_sortino_ratio"] - baseline_agg["avg_sortino_ratio"]
    pf_diff = filtered_agg["avg_profit_factor"] - baseline_agg["avg_profit_factor"]
    
    logger.info("  • Сделок: %+d (%+.1f%%)", trades_diff, (trades_diff / baseline_agg["total_trades"] * 100) if baseline_agg["total_trades"] > 0 else 0)
    logger.info("  • PnL: %+.2f USDT (%+.2f%%)", pnl_diff, pnl_pct_diff)
    logger.info("  • Win Rate: %+.1f%%", wr_diff)
    logger.info("  • Sharpe: %+.2f", sharpe_diff)
    logger.info("  • Sortino: %+.2f", sortino_diff)
    logger.info("  • Profit Factor: %+.2f", pf_diff)
    logger.info("")
    
    # Сохраняем результаты
    report = {
        "backtest_date": datetime.utcnow().isoformat(),
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": BACKTEST_DAYS,
        },
        "parameters": {
            "initial_balance": INITIAL_BALANCE,
            "risk_per_trade": RISK_PER_TRADE,
            "leverage": LEVERAGE,
        },
        "filters_enabled": {
            "dominance_trend": True,
            "interest_zone": True,
            "fibonacci_zone": True,
            "volume_imbalance": True,
            "dynamic_tp_sl_from_zones": True,
        },
        "baseline": {
            "aggregated": baseline_agg,
            "by_symbol": baseline_results,
        },
        "with_all_filters": {
            "aggregated": filtered_agg,
            "by_symbol": filtered_results,
        },
        "comparison": {
            "trades_diff": trades_diff,
            "trades_diff_pct": (trades_diff / baseline_agg["total_trades"] * 100) if baseline_agg["total_trades"] > 0 else 0,
            "pnl_diff": pnl_diff,
            "pnl_diff_pct": pnl_pct_diff,
            "win_rate_diff": wr_diff,
            "sharpe_diff": sharpe_diff,
            "sortino_diff": sortino_diff,
            "profit_factor_diff": pf_diff,
        },
    }
    
    # Сохраняем в файл
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"backtest_all_filters_phases_2_3_{timestamp}.json"
    
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info("✅ Отчёт сохранён: %s", report_file)
    
    return report


if __name__ == "__main__":
    asyncio.run(run_comparison_backtest())

