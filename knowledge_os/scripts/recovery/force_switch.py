#!/usr/bin/env python3
"""
🔄 ПРИНУДИТЕЛЬНОЕ ПЕРЕКЛЮЧЕНИЕ НА ИСПРАВЛЕННУЮ ВЕРСИЮ
Скрипт для принудительного использования исправленной гибридной системы
"""

import logging
import os
import shutil

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def backup_old_version():
    """Создает резервную копию старой версии"""
    try:
        if os.path.exists("signal_live_hybrid.py"):
            shutil.copy("signal_live_hybrid.py", "signal_live_hybrid_backup.py")
            logger.info("✅ Создана резервная копия старой версии")
            return True
    except Exception as e:
        logger.error("❌ Ошибка создания резервной копии: %s", e)
        return False


def replace_with_fixed_version():
    """Заменяет старую версию на исправленную"""
    try:
        if os.path.exists("signal_live_hybrid_fixed.py"):
            shutil.copy("signal_live_hybrid_fixed.py", "signal_live_hybrid.py")
            logger.info("✅ Старая версия заменена на исправленную")
            return True
        else:
            logger.error("❌ Файл signal_live_hybrid_fixed.py не найден")
            return False
    except Exception as e:
        logger.error("❌ Ошибка замены файла: %s", e)
        return False


def create_hybrid_redirect():
    """Создает файл-перенаправление для использования исправленной версии"""
    try:
        redirect_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 ПЕРЕНАПРАВЛЕНИЕ НА ИСПРАВЛЕННУЮ ВЕРСИЮ
Автоматическое перенаправление на signal_live_hybrid_fixed.py
"""

# Импортируем все из исправленной версии
from signal_live_hybrid_fixed import *

# Переопределяем основные функции
check_and_send_signals_hybrid = check_and_send_signals_hybrid_fixed

# Логируем переключение
import logging
logger = logging.getLogger(__name__)
logger.info("🔄 Автоматическое перенаправление на исправленную версию")
'''

        with open("signal_live_hybrid.py", "w", encoding="utf-8") as f:
            f.write(redirect_content)

        logger.info("✅ Создан файл-перенаправление")
        return True

    except Exception as e:
        logger.error("❌ Ошибка создания перенаправления: %s", e)
        return False


def verify_switch():
    """Проверяет успешность переключения"""
    try:
        # Пробуем импортировать исправленную версию
        from signal_live_hybrid_fixed import check_and_send_signals_hybrid_fixed

        logger.info("✅ Исправленная версия доступна для импорта")

        # Пробуем импортировать через перенаправление
        try:
            from signal_live_hybrid import check_and_send_signals_hybrid

            logger.info("✅ Перенаправление работает корректно")
            return True
        except ImportError as e:
            logger.error("❌ Ошибка импорта через перенаправление: %s", e)
            return False

    except ImportError as e:
        logger.error("❌ Ошибка импорта исправленной версии: %s", e)
        return False


def main():
    """Основная функция принудительного переключения"""
    logger.info("🔄 Начинаем принудительное переключение на исправленную версию...")

    success_count = 0
    total_operations = 4

    # 1. Создаем резервную копию
    if backup_old_version():
        success_count += 1

    # 2. Создаем перенаправление
    if create_hybrid_redirect():
        success_count += 1

    # 3. Проверяем переключение
    if verify_switch():
        success_count += 1

    # 4. Дополнительная проверка
    try:
        import signal_live_hybrid

        logger.info("✅ Модуль signal_live_hybrid загружен успешно")
        success_count += 1
    except Exception as e:
        logger.error("❌ Ошибка загрузки модуля: %s", e)

    # Итоговый отчет
    logger.info("\\n" + "=" * 50)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ ПЕРЕКЛЮЧЕНИЯ")
    logger.info("=" * 50)
    logger.info("✅ Успешно выполнено: %d/%d", success_count, total_operations)
    logger.info("📊 Успешность: %.1f%%", success_count / total_operations * 100)

    if success_count >= 3:
        logger.info("🎉 Переключение на исправленную версию выполнено успешно!")
        logger.info("🚀 Теперь система будет использовать исправленную гибридную систему")
        return True
    else:
        logger.warning("⚠️ Переключение выполнено частично")
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("\\n🎉 Переключение завершено успешно!")
        print("🚀 Перезапустите систему для применения изменений")
    else:
        print("\\n⚠️ Переключение выполнено с ошибками")
        print("🔧 Проверьте логи для диагностики")
