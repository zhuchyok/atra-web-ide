#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест сбора данных для ML-модели
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

async def test_collection():
    """Тестирует сбор данных"""
    print("🧪 Тест сбора данных для ML-модели...\n")
    
    try:
        from ml_router_data_collector import get_collector
        
        collector = await get_collector()
        
        # Тест 1: Локальный роутинг
        print("📝 Тест 1: Сбор данных о локальном роутинге...")
        result1 = await collector.collect_routing_decision(
            task_type="coding",
            prompt_length=150,
            category="coding",
            selected_route="local",
            performance_score=0.9,
            tokens_saved=100,
            latency_ms=500.0,
            quality_score=0.85,
            success=True,
            features={"test": True, "source": "test_script"}
        )
        print(f"  {'✅ Успешно' if result1 else '❌ Ошибка'}")
        
        # Тест 2: Облачный роутинг
        print("\n📝 Тест 2: Сбор данных об облачном роутинге...")
        result2 = await collector.collect_routing_decision(
            task_type="general",
            prompt_length=500,
            category="general",
            selected_route="cloud",
            performance_score=0.8,
            tokens_saved=0,
            latency_ms=2000.0,
            quality_score=0.9,
            success=True,
            features={"test": True, "source": "test_script"}
        )
        print(f"  {'✅ Успешно' if result2 else '❌ Ошибка'}")
        
        # Тест 3: Веб-роутинг (Veronica)
        print("\n📝 Тест 3: Сбор данных о веб-роутинге...")
        result3 = await collector.collect_routing_decision(
            task_type="research",
            prompt_length=200,
            category="research",
            selected_route="veronica_web",
            performance_score=0.95,
            tokens_saved=500,
            latency_ms=3000.0,
            quality_score=0.9,
            success=True,
            features={"test": True, "source": "test_script", "web_search": True}
        )
        print(f"  {'✅ Успешно' if result3 else '❌ Ошибка'}")
        
        # Проверяем количество записей
        print("\n📊 Проверка записей в БД...")
        count = await collector.get_training_data_count(days=1)
        print(f"  Всего записей за последние 24 часа: {count}")
        
        # Закрываем соединение
        await collector.close()
        
        if result1 and result2 and result3:
            print("\n✅ Все тесты пройдены успешно!")
            return True
        else:
            print("\n⚠️ Некоторые тесты провалены")
            return False
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_collection())
    sys.exit(0 if success else 1)

