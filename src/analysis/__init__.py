"""
Analysis modules - market structure, entry quality, advanced indicators
"""

# Безопасные импорты с fallback для модулей, требующих talib
try:
    from src.analysis.market_structure import MarketStructureAnalyzer
except ImportError:
    MarketStructureAnalyzer = None

try:
    from src.analysis.entry_quality import EntryQualityScorer
except ImportError:
    EntryQualityScorer = None

# Эти модули не требуют talib
from src.analysis.volume_profile import VolumeProfileAnalyzer
from src.analysis.vwap import VWAPCalculator

try:
    from src.analysis.auction_market_theory import AuctionMarketTheory, MarketPhase
except ImportError:
    AuctionMarketTheory = None
    MarketPhase = None

try:
    from src.analysis.market_profile import TimePriceOpportunity
except ImportError:
    TimePriceOpportunity = None

try:
    from src.analysis.vwt import VolumeWeightedTime
except ImportError:
    VolumeWeightedTime = None

__all__ = [
    'MarketStructureAnalyzer',
    'EntryQualityScorer',
    'VolumeProfileAnalyzer',
    'VWAPCalculator',
    'AuctionMarketTheory',
    'MarketPhase',
    'TimePriceOpportunity',
    'VolumeWeightedTime',
]
