#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генерация тестовых данных для обучения ML-модели
Создает разнообразные записи для быстрого накопления данных (100+ записей)
"""

import asyncio
import sys
import random
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

async def generate_test_data():
    """Генерирует тестовые данные для ML-модели"""
    print("🤖 Генерация тестовых данных для ML-модели...\n")
    
    try:
        from ml_router_data_collector import get_collector
        
        collector = await get_collector()
        
        # Типы задач
        task_types = ["coding", "general", "research"]
        categories = ["coding", "general", "research", "analysis", "debugging"]
        routes = ["local", "cloud", "veronica_web", "local_mac", "local_server"]
        
        # Генерируем 100+ записей
        num_records = 120
        print(f"📝 Генерация {num_records} тестовых записей...\n")
        
        for i in range(num_records):
            task_type = random.choice(task_types)
            category = random.choice(categories)
            route = random.choice(routes)
            
            # Генерируем реалистичные данные
            prompt_length = random.randint(50, 2000)
            performance_score = random.uniform(0.7, 1.0)
            tokens_saved = random.randint(0, 500) if route != "cloud" else 0
            latency_ms = random.uniform(200, 5000)
            quality_score = random.uniform(0.75, 0.95)
            success = random.random() > 0.1  # 90% успешных
            
            # Разнообразные features
            features = {
                "test_data": True,
                "iteration": i,
                "expert_name": random.choice(["Виктория", "Игорь", "Дмитрий", "Максим"]),
                "has_code_keywords": random.choice([0, 1]),
                "has_error_keywords": random.choice([0, 1]),
                "complexity": random.choice(["simple", "medium", "complex"]),
                "timestamp": (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
            }
            
            result = await collector.collect_routing_decision(
                task_type=task_type,
                prompt_length=prompt_length,
                category=category,
                selected_route=route,
                performance_score=performance_score,
                tokens_saved=tokens_saved,
                latency_ms=latency_ms,
                quality_score=quality_score,
                success=success,
                features=features
            )
            
            if (i + 1) % 20 == 0:
                print(f"  ✅ Сгенерировано {i + 1}/{num_records} записей...")
        
        # Проверяем количество записей
        print("\n📊 Проверка записей в БД...")
        count = await collector.get_training_data_count(days=31)
        print(f"  Всего записей: {count}")
        
        # Закрываем соединение
        await collector.close()
        
        print(f"\n✅ Генерация завершена! Создано {num_records} тестовых записей.")
        print(f"\n🎯 Теперь можно обучить ML-модель:")
        print(f"   python knowledge_os/scripts/check_ml_training_data.py")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(generate_test_data())
    sys.exit(0 if success else 1)

