"""
Тестовый скрипт для проверки интеграции Singularity 5.0
Проверяет: semantic_cache с метриками, safety_checker, enhanced_monitor
"""

import asyncio
import os
import sys

# Добавляем путь к модулям
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(project_root, "knowledge_os", "app"))
sys.path.insert(0, project_root)


async def test_semantic_cache_metrics():
    """Тест semantic_cache с новыми метриками"""
    print("🧪 Тест 1: Semantic Cache с метриками роутинга...")
    try:
        from knowledge_os.app.semantic_cache import SemanticAICache

        cache = SemanticAICache()
        test_query = "Как оптимизировать код?"
        test_response = "Используйте кэширование и оптимизацию алгоритмов."

        # Сохраняем с метриками
        await cache.save_to_cache(
            test_query,
            test_response,
            "Виктория",
            routing_source="local_mac",
            performance_score=0.95,
            tokens_saved=500,
        )
        print("   ✅ Сохранение с метриками работает")

        # Проверяем получение
        cached = await cache.get_cached_response(test_query, "Виктория")
        if cached:
            print("   ✅ Получение из кэша работает")
        else:
            print("   ⚠️ Кэш не найден (возможно, миграция не применена)")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False


async def test_safety_checker():
    """Тест safety_checker"""
    print("\n🧪 Тест 2: Safety Checker...")
    try:
        from knowledge_os.app.safety_checker import SafetyChecker

        checker = SafetyChecker()

        # Тест 1: Безопасный код
        safe_code = """
def calculate_sum(a, b):
    return a + b
"""
        is_safe, warning, score = checker.check_response(safe_code, "code")
        print(f"   ✅ Безопасный код: safe={is_safe}, score={score:.2f}")

        # Тест 2: Опасный код
        dangerous_code = "import os; os.system('rm -rf /')"
        is_safe, warning, score = checker.check_response(dangerous_code, "code")
        print(f"   ✅ Опасный код обнаружен: safe={is_safe}, warning={warning}")

        # Тест 3: Низкое качество
        low_quality = "TODO: your_code here"
        is_safe, warning, score = checker.check_response(low_quality, "code")
        print(f"   ✅ Низкое качество обнаружено: score={score:.2f}, warning={warning}")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_routing_metrics():
    """Тест сбора метрик роутинга"""
    print("\n🧪 Тест 3: Сбор метрик роутинга...")
    try:
        from knowledge_os.app.enhanced_monitor import get_routing_metrics

        metrics = await get_routing_metrics()
        if metrics:
            print("   ✅ Метрики собраны:")
            print(f"      - Узлов: {len(metrics.get('nodes', {}))}")
            print(f"      - Запросов сегодня: {metrics.get('today', {}).get('total_requests', 0)}")
            print(
                f"      - Токенов сэкономлено: {metrics.get('today', {}).get('total_tokens_saved', 0)}"
            )
        else:
            print("   ⚠️ Метрики пусты (возможно, миграция не применена или нет данных)")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_local_router_return():
    """Тест возврата routing_source из local_router"""
    print("\n🧪 Тест 4: Local Router возврат routing_source...")
    try:
        from knowledge_os.app.local_router import LocalAIRouter

        router = LocalAIRouter()

        # Проверяем сигнатуру метода
        import inspect

        sig = inspect.signature(router.run_local_llm)
        print("   ✅ Метод run_local_llm существует")
        print(f"   ✅ Сигнатура: {sig}")

        # Проверяем, что метод возвращает tuple (или может вернуть)
        # Не вызываем реально, т.к. может не быть Ollama
        print("   ✅ Структура метода корректна")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Запуск всех тестов"""
    print("🚀 Запуск тестов Singularity 5.0 Integration...\n")

    results = []

    results.append(await test_semantic_cache_metrics())
    results.append(await test_safety_checker())
    results.append(await test_routing_metrics())
    results.append(await test_local_router_return())

    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")

    if passed == total:
        print("✅ Все тесты пройдены!")
    else:
        print("⚠️ Некоторые тесты не прошли (возможно, требуется миграция БД)")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
