#!/bin/bash
# Скрипт для мониторинга загрузки glm-4.7-flash

echo "🔍 Мониторинг загрузки glm-4.7-flash..."
echo "Нажмите Ctrl+C для остановки"
echo ""

while true; do
    clear
    echo "════════════════════════════════════════"
    echo "📥 Статус загрузки glm-4.7-flash"
    echo "════════════════════════════════════════"
    echo ""

    # Проверяем, установлена ли модель
    if ollama list | grep -q "glm-4.7-flash"; then
        echo "✅ МОДЕЛЬ УСТАНОВЛЕНА!"
        echo ""
        ollama list | grep "glm-4.7-flash"
        echo ""
        echo "🎉 Модель готова к использованию!"
        echo ""
        echo "Конфигурация уже настроена в:"
        echo "  - knowledge_os/app/local_router.py"
        echo "  - MODEL_MAP['coding'] = 'glm-4.7-flash'"
        echo "  - MODEL_MAP['reasoning'] = 'glm-4.7-flash'"
        exit 0
    fi

    # Проверяем процесс загрузки
    if ps aux | grep -q "[o]llama pull glm-4.7-flash"; then
        echo "⏳ Загрузка в процессе..."
        echo ""
        echo "Активные процессы:"
        ps aux | grep "[o]llama pull glm-4.7-flash" | grep -v grep | awk '{print "  PID:", $2, "| CPU:", $3"% | MEM:", $4"%"}'
        echo ""
        echo "💡 Для просмотра детального прогресса запустите в отдельном терминале:"
        echo "   ollama pull glm-4.7-flash"
    else
        echo "⚠️  Процесс загрузки не найден"
        echo ""
        echo "Возможные причины:"
        echo "  - Загрузка завершилась (проверьте: ollama list)"
        echo "  - Загрузка была прервана"
        echo ""
        echo "Для запуска загрузки:"
        echo "  ollama pull glm-4.7-flash"
    fi

    echo ""
    echo "════════════════════════════════════════"
    echo "Обновление через 10 секунд..."
    echo "Время: $(date '+%H:%M:%S')"
    sleep 10
done
