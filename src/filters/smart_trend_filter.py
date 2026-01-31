#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Умный фильтр трендов на основе корреляционных групп
Проверяет только релевантный тренд (BTC/ETH/SOL) в зависимости от корреляции монеты
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Импорты для проверки трендов
try:
    from src.signals.filters import (
        check_btc_alignment,
        check_eth_alignment,
        check_sol_alignment,
    )
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False
    logger.warning("⚠️ src.signals.filters недоступен, используем fallback")

# Импорт CorrelationManager
try:
    from src.risk.correlation_risk import CorrelationRiskManager
    # Создаем экземпляр если нужно, или используем синглтон
    _manager = CorrelationRiskManager()
    CORRELATION_MANAGER_AVAILABLE = True
except ImportError as e:
    CORRELATION_MANAGER_AVAILABLE = False
    logger.warning(f"⚠️ CorrelationRiskManager недоступен: {e}")


class SmartTrendFilter:
    """
    Умный фильтр трендов на основе корреляционных групп
    
    Логика:
    - Определяет корреляционную группу монеты (BTC_HIGH, ETH_HIGH, SOL_HIGH)
    - Проверяет только тренд того актива, с которым монета коррелирует
    - Fallback: если группа не определена, проверяет все три тренда
    """

    def __init__(self):
        """Инициализация умного фильтра трендов"""
        self.correlation_manager = None
        if CORRELATION_MANAGER_AVAILABLE:
            try:
                self.correlation_manager = get_correlation_manager()
                logger.info("✅ SmartTrendFilter: CorrelationManager загружен")
            except Exception as e:
                logger.warning("⚠️ SmartTrendFilter: не удалось загрузить CorrelationManager: %s", e)

        # Маппинг групп на тренды для проверки
        self.trend_mapping = {
            "BTC_HIGH": "BTC",
            "BTC_MEDIUM": "BTC",
            "BTC_LOW": "BTC",
            "BTC_INDEPENDENT": "BTC",  # Для независимых от BTC тоже проверяем BTC
            "ETH_HIGH": "ETH",
            "ETH_MEDIUM": "ETH",
            "ETH_LOW": "ETH",
            "ETH_INDEPENDENT": "ETH",
            "SOL_HIGH": "SOL",
            "SOL_MEDIUM": "SOL",
            "SOL_LOW": "SOL",
            "SOL_INDEPENDENT": "SOL",
        }

        # Статистика для мониторинга
        self.stats = {
            "total_checks": 0,
            "btc_only": 0,
            "eth_only": 0,
            "sol_only": 0,
            "all_three": 0,  # Fallback
            "errors": 0,
        }

    async def get_primary_trend_to_check(
        self, symbol: str, df: Optional[Any] = None
    ) -> str:
        """
        Определяет основной тренд для проверки на основе корреляционной группы
        
        Args:
            symbol: Торговый символ
            df: DataFrame с данными (опционально, для расчета корреляции)
            
        Returns:
            "BTC", "ETH", "SOL" или "ALL" (если группа не определена)
        """
        try:
            # Пытаемся получить корреляционную группу
            if self.correlation_manager:
                try:
                    symbol_group = await self.correlation_manager.get_symbol_group_async(
                        symbol, df
                    )
                    if symbol_group and symbol_group in self.trend_mapping:
                        primary_trend = self.trend_mapping[symbol_group]
                        logger.debug(
                            "🎯 [SMART_TREND] %s: группа=%s → проверяем %s тренд",
                            symbol,
                            symbol_group,
                            primary_trend,
                        )
                        return primary_trend
                    else:
                        logger.debug(
                            "⚠️ [SMART_TREND] %s: группа=%s не найдена в маппинге, используем ALL",
                            symbol,
                            symbol_group,
                        )
                except Exception as e:
                    logger.debug(
                        "⚠️ [SMART_TREND] %s: ошибка получения группы: %s, используем ALL",
                        symbol,
                        e,
                    )
            else:
                logger.debug(
                    "⚠️ [SMART_TREND] %s: CorrelationManager недоступен, используем ALL",
                    symbol,
                )

            # Fallback: если группа не определена, возвращаем "ALL"
            return "ALL"

        except Exception as e:
            logger.warning(
                "⚠️ [SMART_TREND] %s: ошибка определения тренда: %s, используем ALL",
                symbol,
                e,
            )
            return "ALL"

    async def check_trend_alignment(
        self, symbol: str, signal_type: str, df: Optional[Any] = None
    ) -> bool:
        """
        Проверяет соответствие сигнала релевантному тренду
        
        Args:
            symbol: Торговый символ
            signal_type: Тип сигнала (BUY/SELL)
            df: DataFrame с данными (опционально)
            
        Returns:
            True если сигнал соответствует тренду, False если нет
        """
        self.stats["total_checks"] += 1

        try:
            # Определяем основной тренд для проверки
            primary_trend = await self.get_primary_trend_to_check(symbol, df)

            # Проверяем только релевантный тренд
            if primary_trend == "BTC":
                self.stats["btc_only"] += 1
                result = await check_btc_alignment(symbol, signal_type)
                logger.info(
                    "🎯 [SMART_TREND] %s %s: проверка BTC тренда = %s",
                    symbol,
                    signal_type,
                    result,
                )
                return result

            elif primary_trend == "ETH":
                self.stats["eth_only"] += 1
                result = await check_eth_alignment(symbol, signal_type)
                logger.info(
                    "🎯 [SMART_TREND] %s %s: проверка ETH тренда = %s",
                    symbol,
                    signal_type,
                    result,
                )
                return result

            elif primary_trend == "SOL":
                self.stats["sol_only"] += 1
                result = await check_sol_alignment(symbol, signal_type)
                logger.info(
                    "🎯 [SMART_TREND] %s %s: проверка SOL тренда = %s",
                    symbol,
                    signal_type,
                    result,
                )
                return result

            else:
                # Fallback: проверяем все три тренда
                self.stats["all_three"] += 1
                logger.info(
                    "⚠️ [SMART_TREND] %s %s: группа не определена, проверяем все три тренда",
                    symbol,
                    signal_type,
                )

                btc_ok = await check_btc_alignment(symbol, signal_type)
                eth_ok = await check_eth_alignment(symbol, signal_type)
                sol_ok = await check_sol_alignment(symbol, signal_type)

                result = btc_ok and eth_ok and sol_ok
                logger.info(
                    "🎯 [SMART_TREND] %s %s: все три тренда (BTC=%s, ETH=%s, SOL=%s) = %s",
                    symbol,
                    signal_type,
                    btc_ok,
                    eth_ok,
                    sol_ok,
                    result,
                )
                return result

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(
                "❌ [SMART_TREND] %s: ошибка проверки тренда: %s, используем fallback (все три)",
                symbol,
                e,
            )
            # Fallback: проверяем все три тренда при ошибке
            try:
                btc_ok = await check_btc_alignment(symbol, signal_type)
                eth_ok = await check_eth_alignment(symbol, signal_type)
                sol_ok = await check_sol_alignment(symbol, signal_type)
                return btc_ok and eth_ok and sol_ok
            except Exception as fallback_error:
                logger.error(
                    "❌ [SMART_TREND] %s: ошибка fallback: %s, разрешаем сигнал",
                    symbol,
                    fallback_error,
                )
                return True  # В крайнем случае разрешаем сигнал

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику использования фильтра"""
        total = self.stats["total_checks"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "btc_only_pct": (self.stats["btc_only"] / total * 100) if total > 0 else 0,
            "eth_only_pct": (self.stats["eth_only"] / total * 100) if total > 0 else 0,
            "sol_only_pct": (self.stats["sol_only"] / total * 100) if total > 0 else 0,
            "all_three_pct": (self.stats["all_three"] / total * 100) if total > 0 else 0,
            "errors_pct": (self.stats["errors"] / total * 100) if total > 0 else 0,
        }


# Глобальный экземпляр (singleton)
_smart_trend_filter_instance: Optional[SmartTrendFilter] = None


def get_smart_trend_filter() -> SmartTrendFilter:
    """Возвращает глобальный экземпляр SmartTrendFilter (singleton)"""
    global _smart_trend_filter_instance
    if _smart_trend_filter_instance is None:
        _smart_trend_filter_instance = SmartTrendFilter()
    return _smart_trend_filter_instance

