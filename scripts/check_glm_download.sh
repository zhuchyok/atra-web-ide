#!/bin/bash
# Скрипт для проверки статуса загрузки glm-4.7-flash

echo "🔍 Проверка статуса glm-4.7-flash..."
echo ""

# Проверяем, установлена ли модель
if ollama list | grep -q "glm-4.7-flash"; then
    echo "✅ Модель установлена!"
    ollama list | grep "glm-4.7-flash"
    echo ""
    echo "🎉 Модель готова к использованию!"
else
    echo "⏳ Модель еще не установлена"
    echo ""

    # Проверяем, идет ли загрузка
    if ps aux | grep -q "[o]llama pull glm-4.7-flash"; then
        echo "📥 Загрузка в процессе..."
        echo ""
        echo "Для просмотра прогресса запустите:"
        echo "  ollama pull glm-4.7-flash"
        echo ""
        echo "Или проверьте процессы:"
        echo "  ps aux | grep 'ollama pull'"
    else
        echo "⚠️  Загрузка не запущена"
        echo ""
        echo "Для запуска загрузки:"
        echo "  ollama pull glm-4.7-flash"
    fi
fi
