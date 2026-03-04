#!/bin/bash
# Update completions script to use native --generate

cd "$(dirname "$0")/.."

echo "🔧 Generating shell completions using atra --generate..."

# Create completions directory
mkdir -p completions

# Generate for each shell
echo "Generating Bash completion..."
cargo run --bin atra -- --generate bash > completions/atra.bash

echo "Generating Zsh completion..."
cargo run --bin atra -- --generate zsh > completions/_atra

echo "Generating Fish completion..."
cargo run --bin atra -- --generate fish > completions/atra.fish

echo "✅ Completions generated in completions/"
echo ""
echo "📋 Installation instructions:"
echo ""
echo "Bash:"
echo "  source completions/atra.bash"
echo "  # Or: sudo cp completions/atra.bash /usr/share/bash-completion/completions/atra"
echo ""
echo "Zsh:"
echo "  # Add to \$fpath and run: compinit"
echo "  sudo mkdir -p /usr/local/share/zsh/site-functions"
echo "  sudo cp completions/_atra /usr/local/share/zsh/site-functions/"
echo ""
echo "Fish:"
echo "  mkdir -p ~/.config/fish/completions"
echo "  cp completions/atra.fish ~/.config/fish/completions/"
