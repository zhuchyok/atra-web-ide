#!/usr/bin/env python3
"""
🤖 ИИ-ОПТИМИЗАТОР TAKE PROFIT УРОВНЕЙ
Индивидуальная оптимизация TP для каждого сигнала на основе технических индикаторов
"""

import json
import logging
import os
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class AITakeProfitOptimizer:
    """ИИ-система для оптимизации Take Profit уровней"""

    def __init__(self, data_dir: str = "ai_tp_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Загружаем исторические данные эффективности TP
        self.tp_effectiveness = self._load_tp_effectiveness()

        # Загружаем все накопленные паттерны для ML оптимизации
        self.all_patterns = self._load_all_patterns()

        # Кэш для быстрого доступа к статистике паттернов
        self.pattern_cache = {}
        self.cache_timestamp = None

        # Веса для различных факторов
        self.factor_weights = {
            'volatility': 0.3,      # Волатильность
            'trend_strength': 0.25, # Сила тренда
            'volume_profile': 0.2,  # Профиль объема
            'support_resistance': 0.15, # Уровни поддержки/сопротивления
            'market_sentiment': 0.1,  # Рыночный сентимент
            'pattern_similarity': 0.35  # Похожесть на успешные паттерны
        }

        logger.info("🤖 ИИ-оптимизатор TP инициализирован")
        if self.all_patterns:
            logger.info("📊 Загружено %d паттернов для ML оптимизации", len(self.all_patterns))

    def _load_tp_effectiveness(self) -> Dict[str, Any]:
        """Загружает историческую эффективность TP для каждого символа"""
        file_path = os.path.join(self.data_dir, "tp_effectiveness.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Ошибка загрузки эффективности TP: %s", e)

        return {}

    def _load_all_patterns(self) -> List[Dict[str, Any]]:
        """Загружает все накопленные паттерны для ML оптимизации"""
        try:
            # Пробуем несколько возможных путей
            paths = [
                "ai_learning_data/trading_patterns.json",
                "../ai_learning_data/trading_patterns.json",
                "trading_patterns.json"
            ]

            for path in paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        patterns = json.load(f)
                        logger.info("📊 Загружено %d паттернов из %s", len(patterns), path)
                        return patterns

            logger.warning("⚠️ Файл trading_patterns.json не найден, паттерны не загружены")
            return []

        except Exception as e:
            logger.error("❌ Ошибка загрузки паттернов: %s", e)
            return []

    def _save_tp_effectiveness(self):
        """Сохраняет эффективность TP"""
        file_path = os.path.join(self.data_dir, "tp_effectiveness.json")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.tp_effectiveness, f, indent=2, ensure_ascii=False)
            logger.debug("💾 Эффективность TP сохранена")
        except Exception as e:
            logger.error("Ошибка сохранения эффективности TP: %s", e)

    def calculate_volatility_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор волатильности"""
        try:
            if current_index < 20:
                return 1.0

            # Анализируем волатильность за последние 20 свечей
            closes = df["close"].iloc[current_index - 20:current_index]
            volatility = closes.std() / closes.mean()

            # Нормализуем волатильность (0.01-0.1 -> 0.5-2.0)
            volatility_factor = np.clip(0.5 + volatility * 15, 0.5, 2.0)

            logger.debug("📊 Волатильность: %.4f, фактор: %.2f", volatility, volatility_factor)
            return volatility_factor

        except Exception as e:
            logger.error("Ошибка расчета волатильности: %s", e)
            return 1.0

    def calculate_trend_strength(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает силу тренда"""
        try:
            if current_index < 50:
                return 1.0

            # Анализируем EMA
            if 'ema_7' in df.columns and 'ema_25' in df.columns:
                ema_7 = df['ema_7'].iloc[current_index]
                ema_25 = df['ema_25'].iloc[current_index]
                current_price = df['close'].iloc[current_index]

                # Расстояние между EMA и ценой
                ema_distance = abs(ema_7 - ema_25) / current_price
                price_ema_distance = abs(current_price - ema_7) / current_price

                # Сила тренда (чем больше расстояние, тем сильнее тренд)
                trend_strength = np.clip(1 + ema_distance * 50 + price_ema_distance * 100, 0.5, 2.5)

                logger.debug("📈 Сила тренда: %.2f", trend_strength)
                return trend_strength
            else:
                return 1.0

        except Exception as e:
            logger.error("Ошибка расчета силы тренда: %s", e)
            return 1.0

    def calculate_volume_profile(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает профиль объема"""
        try:
            if current_index < 20:
                return 1.0

            # Анализируем объем за последние 20 свечей
            volumes = df["volume"].iloc[current_index - 20:current_index]
            current_volume = df["volume"].iloc[current_index]

            avg_volume = volumes.mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Высокий объем увеличивает вероятность достижения TP
            volume_factor = np.clip(0.7 + volume_ratio * 0.6, 0.7, 1.8)

            logger.debug("📊 Объем: %.2fx, фактор: %.2f", volume_ratio, volume_factor)
            return volume_factor

        except Exception as e:
            logger.error("Ошибка расчета объема: %s", e)
            return 1.0

    def calculate_support_resistance_factor(self, df: pd.DataFrame, current_index: int, side: str) -> float:
        """Рассчитывает фактор поддержки/сопротивления"""
        try:
            if current_index < 50:
                return 1.0

            # Анализируем уровни за последние 50 свечей
            highs = df["high"].iloc[current_index - 50:current_index]
            lows = df["low"].iloc[current_index - 50:current_index]
            current_price = df["close"].iloc[current_index]

            if side.lower() == "long":
                # Для LONG: смотрим на сопротивление (максимумы)
                resistance_levels = highs.nlargest(5).values
                closest_resistance = min(resistance_levels, key=lambda x: abs(x - current_price))

                # Если цена близко к сопротивлению, уменьшаем TP
                distance_to_resistance = (closest_resistance - current_price) / current_price
                resistance_factor = np.clip(0.8 + distance_to_resistance * 2, 0.8, 1.3)

            else:  # short
                # Для SHORT: смотрим на поддержку (минимумы)
                support_levels = lows.nsmallest(5).values
                closest_support = min(support_levels, key=lambda x: abs(x - current_price))

                # Если цена близко к поддержке, уменьшаем TP
                distance_to_support = (current_price - closest_support) / current_price
                support_factor = np.clip(0.8 + distance_to_support * 2, 0.8, 1.3)

                resistance_factor = support_factor

            logger.debug("🎯 Фактор S/R: %.2f", resistance_factor)
            return resistance_factor

        except Exception as e:
            logger.error("Ошибка расчета S/R: %s", e)
            return 1.0

    def calculate_market_sentiment_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор рыночного сентимента"""
        try:
            sentiment_factors = []

            # RSI сентимент
            if 'rsi' in df.columns:
                rsi = df['rsi'].iloc[current_index]
                if rsi > 70:  # Перекупленность
                    sentiment_factors.append(0.8)
                elif rsi < 30:  # Перепроданность
                    sentiment_factors.append(1.2)
                else:
                    sentiment_factors.append(1.0)

            # ADX сентимент
            if 'adx' in df.columns:
                adx = df['adx'].iloc[current_index]
                if adx > 30:  # Сильный тренд
                    sentiment_factors.append(1.2)
                elif adx < 20:  # Слабый тренд
                    sentiment_factors.append(0.9)
                else:
                    sentiment_factors.append(1.0)

            # Bollinger Bands сентимент
            if 'bb_position' in df.columns:
                bb_pos = df['bb_position'].iloc[current_index]
                if bb_pos == 'near_upper':  # Близко к верхней полосе
                    sentiment_factors.append(0.9)
                elif bb_pos == 'near_lower':  # Близко к нижней полосе
                    sentiment_factors.append(1.1)
                else:
                    sentiment_factors.append(1.0)

            # Средний сентимент
            if sentiment_factors:
                sentiment_factor = np.mean(sentiment_factors)
            else:
                sentiment_factor = 1.0

            logger.debug("😊 Сентимент: %.2f", sentiment_factor)
            return sentiment_factor

        except Exception as e:
            logger.error("Ошибка расчета сентимента: %s", e)
            return 1.0

    def get_symbol_effectiveness(self, symbol: str, side: str) -> Dict[str, float]:
        """Получает историческую эффективность TP для символа"""
        key = f"{symbol}_{side}"

        if key in self.tp_effectiveness:
            return self.tp_effectiveness[key]

        # Дефолтные значения для новых символов
        return {
            'tp1_success_rate': 0.6,
            'tp2_success_rate': 0.4,
            'avg_tp1_profit': 1.5,
            'avg_tp2_profit': 3.2,
            'optimal_tp1': 1.5,
            'optimal_tp2': 3.0
        }

    def update_symbol_effectiveness(self, symbol: str, side: str, tp1_hit: bool,
                                  tp2_hit: bool, profit_pct: float):
        """Обновляет эффективность TP для символа"""
        key = f"{symbol}_{side}"

        if key not in self.tp_effectiveness:
            self.tp_effectiveness[key] = {
                'tp1_hits': 0,
                'tp1_misses': 0,
                'tp2_hits': 0,
                'tp2_misses': 0,
                'total_profits': [],
                'optimal_tp1': 1.5,
                'optimal_tp2': 3.0
            }

        data = self.tp_effectiveness[key]

        # Обновляем статистику
        if tp1_hit:
            data['tp1_hits'] += 1
        else:
            data['tp1_misses'] += 1

        if tp2_hit:
            data['tp2_hits'] += 1
        else:
            data['tp2_misses'] += 1

        data['total_profits'].append(profit_pct)

        # Ограничиваем историю последними 100 сделками
        if len(data['total_profits']) > 100:
            data['total_profits'] = data['total_profits'][-100:]

        # Пересчитываем оптимальные TP
        self._recalculate_optimal_tp(data)

        # Сохраняем данные
        self._save_tp_effectiveness()

        logger.info("📊 Обновлена эффективность %s %s: TP1=%s, TP2=%s, прибыль=%.2f%%",
                    symbol, side, tp1_hit, tp2_hit, profit_pct)

    def _recalculate_optimal_tp(self, data: Dict[str, Any]):
        """Пересчитывает оптимальные TP на основе исторических данных"""
        if len(data['total_profits']) < 5:
            return

        profits = np.array(data['total_profits'])

        # Анализируем распределение прибылей
        tp1_profits = profits[profits <= 2.5]  # Предполагаем TP1 в районе 1.5-2.5%
        tp2_profits = profits[profits > 2.5]   # Предполагаем TP2 > 2.5%

        # Оптимальные TP на основе медианы успешных сделок
        if len(tp1_profits) > 0:
            data['optimal_tp1'] = float(np.percentile(tp1_profits, 75))

        if len(tp2_profits) > 0:
            data['optimal_tp2'] = float(np.percentile(tp2_profits, 75))

        # Рассчитываем success rate
        total_tp1 = data['tp1_hits'] + data['tp1_misses']
        total_tp2 = data['tp2_hits'] + data['tp2_misses']

        data['tp1_success_rate'] = data['tp1_hits'] / total_tp1 if total_tp1 > 0 else 0.6
        data['tp2_success_rate'] = data['tp2_hits'] / total_tp2 if total_tp2 > 0 else 0.4

    def find_similar_patterns(self, symbol: str, side: str, df: pd.DataFrame,
                              current_index: int, top_n: int = 1000) -> List[Dict[str, Any]]:
        """
        Находит похожие паттерны на основе текущих индикаторов

        Args:
            symbol: Символ
            side: LONG или SHORT
            df: DataFrame с данными
            current_index: Текущий индекс
            top_n: Количество лучших паттернов для возврата

        Returns:
            Список похожих паттернов с оценкой схожести
        """
        if not self.all_patterns:
            return []

        try:
            # Извлекаем текущие индикаторы
            current_indicators = self._extract_current_indicators(df, current_index)
            if not current_indicators:
                return []

            similar_patterns = []

            # Фильтруем паттерны по символу и направлению
            relevant_patterns = [
                p for p in self.all_patterns
                if p.get('symbol') == symbol and p.get('signal_type', '').upper() == side.upper()
            ]

            # Если нет паттернов для этого символа, используем все паттерны этого направления
            if not relevant_patterns:
                relevant_patterns = [
                    p for p in self.all_patterns
                    if p.get('signal_type', '').upper() == side.upper()
                ]

            # Рассчитываем схожесть для каждого паттерна
            for pattern in relevant_patterns:
                similarity_score = self._calculate_pattern_similarity(
                    current_indicators,
                    pattern.get('indicators', {})
                )

                if similarity_score > 0.3:  # Минимальный порог схожести
                    similar_patterns.append({
                        'pattern': pattern,
                        'similarity': similarity_score,
                        'profit_pct': pattern.get('profit_pct', 0),
                        'result': pattern.get('result', 'NEUTRAL')
                    })

            # Сортируем по схожести и результату
            similar_patterns.sort(key=lambda x: (x['similarity'], x['profit_pct']), reverse=True)

            return similar_patterns[:top_n]

        except Exception as e:
            logger.error("❌ Ошибка поиска похожих паттернов: %s", e)
            return []

    def _extract_current_indicators(self, df: pd.DataFrame, current_index: int) -> Dict[str, float]:
        """Извлекает текущие значения индикаторов"""
        try:
            if current_index >= len(df):
                return {}

            indicators = {}
            row = df.iloc[current_index]

            # Список индикаторов для сравнения
            indicator_keys = ['rsi', 'ema_7', 'ema_25', 'macd', 'bb_width', 'volume']

            for key in indicator_keys:
                if key in df.columns:
                    value = row[key]
                    if pd.notna(value) and np.isfinite(value):
                        indicators[key] = float(value)

            return indicators

        except Exception as e:
            logger.error("❌ Ошибка извлечения индикаторов: %s", e)
            return {}

    def _calculate_pattern_similarity(self, indicators1: Dict[str, float],
                                     indicators2: Dict[str, float]) -> float:
        """
        Рассчитывает схожесть между двумя наборами индикаторов

        Returns:
            Оценка схожести от 0 до 1
        """
        if not indicators1 or not indicators2:
            return 0.0

        try:
            similarities = []
            weights = {'rsi': 0.3, 'ema_7': 0.2, 'ema_25': 0.2, 'macd': 0.15, 'bb_width': 0.1, 'volume': 0.05}

            for key, weight in weights.items():
                if key in indicators1 and key in indicators2:
                    val1 = indicators1[key]
                    val2 = indicators2[key]

                    # Нормализуем значения в диапазон 0-1
                    if key == 'rsi':
                        val1_norm = val1 / 100.0
                        val2_norm = val2 / 100.0
                    elif key == 'volume':
                        # Для объема используем относительное сравнение
                        val1_norm = min(val1 / 1000000.0, 1.0)
                        val2_norm = min(val2 / 1000000.0, 1.0)
                    else:
                        # Для остальных индикаторов нормализуем по среднему значению
                        val1_norm = min(abs(val1), 100.0) / 100.0
                        val2_norm = min(abs(val2), 100.0) / 100.0

                    # Рассчитываем схожесть (чем ближе значения, тем выше схожесть)
                    similarity = 1.0 - abs(val1_norm - val2_norm)
                    similarities.append(similarity * weight)

            return sum(similarities) if similarities else 0.0

        except Exception as e:
            logger.error("❌ Ошибка расчета схожести: %s", e)
            return 0.0

    def calculate_optimal_tp_from_patterns(self, similar_patterns: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Рассчитывает оптимальные TP на основе успешных похожих паттернов

        Args:
            similar_patterns: Список похожих паттернов с оценками схожести

        Returns:
            Tuple[optimal_tp1, optimal_tp2] в процентах
        """
        if not similar_patterns:
            return 2.0, 4.0  # Дефолтные значения

        try:
            # Фильтруем только успешные паттерны
            successful_patterns = [
                p for p in similar_patterns
                if p.get('result') == 'WIN' and p.get('profit_pct', 0) > 0
            ]

            if not successful_patterns:
                # Если нет успешных, используем все
                successful_patterns = similar_patterns

            # Берем топ-100 самых похожих для анализа
            top_patterns = successful_patterns[:100]

            # Разделяем на TP1 и TP2
            tp1_profits = []
            tp2_profits = []

            for p in top_patterns:
                profit = p.get('profit_pct', 0)
                if 0 < profit <= 3.0:
                    tp1_profits.append(profit)
                elif profit > 3.0:
                    tp2_profits.append(profit)

            # Рассчитываем оптимальные TP на основе 75-го перцентиля
            if tp1_profits:
                optimal_tp1 = float(np.percentile(tp1_profits, 75))
            else:
                optimal_tp1 = 2.0

            if tp2_profits:
                optimal_tp2 = float(np.percentile(tp2_profits, 75))
            else:
                optimal_tp2 = 4.0

            # Ограничиваем разумными пределами
            optimal_tp1 = np.clip(optimal_tp1, 0.5, 5.0)
            optimal_tp2 = np.clip(optimal_tp2, 1.0, 8.0)

            # Убеждаемся, что TP2 > TP1
            if optimal_tp2 <= optimal_tp1:
                optimal_tp2 = optimal_tp1 * 1.5

            logger.debug("🎯 ML-оптимизация: TP1=%.2f%%, TP2=%.2f%% "
                        "(на основе %d паттернов: %d TP1, %d TP2)",
                        optimal_tp1, optimal_tp2, len(top_patterns),
                        len(tp1_profits), len(tp2_profits))

            return optimal_tp1, optimal_tp2

        except Exception as e:
            logger.error("❌ Ошибка расчета TP из паттернов: %s", e)
            return 2.0, 4.0

    def calculate_ai_optimized_tp(self, symbol: str, side: str, df: pd.DataFrame,
                                current_index: int, base_tp1: float = 1.5,
                                base_tp2: float = 3.0) -> Tuple[float, float]:
        """
        Рассчитывает ИИ-оптимизированные TP уровни для конкретного сигнала

        Args:
            symbol: Торговый символ
            side: LONG или SHORT
            df: DataFrame с данными свечей
            current_index: Текущий индекс свечи
            base_tp1: Базовый TP1 в процентах
            base_tp2: Базовый TP2 в процентах

        Returns:
            Tuple[float, float]: Оптимизированные TP1 и TP2 в процентах
        """
        try:
            logger.info("🤖 Рассчитываем ИИ-оптимизированные TP для %s %s", symbol, side)

            # 1. Получаем историческую эффективность символа
            effectiveness = self.get_symbol_effectiveness(symbol, side)

            # 2. Рассчитываем все факторы
            volatility_factor = self.calculate_volatility_factor(df, current_index)
            trend_strength_factor = self.calculate_trend_strength(df, current_index)
            volume_factor = self.calculate_volume_profile(df, current_index)
            sr_factor = self.calculate_support_resistance_factor(df, current_index, side)
            sentiment_factor = self.calculate_market_sentiment_factor(df, current_index)

            # 3. Комбинированный фактор (базовые индикаторы)
            base_combined_factor = (
                volatility_factor * self.factor_weights['volatility'] +
                trend_strength_factor * self.factor_weights['trend_strength'] +
                volume_factor * self.factor_weights['volume_profile'] +
                sr_factor * self.factor_weights['support_resistance'] +
                sentiment_factor * self.factor_weights['market_sentiment']
            )

            # 4. Учитываем историческую эффективность
            historical_tp1 = effectiveness.get('optimal_tp1', base_tp1)
            historical_tp2 = effectiveness.get('optimal_tp2', base_tp2)

            # 5. 🚀 НОВОЕ: ML-оптимизация на основе похожих паттернов
            pattern_tp1, pattern_tp2 = base_tp1, base_tp2
            pattern_confidence = 0.0

            if self.all_patterns:
                try:
                    # Ищем похожие паттерны
                    similar_patterns = self.find_similar_patterns(symbol, side, df, current_index, top_n=1000)

                    if similar_patterns:
                        # Рассчитываем оптимальные TP из паттернов
                        pattern_tp1, pattern_tp2 = self.calculate_optimal_tp_from_patterns(similar_patterns)

                        # Рассчитываем уверенность на основе качества паттернов
                        top_10 = similar_patterns[:10]
                        successful_count = sum(1 for p in top_10 if p.get('result') == 'WIN')
                        avg_similarity = np.mean([p['similarity'] for p in top_10])
                        pattern_confidence = (successful_count / 10) * avg_similarity

                        logger.info("🧠 ML-анализ: найдено %d похожих паттернов, уверенность=%.2f",
                                    len(similar_patterns), pattern_confidence)
                    else:
                        logger.debug("📊 ML-анализ: похожих паттернов не найдено, используем базовые значения")
                except Exception as e:
                    logger.warning("⚠️ Ошибка ML-оптимизации: %s, используем базовые индикаторы", e)

            # 6. Финальный расчет с учетом всех факторов
            # Если есть ML данные с высокой уверенностью - используем их, иначе классический подход
            if pattern_confidence > 0.5:
                # Высокая уверенность в ML - используем паттерны
                ai_tp1 = pattern_tp1 * 0.6 + historical_tp1 * 0.3 + base_tp1 * base_combined_factor * 0.1
                ai_tp2 = pattern_tp2 * 0.6 + historical_tp2 * 0.3 + base_tp2 * base_combined_factor * 0.1
                logger.info("🧠 Используем ML-оптимизацию (уверенность=%.2f)", pattern_confidence)
            else:
                # Низкая уверенность - используем классический подход
                ai_tp1 = historical_tp1 * 0.7 + base_tp1 * base_combined_factor * 0.3
                ai_tp2 = historical_tp2 * 0.7 + base_tp2 * base_combined_factor * 0.3
                if pattern_confidence > 0:
                    # Добавляем небольшую корректировку от ML
                    ai_tp1 = ai_tp1 * 0.9 + pattern_tp1 * 0.1
                    ai_tp2 = ai_tp2 * 0.9 + pattern_tp2 * 0.1

            # 7. Ограничиваем разумными пределами
            ai_tp1 = np.clip(ai_tp1, 0.5, 5.0)
            ai_tp2 = np.clip(ai_tp2, 1.0, 8.0)

            # 8. Убеждаемся, что TP2 > TP1
            if ai_tp2 <= ai_tp1:
                ai_tp2 = ai_tp1 * 1.5

            logger.info("🎯 ИИ-оптимизированные TP для %s: TP1=%.2f%%, TP2=%.2f%%",
                        symbol, ai_tp1, ai_tp2)
            logger.info("📊 Факторы: волатильность=%.2f, тренд=%.2f, объем=%.2f, ML уверенность=%.2f",
                        volatility_factor, trend_strength_factor, volume_factor, pattern_confidence)

            return ai_tp1, ai_tp2

        except Exception as e:
            logger.error("❌ Ошибка расчета ИИ-оптимизированных TP: %s", e)
            return base_tp1, base_tp2

    def get_ai_analysis_report(self, symbol: str, side: str, df: pd.DataFrame,
                             current_index: int) -> Dict[str, Any]:
        """Возвращает детальный анализ для принятия решения по TP"""
        try:
            effectiveness = self.get_symbol_effectiveness(symbol, side)

            volatility_factor = self.calculate_volatility_factor(df, current_index)
            trend_strength_factor = self.calculate_trend_strength(df, current_index)
            volume_factor = self.calculate_volume_profile(df, current_index)
            sr_factor = self.calculate_support_resistance_factor(df, current_index, side)
            sentiment_factor = self.calculate_market_sentiment_factor(df, current_index)

            analysis = {
                'symbol': symbol,
                'side': side,
                'timestamp': get_utc_now().isoformat(),
                'historical_effectiveness': effectiveness,
                'current_factors': {
                    'volatility_factor': volatility_factor,
                    'trend_strength_factor': trend_strength_factor,
                    'volume_factor': volume_factor,
                    'support_resistance_factor': sr_factor,
                    'sentiment_factor': sentiment_factor
                },
                'recommendation': self._generate_tp_recommendation(
                    effectiveness, volatility_factor, trend_strength_factor, volume_factor
                )
            }

            return analysis

        except Exception as e:
            logger.error("❌ Ошибка генерации анализа: %s", e)
            return {}

    def _generate_tp_recommendation(self, effectiveness: Dict, volatility_factor: float,
                                  trend_strength_factor: float, volume_factor: float) -> str:
        """Генерирует рекомендацию по TP"""
        recommendations = []

        if effectiveness.get('tp1_success_rate', 0.6) > 0.7:
            recommendations.append("✅ TP1 показывает высокую эффективность")
        elif effectiveness.get('tp1_success_rate', 0.6) < 0.5:
            recommendations.append("⚠️ TP1 показывает низкую эффективность")

        if volatility_factor > 1.5:
            recommendations.append("📈 Высокая волатильность - увеличить TP")
        elif volatility_factor < 0.8:
            recommendations.append("📉 Низкая волатильность - уменьшить TP")

        if trend_strength_factor > 1.5:
            recommendations.append("🚀 Сильный тренд - увеличить TP")

        if volume_factor > 1.3:
            recommendations.append("📊 Высокий объем - хорошие шансы на достижение TP")

        return "; ".join(recommendations) if recommendations else "📊 Стандартные параметры TP"

# Глобальный экземпляр ИИ-оптимизатора TP
ai_tp_optimizer = AITakeProfitOptimizer()
