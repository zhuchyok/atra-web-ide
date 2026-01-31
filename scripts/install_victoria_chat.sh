#!/bin/bash
# Автоматическая установка Victoria Chat на любое устройство

set -e

echo "🚀 Установка Victoria Chat..."
echo ""

# Определяем директорию для установки
INSTALL_DIR="${HOME}/.local/bin"
SCRIPT_NAME="victoria_chat"

# Создаем директорию если нет
mkdir -p "$INSTALL_DIR"

# URL скрипта (можно изменить на GitHub или другой источник)
SCRIPT_URL="https://raw.githubusercontent.com/your-repo/atra-web-ide/main/scripts/victoria_chat_standalone.py"

# Если скрипт уже есть локально, используем его
if [ -f "./scripts/victoria_chat_standalone.py" ]; then
    echo "📋 Используется локальный скрипт..."
    cp "./scripts/victoria_chat_standalone.py" "${INSTALL_DIR}/${SCRIPT_NAME}"
else
    echo "📥 Загрузка скрипта..."
    curl -o "${INSTALL_DIR}/${SCRIPT_NAME}" "$SCRIPT_URL" || {
        echo "❌ Не удалось загрузить скрипт"
        echo "💡 Скопируйте scripts/victoria_chat_standalone.py вручную"
        exit 1
    }
fi

# Делаем исполняемым
chmod +x "${INSTALL_DIR}/${SCRIPT_NAME}"

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден!"
    echo "💡 Установите Python 3.7+"
    exit 1
fi

# Устанавливаем requests если нужно
echo "📦 Проверка зависимостей..."
python3 -c "import requests" 2>/dev/null || {
    echo "🔧 Установка requests..."
    python3 -m pip install --user requests || {
        echo "⚠️  Не удалось установить requests автоматически"
        echo "💡 Установите вручную: pip3 install requests"
    }
}

# Добавляем в PATH если нужно
if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
    echo ""
    echo "📝 Добавьте в ~/.bashrc или ~/.zshrc:"
    echo "   export PATH=\"\${HOME}/.local/bin:\$PATH\""
    echo ""
    echo "Или запускайте напрямую:"
    echo "   ${INSTALL_DIR}/${SCRIPT_NAME}"
fi

echo ""
echo "✅ Victoria Chat установлен!"
echo ""
echo "🚀 Использование:"
echo "   ${INSTALL_DIR}/${SCRIPT_NAME}"
echo "   или: victoria_chat (если добавлен в PATH)"
echo ""
echo "🌐 С удаленной Victoria:"
echo "   VICTORIA_REMOTE_URL=http://185.177.216.15:8010 ${INSTALL_DIR}/${SCRIPT_NAME}"
