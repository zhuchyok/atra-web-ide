#!/bin/bash
# Альтернативный метод запуска через SSH команду
# Использование: ./scripts/remote_start.sh

SERVER="root@185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"

echo "🚀 Автоматический запуск системы на продакшн..."

# Создаем временный скрипт для выполнения на сервере
cat > /tmp/start_atra.sh << 'REMOTE_SCRIPT'
#!/bin/bash
cd /root/atra || exit 1

echo "1. Проверка текущего процесса..."
PID=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "   Остановка процесса PID: $PID"
    kill -SIGTERM "$PID" 2>/dev/null || true
    sleep 5
    if ps -p "$PID" > /dev/null 2>&1; then
        kill -9 "$PID" 2>/dev/null || true
    fi
    echo "   ✅ Процесс остановлен"
else
    echo "   ℹ️  Процесс не найден"
fi

echo "2. Обновление конфигурации..."
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env 2>/dev/null || true
echo "   ✅ Конфигурация обновлена"

echo "3. Создание директории для логов..."
mkdir -p logs
echo "   ✅ Директория logs готова"

echo "4. Запуск системы..."
nohup python3 main.py > logs/atra.log 2>&1 &
NEW_PID=$!

# Ожидание создания лог-файла
echo "   Ожидание запуска системы..."
for i in {1..10}; do
    if ps -p $NEW_PID > /dev/null 2>&1; then
        if [ -f logs/atra.log ] && [ -s logs/atra.log ]; then
            break
        fi
    fi
    sleep 1
done

if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "   ✅ Система запущена (PID: $NEW_PID)"
else
    echo "   ❌ Ошибка запуска!"
    if [ -f logs/atra.log ]; then
        tail -50 logs/atra.log
    else
        echo "   Лог-файл не создан"
    fi
    exit 1
fi

echo "5. Проверка логов..."
if [ -f logs/atra.log ] && [ -s logs/atra.log ]; then
    echo "   === Последние 30 строк лога ==="
    tail -30 logs/atra.log
else
    echo "   ⚠️  Лог-файл еще создается, подождите несколько секунд"
    sleep 3
    if [ -f logs/atra.log ]; then
        tail -30 logs/atra.log
    fi
fi

echo ""
echo "✅ ЗАПУСК ЗАВЕРШЕН!"
echo "Для мониторинга: tail -f /root/atra/logs/atra.log"
REMOTE_SCRIPT

# Копируем скрипт на сервер и выполняем
echo "📤 Копирование скрипта на сервер..."
sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no /tmp/start_atra.sh "$SERVER:/tmp/start_atra.sh" 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Скрипт скопирован"
    echo "🚀 Выполнение на сервере..."
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" "chmod +x /tmp/start_atra.sh && bash /tmp/start_atra.sh" 2>&1
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo ""
        echo "✅✅✅ СИСТЕМА УСПЕШНО ЗАПУЩЕНА НА ПРОДАКШН! ✅✅✅"
        echo ""
        echo "Проверка статуса:"
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" "ps aux | grep 'python.*main.py' | grep -v grep" 2>&1
    else
        echo "❌ Ошибка при запуске (код: $EXIT_CODE)"
        exit 1
    fi
else
    echo "❌ Ошибка копирования скрипта"
    echo "Попробуйте установить sshpass: brew install sshpass (macOS) или apt-get install sshpass (Linux)"
    exit 1
fi

# Удаляем временный файл
rm -f /tmp/start_atra.sh

