#!/usr/bin/env bash
# Скрипт сборки всего Rust workspace
# Использует shared dependencies для ускорения rebuild

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "🦀 Building Rust workspace..."
echo "📦 Projects: gateway, atra-cli, scout, knowledge_engine"
echo ""

# Profile: release или release-lto (для production с LTO)
PROFILE="${1:-release}"

if [[ "$PROFILE" == "release-lto" ]]; then
    echo "🚀 Building with Link-Time Optimization (LTO) for production..."
    cargo build --workspace --profile release-lto
else
    echo "⚡ Building with standard release profile..."
    cargo build --workspace --release
fi

echo ""
echo "✅ Build complete!"
echo ""
echo "📍 Binaries:"
echo "   - Gateway:  target/release/gateway"
echo "   - CLI:      target/release/atra"
echo "   - Scout:    target/release/scout"
