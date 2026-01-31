"""
Base strategy class for all trading strategies.
All strategies should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class TradingStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Attributes:
        name (str): Strategy name
        parameters (Dict): Strategy parameters
        data (pd.DataFrame): Market data
        positions (Dict): Current positions
        performance (Dict): Performance metrics
    """
    
    def __init__(self, name: str, parameters: Optional[Dict] = None):
        """
        Initialize the strategy.
        
        Args:
            name: Strategy name
            parameters: Strategy parameters dictionary
        """
        self.name = name
        self.parameters = parameters or {}
        self.data = pd.DataFrame()
        self.positions = {}
        self.performance = {}
        self.initialized = False
        
        # Initialize logging
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    def calculate_signals(self, data: pd.DataFrame) -> Dict:
        """
        Calculate trading signals based on market data.
        
        Args:
            data: Market data DataFrame
            
        Returns:
            Dictionary containing trading signals
        """
        pass
        
    @abstractmethod
    def execute(self, signals: Dict) -> None:
        """
        Execute trades based on signals.
        
        Args:
            signals: Trading signals dictionary
        """
        pass
        
    def update_data(self, data: pd.DataFrame) -> None:
        """
        Update market data for the strategy.
        
        Args:
            data: New market data
        """
        self.data = data.copy()
        self.logger.debug(f"Updated data with {len(data)} rows")
        
    def calculate_performance(self) -> Dict:
        """
        Calculate performance metrics for the strategy.
        
        Returns:
            Dictionary of performance metrics
        """
        # Basic performance metrics
        # @quant: Implement comprehensive performance calculation
        performance = {
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_return': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0
        }
        
        self.performance = performance
        return performance
        
    def validate_parameters(self) -> bool:
        """
        Validate strategy parameters.
        
        Returns:
            True if parameters are valid
        """
        # @quant: Add parameter validation logic
        required_params = self.get_required_parameters()
        
        for param in required_params:
            if param not in self.parameters:
                self.logger.error(f"Missing required parameter: {param}")
                return False
                
        return True
        
    @abstractmethod
    def get_required_parameters(self) -> List[str]:
        """
        Get list of required parameters for the strategy.
        
        Returns:
            List of required parameter names
        """
        pass
        
    def __str__(self) -> str:
        return f"TradingStrategy(name={self.name})"
        
    def __repr__(self) -> str:
        return f"TradingStrategy(name={self.name}, parameters={self.parameters})"
