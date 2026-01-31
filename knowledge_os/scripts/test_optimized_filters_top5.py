#!/usr/bin/env python3
"""Тестирование оптимизированных фильтров на топ-5 монетах за 3 месяца."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader
from scripts.run_advanced_backtest import AdvancedBacktest

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Топ-5 монет по капитализации
TOP_5_COINS = [
    "BTCUSDT",  # Bitcoin
    "ETHUSDT",  # Ethereum
    "BNBUSDT",  # Binance Coin
    "SOLUSDT",  # Solana
    "XRPUSDT",  # Ripple
]


async def run_backtest_for_symbol(
    backtest: AdvancedBacktest,
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: Optional[pd.DataFrame] = None,
    sol_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Запускает бэктест для одного символа."""
    try:
        logger.info(f"📊 Бэктест для {symbol} ({len(df)} свечей)")
        
        # Устанавливаем данные ETH и SOL для фильтров
        if eth_df is not None:
            backtest.eth_df = eth_df
        if sol_df is not None:
            backtest.sol_df = sol_df
        
        # Запускаем бэктест
        await backtest.run_backtest(symbol, df, btc_df, days=90)
        
        # Получаем метрики для этого символа
        metrics = backtest.calculate_metrics()
        
        # Подсчитываем статистику по сделкам для этого символа
        symbol_trades = [t for t in backtest.trades if t.get('symbol') == symbol]
        
        symbol_metrics = {
            'symbol': symbol,
            'total_trades': len(symbol_trades),
            'winning_trades': len([t for t in symbol_trades if t.get('pnl', 0) > 0]),
            'losing_trades': len([t for t in symbol_trades if t.get('pnl', 0) <= 0]),
            'total_pnl': sum(t.get('pnl', 0) for t in symbol_trades),
            'trades': symbol_trades,
        }
        
        if symbol_metrics['total_trades'] > 0:
            symbol_metrics['win_rate'] = (symbol_metrics['winning_trades'] / symbol_metrics['total_trades']) * 100
            wins = [t.get('pnl', 0) for t in symbol_trades if t.get('pnl', 0) > 0]
            losses = [t.get('pnl', 0) for t in symbol_trades if t.get('pnl', 0) <= 0]
            symbol_metrics['avg_win'] = sum(wins) / len(wins) if wins else 0
            symbol_metrics['avg_loss'] = sum(losses) / len(losses) if losses else 0
            symbol_metrics['profit_factor'] = abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else 0
        else:
            symbol_metrics['win_rate'] = 0
            symbol_metrics['avg_win'] = 0
            symbol_metrics['avg_loss'] = 0
            symbol_metrics['profit_factor'] = 0
        
        return symbol_metrics
        
    except Exception as e:
        logger.error(f"❌ Ошибка бэктеста для {symbol}: {e}", exc_info=True)
        return {
            'symbol': symbol,
            'error': str(e),
            'total_trades': 0,
        }


