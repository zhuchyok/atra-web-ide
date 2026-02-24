#!/bin/bash
# Скрипт для компиляции Rust с Profile-Guided Optimization (PGO)
# Ускоряет код на 10-30% за счет оптимизации горячих путей

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUST_DIR="$PROJECT_ROOT/rust-atra"
PGO_DATA_DIR="/tmp/pgo-data"

echo "🔧 Начинаем PGO компиляцию Rust модуля..."

# Создаем директорию для PGO данных
mkdir -p "$PGO_DATA_DIR"
rm -rf "$PGO_DATA_DIR"/*

# Шаг 1: Компиляция с профилированием
echo "📊 Шаг 1: Компиляция с профилированием..."
cd "$RUST_DIR"
RUSTFLAGS="-C profile-generate=$PGO_DATA_DIR" cargo build --release

# Шаг 2: Запуск тестов и бенчмарков для сбора профиля
echo "🧪 Шаг 2: Запуск тестов для сбора профиля..."
if [ -f "$PROJECT_ROOT/Makefile" ]; then
    cd "$PROJECT_ROOT"
    make test || echo "⚠️ Некоторые тесты не прошли, но профиль собран"
else
    # Fallback: запускаем pytest тесты, которые используют Rust
    cd "$PROJECT_ROOT"
    python3 -m pytest tests/ -k "rust" --maxfail=5 -v || echo "⚠️ Некоторые тесты не прошли, но профиль собран"
fi

# Шаг 3: Компиляция с использованием профиля
echo "⚡ Шаг 3: Компиляция с использованием профиля..."
cd "$RUST_DIR"
RUSTFLAGS="-C profile-use=$PGO_DATA_DIR" cargo build --release

# Проверяем результат
if [ -f "$RUST_DIR/target/release/libatra_rs.so" ] || [ -f "$RUST_DIR/target/release/libatra_rs.dylib" ]; then
    echo "✅ PGO компиляция завершена успешно!"
    echo "📦 Бинарник находится в: $RUST_DIR/target/release/"

    # Копируем бинарник в корень проекта (если нужно)
    if [ -f "$RUST_DIR/target/release/libatra_rs.so" ]; then
        cp "$RUST_DIR/target/release/libatra_rs.so" "$PROJECT_ROOT/atra_rs.so"
        echo "✅ Бинарник скопирован в $PROJECT_ROOT/atra_rs.so"
    elif [ -f "$RUST_DIR/target/release/libatra_rs.dylib" ]; then
        cp "$RUST_DIR/target/release/libatra_rs.dylib" "$PROJECT_ROOT/atra_rs.dylib"
        echo "✅ Бинарник скопирован в $PROJECT_ROOT/atra_rs.dylib"
    fi
else
    echo "❌ Ошибка: бинарник не найден после компиляции"
    exit 1
fi

# Очистка временных данных (опционально)
read -p "🗑️ Удалить временные PGO данные? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$PGO_DATA_DIR"
    echo "✅ Временные данные удалены"
else
    echo "ℹ️ Временные данные сохранены в $PGO_DATA_DIR"
fi

echo "🎉 PGO компиляция завершена!"
