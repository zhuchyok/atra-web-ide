#!/usr/bin/env python3
"""
Проверка данных для обучения ML-модели роутинга
"""

import asyncio
import getpass
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

USER_NAME = getpass.getuser()
if USER_NAME == "zhuchyok":
    db_url = f"postgresql://{USER_NAME}@localhost:5432/knowledge_os"
else:
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def check_training_data():
    """Проверяет данные для обучения ML-модели"""
    print("🤖 Проверка данных для обучения ML-модели...\n")

    try:
        conn = await asyncpg.connect(db_url)
        try:
            # Проверяем количество записей
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(DISTINCT selected_route) as unique_routes,
                    AVG(performance_score) as avg_performance,
                    MIN(performance_score) as min_performance,
                    MAX(performance_score) as max_performance
                FROM ml_routing_training_data
            """)

            if stats:
                total = stats["total_records"] or 0
                routes = stats["unique_routes"] or 0
                avg_perf = stats["avg_performance"] or 0.0

                print("📊 Статистика данных:")
                print(f"  - Всего записей: {total}")
                print(f"  - Уникальных маршрутов: {routes}")
                print(f"  - Средняя производительность: {avg_perf:.2f}")

                if total >= 100:
                    print(f"\n✅ Достаточно данных для обучения (минимум 100, есть {total})")

                    # Пробуем обучить модель
                    print("\n🚀 Попытка обучения ML-модели...")
                    try:
                        from ml_router_trainer import MLRouterTrainer

                        trainer = MLRouterTrainer()
                        model = await trainer.train_model()
                        if model:
                            print("✅ ML-модель успешно обучена!")
                            return True
                        else:
                            print("⚠️ Не удалось обучить модель (недостаточно данных или ошибка)")
                            return False
                    except Exception as e:
                        print(f"❌ Ошибка обучения модели: {e}")
                        return False
                else:
                    print(f"\n⚠️ Недостаточно данных для обучения (нужно минимум 100, есть {total})")
                    print("   Модель будет использовать эвристики до накопления данных")
                    return False
            else:
                print("⚠️ Нет данных в таблице ml_routing_training_data")
                print("   Данные будут собираться автоматически при использовании системы")
                return False

        finally:
            await conn.close()
    except Exception as e:
        print(f"❌ Ошибка проверки данных: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(check_training_data())
