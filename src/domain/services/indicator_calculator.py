"""
Indicator Calculator - Domain Service

Calculates technical indicators using Rust acceleration when available,
falls back to Python implementation otherwise.
"""

from typing import List, Tuple, Optional
from decimal import Decimal

from src.infrastructure.performance.rust_accelerator import (
    get_rust_accelerator,
    is_rust_available,
)


class IndicatorCalculator:
    """
    Domain Service for calculating technical indicators
    
    Uses Rust acceleration for 10-100x performance improvement.
    """
    
    def __init__(self):
        """Initialize indicator calculator"""
        self._rust = get_rust_accelerator()
        self._use_rust = is_rust_available()
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        Calculate RSI
        
        Args:
            prices: List of prices
            period: RSI period
            
        Returns:
            List of RSI values
        """
        if self._use_rust and self._rust:
            return self._rust.calculate_rsi(prices, period)
        else:
            return self._calculate_rsi_python(prices, period)
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate EMA
        
        Args:
            prices: List of prices
            period: EMA period
            
        Returns:
            List of EMA values
        """
        if self._use_rust and self._rust:
            return self._rust.calculate_ema(prices, period)
        else:
            return self._calculate_ema_python(prices, period)
    
    def calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate MACD
        
        Args:
            prices: List of prices
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal EMA period
            
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        if self._use_rust and self._rust:
            return self._rust.calculate_macd(prices, fast_period, slow_period, signal_period)
        else:
            return self._calculate_macd_python(prices, fast_period, slow_period, signal_period)
    
    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate Bollinger Bands
        
        Args:
            prices: List of prices
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        if self._use_rust and self._rust:
            return self._rust.calculate_bollinger_bands(prices, period, std_dev)
        else:
            return self._calculate_bollinger_bands_python(prices, period, std_dev)
    
    def calculate_atr(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int = 14,
    ) -> List[float]:
        """
        Calculate ATR
        
        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            period: ATR period
            
        Returns:
            List of ATR values
        """
        if self._use_rust and self._rust:
            return self._rust.calculate_atr(high, low, close, period)
        else:
            return self._calculate_atr_python(high, low, close, period)

    def calculate_adx(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int = 14,
    ) -> List[float]:
        """
        Calculate ADX (Average Directional Index)
        
        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            period: ADX period
            
        Returns:
            List of ADX values
        """
        if self._use_rust and self._rust and hasattr(self._rust, "calculate_adx"):
            return self._rust.calculate_adx(high, low, close, period)
        else:
            return self._calculate_adx_python(high, low, close, period)
    
    # Python fallback implementations
    def _calculate_rsi_python(self, prices: List[float], period: int) -> List[float]:
        """Python fallback for RSI"""
        if len(prices) < period + 1:
            return [50.0] * len(prices)
        
        rsi = [50.0] * period
        gains = [max(0, prices[i] - prices[i-1]) for i in range(1, len(prices))]
        losses = [max(0, prices[i-1] - prices[i]) for i in range(1, len(prices))]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        for i in range(period, len(prices)):
            if avg_loss == 0:
                rsi.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100.0 - (100.0 / (1.0 + rs)))
            
            if i < len(prices) - 1:
                avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        return rsi
    
    def _calculate_ema_python(self, prices: List[float], period: int) -> List[float]:
        """Python fallback for EMA"""
        if not prices:
            return []
        
        multiplier = 2.0 / (period + 1)
        ema = [sum(prices[:min(period, len(prices))]) / min(period, len(prices))]
        
        for price in prices[1:]:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
        
        return ema
    
    def _calculate_macd_python(
        self,
        prices: List[float],
        fast_period: int,
        slow_period: int,
        signal_period: int,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Python fallback for MACD"""
        fast_ema = self._calculate_ema_python(prices, fast_period)
        slow_ema = self._calculate_ema_python(prices, slow_period)
        
        macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
        signal_line = self._calculate_ema_python(macd_line, signal_period)
        histogram = [m - s for m, s in zip(macd_line, signal_line)]
        
        return (macd_line, signal_line, histogram)
    
    def _calculate_bollinger_bands_python(
        self,
        prices: List[float],
        period: int,
        std_dev: float,
    ) -> Tuple[List[float], List[float], List[float]]:
        """Python fallback for Bollinger Bands"""
        if len(prices) < period:
            return ([], [], [])
        
        upper, middle, lower = [], [], []
        
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            sma = sum(window) / period
            variance = sum((x - sma) ** 2 for x in window) / period
            std = variance ** 0.5
            
            middle.append(sma)
            upper.append(sma + std_dev * std)
            lower.append(sma - std_dev * std)
        
        # Pad beginning
        for _ in range(period - 1):
            upper.insert(0, prices[0])
            middle.insert(0, prices[0])
            lower.insert(0, prices[0])
        
        return (upper, middle, lower)

    def _calculate_atr_python(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int,
    ) -> List[float]:
        """Python fallback for ATR"""
        if len(high) < period + 1:
            return [0.0] * len(high)
        
        tr = [high[0] - low[0]]
        for i in range(1, len(high)):
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr.append(max(tr1, tr2, tr3))
        
        atr = [0.0] * period
        atr.append(sum(tr[1:period+1]) / period)
        
        for i in range(period + 1, len(tr)):
            atr.append((atr[-1] * (period - 1) + tr[i]) / period)
        
        return atr

    def _calculate_adx_python(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int,
    ) -> List[float]:
        """Python fallback for ADX"""
        if len(high) < 2 * period:
            return [25.0] * len(high)
        
        # Calculate +DM, -DM and TR
        plus_dm = [0.0]
        minus_dm = [0.0]
        tr = [0.0]
        
        for i in range(1, len(high)):
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            if up_move > down_move and up_move > 0:
                plus_dm.append(up_move)
            else:
                plus_dm.append(0.0)
                
            if down_move > up_move and down_move > 0:
                minus_dm.append(down_move)
            else:
                minus_dm.append(0.0)
                
            tr1 = high[i] - low[i]
            tr2 = abs(high[i] - close[i-1])
            tr3 = abs(low[i] - close[i-1])
            tr.append(max(tr1, tr2, tr3))
            
        # Smooth with EMA-like Wilder's Smoothing
        atr = self._calculate_ema_python(tr, 2 * period - 1) # Wilder uses 2n-1 period for EMA equiv
        plus_di = [100 * p / val if val > 0 else 0 for p, val in zip(self._calculate_ema_python(plus_dm, 2 * period - 1), atr)]
        minus_di = [100 * m / val if val > 0 else 0 for m, val in zip(self._calculate_ema_python(minus_dm, 2 * period - 1), atr)]
        
        dx = [100 * abs(p - m) / (p + m) if (p + m) > 0 else 0 for p, m in zip(plus_di, minus_di)]
        adx = self._calculate_ema_python(dx, 2 * period - 1)
        
        return adx

