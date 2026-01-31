#!/bin/bash
# Скрипт для запуска Task Worker
# Проверяет, не запущен ли уже worker, и запускает его если нужно

cd /root/knowledge_os || exit 1

# Проверяем, не запущен ли уже worker
if pgrep -f "smart_worker_autonomous.py" > /dev/null; then
    echo "[$(date)] Worker уже запущен, пропускаем..."
    exit 0
fi

# Запускаем worker
echo "[$(date)] Запуск Task Worker..."
cd app
nohup python3 smart_worker_autonomous.py > /tmp/task_worker.log 2>&1 &

# Ждем немного и проверяем, что процесс запустился
sleep 2
if pgrep -f "smart_worker_autonomous.py" > /dev/null; then
    echo "[$(date)] ✅ Worker успешно запущен (PID: $(pgrep -f 'smart_worker_autonomous.py'))"
else
    echo "[$(date)] ❌ Ошибка запуска worker, проверьте логи: /tmp/task_worker.log"
    exit 1
fi

