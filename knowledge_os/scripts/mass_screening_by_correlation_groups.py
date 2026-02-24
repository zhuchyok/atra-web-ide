#!/usr/bin/env python3
"""
Массовый скрининг всех монет с группировкой по корреляции к BTC/ETH/SOL
Цель: выбрать топ-5 монет из каждой корреляционной группы (BTC_HIGH, ETH_HIGH, SOL_HIGH)
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_advanced_backtest import AdvancedBacktest
from src.risk.correlation_risk import CorrelationRiskManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Критерии отбора для портфеля
PORTFOLIO_CRITERIA = {
    "min_win_rate": 40.0,
    "min_trades": 5,
    "max_drawdown": 15.0,
    "min_profit_factor": 0.8,
}


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

    except Exception as e:
        logger.error("❌ Ошибка загрузки данных для %s: %s", symbol, e)
        return None


async def run_single_backtest(
    symbol: str,
    df: pd.DataFrame,
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    sol_df: pd.DataFrame,
    days: int = 365,
) -> Dict[str, Any]:
    """Запускает бэктест для одной монеты"""
    try:
        backtest = AdvancedBacktest(initial_balance=10000.0, risk_per_trade=2.0, leverage=2.0)

        backtest.btc_df = btc_df
        backtest.eth_df = eth_df
        backtest.sol_df = sol_df

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
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
            "sortino_ratio": metrics.get("sortino_ratio", 0.0),
            "avg_win": metrics.get("avg_win", 0.0),
            "avg_loss": metrics.get("avg_loss", 0.0),
        }

    except Exception as e:
        logger.error("❌ Ошибка бектеста для %s: %s", symbol, e)
        return {
            "symbol": symbol,
            "error": str(e),
            "total_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "total_pnl": 0.0,
            "total_pnl_pct": 0.0,
        }


def calculate_correlation_from_csv(
    symbol: str, base_symbol: str, symbol_df: pd.DataFrame, base_df: pd.DataFrame
) -> float:
    """Вычисляет корреляцию из CSV данных напрямую"""
    try:
        import numpy as np

        # Приводим к общему размеру (берем минимум)
        min_len = min(len(symbol_df), len(base_df))
        if min_len < 50:
            return 0.0

        symbol_prices = symbol_df["close"].tail(min_len).values
        base_prices = base_df["close"].tail(min_len).values

        # Вычисляем returns
        symbol_returns = pd.Series(symbol_prices).pct_change().dropna().values
        base_returns = pd.Series(base_prices).pct_change().dropna().values

        # Убеждаемся, что длины совпадают
        min_returns_len = min(len(symbol_returns), len(base_returns))
        if min_returns_len < 10:
            return 0.0

        symbol_returns = symbol_returns[:min_returns_len]
        base_returns = base_returns[:min_returns_len]

        # Вычисляем корреляцию
        correlation_matrix = np.corrcoef(symbol_returns, base_returns)
        correlation = correlation_matrix[0, 1]

        # Проверяем на NaN
        if np.isnan(correlation) or np.isinf(correlation):
            return 0.0

        return correlation

    except Exception as e:
        logger.debug("Ошибка расчета корреляции %s к %s: %s", symbol, base_symbol, e)
        return 0.0


async def calculate_correlation_groups(
    symbols: List[str], correlation_manager: CorrelationRiskManager, data_dir: Path
) -> Dict[str, List[str]]:
    """
    Вычисляет корреляционные группы для всех символов

    Returns:
        Dict с ключами: BTC_HIGH, ETH_HIGH, SOL_HIGH, и т.д.
        Значения: списки символов в каждой группе
    """
    groups: Dict[str, List[str]] = {
        "BTC_HIGH": [],
        "BTC_MEDIUM": [],
        "BTC_LOW": [],
        "BTC_INDEPENDENT": [],
        "ETH_HIGH": [],
        "ETH_MEDIUM": [],
        "ETH_LOW": [],
        "ETH_INDEPENDENT": [],
        "SOL_HIGH": [],
        "SOL_MEDIUM": [],
        "SOL_LOW": [],
        "SOL_INDEPENDENT": [],
        "OTHER": [],
    }

    logger.info("📊 Вычисление корреляционных групп для %d монет...", len(symbols))

    # Загружаем данные базовых активов один раз
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL для расчета корреляции")
        return groups

    for idx, symbol in enumerate(symbols, 1):
        try:
            df = load_csv_data(symbol, data_dir)
            if df is None or df.empty:
                continue

            # Вычисляем корреляции напрямую из CSV
            btc_corr = calculate_correlation_from_csv(symbol, "BTC", df, btc_df)
            eth_corr = calculate_correlation_from_csv(symbol, "ETH", df, eth_df)
            sol_corr = calculate_correlation_from_csv(symbol, "SOL", df, sol_df)

            # Определяем максимальную корреляцию
            max_corr = max(btc_corr, eth_corr, sol_corr)
            if max_corr == btc_corr:
                base = "BTC"
            elif max_corr == eth_corr:
                base = "ETH"
            else:
                base = "SOL"

            # Определяем уровень корреляции
            if max_corr >= 0.75:
                level = "HIGH"
            elif max_corr >= 0.50:
                level = "MEDIUM"
            elif max_corr >= 0.25:
                level = "LOW"
            else:
                level = "INDEPENDENT"

            group = f"{base}_{level}"

            if group in groups:
                groups[group].append(symbol)
            else:
                groups["OTHER"].append(symbol)

            if idx % 10 == 0:
                logger.info("📊 Прогресс группировки: %d/%d", idx, len(symbols))

        except Exception as e:
            logger.warning("⚠️ Ошибка определения группы для %s: %s", symbol, e)
            groups["OTHER"].append(symbol)

    # Выводим статистику
    logger.info("📊 Результаты группировки:")
    for group_name, group_symbols in groups.items():
        if group_symbols:
            logger.info("   %s: %d монет", group_name, len(group_symbols))

    return groups


async def screen_by_correlation_groups(days: int = 365, min_trades: int = 5) -> Dict[str, Any]:
    """
    Запускает скрининг всех монет с группировкой по корреляции

    Args:
        days: Количество дней для тестирования (365 для годового)
        min_trades: Минимальное количество сделок

    Returns:
        Словарь с результатами по группам и топ-5 монет из каждой группы
    """
    data_dir = PROJECT_ROOT / "data" / "backtest_data"

    # Получаем список всех CSV файлов
    csv_files = list(data_dir.glob("*.csv"))
    symbols = [f.stem for f in csv_files]

    logger.info("🚀 Начинаем массовый скрининг %d монет...", len(symbols))
    logger.info("📊 Период: %d дней (годовой бектест)", days)
    logger.info("🎯 Минимум сделок: %d", min_trades)

    # Инициализируем CorrelationRiskManager
    correlation_manager = CorrelationRiskManager(db_path="trading.db")

    # Вычисляем корреляционные группы
    groups = await calculate_correlation_groups(symbols, correlation_manager, data_dir)

    # Загружаем данные BTC, ETH, SOL для фильтров
    logger.info("📥 Загрузка данных BTC, ETH, SOL для фильтров...")
    btc_df = load_csv_data("BTCUSDT", data_dir)
    eth_df = load_csv_data("ETHUSDT", data_dir)
    sol_df = load_csv_data("SOLUSDT", data_dir)

    if btc_df is None or eth_df is None or sol_df is None:
        logger.error("❌ Не удалось загрузить данные BTC/ETH/SOL для фильтров")
        return {}

    # Запускаем бектесты для каждой группы
    # Расширяем группы: включаем LOW для BTC и ETH, чтобы набрать достаточно монет
    # Если нужно 10 монет в каждой группе - расширяем дальше
    target_groups = [
        "BTC_HIGH",
        "BTC_MEDIUM",
        "BTC_LOW",
        "ETH_HIGH",
        "ETH_MEDIUM",
        "ETH_LOW",
        "SOL_HIGH",
    ]
    results_by_group: Dict[str, List[Dict[str, Any]]] = {}
    top5_by_group: Dict[str, List[Dict[str, Any]]] = {}

    for group_name in target_groups:
        group_symbols = groups.get(group_name, [])
        if not group_symbols:
            logger.warning("⚠️ Группа %s пуста", group_name)
            results_by_group[group_name] = []
            top5_by_group[group_name] = []
            continue

        logger.info("📊 Тестируем группу %s (%d монет)...", group_name, len(group_symbols))
        results = []

        for idx, symbol in enumerate(group_symbols, 1):
            logger.info("   [%d/%d] Тестируем %s...", idx, len(group_symbols), symbol)

            df = load_csv_data(symbol, data_dir)
            if df is None or df.empty:
                continue

            result = await run_single_backtest(symbol, df, btc_df, eth_df, sol_df, days=days)

            if result.get("total_trades", 0) >= min_trades:
                result["correlation_group"] = group_name
                results.append(result)
                logger.info(
                    "   ✅ %s: %d сделок, Win Rate: %.2f%%, PF: %.2f, PnL: %.2f%%",
                    symbol,
                    result["total_trades"],
                    result["win_rate"],
                    result["profit_factor"],
                    result["total_pnl_pct"],
                )

        # Сортируем по комбинированному скору (Win Rate * Profit Factor * PnL)
        # Используем total_pnl вместо total_pnl_pct (так как pct = 0.0)
        results.sort(
            key=lambda x: (x["win_rate"] * x["profit_factor"] * max(0, x["total_pnl"])),
            reverse=True,
        )

        results_by_group[group_name] = results
        top5_by_group[group_name] = results[:5]

        logger.info("✅ Группа %s: %d монет прошли тест, топ-5 выбраны", group_name, len(results))

    # Объединяем результаты для формирования финального портфеля
    # BTC: BTC_HIGH + BTC_MEDIUM + BTC_LOW → топ-5 или топ-10
    btc_combined = []
    for group in ["BTC_HIGH", "BTC_MEDIUM", "BTC_LOW"]:
        btc_combined.extend(results_by_group.get(group, []))
    btc_combined.sort(
        key=lambda x: x["win_rate"] * x["profit_factor"] * max(0, x["total_pnl"]), reverse=True
    )

    # ETH: ETH_HIGH + ETH_MEDIUM + ETH_LOW → топ-5 или топ-10
    eth_combined = []
    for group in ["ETH_HIGH", "ETH_MEDIUM", "ETH_LOW"]:
        eth_combined.extend(results_by_group.get(group, []))
    eth_combined.sort(
        key=lambda x: x["win_rate"] * x["profit_factor"] * max(0, x["total_pnl"]), reverse=True
    )

    # SOL: SOL_HIGH → топ-5 или топ-10
    sol_combined = results_by_group.get("SOL_HIGH", [])
    sol_combined.sort(
        key=lambda x: x["win_rate"] * x["profit_factor"] * max(0, x["total_pnl"]), reverse=True
    )

    # Выбираем топ-10 для каждой группы (можно изменить на 5)
    TOP_N = 10  # 🔧 ИЗМЕНИТЬ НА 5, если нужно по 5 монет

    # Обновляем top5_by_group с объединенными результатами
    top5_by_group["BTC_HIGH"] = btc_combined[:TOP_N]
    top5_by_group["ETH_HIGH"] = eth_combined[:TOP_N]
    top5_by_group["SOL_HIGH"] = sol_combined[:TOP_N]

    logger.info("📊 Финальный портфель:")
    logger.info("   BTC (HIGH+MEDIUM+LOW): %d монет → топ-%d выбраны", len(btc_combined), TOP_N)
    logger.info("   ETH (HIGH+MEDIUM+LOW): %d монет → топ-%d выбраны", len(eth_combined), TOP_N)
    logger.info("   SOL (HIGH): %d монет → топ-%d выбраны", len(sol_combined), TOP_N)

    return {
        "groups": groups,
        "results_by_group": results_by_group,
        "top5_by_group": top5_by_group,
        "screening_info": {
            "total_symbols": len(symbols),
            "period_days": days,
            "min_trades": min_trades,
            "timestamp": datetime.now().isoformat(),
        },
    }


def save_results(results: Dict[str, Any], output_dir: Path = None):
    """Сохраняет результаты скрининга"""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "reports"

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Сохраняем JSON
    json_file = output_dir / f"correlation_groups_screening_{timestamp}.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("💾 JSON сохранен в %s", json_file)

    # Сохраняем топ-5 по группам в CSV
    csv_file = output_dir / f"correlation_groups_top5_{timestamp}.csv"
    top5_data = []
    for group_name, top5 in results.get("top5_by_group", {}).items():
        for coin in top5:
            coin["group"] = group_name
            top5_data.append(coin)

    if top5_data:
        df_top5 = pd.DataFrame(top5_data)
        df_top5.to_csv(csv_file, index=False)
        logger.info("💾 CSV сохранен в %s", csv_file)

    return json_file, csv_file


def print_summary(results: Dict[str, Any]):
    """Выводит сводку результатов"""
    print("\n" + "=" * 80)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ СКРИНИНГА ПО КОРРЕЛЯЦИОННЫМ ГРУППАМ")
    print("=" * 80)

    top5_by_group = results.get("top5_by_group", {})

    for group_name in ["BTC_HIGH", "ETH_HIGH", "SOL_HIGH"]:
        top5 = top5_by_group.get(group_name, [])
        if not top5:
            print(f"\n⚠️ {group_name}: Нет результатов")
            continue

        print(f"\n🎯 {group_name} - ТОП-5 МОНЕТ:")
        print("-" * 80)
        for idx, coin in enumerate(top5, 1):
            print(
                f"  {idx}. {coin['symbol']:12s} | "
                f"Сделок: {coin['total_trades']:3d} | "
                f"Win Rate: {coin['win_rate']:5.2f}% | "
                f"PF: {coin['profit_factor']:5.2f} | "
                f"PnL: {coin['total_pnl_pct']:7.2f}% | "
                f"MaxDD: {coin['max_drawdown']:5.2f}%"
            )

    print("\n" + "=" * 80)
    print("✅ Скрининг завершен!")
    print("=" * 80)


async def main():
    """Главная функция"""
    days = 365  # Годовой бектест
    min_trades = 5  # Минимум 5 сделок

    logger.info("🚀 Запуск массового скрининга по корреляционным группам...")
    logger.info("📊 Период: %d дней", days)

    results = await screen_by_correlation_groups(days=days, min_trades=min_trades)

    if results:
        save_results(results)
        print_summary(results)
    else:
        logger.error("❌ Не удалось получить результаты скрининга")


if __name__ == "__main__":
    asyncio.run(main())
