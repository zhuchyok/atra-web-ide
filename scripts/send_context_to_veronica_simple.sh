#!/bin/bash
# Простая отправка контекста в Veronica
# Запускать: bash scripts/send_context_to_veronica_simple.sh

VERONICA_URL="${VERONICA_URL:-http://192.168.1.64:8011}"

echo "=============================================="
echo "📚 ОТПРАВКА КОНТЕКСТА В VERONICA"
echo "=============================================="
echo ""

# Проверка доступности
echo "🔍 Проверка Veronica..."
if ! curl -s -f "${VERONICA_URL}/health" >/dev/null 2>&1; then
    echo "   ❌ Veronica недоступна на ${VERONICA_URL}"
    exit 1
fi
echo "   ✅ Veronica доступна"
echo ""

# Формируем задачу
TASK='Изучи весь контекст миграции Docker контейнеров с MacBook на Mac Studio. 

КЛЮЧЕВЫЕ МОМЕНТЫ:
- Mac Studio IP: 192.168.1.64, пользователь: bikos
- Все Docker контейнеры перенесены
- Knowledge OS работает (Victoria, Veronica, API, Database)
- Корневые контейнеры импортированы (Frontend, Backend)
- Docker Desktop установлен на Mac Studio

ЗАДАЧА:
1. Изучи все документы миграции в проекте:
   - FINAL_MIGRATION_REPORT.md
   - MIGRATION_STATUS.md
   - COMPLETE_MIGRATION_REPORT.md
   - FINAL_DOCKER_CHECK.md
   - MIGRATION_FINAL_STATUS.md
   - И другие документы в корне проекта

2. Изучи созданные скрипты:
   - scripts/full_migration_macbook_to_macstudio.sh
   - scripts/migrate_docker_to_mac_studio.sh
   - scripts/import_docker_from_macbook.sh
   - scripts/check_and_start_containers.sh
   - START_ON_MAC_STUDIO.sh

3. Пойми структуру проекта:
   - knowledge_os/docker-compose.yml - основные сервисы
   - docker-compose.yml - корневые контейнеры
   - scripts/ - скрипты управления
   - docs/mac-studio/ - документация

4. Запомни процессы миграции и будь готова отвечать на вопросы.

Используй Extended Thinking для глубокого анализа контекста.'

echo "📤 Отправка контекста..."
echo "   (это может занять некоторое время...)"
echo ""

# Отправляем через API
RESPONSE=$(curl -s -X POST "${VERONICA_URL}/run" \
    -H "Content-Type: application/json" \
    -d "{\"goal\": $(echo "$TASK" | jq -Rs .), \"max_steps\": 25}" \
    --max-time 300 2>&1)

if [ $? -eq 0 ]; then
    echo "✅ Контекст отправлен!"
    echo ""
    echo "📋 Ответ Veronica:"
    echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
else
    echo "❌ Ошибка отправки"
    echo "$RESPONSE"
fi

echo ""
echo "=============================================="
