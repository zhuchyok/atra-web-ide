#!/bin/bash
# Скачивание дампа базы знаний с сервера 46

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "📥 Скачивание дампа базы знаний с сервера 46"
echo "   Время: $(date)"
echo ""

# Настройки
SERVER_46_HOST="${SERVER_46_HOST:-46.149.66.170}"
SERVER_46_USER="${SERVER_46_USER:-root}"
SERVER_46_SSH_PORT="${SERVER_46_SSH_PORT:-22}"
SERVER_46_PASS="${SERVER_46_PASS:-tT@B43Td21w?NB}"

# Проверяем наличие sshpass
if ! command -v sshpass &> /dev/null; then
    echo "⚠️  sshpass не установлен. Устанавливаю через brew..."
    if command -v brew &> /dev/null; then
        brew install hudochenkov/sshpass/sshpass 2>/dev/null || {
            echo "❌ Не удалось установить sshpass"
            echo "   Установите вручную: brew install hudochenkov/sshpass/sshpass"
            exit 1
        }
    else
        echo "❌ brew не найден. Установите sshpass вручную"
        exit 1
    fi
fi

# Проверяем SSH доступ
echo "🔍 Проверка доступа к серверу 46..."
if ! sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "echo 'OK'" 2>/dev/null; then
    echo "❌ Не удалось подключиться к серверу 46"
    echo ""
    echo "Проверьте:"
    echo "  1. Доступность сервера: ping $SERVER_46_HOST"
    echo "  2. Переменные окружения: SERVER_46_HOST, SERVER_46_USER, SERVER_46_PASS"
    exit 1
fi

echo "✅ Подключение к серверу 46 установлено"
echo ""

# Создаем директорию для дампа
DUMP_DIR="$HOME/migration/server2"
mkdir -p "$DUMP_DIR"

# Создаем дамп на сервере
echo "💾 Создание дампа на сервере 46..."

# Ищем правильный путь и контейнер
DUMP_PATH=$(sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "
    # Пробуем разные пути
    for path in /root/atra /root/knowledge_os /opt/atra /home/root/atra; do
        if [ -d \"\$path\" ]; then
            echo \"\$path\"
            break
        fi
    done
    # Если не нашли, используем домашнюю директорию
    echo ~
" | head -1)

echo "   Найден путь: $DUMP_PATH"

# Ищем контейнер PostgreSQL
echo "   Поиск контейнера PostgreSQL..."
PG_CONTAINER=$(sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "
    docker ps --format '{{.Names}}' | grep -iE 'postgres|pg|db|knowledge' | head -1
" | head -1)

if [ -z "$PG_CONTAINER" ]; then
    echo "⚠️  Контейнер не найден, пробуем все варианты..."
    # Пробуем подключиться напрямую к PostgreSQL (если не в Docker)
    PG_AVAILABLE=$(sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "
        which psql > /dev/null 2>&1 && echo 'yes' || echo 'no'
    ")
    if [ "$PG_AVAILABLE" = "yes" ]; then
        echo "   ✅ PostgreSQL доступен напрямую (не в Docker)"
        PG_CONTAINER=""
    else
        echo "❌ PostgreSQL не найден"
        exit 1
    fi
else
    echo "   ✅ Найден контейнер: $PG_CONTAINER"
fi

# Создаем дамп (или пересоздаём, если пустой < 1MB)
sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "
    cd $DUMP_PATH 2>/dev/null || cd ~
    DUMP_FILE=\"knowledge_os_dump.sql\"
    NEED_DUMP=1
    if [ -f \"\$DUMP_FILE\" ]; then
        SZ=\$(stat -c%s \"\$DUMP_FILE\" 2>/dev/null || stat -f%z \"\$DUMP_FILE\" 2>/dev/null || echo 0)
        if [ \"\$SZ\" -gt 1000000 ]; then
            echo '✅ Дамп уже существует на сервере (OK)'
            ls -lh \"\$DUMP_FILE\"
            NEED_DUMP=0
        else
            echo '⚠️  Дамп пустой (\$SZ B), пересоздаём...'
            rm -f \"\$DUMP_FILE\"
        fi
    fi
    if [ \"\$NEED_DUMP\" = 1 ]; then
        echo '📦 Создание дампа...'
        if [ -n \"$PG_CONTAINER\" ]; then
            docker exec $PG_CONTAINER pg_dump -U admin -d knowledge_os > \"\$DUMP_FILE\" 2>&1
        else
            pg_dump -U admin -d knowledge_os -h localhost > \"\$DUMP_FILE\" 2>&1
        fi
        if [ \$? -eq 0 ]; then
            echo '✅ Дамп создан'
            ls -lh \"\$DUMP_FILE\"
        else
            echo '❌ Ошибка создания дампа'
            if [ -n \"$PG_CONTAINER\" ]; then
                docker exec $PG_CONTAINER pg_dump -U admin -d knowledge_os 2>&1 | head -5
            else
                pg_dump -U admin -d knowledge_os -h localhost 2>&1 | head -5
            fi
            exit 1
        fi
    fi
    echo \"DUMP_PATH=\$PWD/\$DUMP_FILE\"
" || {
    echo "❌ Ошибка создания дампа на сервере"
    exit 1
}

# Получаем путь к дампу
REMOTE_DUMP_PATH=$(sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "
    cd $DUMP_PATH 2>/dev/null || cd ~
    if [ -f knowledge_os_dump.sql ]; then
        echo \"\$PWD/knowledge_os_dump.sql\"
    fi
" | head -1)

# Скачиваем дамп
echo ""
echo "📥 Скачивание дампа..."
DUMP_FILE="$DUMP_DIR/knowledge_os_dump.sql"

if [ -z "$REMOTE_DUMP_PATH" ]; then
    # Пробуем стандартные пути
    for remote_path in "$DUMP_PATH/knowledge_os_dump.sql" "/root/atra/knowledge_os_dump.sql" "~/knowledge_os_dump.sql"; do
        if sshpass -p "$SERVER_46_PASS" ssh -o StrictHostKeyChecking=no -p "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST" "test -f $remote_path" 2>/dev/null; then
            REMOTE_DUMP_PATH="$remote_path"
            break
        fi
    done
fi

if [ -z "$REMOTE_DUMP_PATH" ]; then
    echo "❌ Не удалось найти дамп на сервере"
    exit 1
fi

echo "   Удаленный путь: $REMOTE_DUMP_PATH"
sshpass -p "$SERVER_46_PASS" scp -o StrictHostKeyChecking=no -P "$SERVER_46_SSH_PORT" "$SERVER_46_USER@$SERVER_46_HOST:$REMOTE_DUMP_PATH" "$DUMP_FILE"

if [ -f "$DUMP_FILE" ]; then
    echo "✅ Дамп скачан: $DUMP_FILE"
    echo "   Размер: $(du -h "$DUMP_FILE" | cut -f1)"
    echo ""
    echo "🚀 Теперь можно импортировать:"
    echo "   ./scripts/migrate_from_dump.sh"
else
    echo "❌ Ошибка скачивания дампа"
    exit 1
fi
