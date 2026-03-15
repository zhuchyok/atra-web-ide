#!/bin/bash
# Запуск Victoria MCP Server для Cursor
# Использование: bash scripts/start_victoria_mcp.sh

set -e  # Выход при ошибке

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "🚀 Запуск Victoria MCP Server..." >&2
echo "📍 Workspace: $ROOT" >&2
echo "🔗 URL: http://localhost:8012" >&2
echo "" >&2

# Проверяем что Victoria Agent запущен (только если не в режиме Cursor)
if [ -t 0 ]; then
    # Интерактивный режим - можем спросить пользователя
    if ! curl -s http://localhost:8010/health > /dev/null 2>&1; then
        echo "⚠️  Victoria Agent (8010) не запущен!" >&2
        echo "💡 Запустите сначала: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent" >&2
        echo "" >&2
        read -p "Запустить сейчас? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
            echo "⏳ Ждём запуска Victoria Agent..." >&2
            sleep 5
        else
            exit 1
        fi
    fi
else
    # Не интерактивный режим (Cursor) - просто проверяем
    if ! curl -s http://localhost:8010/health > /dev/null 2>&1; then
        echo "⚠️  Victoria Agent (8010) не запущен!" >&2
        echo "💡 Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent" >&2
        exit 1
    fi
fi

# Запускаем MCP Server
export VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
export VICTORIA_MCP_RUN_TIMEOUT_SEC="${VICTORIA_MCP_RUN_TIMEOUT_SEC:-600}"

echo "✅ Victoria Agent готов" >&2

# Проверяем и создаём виртуальное окружение если нужно
VENV_DIR="$ROOT/.venv-agents"
PYTHON_BIN="$VENV_DIR/bin/python"

if [ ! -f "$PYTHON_BIN" ]; then
    echo "📦 Создаю виртуальное окружение .venv-agents..." >&2
    python3 -m venv "$VENV_DIR"
fi

# Проверяем наличие необходимых пакетов
if ! "$PYTHON_BIN" -c "import mcp.server.fastmcp" 2>/dev/null; then
    echo "📥 Устанавливаю зависимости для MCP сервера..." >&2
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet fastmcp httpx
    echo "✅ Зависимости установлены" >&2
fi

echo "🎯 Запускаю MCP Server..." >&2
echo "" >&2

# Запускаем MCP Server через виртуальное окружение
exec "$PYTHON_BIN" -m src.agents.bridge.victoria_mcp_server "$@"
