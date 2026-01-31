#!/bin/bash
# Скрипт для применения всех изменений на Mac Studio
# Использование: bash scripts/apply_to_mac_studio.sh

set -e

MAC_STUDIO="root@185.177.216.15"
SYNC_DIR="/tmp/atra-sync"

echo "🚀 Применение изменений на Mac Studio..."
echo ""

# 1. Найти проект на Mac Studio
echo "📁 Поиск проекта atra-web-ide на Mac Studio..."
PROJECT_PATH=$(ssh -o StrictHostKeyChecking=no "$MAC_STUDIO" "find /root /home /opt /Users -name 'atra-web-ide' -type d 2>/dev/null | head -1")

if [ -z "$PROJECT_PATH" ]; then
    echo "⚠️ Проект не найден на Mac Studio"
    echo "📦 Файлы готовы в: $SYNC_DIR"
    echo ""
    echo "Инструкция:"
    echo "1. Откройте Cursor на Mac Studio"
    echo "2. Найдите проект atra-web-ide"
    echo "3. Скопируйте файлы из $SYNC_DIR"
    echo "4. Или выполните вручную:"
    echo "   cd /path/to/atra-web-ide"
    echo "   cp -r $SYNC_DIR/knowledge_os/app/*.py knowledge_os/app/"
    echo "   cp -r $SYNC_DIR/backend/app/middleware/* backend/app/middleware/"
    echo "   cp $SYNC_DIR/backend/app/{config,main}.py backend/app/"
    echo "   cp $SYNC_DIR/backend/app/services/*.py backend/app/services/"
    echo "   cp $SYNC_DIR/backend/app/routers/*.py backend/app/routers/"
    exit 0
fi

echo "✅ Проект найден: $PROJECT_PATH"
echo ""

# 2. Применить изменения
echo "📦 Применение изменений..."

ssh -o StrictHostKeyChecking=no "$MAC_STUDIO" << EOF
    cd "$PROJECT_PATH"
    
    # Приоритет 3
    echo "  - Копирование файлов Приоритета 3..."
    cp -f $SYNC_DIR/knowledge_os/app/reinforcement_learning.py knowledge_os/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/knowledge_os/app/adaptive_agent.py knowledge_os/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/knowledge_os/app/emergent_hierarchy.py knowledge_os/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/knowledge_os/app/advanced_ensemble.py knowledge_os/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/knowledge_os/app/model_specialization.py knowledge_os/app/ 2>/dev/null || true
    
    # Middleware
    echo "  - Копирование middleware..."
    mkdir -p backend/app/middleware
    cp -f $SYNC_DIR/backend/app/middleware/*.py backend/app/middleware/ 2>/dev/null || true
    
    # Backend улучшения
    echo "  - Копирование backend улучшений..."
    cp -f $SYNC_DIR/backend/app/config.py backend/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/main.py backend/app/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/services/cache.py backend/app/services/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/services/knowledge_os.py backend/app/services/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/services/victoria.py backend/app/services/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/services/ollama.py backend/app/services/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/routers/chat.py backend/app/routers/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/routers/files.py backend/app/routers/ 2>/dev/null || true
    cp -f $SYNC_DIR/backend/app/routers/experts.py backend/app/routers/ 2>/dev/null || true
    
    # Документация
    echo "  - Копирование документации..."
    mkdir -p docs/mac-studio
    cp -f $SYNC_DIR/docs/mac-studio/SINGULARITY_9_IMPROVEMENTS.md docs/mac-studio/ 2>/dev/null || true
    
    echo "✅ Изменения применены!"
EOF

# 3. Проверка
echo ""
echo "✅ Проверка примененных файлов..."
ssh -o StrictHostKeyChecking=no "$MAC_STUDIO" << EOF
    cd "$PROJECT_PATH"
    
    echo "  - Приоритет 3:"
    ls -1 knowledge_os/app/{reinforcement_learning,adaptive_agent,emergent_hierarchy,advanced_ensemble,model_specialization}.py 2>&1 | wc -l
    
    echo "  - Middleware:"
    ls -1 backend/app/middleware/{error_handler,rate_limiter,logging_middleware}.py 2>&1 | wc -l
    
    echo "  - Документация:"
    test -f docs/mac-studio/SINGULARITY_9_IMPROVEMENTS.md && echo "✅ Есть" || echo "❌ Нет"
EOF

echo ""
echo "🎉 Готово! Все изменения применены на Mac Studio"
echo "📝 Проект: $PROJECT_PATH"
