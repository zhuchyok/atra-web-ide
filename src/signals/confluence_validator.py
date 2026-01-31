#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфлюэнции (Confluences) для повышения Win Rate
Мировая практика: минимум 3-5 подтверждений для входа

Ответственный: Павел (Trading Strategy Developer)
"""

import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd
from decimal import Decimal

logger = logging.getLogger(__name__)


class ConfluenceValidator:
    """
    Валидатор конфлюэнций для повышения качества сигналов
    
    Мировые практики:
    - Минимум 3-5 подтверждений для входа
    - Уровни поддержки/сопротивления
    - Свечные паттерны
    - Multiple timeframe confirmation
    - Order flow imbalance
    - Liquidity zones
    """
    
    def __init__(self):
        self.min_confluences = 3  # Минимум 3 конфлюэнции
        self.required_confluences = {
            'strict': 3,  # Строгий режим: 3 конфлюэнции (было 5 - слишком строго)
            'soft': 2     # Мягкий режим: 2 конфлюэнции (было 3 - слишком строго)
        }
    
    def validate_confluences(
        self,
        symbol: str,
        signal_type: str,
        df: pd.DataFrame,
        current_price: float,
        filter_mode: str = 'strict',
        levels_detector: Optional[Any] = None,
        candle_detector: Optional[Any] = None,
        regime_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Валидация конфлюэнций для сигнала
        
        Returns:
            (passed, confluence_score, details)
        """
        try:
            # 🔧 ИСПРАВЛЕНО: Явная проверка пустого DataFrame
            if len(df) == 0:
                logger.warning(f"⚠️ [CONFLUENCE] {symbol} {signal_type}: Пустой DataFrame")
                min_required = self.required_confluences.get(filter_mode, 3)
                return False, 0.0, {
                    'error': 'Empty DataFrame',
                    'total_confluences': 0,
                    'required': min_required,
                    'confluences_list': []
                }
            
            confluences = []
            details = {}
            
            # 1. EMA CROSSOVER (базовая конфлюэнция)
            if len(df) >= 2:
                ema_fast = df['ema_fast'].iloc[-1] if 'ema_fast' in df.columns else None
                ema_slow = df['ema_slow'].iloc[-1] if 'ema_slow' in df.columns else None
                
                if ema_fast and ema_slow:
                    if signal_type == "BUY" and ema_fast > ema_slow:
                        confluences.append("ema_crossover")
                        details['ema_crossover'] = True
                    elif signal_type == "SELL" and ema_fast < ema_slow:
                        confluences.append("ema_crossover")
                        details['ema_crossover'] = True
                    else:
                        details['ema_crossover'] = False
            
            # 2. УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ (критично для Win Rate)
            if levels_detector:
                try:
                    levels = levels_detector.find_levels(df, lookback_period=100, min_touches=2)
                    
                    if signal_type == "BUY":
                        # Для LONG: цена должна быть близко к поддержке
                        supports = levels.get('support', [])
                        if supports:
                            nearest_support = min(supports, key=lambda x: abs(x['price'] - current_price))
                            distance_pct = abs(nearest_support['price'] - current_price) / current_price * 100
                            
                            # Цена в пределах 2% от поддержки = конфлюэнция (было 1% - слишком строго)
                            if distance_pct <= 2.0 and nearest_support['strength'] >= 1:
                                confluences.append("support_level")
                                details['support_level'] = {
                                    'level': nearest_support['price'],
                                    'strength': nearest_support['strength'],
                                    'distance_pct': distance_pct
                                }
                            else:
                                details['support_level'] = False
                        else:
                            details['support_level'] = False
                    
                    elif signal_type == "SELL":
                        # Для SHORT: цена должна быть близко к сопротивлению
                        resistances = levels.get('resistance', [])
                        if resistances:
                            nearest_resistance = min(resistances, key=lambda x: abs(x['price'] - current_price))
                            distance_pct = abs(nearest_resistance['price'] - current_price) / current_price * 100
                            
                            # Цена в пределах 2% от сопротивления = конфлюэнция (было 1% - слишком строго)
                            if distance_pct <= 2.0 and nearest_resistance['strength'] >= 1:
                                confluences.append("resistance_level")
                                details['resistance_level'] = {
                                    'level': nearest_resistance['price'],
                                    'strength': nearest_resistance['strength'],
                                    'distance_pct': distance_pct
                                }
                            else:
                                details['resistance_level'] = False
                        else:
                            details['resistance_level'] = False
                except Exception as e:
                    logger.debug(f"Ошибка проверки уровней для {symbol}: {e}")
                    details['levels'] = False
            
            # 3. СВЕЧНЫЕ ПАТТЕРНЫ (критично для Win Rate)
            if candle_detector:
                try:
                    if signal_type == "BUY":
                        bullish_patterns = candle_detector.detect_bullish_patterns(df)
                        has_bullish = any(bullish_patterns.values())
                        if has_bullish:
                            confluences.append("candle_pattern")
                            details['candle_pattern'] = bullish_patterns
                        else:
                            details['candle_pattern'] = False
                    elif signal_type == "SELL":
                        bearish_patterns = candle_detector.detect_bearish_patterns(df)
                        has_bearish = any(bearish_patterns.values())
                        if has_bearish:
                            confluences.append("candle_pattern")
                            details['candle_pattern'] = bearish_patterns
                        else:
                            details['candle_pattern'] = False
                except Exception as e:
                    logger.debug(f"Ошибка проверки свечных паттернов для {symbol}: {e}")
                    details['candle_pattern'] = False
            
            # 4. VOLUME CONFIRMATION (уже есть, но усилим)
            if 'volume_ratio' in df.columns:
                volume_ratio = df['volume_ratio'].iloc[-1]
                if volume_ratio > 1.2:  # Объем выше среднего на 20%
                    confluences.append("volume_confirmation")
                    details['volume_confirmation'] = True
                else:
                    details['volume_confirmation'] = False
            
            # 5. RSI CONFIRMATION (уже есть, но усилим)
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[-1]
                if signal_type == "BUY" and rsi < 40:  # Не перекуплен
                    confluences.append("rsi_confirmation")
                    details['rsi_confirmation'] = True
                elif signal_type == "SELL" and rsi > 60:  # Не перепродан
                    confluences.append("rsi_confirmation")
                    details['rsi_confirmation'] = True
                else:
                    details['rsi_confirmation'] = False
            
            # 6. MACD CONFIRMATION
            if 'macd' in df.columns and 'macd_signal' in df.columns:
                macd = df['macd'].iloc[-1]
                macd_signal = df['macd_signal'].iloc[-1]
                
                if signal_type == "BUY" and macd > macd_signal:
                    confluences.append("macd_confirmation")
                    details['macd_confirmation'] = True
                elif signal_type == "SELL" and macd < macd_signal:
                    confluences.append("macd_confirmation")
                    details['macd_confirmation'] = True
                else:
                    details['macd_confirmation'] = False
            
            # 7. TREND ALIGNMENT (BTC/ETH/SOL) - уже есть, но считаем как конфлюэнцию
            if regime_data:
                btc_trend = regime_data.get('btc_trend', 'NEUTRAL')
                if (signal_type == "BUY" and btc_trend == "BULLISH") or \
                   (signal_type == "SELL" and btc_trend == "BEARISH"):
                    confluences.append("trend_alignment")
                    details['trend_alignment'] = True
                else:
                    details['trend_alignment'] = False
            
            # 8. PULLBACK ENTRY (критично для Win Rate - вход на откате)
            if len(df) >= 10:
                # Проверяем, что цена откатилась к EMA перед входом
                ema = df['ema_fast'].iloc[-1] if 'ema_fast' in df.columns else None
                if ema:
                    if signal_type == "BUY":
                        # Для LONG: цена должна быть близко к EMA снизу (откат)
                        price_to_ema = (current_price - ema) / ema * 100
                        if -3.0 <= price_to_ema <= 1.0:  # Откат к EMA в пределах 3% (было 2% - слишком строго)
                            confluences.append("pullback_entry")
                            details['pullback_entry'] = True
                        else:
                            details['pullback_entry'] = False
                    elif signal_type == "SELL":
                        # Для SHORT: цена должна быть близко к EMA сверху (откат)
                        price_to_ema = (current_price - ema) / ema * 100
                        if -1.0 <= price_to_ema <= 3.0:  # Откат к EMA в пределах 3% (было 2% - слишком строго)
                            confluences.append("pullback_entry")
                            details['pullback_entry'] = True
                        else:
                            details['pullback_entry'] = False
            
            # Подсчитываем score
            confluence_score = len(confluences) / 8.0  # Максимум 8 конфлюэнций
            
            # Проверяем минимальное количество
            min_required = self.required_confluences.get(filter_mode, 3)
            passed = len(confluences) >= min_required
            
            details['total_confluences'] = len(confluences)
            details['required'] = min_required
            details['confluences_list'] = confluences
            details['score'] = confluence_score
            
            if passed:
                logger.info(
                    f"✅ [CONFLUENCE] {symbol} {signal_type}: {len(confluences)}/{min_required} конфлюэнций "
                    f"(score: {confluence_score:.2f})"
                )
            else:
                logger.warning(
                    f"🚫 [CONFLUENCE] {symbol} {signal_type}: {len(confluences)}/{min_required} конфлюэнций "
                    f"(требуется минимум {min_required})"
                )
            
            return passed, confluence_score, details
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации конфлюэнций для {symbol}: {e}", exc_info=True)
            return False, 0.0, {'error': str(e)}


# Singleton instance
_confluence_validator_instance: Optional[ConfluenceValidator] = None


def get_confluence_validator() -> ConfluenceValidator:
    """Получить экземпляр валидатора конфлюэнций"""
    global _confluence_validator_instance
    if _confluence_validator_instance is None:
        _confluence_validator_instance = ConfluenceValidator()
    return _confluence_validator_instance

