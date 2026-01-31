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

