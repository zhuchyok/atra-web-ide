#!/bin/bash
# Install Rust and build ATRA acceleration module

set -e

echo "🦀 Установка Rust для ATRA..."

# Check if Rust is already installed
if command -v cargo &> /dev/null; then
    echo "✅ Rust уже установлен: $(cargo --version)"
    echo "📦 Собираем модуль..."
    cd "$(dirname "$0")/../rust-atra"
    cargo build --release
    echo "✅ Сборка завершена!"
    exit 0
fi

# Install Rust
echo "📥 Устанавливаем Rust..."
echo "   Это займет несколько минут..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
else
    echo "❌ Неподдерживаемая ОС. Установите Rust вручную: https://rustup.rs/"
    exit 1
fi

echo "✅ Rust установлен: $(cargo --version)"

# Build module
echo "📦 Собираем ATRA модуль..."
cd "$(dirname "$0")/../rust-atra"
cargo build --release

echo ""
echo "🎉 Готово!"
echo "✅ Rust установлен и модуль собран"
echo "💡 Rust ускорение теперь доступно - 10-100x быстрее!"
