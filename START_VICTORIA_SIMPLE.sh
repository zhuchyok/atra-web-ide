#!/bin/bash
cd /Users/bikos/Documents/atra-web-ide

export USE_VICTORIA_ENHANCED=true
export ENABLE_EVENT_MONITORING=true
export PYTHONPATH="/Users/bikos/Documents/atra-web-ide:/Users/bikos/Documents/atra-web-ide/knowledge_os:$PYTHONPATH"

echo "🚀 Запуск Victoria Server..."
echo "   Порт: 8010"
echo ""

cd /Users/bikos/Documents/atra-web-ide
python3 src/agents/bridge/victoria_server.py
