#!/bin/bash
# ATRA Web IDE - Full Recovery Readiness Verification Script
# [SINGULARITY 20.0] Wisdom Era Architecture

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
FAIL=0

echo -e "${YELLOW}🔍 Запуск проверки готовности системы к перезагрузке (Mac Studio)...${NC}\n"

# 1. Проверка Docker Restart Policies
echo -e "--- 1. Docker Restart Policies ---"
CORE_CONTAINERS=("victoria-agent" "knowledge_postgres" "knowledge_os_orchestrator" "knowledge_os_redis")
for container in "${CORE_CONTAINERS[@]}"; do
    POLICY=$(docker inspect "$container" --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "")
    if [ "$POLICY" == "always" ] || [ "$POLICY" == "unless-stopped" ]; then
        echo -e "✅ $container: $POLICY"
    else
        echo -e "${RED}❌ $container: ${POLICY:-missing} (Рекомендуется always)${NC}"
        FAIL=1
    fi
done

# 2. Проверка MLX Autostart (macOS LaunchAgent) — optional spare brain
echo -e "\n--- 2. MLX Autostart (LaunchAgent) ---"
if [ -f ~/Library/LaunchAgents/com.atra.mlx-api-server.plist ]; then
    echo -e "✅ MLX LaunchAgent найден: com.atra.mlx-api-server.plist"
else
    echo -e "${YELLOW}⚠️ MLX LaunchAgent не найден (live brain = Ollama 11434)${NC}"
fi

# 3. Проверка Ollama Pinning (KEEP_ALIVE=-1)
echo -e "\n--- 3. Ollama Configuration (.env) ---"
if [ -f .env ] && grep -q "OLLAMA_KEEP_ALIVE=-1" .env; then
    echo -e "✅ OLLAMA_KEEP_ALIVE=-1 (Модель закреплена)"
else
    echo -e "${RED}❌ OLLAMA_KEEP_ALIVE не равен -1 в .env${NC}"
    FAIL=1
fi

# 4. Проверка Telegram Bot Autostart — optional
echo -e "\n--- 4. Telegram Bot Autostart ---"
if [ -f ~/Library/LaunchAgents/com.atra.victoria-telegram-bot.plist ]; then
    echo -e "✅ Telegram Bot LaunchAgent найден: com.atra.victoria-telegram-bot.plist"
else
    echo -e "${YELLOW}⚠️ Telegram Bot LaunchAgent не найден${NC}"
fi

# 5. Проверка System Auto Recovery Script
echo -e "\n--- 5. System Auto Recovery ---"
if [ -f "scripts/system_auto_recovery.sh" ]; then
    echo -e "✅ Скрипт самовосстановления найден"
    if [ -x "scripts/system_auto_recovery.sh" ]; then
        echo -e "✅ Скрипт исполняемый"
    else
        echo -e "${YELLOW}⚠️ Скрипт не исполняемый. Выполните: chmod +x scripts/system_auto_recovery.sh${NC}"
        FAIL=1
    fi
else
    echo -e "${RED}❌ Скрипт scripts/system_auto_recovery.sh отсутствует!${NC}"
    FAIL=1
fi

# 5.5. Recovery Listener
echo -e "\n--- 5.5. Recovery Listener (порт 9099) ---"
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:9099/recover 2>/dev/null | grep -qE '200|405'; then
    echo -e "✅ Recovery Listener отвечает на 9099"
elif lsof -i :9099 >/dev/null 2>&1; then
    echo -e "✅ Порт 9099 занят (слушатель запущен)"
else
    echo -e "${YELLOW}⚠️ Recovery Listener не запущен${NC}"
fi

# 6. Проверка БД (PostgreSQL Health)
echo -e "\n--- 6. Database Health ---"
if docker exec knowledge_postgres pg_isready -U admin -d knowledge_os > /dev/null 2>&1; then
    echo -e "✅ PostgreSQL доступна и здорова"
else
    echo -e "${RED}❌ PostgreSQL не отвечает!${NC}"
    FAIL=1
fi

# 7. Live brain
echo -e "\n--- 7. Ollama brain (11434) ---"
if curl -sf --connect-timeout 3 http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "✅ Ollama brain доступен"
else
    echo -e "${RED}❌ Ollama brain 11434 недоступен${NC}"
    FAIL=1
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}✨ Проверка завершена. Mac Studio готов к восстановлению после перезагрузки.${NC}"
else
    echo -e "${RED}⚠️ Проверка завершена С ОШИБКАМИ${NC}"
fi
exit "$FAIL"
