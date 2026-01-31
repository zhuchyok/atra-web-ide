#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hybrid MTF Confirmation - гибридная система подтверждения на нескольких таймфреймах
ИСПРАВЛЕНО: Использует 4h вместо 3h (Binance поддерживает)
ДОБАВЛЕНО: Учет Solana в анализе рыночного импульса
"""

import logging
from typing import Dict, Tuple, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class HybridMTFConfirmation:
    """
    Гибридная система MTF подтверждения
    Основной таймфрейм: 4h (исправлено с 3h)
    Компенсация: H1 (1 час) для устранения запаздывания
    """

    def __init__(self, config: Dict):
        self.config = config
        self.mtf_config = config.get('HYBRID_MTF_CONFIG', {})

    def _validate_dataframe(self, df: pd.DataFrame, min_rows: int = 10, symbol: str = "") -> bool:
        """
        Валидация DataFrame перед использованием

        Args:
            df: DataFrame для проверки
            min_rows: Минимальное количество строк
            symbol: Символ для логирования

        Returns:
            bool: True если валидно
        """
        if df is None:
            logger.warning("⚠️ %s: DataFrame is None", symbol)
            return False

        if df.empty:
            logger.warning("⚠️ %s: DataFrame is empty", symbol)
            return False

        if len(df) < min_rows:
            logger.warning("⚠️ %s: Недостаточно строк (%d < %d)", symbol, len(df), min_rows)
            return False

        if 'close' not in df.columns:
            logger.warning("⚠️ %s: Отсутствует колонка 'close'", symbol)
            return False

        # Проверка на NaN
        if df['close'].isna().any():
            logger.warning("⚠️ %s: Обнаружены NaN значения в 'close'", symbol)
            return False

        # Проверка на некорректные значения
        if (df['close'] <= 0).any():
            logger.warning("⚠️ %s: Обнаружены некорректные цены (<= 0)", symbol)
            return False

        return True

    async def check_hybrid_mtf_confirmation(
        self,
        symbol: str,
        signal_type: str,
        df_h4: pd.DataFrame,
        df_h1: pd.DataFrame,
        market_context: Optional[Dict] = None
    ) -> Tuple[bool, float, Dict]:
        """
        Гибридная проверка MTF подтверждения

        Args:
            symbol: Торговый символ
            signal_type: Тип сигнала (LONG/SHORT)
            df_h4: Данные 4h таймфрейма (основной)
            df_h1: Данные 1h таймфрейма (компенсация)
            market_context: Контекст рынка

        Returns:
            confirmed: Подтвержден ли сигнал
            confidence: Уверенность (0-1)
            details: Детали расчета
        """
        try:
            # Валидация данных
            if not self._validate_dataframe(df_h4, min_rows=15, symbol=f"{symbol} H4"):
                return False, 0.0, {'error': 'invalid_h4_data'}

            if not self._validate_dataframe(df_h1, min_rows=30, symbol=f"{symbol} H1"):
                # H1 не критичен, используем только H4
                logger.warning("⚠️ %s: H1 данные недоступны, используем только H4", symbol)
                # 🔧 УЛУЧШЕНО: Для SHORT даем минимальный тренд вместо нейтрального 0.5
                if signal_type.upper() in ("SHORT", "SELL"):
                    h1_trend_strength = 0.2  # Минимальный тренд для fallback
                else:
                    h1_trend_strength = 0.5  # Нейтральный для LONG
                h1_details = {'error': 'insufficient_h1_data'}
            else:
                h1_trend_strength, h1_details = self._analyze_h1_trend_strength(
                    symbol, signal_type, df_h1
                )

            # 1. Проверка на основном 4h таймфрейме
            h4_confirmed, h4_confidence, h4_details = await self._check_h4_confirmation(
                symbol, signal_type, df_h4
            )

            # 2. Анализ рыночного контекста
            market_momentum = self._analyze_market_momentum(market_context)

            # 3. Применение гибридной компенсации
            hybrid_result = self._apply_hybrid_compensation(
                h4_confirmed, h4_confidence, h1_trend_strength, market_momentum, signal_type
            )

            final_confidence = hybrid_result['confidence']
            final_confirmed = hybrid_result['confirmed']

            details = {
                'primary_tf': '4h',
                'h4_confidence': h4_confidence,
                'h4_confirmed': h4_confirmed,
                'h1_trend_strength': h1_trend_strength,
                'market_momentum': market_momentum,
                'hybrid_boost': hybrid_result['boost_applied'],
                'final_confidence': final_confidence,
                'reason': hybrid_result['reason'],
                'h4_details': h4_details,
                'h1_details': h1_details
            }

            logger.info("🎯 Гибридный MTF %s %s: H4=%.2f, H1=%.2f, market=%.2f, final=%.2f",
                       symbol, signal_type, h4_confidence, h1_trend_strength,
                       market_momentum, final_confidence)

            return final_confirmed, final_confidence, details

        except Exception as e:
            logger.error("❌ Ошибка гибридного MTF для %s: %s", symbol, e, exc_info=True)
            # Fallback: стандартная проверка H4
            try:
                h4_confirmed, h4_confidence, h4_details = await self._check_h4_confirmation(
                    symbol, signal_type, df_h4
                )
                return h4_confirmed, h4_confidence, h4_details
            except Exception as fallback_error:
                logger.error("❌ Fallback также не сработал: %s", fallback_error)
                return False, 0.0, {'error': str(e), 'fallback_error': str(fallback_error)}

    async def _check_h4_confirmation(
        self,
        symbol: str,
        signal_type: str,
        df_h4: pd.DataFrame
    ) -> Tuple[bool, float, Dict]:
        """Проверка подтверждения на 4h таймфрейме"""
        try:
            # Дополнительная валидация
            if not self._validate_dataframe(df_h4, min_rows=15, symbol=symbol):
                return False, 0.0, {'error': 'insufficient_h4_data'}

            # Проверка длины перед iloc
            if len(df_h4) < 1:
                return False, 0.0, {'error': 'empty_dataframe'}

            current_price = float(df_h4['close'].iloc[-1])

            # EMA расчеты для 4h
            ema_fast = float(df_h4['close'].ewm(span=8).mean().iloc[-1])
            ema_slow = float(df_h4['close'].ewm(span=21).mean().iloc[-1])

            # MACD для 4h
            exp1 = df_h4['close'].ewm(span=12).mean()
            exp2 = df_h4['close'].ewm(span=26).mean()
            macd = exp1 - exp2
            signal_line = macd.ewm(span=9).mean()
            macd_histogram = macd - signal_line

            current_macd = float(macd.iloc[-1])
            current_signal = float(signal_line.iloc[-1])
            current_histogram = float(macd_histogram.iloc[-1])

            confidence = 0.0
            confirmed = False
            reason = ""

            if signal_type.upper() == "LONG":
                # Для LONG на 4h
                if current_price > ema_fast and ema_fast > ema_slow:
                    confidence = 0.85
                    confirmed = True
                    reason = "4h strong bullish trend"
                elif current_price > ema_slow and ema_fast > ema_slow:
                    confidence = 0.75
                    confirmed = True
                    reason = "4h bullish trend"
                elif current_price > ema_slow:
                    confidence = 0.65
                    confirmed = True
                    reason = "4h price above slow EMA"
                else:
                    # 🔧 УЛУЧШЕНО: Для LONG при отсутствии бычьего тренда анализируем боковой тренд
                    ema_diff_pct = abs(ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0

                    if ema_diff_pct < 0.01:  # Боковой тренд (<1% разница между EMA)
                        confidence = 0.45  # Нейтральный тренд - даем больше шансов компенсации
                        confirmed = False
                        reason = "4h sideways trend"
                    elif current_price > ema_slow * 0.98:  # Цена близко к медленной EMA (допуск 2%)
                        confidence = 0.35  # Слабый бычий тренд
                        confirmed = False
                        reason = "4h weak bullish trend"
                    else:
                        confidence = 0.25  # Слабый тренд, но не бычий
                        confirmed = False
                        reason = "4h not bullish (weak trend)"

                # Корректировка по MACD
                if current_macd > current_signal and current_histogram > 0:
                    confidence = min(1.0, confidence + 0.15)
                    reason += " + MACD bullish"
                elif current_macd < current_signal:
                    # 🔧 УЛУЧШЕНО: Не снижаем confidence ниже 0.2 для LONG (чтобы fallback мог сработать)
                    confidence = max(0.2, confidence - 0.05)  # Минимум 0.2 вместо 0.0
                    reason += " - MACD bearish"

            elif signal_type.upper() == "SHORT":
                # Для SHORT на 4h
                if current_price < ema_fast and ema_fast < ema_slow:
                    confidence = 0.85
                    confirmed = True
                    reason = "4h strong bearish trend"
                elif current_price < ema_slow and ema_fast < ema_slow:
                    confidence = 0.75
                    confirmed = True
                    reason = "4h bearish trend"
                elif current_price < ema_slow:
                    confidence = 0.65
                    confirmed = True
                    reason = "4h price below slow EMA"
                else:
                    # 🔧 УЛУЧШЕНО: Для SHORT при отсутствии медвежьего тренда анализируем боковой тренд
                    ema_diff_pct = abs(ema_fast - ema_slow) / ema_slow if ema_slow > 0 else 0

                    if ema_diff_pct < 0.01:  # Боковой тренд (<1% разница между EMA)
                        confidence = 0.45  # Нейтральный тренд - даем больше шансов компенсации
                        confirmed = False
                        reason = "4h sideways trend"
                    elif current_price < ema_slow * 1.02:  # Цена близко к медленной EMA (допуск 2%)
                        confidence = 0.35  # Слабый медвежий тренд
                        confirmed = False
                        reason = "4h weak bearish trend"
                    else:
                        confidence = 0.25  # Слабый тренд, но не медвежий
                        confirmed = False
                        reason = "4h not bearish (weak trend)"

                # Корректировка по MACD
                if current_macd < current_signal and current_histogram < 0:
                    confidence = min(1.0, confidence + 0.15)
                    reason += " + MACD bearish"
                elif current_macd > current_signal:
                    # 🔧 УЛУЧШЕНО: Не снижаем confidence ниже 0.2 для SHORT (чтобы fallback мог сработать)
                    confidence = max(0.2, confidence - 0.05)  # Минимум 0.2 вместо 0.0
                    reason += " - MACD bullish"

            # Минимальный порог уверенности для 4h
            # 🔧 ИСПРАВЛЕНО: Для SHORT сигналов используем более мягкий порог
            if signal_type.upper() == "SHORT":
                min_confidence = self.mtf_config.get('min_h4_confidence_short', 0.4)  # Снижено с 0.6 для SHORT
            else:
                min_confidence = self.mtf_config.get('min_h4_confidence', 0.6)
            confirmed = confirmed and confidence >= min_confidence

            details = {
                'confidence': confidence,
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'macd': current_macd,
                'macd_signal': current_signal,
                'macd_histogram': current_histogram,
                'reason': reason
            }

            return confirmed, confidence, details

        except Exception as e:
            logger.error("❌ Ошибка 4h подтверждения для %s: %s", symbol, e, exc_info=True)
            return False, 0.0, {'error': str(e)}

    def _analyze_h1_trend_strength(
        self,
        symbol: str,
        signal_type: str,
        df_h1: pd.DataFrame
    ) -> Tuple[float, Dict]:
        """Анализ силы тренда на H1 для компенсации"""
        try:
            if not self._validate_dataframe(df_h1, min_rows=30, symbol=symbol):
                return 0.5, {'error': 'insufficient_h1_data'}

            if len(df_h1) < 1:
                return 0.5, {'error': 'empty_dataframe'}

            current_price = float(df_h1['close'].iloc[-1])

            # Быстрые EMA для H1
            ema_9 = float(df_h1['close'].ewm(span=9).mean().iloc[-1])
            ema_21 = float(df_h1['close'].ewm(span=21).mean().iloc[-1])
            ema_50 = float(df_h1['close'].ewm(span=50).mean().iloc[-1])

            # RSI для импульса
            delta = df_h1['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

            # Защита от деления на ноль
            rs = gain / (loss + 1e-10)
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            # Объемный анализ
            volume_sma = float(df_h1['volume'].rolling(20).mean().iloc[-1])
            current_volume = float(df_h1['volume'].iloc[-1])
            volume_ratio = current_volume / (volume_sma + 1e-10) if volume_sma > 0 else 1.0

            # Волатильность на H1
            atr = float((df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-1])
            atr_pct = atr / (current_price + 1e-10) if current_price > 0 else 0

            trend_strength = 0.0
            details = {}

            if signal_type.upper() == "LONG":
                # 🔧 УЛУЧШЕНО: Более мягкие условия для бычьего тренда на H1 для LONG
                bullish_conditions = 0
                total_conditions = 5

                # Более мягкие условия с допусками
                if current_price > ema_9 * 0.99:  # Допуск 1% для слабого тренда
                    bullish_conditions += 1
                elif current_price > ema_9 * 0.98:  # Допуск 2% для очень слабого тренда
                    bullish_conditions += 0.5

                if ema_9 > ema_21 * 0.99:  # Допуск 1%
                    bullish_conditions += 1
                elif ema_9 > ema_21 * 0.98:  # Допуск 2%
                    bullish_conditions += 0.5

                if ema_21 > ema_50 * 0.99:  # Допуск 1%
                    bullish_conditions += 1
                elif ema_21 > ema_50 * 0.98:  # Допуск 2%
                    bullish_conditions += 0.5

                if rsi > 50:
                    bullish_conditions += 1
                elif rsi > 45:  # Более мягкое условие
                    bullish_conditions += 0.5
                if rsi > 60:
                    bullish_conditions += 0.5

                trend_strength = bullish_conditions / total_conditions

                # 🔧 УЛУЧШЕНО: Более агрессивное усиление при высоком объеме для LONG
                if volume_ratio > 1.5:
                    trend_strength = min(1.0, trend_strength + 0.25)  # Увеличено с 0.2
                elif volume_ratio > 1.2:
                    trend_strength = min(1.0, trend_strength + 0.15)  # Увеличено с 0.1
                elif volume_ratio > 1.0:
                    trend_strength = min(1.0, trend_strength + 0.05)  # Новое: минимальный boost

                # 🔧 ДОБАВЛЕНО: Минимальный trend_strength для LONG (чтобы fallback мог сработать)
                if trend_strength < 0.2:
                    trend_strength = 0.2  # Минимум 0.2 вместо 0.0

                details = {
                    'price_above_ema9': current_price > ema_9,
                    'ema9_above_ema21': ema_9 > ema_21,
                    'ema21_above_ema50': ema_21 > ema_50,
                    'rsi_bullish': rsi > 50,
                    'rsi_strong_bullish': rsi > 60,
                    'volume_boost': volume_ratio,
                    'rsi_value': rsi,
                    'atr_pct': atr_pct
                }

            elif signal_type.upper() == "SHORT":
                # 🔧 УЛУЧШЕНО: Более мягкие условия для медвежьего тренда на H1 для SHORT
                bearish_conditions = 0
                total_conditions = 5

                # Более мягкие условия с допусками
                if current_price < ema_9 * 1.01:  # Допуск 1% для слабого тренда
                    bearish_conditions += 1
                elif current_price < ema_9 * 1.02:  # Допуск 2% для очень слабого тренда
                    bearish_conditions += 0.5

                if ema_9 < ema_21 * 1.01:  # Допуск 1%
                    bearish_conditions += 1
                elif ema_9 < ema_21 * 1.02:  # Допуск 2%
                    bearish_conditions += 0.5

                if ema_21 < ema_50 * 1.01:  # Допуск 1%
                    bearish_conditions += 1
                elif ema_21 < ema_50 * 1.02:  # Допуск 2%
                    bearish_conditions += 0.5

                if rsi < 50:
                    bearish_conditions += 1
                elif rsi < 55:  # Более мягкое условие
                    bearish_conditions += 0.5
                if rsi < 40:
                    bearish_conditions += 0.5

                trend_strength = bearish_conditions / total_conditions

                # 🔧 УЛУЧШЕНО: Более агрессивное усиление при высоком объеме для SHORT
                if volume_ratio > 1.5:
                    trend_strength = min(1.0, trend_strength + 0.25)  # Увеличено с 0.2
                elif volume_ratio > 1.2:
                    trend_strength = min(1.0, trend_strength + 0.15)  # Увеличено с 0.1
                elif volume_ratio > 1.0:
                    trend_strength = min(1.0, trend_strength + 0.05)  # Новое: минимальный boost

                # 🔧 ДОБАВЛЕНО: Минимальный trend_strength для SHORT (чтобы fallback мог сработать)
                if trend_strength < 0.2:
                    trend_strength = 0.2  # Минимум 0.2 вместо 0.0

                details = {
                    'price_below_ema9': current_price < ema_9,
                    'ema9_below_ema21': ema_9 < ema_21,
                    'ema21_below_ema50': ema_21 < ema_50,
                    'rsi_bearish': rsi < 50,
                    'rsi_strong_bearish': rsi < 40,
                    'volume_boost': volume_ratio,
                    'rsi_value': rsi,
                    'atr_pct': atr_pct,
                    'bearish_conditions': bearish_conditions,
                    'trend_strength': trend_strength
                }

            return trend_strength, details

        except Exception as e:
            logger.error("❌ Ошибка анализа H1 тренда для %s: %s", symbol, e, exc_info=True)
            return 0.5, {'error': str(e)}

    def _analyze_market_momentum(self, market_context: Optional[Dict]) -> float:
        """
        Анализ общего импульса рынка
        ДОБАВЛЕНО: Учет Solana (SOL) в анализе
        """
        try:
            if not market_context:
                return 0.5

            # Анализ роста основных активов
            btc_change_12h = market_context.get('btc_change_12h', 0)
            eth_change_12h = market_context.get('eth_change_12h', 0)
            sol_change_12h = market_context.get('sol_change_12h', 0)  # ✅ ДОБАВЛЕНО
            market_regime = market_context.get('market_regime', 'NEUTRAL')
            overall_trend = market_context.get('overall_trend', 'NEUTRAL')

            momentum_score = 0.5  # Нейтральный

            # Учет роста BTC (вес 35%, было 40%)
            if btc_change_12h > 0.04:  # +4%
                momentum_score += 0.35
            elif btc_change_12h > 0.02:  # +2%
                momentum_score += 0.175
            elif btc_change_12h > 0.01:  # +1%
                momentum_score += 0.088
            elif btc_change_12h < -0.04:  # -4%
                momentum_score -= 0.35
            elif btc_change_12h < -0.02:  # -2%
                momentum_score -= 0.175

            # Учет роста ETH (вес 25%, было 30%)
            if eth_change_12h > 0.04:
                momentum_score += 0.25
            elif eth_change_12h > 0.02:
                momentum_score += 0.125
            elif eth_change_12h > 0.01:
                momentum_score += 0.063
            elif eth_change_12h < -0.04:
                momentum_score -= 0.25
            elif eth_change_12h < -0.02:
                momentum_score -= 0.125

            # ✅ ДОБАВЛЕНО: Учет роста SOL (вес 20%)
            if sol_change_12h > 0.04:  # +4%
                momentum_score += 0.2
            elif sol_change_12h > 0.02:  # +2%
                momentum_score += 0.1
            elif sol_change_12h > 0.01:  # +1%
                momentum_score += 0.05
            elif sol_change_12h < -0.04:  # -4%
                momentum_score -= 0.2
            elif sol_change_12h < -0.02:  # -2%
                momentum_score -= 0.1

            # Учет рыночного режима (вес 20%, было 30%)
            if market_regime == 'BULL_TREND' or overall_trend == 'BULLISH':
                momentum_score += 0.2
            elif market_regime == 'BEAR_TREND' or overall_trend == 'BEARISH':
                momentum_score -= 0.2

            # Ограничение диапазона
            momentum_score = max(0.0, min(1.0, momentum_score))

            return momentum_score

        except Exception:
            logger.error("❌ Ошибка анализа рыночного импульса", exc_info=True)
            return 0.5

    def _apply_hybrid_compensation(
        self,
        h4_confirmed: bool,
        h4_confidence: float,
        h1_trend_strength: float,
        market_momentum: float,
        signal_type: str
    ) -> Dict:
        """Применение гибридной компенсации"""

        # 🔧 ДОБАВЛЕНО: Логирование входных параметров для диагностики
        logger.info("🔍 _apply_hybrid_compensation: signal_type=%s, h4_confidence=%.6f, "
                   "h1_trend_strength=%.6f, market_momentum=%.6f",
                   signal_type, h4_confidence, h1_trend_strength, market_momentum)

        min_confidence = self.mtf_config.get('min_h4_confidence', 0.6)
        max_boost = self.mtf_config.get('max_hybrid_boost', 0.35)

        hybrid_boost = 0.0
        reason_parts = []

        # 1. Компенсация от силы тренда на H1
        # 🔧 ИСПРАВЛЕНО: Для SHORT сигналов более агрессивная компенсация
        # 🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: signal_type может быть "SELL" или "SHORT"
        is_short_compensation = signal_type.upper() in ("SHORT", "SELL")
        h1_threshold_multiplier = 0.8 if is_short_compensation else 1.0
        adjusted_h1_strength = h1_trend_strength * h1_threshold_multiplier

        if adjusted_h1_strength >= 0.9 or (is_short_compensation and h1_trend_strength >= 0.72):
            boost_amount = min(max_boost * 0.8, 0.28)
            hybrid_boost += boost_amount
            reason_parts.append(f"H1 сильный +{boost_amount:.2f}")
        elif adjusted_h1_strength >= 0.8 or (is_short_compensation and h1_trend_strength >= 0.64):
            boost_amount = min(max_boost * 0.6, 0.21)
            hybrid_boost += boost_amount
            reason_parts.append(f"H1 тренд +{boost_amount:.2f}")
        elif adjusted_h1_strength >= 0.7 or (is_short_compensation and h1_trend_strength >= 0.56):
            boost_amount = min(max_boost * 0.4, 0.14)
            hybrid_boost += boost_amount
            reason_parts.append(f"H1 умеренный +{boost_amount:.2f}")
        elif adjusted_h1_strength >= 0.6 or (is_short_compensation and h1_trend_strength >= 0.48):
            boost_amount = min(max_boost * 0.2, 0.07)
            hybrid_boost += boost_amount
            reason_parts.append(f"H1 слабый +{boost_amount:.2f}")

        # 2. Компенсация от рыночного импульса
        if market_momentum >= 0.8:
            boost_amount = min(max_boost * 0.5, 0.175)
            hybrid_boost += boost_amount
            reason_parts.append(f"Рынок сильный +{boost_amount:.2f}")
        elif market_momentum >= 0.7:
            boost_amount = min(max_boost * 0.3, 0.105)
            hybrid_boost += boost_amount
            reason_parts.append(f"Рынок +{boost_amount:.2f}")
        elif market_momentum >= 0.6:
            boost_amount = min(max_boost * 0.15, 0.052)
            hybrid_boost += boost_amount
            reason_parts.append(f"Рынок умеренный +{boost_amount:.2f}")
        elif market_momentum >= 0.3:
            # 🔧 ИСПРАВЛЕНО: Добавлен минимальный boost для низкого market_momentum
            boost_amount = min(max_boost * 0.1, 0.035)
            hybrid_boost += boost_amount
            reason_parts.append(f"Рынок базовый +{boost_amount:.2f}")

        hybrid_boost = min(hybrid_boost, max_boost)

        boosted_confidence = min(1.0, h4_confidence + hybrid_boost)

        # 🔧 УЛУЧШЕНО: Умный fallback для SHORT и LONG при низком H4 confidence
        # 🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: signal_type может быть "SELL", "SHORT", "BUY" или "LONG"
        is_short = signal_type.upper() in ("SHORT", "SELL")
        is_long = signal_type.upper() in ("LONG", "BUY")
        if (is_short or is_long) and h4_confidence < 0.4:  # Расширенный диапазон для fallback
            # Умный fallback с учетом всех факторов
            logger.info("🔧 %(signal_type)s Fallback check: H4=%(h4_confidence:.3f)s, H1=%(h1_trend_strength:.3f)s, market=%(market_momentum:.3f)s")

            fallback_score = 0.0
            fallback_reasons = []

            # Фактор 1: H1 тренд
            # 🔧 УЛУЧШЕНО: Даже при H1=0.0 даем минимальный балл, если есть минимальный тренд
            if h1_trend_strength >= 0.4:
                fallback_score += 0.3
                fallback_reasons.append(f"H1 strong ({h1_trend_strength:.2f})")
            elif h1_trend_strength >= 0.3:
                fallback_score += 0.2
                fallback_reasons.append(f"H1 moderate ({h1_trend_strength:.2f})")
            elif h1_trend_strength >= 0.2:
                fallback_score += 0.1
                fallback_reasons.append(f"H1 weak ({h1_trend_strength:.2f})")
            elif h1_trend_strength >= 0.1:
                fallback_score += 0.05  # Минимальный балл даже при очень слабом H1
                fallback_reasons.append(f"H1 very weak ({h1_trend_strength:.2f})")

            # Фактор 2: Рыночный импульс
            if market_momentum >= 0.5:
                fallback_score += 0.3
                fallback_reasons.append(f"Market strong ({market_momentum:.2f})")
            elif market_momentum >= 0.3:
                fallback_score += 0.25  # Увеличено с 0.2 для market=0.3
                fallback_reasons.append(f"Market moderate ({market_momentum:.2f})")
            elif market_momentum >= 0.2:
                fallback_score += 0.15  # Увеличено с 0.1
                fallback_reasons.append(f"Market weak ({market_momentum:.2f})")
            elif market_momentum >= 0.1:
                fallback_score += 0.05  # Минимальный балл
                fallback_reasons.append(f"Market very weak ({market_momentum:.2f})")

            # Фактор 3: Даже слабый H4 лучше чем 0.0
            if h4_confidence >= 0.2:
                fallback_score += 0.2
                fallback_reasons.append(f"H4 weak ({h4_confidence:.2f})")
            elif h4_confidence >= 0.1:
                fallback_score += 0.15  # Увеличено с 0.1
                fallback_reasons.append(f"H4 very weak ({h4_confidence:.2f})")
            elif h4_confidence > 0.0:
                fallback_score += 0.05  # Минимальный балл даже при H4 > 0
                fallback_reasons.append(f"H4 minimal ({h4_confidence:.2f})")

            # 🔧 УЛУЧШЕНО: Снижен порог для fallback и добавлен специальный случай для market >= 0.3
            # Если market >= 0.3, это уже достаточный сигнал для fallback
            if market_momentum >= 0.3:
                # Market >= 0.3 дает достаточно сигнала, даже если H1=0.0
                min_fallback_threshold = 0.25  # Снижено с 0.3
            else:
                min_fallback_threshold = 0.3

            # Применяем fallback если набрали достаточно баллов
            if fallback_score >= min_fallback_threshold:
                # Динамический boost в зависимости от fallback_score
                if fallback_score >= 0.6:
                    fallback_boost = 0.55  # Сильный fallback
                elif fallback_score >= 0.4:
                    fallback_boost = 0.50  # Средний fallback
                else:
                    fallback_boost = 0.45  # Слабый fallback

                boosted_confidence = max(boosted_confidence, fallback_boost)
                logger.info("✅ %s Fallback ПРИМЕНЕН (score=%.2f): "
                           "H4=%.3f, H1=%.3f, market=%.3f, boosted_confidence=%.3f, reasons=%s",
                           signal_type, fallback_score, h4_confidence, h1_trend_strength,
                           market_momentum, boosted_confidence, ', '.join(fallback_reasons))
                reason_parts.append(f"Fallback boost +{fallback_boost:.2f} (score={fallback_score:.2f})")
            else:
                logger.warning("⚠️ %s Fallback НЕ применен (score=%.2f < 0.3): "
                              "H1=%.3f, market=%.3f, H4=%.3f",
                              signal_type, fallback_score, h1_trend_strength,
                              market_momentum, h4_confidence)

        # 🔧 ИСПРАВЛЕНО: Для SHORT и LONG используем более мягкий min_confidence
        # 🔧 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: signal_type может быть "SELL", "SHORT", "BUY" или "LONG"
        if is_short:
            min_confidence_for_final = self.mtf_config.get('min_h4_confidence_short', 0.4)
        elif is_long:
            min_confidence_for_final = self.mtf_config.get('min_h4_confidence_long', 0.4)
        else:
            min_confidence_for_final = min_confidence

        final_confirmed = boosted_confidence >= min_confidence_for_final

        if not h4_confirmed and final_confirmed:
            reason = f"Гибридная компенсация: {h4_confidence:.2f}→{boosted_confidence:.2f} ({', '.join(reason_parts)})"
        elif h4_confirmed:
            reason = "4h подтвержден"
            if hybrid_boost > 0:
                reason += f" + усиление ({', '.join(reason_parts)})"
        else:
            reason = f"4h не подтвержден: {h4_confidence:.2f} < {min_confidence}"
            if hybrid_boost > 0:
                reason += f" (компенсация {hybrid_boost:.2f} недостаточна)"

        return {
            'confirmed': final_confirmed,
            'confidence': boosted_confidence,
            'boost_applied': hybrid_boost,
            'reason': reason
        }
