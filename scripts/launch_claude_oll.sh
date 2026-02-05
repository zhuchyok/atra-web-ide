#!/usr/bin/env bash
# Запуск Claude Code через Ollama с рабочей папкой OLL.
# Использование: ./scripts/launch_claude_oll.sh

set -e
OLL_DIR="${OLL_DIR:-/Users/bikos/Documents/OLL}"
cd "$OLL_DIR"
exec ollama launch claude
