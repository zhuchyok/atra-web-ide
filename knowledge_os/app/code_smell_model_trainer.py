"""
Code Smell Model Trainer: Обучение ML модели для предсказания багов в коде

Функционал:
- Сбор данных из code_smell_training_data
- Feature engineering (code complexity, history, patterns)
- Обучение LightGBM/XGBoost модели
- Валидация: precision > 70%, recall > 60%
"""

import asyncio
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

# Import database connection from evaluator
from evaluator import get_pool

# Try to import ML libraries
try:
    from sklearn.metrics import classification_report, precision_score, recall_score
    from sklearn.model_selection import train_test_split

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import lightgbm as lgb

    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

try:
    from sklearn.ensemble import RandomForestClassifier

    RANDOM_FOREST_AVAILABLE = True
except ImportError:
    RANDOM_FOREST_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

# Пороги валидации
MIN_PRECISION = 0.70  # 70%
MIN_RECALL = 0.60  # 60%

# Путь для сохранения модели
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "code_smell_model.pkl")
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)


class CodeSmellModelTrainer:
    """Класс для обучения ML модели предсказания багов"""

    def __init__(self, db_url: str = DB_URL, model_type: str = "lightgbm"):
        self.db_url = db_url
        self.model_type = model_type
        self.model = None
        self.feature_names = [
            "cyclomatic_complexity",
            "function_count",
            "class_count",
            "avg_function_length",
            "has_null_pointer_pattern",
            "has_race_condition_pattern",
            "has_memory_leak_pattern",
            "has_type_error_pattern",
            "has_logic_error_pattern",
            "magic_numbers_count",
            "file_size",
            "recent_changes",
        ]

    async def load_training_data(self, days: int = 90) -> Tuple[List[Dict], List[bool]]:
        """
        Загружает данные для обучения из БД.

        Args:
            days: Количество дней истории

        Returns:
            Кортеж (features_list, labels)
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    code_features,
                    actual_bug,
                    bug_type
                FROM code_smell_training_data
                WHERE created_at > NOW() - INTERVAL '1 day' * $1
                ORDER BY created_at DESC
            """,
                days,
            )

            features_list = []
            labels = []

            for row in rows:
                features = row["code_features"] or {}
                actual_bug = row["actual_bug"] or False

                # Формируем features
                feature_dict = {
                    "cyclomatic_complexity": float(features.get("cyclomatic_complexity", 0.0)),
                    "function_count": float(features.get("function_count", 0.0)),
                    "class_count": float(features.get("class_count", 0.0)),
                    "avg_function_length": float(features.get("avg_function_length", 0.0)),
                    "has_null_pointer_pattern": 1.0
                    if "null_pointer" in str(features.get("anti_patterns", [])).lower()
                    else 0.0,
                    "has_race_condition_pattern": 1.0
                    if "race_condition" in str(features.get("anti_patterns", [])).lower()
                    else 0.0,
                    "has_memory_leak_pattern": 1.0
                    if "memory_leak" in str(features.get("anti_patterns", [])).lower()
                    else 0.0,
                    "has_type_error_pattern": 1.0
                    if "type_error" in str(features.get("anti_patterns", [])).lower()
                    else 0.0,
                    "has_logic_error_pattern": 1.0
                    if "logic_error" in str(features.get("anti_patterns", [])).lower()
                    else 0.0,
                    "magic_numbers_count": float(features.get("magic_numbers_count", 0.0)),
                    "file_size": float(features.get("file_size", 0.0)),
                    "recent_changes": float(features.get("recent_changes", 0.0)),
                }

                features_list.append(feature_dict)
                labels.append(bool(actual_bug))

            logger.info(
                f"📊 Loaded {len(features_list)} training samples ({sum(labels)} bugs, {len(labels) - sum(labels)} non-bugs)"
            )
            return features_list, labels

    def _prepare_features(self, features_list: List[Dict]) -> np.ndarray:
        """
        Подготавливает features для обучения модели.

        Args:
            features_list: Список словарей с features

        Returns:
            NumPy array с features
        """
        feature_matrix = []

        for features in features_list:
            feature_vector = [features.get(name, 0.0) for name in self.feature_names]
            feature_matrix.append(feature_vector)

        return np.array(feature_matrix)

    async def train_model(self, days: int = 90) -> bool:
        """
        Обучает ML модель на исторических данных.

        Args:
            days: Количество дней истории

        Returns:
            True если обучение успешно и метрики достигнуты
        """
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn не установлен, обучение невозможно")
            return False

        logger.info(f"🚀 [CODE SMELL TRAINER] Начало обучения модели (данные за {days} дней)...")

        # Загружаем данные
        features_list, labels = await self.load_training_data(days=days)

        if not features_list or not labels:
            logger.warning("⚠️ [CODE SMELL TRAINER] Нет данных для обучения")
            return False

        if len(features_list) < 50:
            logger.warning(
                f"⚠️ [CODE SMELL TRAINER] Недостаточно данных для обучения: {len(features_list)} (минимум 50)"
            )
            return False

        # Подготавливаем features
        X = self._prepare_features(features_list)
        y = np.array(labels, dtype=int)

        # Разделяем на train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if len(set(y)) > 1 else None
        )

        # Обучаем модель
        if self.model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            # LightGBM
            train_data = lgb.Dataset(X_train, label=y_train, feature_name=self.feature_names)
            val_data = lgb.Dataset(
                X_test, label=y_test, reference=train_data, feature_name=self.feature_names
            )

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
            }

            self.model = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=100,
                callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(period=0)],
            )
        elif RANDOM_FOREST_AVAILABLE:
            # Random Forest (fallback)
            self.model = RandomForestClassifier(
                n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
            )
            self.model.fit(X_train, y_train)
        else:
            logger.error("❌ [CODE SMELL TRAINER] Нет доступных ML библиотек")
            return False

        # Оцениваем качество
        y_pred = self.model.predict(X_test)
        y_pred_proba = None

        if hasattr(self.model, "predict_proba"):
            y_pred_proba = self.model.predict_proba(X_test)[:, 1]
        elif hasattr(self.model, "predict"):
            y_pred_proba = (
                self.model.predict(X_test, raw_score=False) if LIGHTGBM_AVAILABLE else y_pred
            )

        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)

        logger.info(f"📊 [CODE SMELL TRAINER] Precision: {precision:.2%}, Recall: {recall:.2%}")
        logger.info(
            f"📊 [CODE SMELL TRAINER] Classification report:\n{classification_report(y_test, y_pred)}"
        )

        # Проверяем, достигнуты ли целевые метрики
        if precision >= MIN_PRECISION and recall >= MIN_RECALL:
            logger.info(
                f"✅ [CODE SMELL TRAINER] Метрики достигнуты! Precision: {precision:.2%} >= {MIN_PRECISION:.2%}, Recall: {recall:.2%} >= {MIN_RECALL:.2%}"
            )

            # Сохраняем модель
            try:
                with open(MODEL_PATH, "wb") as f:
                    pickle.dump(
                        {
                            "model": self.model,
                            "feature_names": self.feature_names,
                            "model_type": self.model_type,
                            "precision": precision,
                            "recall": recall,
                            "trained_at": datetime.now().isoformat(),
                        },
                        f,
                    )
                logger.info(f"✅ [CODE SMELL TRAINER] Модель сохранена: {MODEL_PATH}")
                return True
            except Exception as e:
                logger.error(f"❌ [CODE SMELL TRAINER] Ошибка сохранения модели: {e}")
                return False
        else:
            logger.warning(
                f"⚠️ [CODE SMELL TRAINER] Метрики не достигнуты. Precision: {precision:.2%} < {MIN_PRECISION:.2%} или Recall: {recall:.2%} < {MIN_RECALL:.2%}"
            )
            return False

    def load_model(self) -> bool:
        """
        Загружает обученную модель из файла.

        Returns:
            True если модель загружена успешно
        """
        try:
            if not os.path.exists(MODEL_PATH):
                logger.warning(f"⚠️ [CODE SMELL TRAINER] Модель не найдена: {MODEL_PATH}")
                return False

            with open(MODEL_PATH, "rb") as f:
                model_data = pickle.load(f)
                self.model = model_data["model"]
                self.feature_names = model_data.get("feature_names", self.feature_names)
                self.model_type = model_data.get("model_type", self.model_type)

            logger.info(f"✅ [CODE SMELL TRAINER] Модель загружена: {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"❌ [CODE SMELL TRAINER] Ошибка загрузки модели: {e}")
            return False

    def predict(self, features: Dict) -> Tuple[float, bool]:
        """
        Предсказывает вероятность бага для заданных features.

        Args:
            features: Словарь с features кода

        Returns:
            Кортеж (probability, is_bug) - вероятность бага и бинарное предсказание
        """
        if not self.model:
            logger.warning("⚠️ [CODE SMELL TRAINER] Модель не загружена")
            return 0.0, False

        # Подготавливаем features
        feature_vector = np.array([[features.get(name, 0.0) for name in self.feature_names]])

        # Предсказываем
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(feature_vector)[0, 1]
        elif hasattr(self.model, "predict"):
            if LIGHTGBM_AVAILABLE and isinstance(self.model, lgb.Booster):
                proba = self.model.predict(feature_vector)[0]
            else:
                proba = float(self.model.predict(feature_vector)[0])
        else:
            proba = 0.0

        is_bug = proba >= 0.5  # Порог для бинарного предсказания

        return float(proba), bool(is_bug)


async def train_code_smell_model(days: int = 90) -> bool:
    """Обертка для обучения модели"""
    trainer = CodeSmellModelTrainer()
    return await trainer.train_model(days=days)


if __name__ == "__main__":
    asyncio.run(train_code_smell_model())
