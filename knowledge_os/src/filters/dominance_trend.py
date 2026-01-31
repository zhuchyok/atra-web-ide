"""
Dominance Trend Filter - фильтр на основе тренда доминации BTC
Блокирует LONG альтов при росте BTC.D, разрешает при падении (альтсезон)
"""

import logging
from typing import Dict, Any, Optional

from src.filters.base import BaseFilter, FilterResult
from src.market.dominance import get_dominance_analyzer, BTCDominanceAnalyzer

logger = logging.getLogger(__name__)


class DominanceTrendFilter(BaseFilter):
    """
    Фильтр тренда доминации BTC
    
    Логика:
    - LONG альты: разрешаем при падении BTC.D (альтсезон)
    - LONG альты: блокируем при росте BTC.D > порога
    - SHORT альты: разрешаем при росте BTC.D
    - SHORT альты: блокируем при падении BTC.D > порога
    """
    
    def __init__(
        self,
        enabled: bool = True,
        block_long_on_rising: bool = True,  # Блокировать LONG при росте BTC.D
        block_short_on_falling: bool = True,  # Блокировать SHORT при падении BTC.D
        dominance_threshold_pct: float = 1.0,  # Порог изменения доминации (%)
        min_days_for_trend: int = 1,  # Минимальное количество дней для определения тренда
    ):
        super().__init__(
            name="DominanceTrendFilter",
            enabled=enabled,
            priority=3  # Средний приоритет (после базовых фильтров)
        )
        self.block_long_on_rising = block_long_on_rising
        self.block_short_on_falling = block_short_on_falling
        self.dominance_threshold_pct = dominance_threshold_pct
        self.min_days_for_trend = min_days_for_trend
        self._analyzer: Optional[BTCDominanceAnalyzer] = None
    
    async def _get_analyzer(self) -> Optional[BTCDominanceAnalyzer]:
        """Получает анализатор доминации (ленивая инициализация)"""
        if self._analyzer is None:
            self._analyzer = await get_dominance_analyzer()
        return self._analyzer
    
    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """
        Фильтрует сигнал на основе тренда доминации BTC
        
        Args:
            signal_data: Данные сигнала
                - direction: "LONG" | "SHORT"
                - symbol: торговый символ (например, "ETHUSDT")
        
        Returns:
            FilterResult: Результат фильтрации
        """
        if not self.enabled:
            return FilterResult(passed=True, reason="FILTER_DISABLED")
        
        self.filter_stats['total_checked'] += 1
        
        try:
            direction = signal_data.get("direction", "").upper()
            symbol = signal_data.get("symbol", "")
            
            # Пропускаем BTC и ETH (они не альты относительно BTC)
            if symbol in ("BTCUSDT", "ETHUSDT"):
                return FilterResult(passed=True, reason="NOT_ALTCOIN")
            
            # Получаем данные доминации
            analyzer = await self._get_analyzer()
            if analyzer is None:
                logger.warning("⚠️ DominanceTrendFilter: анализатор недоступен, пропускаем фильтр")
                return FilterResult(passed=True, reason="ANALYZER_UNAVAILABLE")
            
            async with analyzer:
                dominance_data = await analyzer.get_current_dominance()
                
                if dominance_data is None:
                    logger.warning("⚠️ DominanceTrendFilter: данные доминации недоступны, пропускаем фильтр")
                    return FilterResult(passed=True, reason="DATA_UNAVAILABLE")
                
                # Получаем историю для определения тренда
                history_df = await analyzer.get_dominance_history(days=7)
                trend_info = analyzer.calculate_dominance_trend(history_df)
                
                trend = trend_info.get("trend", "neutral")
                change_pct = trend_info.get("change_pct", 0.0)
                
                # Принимаем решение на основе тренда
                if direction == "LONG":
                    # LONG альты: разрешаем при падении BTC.D (альтсезон)
                    if trend == "falling" and abs(change_pct) >= self.dominance_threshold_pct:
                        self.filter_stats['passed'] += 1
                        return FilterResult(
                            passed=True,
                            reason="ALT_SEASON",
                            details={
                                "trend": trend,
                                "change_pct": change_pct,
                                "btc_dominance": dominance_data.btc_dominance
                            }
                        )
                    
                    # LONG альты: блокируем при росте BTC.D
                    if self.block_long_on_rising and trend == "rising" and abs(change_pct) >= self.dominance_threshold_pct:
                        self.filter_stats['blocked'] += 1
                        return FilterResult(
                            passed=False,
                            reason="BTC_DOMINANCE_RISING",
                            details={
                                "trend": trend,
                                "change_pct": change_pct,
                                "btc_dominance": dominance_data.btc_dominance,
                                "message": f"BTC.D растет ({change_pct:.2f}%), альтсезон не активен"
                            }
                        )
                
                elif direction == "SHORT":
                    # SHORT альты: разрешаем при росте BTC.D
                    if trend == "rising" and abs(change_pct) >= self.dominance_threshold_pct:
                        self.filter_stats['passed'] += 1
                        return FilterResult(
                            passed=True,
                            reason="BTC_DOMINANCE_RISING",
                            details={
                                "trend": trend,
                                "change_pct": change_pct,
                                "btc_dominance": dominance_data.btc_dominance
                            }
                        )
                    
                    # SHORT альты: блокируем при падении BTC.D
                    if self.block_short_on_falling and trend == "falling" and abs(change_pct) >= self.dominance_threshold_pct:
                        self.filter_stats['blocked'] += 1
                        return FilterResult(
                            passed=False,
                            reason="ALT_SEASON",
                            details={
                                "trend": trend,
                                "change_pct": change_pct,
                                "btc_dominance": dominance_data.btc_dominance,
                                "message": f"BTC.D падает ({change_pct:.2f}%), альтсезон активен - не шортим"
                            }
                        )
                
                # Нейтральный тренд или изменение < порога - разрешаем
                self.filter_stats['passed'] += 1
                return FilterResult(
                    passed=True,
                    reason="NEUTRAL_TREND",
                    details={
                        "trend": trend,
                        "change_pct": change_pct,
                        "btc_dominance": dominance_data.btc_dominance
                    }
                )
                
        except Exception as e:
            logger.error("❌ Ошибка в DominanceTrendFilter: %s", e)
            self.filter_stats['errors'] += 1
            # При ошибке разрешаем сигнал (graceful degradation)
            return FilterResult(passed=True, reason="ERROR_FALLBACK", details={"error": str(e)})

