#!/bin/bash
# [v149.19] Целостность исходников: порча .py в системных путях → мгновенный откат из git + алерт.
# (SOURCE_GUARD ловит записи через write_file/execution, но не прямой open() из LLM-контента.)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd /Users/bikos/Documents/atra-web-ide || exit 1
PROTECTED="knowledge_os/app/ai_core.py knowledge_os/app/local_router.py src/agents/core/base_agent.py src/agents/core/executor.py src/agents/bridge/victoria_server.py knowledge_os/app/victoria_morning_report.py knowledge_os/app/ollama_keep_alive_policy.py knowledge_os/app/semantic_cache.py knowledge_os/app/nightly_learner.py"
DIRTY=""
for f in $PROTECTED; do
  python3 -m py_compile "$f" 2>/dev/null || DIRTY="$DIRTY $f"
done
if [ -n "$DIRTY" ]; then
  echo "$(date '+%F %T') CORRUPTED:$DIRTY — откат из git + рестарт воркеров" >> "$HOME/Library/Logs/atra/source_integrity.log"
  git checkout -- $DIRTY
  docker restart victoria-agent knowledge_os-expert-worker-dynamic-1-1 knowledge_os-expert-worker-dynamic-2-1 knowledge_os-expert-worker-dynamic-3-1 knowledge_os-expert-worker-dynamic-4-1 knowledge_os-expert-worker-dynamic-5-1 2>/dev/null
  curl -s -m 8 -H "Title: 🛡 SOURCE INTEGRITY: порча откатана" -H "Priority: high" \
    -d "Файлы:$DIRTY восстановлены из git; воркеры перезапущены" \
    "https://ntfy.sh/atra_victoria_curator" >/dev/null 2>&1
fi
