#!/bin/bash
# Запуск автономных систем корпорации (Orchestrator и Nightly Learner)
# Запускать после start_full_corporation.sh

set -e

echo "=============================================="
echo "🤖 ЗАПУСК АВТОНОМНЫХ СИСТЕМ"
echo "=============================================="
echo ""

# 1. Enhanced Orchestrator (каждые 5 минут)
echo "[1/4] Запуск Enhanced Orchestrator..."
cat > /tmp/start_orchestrator.sh << 'ORCH_EOF'
#!/bin/bash
while true; do
    echo "[$(date)] Запуск Enhanced Orchestrator..."
    # Исправляем REDIS_URL для подключения к atra-redis из контейнера
    docker exec -e REDIS_URL=redis://atra-redis:6379 -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os knowledge_os_api python /app/enhanced_orchestrator.py 2>&1 | tee -a /tmp/orchestrator.log | head -50
    echo "[$(date)] Orchestrator завершен, ожидание 5 минут..."
    sleep 300  # 5 минут
done
ORCH_EOF
chmod +x /tmp/start_orchestrator.sh

# Проверяем, не запущен ли уже
if ! pgrep -f "start_orchestrator.sh" > /dev/null; then
    nohup /tmp/start_orchestrator.sh > /tmp/orchestrator_daemon.log 2>&1 &
    echo "  ✅ Orchestrator запущен (PID: $!)"
    echo "  📝 Логи: /tmp/orchestrator.log"
else
    echo "  ℹ️ Orchestrator уже запущен"
fi

# 2. Model Tracker (отслеживание моделей каждый час)
echo "[2/6] Запуск Model Tracker..."
cat > /tmp/start_model_tracker.sh << 'MODELTRACKER_EOF'
#!/bin/bash
while true; do
    echo "[$(date)] Запуск Model Tracker..."
    cd /Users/zhuchyok/Documents/atra-web-ide
    bash scripts/start_model_tracker.sh 2>&1 | tee -a /tmp/model_tracker.log
    echo "[$(date)] Model Tracker завершен, ожидание 3600 секунд (1 час)..."
    sleep 3600  # 1 час
done
MODELTRACKER_EOF
chmod +x /tmp/start_model_tracker.sh
nohup /tmp/start_model_tracker.sh > /dev/null 2>&1 &
MODELTRACKER_PID=$!
echo "  ✅ Model Tracker запущен (PID: $MODELTRACKER_PID)"
echo "  📝 Логи: /tmp/model_tracker.log"

# 3. Self-Check System (самопроверка системы каждую минуту)
echo "[3/6] Запуск Self-Check System..."
cat > /tmp/start_self_check.sh << 'SELFCHECK_EOF'
#!/bin/bash
while true; do
    echo "[$(date)] Запуск Self-Check System..."
    docker exec -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os -e REDIS_URL=redis://atra-redis:6379 knowledge_os_api python /app/self_check_system.py 2>&1 | tee -a /tmp/self_check.log
    echo "[$(date)] Self-Check System завершен, ожидание 60 секунд..."
    sleep 60  # 1 минута
done
SELFCHECK_EOF
chmod +x /tmp/start_self_check.sh
nohup /tmp/start_self_check.sh > /dev/null 2>&1 &
SELFCHECK_PID=$!
echo "  ✅ Self-Check System запущен (PID: $SELFCHECK_PID)"
echo "  📝 Логи: /tmp/self_check.log"

# 4. Debate Processor (обработка дебатов каждые 2 часа)
echo "[4/6] Запуск Debate Processor..."
cat > /tmp/start_debate_processor.sh << 'DEBATE_EOF'
#!/bin/bash
while true; do
    echo "[$(date)] Запуск Debate Processor..."
    docker exec -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os knowledge_os_api python /app/debate_processor.py 2>&1 | tee -a /tmp/debate_processor.log
    echo "[$(date)] Debate Processor завершен, ожидание 2 часа..."
    sleep 7200  # 2 часа
done
DEBATE_EOF
chmod +x /tmp/start_debate_processor.sh
nohup /tmp/start_debate_processor.sh > /dev/null 2>&1 &
DEBATE_PID=$!
echo "  ✅ Debate Processor запущен (PID: $DEBATE_PID)"
echo "  📝 Логи: /tmp/debate_processor.log"

# 4. Nightly Learner (проверка каждый час, обучение в 6:00 MSK)
echo "[4/5] Запуск Nightly Learner..."
cat > /tmp/start_nightly_learner.sh << 'NIGHTLY_EOF'
#!/bin/bash
LAST_RUN_FILE="/tmp/nightly_learner_last_run"
FORCE_RUN="${1:-}"

while true; do
    HOUR=$(date +%H)
    LAST_RUN=$(cat "$LAST_RUN_FILE" 2>/dev/null || echo "0")
    CURRENT_DATE=$(date +%Y-%m-%d)
    
    # Запуск если:
    # 1. Наступило время (6:00 MSK = 3:00 UTC)
    # 2. Или прошло больше 24 часов с последнего запуска
    # 3. Или принудительный запуск
    if [ "$FORCE_RUN" = "force" ] || [ "$HOUR" = "06" ] || [ "$LAST_RUN" != "$CURRENT_DATE" ]; then
        echo "[$(date)] Запуск Nightly Learner..."
        docker exec -e REDIS_URL=redis://atra-redis:6379 -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os knowledge_os_api python /app/nightly_learner.py 2>&1 | tee -a /tmp/nightly_learner.log
        echo "$CURRENT_DATE" > "$LAST_RUN_FILE"
        echo "[$(date)] Nightly Learner завершен"
        FORCE_RUN=""  # Сбрасываем флаг после первого запуска
        sleep 3600  # Ждем час после обучения
    else
        sleep 600  # Проверяем каждые 10 минут
    fi
done
NIGHTLY_EOF
chmod +x /tmp/start_nightly_learner.sh

# Проверяем, не запущен ли уже
if ! pgrep -f "start_nightly_learner.sh" > /dev/null; then
    nohup /tmp/start_nightly_learner.sh > /tmp/nightly_learner_daemon.log 2>&1 &
    echo "  ✅ Nightly Learner запущен (PID: $!)"
    echo "  📝 Логи: /tmp/nightly_learner.log"
    echo "  💡 Для немедленного обучения: /tmp/start_nightly_learner.sh force"
else
    echo "  ℹ️ Nightly Learner уже запущен"
fi

echo ""
echo "=============================================="
echo "✅ АВТОНОМНЫЕ СИСТЕМЫ ЗАПУЩЕНЫ"
echo "=============================================="
echo ""
echo "📊 Статус:"
echo "  - Enhanced Orchestrator: каждые 5 минут"
echo "  - Self-Check System: каждую минуту (САМОПРОВЕРЯЮЩАЯСЯ) ✅"
echo "  - Debate Processor: каждые 2 часа"
echo "  - Nightly Learner: ежедневно в 6:00 MSK"
echo "  - Smart Worker: постоянно обрабатывает задачи"
echo ""
echo "📝 Логи:"
echo "  - Orchestrator: tail -f /tmp/orchestrator.log"
echo "  - Self-Check System: tail -f /tmp/self_check.log"
echo "  - Debate Processor: tail -f /tmp/debate_processor.log"
echo "  - Nightly Learner: tail -f /tmp/nightly_learner.log"
echo "  - Worker: docker logs -f knowledge_os_worker"
echo ""
