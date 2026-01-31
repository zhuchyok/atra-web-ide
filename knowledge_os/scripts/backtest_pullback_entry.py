#!/usr/bin/env python3
"""
Бэктест новой логики входа на откате (Pullback Entry)
Сравнение: старая логика (EMA кроссовер) vs новая логика (вход на откате)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest
from data.historical_data_loader import HistoricalDataLoader
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# TOP-10 SOL портфель
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
BACKTEST_DAYS = 30


async def run_backtest_with_entry_logic(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    use_pullback_entry: bool = False,
) -> Dict[str, Any]:
    """
    Запускает бэктест для одного символа с указанной логикой входа
    
    Args:
        symbol: Торговый символ
        start_date: Начальная дата
        end_date: Конечная дата
        use_pullback_entry: Использовать ли новую логику входа на откате
    
    Returns:
        Dict с результатами бэктеста
    """
    try:
        logger.info("📊 Бэктест %s: %s -> %s (Pullback Entry: %s)",
                   symbol, start_date.date(), end_date.date(), "ВКЛ" if use_pullback_entry else "ВЫКЛ")
        
        # Устанавливаем переменную окружения для логики входа
        if use_pullback_entry:
            os.environ["USE_PULLBACK_ENTRY"] = "true"
        else:
            os.environ.pop("USE_PULLBACK_ENTRY", None)
        
        # Перезагружаем config для применения изменений
        import importlib
        import config
        importlib.reload(config)
        
        # Загружаем исторические данные
        async with HistoricalDataLoader(exchange="binance") as loader:
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
            
            # Загружаем данные BTC
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
    Запускает сравнительный бэктест: старая логика vs новая логика входа
    """
    logger.info("🚀 ЗАПУСК БЭКТЕСТА: Сравнение логики входа")
    logger.info("=" * 70)
    logger.info("Портфель: TOP-10 SOL (%d монет)", len(TOP10_SOL_PORTFOLIO))
    logger.info("Период: последние %d дней", BACKTEST_DAYS)
    logger.info("Начальный баланс: %.2f USDT", INITIAL_BALANCE)
    logger.info("")
    logger.info("Сравнение:")
    logger.info("  • Старая логика: EMA кроссовер")
    logger.info("  • Новая логика: Вход на откате к поддержке/сопротивлению")
    logger.info("")
    
    # Определяем даты
    end_date = get_utc_now()
    start_date = end_date - timedelta(days=BACKTEST_DAYS)
    
    logger.info("📅 Период: %s -> %s", start_date.date(), end_date.date())
    logger.info("")
    
    # Результаты для старой логики (EMA кроссовер)
    logger.info("📊 ЭТАП 1: Бэктест СТАРОЙ логики (EMA кроссовер)")
    logger.info("-" * 70)
    old_logic_results = {}
    
    for symbol in TOP10_SOL_PORTFOLIO:
        result = await run_backtest_with_entry_logic(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_pullback_entry=False,
        )
        old_logic_results[symbol] = result
        
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
    logger.info("📊 ЭТАП 2: Бэктест НОВОЙ логики (Pullback Entry)")
    logger.info("-" * 70)
    new_logic_results = {}
    
    for symbol in TOP10_SOL_PORTFOLIO:
        result = await run_backtest_with_entry_logic(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_pullback_entry=True,
        )
        new_logic_results[symbol] = result
        
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
        
        # Максимальная просадка
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
    
    old_agg = aggregate_results(old_logic_results)
    new_agg = aggregate_results(new_logic_results)
    
    # Сравнение
    logger.info("")
    logger.info("=" * 70)
    logger.info("📈 СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
    logger.info("=" * 70)
    logger.info("")
    logger.info("СТАРАЯ ЛОГИКА (EMA кроссовер):")
    logger.info("  • Всего сделок: %d", old_agg["total_trades"])
    logger.info("  • Общий PnL: %.2f USDT (%.2f%%)", old_agg["total_pnl"], old_agg["total_pnl_pct"])
    logger.info("  • Win Rate: %.1f%%", old_agg["win_rate"])
    logger.info("  • Средний Sharpe: %.2f", old_agg["avg_sharpe_ratio"])
    logger.info("  • Средний Sortino: %.2f", old_agg["avg_sortino_ratio"])
    logger.info("  • Max Drawdown: %.2f%%", old_agg["max_drawdown_pct"])
    logger.info("  • Средний Profit Factor: %.2f", old_agg["avg_profit_factor"])
    logger.info("")
    logger.info("НОВАЯ ЛОГИКА (Pullback Entry):")
    logger.info("  • Всего сделок: %d", new_agg["total_trades"])
    logger.info("  • Общий PnL: %.2f USDT (%.2f%%)", new_agg["total_pnl"], new_agg["total_pnl_pct"])
    logger.info("  • Win Rate: %.1f%%", new_agg["win_rate"])
    logger.info("  • Средний Sharpe: %.2f", new_agg["avg_sharpe_ratio"])
    logger.info("  • Средний Sortino: %.2f", new_agg["avg_sortino_ratio"])
    logger.info("  • Max Drawdown: %.2f%%", new_agg["max_drawdown_pct"])
    logger.info("  • Средний Profit Factor: %.2f", new_agg["avg_profit_factor"])
    logger.info("")
    logger.info("ИЗМЕНЕНИЯ:")
    trades_diff = new_agg["total_trades"] - old_agg["total_trades"]
    pnl_diff = new_agg["total_pnl"] - old_agg["total_pnl"]
    pnl_pct_diff = new_agg["total_pnl_pct"] - old_agg["total_pnl_pct"]
    wr_diff = new_agg["win_rate"] - old_agg["win_rate"]
    sharpe_diff = new_agg["avg_sharpe_ratio"] - old_agg["avg_sharpe_ratio"]
    sortino_diff = new_agg["avg_sortino_ratio"] - old_agg["avg_sortino_ratio"]
    pf_diff = new_agg["avg_profit_factor"] - old_agg["avg_profit_factor"]
    
    logger.info("  • Сделок: %+d (%+.1f%%)", trades_diff, (trades_diff / old_agg["total_trades"] * 100) if old_agg["total_trades"] > 0 else 0)
    logger.info("  • PnL: %+.2f USDT (%+.2f%%)", pnl_diff, pnl_pct_diff)
    logger.info("  • Win Rate: %+.1f%%", wr_diff)
    logger.info("  • Sharpe: %+.2f", sharpe_diff)
    logger.info("  • Sortino: %+.2f", sortino_diff)
    logger.info("  • Profit Factor: %+.2f", pf_diff)
    logger.info("")
    
    # Сохраняем результаты
    report = {
        "backtest_date": get_utc_now().isoformat(),
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
        "old_logic": {
            "name": "EMA Crossover",
            "aggregated": old_agg,
            "by_symbol": old_logic_results,
        },
        "new_logic": {
            "name": "Pullback Entry",
            "aggregated": new_agg,
            "by_symbol": new_logic_results,
        },
        "comparison": {
            "trades_diff": trades_diff,
            "trades_diff_pct": (trades_diff / old_agg["total_trades"] * 100) if old_agg["total_trades"] > 0 else 0,
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
    
    timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"backtest_pullback_entry_{timestamp}.json"
    
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info("✅ Отчёт сохранён: %s", report_file)
    
    return report


if __name__ == "__main__":
    asyncio.run(run_comparison_backtest())

