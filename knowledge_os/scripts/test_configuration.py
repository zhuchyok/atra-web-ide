#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка конфигурации
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# Импорты после sys.path.insert необходимы для корректной работы
# pylint: disable=wrong-import-position
from scripts.test_utils import (
    TestResult, TestStatus, check_file_exists, measure_time, get_file_path
)
from scripts.test_config import TELEGRAM_TOKENS
# pylint: enable=wrong-import-position


@measure_time
def test_environment_detection() -> TestResult:
    """Проверяет определение окружения (PROD/DEV)"""
    try:
        # pylint: disable=import-outside-toplevel
        from config import ATRA_ENV

        env = ATRA_ENV.lower().strip()

        if env not in ["prod", "dev"]:
            return TestResult(
                name="Определение окружения",
                status=TestStatus.WARNING,
                message=f"Неизвестное окружение: {env}",
                details={"detected_env": env},
                recommendations=[
                    "Установите ATRA_ENV=prod или ATRA_ENV=dev",
                    "Проверьте файлы env.prod или env.dev"
                ]
            )

        # Проверяем наличие файлов окружения
        env_files = {
            "prod": ["env.prod", ".env.prod"],
            "dev": ["env.dev", ".env.dev"]
        }

        found_files = []
        for env_file in env_files.get(env, []):
            if check_file_exists(get_file_path(env_file)) or check_file_exists(env_file):
                found_files.append(env_file)

        return TestResult(
            name="Определение окружения",
            status=TestStatus.PASS,
            message=f"Окружение определено как: {env.upper()}",
            details={
                "detected_env": env,
                "env_files_found": found_files
            }
        )
    except ImportError as e:
        return TestResult(
            name="Определение окружения",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать config: {str(e)}",
            recommendations=["Проверьте наличие config.py"]
        )
    except Exception as e:
        return TestResult(
            name="Определение окружения",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке окружения: {str(e)}"
        )


@measure_time
def test_telegram_token() -> TestResult:
    """Проверяет корректность токена Telegram"""
    try:
        # pylint: disable=import-outside-toplevel
        from config import ATRA_ENV, TOKEN, TELEGRAM_TOKEN_DEV

        env = ATRA_ENV.lower().strip()

        # Определяем, какой токен должен использоваться
        expected_token = TELEGRAM_TOKENS.get(env.upper())
        actual_token = TOKEN if env == "prod" else (TELEGRAM_TOKEN_DEV or TOKEN)

        if not actual_token:
            return TestResult(
                name="Токен Telegram",
                status=TestStatus.FAIL,
                message=f"Токен Telegram не установлен для окружения {env}",
                details={"environment": env},
                recommendations=[
                    "Установите TELEGRAM_TOKEN для PROD или TELEGRAM_TOKEN_DEV для DEV",
                    f"Проверьте файлы env.{env} или .env.{env}"
                ]
            )

        # Проверяем формат токена (должен быть в формате NUMBER:STRING)
        if ":" not in actual_token:
            return TestResult(
                name="Токен Telegram",
                status=TestStatus.FAIL,
                message="Неверный формат токена Telegram",
                details={"token_format": "invalid"},
                recommendations=["Токен должен быть в формате NUMBER:STRING"]
            )

        # Проверяем соответствие ожидаемому токену (если указан)
        if expected_token and actual_token != expected_token:
            return TestResult(
                name="Токен Telegram",
                status=TestStatus.WARNING,
                message=f"Токен не соответствует ожидаемому для {env}",
                details={
                    "environment": env,
                    "expected_prefix": expected_token[:10] if expected_token else None,
                    "actual_prefix": actual_token[:10]
                },
                recommendations=[
                    f"Убедитесь, что используется правильный токен для {env}",
                    f"DEV токен: {TELEGRAM_TOKENS['DEV'][:20]}...",
                    f"PROD токен: {TELEGRAM_TOKENS['PROD'][:20]}..."
                ]
            )

        return TestResult(
            name="Токен Telegram",
            status=TestStatus.PASS,
            message=f"Токен Telegram корректно настроен для {env}",
            details={
                "environment": env,
                "token_prefix": actual_token[:10] + "..."
            }
        )
    except ImportError as e:
        return TestResult(
            name="Токен Telegram",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать config: {str(e)}"
        )
    except Exception as e:
        return TestResult(
            name="Токен Telegram",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке токена: {str(e)}"
        )


