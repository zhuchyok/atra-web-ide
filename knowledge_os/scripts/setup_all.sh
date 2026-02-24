#!/bin/bash
# Полная автоматическая настройка Singularity 8.0

echo "🚀 Singularity 8.0: Полная автоматическая настройка"
echo "=================================================="
echo ""

# 1. Установка зависимостей
echo "📦 Шаг 1: Установка зависимостей..."
python3 knowledge_os/scripts/install_dependencies.py
if [ $? -ne 0 ]; then
    echo "❌ Ошибка установки зависимостей"
    exit 1
fi

echo ""

# 2. Настройка переменных окружения
echo "🔧 Шаг 2: Настройка переменных окружения..."
python3 knowledge_os/scripts/setup_environment.py

echo ""

# 3. Инициализация Secret Manager
echo "🔐 Шаг 3: Инициализация Secret Manager..."
python3 knowledge_os/scripts/init_secret_manager.py

echo ""

# 4. Проверка ML данных
echo "🤖 Шаг 4: Проверка данных для ML-модели..."
python3 knowledge_os/scripts/check_ml_training_data.py

echo ""

# 5. Финальная проверка готовности
echo "✅ Шаг 5: Финальная проверка готовности..."
python3 knowledge_os/scripts/check_system_ready.py

echo ""
echo "=================================================="
echo "🎉 Настройка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "  1. Отредактируйте .env файл и укажите реальные токены"
echo "  2. Запустите систему: bash knowledge_os/scripts/start_singularity.sh"
echo ""
