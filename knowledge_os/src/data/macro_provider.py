import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class MacroProvider:
    """
    🌍 MACRO PROVIDER: Источник глобальных индикаторов (DXY).
    Оптимизирован для быстрой реакции на изменение ликвидности доллара.
    """

    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"

    def get_dxy_trend(self) -> dict:
        """Улучшенная логика определения тренда DXY"""
        try:
            dxy = yf.Ticker(self.dxy_ticker)
            df = dxy.history(period="6mo")

            if df.empty:
                return {"trend": "NEUTRAL", "value": 0, "change_pct": 0}

            current_price = df["Close"].iloc[-1]
            ma50 = df["Close"].rolling(window=50).mean().iloc[-1]
            ma200 = df["Close"].rolling(window=200).mean().iloc[-1]
            prev_price = df["Close"].iloc[-5]  # Цена неделю назад

            # 🚀 Новая адаптивная логика тренда
            if current_price < ma50:
                # Доллар под среднесрочной линией — это BEARISH (хорошо для BTC)
                trend = "BEARISH"
                strength = "STRONG" if ma50 < ma200 else "INITIAL"
            elif current_price > ma50:
                # Доллар выше линии — это BULLISH (риск для BTC)
                trend = "BULLISH"
                strength = "STRONG" if ma50 > ma200 else "INITIAL"
            else:
                trend = "NEUTRAL"
                strength = "NORMAL"

            # Скорректированный % изменения за сутки
            change_24h = ((current_price - df["Close"].iloc[-2]) / df["Close"].iloc[-2]) * 100
            # Динамика за неделю (momentum)
            momentum = "FALLING" if current_price < prev_price else "RISING"

            return {
                "trend": trend,
                "strength": strength,
                "momentum": momentum,
                "value": round(current_price, 2),
                "change_pct": round(change_24h, 2),
                "ma50": round(ma50, 2) if not pd.isna(ma50) else 0,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных DXY: {e}")
            return {"trend": "UNKNOWN", "value": 0, "change_pct": 0}


def get_macro_provider():
    return MacroProvider()
