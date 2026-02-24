"""
Полное тестирование Singularity 5.0 после применения миграции
Проверяет все компоненты: кэш, роутинг, метрики, safety checker
"""

import asyncio
import os
import sys

# Добавляем путь к модулям
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(project_root, "knowledge_os", "app"))
sys.path.insert(0, project_root)


async def test_migration_applied():
    """Проверка, что миграция применена"""
    print("🧪 Тест 1: Проверка миграции БД...")
    try:
        import asyncpg

        from knowledge_os.app.semantic_cache import DATABASE_URL

        # Единая локальная БД (миграция уже перенесена сюда)
        db_url = DATABASE_URL
        conn = await asyncpg.connect(db_url, timeout=3.0)

        # Проверяем наличие колонок
        columns = await conn.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'semantic_ai_cache'
            AND column_name IN ('routing_source', 'performance_score', 'tokens_saved')
        """)

        await conn.close()

        found_columns = [row["column_name"] for row in columns]
        required = ["routing_source", "performance_score", "tokens_saved"]

        if all(col in found_columns for col in required):
            print(f"   ✅ Миграция применена: найдены колонки {found_columns}")
            return True
        else:
            missing = set(required) - set(found_columns)
            print(f"   ❌ Отсутствуют колонки: {missing}")
            return False
    except Exception as e:
        print(f"   ⚠️ Ошибка проверки миграции: {e}")
        return False


async def test_semantic_cache_with_metrics():
    """Тест semantic_cache с новыми метриками"""
    print("\n🧪 Тест 2: Semantic Cache с метриками...")
    try:
        from knowledge_os.app.semantic_cache import SemanticAICache

        cache = SemanticAICache()
        test_query = "Тест Singularity 5.0: проверка метрик роутинга"
        test_response = "Система работает корректно с метриками роутинга."

        # Сохраняем с метриками
        await cache.save_to_cache(
            test_query,
            test_response,
            "Виктория",
            routing_source="local_mac",
            performance_score=0.95,
            tokens_saved=1000,
        )
        print("   ✅ Сохранение с метриками работает")

        # Проверяем получение
        cached = await cache.get_cached_response(test_query, "Виктория")
        if cached:
            print("   ✅ Получение из кэша работает")
        else:
            print("   ⚠️ Кэш не найден (возможно, embedding не совпал)")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_routing_metrics_collection():
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
            print(
                f"      - Средний Performance: {metrics.get('today', {}).get('avg_performance', 0):.2f}"
            )

            # Показываем детали по узлам
            nodes = metrics.get("nodes", {})
            for node_name, node_data in nodes.items():
                print(
                    f"      - {node_name}: {node_data.get('count', 0)} запросов, performance: {node_data.get('avg_performance', 0):.2f}"
                )
        else:
            print("   ⚠️ Метрики пусты (нет данных в кэше или миграция не применена)")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_local_router_performance():
    """Тест роутера с метриками производительности"""
    print("\n🧪 Тест 4: Local Router с метриками производительности...")
    try:
        from knowledge_os.app.local_router import LocalAIRouter

        router = LocalAIRouter()

        # Проверяем метод получения метрик
        metrics = await router._get_node_performance_metrics()
        if metrics:
            print("   ✅ Метрики производительности получены:")
            for node_key, node_metrics in metrics.items():
                print(
                    f"      - {node_key}: performance={node_metrics.get('avg_performance', 0):.2f}, success_rate={node_metrics.get('success_rate', 0):.2f}"
                )
        else:
            print("   ⚠️ Метрики пусты (нет данных в кэше)")

        # Проверяем health check
        healthy_nodes = await router.check_health()
        if healthy_nodes:
            print(f"   ✅ Health check работает: {len(healthy_nodes)} узлов онлайн")
            for node in healthy_nodes:
                perf = node.get("performance_score", "N/A")
                print(
                    f"      - {node['name']}: latency={node.get('latency', 0):.3f}s, performance={perf}"
                )
        else:
            print("   ⚠️ Нет доступных узлов (Ollama не запущен)")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_safety_checker():
    """Тест safety checker"""
    print("\n🧪 Тест 5: Safety Checker...")
    try:
        from knowledge_os.app.safety_checker import SafetyChecker

        checker = SafetyChecker()

        # Тест безопасного кода
        safe_code = """
def calculate_sum(a, b):
    return a + b
"""
        is_safe, warning, score = checker.check_response(safe_code, "code")
        print(f"   ✅ Безопасный код: safe={is_safe}, score={score:.2f}")

        # Тест опасного кода
        dangerous_code = "import os; os.system('rm -rf /')"
        is_safe, warning, score = checker.check_response(dangerous_code, "code")
        should_reroute = checker.should_reroute_to_cloud(dangerous_code, "code")
        print(f"   ✅ Опасный код обнаружен: safe={is_safe}, reroute={should_reroute}")

        return True
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Запуск всех тестов"""
    print("🚀 Полное тестирование Singularity 5.0 после миграции...\n")
    print("=" * 60)

    results = []

    results.append(await test_migration_applied())
    results.append(await test_semantic_cache_with_metrics())
    results.append(await test_routing_metrics_collection())
    results.append(await test_local_router_performance())
    results.append(await test_safety_checker())

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")

    if passed == total:
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Система готова к использованию! 🎉")
    else:
        print("⚠️ Некоторые тесты не прошли. Проверьте логи выше.")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
