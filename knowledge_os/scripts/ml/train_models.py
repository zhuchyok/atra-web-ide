#!/usr/bin/env python3
"""
Скрипт для обучения LightGBM моделей
Использование: python train_lightgbm_models.py
"""

import logging
import sys

from lightgbm_predictor import get_lightgbm_predictor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция обучения"""
    logger.info("🚀 Запуск обучения LightGBM моделей...")

    # Получаем предсказатель
    predictor = get_lightgbm_predictor()

    # Обучаем модели
    success = predictor.train_models(test_size=0.2, validation_size=0.1, random_state=42)

    if success:
        logger.info("✅ Обучение завершено успешно!")
        logger.info("📊 Метрики классификатора:")
        if "classifier" in predictor.training_metrics:
            for metric, value in predictor.training_metrics["classifier"].items():
                logger.info("  %s: %.4f", metric, value)

        logger.info("📈 Метрики регрессора:")
        if "regressor" in predictor.training_metrics:
            for metric, value in predictor.training_metrics["regressor"].items():
                logger.info("  %s: %.4f", metric, value)

        return 0
    else:
        logger.error("❌ Ошибка обучения моделей")
        return 1


if __name__ == "__main__":
    sys.exit(main())
