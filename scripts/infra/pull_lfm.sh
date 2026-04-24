#!/bin/bash
# [SINGULARITY 28.2] Pull Lfm-2.5-350m using direct GGUF download with correct URL
LFM_URL="https://huggingface.co/bartowski/LFM-2.5-350M-Instruct-GGUF/resolve/main/LFM-2.5-350M-Instruct-Q8_0.gguf?download=true"

echo "📥 Downloading Lfm-2.5-350m GGUF..."
curl -L "$LFM_URL" -o /tmp/lfm-350m.gguf

# Check file size to ensure it's not a small error page
FILE_SIZE=$(du -m /tmp/lfm-350m.gguf | cut -f1)
if [ "$FILE_SIZE" -lt 100 ]; then
    echo "❌ Download failed or file too small ($FILE_SIZE MB). Check URL."
    exit 1
fi

echo "🛠️ Creating Ollama Modelfile..."
cat <<'MODELF' > /tmp/LfmModelfile
FROM /tmp/lfm-350m.gguf
PARAMETER temperature 0.7
PARAMETER stop "<|endoftext|>"
MODELF

echo "🚀 Creating Ollama model 'lfm:350m'..."
ollama create lfm:350m -f /tmp/LfmModelfile

echo "✅ Lfm:350m is ready."
rm /tmp/lfm-350m.gguf /tmp/LfmModelfile
