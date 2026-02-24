"""
ML Router Trainer
Обучение ML модели для предсказания оптимального роутинга
Singularity 8.0: Intelligent Improvements
"""

import asyncio
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import numpy as np

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.model_selection import train_test_split

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("⚠️ scikit-learn не установлен, ML обучение недоступно")


class MLRouterTrainer:
    """
    Обучение ML модели для предсказания оптимального роутинга.
    Использует RandomForest для классификации оптимального роута.
    """

    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), "ml_router_model.pkl")

    async def load_training_data(
        self, days: int = 30, min_samples: int = 100
    ) -> Tuple[List[Dict], List[str]]:
        """
        Загружает данные для обучения из БД.

        Args:
            days: Количество дней истории для обучения
            min_samples: Минимальное количество образцов

        Returns:
            Кортеж (features, labels)
        """
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn не установлен, обучение невозможно")
            return [], []

        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Загружаем данные за последние N дней
                rows = await conn.fetch(
                    """
                    SELECT
                        task_type,
                        prompt_length,
                        category,
                        selected_route,
                        performance_score,
                        tokens_saved,
                        latency_ms,
                        quality_score,
                        success,
                        features,
                        actual_route_used,
                        user_satisfaction
                    FROM ml_routing_training_data
                    WHERE created_at > NOW() - INTERVAL '1 day' * $1
                    AND success = TRUE
                    AND performance_score IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 10000
                """,
                    days,
                )

                if len(rows) < min_samples:
                    logger.warning(
                        f"⚠️ [ML TRAINER] Недостаточно данных для обучения: {len(rows)} < {min_samples}"
                    )
                    return [], []

                # Извлекаем features и labels
                features_list = []
                labels = []

                for row in rows:
                    # Features
                    feature_dict = {
                        "prompt_length": row["prompt_length"],
                        "task_type_coding": 1 if row["task_type"] == "coding" else 0,
                        "task_type_general": 1 if row["task_type"] == "general" else 0,
                        "task_type_research": 1 if row["task_type"] == "research" else 0,
                        "category_coding": 1 if row["category"] == "coding" else 0,
                        "category_general": 1 if row["category"] == "general" else 0,
                        "performance_score": row["performance_score"] or 0.5,
                        "tokens_saved": row["tokens_saved"] or 0,
                        "latency_ms": row["latency_ms"] or 0,
                        "quality_score": row["quality_score"] or 0.5,
                        "user_satisfaction": row["user_satisfaction"] or 0.5,
                    }

                    # Добавляем features из JSONB
                    if row["features"]:
                        feature_dict.update(row["features"])

                    # Время дня (hour of day)
                    hour = datetime.now().hour
                    feature_dict["hour_of_day"] = hour
                    feature_dict["is_weekend"] = 1 if datetime.now().weekday() >= 5 else 0

                    features_list.append(feature_dict)

                    # Label: оптимальный роут (actual_route_used или selected_route)
                    optimal_route = row["actual_route_used"] or row["selected_route"]
                    labels.append(optimal_route)

                logger.info(f"✅ [ML TRAINER] Загружено {len(features_list)} образцов для обучения")
                return features_list, labels
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [ML TRAINER] Ошибка загрузки данных: {e}")
            return [], []

    def _prepare_features(self, features_list: List[Dict]) -> np.ndarray:
        """Подготавливает features для обучения"""
        if not features_list:
            return np.array([])

        # Собираем все уникальные ключи
        all_keys = set()
        for feat in features_list:
            all_keys.update(feat.keys())

        # Сортируем ключи для консистентности
        sorted_keys = sorted(all_keys)

        # Преобразуем в numpy array
        feature_matrix = []
        for feat in features_list:
            row = [feat.get(key, 0) for key in sorted_keys]
            feature_matrix.append(row)

        return np.array(feature_matrix)

    async def train_model(self, days: int = 30) -> bool:
        """
        Обучает ML модель на исторических данных.

        Args:
            days: Количество дней истории

        Returns:
            True если обучение успешно
        """
        if not SKLEARN_AVAILABLE:
            logger.error("❌ scikit-learn не установлен, обучение невозможно")
            return False

        logger.info(f"🚀 [ML TRAINER] Начало обучения модели (данные за {days} дней)...")

        # Загружаем данные
        features_list, labels = await self.load_training_data(days=days)

        if not features_list or not labels:
            logger.warning("⚠️ [ML TRAINER] Нет данных для обучения")
            return False

        # Подготавливаем features
        X = self._prepare_features(features_list)
        y = np.array(labels)

        # Разделяем на train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Обучаем модель
        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=10, random_state=42, n_jobs=-1
        )

        self.model.fit(X_train, y_train)

        # Оцениваем качество
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        logger.info(f"✅ [ML TRAINER] Модель обучена, accuracy: {accuracy:.2%}")
        logger.info(
            f"📊 [ML TRAINER] Classification report:\n{classification_report(y_test, y_pred)}"
        )

        # Сохраняем модель
        try:
            with open(self.model_path, "wb") as f:
                pickle.dump(self.model, f)
            logger.info(f"💾 [ML TRAINER] Модель сохранена в {self.model_path}")
        except Exception as e:
            logger.error(f"❌ [ML TRAINER] Ошибка сохранения модели: {e}")
            return False

        return accuracy > 0.7  # Минимальная точность 70%

    def load_model(self) -> bool:
        """
        Загружает обученную модель из файла.

        Returns:
            True если модель загружена успешно
        """
        if not SKLEARN_AVAILABLE:
            return False

        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                logger.info(f"✅ [ML TRAINER] Модель загружена из {self.model_path}")
                return True
            else:
                logger.warning(f"⚠️ [ML TRAINER] Модель не найдена: {self.model_path}")
                return False
        except Exception as e:
            logger.error(f"❌ [ML TRAINER] Ошибка загрузки модели: {e}")
            return False

    def predict_optimal_route(
        self,
        task_type: str,
        prompt_length: int,
        category: Optional[str] = None,
        features: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Предсказывает оптимальный роут для запроса.

        Args:
            task_type: Тип задачи
            prompt_length: Длина промпта
            category: Категория
            features: Дополнительные features

        Returns:
            Предсказанный роут или None
        """
        if not self.model:
            if not self.load_model():
                return None

        # Подготавливаем features
        feature_dict = {
            "prompt_length": prompt_length,
            "task_type_coding": 1 if task_type == "coding" else 0,
            "task_type_general": 1 if task_type == "general" else 0,
            "task_type_research": 1 if task_type == "research" else 0,
            "category_coding": 1 if category == "coding" else 0,
            "category_general": 1 if category == "general" else 0,
            "performance_score": 0.5,  # По умолчанию
            "tokens_saved": 0,
            "latency_ms": 0,
            "quality_score": 0.5,
            "user_satisfaction": 0.5,
            "hour_of_day": datetime.now().hour,
            "is_weekend": 1 if datetime.now().weekday() >= 5 else 0,
        }

        if features:
            feature_dict.update(features)

        # Преобразуем в numpy array (используем те же ключи, что и при обучении)
        # Для упрощения используем те же ключи, что и в обучении
        X = self._prepare_features([feature_dict])

        if X.size == 0:
            return None

        # Предсказываем
        try:
            prediction = self.model.predict(X)[0]
            return prediction
        except Exception as e:
            logger.error(f"❌ [ML TRAINER] Ошибка предсказания: {e}")
            return None


# Singleton instance
_trainer_instance: Optional[MLRouterTrainer] = None


def get_ml_router_trainer(db_url: str = DB_URL) -> MLRouterTrainer:
    """Получить singleton экземпляр тренера"""
    global _trainer_instance
    if _trainer_instance is None:
        _trainer_instance = MLRouterTrainer(db_url=db_url)
    return _trainer_instance
