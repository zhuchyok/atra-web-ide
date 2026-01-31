#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fallback 15m momentum + liquidity стратегия.

Цель: простая резервная система генерации сигналов, когда основной пайплайн недоступен.
Логика основана на описании из раздела 6 аудита: основной таймфрейм 15m, подтверждение тренда на 1h.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.database.db import Database
from market_regime_detector import MarketRegimeDetector
try:
    from src.utils.ohlc_utils import get_ohlc_binance_sync_range
except ImportError:
    try:
        from ohlc_utils import get_ohlc_binance_sync_range
    except ImportError:
        def get_ohlc_binance_sync_range(*args, **kwargs): return None

logger = logging.getLogger(__name__)


@dataclass
class FallbackConfig:
    """Конфигурация fallback-стратегии на 15m с подтверждением тренда."""
    symbols: List[str]
    interval: str = "15m"
    confirmation_interval: str = "1h"
    days: int = 7
    min_volume_usd: float = 50_000_000
    max_spread_pct: float = 0.25
    rsi_threshold: float = 60.0
    volume_acceleration: float = 1.3
    risk_pct: float = 1.0
    leverage: float = 3.0
    atr_multiplier_sl: float = 1.2
    atr_multiplier_tp1: float = 0.8
    atr_multiplier_tp2: float = 1.6


