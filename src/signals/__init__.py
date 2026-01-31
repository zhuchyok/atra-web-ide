#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пакет сигналов ATRA
Рефакторинг signal_live.py на модули
"""

# Импорт всех модулей для удобного доступа
try:
    from src.signals.indicators import add_technical_indicators
except ImportError:
    def add_technical_indicators(*args, **kwargs):
        return None

try:
    from src.signals.validation import (
        calculate_direction_confidence,
        check_rsi_warning
    )
except ImportError:
    def calculate_direction_confidence(*args, **kwargs):
        return 0.5
    def check_rsi_warning(*args, **kwargs):
        return True

try:
    from src.signals.filters import check_btc_alignment, check_eth_alignment, check_sol_alignment
except ImportError:
    def check_btc_alignment(*args, **kwargs):
        return True, "fallback"
    def check_eth_alignment(*args, **kwargs):
        return True, "fallback"
    def check_sol_alignment(*args, **kwargs):
        return True, "fallback"
try:
    from src.signals.data import (
        get_symbol_data,
        load_user_data,
        get_symbols
    )
except ImportError:
    def get_symbol_data(*args, **kwargs):
        return None
    def load_user_data(*args, **kwargs):
        return {}
    def get_symbols(*args, **kwargs):
        return []

# Реэкспорт базовых функций
try:
    from src.signals.core import generate_signal_base as generate_signal
except ImportError:
    async def generate_signal(*args, **kwargs):
        return None

try:
    from src.signals.delivery import send_signal, check_and_send_signals
except ImportError:
    async def send_signal(*args, **kwargs):
        return False
    async def check_and_send_signals(*args, **kwargs):
        return False

try:
    from src.signals.system import (
        run_hybrid_signal_system_fixed,
        process_symbol_signals,
        health_check_correlations,
        periodic_health_check_correlations,
    )
except ImportError:
    async def run_hybrid_signal_system_fixed(*args, **kwargs):
        pass
    async def process_symbol_signals(*args, **kwargs):
        return []
    def health_check_correlations(*args, **kwargs):
        return True
    async def periodic_health_check_correlations(*args, **kwargs):
        pass

# State containers for stateless architecture
try:
    from src.signals.state_container import (
        FilterState,
        IndicatorState,
        SignalState,
    )
except ImportError:
    class FilterState:
        pass
    class IndicatorState:
        pass
    class SignalState:
        pass

__all__ = [
    # Indicators
    'add_technical_indicators',
    
    # Validation
    'calculate_direction_confidence',
    'check_rsi_warning',
    
    # Filters
    'check_btc_alignment',
    'check_eth_alignment',
    'check_sol_alignment',
    
    # Data
    'get_symbol_data',
    'load_user_data',
    'get_symbols',
    
    # Generation
    'generate_signal',
    
    # Delivery
    'send_signal',
    'check_and_send_signals',
    
    # System
    'run_hybrid_signal_system_fixed',
    'process_symbol_signals',
    'health_check_correlations',
    'periodic_health_check_correlations',
    
    # State containers
    'FilterState',
    'IndicatorState',
    'SignalState',
]
