# Руководство по авто-профилированию (Living Brain §6.3)

Для Performance Engineer (Ольга) и SRE. Периодический анализ узких мест в горячих модулях.

## Цель

Находить узкие места в ai_core, semantic_cache, local_router и создавать задачи для оптимизации или записывать инсайты в knowledge_nodes (domain: Performance).

## Ручной запуск

### cProfile (встроенный)

```bash
cd knowledge_os
.venv/bin/python -c "
import cProfile
import pstats
import io
from app import ai_core

prof = cProfile.Profile()
prof.enable()
import asyncio
asyncio.run(ai_core.run_smart_agent_async('Кратко: что такое RAG?', expert_name='Виктория'))
prof.disable()
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats('cumulative')
ps.print_stats(20)
print(s.getvalue())
" 2>&1 | tee /tmp/ai_core_profile.txt
```

### py-spy (нужна установка)

```bash
# Установка: pip install py-spy
cd knowledge_os
py-spy record -o /tmp/profile.svg -d 30 -- .venv/bin/python -c "
import asyncio, time
from app import ai_core
start = time.time()
while time.time() - start < 25:
    asyncio.run(ai_core.run_smart_agent_async('Тест RAG', expert_name='Виктория'))
"
# Открыть /tmp/profile.svg в браузере
```

## Интеграция с Nightly Learner (реализовано)

**Phase 15:** по воскресеньям запуск cProfile на json_fast load/dump roundtrip (500 итераций), топ-15 функций по cumulative time → knowledge_nodes с `source_ref='auto_profiling'`, domain Performance. Файл: `knowledge_os/app/nightly_learner.py`. См. CORPORATION_PLANNING_CALENDAR.

## Связанные документы

- [MASTER_REFERENCE](MASTER_REFERENCE.md) §5
- [VERIFICATION_CHECKLIST_OPTIMIZATIONS](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md)
- Living Brain plan §6.3
