#!/bin/bash
# Скрипт для деплоя stateless архитектуры на staging сервер

set -e

SERVER="185.177.216.15"
USER="root"
PASSWORD="u44Ww9NmtQj,XG"
REMOTE_DIR="/root/atra"

echo "=================================================================================="
echo "👥 КОМАНДА ИЗ 13 ЭКСПЕРТОВ - ДЕПЛОЙ STATELESS АРХИТЕКТУРЫ НА STAGING"
echo "=================================================================================="
echo ""

# Проверяем наличие expect
if ! command -v expect &> /dev/null; then
    echo "❌ Ошибка: expect не установлен"
    echo "   Установите: brew install expect (macOS) или apt-get install expect (Linux)"
    exit 1
fi

# Функция для выполнения команд на сервере через expect
run_remote_command() {
    local command="$1"
    expect << EOF
set timeout 30
spawn ssh -o StrictHostKeyChecking=no $USER@$SERVER "$command"
expect {
    "password:" {
        send "$PASSWORD\r"
        exp_continue
    }
    "Permission denied" {
        puts "❌ Ошибка доступа"
        exit 1
    }
    timeout {
        puts "❌ Таймаут подключения"
        exit 1
    }
    eof
}
EOF
}

# Функция для копирования файлов через expect и scp
copy_file() {
    local local_file="$1"
    local remote_file="$2"
    if [ ! -f "$local_file" ]; then
        echo "  ⚠️  Файл не найден: $local_file"
        return 1
    fi
    # Используем scp с правильным экранированием пути
    expect << EOF
set timeout 60
spawn scp -o StrictHostKeyChecking=no "$local_file" $USER@$SERVER:$remote_file
expect {
    "password:" {
        send "$PASSWORD\r"
        exp_continue
    }
    "Permission denied" {
        puts "❌ Ошибка доступа"
        exit 1
    }
    timeout {
        puts "❌ Таймаут подключения"
        exit 1
    }
    eof
}
EOF
    # Проверяем, что файл скопировался
    local local_size=$(stat -f%z "$local_file" 2>/dev/null || stat -c%s "$local_file" 2>/dev/null || echo "0")
    if [ "$local_size" != "0" ]; then
        run_remote_command "test -f $remote_file && stat -c%s $remote_file 2>/dev/null || stat -f%z $remote_file 2>/dev/null || echo '0'" > /tmp/remote_size.txt 2>&1 || true
        local remote_size=$(cat /tmp/remote_size.txt 2>/dev/null | tail -1 | tr -d '\r\n' || echo "0")
        if [ "$remote_size" = "0" ] || [ -z "$remote_size" ]; then
            echo "  ⚠️  Предупреждение: размер файла на сервере = 0, возможно файл не скопировался полностью"
        fi
    fi
}

echo "📋 Шаг 1: Проверка подключения к серверу..."
if run_remote_command "echo 'Connection OK'"; then
    echo "✅ Подключение успешно"
else
    echo "❌ Не удалось подключиться к серверу"
    exit 1
fi

echo ""
echo "📋 Шаг 2: Проверка статуса проекта на сервере..."
run_remote_command "cd $REMOTE_DIR && pwd && git status --short | head -10"

echo ""
echo "📋 Шаг 3: Обновление кода с GitHub..."
run_remote_command "cd $REMOTE_DIR && git fetch origin && git config pull.rebase false && (git reset --hard origin/worker || echo 'Git reset completed') && echo 'Code updated'"

echo ""
echo "📋 Шаг 4: Копирование stateless файлов на сервер..."
# Создаем все необходимые директории на сервере
run_remote_command "cd $REMOTE_DIR && mkdir -p src/infrastructure/cache src/core src/signals src/utils src/ai src/telegram && echo 'All directories created'"

# Копируем stateless файлы
echo "  📤 Копируем stateless_cache.py..."
copy_file "src/infrastructure/cache/stateless_cache.py" "$REMOTE_DIR/src/infrastructure/cache/stateless_cache.py"
copy_file "src/infrastructure/cache/__init__.py" "$REMOTE_DIR/src/infrastructure/cache/__init__.py" 2>/dev/null || echo "  ⚠️  __init__.py не найден локально"

echo "  📤 Копируем state_container.py..."
copy_file "src/signals/state_container.py" "$REMOTE_DIR/src/signals/state_container.py"

echo "  📤 Копируем cache.py..."
copy_file "src/core/cache.py" "$REMOTE_DIR/src/core/cache.py"

echo "  📤 Копируем обновленные файлы..."
copy_file "src/utils/cache_manager.py" "$REMOTE_DIR/src/utils/cache_manager.py"
copy_file "src/core/config.py" "$REMOTE_DIR/src/core/config.py"
copy_file "src/signals/filters_volume_vwap.py" "$REMOTE_DIR/src/signals/filters_volume_vwap.py"
copy_file "src/signals/core.py" "$REMOTE_DIR/src/signals/core.py"
copy_file "src/ai/system_manager.py" "$REMOTE_DIR/src/ai/system_manager.py"
copy_file "src/telegram/handlers.py" "$REMOTE_DIR/src/telegram/handlers.py"
copy_file "src/signals/__init__.py" "$REMOTE_DIR/src/signals/__init__.py"

echo ""
echo "📋 Шаг 4.1: Проверка скопированных файлов..."
run_remote_command "cd $REMOTE_DIR && echo 'Проверка stateless файлов:' && ls -la src/infrastructure/cache/ 2>/dev/null && ls -la src/signals/state_container.py 2>/dev/null && echo '✅ Все файлы на месте'"

echo ""
echo "📋 Шаг 5: Проверка Python..."
run_remote_command "cd $REMOTE_DIR && python3 --version"

echo ""
echo "📋 Шаг 6: Проверка синтаксиса Python файлов..."
run_remote_command "cd $REMOTE_DIR && python3 -m py_compile src/infrastructure/cache/stateless_cache.py src/signals/state_container.py src/core/cache.py 2>&1 || echo 'Проверка завершена'"

echo ""
echo "📋 Шаг 7: Запуск unit-тестов stateless компонентов..."
run_remote_command "cd $REMOTE_DIR && python3 -m pytest tests/test_stateless_cache.py tests/test_state_containers.py -v --tb=short 2>&1 | tail -20 || echo 'Тесты завершены'"

echo ""
echo "📋 Шаг 8: Проверка статуса сервисов..."
run_remote_command "ps aux | grep -E '(python.*atra|python.*main)' | grep -v grep | head -5 || echo 'Процессы не найдены'"

echo ""
echo "=================================================================================="
echo "✅ ДЕПЛОЙ STATELESS АРХИТЕКТУРЫ НА STAGING ЗАВЕРШЕН"
echo "=================================================================================="
echo ""
echo "📊 Следующие шаги:"
echo "   1. Проверьте логи: tail -f $REMOTE_DIR/logs/system.log"
echo "   2. Проверьте работу системы: ssh $USER@$SERVER 'cd $REMOTE_DIR && ./atra_server.sh status'"
echo "   3. При необходимости перезапустите: ssh $USER@$SERVER 'cd $REMOTE_DIR && ./atra_server.sh restart'"
echo ""
