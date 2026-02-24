#!/bin/bash

# Скрипт для загрузки улучшений ИИ системы на сервер
# Реализует Вариант 3: Умное автоматическое управление паттернами

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🤖 Загрузка улучшений ИИ системы на сервер"
echo "==========================================="
echo ""
echo "📊 Что включено:"
echo "  ✅ Автоматическое управление паттернами (макс 30K)"
echo "  ✅ Умная очистка с сохранением важных данных"
echo "  ✅ Система весов для приоритизации"
echo "  ✅ Обновленный лимит мониторинга"
echo ""

# Функция для загрузки файла
upload_file() {
    local file="$1"
    echo "📤 Загрузка $file..."

    expect << EOF
spawn scp -o StrictHostKeyChecking=no $file $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

    if [ $? -eq 0 ]; then
        echo "✅ $file загружен успешно"
    else
        echo "❌ Ошибка загрузки $file"
        return 1
    fi
}

# Загружаем файлы
upload_file "ai_config.py" || exit 1
upload_file "ai_learning_system.py" || exit 1
upload_file "ai_monitor.py" || exit 1

echo ""
echo "✅ Все улучшения ИИ загружены на сервер!"
echo ""
echo "🔄 Перезапустите бота для применения:"
echo "./restart_bot_on_server.sh"
echo ""
echo "📊 Ожидаемый результат:"
echo "  • 33156 паттернов → автоочистка → ~23000 паттернов"
echo "  • Быстрый старт системы (в 2-3 раза быстрее)"
echo "  • Стабильная производительность"
echo "  • Сохранены все важные данные (WIN/LOSS)"
