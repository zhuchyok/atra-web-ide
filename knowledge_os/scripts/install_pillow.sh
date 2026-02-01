#!/usr/bin/env bash
# Установка Pillow для локальной работы с картинками (vision).
# Запуск из корня репо: bash knowledge_os/scripts/install_pillow.sh
# Или из knowledge_os: bash scripts/install_pillow.sh
# Нужен один раз тем, кто запускает обработку изображений локально.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_OS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$KNOWLEDGE_OS_DIR"

if [ ! -d ".venv" ]; then
  echo "❌ Сначала выполните: bash knowledge_os/scripts/setup_knowledge_os.sh"
  exit 1
fi

echo "📷 Установка Pillow (работа с картинками)..."

# pkg-config для Homebrew (macOS)
[ -d /opt/homebrew/lib/pkgconfig ] && export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:${PKG_CONFIG_PATH}"

# 1. Проверяем libjpeg (macOS: Homebrew). Без него Pillow не соберётся.
if ! pkg-config --exists libjpeg 2>/dev/null; then
  echo "⚠️  libjpeg не найден. Для сборки Pillow нужен libjpeg."
  if command -v brew >/dev/null 2>&1; then
    echo "   Выполните один раз (при необходимости сначала исправить права, затем jpeg):"
    [ ! -w "/opt/homebrew" ] 2>/dev/null && echo "   sudo chown -R \$(whoami) /opt/homebrew"
    echo "   brew install jpeg"
    echo "   Затем снова: bash knowledge_os/scripts/install_pillow.sh"
  else
    echo "   Установите libjpeg: macOS — brew install jpeg; Linux — sudo apt install libjpeg-dev (или yum/dnf)."
  fi
  exit 1
fi

# 2. Устанавливаем Pillow в venv
.venv/bin/pip install -q "Pillow>=10.0.0"

if .venv/bin/python -c "from PIL import Image" 2>/dev/null; then
  echo "✅ Pillow установлен. Локальная работа с картинками доступна."
else
  echo "❌ Pillow не установился. Проверьте: pkg-config --libs libjpeg"
  exit 1
fi
