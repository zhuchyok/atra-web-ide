#!/usr/bin/env python3
"""
🚀 LightGBM Predictor для торговой системы
Комбинированная система классификации и регрессии для предсказания успешности сигналов
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

# LightGBM библиотеки (опционально)
try:
    import joblib
    import lightgbm as lgb
    import shap
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        r2_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.warning("⚠️ LightGBM не установлен, ML функции будут ограничены")
    logger.warning("💡 Установите: pip install lightgbm scikit-learn")


class LightGBMPredictor:
    """
    LightGBM система для предсказания успешности торговых сигналов

    Использует два подхода:
    1. Классификация - вероятность успеха (0-100%)
    2. Регрессия - размер прибыли в процентах

    Комбинирует оба подхода для итоговой оценки сигнала
    """

    _instance: Optional["LightGBMPredictor"] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LightGBMPredictor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        patterns_file: str = "ai_learning_data/trading_patterns.json",
        model_dir: str = "ai_learning_data/lightgbm_models",
    ):
        if getattr(self, "_initialized", False):
            return

        self.patterns_file = patterns_file
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)

        # Модели
        self.classifier: Optional[lgb.Booster] = None
        self.regressor: Optional[lgb.Booster] = None

        # Encoders для категориальных признаков
        self.label_encoders: Dict[str, LabelEncoder] = {}

        # Feature names
        self.feature_names: List[str] = []

        # Статус обучения
        self.is_trained = False
        self.training_metrics: Dict[str, Any] = {}

        # Данные
        self.patterns: List[Dict[str, Any]] = []

        # Попытка автоматической загрузки моделей при инициализации
        if LIGHTGBM_AVAILABLE:
            self.load_models()

        self._initialized = True

    def load_patterns(self) -> int:
        """Загружает паттерны из файла"""
        try:
            if not os.path.exists(self.patterns_file):
                logger.warning("⚠️ Файл паттернов не найден: %s", self.patterns_file)
                return 0

            with open(self.patterns_file, encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                logger.error("❌ Некорректный формат паттернов: ожидается список")
                return 0

            self.patterns = data
            logger.info("✅ Загружено %d паттернов из %s", len(self.patterns), self.patterns_file)
            return len(self.patterns)

        except Exception as e:
            logger.error("❌ Ошибка загрузки паттернов: %s", e)
            return 0

    def prepare_features(
        self, patterns: List[Dict[str, Any]], include_result: bool = True
    ) -> Tuple[Optional[pd.DataFrame], Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Подготавливает features для обучения модели
        """
        if not LIGHTGBM_AVAILABLE or not patterns:
            return None, None, None

        try:
            features_list = []
            y_class = []
            y_reg = []

            for pattern in patterns:
                feature_vector = self._extract_features(pattern)
                if feature_vector is None:
                    continue

                features_list.append(feature_vector)

                if include_result:
                    result = pattern.get("result", "")
                    y_class.append(1 if result == "WIN" else 0)
                    profit_pct = pattern.get("profit_pct", 0.0)
                    y_reg.append(float(profit_pct) if profit_pct is not None else 0.0)

            if not features_list:
                logger.warning("⚠️ Не удалось извлечь features из паттернов")
                return None, None, None

            X = pd.DataFrame(features_list)
            self.feature_names = list(X.columns)

            y_class_array = np.array(y_class) if include_result else None
            y_reg_array = np.array(y_reg) if include_result else None

            logger.info("✅ Подготовлено %d samples с %d features", len(X), len(self.feature_names))
            return X, y_class_array, y_reg_array

        except Exception as e:
            logger.error("❌ Ошибка подготовки features: %s", e)
            return None, None, None

    def _extract_features(self, pattern: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Извлекает все features для модели
        """
        try:
            features = {}

            # Индикаторы
            indicators = pattern.get("indicators", {})
            features["rsi"] = float(indicators.get("rsi", 50.0))
            features["macd"] = float(indicators.get("macd", 0.0))

            # Рыночные условия
            market = pattern.get("market_conditions", {})
            features["volume_ratio"] = float(market.get("volume_ratio", 1.0))
            features["volatility"] = float(market.get("volatility", 0.02))

            # Параметры сигнала
            features["risk_pct"] = float(pattern.get("risk_pct", 2.0))
            features["leverage"] = float(pattern.get("leverage", 1.0))

            # Entry price
            entry_price = float(pattern.get("entry_price", 0.0))
            if entry_price <= 0:
                entry_price = 1.0

            # 1. EMA distance
            ema_fast = float(indicators.get("ema_fast", entry_price * 1.01))
            ema_slow = float(indicators.get("ema_slow", entry_price * 0.99))
            features["ema_distance"] = abs(ema_fast - ema_slow) / entry_price

            # 2. BB position
            bb_upper = float(indicators.get("bb_upper", entry_price * 1.02))
            bb_lower = float(indicators.get("bb_lower", entry_price * 0.98))
            if bb_upper > bb_lower:
                features["bb_position"] = (entry_price - bb_lower) / (bb_upper - bb_lower)
            else:
                features["bb_position"] = 0.5

            # 3. ATR %
            atr = float(indicators.get("atr", entry_price * 0.015))
            features["atr_pct"] = atr / entry_price

            # 4. Signal direction
            side = pattern.get("side", pattern.get("signal_type", "LONG"))
            features["signal_is_long"] = 1.0 if side in ["LONG", "BUY"] else 0.0

            # 5. TP distances
            tp1 = float(pattern.get("tp1", entry_price * 1.025))
            tp2 = float(pattern.get("tp2", entry_price * 1.05))
            features["tp1_distance_pct"] = abs(tp1 - entry_price) / entry_price * 100
            features["tp2_distance_pct"] = abs(tp2 - entry_price) / entry_price * 100

            # 6. Time features
            timestamp = pattern.get("timestamp", "")
            if timestamp:
                try:
                    dt = (
                        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        if isinstance(timestamp, str)
                        else timestamp
                    )
                    features["hour_of_day"] = float(dt.hour)
                    features["day_of_week"] = float(dt.weekday())
                    features["is_weekend"] = 1.0 if dt.weekday() >= 5 else 0.0
                except Exception:
                    features["hour_of_day"], features["day_of_week"], features["is_weekend"] = (
                        12.0,
                        0.0,
                        0.0,
                    )
            else:
                features["hour_of_day"], features["day_of_week"], features["is_weekend"] = (
                    12.0,
                    0.0,
                    0.0,
                )

            # 7. Lag Features
            historical_data = pattern.get("historical_indicators", {})

            # RSI lags
            rsi_current = features["rsi"]
            features["rsi_lag_1"] = float(historical_data.get("rsi_lag_1", rsi_current))
            features["rsi_lag_2"] = float(historical_data.get("rsi_lag_2", rsi_current))
            features["rsi_lag_3"] = float(historical_data.get("rsi_lag_3", rsi_current))
            features["rsi_change"] = rsi_current - features["rsi_lag_1"]

            # MACD lags
            macd_current = features["macd"]
            features["macd_lag_1"] = float(historical_data.get("macd_lag_1", macd_current))
            features["macd_lag_2"] = float(historical_data.get("macd_lag_2", macd_current))
            features["macd_lag_3"] = float(historical_data.get("macd_lag_3", macd_current))
            features["macd_change"] = macd_current - features["macd_lag_1"]

            # Volume ratio lags
            volume_current = features["volume_ratio"]
            features["volume_ratio_lag_1"] = float(
                historical_data.get("volume_ratio_lag_1", volume_current)
            )
            features["volume_trend"] = volume_current - features["volume_ratio_lag_1"]
            features["volume_change_1"] = volume_current - features["volume_ratio_lag_1"]

            # Volatility lags
            vol_current = features["volatility"]
            features["volatility_lag_1"] = float(
                historical_data.get("volatility_lag_1", vol_current)
            )
            features["volatility_change"] = vol_current - features["volatility_lag_1"]

            # Price changes
            features["price_change_1"] = float(historical_data.get("price_change_1", 0.0))
            features["price_change_3"] = float(historical_data.get("price_change_3", 0.0))

            # Фильтруем только нужные features
            if self.feature_names:
                expected_features = self.feature_names
            else:
                expected_features = [
                    "rsi",
                    "macd",
                    "volume_ratio",
                    "volatility",
                    "ema_distance",
                    "bb_position",
                    "atr_pct",
                    "signal_is_long",
                    "risk_pct",
                    "leverage",
                    "tp1_distance_pct",
                    "tp2_distance_pct",
                    "hour_of_day",
                    "day_of_week",
                    "is_weekend",
                    "rsi_lag_1",
                    "rsi_lag_2",
                    "rsi_lag_3",
                    "rsi_change",
                    "macd_lag_1",
                    "macd_lag_2",
                    "macd_lag_3",
                    "macd_change",
                    "volume_ratio_lag_1",
                    "volume_trend",
                    "volume_change_1",
                    "volatility_lag_1",
                    "volatility_change",
                    "price_change_1",
                    "price_change_3",
                ]

            filtered_features = {feat: features.get(feat, 0.0) for feat in expected_features}
            return filtered_features

        except Exception as e:
            logger.debug("⚠️ Ошибка извлечения features: %s", e)
            return None

    def train_models(
        self, test_size: float = 0.2, validation_size: float = 0.1, random_state: int = 42
    ) -> bool:
        """Обучает обе модели (классификатор и регрессор)"""
        if not LIGHTGBM_AVAILABLE:
            return False

        try:
            pattern_count = self.load_patterns()
            if pattern_count < 100:
                logger.warning(
                    "⚠️ Недостаточно паттернов для обучения (нужно минимум 100, есть %d)",
                    pattern_count,
                )
                return False

            X, y_class, y_reg = self.prepare_features(self.patterns, include_result=True)
            if X is None or y_class is None or y_reg is None:
                return False

            valid_mask = ~pd.isna(y_class) & ~pd.isna(y_reg)
            X, y_class, y_reg = X[valid_mask], y_class[valid_mask], y_reg[valid_mask]

            X_train, X_test, y_class_train, y_class_test, y_reg_train, y_reg_test = (
                train_test_split(
                    X,
                    y_class,
                    y_reg,
                    test_size=test_size,
                    random_state=random_state,
                    stratify=y_class,
                )
            )

            X_train_final, X_val, y_class_train_final, y_class_val, y_reg_train_final, y_reg_val = (
                train_test_split(
                    X_train,
                    y_class_train,
                    y_reg_train,
                    test_size=validation_size,
                    random_state=random_state,
                    stratify=y_class_train,
                )
            )

            classifier_trained = self._train_classifier(
                X_train_final, y_class_train_final, X_val, y_class_val, X_test, y_class_test
            )
            regressor_trained = self._train_regressor(
                X_train_final, y_reg_train_final, X_val, y_reg_val, X_test, y_reg_test
            )

            self.is_trained = classifier_trained and regressor_trained
            if self.is_trained:
                self._save_models()
            return self.is_trained

        except Exception as e:
            logger.error("❌ Ошибка обучения моделей: %s", e)
            return False

    def _train_classifier(self, X_train, y_train, X_val, y_val, X_test, y_test) -> bool:
        try:
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "random_state": 42,
            }
            self.classifier = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=1000,
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
            )
            y_pred_proba = self.classifier.predict(
                X_test, num_iteration=self.classifier.best_iteration
            )
            metrics = {
                "roc_auc": roc_auc_score(y_test, y_pred_proba),
                "accuracy": accuracy_score(y_test, (y_pred_proba > 0.5).astype(int)),
            }
            self.training_metrics["classifier"] = metrics
            return True
        except Exception as e:
            logger.error("❌ Ошибка обучения классификатора: %s", e)
            return False

    def _train_regressor(self, X_train, y_train, X_val, y_val, X_test, y_test) -> bool:
        try:
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            params = {
                "objective": "regression",
                "metric": "rmse",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "random_state": 42,
            }
            self.regressor = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=1000,
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
            )
            self.training_metrics["regressor"] = {
                "mae": mean_absolute_error(y_test, self.regressor.predict(X_test))
            }
            return True
        except Exception as e:
            logger.error("❌ Ошибка обучения регрессора: %s", e)
            return False

    def predict(
        self,
        market_conditions: Dict[str, Any],
        indicators: Dict[str, float],
        signal_params: Dict[str, float],
        include_explainability: bool = False,
    ) -> Dict[str, Any]:
        """
        Предсказывает успешность сигнала с высокой производительностью
        """
        if not self.is_trained or not self.classifier or not self.regressor:
            if not self.load_models():
                return {
                    "success_probability": 0.5,
                    "expected_profit_pct": 0.0,
                    "combined_score": 0.0,
                    "recommendation": "SKIP",
                }

        try:
            historical_indicators = indicators.get("_historical", {})
            pattern = {
                "indicators": indicators,
                "market_conditions": market_conditions,
                "entry_price": signal_params.get("entry_price", 0.0),
                "tp1": signal_params.get("tp1", 0.0),
                "tp2": signal_params.get("tp2", 0.0),
                "risk_pct": signal_params.get("risk_pct", 2.0),
                "leverage": signal_params.get("leverage", 1.0),
                "quality_score": signal_params.get("quality_score", 0.5),
                "mtf_score": signal_params.get("mtf_score", 0.5),
                "spread_pct": signal_params.get("spread_pct", 0.0),
                "depth_usd": signal_params.get("depth_usd", 0.0),
                "historical_indicators": historical_indicators,
            }

            feature_dict = self._extract_features(pattern)
            if feature_dict is None:
                return {
                    "success_probability": 0.5,
                    "expected_profit_pct": 0.0,
                    "combined_score": 0.0,
                    "recommendation": "SKIP",
                }

            X = pd.DataFrame([feature_dict]).reindex(columns=self.feature_names, fill_value=0.0)

            success_prob = float(
                self.classifier.predict(X, num_iteration=self.classifier.best_iteration)[0]
            )
            expected_profit = float(
                self.regressor.predict(X, num_iteration=self.regressor.best_iteration)[0]
            )

            success_prob = max(0.0, min(1.0, success_prob))
            expected_profit = max(-50.0, min(50.0, expected_profit))
            combined_score = success_prob * expected_profit
            recommendation = "BUY" if (success_prob > 0.4 and expected_profit > 0.3) else "SKIP"

            ai_factors = []
            if include_explainability:
                try:
                    if not hasattr(self, "_explainer") or self._explainer is None:
                        self._explainer = shap.TreeExplainer(self.classifier)
                    shap_values = self._explainer.shap_values(X)
                    instance_shap = (
                        shap_values[1][0]
                        if isinstance(shap_values, list)
                        else (shap_values[0] if len(shap_values.shape) > 1 else shap_values)
                    )

                    for i, feat_name in enumerate(self.feature_names):
                        val = float(instance_shap[i])
                        if abs(val) > 0.01:
                            ai_factors.append({"feature": feat_name, "impact": val})
                    ai_factors.sort(key=lambda x: abs(x["impact"]), reverse=True)
                    ai_factors = ai_factors[:5]
                except Exception:
                    pass

            return {
                "success_probability": success_prob,
                "expected_profit_pct": expected_profit,
                "combined_score": combined_score,
                "recommendation": recommendation,
                "ai_factors": ai_factors,
            }
        except Exception as e:
            logger.error("❌ Ошибка в LightGBMPredictor.predict: %s", e)
            return {
                "success_probability": 0.5,
                "expected_profit_pct": 0.0,
                "combined_score": 0.0,
                "recommendation": "SKIP",
            }

    def _save_models(self):
        try:
            if self.classifier:
                self.classifier.save_model(os.path.join(self.model_dir, "classifier.txt"))
            if self.regressor:
                self.regressor.save_model(os.path.join(self.model_dir, "regressor.txt"))
            with open(os.path.join(self.model_dir, "metadata.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "feature_names": self.feature_names,
                        "metrics": self.training_metrics,
                        "trained_at": get_utc_now().isoformat(),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error("❌ Ошибка сохранения моделей: %s", e)

    def load_models(self) -> bool:
        if not LIGHTGBM_AVAILABLE:
            return False
        try:
            c_path, r_path, m_path = (
                os.path.join(self.model_dir, "classifier.txt"),
                os.path.join(self.model_dir, "regressor.txt"),
                os.path.join(self.model_dir, "metadata.json"),
            )
            if not os.path.exists(c_path) or not os.path.exists(r_path):
                return False
            self.classifier, self.regressor = (
                lgb.Booster(model_file=c_path),
                lgb.Booster(model_file=r_path),
            )
            if os.path.exists(m_path):
                with open(m_path, encoding="utf-8") as f:
                    meta = json.load(f)
                    self.feature_names = meta.get("feature_names", [])
                    self.training_metrics = meta.get("metrics", {})
            self.is_trained = True
            return True
        except Exception as e:
            logger.error("❌ Ошибка загрузки моделей: %s", e)
            return False


def get_lightgbm_predictor() -> LightGBMPredictor:
    """Возвращает глобальный экземпляр LightGBM предсказателя"""
    return LightGBMPredictor()