async def main():
    """Основная функция."""
    logger.info("🚀 Начало тестирования оптимизированных фильтров на топ-5 монетах")
    logger.info("📅 Период: 3 месяца")
    logger.info("🪙 Монеты: %s", ", ".join(TOP_5_COINS))
    
    # Создаем загрузчик данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        # Загружаем данные за 3 месяца (90 дней)
        logger.info("📥 Загрузка данных за 3 месяца...")
        days = 90
        
        data_dict = await loader.load_multiple_symbols(
            symbols=TOP_5_COINS,
            interval="1h",
            days=days,
        )
        
        # Фильтруем символы с достаточным количеством данных
        valid_data = {k: v for k, v in data_dict.items() if not v.empty and len(v) >= 200}
        logger.info("✅ Загружено данных для %d символов (из %d)", len(valid_data), len(TOP_5_COINS))
        
        if not valid_data:
            logger.error("❌ Нет данных для бэктеста!")
            return
        
        # Получаем данные BTC, ETH, SOL для фильтров
        btc_df = valid_data.get("BTCUSDT")
        eth_df = valid_data.get("ETHUSDT")
        sol_df = valid_data.get("SOLUSDT")
        
        if btc_df is None or btc_df.empty:
            logger.warning("⚠️ Данные BTC не найдены, используем первый доступный символ")
            btc_df = list(valid_data.values())[0] if valid_data else pd.DataFrame()
    
    # Создаем бэктест с оптимизированными параметрами
    logger.info("🧪 Создание бэктеста с оптимизированными фильтрами...")
    backtest = AdvancedBacktest(
        initial_balance=10000.0,
        risk_per_trade=2.0,
        leverage=2.0,
    )
    
    # Запускаем бэктест для каждого символа
    results_by_symbol: List[Dict[str, Any]] = []
    
    for symbol in TOP_5_COINS:
        if symbol not in valid_data:
            logger.warning(f"⚠️ Пропускаем {symbol} - нет данных")
            continue
        
        df = valid_data[symbol]
        if df.empty or len(df) < 200:
            logger.warning(f"⚠️ Пропускаем {symbol} - недостаточно данных ({len(df)} свечей)")
            continue
        
        symbol_results = await run_backtest_for_symbol(
            backtest, symbol, df, btc_df, eth_df, sol_df
        )
        results_by_symbol.append(symbol_results)
    
    # Генерируем общие метрики (даже если нет сделок, чтобы получить статистику по фильтрам)
    all_metrics = backtest.calculate_metrics()
    
    # Если метрики пустые (нет сделок), все равно получаем статистику по фильтрам
    if not all_metrics:
        all_metrics = {
            "filter_statistics": {
                "total_signals_checked": backtest.total_signals_checked,
                "filter_rejections": backtest.filter_rejections.copy(),
                "rejection_percentages": {}
            }
        }
        # Рассчитываем проценты отклонений
        if backtest.total_signals_checked > 0:
            for filter_name, count in backtest.filter_rejections.items():
                all_metrics["filter_statistics"]["rejection_percentages"][filter_name] = (count / backtest.total_signals_checked) * 100
    
    # Выводим результаты
    print("\n" + "=" * 100)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ОПТИМИЗИРОВАННЫХ ФИЛЬТРОВ")
    print("=" * 100)
    print(f"\n📅 Период: 3 месяца (90 дней)")
    print(f"🪙 Монеты: {', '.join(TOP_5_COINS)}")
    print(f"🔧 Фильтры: Оптимизированные (MACD 8/21/5, EMA 6/14/22, Volume 1.2, BB 18/1.8)")
    
    print(f"\n💰 ОБЩИЕ ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:")
    print(f"  Начальный баланс: {backtest.initial_balance:.2f} USDT")
    print(f"  Финальный баланс: {all_metrics.get('final_balance', backtest.current_balance):.2f} USDT")
    print(f"  Общий PnL: {all_metrics.get('total_pnl', 0):.2f} USDT ({all_metrics.get('total_return', 0):.2f}%)")
    print(f"  Максимальная прибыль: {all_metrics.get('max_profit', 0):.2f} USDT")
    print(f"  Максимальный убыток: {all_metrics.get('max_loss', 0):.2f} USDT")
    print(f"  Максимальная просадка: {all_metrics.get('max_drawdown', 0):.2f}%")
    
    print(f"\n📈 ОБЩАЯ СТАТИСТИКА СДЕЛОК:")
    print(f"  Всего сделок: {all_metrics.get('total_trades', 0)}")
    print(f"  Прибыльных: {all_metrics.get('winning_trades', 0)} ({all_metrics.get('win_rate', 0):.2f}%)")
    print(f"  Убыточных: {all_metrics.get('losing_trades', 0)}")
    print(f"  Средняя прибыль: {all_metrics.get('avg_win', 0):.2f} USDT")
    print(f"  Средний убыток: {all_metrics.get('avg_loss', 0):.2f} USDT")
    print(f"  Profit Factor: {all_metrics.get('profit_factor', 0):.2f}")
    
    print(f"\n📊 МЕТРИКИ РИСКА:")
    print(f"  Sharpe Ratio: {all_metrics.get('sharpe_ratio', 0):.2f}")
    print(f"  Sortino Ratio: {all_metrics.get('sortino_ratio', 0):.2f}")
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ПО МОНЕТАМ:")
    print("-" * 100)
    for symbol_result in results_by_symbol:
        symbol = symbol_result.get('symbol', 'UNKNOWN')
        total_trades = symbol_result.get('total_trades', 0)
        win_rate = symbol_result.get('win_rate', 0)
        total_pnl = symbol_result.get('total_pnl', 0)
        profit_factor = symbol_result.get('profit_factor', 0)
        
        print(f"\n  {symbol}:")
        print(f"    Сделок: {total_trades}")
        print(f"    Win Rate: {win_rate:.2f}%")
        print(f"    PnL: {total_pnl:.2f} USDT")
        print(f"    Profit Factor: {profit_factor:.2f}")
        
        if 'error' in symbol_result:
            print(f"    ⚠️ Ошибка: {symbol_result['error']}")
    
    # 🆕 Статистика по фильтрам
    filter_stats = all_metrics.get('filter_statistics', {})
    if filter_stats:
        print(f"\n🔍 СТАТИСТИКА БЛОКИРОВОК ПО ФИЛЬТРАМ:")
        print("-" * 100)
        total_checked = filter_stats.get('total_signals_checked', 0)
        rejections = filter_stats.get('filter_rejections', {})
        percentages = filter_stats.get('rejection_percentages', {})
        
        print(f"\n  Всего проверено сигналов: {total_checked}")
        print(f"\n  Блокировок по фильтрам:")
        
        # Сортируем по количеству блокировок
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
    
    # Сохраняем детальный отчет
    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = report_dir / f"optimized_filters_top5_3months_{timestamp}.json"
    
    report_data = {
        "backtest_info": {
            "start_date": (datetime.utcnow() - timedelta(days=days)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "symbols": TOP_5_COINS,
            "days": days,
            "initial_balance": backtest.initial_balance,
            "risk_per_trade": backtest.risk_per_trade,
            "leverage": backtest.leverage,
            "filters_version": "2.4 (Optimized)",
            "filters_config": {
                "macd": {"fast": 8, "slow": 21, "signal": 5, "min_strength": 0.003},
                "ema": {"fast": 6, "medium": 14, "slow": 22, "min_distance": 0.008},
                "volume": {"threshold": 1.2, "min_volume": 500, "max_ratio": 8},
                "bb": {"period": 18, "std_dev": 1.8, "position_long": 0.15, "position_short": 0.85},
                "trend": {"ema_fast": 10, "ema_slow": 22, "min_trend_strength": 0.002},
            },
        },
        "overall_metrics": all_metrics,
        "results_by_symbol": results_by_symbol,
        "trades": backtest.trades[:2000],  # Первые 2000 сделок
    }
    
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("💾 Отчет сохранен: %s", report_file)
    
    # Создаем краткий текстовый отчет
    text_report_file = report_dir / f"optimized_filters_top5_3months_{timestamp}.txt"
    with open(text_report_file, "w", encoding="utf-8") as f:
        f.write("=" * 100 + "\n")
        f.write("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ОПТИМИЗИРОВАННЫХ ФИЛЬТРОВ\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"📅 Период: 3 месяца (90 дней)\n")
        f.write(f"🪙 Монеты: {', '.join(TOP_5_COINS)}\n")
        f.write(f"🔧 Фильтры: Оптимизированные (MACD 8/21/5, EMA 6/14/22, Volume 1.2, BB 18/1.8)\n\n")
        
        f.write("💰 ОБЩИЕ ФИНАНСОВЫЕ ПОКАЗАТЕЛИ:\n")
        f.write(f"  Начальный баланс: {backtest.initial_balance:.2f} USDT\n")
        f.write(f"  Финальный баланс: {all_metrics.get('final_balance', backtest.current_balance):.2f} USDT\n")
        f.write(f"  Общий PnL: {all_metrics.get('total_pnl', 0):.2f} USDT ({all_metrics.get('total_return', 0):.2f}%)\n")
        f.write(f"  Максимальная просадка: {all_metrics.get('max_drawdown', 0):.2f}%\n\n")
        
        f.write("📈 ОБЩАЯ СТАТИСТИКА СДЕЛОК:\n")
        f.write(f"  Всего сделок: {all_metrics.get('total_trades', 0)}\n")
        f.write(f"  Win Rate: {all_metrics.get('win_rate', 0):.2f}%\n")
        f.write(f"  Profit Factor: {all_metrics.get('profit_factor', 0):.2f}\n")
        f.write(f"  Sharpe Ratio: {all_metrics.get('sharpe_ratio', 0):.2f}\n")
        f.write(f"  Sortino Ratio: {all_metrics.get('sortino_ratio', 0):.2f}\n\n")
        
        f.write("📊 РЕЗУЛЬТАТЫ ПО МОНЕТАМ:\n")
        f.write("-" * 100 + "\n")
        for symbol_result in results_by_symbol:
            symbol = symbol_result.get('symbol', 'UNKNOWN')
            f.write(f"\n{symbol}:\n")
            f.write(f"  Сделок: {symbol_result.get('total_trades', 0)}\n")
            f.write(f"  Win Rate: {symbol_result.get('win_rate', 0):.2f}%\n")
            f.write(f"  PnL: {symbol_result.get('total_pnl', 0):.2f} USDT\n")
            f.write(f"  Profit Factor: {symbol_result.get('profit_factor', 0):.2f}\n")
        
        # Статистика по фильтрам
        filter_stats = all_metrics.get('filter_statistics', {})
        if filter_stats:
            f.write("\n🔍 СТАТИСТИКА БЛОКИРОВОК ПО ФИЛЬТРАМ:\n")
            f.write("-" * 100 + "\n")
            total_checked = filter_stats.get('total_signals_checked', 0)
            rejections = filter_stats.get('filter_rejections', {})
            percentages = filter_stats.get('rejection_percentages', {})
            
            f.write(f"\nВсего проверено сигналов: {total_checked}\n")
            f.write("\nБлокировок по фильтрам:\n")
            
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
                    
                    f.write(f"  {filter_display_name}: {count} ({pct:.2f}%)\n")
    
    logger.info("💾 Текстовый отчет сохранен: %s", text_report_file)
    
    print("\n" + "=" * 100)
    print("✅ Тестирование завершено!")
    print(f"💾 JSON отчет: {report_file}")
    print(f"💾 Текстовый отчет: {text_report_file}")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