@measure_time
def test_auto_execution_blocked_in_dev() -> TestResult:
    """Проверяет, что авто-исполнение заблокировано в DEV"""
    try:
        # pylint: disable=import-outside-toplevel
        from config import ATRA_ENV

        env = ATRA_ENV.lower().strip()

        if env != "dev":
            return TestResult(
                name="Блокировка авто-исполнения в DEV",
                status=TestStatus.SKIP,
                message=f"Проверка не применима для окружения {env}",
                details={"environment": env}
            )

        # Проверяем наличие флага AUTO_EXECUTION_ENABLED
        try:
            # pylint: disable=import-outside-toplevel
            from config import AUTO_EXECUTION_ENABLED

            # В DEV окружении AUTO_EXECUTION_ENABLED должен быть False
            if AUTO_EXECUTION_ENABLED and env == "dev":
                return TestResult(
                    name="Блокировка авто-исполнения в DEV",
                    status=TestStatus.FAIL,
                    message="Авто-исполнение включено в DEV окружении",
                    details={
                        "environment": env,
                        "auto_execution_enabled": AUTO_EXECUTION_ENABLED
                    },
                    recommendations=[
                        "Отключите AUTO_EXECUTION_ENABLED в DEV",
                        "Установите AUTO_EXECUTION_ENABLED=false в env.dev"
                    ]
                )

            return TestResult(
                name="Блокировка авто-исполнения в DEV",
                status=TestStatus.PASS,
                message="Авто-исполнение корректно заблокировано в DEV",
                details={
                    "environment": env,
                    "auto_execution_enabled": AUTO_EXECUTION_ENABLED
                }
            )
        except ImportError:
            # Если флаг не определен, проверяем логику в auto_execution.py
            try:
                # pylint: disable=import-outside-toplevel,unused-import
                from src.execution import auto_execution  # noqa: F401
                # Проверяем, есть ли проверка окружения в модуле
                # Используем модуль для проверки его наличия
                _ = auto_execution  # noqa: F841
                return TestResult(
                    name="Блокировка авто-исполнения в DEV",
                    status=TestStatus.WARNING,
                    message="Не удалось проверить флаг AUTO_EXECUTION_ENABLED",
                    details={"environment": env},
                    recommendations=[
                        "Убедитесь, что auto_execution.py проверяет ATRA_ENV",
                        "Добавьте явную проверку окружения в код"
                    ]
                )
            except ImportError:
                return TestResult(
                    name="Блокировка авто-исполнения в DEV",
                    status=TestStatus.WARNING,
                    message="Модуль auto_execution не найден",
                    details={"environment": env}
                )
    except ImportError as e:
        return TestResult(
            name="Блокировка авто-исполнения в DEV",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать config: {str(e)}"
        )
    except Exception as e:
        return TestResult(
            name="Блокировка авто-исполнения в DEV",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_exchange_api_keys() -> TestResult:
    """Проверяет наличие API ключей биржи"""
    try:
        # pylint: disable=import-outside-toplevel
        from config import ATRA_ENV

        env = ATRA_ENV.lower().strip()

        # Проверяем наличие переменных окружения для API ключей
        api_key = os.getenv("BITGET_API_KEY")
        api_secret = os.getenv("BITGET_SECRET_KEY")
        api_passphrase = os.getenv("BITGET_PASSPHRASE")

        if not api_key or not api_secret:
            # В DEV окружении это нормально - API ключи не обязательны
            if env == "dev":
                return TestResult(
                    name="API ключи биржи",
                    status=TestStatus.PASS,
                    message="API ключи не установлены (нормально для DEV окружения)",
                    details={
                        "environment": env,
                        "api_key_set": bool(api_key),
                        "api_secret_set": bool(api_secret),
                        "api_passphrase_set": bool(api_passphrase),
                        "note": "API ключи не обязательны для тестирования сигналов в DEV"
                    },
                    recommendations=[
                        "Для тестирования исполнения ордеров установите BITGET_API_KEY и BITGET_SECRET_KEY",
                        "В DEV окружении это не критично"
                    ]
                )
            else:
                # В PROD это предупреждение
                return TestResult(
                    name="API ключи биржи",
                    status=TestStatus.WARNING,
                    message="API ключи биржи не установлены в PROD окружении",
                    details={
                        "environment": env,
                        "api_key_set": bool(api_key),
                        "api_secret_set": bool(api_secret),
                        "api_passphrase_set": bool(api_passphrase)
                    },
                    recommendations=[
                        "Для работы в PROD установите BITGET_API_KEY и BITGET_SECRET_KEY",
                        "Проверьте файлы env.prod"
                    ]
                )

        return TestResult(
            name="API ключи биржи",
            status=TestStatus.PASS,
            message="API ключи биржи настроены",
            details={
                "environment": env,
                "api_key_set": True,
                "api_secret_set": True,
                "api_passphrase_set": bool(api_passphrase)
            }
        )
    except Exception as e:
        return TestResult(
            name="API ключи биржи",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке API ключей: {str(e)}"
        )


@measure_time
def test_filter_configuration() -> TestResult:
    """Проверяет конфигурацию фильтров"""
    try:
        # Проверяем наличие конфигурационных файлов фильтров
        config_files = [
            "src/filters/config.py",
            "config.py"
        ]

        found_files = []
        missing_files = []

        for config_file in config_files:
            if check_file_exists(get_file_path(config_file)):
                found_files.append(config_file)
            else:
                missing_files.append(config_file)

        # Проверяем наличие ключевых параметров
        try:
            # pylint: disable=import-outside-toplevel
            from config import (
                USE_ADAPTIVE_STRATEGY,
                BTC_TREND_EMA_SOFT,
                BTC_TREND_EMA_STRICT
            )

            config_params = {
                "USE_ADAPTIVE_STRATEGY": USE_ADAPTIVE_STRATEGY,
                "BTC_TREND_EMA_SOFT": BTC_TREND_EMA_SOFT,
                "BTC_TREND_EMA_STRICT": BTC_TREND_EMA_STRICT
            }

            return TestResult(
                name="Конфигурация фильтров",
                status=TestStatus.PASS,
                message="Конфигурация фильтров доступна",
                details={
                    "config_files": found_files,
                    "parameters": config_params
                }
            )
        except ImportError:
            return TestResult(
                name="Конфигурация фильтров",
                status=TestStatus.WARNING,
                message="Некоторые параметры фильтров не найдены",
                details={"config_files": found_files},
                recommendations=["Проверьте наличие всех параметров в config.py"]
            )
    except Exception as e:
        return TestResult(
            name="Конфигурация фильтров",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке конфигурации: {str(e)}"
        )


def run_all_config_tests() -> list:
    """Запускает все тесты конфигурации"""
    tests = [
        test_environment_detection,
        test_telegram_token,
        test_auto_execution_blocked_in_dev,
        test_exchange_api_keys,
        test_filter_configuration
    ]

    test_results = []
    for test_func in tests:
        try:
            result = test_func()
            test_results.append(result)
            print(result)
        except Exception as e:
            test_results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))

    return test_results


if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА КОНФИГУРАЦИИ")
    print("=" * 60)

    results = run_all_config_tests()

    from scripts.test_utils import print_test_summary
    print_test_summary(results)
