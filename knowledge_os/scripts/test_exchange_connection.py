#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка подключения к бирже
"""

import sys
import os
import asyncio
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Загружаем переменные окружения: сначала env (шаблон), потом .env (реальные ключи)
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    
    # Сначала загружаем env (шаблон, может быть закоммичен)
    env_file = project_root / 'env'
    if env_file.exists():
        load_dotenv(env_file, override=False)
    
    # Затем загружаем .env (реальные ключи, в .gitignore) - перезаписывает пустые значения
    env_file_dot = project_root / '.env'
    if env_file_dot.exists():
        load_dotenv(env_file_dot, override=True)
except ImportError:
    pass

from scripts.test_utils import TestResult, TestStatus, measure_time


@measure_time
def test_exchange_adapter_import() -> TestResult:
    """Проверяет возможность импорта ExchangeAdapter"""
    try:
        from exchange_adapter import ExchangeAdapter
        
        return TestResult(
            name="Импорт ExchangeAdapter",
            status=TestStatus.PASS,
            message="ExchangeAdapter успешно импортирован",
            details={"module": "exchange_adapter"}
        )
    except ImportError as e:
        return TestResult(
            name="Импорт ExchangeAdapter",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать ExchangeAdapter: {str(e)}",
            recommendations=[
                "Установите зависимости: pip install ccxt",
                "Проверьте наличие файла exchange_adapter.py"
            ]
        )
    except Exception as e:
        return TestResult(
            name="Импорт ExchangeAdapter",
            status=TestStatus.FAIL,
            message=f"Ошибка при импорте: {str(e)}"
        )


@measure_time
async def test_exchange_connection() -> TestResult:
    """Проверяет подключение к бирже"""
    try:
        from exchange_adapter import ExchangeAdapter
        
        # Получаем API ключи из окружения
        api_key = os.getenv("BITGET_API_KEY")
        api_secret = os.getenv("BITGET_SECRET_KEY")
        api_passphrase = os.getenv("BITGET_PASSPHRASE")
        
        if not api_key or not api_secret:
            return TestResult(
                name="Подключение к бирже",
                status=TestStatus.SKIP,
                message="API ключи не установлены, пропускаем проверку подключения",
                details={
                    "api_key_set": bool(api_key),
                    "api_secret_set": bool(api_secret)
                },
                recommendations=[
                    "Для полной проверки установите BITGET_API_KEY и BITGET_SECRET_KEY",
                    "Это не критично для тестирования сигналов"
                ]
            )
        
        # Создаем адаптер
        keys = {
            "api_key": api_key,
            "secret": api_secret,
            "passphrase": api_passphrase or ""
        }
        
        adapter = ExchangeAdapter(
            exchange="bitget",
            keys=keys,
            sandbox=True,  # Используем sandbox для тестирования
            trade_mode="futures"
        )
        
        if adapter.client is None:
            return TestResult(
                name="Подключение к бирже",
                status=TestStatus.FAIL,
                message="Не удалось создать клиент биржи",
                recommendations=[
                    "Проверьте корректность API ключей",
                    "Убедитесь, что библиотека ccxt установлена"
                ]
            )
        
        # Пробуем выполнить простой запрос (публичный)
        try:
            # Публичный запрос не требует API ключей
            markets = adapter.client.load_markets()
            
            return TestResult(
                name="Подключение к бирже",
                status=TestStatus.PASS,
                message="Подключение к бирже успешно",
                details={
                    "exchange": "bitget",
                    "markets_loaded": len(markets) if markets else 0
                },
                metrics={"markets_count": len(markets) if markets else 0}
            )
        except Exception as e:
            return TestResult(
                name="Подключение к бирже",
                status=TestStatus.WARNING,
                message=f"Ошибка при запросе к бирже: {str(e)}",
                details={"error": str(e)},
                recommendations=[
                    "Проверьте интернет-соединение",
                    "Возможно, биржа временно недоступна"
                ]
            )
    except ImportError as e:
        return TestResult(
            name="Подключение к бирже",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать модули: {str(e)}"
        )
    except Exception as e:
        return TestResult(
            name="Подключение к бирже",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке подключения: {str(e)}"
        )


@measure_time
async def test_exchange_balance() -> TestResult:
    """Проверяет получение баланса (требует API ключи)"""
    try:
        from exchange_adapter import ExchangeAdapter
        
        api_key = os.getenv("BITGET_API_KEY")
        api_secret = os.getenv("BITGET_SECRET_KEY")
        api_passphrase = os.getenv("BITGET_PASSPHRASE")
        
        if not api_key or not api_secret:
            return TestResult(
                name="Баланс биржи",
                status=TestStatus.SKIP,
                message="API ключи не установлены, пропускаем проверку баланса"
            )
        
        keys = {
            "api_key": api_key,
            "secret": api_secret,
            "passphrase": api_passphrase or ""
        }
        
        adapter = ExchangeAdapter(
            exchange="bitget",
            keys=keys,
            sandbox=True,
            trade_mode="futures"
        )
        
        if adapter.client is None:
            return TestResult(
                name="Баланс биржи",
                status=TestStatus.SKIP,
                message="Клиент биржи не создан"
            )
        
        try:
            # Пробуем получить баланс
            balance = await adapter.client.fetch_balance()
            
            return TestResult(
                name="Баланс биржи",
                status=TestStatus.PASS,
                message="Баланс успешно получен",
                details={
                    "currencies": list(balance.get("total", {}).keys())[:5] if balance else []
                }
            )
        except Exception as e:
            return TestResult(
                name="Баланс биржи",
                status=TestStatus.WARNING,
                message=f"Не удалось получить баланс: {str(e)}",
                recommendations=[
                    "Проверьте права API ключей",
                    "Убедитесь, что ключи имеют доступ к чтению баланса"
                ]
            )
    except Exception as e:
        return TestResult(
            name="Баланс биржи",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке баланса: {str(e)}"
        )


@measure_time
def test_symbol_format() -> TestResult:
    """Проверяет формат символов (BTCUSDT)"""
    # Проверяем, что символы в правильном формате
    test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    # Формат должен быть: BASEQUOTE (например, BTCUSDT)
    invalid_symbols = []
    valid_symbols = []
    
    for symbol in test_symbols:
        # Простая проверка формата
        if len(symbol) >= 6 and symbol.endswith("USDT"):
            valid_symbols.append(symbol)
        else:
            invalid_symbols.append(symbol)
    
    if invalid_symbols:
        return TestResult(
            name="Формат символов",
            status=TestStatus.WARNING,
            message=f"Некорректный формат символов: {len(invalid_symbols)}",
            details={"invalid": invalid_symbols, "valid": valid_symbols},
            recommendations=[
                "Символы должны быть в формате BASEQUOTE (например, BTCUSDT)",
                "Проверьте список символов в config.py"
            ]
        )
    
    return TestResult(
        name="Формат символов",
        status=TestStatus.PASS,
        message="Формат символов корректен",
        details={"tested_symbols": valid_symbols}
    )


async def run_all_exchange_tests() -> list:
    """Запускает все тесты подключения к бирже"""
    results = []
    
    # Синхронные тесты
    sync_tests = [
        test_exchange_adapter_import,
        test_symbol_format
    ]
    
    for test_func in sync_tests:
        try:
            result = test_func()
            results.append(result)
            print(result)
        except Exception as e:
            results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))
    
    # Асинхронные тесты
    async_tests = [
        test_exchange_connection,
        test_exchange_balance
    ]
    
    for test_func in async_tests:
        try:
            result = await test_func()
            results.append(result)
            print(result)
        except Exception as e:
            results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА ПОДКЛЮЧЕНИЯ К БИРЖЕ")
    print("=" * 60)
    
    results = asyncio.run(run_all_exchange_tests())
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

