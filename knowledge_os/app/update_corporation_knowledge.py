#!/usr/bin/env python3
"""
Скрипт для обновления знаний корпорации
Запускается автоматически при старте системы и периодически
"""

import asyncio
import os
import sys

# Добавляем путь к app
sys.path.insert(0, os.path.dirname(__file__))

from corporation_knowledge_system import update_all_agents_knowledge


async def main():
    """Обновить знания корпорации"""
    print("🔄 Обновление знаний корпорации...")
    try:
        knowledge = await update_all_agents_knowledge()
        print("✅ Знания обновлены:")
        print(f"   - Ollama моделей: {knowledge['total_ollama_models']}")
        print(f"   - MLX моделей: {knowledge['total_mlx_models']}")
        print(f"   - Скриптов: {knowledge['total_scripts']}")
        print(f"   - Недавних изменений: {len(knowledge['recent_changes'])}")

        # Также извлекаем полные знания корпорации (системы, логика, умения)
        try:
            from app.corporation_complete_knowledge import CorporationCompleteKnowledge

            complete_extractor = CorporationCompleteKnowledge()
            complete_result = await complete_extractor.extract_all()
            print("\n✅ Полные знания корпорации:")
            print(f"   - Систем: {complete_result['systems_count']}")
            print(f"   - Данных: {complete_result['data_count']}")
            print(f"   - Логики: {complete_result['logic_count']}")
            print(f"   - Всего извлечено: {complete_result['total_extracted']}")
            print(f"   - Сохранено в БД: {complete_result['saved_to_db']}")
        except Exception as e:
            print(f"⚠️ Не удалось извлечь полные знания: {e}")
    except Exception as e:
        print(f"❌ Ошибка обновления знаний: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
