#!/bin/bash
# Автоматическая установка Victoria Chat одной командой
# Использование: curl -sSL https://.../victoria_chat_auto_install.sh | bash

set -e

echo "🚀 Victoria Chat - Автоматическая установка"
echo "============================================"
echo ""

# Определяем директорию
INSTALL_DIR="${HOME}/.local/bin"
SCRIPT_NAME="victoria_chat"
SCRIPT_PATH="${INSTALL_DIR}/${SCRIPT_NAME}"

# Создаем директорию
mkdir -p "$INSTALL_DIR"

# URL скрипта (замените на реальный URL)
# Для тестирования используем локальный путь
if [ -f "./scripts/victoria_chat_standalone.py" ]; then
    echo "📋 Копирование локального скрипта..."
    cp "./scripts/victoria_chat_standalone.py" "$SCRIPT_PATH"
else
    # Если есть curl или wget, загружаем
    if command -v curl &> /dev/null; then
        echo "📥 Загрузка скрипта через curl..."
        curl -o "$SCRIPT_PATH" "https://raw.githubusercontent.com/your-repo/atra-web-ide/main/scripts/victoria_chat_standalone.py" || {
            echo "❌ Не удалось загрузить скрипт"
            exit 1
        }
    elif command -v wget &> /dev/null; then
        echo "📥 Загрузка скрипта через wget..."
        wget -O "$SCRIPT_PATH" "https://raw.githubusercontent.com/your-repo/atra-web-ide/main/scripts/victoria_chat_standalone.py" || {
            echo "❌ Не удалось загрузить скрипт"
            exit 1
        }
    else
        echo "❌ Не найден curl или wget для загрузки скрипта"
        echo "💡 Скопируйте scripts/victoria_chat_standalone.py вручную"
        exit 1
    fi
fi

# Делаем исполняемым
chmod +x "$SCRIPT_PATH"

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден!"
    echo "💡 Установите Python 3.7+"
    exit 1
fi

# Устанавливаем requests (скрипт сделает это сам при первом запуске)
echo "✅ Скрипт установлен: $SCRIPT_PATH"
echo ""
echo "🚀 Запуск:"
echo "   $SCRIPT_PATH"
echo ""
echo "🌐 С удаленной Victoria:"
echo "   VICTORIA_REMOTE_URL=http://185.177.216.15:8010 $SCRIPT_PATH"
echo ""
echo "💡 Скрипт автоматически установит зависимости при первом запуске!"
