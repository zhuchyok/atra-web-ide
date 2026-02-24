#!/usr/bin/env python3
"""Комплексный бектест с реальной логикой сигналов и подробным отчетом."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.historical_data_loader import HistoricalDataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ComprehensiveBacktest:
    """Комплексный бектест с реальной логикой сигналов."""

    def __init__(
        self,
        initial_balance: float = 10000.0,
        risk_per_trade: float = 2.0,
        leverage: float = 2.0,
    ):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.leverage = leverage

        self.trades: List[Dict[str, Any]] = []
        self.open_positions: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []

        # Статистика
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_profit = 0.0
        self.max_loss = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = initial_balance

        # Фильтры статистика
        self.filter_stats: Dict[str, int] = {
            "rsi_filter": 0,
            "macd_filter": 0,
            "volume_filter": 0,
            "btc_trend_filter": 0,
            "confidence_filter": 0,
        }

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Рассчитывает технические индикаторы."""
        # EMA
        df["ema_5"] = df["close"].ewm(span=5).mean()
        df["ema_13"] = df["close"].ewm(span=13).mean()
        df["ema_21"] = df["close"].ewm(span=21).mean()
        df["ema_34"] = df["close"].ewm(span=34).mean()
        df["ema_50"] = df["close"].ewm(span=50).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df["close"].ewm(span=12).mean()
        exp2 = df["close"].ewm(span=26).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + (bb_std * 2)
        df["bb_lower"] = df["bb_middle"] - (bb_std * 2)

        # Volume
        df["volume_ma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma"]

        # ATR для волатильности
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df["atr"] = true_range.rolling(window=14).mean()

        return df

    def check_btc_trend(self, btc_df: pd.DataFrame, current_time: pd.Timestamp) -> Optional[bool]:
        """Проверяет BTC тренд (упрощённая версия)."""
        try:
            # Находим ближайшую свечу BTC
            btc_row = (
                btc_df.loc[btc_df.index <= current_time].iloc[-1]
                if len(btc_df.loc[btc_df.index <= current_time]) > 0
                else None
            )
            if btc_row is None:
                return None

            # Простая проверка: EMA 50 выше EMA 200 = бычий тренд
            if "ema_50" not in btc_row or pd.isna(btc_row["ema_50"]):
                return None

            ema_50 = btc_row.get("ema_50", btc_row["close"])
            ema_200 = (
                btc_row["close"].rolling(200).mean().iloc[-1] if len(btc_df) >= 200 else ema_50
            )

            return ema_50 > ema_200 if not pd.isna(ema_200) else None
        except Exception as e:
            logger.debug("Ошибка проверки BTC тренда: %s", e)
            return None

    def generate_signal(
        self,
        row: pd.Series,
        btc_df: pd.DataFrame,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """Генерирует торговый сигнал на основе реальной логики."""
        try:
            # Проверка на NaN
            if pd.isna(row.get("rsi")) or pd.isna(row.get("macd")):
                return None

            direction = None
            confidence = 0.0
            filters_passed = []

            # 1. RSI фильтр
            rsi = row["rsi"]
            if rsi < 30:
                direction = "LONG"
                confidence += 20
                filters_passed.append("rsi_oversold")
            elif rsi > 70:
                direction = "SHORT"
                confidence += 20
                filters_passed.append("rsi_overbought")
            else:
                self.filter_stats["rsi_filter"] += 1
                return None

            # 2. MACD фильтр
            macd = row["macd"]
            macd_signal = row["macd_signal"]
            macd_hist = row["macd_hist"]

            if direction == "LONG":
                if macd > macd_signal and macd_hist > 0:
                    confidence += 20
                    filters_passed.append("macd_bullish")
                else:
                    self.filter_stats["macd_filter"] += 1
                    return None
            else:  # SHORT
                if macd < macd_signal and macd_hist < 0:
                    confidence += 20
                    filters_passed.append("macd_bearish")
                else:
                    self.filter_stats["macd_filter"] += 1
                    return None

            # 3. Volume фильтр
            volume_ratio = row.get("volume_ratio", 1.0)
            if volume_ratio > 1.2:
                confidence += 15
                filters_passed.append("high_volume")
            elif volume_ratio < 0.8:
                self.filter_stats["volume_filter"] += 1
                return None
            else:
                confidence += 10

            # 4. BTC тренд фильтр
            btc_trend = self.check_btc_trend(btc_df, row.name)
            if btc_trend is not None:
                if (direction == "LONG" and btc_trend) or (direction == "SHORT" and not btc_trend):
                    confidence += 15
                    filters_passed.append("btc_aligned")
                else:
                    self.filter_stats["btc_trend_filter"] += 1
                    return None

            # 5. EMA фильтр
            ema_5 = row["ema_5"]
            ema_13 = row["ema_13"]
            ema_21 = row["ema_21"]

            if direction == "LONG":
                if ema_5 > ema_13 > ema_21:
                    confidence += 15
                    filters_passed.append("ema_bullish")
                else:
                    confidence += 5
            else:  # SHORT
                if ema_5 < ema_13 < ema_21:
                    confidence += 15
                    filters_passed.append("ema_bearish")
                else:
                    confidence += 5

            # 6. Bollinger Bands
            bb_position = (row["close"] - row["bb_lower"]) / (row["bb_upper"] - row["bb_lower"])
            if direction == "LONG" and bb_position < 0.2:
                confidence += 10
                filters_passed.append("bb_oversold")
            elif direction == "SHORT" and bb_position > 0.8:
                confidence += 10
                filters_passed.append("bb_overbought")

            # Минимальная уверенность
            if confidence < 60:
                self.filter_stats["confidence_filter"] += 1
                return None

            # Расчёт TP/SL
            atr = row.get("atr", row["close"] * 0.02)
            entry_price = row["close"]

            if direction == "LONG":
                sl_price = entry_price - (atr * 2)
                tp1_price = entry_price + (atr * 1.5)
                tp2_price = entry_price + (atr * 3)
            else:  # SHORT
                sl_price = entry_price + (atr * 2)
                tp1_price = entry_price - (atr * 1.5)
                tp2_price = entry_price - (atr * 3)

            return {
                "symbol": symbol,
                "direction": direction,
                "entry_price": float(entry_price),
                "sl_price": float(sl_price),
                "tp1_price": float(tp1_price),
                "tp2_price": float(tp2_price),
                "confidence": confidence,
                "filters_passed": filters_passed,
                "timestamp": row.name,
                "rsi": float(rsi),
                "macd": float(macd),
                "volume_ratio": float(volume_ratio),
                "btc_trend": btc_trend,
            }

        except Exception as e:
            logger.debug("Ошибка генерации сигнала: %s", e)
            return None

    def run_backtest(
        self,
        symbol: str,
        df: pd.DataFrame,
        btc_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Запускает бектест для символа."""
        logger.info("🔄 Запуск бектеста для %s (%d свечей)", symbol, len(df))

        df = self.calculate_indicators(df.copy())
        btc_df = self.calculate_indicators(btc_df.copy())

        # Удаляем NaN
        df = df.dropna()
        if len(df) < 50:
            logger.warning("⚠️ Недостаточно данных для %s", symbol)
            return {}

        for idx, row in df.iterrows():
            # Проверяем открытые позиции
            for pos in self.open_positions[:]:
                if pos["symbol"] == symbol:
                    # Проверка TP/SL
                    current_price = row["close"]
                    direction = pos["direction"]

                    if direction == "LONG":
                        if current_price >= pos["tp2_price"]:
                            # TP2 достигнут
                            self.close_position(pos, current_price, "tp2", idx)
                        elif current_price >= pos["tp1_price"] and pos.get("tp1_hit") is None:
                            # TP1 достигнут
                            pos["tp1_hit"] = True
                            # Частичное закрытие 50%
                            partial_pnl = self.close_partial_position(
                                pos, pos["tp1_price"], "tp1", 0.5, idx
                            )
                        elif current_price <= pos["sl_price"]:
                            # SL достигнут
                            self.close_position(pos, current_price, "sl", idx)
                    else:  # SHORT
                        if current_price <= pos["tp2_price"]:
                            # TP2 достигнут
                            self.close_position(pos, current_price, "tp2", idx)
                        elif current_price <= pos["tp1_price"] and pos.get("tp1_hit") is None:
                            # TP1 достигнут
                            pos["tp1_hit"] = True
                            # Частичное закрытие 50%
                            partial_pnl = self.close_partial_position(
                                pos, pos["tp1_price"], "tp1", 0.5, idx
                            )
                        elif current_price >= pos["sl_price"]:
                            # SL достигнут
                            self.close_position(pos, current_price, "sl", idx)

            # Генерируем новый сигнал
            signal = self.generate_signal(row, btc_df, symbol)
            if signal:
                # Проверяем, нет ли уже открытой позиции
                has_open = any(p["symbol"] == symbol for p in self.open_positions)
                if not has_open:
                    self.open_position(signal, row)

            # Обновляем equity curve
            self.update_equity_curve(idx)

        # Закрываем все открытые позиции в конце
        for pos in self.open_positions[:]:
            if pos["symbol"] == symbol:
                last_price = df.iloc[-1]["close"]
                self.close_position(pos, last_price, "end_of_data", df.index[-1])

        return {
            "symbol": symbol,
            "trades_count": len([t for t in self.trades if t["symbol"] == symbol]),
        }

    def open_position(self, signal: Dict[str, Any], row: pd.Series) -> None:
        """Открывает позицию."""
        entry_price = signal["entry_price"]
        direction = signal["direction"]

        # Расчёт размера позиции
        risk_amount = self.current_balance * (self.risk_per_trade / 100)
        sl_distance_pct = abs(entry_price - signal["sl_price"]) / entry_price

        # Размер позиции в базовой валюте (например, BTC)
        # risk_amount = position_size * sl_distance_pct * entry_price
        # position_size = risk_amount / (sl_distance_pct * entry_price)
        position_size_base = risk_amount / (sl_distance_pct * entry_price)

        # Применяем плечо
        position_size = position_size_base * self.leverage

        # Ограничиваем размер позиции (максимум 50% баланса)
        max_position_value = self.current_balance * 0.5
        max_position_size = max_position_value / entry_price
        position_size = min(position_size, max_position_size)

        position = {
            "symbol": signal["symbol"],
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": signal["sl_price"],
            "tp1_price": signal["tp1_price"],
            "tp2_price": signal["tp2_price"],
            "position_size": position_size,
            "entry_time": signal["timestamp"],
            "confidence": signal["confidence"],
            "filters_passed": signal["filters_passed"],
            "rsi": signal.get("rsi"),
            "macd": signal.get("macd"),
            "volume_ratio": signal.get("volume_ratio"),
            "btc_trend": signal.get("btc_trend"),
        }

        self.open_positions.append(position)

    def close_position(
        self,
        position: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        timestamp: pd.Timestamp,
    ) -> None:
        """Закрывает позицию полностью."""
        if position not in self.open_positions:
            return

        entry_price = position["entry_price"]
        direction = position["direction"]
        position_size = position["position_size"]

        # Расчёт PnL
        if direction == "LONG":
            pnl = (exit_price - entry_price) * position_size
        else:  # SHORT
            pnl = (entry_price - exit_price) * position_size

        pnl_percent = (pnl / (entry_price * position_size)) * 100

        trade = {
            "symbol": position["symbol"],
            "direction": direction,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "entry_time": position["entry_time"],
            "exit_time": timestamp,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_reason": exit_reason,
            "confidence": position["confidence"],
            "filters_passed": position["filters_passed"],
            "rsi": position.get("rsi"),
            "macd": position.get("macd"),
            "volume_ratio": position.get("volume_ratio"),
            "btc_trend": position.get("btc_trend"),
            "holding_time": (timestamp - position["entry_time"]).total_seconds() / 3600,
        }

        self.trades.append(trade)
        self.current_balance += pnl
        self.total_pnl += pnl

        if pnl > 0:
            self.winning_trades += 1
            self.max_profit = max(self.max_profit, pnl)
        else:
            self.losing_trades += 1
            self.max_loss = min(self.max_loss, pnl)

        self.total_trades += 1
        self.open_positions.remove(position)

        # Обновляем drawdown
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance * 100
        self.max_drawdown = max(self.max_drawdown, drawdown)

    def close_partial_position(
        self,
        position: Dict[str, Any],
        exit_price: float,
        exit_reason: str,
        partial_ratio: float,
        timestamp: pd.Timestamp,
    ) -> float:
        """Закрывает часть позиции."""
        entry_price = position["entry_price"]
        direction = position["direction"]
        partial_size = position["position_size"] * partial_ratio

        # Расчёт PnL
        if direction == "LONG":
            pnl = (exit_price - entry_price) * partial_size
        else:  # SHORT
            pnl = (entry_price - exit_price) * partial_size

        # Обновляем размер позиции
        position["position_size"] -= partial_size
        position["tp1_hit"] = True

        self.current_balance += pnl
        self.total_pnl += pnl

        return pnl

    def update_equity_curve(self, timestamp: pd.Timestamp) -> None:
        """Обновляет кривую эквити."""
        # Рассчитываем unrealized PnL
        unrealized_pnl = 0.0
        # Упрощённо: считаем только по закрытым позициям
        total_balance = self.current_balance

        self.equity_curve.append(
            {
                "timestamp": timestamp,
                "balance": total_balance,
                "drawdown": (self.peak_balance - total_balance) / self.peak_balance * 100
                if self.peak_balance > 0
                else 0,
            }
        )

    def calculate_metrics(self) -> Dict[str, Any]:
        """Рассчитывает метрики производительности."""
        if not self.trades:
            return {}

        df_trades = pd.DataFrame(self.trades)

        # Базовые метрики
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        # PnL метрики
        total_pnl = df_trades["pnl"].sum()
        avg_pnl = df_trades["pnl"].mean()
        avg_win = df_trades[df_trades["pnl"] > 0]["pnl"].mean() if self.winning_trades > 0 else 0
        avg_loss = df_trades[df_trades["pnl"] < 0]["pnl"].mean() if self.losing_trades > 0 else 0

        # Процентные метрики
        total_return = ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        avg_pnl_percent = df_trades["pnl_percent"].mean()

        # Sharpe Ratio
        returns = df_trades["pnl_percent"].values
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(252)  # Годовая
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0 and np.std(negative_returns) > 0:
            sortino_ratio = (np.mean(returns) / np.std(negative_returns)) * np.sqrt(252)
        else:
            sortino_ratio = 0.0

        # Profit Factor
        gross_profit = (
            df_trades[df_trades["pnl"] > 0]["pnl"].sum() if self.winning_trades > 0 else 0
        )
        gross_loss = (
            abs(df_trades[df_trades["pnl"] < 0]["pnl"].sum()) if self.losing_trades > 0 else 1
        )
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Максимальные серии
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for pnl in returns:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)

        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_return": total_return,
            "avg_pnl": avg_pnl,
            "avg_pnl_percent": avg_pnl_percent,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "profit_factor": profit_factor,
            "max_consecutive_wins": max_consecutive_wins,
            "max_consecutive_losses": max_consecutive_losses,
            "final_balance": self.current_balance,
            "initial_balance": self.initial_balance,
            "filter_stats": self.filter_stats,
        }


async def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(description="Комплексный бектест с подробным отчетом")
    parser.add_argument("--symbols", nargs="+", help="Список символов для бектеста")
    parser.add_argument("--top-n", type=int, default=10, help="Количество топ монет")
    parser.add_argument("--days", type=int, default=30, help="Количество дней для анализа")
    parser.add_argument("--initial-balance", type=float, default=10000.0, help="Начальный баланс")
    parser.add_argument("--risk", type=float, default=2.0, help="Риск на сделку (%)")
    parser.add_argument("--leverage", type=float, default=2.0, help="Плечо")
    parser.add_argument(
        "--output", default="data/backtest_report.json", help="Путь для сохранения отчета"
    )
    args = parser.parse_args()

    logger.info("🚀 Запуск комплексного бектеста...")

    # 1. Загрузка данных
    async with HistoricalDataLoader(exchange="binance") as loader:
        if args.symbols:
            symbols = args.symbols
        else:
            logger.info("📊 Получение топ %d монет...", args.top_n)
            symbols = await loader.get_top_symbols(limit=args.top_n)

        logger.info("📈 Символы для бектеста: %s", ", ".join(symbols))

        # Загружаем BTC для проверки тренда
        logger.info("📥 Загрузка данных BTC...")
        btc_df = await loader.fetch_ohlcv("BTCUSDT", interval="1h", days=args.days)

        # Загружаем данные для всех символов
        logger.info("📥 Загрузка исторических данных...")
        data_dict = await loader.load_multiple_symbols(symbols, interval="1h", days=args.days)

    # 2. Запуск бектеста
    backtest = ComprehensiveBacktest(
        initial_balance=args.initial_balance,
        risk_per_trade=args.risk,
        leverage=args.leverage,
    )

    results = []
    for symbol in symbols:
        if symbol not in data_dict or data_dict[symbol].empty:
            logger.warning("⚠️ Нет данных для %s, пропускаем", symbol)
            continue

        result = backtest.run_backtest(symbol, data_dict[symbol], btc_df)
        results.append(result)

    # 3. Расчёт метрик
    metrics = backtest.calculate_metrics()

    # 4. Генерация отчета
    report = {
        "backtest_info": {
            "start_date": (datetime.utcnow() - timedelta(days=args.days)).isoformat(),
            "end_date": datetime.utcnow().isoformat(),
            "symbols": symbols,
            "days": args.days,
            "initial_balance": args.initial_balance,
            "risk_per_trade": args.risk,
            "leverage": args.leverage,
        },
        "metrics": metrics,
        "trades": backtest.trades,
        "filter_stats": backtest.filter_stats,
    }

    # 5. Сохранение отчета
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    logger.info("✅ Бектест завершён")
    logger.info("📊 Результаты:")
    logger.info("   Всего сделок: %d", metrics.get("total_trades", 0))
    logger.info("   Win rate: %.2f%%", metrics.get("win_rate", 0))
    logger.info("   Total PnL: %.2f USD", metrics.get("total_pnl", 0))
    logger.info("   Sharpe Ratio: %.2f", metrics.get("sharpe_ratio", 0))
    logger.info("   Sortino Ratio: %.2f", metrics.get("sortino_ratio", 0))
    logger.info("   Max Drawdown: %.2f%%", metrics.get("max_drawdown", 0))
    logger.info("💾 Отчет сохранён: %s", output_path)

    return report


if __name__ == "__main__":
    asyncio.run(main())
