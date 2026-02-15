#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Victoria Enhanced
Проверяет работу всех новых компонентов супер-корпорации
"""

import sys
import os
import asyncio
import logging

# Добавляем пути
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'knowledge_os'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_victoria_enhanced():
    """Тестирование Victoria Enhanced"""
    try:
        from knowledge_os.app.victoria_enhanced import VictoriaEnhanced
        
        print("🚀 Запуск тестирования Victoria Enhanced...\n")
        
        # Инициализируем Victoria Enhanced
        victoria = VictoriaEnhanced(
            model_name="phi3.5:3.8b",
            use_react=True,
            use_extended_thinking=True,
            use_swarm=True,
            use_consensus=True,
            use_collective_memory=True
        )
        
        # Проверяем статус компонентов
        print("=" * 60)
        print("📊 СТАТУС КОМПОНЕНТОВ")
        print("=" * 60)
        status = await victoria.get_status()
        for key, value in status.items():
            icon = "✅" if value else "❌"
            print(f"{icon} {key}: {value}")
        
        print("\n" + "=" * 60)
        print("🧪 ТЕСТИРОВАНИЕ РАЗНЫХ ТИПОВ ЗАДАЧ")
        print("=" * 60)
        
        # Тест 1: Reasoning задача
        print("\n1️⃣ Reasoning задача:")
        print("   Задача: Реши задачу: У Маши было 5 яблок, она отдала 2, затем купила 3. Сколько яблок у Маши?")
        result1 = await victoria.solve(
            "Реши задачу: У Маши было 5 яблок, она отдала 2, затем купила 3. Сколько яблок у Маши?",
            use_enhancements=True
        )
        print(f"   ✅ Метод: {result1.get('method')}")
        print(f"   ✅ Результат: {str(result1.get('result', ''))[:300]}")
        if 'confidence' in result1:
            print(f"   ✅ Уверенность: {result1['confidence']:.2f}")
        
        # Тест 2: Planning задача
        print("\n2️⃣ Planning задача:")
        print("   Задача: Спланируй оптимизацию производительности веб-приложения")
        result2 = await victoria.solve(
            "Спланируй оптимизацию производительности веб-приложения",
            use_enhancements=True
        )
        print(f"   ✅ Метод: {result2.get('method')}")
        print(f"   ✅ Результат: {str(result2.get('result', ''))[:300]}")
        
        # Тест 3: Complex задача (Swarm)
        print("\n3️⃣ Complex задача (Swarm Intelligence):")
        print("   Задача: Как улучшить работу мультиагентной системы?")
        result3 = await victoria.solve(
            "Как улучшить работу мультиагентной системы?",
            use_enhancements=True
        )
        print(f"   ✅ Метод: {result3.get('method')}")
        print(f"   ✅ Результат: {str(result3.get('result', ''))[:300]}")
        if 'global_best_score' in result3:
            print(f"   ✅ Score: {result3['global_best_score']:.2f}")
        
        # Тест 4: Execution задача (ReAct)
        print("\n4️⃣ Execution задача (ReAct):")
        print("   Задача: Выполни анализ структуры проекта")
        result4 = await victoria.solve(
            "Выполни анализ структуры проекта atra-web-ide",
            use_enhancements=True
        )
        print(f"   ✅ Метод: {result4.get('method')}")
        print(f"   ✅ Результат: {str(result4.get('result', ''))[:300]}")
        if 'steps' in result4:
            print(f"   ✅ Шагов: {result4['steps']}")
        
        print("\n" + "=" * 60)
        print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_victoria_enhanced())
    sys.exit(0 if success else 1)
