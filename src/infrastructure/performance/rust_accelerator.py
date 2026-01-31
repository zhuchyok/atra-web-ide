"""
Rust Accelerator - Python Bindings for Rust Performance Module

This module provides high-performance implementations of trading indicators
and data processing using Rust (10-100x faster than pure Python).
"""

import os
import sys
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

# Try to import Rust module
try:
    import atra_rs
    
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    print("⚠️  Rust acceleration module not available. Install with: cd rust-atra && cargo build --release")


class RustAccelerator:
    """
    High-performance Rust-accelerated operations
    
    This class provides Python bindings to Rust implementations
    that are 10-100x faster than pure Python equivalents.
    """
    
    def __init__(self):
        """Initialize Rust accelerator"""
        self.available = RUST_AVAILABLE
        
        if not self.available:
            raise RuntimeError(
                "Rust module not available. "
                "Build with: cd rust-atra && cargo build --release"
            )
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """
        Calculate RSI using Rust (10-50x faster)
        
        Args:
            prices: List of prices
            period: RSI period (default 14)
            
        Returns:
            List of RSI values
        """
        return atra_rs.calculate_rsi(prices, period)
    
    def calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate EMA using Rust (10-30x faster)
        
        Args:
            prices: List of prices
            period: EMA period
            
        Returns:
            List of EMA values
        """
        return atra_rs.calculate_ema(prices, period)
    
    def calculate_macd(
        self,
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate MACD using Rust (10-40x faster)
        
        Args:
            prices: List of prices
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal EMA period
            
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        return atra_rs.calculate_macd(prices, fast_period, slow_period, signal_period)
    
    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Calculate Bollinger Bands using Rust (10-30x faster)
        
        Args:
            prices: List of prices
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        return atra_rs.calculate_bollinger_bands(prices, period, std_dev)
    
    def calculate_atr(
        self,
        high: List[float],
        low: List[float],
        close: List[float],
        period: int = 14,
    ) -> List[float]:
        """
        Calculate ATR using Rust (10-30x faster)
        
        Args:
            high: List of high prices
            low: List of low prices
            close: List of close prices
            period: ATR period
            
        Returns:
            List of ATR values
        """
        return atra_rs.calculate_atr(high, low, close, period)
    
    def process_ohlcv_batch(self, ohlcv_data: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """
        Process OHLCV data in parallel using Rust (5-20x faster)
        
        Args:
            ohlcv_data: List of OHLCV dictionaries
            
        Returns:
            Processed data with additional metrics
        """
        return atra_rs.process_ohlcv_batch(ohlcv_data)
    
    def calculate_indicators_batch(
        self,
        symbols_data: Dict[str, List[float]],
        indicator_config: Dict[str, Any],
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Calculate indicators for multiple symbols in parallel (10-50x faster)
        
        Args:
            symbols_data: Dictionary mapping symbol to price array
            indicator_config: Dictionary with indicator parameters
            
        Returns:
            Dictionary mapping symbol to calculated indicators
        """
        return atra_rs.calculate_indicators_batch(symbols_data, indicator_config)
    
    def filter_signals_parallel(
        self,
        signals: List[Dict[str, Any]],
        filters: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Filter signals in parallel using Rust (5-15x faster)
        
        Args:
            signals: List of signal dictionaries
            filters: Dictionary with filter criteria
            
        Returns:
            Filtered signals
        """
        return atra_rs.filter_signals_parallel(signals, filters)
    
    def calculate_sma(self, prices: List[float], period: int) -> List[float]:
        """
        Calculate SMA using Rust (10-30x faster)
        
        Args:
            prices: List of prices
            period: SMA period
            
        Returns:
            List of SMA values
        """
        return atra_rs.calculate_sma(prices, period)
    
    def calculate_momentum(self, prices: List[float], period: int = 10) -> List[float]:
        """
        Calculate Momentum using Rust (10-30x faster)
        
        Args:
            prices: List of prices
            period: Momentum period (default 10)
            
        Returns:
            List of Momentum values
        """
        return atra_rs.calculate_momentum(prices, period)
    
    def calculate_volume_ratio(
        self,
        current_volumes: List[float],
        avg_volumes: List[float],
    ) -> List[float]:
        """
        Calculate Volume Ratio using Rust (10-30x faster)
        
        Args:
            current_volumes: List of current volumes
            avg_volumes: List of average volumes
            
        Returns:
            List of Volume Ratio values
        """
        return atra_rs.calculate_volume_ratio(current_volumes, avg_volumes)
    
    def calculate_fear_greed_index(
        self,
        prices: List[float],
        volumes: List[float],
    ) -> List[float]:
        """
        Calculate Fear/Greed Index using Rust (10-30x faster)
        
        Args:
            prices: List of prices
            volumes: List of volumes
            
        Returns:
            List of Fear/Greed Index values
        """
        return atra_rs.calculate_fear_greed_index(prices, volumes)
    
    def calculate_trend_strength(
        self,
        prices: List[float],
        sma_short: int = 20,
        sma_long: int = 200,
    ) -> List[float]:
        """
        Calculate Trend Strength using Rust (10-40x faster)
        
        Args:
            prices: List of prices
            sma_short: Short SMA period (default 20)
            sma_long: Long SMA period (default 200)
            
        Returns:
            List of Trend Strength values
        """
        return atra_rs.calculate_trend_strength(prices, sma_short, sma_long)
    
    def calculate_volume_profile(
        self,
        volumes: List[float],
        prices: List[float],
        bins: int = 20,
    ) -> List[float]:
        """
        Calculate Volume Profile using Rust (10-30x faster)
        
        Args:
            volumes: List of volumes
            prices: List of prices
            bins: Number of bins for profile (default 20)
            
        Returns:
            Volume profile as List of floats (volume distribution)
        """
        return atra_rs.calculate_volume_profile(volumes, prices, bins)
    
    def calculate_vwap(
        self,
        prices: List[float],
        volumes: List[float],
    ) -> List[float]:
        """
        Calculate VWAP using Rust (10-30x faster)
        
        Args:
            prices: List of prices (typically close prices)
            volumes: List of volumes
            
        Returns:
            List of VWAP values
        """
        return atra_rs.calculate_vwap(prices, volumes)
    
    def calculate_market_profile(
        self,
        high: List[float],
        low: List[float],
        volume: List[float],
        bins: int = 30,
    ) -> List[float]:
        """
        Calculate Market Profile using Rust (10-30x faster)
        
        Args:
            high: List of high prices
            low: List of low prices
            volume: List of volumes
            bins: Number of price bins (default 30)
            
        Returns:
            Market profile as List of floats (volume distribution)
        """
        return atra_rs.calculate_market_profile(high, low, volume, bins)
    
    def check_btc_trend_filter(
        self,
        btc_prices: List[float],
        signal_direction: str,
        period: int = 20,
    ) -> Dict[str, Any]:
        """
        Check BTC trend filter using Rust (10-30x faster)
        
        Args:
            btc_prices: List of BTC prices
            signal_direction: "BUY" or "SELL"
            period: Trend period (default 20)
            
        Returns:
            Dictionary with passed, reason, and score
        """
        result = atra_rs.check_btc_trend_filter(btc_prices, signal_direction, period)
        return {
            'passed': result.passed,
            'reason': result.reason,
            'score': result.score
        }
    
    def check_momentum_filter(
        self,
        closes: List[float],
        volumes: List[float],
        signal_direction: str,
        period: int = 14,
    ) -> Dict[str, Any]:
        """
        Check momentum filter using Rust (10-30x faster)
        
        Args:
            closes: List of close prices
            volumes: List of volumes
            signal_direction: "BUY" or "SELL"
            period: Momentum period (default 14)
            
        Returns:
            Dictionary with passed, reason, and score
        """
        result = atra_rs.check_momentum_filter(closes, volumes, signal_direction, period)
        return {
            'passed': result.passed,
            'reason': result.reason,
            'score': result.score
        }
    
    def check_anomaly_filter(
        self,
        closes: List[float],
        volumes: List[float],
        lookback: int = 20,
        volume_threshold: float = 3.0,
        price_z_threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Check anomaly filter using Rust (10-30x faster)
        
        Args:
            closes: List of close prices
            volumes: List of volumes
            lookback: Lookback period (default 20)
            volume_threshold: Volume anomaly threshold (default 3.0)
            price_z_threshold: Price Z-score threshold (default 3.0)
            
        Returns:
            Dictionary with passed, reason, and score
        """
        result = atra_rs.check_anomaly_filter(closes, volumes, lookback, volume_threshold, price_z_threshold)
        return {
            'passed': result.passed,
            'reason': result.reason,
            'score': result.score
        }
    
    def check_volume_filter(
        self,
        volumes: List[float],
        min_volume_ratio: float = 1.2,
        period: int = 20,
    ) -> Dict[str, Any]:
        """
        Check volume filter using Rust (10-30x faster)
        
        Args:
            volumes: List of volumes
            min_volume_ratio: Minimum volume ratio (default 1.2)
            period: Period for average volume calculation (default 20)
            
        Returns:
            Dictionary with passed, reason, and score
        """
        result = atra_rs.check_volume_filter(volumes, min_volume_ratio, period)
        return {
            'passed': result.passed,
            'reason': result.reason,
            'score': result.score
        }
    
    def check_trend_strength_filter(
        self,
        closes: List[float],
        signal_direction: str,
        sma_short: int = 20,
        sma_long: int = 50,
        min_strength: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Check trend strength filter using Rust (10-40x faster)
        
        Args:
            closes: List of close prices
            signal_direction: "BUY" or "SELL"
            sma_short: Short SMA period (default 20)
            sma_long: Long SMA period (default 50)
            min_strength: Minimum trend strength (default 2.0)
            
        Returns:
            Dictionary with passed, reason, and score
        """
        result = atra_rs.check_trend_strength_filter(closes, signal_direction, sma_short, sma_long, min_strength)
        return {
            'passed': result.passed,
            'reason': result.reason,
            'score': result.score
        }
    
    def calculate_sniper_trend_signal(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        rsi_long_threshold: float = 60.0,
        rsi_short_threshold: float = 40.0,
        ema_period: int = 200,
        atr_period: int = 14,
        atr_multiplier: float = 1.5,
        rr_ratio: float = 3.5,
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Sniper Trend signal using Rust (10-50x faster)
        
        Args:
            closes: List of close prices
            highs: List of high prices
            lows: List of low prices
            volumes: List of volumes
            rsi_long_threshold: RSI threshold for long (default 60)
            rsi_short_threshold: RSI threshold for short (default 40)
            ema_period: EMA period for trend (default 200)
            atr_period: ATR period (default 14)
            atr_multiplier: ATR multiplier for SL (default 1.5)
            rr_ratio: Risk/Reward ratio (default 3.5)
            
        Returns:
            Dictionary with signal data or None
        """
        result = atra_rs.calculate_sniper_trend_signal(
            closes, highs, lows, volumes,
            rsi_long_threshold, rsi_short_threshold,
            ema_period, atr_period, atr_multiplier, rr_ratio
        )
        return result
    
    def detect_pattern(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        pattern_type: str,
        lookback: int = 20,
    ) -> Optional[Dict[str, float]]:
        """
        Detect pattern using Rust (10-30x faster)
        
        Args:
            closes: List of close prices
            highs: List of high prices
            lows: List of low prices
            pattern_type: Type of pattern ("support", "resistance", "breakout")
            lookback: Lookback period (default 20)
            
        Returns:
            Dictionary with pattern data or None
        """
        return atra_rs.detect_pattern(closes, highs, lows, pattern_type, lookback)
    
    def calculate_entry_timing(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        signal_direction: str,
    ) -> Optional[Dict[str, float]]:
        """
        Calculate entry timing using Rust (10-30x faster)
        
        Args:
            closes: List of close prices
            highs: List of high prices
            lows: List of low prices
            volumes: List of volumes
            signal_direction: "BUY" or "SELL"
            
        Returns:
            Dictionary with timing data or None
        """
        return atra_rs.calculate_entry_timing(closes, highs, lows, volumes, signal_direction)
    
    def calculate_exit_levels(
        self,
        entry_price: float,
        signal_direction: str,
        atr: float,
        atr_multiplier: float = 1.5,
        rr_ratio: float = 3.5,
    ) -> Dict[str, float]:
        """
        Calculate exit levels using Rust (10-30x faster)
        
        Args:
            entry_price: Entry price
            signal_direction: "BUY" or "SELL"
            atr: ATR value
            atr_multiplier: ATR multiplier for SL (default 1.5)
            rr_ratio: Risk/Reward ratio (default 3.5)
            
        Returns:
            Dictionary with exit levels
        """
        return atra_rs.calculate_exit_levels(entry_price, signal_direction, atr, atr_multiplier, rr_ratio)
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate Sharpe Ratio using Rust (10-30x faster)
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate (default 0.0)
            
        Returns:
            Sharpe Ratio
        """
        return atra_rs.calculate_sharpe_ratio(returns, risk_free_rate)
    
    def calculate_sortino_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.0,
    ) -> float:
        """
        Calculate Sortino Ratio using Rust (10-30x faster)
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate (default 0.0)
            
        Returns:
            Sortino Ratio
        """
        return atra_rs.calculate_sortino_ratio(returns, risk_free_rate)
    
    def calculate_max_drawdown(
        self,
        equity_curve: List[float],
    ) -> float:
        """
        Calculate Max Drawdown using Rust (10-30x faster)
        
        Args:
            equity_curve: List of equity values
            
        Returns:
            Max drawdown (as negative percentage)
        """
        return atra_rs.calculate_max_drawdown(equity_curve)
    
    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size using Rust (10-30x faster)
        
        Args:
            account_balance: Account balance
            risk_percent: Risk percentage (e.g., 2.0 for 2%)
            entry_price: Entry price
            stop_loss_price: Stop loss price
            
        Returns:
            Position size
        """
        return atra_rs.calculate_position_size(account_balance, risk_percent, entry_price, stop_loss_price)
    
    def calculate_correlation(
        self,
        prices1: List[float],
        prices2: List[float],
    ) -> float:
        """
        Calculate correlation using Rust (10-30x faster)
        
        Args:
            prices1: First price series
            prices2: Second price series
            
        Returns:
            Correlation coefficient (-1.0 to 1.0)
        """
        return atra_rs.calculate_correlation(prices1, prices2)
    
    def process_historical_data(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
    ) -> List[Any]:
        """
        Process historical data for backtesting using Rust (10-30x faster)
        
        Args:
            closes: List of close prices
            highs: List of high prices
            lows: List of low prices
            volumes: List of volumes
            
        Returns:
            List of OHLCVBar objects
        """
        return atra_rs.process_historical_data(closes, highs, lows, volumes)
    
    def calculate_backtest_metrics(
        self,
        pnl_series: List[float],
        returns: List[float],
        equity_curve: List[float],
    ) -> Dict[str, float]:
        """
        Calculate backtest metrics using Rust (10-50x faster)
        
        Args:
            pnl_series: List of PnL values
            returns: List of returns (as percentages)
            equity_curve: List of equity values
            
        Returns:
            Dictionary with all metrics
        """
        return atra_rs.calculate_backtest_metrics(pnl_series, returns, equity_curve)
    
    def calculate_trade_statistics(
        self,
        trades: List[Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Calculate trade statistics using Rust (10-30x faster)
        
        Args:
            trades: List of trade dictionaries
            
        Returns:
            Dictionary with trade statistics
        """
        return atra_rs.calculate_trade_statistics(trades)


# Global instance
_rust_accelerator: Optional[RustAccelerator] = None


def get_rust_accelerator() -> Optional[RustAccelerator]:
    """
    Get global Rust accelerator instance
    
    Returns:
        RustAccelerator instance or None if not available
    """
    global _rust_accelerator
    
    if _rust_accelerator is None and RUST_AVAILABLE:
        try:
            _rust_accelerator = RustAccelerator()
        except RuntimeError:
            pass
    
    return _rust_accelerator


def is_rust_available() -> bool:
    """Check if Rust acceleration is available"""
    return RUST_AVAILABLE

