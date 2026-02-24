#!/usr/bin/env python3

"""Модуль управления зависимостями ATRA.

Содержит функции для проверки, установки и восстановления
критических зависимостей системы.
"""

import logging
import os
import py_compile
import subprocess
import sys

logger = logging.getLogger(__name__)


def install_dependencies():
    """Автоматическая установка зависимостей из requirements.txt"""
    logger.info("📦 Проверка и установка зависимостей...")

    try:
        # Проверяем наличие requirements.txt
        if not os.path.exists("requirements.txt"):
            logger.warning("⚠️ Файл requirements.txt не найден")
            return False

        # Проверяем, установлен ли pip
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(
                "❌ pip не найден. Установите pip для автоматической установки зависимостей"
            )
            return False

        # Устанавливаем зависимости
        logger.info("🔧 Установка зависимостей из requirements.txt...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            logger.info("✅ Зависимости успешно установлены")
            return True
        else:
            logger.error("❌ Ошибка установки зависимостей: %s", result.stderr)
            return False

    except (OSError, subprocess.SubprocessError) as e:
        logger.error("❌ Ошибка при установке зависимостей: %s", e)
        return False


def check_critical_dependencies():
    """Проверка критически важных зависимостей"""
    logger.info("🔍 Проверка критических зависимостей...")

    # Проверяем, работаем ли мы в виртуальном окружении
    in_venv = hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )
    if in_venv:
        logger.info("✅ Работаем в виртуальном окружении: %s", sys.prefix)
    else:
        logger.info("ℹ️ Работаем в глобальном окружении")

    critical_modules = [
        "pandas",
        "numpy",
        "requests",
        "aiohttp",
        "ta",
        "ccxt",
        "telegram",
        "lightgbm",
        "shap",
    ]

    missing_modules = []

    for module in critical_modules:
        try:
            __import__(module)
            logger.info("✅ %s - установлен", module)
        except ImportError:
            logger.warning("⚠️ %s - не найден", module)
            missing_modules.append(module)

    if missing_modules:
        logger.warning("⚠️ Отсутствуют модули: %s", ", ".join(missing_modules))
        logger.info("🔄 Попытка автоматической установки...")
        return install_dependencies()
    else:
        logger.info("✅ Все критические зависимости установлены")
        return True


def restore_critical_fixes():
    """Восстановление критических исправлений"""
    logger.info("🔧 Проверка и восстановление критических исправлений...")

    try:
        # Проверяем и исправляем синтаксические ошибки в критических файлах
        critical_files = [
            "signal_live.py",
            "telegram_bot.py",
            "main.py",
            "auto_optimizer.py",
        ]

        for file_path in critical_files:
            if os.path.exists(file_path):
                logger.info("🔍 Проверка синтаксиса %s...", file_path)

                # Проверяем синтаксис
                try:
                    py_compile.compile(file_path, doraise=True)
                    logger.info("✅ Синтаксис %s корректен", file_path)
                except SyntaxError as syntax_error:
                    logger.error("❌ Синтаксическая ошибка в %s: %s", file_path, syntax_error)

                    # Автоматическое исправление известных ошибок
                    if file_path == "signal_live.py":
                        fix_signal_live_syntax()
                    elif file_path == "telegram_bot.py":
                        fix_telegram_bot_syntax()
                    else:
                        logger.warning(
                            "⚠️ Автоматическое исправление для %s не реализовано",
                            file_path,
                        )

        # ОТКЛЮЧЕНО: Автоматическое восстановление из кэша
        # Система кэширования отключена для предотвращения восстановления ошибок
        logger.info("ℹ️ Автоматическое восстановление отключено")

    except (OSError, py_compile.PyCompileError, SyntaxError) as e:
        logger.error("❌ Ошибка восстановления исправлений: %s", e)


def fix_signal_live_syntax():
    """Автоматическое исправление отключено для предотвращения перезаписи файла"""
    logger.info("ℹ️ Автоматическое исправление signal_live.py отключено")
    return True


def fix_telegram_bot_syntax():
    """Автоматическое исправление синтаксических ошибок в telegram_bot.py"""
    logger.info("🔧 Автоматическое исправление telegram_bot.py...")

    try:
        with open("telegram_bot.py", encoding="utf-8") as f:
            content = f.read()

        # Известные исправления для telegram_bot.py
        fixes = [
            ("2.4", "2.4"),
            ("0.0", "0.0"),
        ]

        original_content = content
        for old, new in fixes:
            content = content.replace(old, new)

        if content != original_content:
            with open("telegram_bot.py", "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("✅ Синтаксические ошибки в telegram_bot.py исправлены")

            # Проверяем синтаксис после исправления
            py_compile.compile("telegram_bot.py", doraise=True)
            logger.info("✅ Синтаксис telegram_bot.py проверен после исправления")
        else:
            logger.info("ℹ️ Синтаксические ошибки в telegram_bot.py не найдены")

    except (OSError, UnicodeDecodeError, UnicodeEncodeError) as e:
        logger.error("❌ Ошибка исправления telegram_bot.py: %s", e)
