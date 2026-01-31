#!/usr/bin/env python3
"""
Массовый скрининг всех монет из data/backtest_data/
Цель: найти лучшие монеты для торговли на основе Win Rate и Profit Factor
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest
from data.historical_data_loader import HistoricalDataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Критерии отбора для портфеля
PORTFOLIO_CRITERIA = {
    "min_win_rate": 45.0,
    "min_trades": 8,
    "max_drawdown": 12.0,
    "min_profit_factor": 1.0,
}


def load_csv_data(symbol: str, data_dir: Path = None) -> Optional[pd.DataFrame]:
    """
    Загружает данные из CSV файла
    
    Args:
        symbol: Символ монеты (например, BTCUSDT)
        data_dir: Директория с данными (по умолчанию data/backtest_data)
    
    Returns:
        DataFrame с данными или None если файл не найден
    """
    if data_dir is None:
        data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    csv_file = data_dir / f"{symbol}.csv"
    
    if not csv_file.exists():
        logger.warning("⚠️ Файл не найден: %s", csv_file)
        return None
    
    try:
        df = pd.read_csv(csv_file)
        
        # Преобразуем timestamp в datetime и устанавливаем как индекс
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        elif df.index.name == 'timestamp' or df.index.dtype == 'object':
            df.index = pd.to_datetime(df.index)
        
        # Переименовываем колонки если нужно
        column_mapping = {
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume',
        }
        
        # Проверяем наличие необходимых колонок
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            logger.warning("⚠️ Не все необходимые колонки найдены для %s", symbol)
            return None
        
        logger.debug("✅ Загружено %d строк для %s", len(df), symbol)
        return df
    
    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def run_single_backtest(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Запускает бэктест для одной монеты
    
    Args:
        symbol: Символ монеты
        df: DataFrame с данными монеты
        btc_df: DataFrame с данными BTC (для фильтров)
        eth_df: DataFrame с данными ETH (для фильтров)
        sol_df: DataFrame с данными SOL (для фильтров)
        days: Количество дней для тестирования
    
    Returns:
        Словарь с результатами бэктеста
    """
    try:
        backtest = AdvancedBacktest(
            initial_balance=10000.0,
            risk_per_trade=2.0,
            leverage=2.0,
        )
        
        # Устанавливаем данные для фильтров
        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df
        
        # Запускаем бэктест
        await backtest.run_backtest(symbol, df, btc_df, days=days)
        
        # Собираем метрики
        symbol_trades = [t for t in backtest.trades if t.get('symbol') == symbol]
        total_trades = len(symbol_trades)
        
        if total_trades == 0:
            return {
                "symbol": symbol,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
                "total_return": 0.0,
                "max_drawdown": 0.0,
                "status": "NO_TRADES",
            }
        
        winning_trades = len([t for t in symbol_trades if t.get('pnl', 0) > 0])
        losing_trades = total_trades - winning_trades
        total_pnl = sum(t.get('pnl', 0) for t in symbol_trades)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        gross_profit = sum(t.get('pnl', 0) for t in symbol_trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in symbol_trades if t.get('pnl', 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        
        # Вычисляем max drawdown
        balance_curve = [10000.0]
        current_balance = 10000.0
        peak_balance = 10000.0
        max_drawdown = 0.0
        
        for trade in symbol_trades:
            current_balance += trade.get('pnl', 0)
            balance_curve.append(current_balance)
            if current_balance > peak_balance:
                peak_balance = current_balance
            drawdown = ((peak_balance - current_balance) / peak_balance) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        total_return = ((current_balance - 10000.0) / 10000.0) * 100
        
        return {
            "symbol": symbol,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "status": "SUCCESS",
        }
    
    except Exception as e:
        logger.error("❌ Ошибка бэктеста для %s: %s", symbol, e)
        return {
            "symbol": symbol,
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "status": f"ERROR: {str(e)}",
        }


async def screen_all_symbols(days: int = 30, min_trades: int = 5) -> List[Dict[str, Any]]:
    """
    Запускает скрининг всех монет из data/backtest_data/
    
    Args:
        days: Количество дней для тестирования
        min_trades: Минимальное количество сделок для включения в результаты
    
    Returns:
        Список результатов, отсортированный по Win Rate
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"
    
    # Получаем список всех CSV файлов
    csv_files = list(data_dir.glob("*.csv"))
    symbols = [f.stem for f in csv_files]
    
    logger.info("🚀 Начинаем массовый скрининг %d монет...", len(symbols))
    logger.info("📊 Период: %d дней", days)
    logger.info("🎯 Минимум сделок: %d", min_trades)
    
    # Загружаем данные BTC, ETH, SOL для фильтров
    logger.info("📥 Загрузка данных BTC, ETH, SOL для фильтров...")
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)
    
    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL для фильтров")
        return []
    
    results = []
    total_symbols = len(symbols)
    start_time = time.time()
    
    for idx, symbol in enumerate(symbols, 1):
        logger.info("📊 [%d/%d] Тестируем %s...", idx, total_symbols, symbol)
        
        # Загружаем данные монеты
        df = load_csv_data(symbol, data_dir)
        if df is None or df.empty:
            logger.warning("⚠️ Пропускаем %s - нет данных", symbol)
            continue
        
        # Запускаем бэктест
        result = await run_single_backtest(symbol, df, btc_df, eth_df, sol_df, days=days)
        
        # Добавляем только если есть достаточно сделок
        if result["total_trades"] >= min_trades:
            results.append(result)
            logger.info(
                "✅ %s: %d сделок, Win Rate: %.2f%%, PF: %.2f, PnL: %.2f USDT",
                symbol,
                result["total_trades"],
                result["win_rate"],
                result["profit_factor"],
                result["total_pnl"],
            )
        else:
            logger.debug(
                "⏭️ %s: %d сделок (меньше минимума %d)",
                symbol,
                result["total_trades"],
                min_trades,
            )
        
        # Прогресс каждые 10 монет
        if idx % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = (total_symbols - idx) * avg_time
            logger.info(
                "⏱️ Прогресс: %d/%d (%.1f%%), Осталось: ~%.1f минут",
                idx,
                total_symbols,
                (idx / total_symbols) * 100,
                remaining / 60,
            )
    
    # Сортируем по Win Rate (по убыванию)
    results.sort(key=lambda x: x["win_rate"], reverse=True)
    
    elapsed_total = time.time() - start_time
    logger.info("✅ Скрининг завершен за %.1f минут", elapsed_total / 60)
    logger.info("📊 Найдено %d монет с >= %d сделками", len(results), min_trades)
    
    return results


def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Анализирует результаты скрининга и формирует рекомендации
    
    Args:
        results: Список результатов бэктестов
    
    Returns:
        Словарь с анализом и рекомендациями
    """
    if not results:
        return {"error": "Нет результатов для анализа"}
    
    # Группируем по Win Rate
    excellent = [r for r in results if r["win_rate"] >= 55.0]
    good = [r for r in results if 45.0 <= r["win_rate"] < 55.0]
    average = [r for r in results if 35.0 <= r["win_rate"] < 45.0]
    poor = [r for r in results if r["win_rate"] < 35.0]
    
    # Находим лучшие монеты по критериям портфеля
    portfolio_candidates = [
        r
        for r in results
        if r["win_rate"] >= PORTFOLIO_CRITERIA["min_win_rate"]
        and r["total_trades"] >= PORTFOLIO_CRITERIA["min_trades"]
        and r["max_drawdown"] <= PORTFOLIO_CRITERIA["max_drawdown"]
        and r["profit_factor"] >= PORTFOLIO_CRITERIA["min_profit_factor"]
    ]
    
    # Топ-10 по Win Rate
    top_10_win_rate = sorted(results, key=lambda x: x["win_rate"], reverse=True)[:10]
    
    # Топ-10 по Profit Factor
    top_10_profit_factor = sorted(
        [r for r in results if r["profit_factor"] > 0],
        key=lambda x: x["profit_factor"],
        reverse=True,
    )[:10]
    
    # Топ-10 по Total PnL
    top_10_pnl = sorted(results, key=lambda x: x["total_pnl"], reverse=True)[:10]
    
    return {
        "summary": {
            "total_tested": len(results),
            "excellent_wr_55plus": len(excellent),
            "good_wr_45_55": len(good),
            "average_wr_35_45": len(average),
            "poor_wr_below_35": len(poor),
            "portfolio_candidates": len(portfolio_candidates),
        },
        "distribution": {
            "excellent": excellent,
            "good": good,
            "average": average,
            "poor": poor,
        },
        "top_10": {
            "by_win_rate": top_10_win_rate,
            "by_profit_factor": top_10_profit_factor,
            "by_pnl": top_10_pnl,
        },
        "portfolio_candidates": portfolio_candidates,
    }


def save_results(results: List[Dict[str, Any]], analysis: Dict[str, Any], output_dir: Path = None):
    """
    Сохраняет результаты скрининга в файлы
    
    Args:
        results: Список результатов бэктестов
        analysis: Анализ результатов
        output_dir: Директория для сохранения (по умолчанию data/reports)
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "reports"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
    
    # Сохраняем полные результаты
    results_file = output_dir / f"mass_screening_results_{timestamp}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "screening_info": {
                    "timestamp": timestamp,
                    "total_symbols": len(results),
                    "period_days": 30,
                },
                "results": results,
                "analysis": analysis,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    
    logger.info("💾 Результаты сохранены в %s", results_file)
    
    # Сохраняем CSV для удобного анализа
    csv_file = output_dir / f"mass_screening_results_{timestamp}.csv"
    df_results = pd.DataFrame(results)
    df_results.to_csv(csv_file, index=False)
    logger.info("💾 CSV сохранен в %s", csv_file)
    
    return results_file, csv_file


def print_summary(results: List[Dict[str, Any]], analysis: Dict[str, Any]):
    """
    Выводит сводку результатов скрининга
    """
    print("\n" + "=" * 80)
    print("📊 РЕЗУЛЬТАТЫ МАССОВОГО СКРИНИНГА ВСЕХ МОНЕТ")
    print("=" * 80)
    
    print(f"\n✅ Всего протестировано: {len(results)} монет")
    print(f"\n📈 Распределение по Win Rate:")
    print(f"  🟢 Отлично (≥55%): {analysis['summary']['excellent_wr_55plus']} монет")
    print(f"  🟡 Хорошо (45-55%): {analysis['summary']['good_wr_45_55']} монет")
    print(f"  🟠 Средне (35-45%): {analysis['summary']['average_wr_35_45']} монет")
    print(f"  🔴 Плохо (<35%): {analysis['summary']['poor_wr_below_35']} монет")
    print(f"\n🎯 Кандидаты в портфель: {analysis['summary']['portfolio_candidates']} монет")
    
    print(f"\n🏆 ТОП-10 ПО WIN RATE:")
    print("-" * 80)
    for idx, coin in enumerate(analysis["top_10"]["by_win_rate"], 1):
        print(
            f"  {idx:2d}. {coin['symbol']:12s} | WR: {coin['win_rate']:5.2f}% | "
            f"PF: {coin['profit_factor']:5.2f} | Сделок: {coin['total_trades']:3d} | "
            f"PnL: {coin['total_pnl']:8.2f} USDT"
        )
    
    print(f"\n💰 ТОП-10 ПО PROFIT FACTOR:")
    print("-" * 80)
    for idx, coin in enumerate(analysis["top_10"]["by_profit_factor"], 1):
        print(
            f"  {idx:2d}. {coin['symbol']:12s} | PF: {coin['profit_factor']:5.2f} | "
            f"WR: {coin['win_rate']:5.2f}% | Сделок: {coin['total_trades']:3d} | "
            f"PnL: {coin['total_pnl']:8.2f} USDT"
        )
    
    print(f"\n💎 ТОП-10 ПО PnL:")
    print("-" * 80)
    for idx, coin in enumerate(analysis["top_10"]["by_pnl"], 1):
        print(
            f"  {idx:2d}. {coin['symbol']:12s} | PnL: {coin['total_pnl']:8.2f} USDT | "
            f"WR: {coin['win_rate']:5.2f}% | PF: {coin['profit_factor']:5.2f} | "
            f"Сделок: {coin['total_trades']:3d}"
        )
    
    if analysis["portfolio_candidates"]:
        print(f"\n🎯 КАНДИДАТЫ В ПОРТФЕЛЬ (WR≥45%, PF≥1.0, Сделок≥8):")
        print("-" * 80)
        for idx, coin in enumerate(analysis["portfolio_candidates"], 1):
            print(
                f"  {idx:2d}. {coin['symbol']:12s} | WR: {coin['win_rate']:5.2f}% | "
                f"PF: {coin['profit_factor']:5.2f} | Сделок: {coin['total_trades']:3d} | "
                f"PnL: {coin['total_pnl']:8.2f} USDT | MaxDD: {coin['max_drawdown']:5.2f}%"
            )
    
    print("\n" + "=" * 80)


async def main():
    """Основная функция"""
    logger.info("🚀 Запуск массового скрининга всех монет...")
    
    # Запускаем скрининг
    results = await screen_all_symbols(days=30, min_trades=5)
    
    if not results:
        logger.error("❌ Нет результатов для анализа")
        return
    
    # Анализируем результаты
    analysis = analyze_results(results)
    
    # Сохраняем результаты
    results_file, csv_file = save_results(results, analysis)
    
    # Выводим сводку
    print_summary(results, analysis)
    
    logger.info("✅ Скрининг завершен! Результаты сохранены в %s", results_file)


if __name__ == "__main__":
    asyncio.run(main())

