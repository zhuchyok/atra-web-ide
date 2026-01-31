#!/bin/bash
# Быстрый старт Singularity 8.0

echo "🚀 Singularity 8.0: Быстрый старт"
echo "=================================="
echo ""

# 1. Проверка зависимостей
echo "📦 Шаг 1: Проверка зависимостей..."
python3 knowledge_os/scripts/check_system_ready.py
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️ Установка недостающих зависимостей..."
    python3 knowledge_os/scripts/install_dependencies.py
fi

echo ""
echo "✅ Готово! Теперь можно запустить систему:"
echo ""
echo "  # Telegram бот:"
echo "  python3 knowledge_os/app/telegram_simple.py"
echo ""
echo "  # Автономные компоненты:"
echo "  python3 knowledge_os/app/singularity_autonomous.py"
echo ""

