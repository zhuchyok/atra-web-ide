#!/bin/bash
# ATRA Web IDE - Full Recovery Readiness Verification Script
# [SINGULARITY 20.0] Wisdom Era Architecture

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Запуск проверки готовности системы к перезагрузке (Mac Studio)...${NC}\n"

# 1. Проверка Docker Restart Policies
echo -e "--- 1. Docker Restart Policies ---"
CORE_CONTAINERS=("victoria-agent" "knowledge_postgres" "knowledge_os_orchestrator" "knowledge_os_redis")
for container in "${CORE_CONTAINERS[@]}"; do
    POLICY=$(docker inspect "$container" --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null)
    if [ "$POLICY" == "always" ] || [ "$POLICY" == "unless-stopped" ]; then
        echo -e "✅ $container: $POLICY"
    else
        echo -e "${RED}❌ $container: $POLICY (Рекомендуется always)${NC}"
    fi
done

# 2. Проверка MLX Autostart (macOS LaunchAgent)
echo -e "\n--- 2. MLX Autostart (LaunchAgent) ---"
if [ -f ~/Library/LaunchAgents/com.atra.mlx-api-server.plist ]; then
    echo -e "✅ MLX LaunchAgent найден: com.atra.mlx-api-server.plist"
else
    echo -e "${YELLOW}⚠️ MLX LaunchAgent не найден. Запустите scripts/setup_mlx_autostart.sh${NC}"
fi

# 3. Проверка Ollama Pinning (KEEP_ALIVE=-1)
echo -e "\n--- 3. Ollama Configuration (.env) ---"
if grep -q "OLLAMA_KEEP_ALIVE=-1" .env; then
    echo -e "✅ OLLAMA_KEEP_ALIVE=-1 (Модель закреплена)"
else
    echo -e "${RED}❌ OLLAMA_KEEP_ALIVE не равен -1 в .env${NC}"
fi

# 4. Проверка Telegram Bot Autostart
echo -e "\n--- 4. Telegram Bot Autostart ---"
if [ -f ~/Library/LaunchAgents/com.atra.victoria-telegram-bot.plist ]; then
    echo -e "✅ Telegram Bot LaunchAgent найден: com.atra.victoria-telegram-bot.plist"
else
    echo -e "${YELLOW}⚠️ Telegram Bot LaunchAgent не найден. Запустите scripts/setup_victoria_telegram_bot_autostart.sh${NC}"
fi

# 5. Проверка System Auto Recovery Script
echo -e "\n--- 5. System Auto Recovery ---"
if [ -f "scripts/system_auto_recovery.sh" ]; then
    echo -e "✅ Скрипт самовосстановления найден"
    if [ -x "scripts/system_auto_recovery.sh" ]; then
        echo -e "✅ Скрипт исполняемый"
    else
        echo -e "${YELLOW}⚠️ Скрипт не исполняемый. Выполните: chmod +x scripts/system_auto_recovery.sh${NC}"
    fi
else
    echo -e "${RED}❌ Скрипт scripts/system_auto_recovery.sh отсутствует!${NC}"
fi

# 5.5. Recovery Listener (дефибриллятор MLX/Ollama)
echo -e "\n--- 5.5. Recovery Listener (порт 9099) ---"
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:9099/recover 2>/dev/null | grep -qE '200|405'; then
    echo -e "✅ Recovery Listener отвечает на 9099"
elif lsof -i :9099 >/dev/null 2>&1; then
    echo -e "✅ Порт 9099 занят (слушатель запущен)"
else
    echo -e "${YELLOW}⚠️ Recovery Listener не запущен. После перезагрузки: nohup python3 scripts/host_recovery_listener.py &${NC}"
fi

# 6. Проверка БД (PostgreSQL Health)
echo -e "\n--- 6. Database Health ---"
if docker exec knowledge_postgres pg_isready -U admin -d knowledge_os > /dev/null 2>&1; then
    echo -e "✅ PostgreSQL доступна и здорова"
else
    echo -e "${RED}❌ PostgreSQL не отвечает!${NC}"
fi

echo -e "\n${GREEN}✨ Проверка завершена. Если все пункты '✅', ваш Mac Studio готов к полноценному восстановлению после перезагрузки.${NC}"
