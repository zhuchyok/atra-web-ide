# ATRA Web IDE

Multi-agent AI system with Victoria as team lead, 88 experts, PostgreSQL, Redis, Ollama.

## Architecture

- **Victoria** (port 8010) → `victoria-wisdom-24k:latest` (num_ctx=24576, ~7.9GB RSS)
- **Backend** (port 8080) → FastAPI
- **Ollama** (port 11434) → MLX API
- **PostgreSQL** (port 5432) → knowledge_os DB, 91,328 records, 88 experts
- **Redis** → streams for expert task routing

## Expert Workers

| Worker     | Expert          | Stream    |
| ---------- | --------------- | --------- |
| dynamic-1  | Инна (overflow) | overflow  |
| dynamic-2  | Юлия (overflow) | overflow  |
| anna-1     | Анна            | dedicated |
| victoria-1 | Виктория        | dedicated |
| heavy-1    | heavy tasks     | dedicated |

## Key Files

- `src/agents/bridge/victoria_server.py` — Victoria server, model routing, concurrency semaphore
- `src/agents/core/executor.py` — executor model selection
- `knowledge_os/app/expert_stream_routing.py` — task dispatch (overflow/dedicated/shared)
- `knowledge_os/app/expert_worker.py` — worker startup, consumer groups
- `knowledge_os/app/enhanced_orchestrator.py` — orchestrator dispatch
- `knowledge_os/app/medic/log_scanner.py` — rate limiting (5 tasks/hour)
- `knowledge_os/app/medic/watchdog.py` — health monitoring
- `knowledge_os/docker-compose.agents.yml` — container config

## Current State (Sept 2026)

- Victoria model: `victoria-wisdom-24k` (switched from v3.5, 6x faster response)
- All containers healthy, 0 pending tasks
- Overflow routing fixed (dispatch_stream_for_expert checks is_overflow_expert)
- Docker VM: 24GB
- Grafana alerts → Telegram ( AtlE bot `vikoria_atra_bot`, chat 556251171)
- Alert `deferred-to-human-high`: `knowledge_os_tasks_deferred_new_24h_total > 10` (pipeline A→reduce→math)
- Prometheus scrapes knowledge_rest:8002 (deferred metrics)
- Old monitoring stack (atra-grafana, atra-prometheus, atra-kibana, atra-elasticsearch) остановлен (restart=no, volumes сохранены)
- Исторический бэклог 65 deferred задач помечен `deferred_review_done=true` (13.09.2026)
