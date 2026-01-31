#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML-оптимизатор фильтров на основе 50K паттернов
Использует машинное обучение для адаптивной настройки параметров фильтров
"""

import logging
import json
import os
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# ML библиотеки (опционально)
try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    import joblib
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("⚠️ scikit-learn не установлен, ML функции будут ограничены")


class MLFilterOptimizer:
    """
    ML-оптимизатор фильтров на основе исторических паттернов

    Логика:
    1. Загружает 50K паттернов из trading_patterns.json
    2. Обучает модель предсказывать успешность сигнала
    3. Оптимизирует параметры фильтров для текущих рыночных условий
    """

    def __init__(self, patterns_file: str = "ai_learning_data/trading_patterns.json"):
        self.patterns_file = patterns_file
        self.model = None
        self.scaler = StandardScaler() if ML_AVAILABLE else None
        self.patterns: List[Dict[str, Any]] = []
        self.is_trained = False

    def load_patterns(self) -> int:
        """Загружает паттерны из файла"""
        try:
            if not os.path.exists(self.patterns_file):
                logger.warning("⚠️ Файл паттернов не найден: %s", self.patterns_file)
                return 0

            with open(self.patterns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                self.patterns = data
                logger.info("✅ Загружено %d паттернов из %s", len(self.patterns), self.patterns_file)
                return len(self.patterns)
            else:
                logger.error("❌ Некорректный формат паттернов: ожидается список")
                return 0

        except Exception as e:
            logger.error("❌ Ошибка загрузки паттернов: %s", e)
            return 0

    def prepare_features(self, patterns: List[Dict[str, Any]]) -> tuple:
        """
        Подготавливает features для обучения модели

        Returns:
            (X, y) - features и target (успешность сигнала)
        """
        if not ML_AVAILABLE or not patterns:
            return None, None

        try:
            features = []
            targets = []

            for pattern in patterns:
                # Извлекаем features из паттерна
                feature_vector = self._extract_features(pattern)
                if feature_vector is None:
                    continue

                features.append(feature_vector)

                # Target: успешность сигнала (1 = WIN, 0 = LOSS)
                result = pattern.get('result', '')
                target = 1 if result == 'WIN' else 0
                targets.append(target)

            if not features:
                logger.warning("⚠️ Не удалось извлечь features из паттернов")
                return None, None

            # Стандартные имена для ML (X - features, y - target)
            features_array = np.array(features)  # pylint: disable=invalid-name
            targets_array = np.array(targets)  # pylint: disable=invalid-name

            logger.info(
                "✅ Подготовлено %d samples с %d features",
                len(features_array), features_array.shape[1]
            )
            return features_array, targets_array

        except Exception as e:
            logger.error("❌ Ошибка подготовки features: %s", e)
            return None, None

    def _extract_features(self, pattern: Dict[str, Any]) -> Optional[np.ndarray]:
        """Извлекает features из одного паттерна"""
        try:
            features = []

            # Индикаторы
            indicators = pattern.get('indicators', {})
            features.append(indicators.get('rsi', 50.0))
            features.append(indicators.get('ema_fast', 0.0))
            features.append(indicators.get('ema_slow', 0.0))
            features.append(indicators.get('macd', 0.0))
            features.append(indicators.get('bb_upper', 0.0))
            features.append(indicators.get('bb_lower', 0.0))

            # Рыночные условия
            market = pattern.get('market_conditions', {})
            features.append(1.0 if market.get('btc_trend', False) else 0.0)
            features.append(market.get('volume_ratio', 1.0))
            features.append(market.get('volatility', 0.0))

            # Параметры сигнала
            features.append(pattern.get('risk_pct', 2.0))
            features.append(pattern.get('leverage', 1.0))

            # Время (hour of day, day of week)
            timestamp = pattern.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
                    features.append(dt.hour)
                    features.append(dt.weekday())
                except Exception:
                    features.extend([12, 0])  # Default: noon, Monday
            else:
                features.extend([12, 0])

            return np.array(features)

        except Exception as e:
            logger.debug("⚠️ Ошибка извлечения features: %s", e)
            return None

    def train_model(self) -> bool:
        """Обучает модель на исторических паттернах"""
        if not ML_AVAILABLE:
            logger.warning("⚠️ ML библиотеки недоступны, обучение пропущено")
            return False

        try:
            # Загружаем паттерны
            pattern_count = self.load_patterns()
            if pattern_count < 100:
                logger.warning("⚠️ Недостаточно паттернов для обучения (нужно минимум 100, есть %d)", pattern_count)
                return False

            # Подготавливаем данные
            features_data, targets_data = self.prepare_features(self.patterns)
            if features_data is None or targets_data is None:
                return False

            # Разделяем на train/test (стандартные имена ML)
            # pylint: disable=invalid-name
            x_train, x_test, y_train, y_test = train_test_split(
                features_data, targets_data, test_size=0.2, random_state=42
            )

            # Нормализуем features
            x_train_scaled = self.scaler.fit_transform(x_train)
            x_test_scaled = self.scaler.transform(x_test)

            # Обучаем модель
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            self.model.fit(x_train_scaled, y_train)

            # Оцениваем качество
            train_score = self.model.score(x_train_scaled, y_train)
            test_score = self.model.score(x_test_scaled, y_test)

            logger.info("✅ Модель обучена: train_score=%.3f, test_score=%.3f", train_score, test_score)
            self.is_trained = True

            return True

        except Exception as e:
            logger.error("❌ Ошибка обучения модели: %s", e)
            return False

    def optimize_filter_parameters(
        self,
        current_market_conditions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Оптимизирует параметры фильтров для текущих рыночных условий

        Args:
            current_market_conditions: Текущие рыночные условия

        Returns:
            Оптимизированные параметры фильтров
        """
        if not self.is_trained or not self.model:
            logger.warning("⚠️ Модель не обучена, используем дефолтные параметры")
            return self._get_default_parameters()

        try:
            # Подготавливаем features для текущих условий
            pattern_template = {
                'indicators': current_market_conditions.get('indicators', {}),
                'market_conditions': current_market_conditions.get('market_conditions', {}),
                'risk_pct': current_market_conditions.get('risk_pct', 2.0),
                'leverage': current_market_conditions.get('leverage', 1.0),
                'timestamp': datetime.now().isoformat()
            }

            feature_vector = self._extract_features(pattern_template)
            if feature_vector is None:
                return self._get_default_parameters()

            # Предсказываем успешность
            features_scaled = self.scaler.transform([feature_vector])  # pylint: disable=invalid-name
            predicted_success = self.model.predict(features_scaled)[0]

            # Адаптируем параметры на основе предсказания
            # Если предсказание высокое (>0.6) - ослабляем фильтры
            # Если низкое (<0.4) - ужесточаем фильтры

            # 🆕 Получаем оптимальные веса для false_breakout
            optimal_weights = self.get_optimal_weights(current_market_conditions)

            if predicted_success > 0.6:
                # Хорошие условия - можно ослабить фильтры
                return {
                    'min_volume_ratio': 0.7,  # 🔧 ОСЛАБЛЕНО для интрадей (было 0.8)
                    'require_volume_confirmation': False,
                    'confidence_threshold': 0.58,  # 🔧 ОСЛАБЛЕНО (было 0.60)
                    'false_breakout_threshold': 0.15,  # 🆕 ML оптимизация false_breakout (было 0.20)
                    'false_breakout_weights': optimal_weights  # 🆕 ML оптимизация весов
                }
            elif predicted_success < 0.4:
                # Плохие условия - умеренно ужесточаем фильтры (для интрадей не слишком строго)
                return {
                    'min_volume_ratio': 0.9,  # 🔧 ДОПОЛНИТЕЛЬНО ОСЛАБЛЕНО для интрадей (было 1.1)
                    'require_volume_confirmation': False,  # 🔧 ОСЛАБЛЕНО: не требуем подтверждение в плохих условиях
                    'confidence_threshold': 0.70,  # 🔧 ОСЛАБЛЕНО (было 0.75)
                    'false_breakout_threshold': 0.25,  # 🆕 ML оптимизация false_breakout (было 0.20)
                    'false_breakout_weights': optimal_weights  # 🆕 ML оптимизация весов
                }
            else:
                # Средние условия - стандартные параметры (ослаблены для интрадей)
                return {
                    'min_volume_ratio': 0.8,  # 🔧 ДОПОЛНИТЕЛЬНО ОСЛАБЛЕНО для интрадей (было 1.0)
                    'require_volume_confirmation': False,  # 🔧 ОСЛАБЛЕНО: не требуем подтверждение в средних условиях
                    'confidence_threshold': 0.65,  # 🔧 ОСЛАБЛЕНО (было 0.68)
                    'false_breakout_threshold': 0.20,  # 🆕 ML оптимизация false_breakout (стандарт)
                    'false_breakout_weights': optimal_weights  # 🆕 ML оптимизация весов
                }

        except Exception as e:
            logger.error("❌ Ошибка оптимизации параметров: %s", e)
            return self._get_default_parameters()

    def optimize_ml_filter_thresholds(self) -> Dict[str, float]:
        """
        🆕 Оптимизирует пороги ML фильтра (min_success_prob, min_expected_profit)
        на основе исторических результатов из signals_log

        Returns:
            Dict с оптимальными порогами: {
                'min_success_prob': 0.4,
                'min_expected_profit': 0.3,
                'min_combined_score': 0.15
            }
        """
        try:
            db_path = "trading.db"
            if not os.path.exists(db_path):
                logger.debug("⚠️ База данных не найдена, используем дефолтные пороги ML")
                return self._get_default_ml_thresholds()

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Получаем последние закрытые сделки с результатами
            cursor.execute("""
                SELECT result, net_profit, entry, tp1, tp2, stop
                FROM signals_log
                WHERE entry > 0
                  AND result IN ('TP1', 'TP2', 'TP1_PARTIAL', 'TP2_REACHED', 'SL', 'SL_BE', 'CLOSED')
                ORDER BY created_at DESC
                LIMIT 500
            """)

            rows = cursor.fetchall()
            conn.close()

            if len(rows) < 50:
                logger.debug("⚠️ Недостаточно данных для оптимизации порогов ML (нужно минимум 50, есть %d)", len(rows))
                return self._get_default_ml_thresholds()

            # Анализируем результаты
            wins = 0
            losses = 0
            total_profit = 0.0
            total_loss = 0.0
            win_profits = []
            loss_profits = []

            for row in rows:
                result, net_profit, entry, _tp1, _tp2, _stop = row
                result_upper = str(result).upper() if result else ''

                # Определяем WIN/LOSS
                is_win = False
                profit_pct = 0.0

                if 'TP2' in result_upper:
                    is_win = True
                    profit_pct = 4.0
                elif 'TP1' in result_upper:
                    is_win = True
                    profit_pct = 2.0
                elif 'SL' in result_upper and 'BE' not in result_upper:
                    is_win = False
                    profit_pct = -2.0
                elif result_upper == 'CLOSED' and net_profit:
                    is_win = net_profit > 0
                    if entry:
                        profit_pct = (float(net_profit) / (float(entry) * 100)) * 100
                    else:
                        profit_pct = 2.0 if is_win else -2.0
                else:
                    continue  # Пропускаем неопределенные результаты

                if is_win:
                    wins += 1
                    total_profit += profit_pct
                    win_profits.append(profit_pct)
                else:
                    losses += 1
                    total_loss += abs(profit_pct)
                    loss_profits.append(profit_pct)

            if wins + losses < 30:
                msg = "⚠️ Недостаточно WIN/LOSS данных для оптимизации (нужно минимум 30, есть %d)"
                logger.debug(msg, wins + losses)
                return self._get_default_ml_thresholds()

            # Рассчитываем метрики
            win_rate = wins / (wins + losses)
            avg_win = total_profit / wins if wins > 0 else 0.0
            avg_loss = total_loss / losses if losses > 0 else 0.0
            profit_factor = total_profit / total_loss if total_loss > 0 else 0.0

            logger.info(
                "📊 [ML_THRESHOLDS] Анализ: Win Rate=%.1f%%, Avg Win=%.2f%%, Avg Loss=%.2f%%, Profit Factor=%.2f",
                win_rate * 100, avg_win, avg_loss, profit_factor
            )

            # Оптимизируем пороги на основе метрик
            # Если Win Rate высокий (>60%) и Profit Factor хороший (>1.5) - можно ослабить пороги
            # Если Win Rate низкий (<40%) или Profit Factor плохой (<1.0) - нужно ужесточить пороги

            if win_rate > 0.6 and profit_factor > 1.5:
                # Хорошие результаты - ослабляем пороги для большего количества сигналов
                min_success_prob = 0.35  # Было 0.4
                min_expected_profit = 0.25  # Было 0.3
                min_combined_score = 0.12  # Было 0.15
                logger.info("✅ [ML_THRESHOLDS] Хорошие результаты - ослабляем пороги для большего количества сигналов")
            elif win_rate < 0.4 or profit_factor < 1.0:
                # Плохие результаты - ужесточаем пороги для качества
                min_success_prob = 0.50  # Было 0.4
                min_expected_profit = 0.40  # Было 0.3
                min_combined_score = 0.20  # Было 0.15
                logger.info("⚠️ [ML_THRESHOLDS] Плохие результаты - ужесточаем пороги для качества")
            else:
                # Средние результаты - стандартные пороги
                min_success_prob = 0.4
                min_expected_profit = 0.3
                min_combined_score = 0.15
                logger.info("📊 [ML_THRESHOLDS] Средние результаты - используем стандартные пороги")

            return {
                'min_success_prob': min_success_prob,
                'min_expected_profit': min_expected_profit,
                'min_combined_score': min_combined_score
            }

        except Exception as e:
            logger.error("❌ Ошибка оптимизации порогов ML фильтра: %s", e)
            return self._get_default_ml_thresholds()

    def _get_default_ml_thresholds(self) -> Dict[str, float]:
        """Возвращает дефолтные пороги ML фильтра"""
        return {
            'min_success_prob': 0.4,
            'min_expected_profit': 0.3,
            'min_combined_score': 0.15
        }

    def _get_default_parameters(self) -> Dict[str, Any]:
        """Возвращает дефолтные параметры фильтров (ослаблены для интрадей)"""
        return {
            'min_volume_ratio': 0.7,  # 🔧 ДОПОЛНИТЕЛЬНО ОСЛАБЛЕНО для интрадей (было 1.0)
            'require_volume_confirmation': False,  # 🔧 ОСЛАБЛЕНО: не требуем подтверждение по умолчанию
            'confidence_threshold': 0.65,  # 🔧 ОСЛАБЛЕНО (было 0.68)
            'false_breakout_threshold': 0.20,  # 🆕 ML оптимизация false_breakout
            'false_breakout_weights': {  # 🆕 ML оптимизация весов
                'volume': 0.40,
                'momentum': 0.30,
                'level': 0.30
            }
        }

    def get_optimal_weights(
        self,
        market_conditions: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        🆕 ML-оптимизация весов для FalseBreakoutDetector

        Определяет оптимальные веса для volume/momentum/level на основе:
        - Рыночного режима
        - Волатильности
        - Времени суток
        - Исторических паттернов

        Args:
            market_conditions: Текущие рыночные условия

        Returns:
            Dict с весами: {'volume': 0.4, 'momentum': 0.3, 'level': 0.3}
        """
        try:
            # Извлекаем ключевые параметры
            regime = market_conditions.get('regime', 'UNKNOWN')
            volatility = market_conditions.get('volatility', 0.0)
            trend_strength = market_conditions.get('trend_strength', 0.5)

            # 🔧 ЭВРИСТИЧЕСКАЯ ЛОГИКА (работает всегда, даже без обученной модели)
            # В трендовом рынке: больше веса momentum
            # В волатильном: больше веса volume
            # В боковике: больше веса level

            if regime in ('BULL_TREND', 'BEAR_TREND'):
                # Трендовый рынок: momentum важнее
                weights = {
                    'volume': 0.30,
                    'momentum': 0.45,  # 🆕 Больше веса в тренде
                    'level': 0.25
                }
            elif volatility > 1.5:  # 🔧 Исправлено: волатильность в процентах (1.5% = высокая)
                # Высокая волатильность: volume важнее
                weights = {
                    'volume': 0.50,  # 🆕 Больше веса при волатильности
                    'momentum': 0.25,
                    'level': 0.25
                }
            elif trend_strength < 0.3:
                # Боковик: level важнее
                weights = {
                    'volume': 0.30,
                    'momentum': 0.20,
                    'level': 0.50  # 🆕 Больше веса в боковике
                }
            else:
                # Стандартные веса
                weights = {
                    'volume': 0.40,
                    'momentum': 0.30,
                    'level': 0.30
                }

            # Нормализуем веса (сумма = 1.0)
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}

            logger.debug(
                "🤖 [ML_WEIGHTS] Оптимальные веса для режима %s (vol=%.2f): volume=%.2f, momentum=%.2f, level=%.2f",
                regime, volatility, weights['volume'], weights['momentum'], weights['level']
            )

            return weights

        except Exception as e:
            logger.debug("⚠️ [ML_WEIGHTS] Ошибка оптимизации весов, используем стандартные: %s", e)
            return {
                'volume': 0.40,
                'momentum': 0.30,
                'level': 0.30
            }

    def save_model(self, model_path: str = "ai_learning_data/ml_filter_model.pkl"):
        """Сохраняет обученную модель"""
        if not self.is_trained or not self.model:
            logger.warning("⚠️ Нет обученной модели для сохранения")
            return False

        try:
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            joblib.dump({
                'model': self.model,
                'scaler': self.scaler
            }, model_path)
            logger.info("✅ Модель сохранена: %s", model_path)
            return True
        except Exception as e:
            logger.error("❌ Ошибка сохранения модели: %s", e)
            return False

    def load_model(self, model_path: str = "ai_learning_data/ml_filter_model.pkl") -> bool:
        """Загружает обученную модель"""
        if not ML_AVAILABLE:
            return False

        try:
            if not os.path.exists(model_path):
                logger.warning("⚠️ Файл модели не найден: %s", model_path)
                return False

            data = joblib.load(model_path)
            self.model = data['model']
            self.scaler = data['scaler']
            self.is_trained = True

            logger.info("✅ Модель загружена: %s", model_path)
            return True
        except Exception as e:
            logger.error("❌ Ошибка загрузки модели: %s", e)
            return False


# Глобальный экземпляр
_ml_optimizer_instance: Optional[MLFilterOptimizer] = None


def get_ml_filter_optimizer() -> MLFilterOptimizer:
    """Возвращает глобальный экземпляр ML оптимизатора"""
    global _ml_optimizer_instance
    if _ml_optimizer_instance is None:
        _ml_optimizer_instance = MLFilterOptimizer()
    return _ml_optimizer_instance


