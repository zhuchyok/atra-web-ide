#!/bin/bash
# Запуск дашборда корпорации ATRA
# Streamlit дашборд с задачами, экспертами, структурой

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASHBOARD_DIR="$PROJECT_ROOT/knowledge_os/dashboard"

echo "🚀 Запуск дашборда корпорации ATRA..."
echo "   Проект: $PROJECT_ROOT"
echo "   Время: $(date)"

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверяем БД
if ! docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ База данных недоступна!"
    exit 1
fi

# Устанавливаем зависимости если нужно
if [ ! -f "$DASHBOARD_DIR/.dependencies_installed" ]; then
    echo "📦 Установка зависимостей..."
    docker exec victoria-agent pip install streamlit pandas plotly psycopg2-binary networkx 2>&1 | tail -5
    touch "$DASHBOARD_DIR/.dependencies_installed"
fi

# Запускаем Streamlit дашборд
echo "🌐 Запуск Streamlit дашборда..."
echo "   URL: http://localhost:8501"
echo ""

# Проверяем, не запущен ли уже
if lsof -i :8501 > /dev/null 2>&1; then
    echo "⚠️ Дашборд уже запущен на порту 8501"
    echo "   Откройте: http://localhost:8501"
    exit 0
fi

# Запускаем через Docker с пробросом порта
echo "📦 Запуск через Docker..."
docker run -d \
    --name corporation_dashboard \
    --network atra-network \
    -p 8501:8501 \
    -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    -v "$PROJECT_ROOT/knowledge_os:/app/knowledge_os:ro" \
    -v "$PROJECT_ROOT:/app:ro" \
    --restart unless-stopped \
    python:3.11-slim \
    bash -c "pip install -q streamlit pandas plotly psycopg2-binary networkx asyncpg && cd /app/knowledge_os/dashboard && streamlit run app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"

sleep 3

# Проверяем что запустился
if lsof -i :8501 > /dev/null 2>&1; then
    echo "✅ Дашборд запущен!"
    echo ""
    echo "📊 Доступ:"
    echo "   Локально: http://localhost:8501"
    echo "   Удаленно: http://$(hostname -I | awk '{print $1}'):8501"
    echo ""
    echo "📋 Что показывает дашборд:"
    echo "   ✅ Задачи корпорации (статусы, исполнители)"
    echo "   ✅ Структура экспертов (департаменты, роли)"
    echo "   ✅ Обучение (академия ИИ, дебаты)"
    echo "   ✅ Аналитика (рост знаний, специализация)"
    echo "   ✅ OKR стратегия"
    echo "   ✅ И многое другое..."
else
    echo "⚠️ Дашборд не запустился, проверьте логи:"
    echo "   docker logs victoria-agent | grep streamlit"
fi
