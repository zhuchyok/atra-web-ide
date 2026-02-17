#!/bin/bash
# [SINGULARITY 14.3] External System Watchdog
# Monitors Victoria Agent and Orchestrator health.
# Performs auto-recovery if the system is unresponsive.

VICTORIA_URL="http://localhost:8010/health"
ORCHESTRATOR_URL="http://localhost:8080/health"
CHECK_INTERVAL=30
MAX_FAILURES=3
LOG_FILE="/tmp/singularity_watchdog.log"

echo "$(date) - Watchdog started" >> $LOG_FILE

failure_count=0

while true; do
    # Check Victoria
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 $VICTORIA_URL)
    
    if [ "$response" != "200" ]; then
        ((failure_count++))
        echo "$(date) - Victoria health check failed (Code: $response). Failure $failure_count/$MAX_FAILURES" >> $LOG_FILE
    else
        if [ $failure_count -gt 0 ]; then
            echo "$(date) - Victoria recovered" >> $LOG_FILE
        fi
        failure_count=0
    fi

    if [ $failure_count -ge $MAX_FAILURES ]; then
        echo "$(date) - CRITICAL: System unresponsive. Triggering emergency restart..." >> $LOG_FILE
        
        # Try to notify via Telegram if possible (using host-level bot)
        # Note: This assumes TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID are available in the environment
        if [ ! -z "$TELEGRAM_BOT_TOKEN" ] && [ ! -z "$TELEGRAM_USER_ID" ]; then
            curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
                -d "chat_id=$TELEGRAM_USER_ID&text=🚨 [WATCHDOG] Singularity 14.3: System unresponsive. Performing emergency restart." > /dev/null
        fi

        # Emergency Restart
        docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
        docker-compose restart backend
        
        echo "$(date) - Emergency restart completed" >> $LOG_FILE
        failure_count=0
        sleep 60 # Give it time to recover
    fi

    sleep $CHECK_INTERVAL
done
