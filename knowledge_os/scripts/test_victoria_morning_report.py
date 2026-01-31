#!/usr/bin/env python3
"""
Комплексный тест всех компонентов утреннего отчета Виктории.
Проверяет доступность всех зависимостей и компонентов.
"""

import asyncio
import os
import sys
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Настройки
TG_TOKEN = os.getenv("PROD_TELEGRAM_TOKEN", "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", '556251171')

# Результаты тестов
test_results: Dict[str, Dict[str, any]] = {}

def test_result(name: str, status: str, details: str = "", error: Optional[Exception] = None):
    """Записывает результат теста"""
    test_results[name] = {
        "status": status,  # "PASS", "FAIL", "WARN"
        "details": details,
        "error": str(error) if error else None,
        "timestamp": datetime.now().isoformat()
    }
    emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    logger.info(f"{emoji} {name}: {status}")
    if details:
        logger.info(f"   {details}")
    if error:
        logger.error(f"   Ошибка: {error}")

async def test_database_connection():
    """Тест 1: Подключение к базе данных"""
    try:
        import asyncpg
        import getpass
        
        user_name = getpass.getuser()
        if user_name == 'zhuchyok':
            default_url = f'postgresql://{user_name}@localhost:5432/knowledge_os'
        else:
            default_url = 'postgresql://admin:secret@localhost:5432/knowledge_os'
        
        db_url = os.getenv('DATABASE_URL', default_url)
        
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3, timeout=5)
        
        async with pool.acquire() as conn:
            # Проверяем подключение
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                # Проверяем наличие таблиц
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('experts', 'okrs', 'knowledge_nodes', 'interaction_logs')
                """)
                table_names = [t['table_name'] for t in tables]
                
                if len(table_names) >= 4:
                    test_result("Database Connection", "PASS", f"Подключено. Таблицы: {', '.join(table_names)}")
                else:
                    test_result("Database Connection", "WARN", f"Подключено, но не все таблицы найдены: {table_names}")
            else:
                test_result("Database Connection", "FAIL", "Подключение установлено, но запрос не вернул ожидаемый результат")
        
        await pool.close()
    except Exception as e:
        test_result("Database Connection", "FAIL", f"Не удалось подключиться к БД", e)

async def test_ai_core_import():
    """Тест 2: Импорт ai_core"""
    try:
        # Добавляем путь к app директории
        app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')
        app_dir = os.path.abspath(app_dir)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        from ai_core import run_smart_agent_async, run_smart_agent_sync
        
        if run_smart_agent_async and run_smart_agent_sync:
            test_result("AI Core Import", "PASS", "Модуль ai_core успешно импортирован")
        else:
            test_result("AI Core Import", "FAIL", "Модуль импортирован, но функции недоступны")
    except ImportError as e:
        test_result("AI Core Import", "FAIL", "Не удалось импортировать ai_core", e)
    except Exception as e:
        test_result("AI Core Import", "FAIL", "Ошибка при импорте", e)

async def test_ai_core_execution():
    """Тест 3: Выполнение ai_core (быстрый тест)"""
    try:
        app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')
        app_dir = os.path.abspath(app_dir)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        from ai_core import run_smart_agent_async
        
        # Простой тестовый промпт с коротким таймаутом
        test_prompt = "Скажи 'Тест пройден' одним предложением."
        
        try:
            result = await asyncio.wait_for(
                run_smart_agent_async(test_prompt, expert_name="Виктория", category="test"),
                timeout=30
            )
            
            if result and str(result).strip():
                test_result("AI Core Execution", "PASS", f"Ответ получен: {str(result)[:100]}...")
            else:
                test_result("AI Core Execution", "WARN", "Ответ получен, но пустой")
        except asyncio.TimeoutError:
            test_result("AI Core Execution", "FAIL", "Таймаут выполнения (30s)")
        except Exception as e:
            test_result("AI Core Execution", "FAIL", f"Ошибка выполнения", e)
    except Exception as e:
        test_result("AI Core Execution", "FAIL", f"Не удалось выполнить тест", e)

async def test_dependencies_import():
    """Тест 4: Импорт зависимостей"""
    dependencies = {
        "distillation_engine": "KnowledgeDistiller",
        "training_pipeline": "LocalTrainingPipeline",
        "asyncpg": "asyncpg",
        "requests": "requests"
    }
    
    failed = []
    passed = []
    
    for module_name, class_name in dependencies.items():
        try:
            if module_name == "asyncpg":
                import asyncpg
                passed.append(module_name)
            elif module_name == "requests":
                import requests
                passed.append(module_name)
            else:
                app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')
                app_dir = os.path.abspath(app_dir)
                if app_dir not in sys.path:
                    sys.path.insert(0, app_dir)
                
                module = __import__(module_name)
                if hasattr(module, class_name):
                    passed.append(module_name)
                else:
                    failed.append(f"{module_name} (класс {class_name} не найден)")
        except ImportError:
            failed.append(module_name)
        except Exception as e:
            failed.append(f"{module_name} ({str(e)[:50]})")
    
    if failed:
        test_result("Dependencies Import", "WARN", 
                   f"Пройдено: {', '.join(passed)}, Провалено: {', '.join(failed)}")
    else:
        test_result("Dependencies Import", "PASS", f"Все зависимости доступны: {', '.join(passed)}")

def test_telegram_api():
    """Тест 5: Telegram API"""
    try:
        url = f'https://api.telegram.org/bot{TG_TOKEN}/getMe'
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                bot_info = data.get('result', {})
                bot_name = bot_info.get('first_name', 'Unknown')
                test_result("Telegram API", "PASS", f"Бот доступен: {bot_name}")
            else:
                test_result("Telegram API", "FAIL", f"API вернул ошибку: {data.get('description', 'Unknown')}")
        else:
            test_result("Telegram API", "FAIL", f"HTTP {response.status_code}: {response.text[:100]}")
    except requests.exceptions.Timeout:
        test_result("Telegram API", "FAIL", "Таймаут подключения к Telegram API")
    except Exception as e:
        test_result("Telegram API", "FAIL", f"Ошибка подключения", e)

async def test_database_queries():
    """Тест 6: Выполнение SQL запросов из отчета"""
    try:
        import asyncpg
        import getpass
        
        user_name = getpass.getuser()
        if user_name == 'zhuchyok':
            default_url = f'postgresql://{user_name}@localhost:5432/knowledge_os'
        else:
            default_url = 'postgresql://admin:secret@localhost:5432/knowledge_os'
        
        db_url = os.getenv('DATABASE_URL', default_url)
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3, timeout=5)
        
        async with pool.acquire() as conn:
            queries = {
                "Experts": "SELECT COUNT(*) FROM experts WHERE name = 'Виктория'",
                "Finance Stats": "SELECT COALESCE(SUM(token_usage), 0) as total_tokens FROM interaction_logs WHERE created_at > NOW() - INTERVAL '24 hours'",
                "OKRs": "SELECT COUNT(*) FROM okrs WHERE period = '2025-Q4'",
                "Knowledge Nodes": "SELECT COUNT(*) FROM knowledge_nodes WHERE created_at > NOW() - INTERVAL '12 hours'"
            }
            
            results = {}
            for name, query in queries.items():
                try:
                    result = await conn.fetchval(query)
                    results[name] = result
                except Exception as e:
                    results[name] = f"ERROR: {str(e)[:50]}"
            
            all_ok = all(not str(v).startswith("ERROR") for v in results.values())
            if all_ok:
                test_result("Database Queries", "PASS", f"Все запросы выполнены: {results}")
            else:
                test_result("Database Queries", "WARN", f"Некоторые запросы не выполнены: {results}")
        
        await pool.close()
    except Exception as e:
        test_result("Database Queries", "FAIL", f"Ошибка выполнения запросов", e)

async def test_full_report_generation():
    """Тест 7: Полная генерация отчета (без отправки)"""
    try:
        app_dir = os.path.join(os.path.dirname(__file__), '..', 'app')
        app_dir = os.path.abspath(app_dir)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        # Импортируем функцию генерации отчета
        from victoria_morning_report import generate_morning_plan
        
        # Запускаем генерацию с таймаутом
        try:
            await asyncio.wait_for(generate_morning_plan(), timeout=90)
            test_result("Full Report Generation", "PASS", "Отчет успешно сгенерирован")
        except asyncio.TimeoutError:
            test_result("Full Report Generation", "FAIL", "Таймаут генерации отчета (90s)")
        except Exception as e:
            test_result("Full Report Generation", "FAIL", f"Ошибка генерации", e)
    except Exception as e:
        test_result("Full Report Generation", "FAIL", f"Не удалось запустить генерацию", e)

def print_summary():
    """Выводит итоговую сводку тестов"""
    print("\n" + "="*70)
    print("📊 ИТОГОВАЯ СВОДКА ТЕСТОВ")
    print("="*70)
    
    total = len(test_results)
    passed = sum(1 for r in test_results.values() if r['status'] == 'PASS')
    failed = sum(1 for r in test_results.values() if r['status'] == 'FAIL')
    warned = sum(1 for r in test_results.values() if r['status'] == 'WARN')
    
    print(f"\nВсего тестов: {total}")
    print(f"✅ Пройдено: {passed}")
    print(f"⚠️  Предупреждений: {warned}")
    print(f"❌ Провалено: {failed}")
    
    if failed > 0:
        print("\n❌ ПРОВАЛЕННЫЕ ТЕСТЫ:")
        for name, result in test_results.items():
            if result['status'] == 'FAIL':
                print(f"   - {name}")
                if result['error']:
                    print(f"     Ошибка: {result['error']}")
    
    if warned > 0:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for name, result in test_results.items():
            if result['status'] == 'WARN':
                print(f"   - {name}: {result['details']}")
    
    print("\n" + "="*70)
    
    if failed == 0:
        print("✅ ВСЕ КРИТИЧЕСКИЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("   Утренний доклад должен работать корректно")
    else:
        print("❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ")
        print("   Необходимо исправить проваленные тесты перед запуском")
    
    print("="*70 + "\n")

async def main():
    """Основная функция запуска тестов"""
    print("🧪 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ УТРЕННЕГО ОТЧЕТА ВИКТОРИИ")
    print("="*70)
    print()
    
    # Запускаем все тесты
    await test_database_connection()
    await test_dependencies_import()
    test_telegram_api()
    await test_ai_core_import()
    await test_database_queries()
    await test_ai_core_execution()
    await test_full_report_generation()
    
    # Выводим итоговую сводку
    print_summary()
    
    # Возвращаем код выхода
    failed_count = sum(1 for r in test_results.values() if r['status'] == 'FAIL')
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == '__main__':
    asyncio.run(main())

