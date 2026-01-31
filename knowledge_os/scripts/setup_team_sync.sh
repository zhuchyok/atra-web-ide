#!/bin/bash
# Скрипт настройки синхронизации данных команды

set -e

echo "🔄 Настройка синхронизации данных команды..."

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python3."
    exit 1
fi

# Проверка наличия Git
if ! command -v git &> /dev/null; then
    echo "❌ Git не найден. Установите Git."
    exit 1
fi

# Запрос URL репозитория
read -p "Введите URL репозитория данных команды (или нажмите Enter для пропуска): " REPO_URL

if [ -z "$REPO_URL" ]; then
    echo "⚠️ URL репозитория не указан. Используйте переменную окружения TEAM_DATA_REPO."
else
    export TEAM_DATA_REPO="$REPO_URL"
    echo "✅ TEAM_DATA_REPO установлен: $TEAM_DATA_REPO"
fi

# Запрос локальной директории
read -p "Введите локальную директорию для данных (по умолчанию .team_data): " LOCAL_DIR
LOCAL_DIR=${LOCAL_DIR:-".team_data"}
export TEAM_DATA_DIR="$LOCAL_DIR"
echo "✅ TEAM_DATA_DIR установлен: $TEAM_DATA_DIR"

# Создание .env файла (опционально)
read -p "Создать .env файл для сохранения настроек? (y/n): " CREATE_ENV
if [ "$CREATE_ENV" = "y" ] || [ "$CREATE_ENV" = "Y" ]; then
    ENV_FILE=".env.team_sync"
    echo "# Настройки синхронизации данных команды" > "$ENV_FILE"
    echo "export TEAM_DATA_REPO=\"$REPO_URL\"" >> "$ENV_FILE"
    echo "export TEAM_DATA_DIR=\"$LOCAL_DIR\"" >> "$ENV_FILE"
    echo "✅ Создан файл $ENV_FILE"
    echo "📝 Для использования выполните: source $ENV_FILE"
fi

# Первая синхронизация
read -p "Выполнить первую синхронизацию? (y/n): " DO_SYNC
if [ "$DO_SYNC" = "y" ] || [ "$DO_SYNC" = "Y" ]; then
    echo "🔄 Выполнение первой синхронизации..."
    python3 scripts/sync_team_data.py sync
fi

# Проверка статуса
echo "📊 Проверка статуса..."
python3 scripts/sync_team_data.py status

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "  1. Если создан .env файл: source $ENV_FILE"
echo "  2. Для синхронизации: python3 scripts/sync_team_data.py sync"
echo "  3. Для отправки изменений: python3 scripts/sync_team_data.py push"
echo "  4. Для получения изменений: python3 scripts/sync_team_data.py pull"

