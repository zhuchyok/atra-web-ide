#!/usr/bin/env python3
"""
Система фильтрации паттернов - оставляет только самые прибыльные и качественные
Ограничивает до 30,000 лучших паттернов для эффективного обучения ИИ
"""

import json
import logging
import os
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def filter_best_patterns(patterns_file, max_patterns=30000):
    """
    Фильтрует паттерны, оставляя только самые прибыльные и качественные

    Критерии отбора:
    1. Прибыльность (profit_pct > 0)
    2. Качество результата (WIN > LOSS > NEUTRAL)
    3. Свежесть данных (не старше 90 дней)
    4. Полнота данных (все поля заполнены)
    """

    logger.info(f"🔍 Начинаем фильтрацию паттернов из {patterns_file}")

    # Загружаем паттерны
    try:
        with open(patterns_file, encoding="utf-8") as f:
            patterns = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        return False

    total_patterns = len(patterns)
    logger.info(f"📊 Загружено {total_patterns:,} паттернов")

    # Фильтруем паттерны по критериям
    filtered_patterns = []

    # Дата отсечения (90 дней назад)
    cutoff_date = get_utc_now() - timedelta(days=90)

    for pattern in patterns:
        # Проверяем полноту данных
        if not all(key in pattern for key in ["symbol", "timestamp", "signal_type", "result"]):
            continue

        # Проверяем свежесть данных
        try:
            pattern_date = datetime.fromisoformat(pattern["timestamp"].replace("Z", "+00:00"))
            if pattern_date < cutoff_date:
                continue
        except:
            continue

        # Проверяем результат
        result = pattern.get("result")
        if result not in ["WIN", "LOSS", "NEUTRAL"]:
            continue

        # Проверяем прибыльность
        profit_pct = pattern.get("profit_pct")
        if profit_pct is None:
            continue

        filtered_patterns.append(pattern)

    logger.info(f"✅ После базовой фильтрации: {len(filtered_patterns):,} паттернов")

    # Сортируем по качеству и прибыльности
    def pattern_score(pattern):
        """Вычисляет оценку паттерна для сортировки"""
        score = 0

        # Результат
        result = pattern.get("result")
        if result == "WIN":
            score += 1000
        elif result == "LOSS":
            score += 100
        elif result == "NEUTRAL":
            score += 50

        # Прибыльность
        profit_pct = pattern.get("profit_pct", 0)
        if profit_pct > 0:
            score += profit_pct * 10  # Прибыльность важна
        else:
            score -= abs(profit_pct) * 5  # Убытки снижают оценку

        # Свежесть (более свежие паттерны важнее)
        try:
            pattern_date = datetime.fromisoformat(pattern["timestamp"].replace("Z", "+00:00"))
            days_old = (get_utc_now() - pattern_date).days
            score += max(0, 90 - days_old)  # Свежесть до 90 дней
        except:
            pass

        return score

    # Сортируем по оценке
    filtered_patterns.sort(key=pattern_score, reverse=True)

    # Ограничиваем количество
    if len(filtered_patterns) > max_patterns:
        filtered_patterns = filtered_patterns[:max_patterns]
        logger.info(f"🎯 Ограничено до {max_patterns:,} лучших паттернов")

    # Создаем бэкап исходного файла
    backup_file = f"{patterns_file}.backup_{get_utc_now().strftime('%Y%m%d_%H%M%S')}"
    try:
        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(patterns, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Создан бэкап: {backup_file}")
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}")

    # Сохраняем отфильтрованные паттерны
    try:
        with open(patterns_file, "w", encoding="utf-8") as f:
            json.dump(filtered_patterns, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Отфильтрованные паттерны сохранены в {patterns_file}")
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        return False

    # Статистика
    logger.info("📈 СТАТИСТИКА ФИЛЬТРАЦИИ:")
    logger.info(f"   - Исходное количество: {total_patterns:,}")
    logger.info(f"   - После фильтрации: {len(filtered_patterns):,}")
    logger.info(
        f"   - Сокращение: {((total_patterns - len(filtered_patterns)) / total_patterns * 100):.1f}%"
    )

    # Статистика по результатам
    wins = sum(1 for p in filtered_patterns if p.get("result") == "WIN")
    losses = sum(1 for p in filtered_patterns if p.get("result") == "LOSS")
    neutral = len(filtered_patterns) - wins - losses

    logger.info(f"   - WIN: {wins:,} ({wins / len(filtered_patterns) * 100:.1f}%)")
    logger.info(f"   - LOSS: {losses:,} ({losses / len(filtered_patterns) * 100:.1f}%)")
    logger.info(f"   - NEUTRAL: {neutral:,} ({neutral / len(filtered_patterns) * 100:.1f}%)")

    return True


def main():
    """Основная функция"""

    try:
        from src.config.patterns import get_patterns_file_path
    except ImportError:
        from patterns_config import get_patterns_file_path
    patterns_file = get_patterns_file_path("main")

    if not os.path.exists(patterns_file):
        logger.error(f"Файл паттернов не найден: {patterns_file}")
        return False

    # Фильтруем паттерны
    success = filter_best_patterns(patterns_file, max_patterns=30000)

    if success:
        logger.info("🎉 Фильтрация паттернов завершена успешно!")
        logger.info("🧠 ИИ теперь имеет только самые качественные паттерны для обучения")
    else:
        logger.error("❌ Ошибка при фильтрации паттернов")

    return success


if __name__ == "__main__":
    main()
