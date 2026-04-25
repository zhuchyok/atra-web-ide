#!/usr/bin/env bash
# [SINGULARITY 25.0] Harden Phi-3.5 model with strict context limits to prevent VRAM overflow.

set -e

MODEL_NAME="phi3.5:3.8b"
STABLE_NAME="phi3.5:3.8b-stable"

echo "🛡️ Hardening $MODEL_NAME into $STABLE_NAME..."

# Create temporary Modelfile
cat <<EOF > /tmp/StablePhi.Modelfile
FROM $MODEL_NAME
PARAMETER num_ctx 16384
PARAMETER stop "<|system|>"
PARAMETER stop "<|user|>"
PARAMETER stop "<|end|>"
PARAMETER stop "<|assistant|>"
EOF

# Register model in Ollama
ollama create $STABLE_NAME -f /tmp/StablePhi.Modelfile

echo "✅ Model $STABLE_NAME created with 16K context limit."
rm /tmp/StablePhi.Modelfile
