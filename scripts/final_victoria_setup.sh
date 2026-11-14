#!/bin/bash
# Финальная автоматическая настройка Victoria для всех проектов Cursor.
# Запускать один раз: bash scripts/final_victoria_setup.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
SETUP_FAIL=0

echo "=============================================="
echo "🚀 Финальная настройка Victoria"
echo "=============================================="
echo ""

# 1. MCP в Cursor settings
echo "[1/4] Настройка MCP в Cursor..."
if [ -f "$ROOT/scripts/setup_cursor_mcp_global.py" ]; then
  python3 "$ROOT/scripts/setup_cursor_mcp_global.py" 2>&1 | grep -E "(✅|⚠️|❌)" || true
elif [ -f "$ROOT/scripts/victoria/setup_cursor_mcp_global.py" ]; then
  python3 "$ROOT/scripts/victoria/setup_cursor_mcp_global.py" 2>&1 | grep -E "(✅|⚠️|❌)" || true
else
  echo "      ⚠️  setup_cursor_mcp_global.py не найден"
fi

# 2. Проверка Victoria — CRITICAL
echo ""
echo "[2/4] Проверка Victoria (8010)..."
if curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      ❌ Victoria не отвечает (проверь Docker)"
  SETUP_FAIL=1
fi

# 3. Установка fastmcp (только если legacy MCP)
echo ""
echo "[3/4] Проверка fastmcp..."
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
  if python3 -c "import fastmcp" 2>/dev/null; then
    echo "      ✅ fastmcp установлен"
  else
    echo "      📦 Установка fastmcp..."
    if pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1; then
      echo "      ✅ fastmcp установлен"
    else
      echo "      ❌ fastmcp install failed"
      SETUP_FAIL=1
    fi
  fi
else
  echo "      ℹ️  fastmcp skip (CHECK_LEGACY_MCP!=true)"
fi

# 4. MCP 8012 optional
echo ""
echo "[4/4] MCP сервер (legacy 8012)..."
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
  if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер работает"
  else
    export PYTHONPATH="$ROOT:$PYTHONPATH"
    nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
    sleep 3
    if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
      echo "      ✅ MCP сервер запущен"
    else
      echo "      ❌ MCP 8012 не поднялся"
      SETUP_FAIL=1
    fi
  fi
else
  echo "      ℹ️  MCP 8012 skip; live = 8010 + brain 11434"
fi

echo ""
echo "=============================================="
if [ "$SETUP_FAIL" -eq 0 ]; then
  echo "✅ ГОТОВО!"
else
  echo "⚠️ НАСТРОЙКА ЗАВЕРШЕНА С ОШИБКАМИ"
fi
echo "=============================================="
exit "$SETUP_FAIL"
