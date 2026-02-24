#!/bin/bash
# Build script for Rust acceleration module

set -e

echo "🦀 Building Rust acceleration module..."

cd rust-atra

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo not found. Please install Rust: https://rustup.rs/"
    exit 1
fi

# Build release version
echo "📦 Building release version..."
cargo build --release

# Find the compiled library
if [ -f "target/release/libatra_rs.so" ]; then
    LIB_PATH="target/release/libatra_rs.so"
elif [ -f "target/release/libatra_rs.dylib" ]; then
    LIB_PATH="target/release/libatra_rs.dylib"
elif [ -f "target/release/atra_rs.dll" ]; then
    LIB_PATH="target/release/atra_rs.dll"
else
    echo "❌ Compiled library not found"
    exit 1
fi

echo "✅ Build successful!"
echo "📁 Library location: $LIB_PATH"

# Try to install to Python site-packages
if command -v python3 &> /dev/null; then
    PYTHON_SITE=$(python3 -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || echo "")
    if [ -n "$PYTHON_SITE" ] && [ -d "$PYTHON_SITE" ]; then
        echo "📦 Installing to Python site-packages..."
        cp "$LIB_PATH" "$PYTHON_SITE/atra_rs.so"
        echo "✅ Installed to: $PYTHON_SITE/atra_rs.so"
    else
        echo "⚠️  Could not determine Python site-packages"
        echo "   Manually copy $LIB_PATH to your Python path"
    fi
fi

echo ""
echo "🎉 Rust acceleration module ready!"
echo "   Use: from src.infrastructure.performance.rust_accelerator import get_rust_accelerator"