class FallbackMomentumStrategy:
    """Простая стратегия momentum + liquidity на 15m."""

    def __init__(self, config: FallbackConfig) -> None:
        self.config = config
        self.regime_detector = MarketRegimeDetector()
        self._db: Optional[Database] = None

    def fetch_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Получает 15m OHLC."""
        try:
            days = max(1, int(self.config.days))
            data = get_ohlc_binance_sync_range(
                symbol,
                interval=self.config.interval,
                days=days,
                max_per_call=720,
            )
            if not data:
                return None
            df = pd.DataFrame(data)
            if "open_time" in df.columns:
                df["open_time"] = pd.to_datetime(df["open_time"])
                df = df.set_index("open_time")
            elif "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df = df.set_index("timestamp")
            else:
                logger.error("❌ [Fallback] Неизвестный формат OHLC для %s: колонки %s", symbol, df.columns)
                return None
            return df
        except Exception as exc:  # noqa: BLE001
            logger.error("❌ [Fallback] Не удалось получить OHLC для %s: %s", symbol, exc)
            return None

    def prepare_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет необходимые индикаторы через централизованный модуль."""
        if df.empty:
            return df
        
        from src.signals.indicators import add_technical_indicators
        
        # Используем централизованный модуль
        # EMA 34 и 89 не стандартные, укажем их явно
        work = add_technical_indicators(
            df,
            rsi_period=14,
            ema_periods=[34, 89],
            atr_period=14
        )
        
        # Backward compatibility для имен в этой стратегии
        if 'ema34' in work.columns: work['ema34'] = work['ema34']
        if 'ema89' in work.columns: work['ema89'] = work['ema89']
        if 'rsi_14' in work.columns: work['rsi14'] = work['rsi_14']
        if 'atr' in work.columns: work['atr14'] = work['atr']
        
        # Volume ratio уже есть в add_technical_indicators
        return work

    def _fetch_confirmation_data(self, symbol: str, days: int) -> Optional[pd.DataFrame]:
        try:
            data = get_ohlc_binance_sync_range(
                symbol,
                interval=self.config.confirmation_interval,
                days=max(1, days),
                max_per_call=365,
            )
            if not data:
                return None
            df = pd.DataFrame(data)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            elif "open_time" in df.columns:
                df["timestamp"] = pd.to_datetime(df["open_time"])
            else:
                return None
            return df.set_index("timestamp").sort_index()
        except Exception as exc:  # noqa: BLE001
            logger.error("❌ [Fallback] Не удалось получить 1h данные для %s: %s", symbol, exc)
            return None

    def confirm_trend(
        self,
        symbol: str,
        timestamp: Optional[pd.Timestamp] = None,
        data_1h: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Подтверждение тренда на 1h через централизованные индикаторы."""
        try:
            if data_1h is None:
                data_1h = self._fetch_confirmation_data(symbol, self.config.days)
            if data_1h is None or data_1h.empty:
                return False, "Недостаточно 1h данных"
            
            df = data_1h
            if timestamp is not None:
                df = df[df.index <= timestamp]
                if df.empty:
                    return False, "Нет 1h истории до точки входа"
            
            from src.signals.indicators import add_technical_indicators
            df = add_technical_indicators(df, ema_periods=[34, 89])
            
            if df["ema34"].iloc[-1] > df["ema89"].iloc[-1]:
                return True, "1h trend up"
            return False, "1h trend down"
        except Exception as exc:  # noqa: BLE001
            return False, f"Ошибка подтверждения тренда: {exc}"

    def evaluate_symbol(self, symbol: str) -> Optional[Dict[str, any]]:
        """Основной метод оценки символа."""
        df = self.fetch_data(symbol)
        if df is None or df.empty:
            return None
        df = self.prepare_indicators(df)
        latest = df.iloc[-1]
        timestamp = df.index[-1]

        if not self._meets_entry_conditions(latest):
            logger.debug("🚫 %s: EMA34 <= EMA89", symbol)
            return None

        confirmed, reason = self.confirm_trend(symbol, timestamp=timestamp)
        if not confirmed:
            logger.debug("🚫 %s: 1h подтверждение не прошло: %s", symbol, reason)
            return None

        atr = latest["atr14"]
        entry_price = latest["close"]
        sl = entry_price - atr * self.config.atr_multiplier_sl
        tp1 = entry_price + atr * self.config.atr_multiplier_tp1
        tp2 = entry_price + atr * self.config.atr_multiplier_tp2

        return {
            "symbol": symbol,
            "direction": "LONG",
            "entry_price": float(entry_price),
            "sl_price": float(sl),
            "tp1_price": float(tp1),
            "tp2_price": float(tp2),
            "risk_pct": self.config.risk_pct,
            "leverage": self.config.leverage,
            "volume_ratio": float(latest["volume_ratio"]),
            "rsi14": float(latest["rsi14"]),
            "atr14": float(atr),
            "timestamp": get_utc_now().isoformat(),
            "confirmation_reason": reason,
        }

    def _meets_entry_conditions(self, row: pd.Series) -> bool:
        if row["ema34"] <= row["ema89"]:
            return False
        if row["rsi14"] >= self.config.rsi_threshold:
            return False
        if row["volume_ratio"] < self.config.volume_acceleration:
            return False
        return True

    def run(self) -> List[Dict[str, any]]:
        """Проход по списку символов."""
        signals: List[Dict[str, any]] = []
        for symbol in self.config.symbols:
            try:
                signal = self.evaluate_symbol(symbol)
                if signal:
                    signals.append(signal)
            except Exception as exc:  # noqa: BLE001
                logger.error("Ошибка при обработке %s: %s", symbol, exc, exc_info=True)
        return signals

    def save_signals(
        self,
        signals: List[Dict[str, any]],
        *,
        user_id: Optional[int] = 0,
        entry_amount_usd: Optional[float] = 100.0,
        trade_mode: str = "backfill",
    ) -> int:
        """Сохраняет подготовленные сигналы в `signals_log`."""
        if not signals:
            return 0

        if self._db is None:
            self._db = Database()

        saved = 0
        for sig in signals:
            entry_time = sig.get("timestamp") or get_utc_now().isoformat()
            quality_meta = {
                "source": "fallback_15m",
                "volume_ratio": sig.get("volume_ratio"),
                "rsi14": sig.get("rsi14"),
                "atr14": sig.get("atr14"),
                "confirmation": sig.get("confirmation_reason"),
            }
            ok = self._db.insert_signal_log(
                symbol=sig["symbol"],
                entry=sig["entry_price"],
                stop=sig["sl_price"],
                tp1=sig["tp1_price"],
                tp2=sig["tp2_price"],
                entry_time=entry_time,
                leverage_used=int(sig["leverage"]) if sig.get("leverage") is not None else None,
                risk_pct_used=float(sig["risk_pct"]) if sig.get("risk_pct") is not None else None,
                entry_amount_usd=float(entry_amount_usd) if entry_amount_usd is not None else None,
                trade_mode=trade_mode,
                user_id=int(user_id) if user_id is not None else None,
                quality_meta=quality_meta,
            )
            if ok:
                saved += 1
        return saved

    def backtest(
        self,
        days: int = 30,
        max_horizon_bars: int = 16,
        entry_amount_usd: float = 100.0,
    ) -> Dict[str, any]:
        """Простой бэктест по историческим 15m данным."""
        report = {
            "config": dataclasses.asdict(self.config),
            "days": days,
            "entry_amount_usd": entry_amount_usd,
            "symbols": {},
            "totals": {
                "signals": 0,
                "tp1": 0,
                "tp2": 0,
                "sl": 0,
                "hold": 0,
                "pnl_usd": 0.0,
                "pnl_pct": 0.0,
                "sharpe": 0.0,
                "max_drawdown_pct": 0.0,
            },
        }

        pnl_history: List[float] = []
        equity = 1000.0
        peak = equity
        max_drawdown_pct = 0.0

        for symbol in self.config.symbols:
            df = self.fetch_data(symbol)
            if df is None or df.empty:
                continue
            df = df.sort_index()
            df = self.prepare_indicators(df)
            df1h = self._fetch_confirmation_data(symbol, days)
            symbol_stats = {
                "signals": 0,
                "tp1": 0,
                "tp2": 0,
                "sl": 0,
                "hold": 0,
                "pnl_usd": 0.0,
                "pnl_pct": 0.0,
                "avg_return_pct": 0.0,
                "win_rate": 0.0,
            }
            returns_pct: List[float] = []

            for idx in range(len(df) - 1):
                row = df.iloc[idx]
                if not self._meets_entry_conditions(row):
                    continue

                timestamp = df.index[idx]
                confirmed, _ = self.confirm_trend(symbol, timestamp=timestamp, data_1h=df1h)
                if not confirmed:
                    continue

                entry = float(row["close"])
                atr = float(row["atr14"])
                sl = entry - atr * self.config.atr_multiplier_sl
                tp1 = entry + atr * self.config.atr_multiplier_tp1
                tp2 = entry + atr * self.config.atr_multiplier_tp2

                future = df.iloc[idx + 1 : idx + 1 + max_horizon_bars]
                outcome = "HOLD"
                exit_price = float(future.iloc[-1]["close"]) if not future.empty else entry

                for _, frow in future.iterrows():
                    low = float(frow["low"])
                    high = float(frow["high"])
                    if low <= sl:
                        outcome = "SL"
                        exit_price = sl
                        break
                    if high >= tp2:
                        outcome = "TP2"
                        exit_price = tp2
                        break
                    if high >= tp1:
                        outcome = "TP1"
                        exit_price = tp1
                        break

                pnl_pct = (exit_price - entry) / entry
                pnl_usd = pnl_pct * entry_amount_usd

                symbol_stats["signals"] += 1
                symbol_stats["pnl_usd"] += pnl_usd
                symbol_stats["pnl_pct"] += pnl_pct
                returns_pct.append(pnl_pct)

                if outcome == "TP2":
                    symbol_stats["tp2"] += 1
                elif outcome == "TP1":
                    symbol_stats["tp1"] += 1
                elif outcome == "SL":
                    symbol_stats["sl"] += 1
                else:
                    symbol_stats["hold"] += 1

                equity += pnl_usd
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0.0
                if drawdown > max_drawdown_pct:
                    max_drawdown_pct = drawdown

                pnl_history.append(pnl_usd)

            if returns_pct:
                symbol_stats["avg_return_pct"] = sum(returns_pct) / len(returns_pct)
                wins = sum(1 for r in returns_pct if r > 0)
                symbol_stats["win_rate"] = wins / len(returns_pct) * 100

            report["symbols"][symbol] = symbol_stats
            report["totals"]["signals"] += symbol_stats["signals"]
            report["totals"]["tp1"] += symbol_stats["tp1"]
            report["totals"]["tp2"] += symbol_stats["tp2"]
            report["totals"]["sl"] += symbol_stats["sl"]
            report["totals"]["hold"] += symbol_stats["hold"]
            report["totals"]["pnl_usd"] += symbol_stats["pnl_usd"]
            report["totals"]["pnl_pct"] += symbol_stats["pnl_pct"]

        if pnl_history:
            mean = sum(pnl_history) / len(pnl_history)
            variance = sum((p - mean) ** 2 for p in pnl_history) / max(1, len(pnl_history) - 1)
            std = variance ** 0.5
            if std > 0:
                report["totals"]["sharpe"] = (mean / std) * (len(pnl_history) ** 0.5)
        report["totals"]["max_drawdown_pct"] = max_drawdown_pct * 100
        return report

    def to_signal_log(self, signal: Dict[str, any], params: Optional[Dict[str, any]] = None) -> Dict[str, any]:
        """Формирует запись для signals_log."""
        params = params or {}
        return {
            "symbol": signal["symbol"],
            "entry": signal["entry_price"],
            "stop": signal["sl_price"],
            "tp1": signal["tp1_price"],
            "tp2": signal["tp2_price"],
            "entry_time": signal.get("timestamp") or get_utc_now().isoformat(),
            "result": "PENDING",
            "net_profit": None,
            "qty_added": None,
            "qty_closed": None,
            "user_id": params.get("user_id"),
            "trade_mode": params.get("trade_mode", "spot"),
            "entry_amount_usd": params.get("entry_amount_usd"),
        }
