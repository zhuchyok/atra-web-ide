#!/usr/bin/env bash
# Установка моделей Ollama: 6 из docs/CURRENT_MODELS_LIST.md + nomic-embed-text (для эмбеддингов RAG/кэш).
# Запуск: ./scripts/install_ollama_models.sh (или bash scripts/install_ollama_models.sh)

set -e
MODELS=(
  "phi3.5:3.8b"
  "moondream:latest"
  "llava:7b"
  "qwen2.5-coder:32b"
  "glm-4.7-flash:q8_0"
  "qwq:32b"
  "nomic-embed-text"   # для /api/embeddings (RAG, semantic_cache, Victoria)
)
for m in "${MODELS[@]}"; do
  echo "=== Pulling $m ==="
  ollama pull "$m" || { echo "Warning: $m failed"; }
done
echo "=== Done. ollama list ==="
ollama list
