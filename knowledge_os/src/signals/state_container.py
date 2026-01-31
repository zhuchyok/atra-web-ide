"""
State containers for stateless signal processing.

This module provides state containers for managing state in stateless functions,
replacing module-level variables with explicit state management.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class FilterState:
    """
    State container for filter functions.
    
    This container holds state for filter functions, allowing them to be
    stateless while maintaining necessary state between calls.
    
    Attributes:
        cache: Cache for filter calculations (e.g., volume profile cache)
        stats: Statistics about filter operations
        previous_values: Previous values for indicators or calculations
        
    Example:
        ```python
        filter_state = FilterState()
        
        passed, reason, new_state = check_filter(
            data, filter_state=filter_state
        )
        ```
    """
    cache: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=dict)
    previous_values: Dict[str, Any] = field(default_factory=dict)
    
    def reset_stats(self) -> None:
        """Reset statistics to zero"""
        self.stats.clear()
    
    def increment_stat(self, key: str, value: int = 1) -> None:
        """
        Increment statistic counter.
        
        Args:
            key: Statistic key
            value: Value to increment by (default: 1)
        """
        self.stats[key] = self.stats.get(key, 0) + value
    
    def get_stat(self, key: str, default: int = 0) -> int:
        """
        Get statistic value.
        
        Args:
            key: Statistic key
            default: Default value if key doesn't exist
            
        Returns:
            Statistic value
        """
        return self.stats.get(key, default)


@dataclass
class IndicatorState:
    """
    State container for indicator calculations.
    
    This container holds previous values for indicators, allowing them to be
    calculated in a stateless manner.
    
    Attributes:
        prev_rsi: Previous RSI value
        prev_macd: Previous MACD value
        prev_ema_12: Previous EMA(12) value
        prev_ema_39: Previous EMA(39) value
        prev_ema_50: Previous EMA(50) value
        custom_values: Custom previous values for other indicators
        
    Example:
        ```python
        indicator_state = IndicatorState()
        
        indicators, new_state = calculate_indicators(
            df, state=indicator_state
        )
        ```
    """
    prev_rsi: Optional[float] = None
    prev_macd: Optional[float] = None
    prev_ema_12: Optional[float] = None
    prev_ema_39: Optional[float] = None
    prev_ema_50: Optional[float] = None
    custom_values: Dict[str, Any] = field(default_factory=dict)
    
    def get_prev_value(self, key: str) -> Optional[Any]:
        """
        Get previous value for custom indicator.
        
        Args:
            key: Indicator key
            
        Returns:
            Previous value or None
        """
        return self.custom_values.get(key)
    
    def set_prev_value(self, key: str, value: Any) -> None:
        """
        Set previous value for custom indicator.
        
        Args:
            key: Indicator key
            value: Previous value
        """
        self.custom_values[key] = value


@dataclass
class SignalState:
    """
    State container for signal generation.
    
    This container holds state for signal generation, including previous signals,
    cache, and statistics.
    
    Attributes:
        previous_signals: Previous signals for comparison
        cache: Cache for signal calculations
        stats: Statistics about signal generation
        
    Example:
        ```python
        signal_state = SignalState()
        
        signal, new_state = generate_signal(
            data, state=signal_state
        )
        ```
    """
    previous_signals: Dict[str, Any] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=dict)
    
    def add_previous_signal(self, key: str, signal: Any) -> None:
        """
        Add previous signal.
        
        Args:
            key: Signal key
            signal: Signal data
        """
        self.previous_signals[key] = signal
    
    def get_previous_signal(self, key: str) -> Optional[Any]:
        """
        Get previous signal.
        
        Args:
            key: Signal key
            
        Returns:
            Previous signal or None
        """
        return self.previous_signals.get(key)

