#!/bin/bash
# =============================================================================
# Сборка frontend (Svelte + xterm). Требует: npm/node.
# =============================================================================

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

if ! command -v npm &>/dev/null; then
    echo "❌ npm не найден. Установите Node.js (nvm, brew, etc.)."
    exit 1
fi

echo "=============================================="
echo "🧪 ATRA Web IDE — frontend build"
echo "=============================================="
echo ""

echo "[1/2] npm install..."
npm install

echo "[2/2] npm run build..."
npm run build

echo ""
echo "✅ Frontend собран (dist/)."
