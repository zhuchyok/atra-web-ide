#!/usr/bin/env python3
"""
🤖 ИИ-ОПТИМИЗАТОР STOP LOSS УРОВНЕЙ
Индивидуальная оптимизация SL для каждого сигнала на основе технических индикаторов
и исторических паттернов

Аналогично AITakeProfitOptimizer, но для оптимизации уровней стоп-лосса
"""

import json
import logging
import os
from typing import Dict, List, Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class AIStopLossOptimizer:
    """ИИ-система для оптимизации Stop Loss уровней"""

    def __init__(self, data_dir: str = "ai_sl_data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # Загружаем исторические данные эффективности SL
        self.sl_effectiveness = self._load_sl_effectiveness()

        # Загружаем все накопленные паттерны для ML оптимизации
        self.all_patterns = self._load_all_patterns()

        # Кэш для быстрого доступа к статистике паттернов
        self.pattern_cache = {}
        self.cache_timestamp = None

        # Веса для различных факторов
        self.factor_weights = {
            'volatility': 0.35,      # Волатильность (более важно для SL)
            'trend_strength': 0.2,   # Сила тренда
            'volume_profile': 0.15,  # Профиль объема
            'support_resistance': 0.2, # Уровни поддержки/сопротивления
            'pattern_similarity': 0.3  # Похожесть на успешные паттерны
        }

        logger.info("🤖 ИИ-оптимизатор SL инициализирован")
        if self.all_patterns:
            logger.info("📊 Загружено %d паттернов для ML оптимизации SL", len(self.all_patterns))

    def _load_sl_effectiveness(self) -> Dict[str, Any]:
        """Загружает историческую эффективность SL для каждого символа"""
        file_path = os.path.join(self.data_dir, "sl_effectiveness.json")

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Ошибка загрузки эффективности SL: %s", e)

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
                        logger.info("📊 Загружено %d паттернов из %s для SL", len(patterns), path)
                        return patterns

            logger.warning("⚠️ Файл trading_patterns.json не найден, паттерны не загружены")
            return []

        except Exception as e:
            logger.error("❌ Ошибка загрузки паттернов для SL: %s", e)
            return []

    def _save_sl_effectiveness(self):
        """Сохраняет эффективность SL"""
        file_path = os.path.join(self.data_dir, "sl_effectiveness.json")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.sl_effectiveness, f, indent=2, ensure_ascii=False)
            logger.debug("💾 Эффективность SL сохранена")
        except Exception as e:
            logger.error("Ошибка сохранения эффективности SL: %s", e)

    def calculate_volatility_factor(self, df: pd.DataFrame, current_index: int) -> float:
        """Рассчитывает фактор волатильности для SL"""
        try:
            if current_index < 20:
                return 1.0

            # Используем ATR для оценки волатильности
            if 'atr' in df.columns:
                atr = df['atr'].iloc[current_index]
                current_price = df['close'].iloc[current_index]

                if pd.notna(atr) and current_price > 0:
                    atr_pct = (atr / current_price) * 100

                    # Нормализуем волатильность: низкая (<1%) = 0.8x, нормальная (1-3%) = 1.0x, высокая (>3%) = 1.3x
                    if atr_pct < 1.0:
                        return 0.8  # Ужесточаем SL при низкой волатильности
                    elif atr_pct > 3.0:
                        return 1.3  # Ослабляем SL при высокой волатильности
                    else:
                        return 1.0

            return 1.0

        except Exception as e:
            logger.error("❌ Ошибка расчета фактора волатильности для SL: %s", e)
            return 1.0

    def find_similar_patterns_for_sl(self, symbol: str, side: str, df: pd.DataFrame,
                                     current_index: int, top_n: int = 100) -> List[Dict[str, Any]]:
        """
        Находит похожие паттерны для оптимизации SL
        
        Args:
            symbol: Символ
            side: LONG или SHORT
            df: DataFrame с данными
            current_index: Текущий индекс
            top_n: Количество лучших паттернов
            
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

            # Фильтруем паттерны по символу и стороне (если доступно)
            relevant_patterns = []
            for pattern in self.all_patterns:
                pattern_symbol = pattern.get('symbol', '')
                pattern_side = pattern.get('signal_type', '').upper()

                # Учитываем паттерны того же символа или всех символов если данных мало
                if pattern_symbol == symbol or len(self.all_patterns) < 50:
                    if pattern_side == side.upper() or not pattern_side:
                        relevant_patterns.append(pattern)

            if not relevant_patterns:
                return []

            # Рассчитываем схожесть для каждого паттерна
            similarities = []
            for pattern in relevant_patterns:
                pattern_indicators = pattern.get('indicators', {})
                similarity = self._calculate_pattern_similarity(current_indicators, pattern_indicators)

                similarities.append({
                    'pattern': pattern,
                    'similarity': similarity
                })

            # Сортируем по схожести и берем топ-N
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            top_patterns = similarities[:top_n]

            # Форматируем результат
            result = []
            for item in top_patterns:
                pattern = item['pattern']
                pattern['similarity_score'] = item['similarity']
                result.append(pattern)

            return result

        except Exception as e:
            logger.error("❌ Ошибка поиска похожих паттернов для SL: %s", e)
            return []

    def _extract_current_indicators(self, df: pd.DataFrame, current_index: int) -> Dict[str, float]:
        """Извлекает текущие значения индикаторов"""
        try:
            if current_index >= len(df):
                return {}

            indicators = {}
            row = df.iloc[current_index]

            # Список индикаторов для сравнения
            indicator_keys = ['rsi', 'ema_7', 'ema_25', 'macd', 'bb_width', 'volume', 'atr']

            for key in indicator_keys:
                if key in df.columns:
                    value = row[key]
                    if pd.notna(value) and np.isfinite(value):
                        indicators[key] = float(value)

            return indicators

        except Exception as e:
            logger.error("❌ Ошибка извлечения индикаторов для SL: %s", e)
            return {}

    def _calculate_pattern_similarity(self, indicators1: Dict[str, float],
                                     indicators2: Dict[str, float]) -> float:
        """Рассчитывает схожесть между двумя наборами индикаторов"""
        if not indicators1 or not indicators2:
            return 0.0

        try:
            similarities = []
            weights = {'rsi': 0.25, 'ema_7': 0.2, 'ema_25': 0.2, 'macd': 0.15,
                      'bb_width': 0.1, 'volume': 0.05, 'atr': 0.05}

            for key, weight in weights.items():
                if key in indicators1 and key in indicators2:
                    val1 = indicators1[key]
                    val2 = indicators2[key]

                    # Нормализуем значения
                    if key == 'rsi':
                        val1_norm = val1 / 100.0
                        val2_norm = val2 / 100.0
                    elif key == 'volume':
                        val1_norm = min(val1 / 1000000.0, 1.0)
                        val2_norm = min(val2 / 1000000.0, 1.0)
                    elif key == 'atr':
                        val1_norm = min(val1 / 100.0, 1.0)
                        val2_norm = min(val2 / 100.0, 1.0)
                    else:
                        val1_norm = min(abs(val1), 100.0) / 100.0
                        val2_norm = min(abs(val2), 100.0) / 100.0

                    similarity = 1.0 - abs(val1_norm - val2_norm)
                    similarities.append(similarity * weight)

            return sum(similarities) if similarities else 0.0

        except Exception as e:
            logger.error("❌ Ошибка расчета схожести для SL: %s", e)
            return 0.0

    def calculate_optimal_sl_from_patterns(self, similar_patterns: List[Dict[str, Any]],
                                          side: str = "long") -> float:
        """
        Рассчитывает оптимальный SL на основе похожих паттернов
        
        Args:
            similar_patterns: Список похожих паттернов
            side: LONG или SHORT
            
        Returns:
            Оптимальный SL в процентах
        """
        if not similar_patterns:
            return 2.0  # Дефолтное значение

        try:
            # Анализируем только паттерны, где SL сработал (были убытки)
            sl_patterns = []
            for p in similar_patterns:
                exit_reason = p.get('exit_reason', '').upper()
                sl_pct = p.get('stop_loss_pct')

                # Учитываем паттерны где SL сработал или где был SL установлен
                if exit_reason in ['SL', 'STOP_LOSS'] or (sl_pct and sl_pct > 0):
                    sl_patterns.append(p)

            # Если нет паттернов со SL, анализируем все убыточные
            if not sl_patterns:
                sl_patterns = [p for p in similar_patterns if p.get('result') == 'LOSS']

            if not sl_patterns:
                return 2.0

            # Анализируем оптимальный SL на основе успешных сделок (где SL не сработал)
            # и неуспешных (где SL сработал)
            successful_patterns = [p for p in similar_patterns if p.get('result') == 'WIN']
            failed_patterns = [p for p in similar_patterns if p.get('result') == 'LOSS']

            optimal_sl = 2.0

            if failed_patterns:
                # Анализируем убытки - SL должен быть меньше среднего убытка
                losses = []
                for p in failed_patterns:
                    profit_pct = p.get('profit_pct', 0)
                    if profit_pct < 0:
                        losses.append(abs(profit_pct))

                if losses:
                    # Оптимальный SL = 80% от среднего убытка (но не меньше 1%)
                    avg_loss = np.mean(losses)
                    optimal_sl = max(1.0, min(5.0, avg_loss * 0.8))

            if successful_patterns:
                # Анализируем успешные - SL не должен быть слишком тесным
                # Рассчитываем минимальный просадку в успешных сделках
                drawdowns = []
                for p in successful_patterns:
                    max_dd = p.get('max_drawdown', 0)
                    if max_dd > 0:
                        drawdowns.append(max_dd)

                if drawdowns:
                    # SL должен быть больше максимальной просадки в успешных сделках
                    max_dd = np.max(drawdowns)
                    optimal_sl = max(optimal_sl, max_dd * 1.2)

            # Ограничиваем разумными пределами: 0.8% - 8%
            optimal_sl = np.clip(optimal_sl, 0.8, 8.0)

            logger.debug("🎯 ML-оптимизация SL: %.2f%% (на основе %d паттернов: "
                        "%d успешных, %d убыточных)",
                        optimal_sl, len(similar_patterns),
                        len(successful_patterns), len(failed_patterns))

            return float(optimal_sl)

        except Exception as e:
            logger.error("❌ Ошибка расчета оптимального SL: %s", e)
            return 2.0

    def calculate_ai_optimized_sl(self, symbol: str, side: str, df: pd.DataFrame,
                                 current_index: int, base_sl: float = 2.0) -> float:
        """
        Рассчитывает ИИ-оптимизированный SL для конкретного сигнала
        
        Args:
            symbol: Торговый символ
            side: LONG или SHORT
            df: DataFrame с данными свечей
            current_index: Текущий индекс свечи
            base_sl: Базовый SL в процентах
            
        Returns:
            ИИ-оптимизированный SL в процентах
        """
        try:
            # 1. Фактор волатильности
            volatility_factor = self.calculate_volatility_factor(df, current_index)

            # 2. Находим похожие паттерны
            similar_patterns = self.find_similar_patterns_for_sl(symbol, side, df, current_index, top_n=100)

            # 3. Рассчитываем оптимальный SL из паттернов
            pattern_sl = self.calculate_optimal_sl_from_patterns(similar_patterns, side)

            # 4. Комбинируем: базовый SL + корректировка на основе паттернов + волатильность
            if similar_patterns:
                # Если есть паттерны, используем их как основу
                ai_sl = pattern_sl * volatility_factor
            else:
                # Если нет паттернов, корректируем базовый SL
                ai_sl = base_sl * volatility_factor

            # 5. Ограничиваем разумными пределами: 0.8% - 8%
            ai_sl = max(0.8, min(8.0, ai_sl))

            logger.debug("🤖 ИИ SL: базовый=%.2f%%, волатильность=%.2fx, "
                        "паттерны=%.2f%%, итоговый=%.2f%%",
                        base_sl, volatility_factor, pattern_sl, ai_sl)

            return float(ai_sl)

        except Exception as e:
            logger.error("❌ Ошибка расчета ИИ-оптимизированного SL: %s", e)
            return base_sl

    def update_sl_effectiveness(self, symbol: str, side: str, sl_pct: float,
                               sl_hit: bool, profit_pct: float):
        """
        Обновляет эффективность SL для символа
        
        Args:
            symbol: Символ
            side: LONG или SHORT
            sl_pct: Процент SL
            sl_hit: Сработал ли SL
            profit_pct: Прибыль/убыток в процентах
        """
        try:
            key = f"{symbol}_{side}"

            if key not in self.sl_effectiveness:
                self.sl_effectiveness[key] = {
                    'total_trades': 0,
                    'sl_hits': 0,
                    'sl_misses': 0,
                    'avg_loss_on_sl': [],
                    'avg_profit_on_miss': []
                }

            data = self.sl_effectiveness[key]
            data['total_trades'] += 1

            if sl_hit:
                data['sl_hits'] += 1
                if profit_pct < 0:
                    data['avg_loss_on_sl'].append(abs(profit_pct))
                    # Храним последние 100 значений
                    data['avg_loss_on_sl'] = data['avg_loss_on_sl'][-100:]
            else:
                data['sl_misses'] += 1
                if profit_pct > 0:
                    data['avg_profit_on_miss'].append(profit_pct)
                    # Храним последние 100 значений
                    data['avg_profit_on_miss'] = data['avg_profit_on_miss'][-100:]

            # Сохраняем данные
            self._save_sl_effectiveness()

        except Exception as e:
            logger.error("❌ Ошибка обновления эффективности SL: %s", e)


# Глобальный экземпляр оптимизатора
_AI_SL_OPTIMIZER = None  # pylint: disable=invalid-name

def get_ai_sl_optimizer() -> AIStopLossOptimizer:
    """Получает глобальный экземпляр AI SL оптимизатора"""
    global _AI_SL_OPTIMIZER  # pylint: disable=invalid-name
    if _AI_SL_OPTIMIZER is None:
        _AI_SL_OPTIMIZER = AIStopLossOptimizer()
    return _AI_SL_OPTIMIZER
