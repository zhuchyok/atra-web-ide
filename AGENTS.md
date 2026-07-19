# ATRA Web IDE — Agent Instructions

## Quick Start
```bash
# Start services (MLX, Ollama, Postgres, workers)
docker compose up -d

# Start Victoria API
cd knowledge_os && uvicorn app.main:app --host 0.0.0.0 --port 8010
```

## Key Directories
- `knowledge_os/app/` — Core AI agents (Victoria, orchestrators, workers)
- `knowledge_os/db/` — PostgreSQL schema and migrations
- `backend/` — Rust core components
- `frontend/` — React/TypeScript UI
- `src/agents/bridge/` — Victoria & Veronica server implementations

## Services & Ports

| Service | Host Port | Internal Port | Role |
|---------|-----------|---------------|------|
| **Victoria Agent** | 8010 | 8000 | Orchestrator / Decision-maker. Routes tasks to experts. Full RAG access. |
| **Veronica Agent** | 8011 | 8000 | Executor ("hands"). File ops, web search, browser automation, code gen. |
| **Python Backend** | 8080 | 8000 | FastAPI backend (ILIKE text search on knowledge). |
| **Rust Gateway** | 8081 | 8081 | High-throughput API gateway. |
| **Knowledge REST API** | 8002 | 8002 | JWT-auth knowledge API. |
| **Visual Search** | 8005 | 8005 | UI/schema/PDF analysis (VisualRAG). |
| **Open WebUI** | 3005 | 8080 | Frontend chat UI. |
| **Corporation Dashboard** | 8501 | 8501 | Streamlit dashboard. |
| **MLX API** | 11435 | 11435 | Local LLM inference (victoria-wisdom-v3.5). |
| **Ollama** | 11434 | 11434 | Ollama models. |

## Knowledge Base (RAG) — 114k+ nodes

**Endpoint (best for agents):**
```bash
curl -s -X POST http://localhost:8010/api/omni-rag/search \
  -H "Content-Type: application/json" \
  -d '{"query":"архитектура ATRA","limit":3}'
```
Returns hybrid search (vector + keyword + rerank). **Keep queries short (2-4 words).** Long queries cause 500.

**Alternative (ILIKE text search, no auth):**
```bash
curl "http://localhost:8080/knowledge?q=deploy&limit=5"
```

**DB stats:**
```bash
docker exec knowledge_postgres psql -U admin -d knowledge_os -c \
  "SELECT COUNT(*) FROM knowledge_nodes;"
```
~114k nodes: 47k 💎 fundamental knowledge, 23k PROJECT_FILE, 3.8k markdown_doc + hypotheses.

## Bible (MASTER_REFERENCE.md)
**Path:** `docs/MASTER_REFERENCE.md` (2047 lines, Singularity 31.2+)
- Mounted in containers at `/workspace/global_docs/MASTER_REFERENCE.md`
- Also: `docs/CHANGES_FROM_OTHER_CHATS.md`
- Referred to as "библия" / "корпоративный контекст" in codebase

## Key Agents

### Victoria (port 8010)
- **Role:** Chief Architect / Orchestrator. Analyzes tasks, selects experts (85+ in DB), delegates, synthesizes results.
- **Models:** MLX (victoria-wisdom-v3.5) + Ollama + cloud fallback
- **Entry:** `python -m src.agents.bridge.victoria_server`
- **RAG:** Full access to knowledge_nodes. Routes to Veronica for web research.
- **Endpoints:** `/v1/chat/completions`, `/run`, `/orchestrate`, `/plan`, `/api/omni-rag/search`, `/api/hidden-thoughts/{session_id}`
- **Health:** `curl localhost:8010/health`

### Veronica (port 8011)
- **Role:** Local Developer / "hands". Executes concrete steps, no strategic decisions.
- **Models:** Ollama only (no direct MLX)
- **Entry:** `python -m src.agents.bridge.server`
- **Capabilities:** read_file, run_terminal_cmd, ssh_run, web_search (DuckDuckGo), grep_search, apply_patch, browser_action (Playwright)
- **Sub-modules:**
  - `VeronicaWebResearcher` — zero-token research via local models + DuckDuckGo
  - `VeronicaScout` — autonomous daemon (every 6h), scrapes AI news → knowledge_nodes
- **Health:** `curl localhost:8011/health`
- **Execute task:** `POST localhost:8011/run` with `{"goal": "...", "project_context": "atra-web-ide"}`

### Orchestrator (`orchestrator.py`)
- **Cycle:** `run_orchestration_cycle()` — runs periodically
  - Phase 1: Cross-domain knowledge linking (Associative Brain)
  - Phase 2: Detect knowledge deserts → assign research (Curiosity Engine)
  - Phase 3: Auto-recruit experts for uncovered domains
- **Task decomposition:** `task_orchestration/task_decomposer.py` creates DAG of subtasks
- **Expert matching:** `expert_matching_engine.py` selects best expert by category/workload/models
- **Bidding:** `blackboard_service.py` — auction-style task assignment (post_goal → bid → resolve → claim)

### Experts & Workers
- **Expert Worker** (`expert_worker.py`): Core execution engine. AgentScope-based distributed actor. Handles task lifecycle, adaptive timeouts, contract enforcement.
- **Smart Worker Autonomous** (`smart_worker_autonomous.py`): Parallel processing loop, heartbeat watchdog, RAG-loop guard, batch processing, escalation to Board of Directors.
- **Expert Council** (`expert_council_discussion.py`): Multi-agent debate (9+ experts) for brainstorming.
- **Expert Evolver** (`expert_evolver.py`): Mutates expert prompts based on performance.
- **Expert Generator** (`expert_generator.py`): Autonomous recruitment for uncovered domains.
- **Expert DNA Manager** (`expert_dna_manager.py`): Loads expert-specific `.mdc` rule files.

### Demons (Security & Adversarial Agents)
- **Adversarial Critic** (`adversarial_critic.py`): "Devil's Advocate" — stress-tests knowledge nodes and high-priority tasks for flaws, hallucinations, security risks. Mandatory Trust Gate for priority >= 8 tasks.
- **Chaos Injector** (`agent_chaos_injector.py`): Chaos Monkey — injects latency/hallucination/tool errors into Shadow Execution to test resilience.
- **Threat Detector** (`threat_detector.py`): Real-time guardrail — regex for prompt injection, data leaks, resource exhaustion. Logs to `anomaly_detection_logs`.
- **Shadow Execution** (`shadow_execution_manager_v2.py`): Runs optimized/shadow version in parallel, compares results, recommends hot-swap if >15% faster.
- **Enhanced Immunity** (`enhanced_immunity.py`): Nightly pipeline — Phase 1: auto-fix weak nodes, Phase 2: adversarial + auto-fix, Phase 3: cleanup outdated.
- **Adversarial Implementation Generator** (`adversarial_implementation_generator.py`): Creates implementation tasks from survived knowledge.

## Communication Architecture

```
Task → Orchestrator → TaskDecomposer → ExpertMatchingEngine
  → Blackboard (post_goal → bids → resolve_auction → claim)
  → Expert Worker (via Redis Streams: expert_tasks:{name})
  → ai_core.run_smart_agent_async() → LLM (MLX/Ollama)
  → Result → tasks table + knowledge_nodes + Blackboard evidence
```

Channels: Redis Streams (task distribution), Blackboard (bidding), PostgreSQL (persistence), AgentScope (actor model with event sourcing).

## Critical Commands

### Query knowledge nodes
```bash
docker exec knowledge_postgres psql -U admin -d knowledge_os -c \
  "SELECT id, LEFT(content,80), similarity, confidence_score FROM knowledge_nodes ORDER BY created_at DESC LIMIT 5;"
```

### Query tasks status
```bash
docker exec knowledge_postgres psql -U admin -d knowledge_os -c \
  "SELECT status, count(*) FROM tasks GROUP BY status;"
```

### Check services
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### Run Victoria (main API)
```bash
uvicorn knowledge_os.app.main:app --host 0.0.0.0 --port 8010
```

## Common Issues

### "Solved:" or "ЗАДАЧА:" in responses
- Check `ai_core.py` — `_clean_response()` should filter metadata markers
- Check `VictoriaEnhanced.solve()` — should call `run_smart_agent_async`, not return stub

### Hallucinations
- Ensure anti-hallucination prompt is injected in `ai_core.py` for Victoria
- System relies on `victoria-wisdom-v3.5` model via MLX (port 11435)

### Database not accessible
- Use `docker exec knowledge_postgres psql -U admin -d knowledge_os` instead of local `psql`
- Default: `postgresql://admin:secret@localhost:6432/knowledge_os`

### Worker stuck tasks
- Check Redis queue: `knowledge_os/app/redis_manager.py`
- Task states: `pending`, `in_progress`, `completed`, `cancelled`
- Auto-requeue: see `smart_worker_autonomous.py`

## Docker Compose Files

| File | Services |
|------|----------|
| `docker-compose.yml` | gateway (8081), frontend (3000), backend (8080), prometheus (9091), grafana (3002) |
| `docker-compose.vds.yml` | postgres, redis, nginx-proxy, atra-core, moskit-api |
| `knowledge_os/docker-compose.yml` | db (5432), pgbouncer (6432), redis (6381), searxng (8084) — includes 3 others |
| `knowledge_os/docker-compose.agents.yml` | quality-service, victoria-agent (8010), veronica-agent (8011), orchestrator, expert-workers (heavy/anna/victoria/dynamic), smart-worker, evolution, nightly, rest-api (8002), telegram, watchdog, board-scheduler, visual-search (8005) |
| `knowledge_os/docker-compose.ui.yml` | open-webui (3005), corporation-dashboard (8501) |
| `knowledge_os/docker-compose.monitoring.yml` | prometheus (9092), grafana (3001), elasticsearch (9200), kibana (5601) |

## Frontend Stack
- **Framework:** Svelte 4 + Tailwind CSS 3 + Vite 5
- **Components:** CodeMirror editor, xterm.js terminal, Chat (SSE streaming), FileTree, PlanPanel, Preview, SystemMetrics, ExpertSelector, ClusterDashboard, Git
- **Backend routers (23):** chat, files, editor, terminal, preview, experts, expert_dialogue, knowledge, domains, metrics, system_metrics, quality, latency, rag_optimization, ab_testing, auto_optimizer, cache_stats, data_retention, multimodal, plan_cache, sandbox
- **Open WebUI (3005):** Faces Victoria API as OpenAI-compatible endpoint. Bootstrap scripts in `scripts/openwebui_*.py`

## Knowledge REST API (port 8002)
- **Auth:** JWT (`/auth/login`) + API-Key
- **Endpoints:** `/search` (ILIKE), `/knowledge` (CRUD), `/feedback`, `/api/board/consult`, `/api/experts/evolve`, `/api/experts/skills/*`, `/api/tasks/reset-stuck`, `/api/victoria/solve`, `/api/approvals/*`
- **Prometheus:** `/metrics` — orchestration, A/B, deferred, web search

## Docker Agent Services

| Container | Role |
|-----------|------|
| `victoria-agent` | Chief Architect (port 8010) |
| `veronica-agent` | Executor "hands" (port 8011) |
| `expert-worker-heavy` (Роман) | Heavy expert worker |
| `expert-worker-anna` (Анна) | Expert worker |
| `expert-worker-victoria` (Виктория) | Expert worker (5g mem) |
| `expert-worker-dynamic-1` (Инна) | Dynamic slot |
| `expert-worker-dynamic-2` (Юлия) | Dynamic slot |
| `knowledge_os_worker` | Smart autonomous worker |
| `knowledge_evolution` | Evolution loop (4g) |
| `knowledge_nightly` | Nightly learning (8g) |

## Pipeline: ai_core.py (central LLM entry)

```
Expert/Worker → run_smart_agent_async()
  → SafetyChecker → AnomalyDetector → SemanticCache
  → RAG retrieval (knowledge_nodes)
  → Model selection (MLX → Ollama → Cloud)
  → LLM call → _clean_response()
  → ConstitutionalCourt → TaskResultValidator
  → Result → tasks + knowledge_nodes + Blackboard
```

All agents call `ai_core.py:run_smart_agent_async()`. It integrates 40+ modules.

## Architecture Flow

```
Board of Directors → EnhancedOrchestrator
  → TaskDecomposer (DAG)
  → ExpertMatchingEngine
  → Blackboard (post_goal → bidding → claim)
  → Expert Worker (AgentScope actor)
  → ai_core → LLM → validation → result
```

Channels: Redis Streams (expert_tasks:{name}), Blackboard (bidding), PostgreSQL (tasks table), AgentScope (event sourcing).

## Curator System (скоринг «как я»)

Система, которая сравнивает ответы Victoria с эталоном (стандарты куратора/Cursor-агента).

**Файлы:**
- `scripts/curator_send_tasks_to_victoria.py` (917 строк) — отправляет список задач Victoria, poll-ит результат, сохраняет JSON+MD отчёт в `docs/curator_reports/`
- `scripts/curator_compare_to_standard.py` — сравнивает ответ Victoria с эталоном, скор «как я»
- `scripts/curator_findings_to_knowledge.py` — извлекает PROBLEM-строки из отчёта в `knowledge_nodes`
- `scripts/curator_add_standard_to_knowledge.py` — добавляет эталоны в RAG (домен `curator_standards`)
- `scripts/victoria_self_curator.py` — прогон куратора + самоанализ Victoria

**Стандарты (эталонные ответы):** `docs/curator_reports/standards/`
- `greeting.md`, `status_project.md`, `what_can_you_do.md`, `list_files.md`, `one_line_code.md`, `code_audit.md`
- Секции: **Ключевые фразы** + **Эталонный ответ** + **Критерии**

**Запуск:**
```bash
./scripts/run_curator.sh                                          # быстрый прогон
./scripts/run_curator_and_compare.sh                              # прогон + сравнение
DATABASE_URL=... python3 scripts/curator_add_standard_to_knowledge.py  # добавить эталоны в RAG
```

## Nightly Learner & Distillation

**`nightly_learner.py`** — главный демон:
- **Continuous distillation** (каждые 300с = 5 мин): `run_continuous_distillation()` → `distillation_engine.py:KnowledgeDistiller`
- **Nightly cycle** (каждые 86400с = 24ч): self-learning → evolution → promotion → mentorship
- **Turbo mode** — включается при backlog > 12, до 10 раундов

**`distillation_engine.py`** (915 строк) — `KnowledgeDistiller`:
1. Lease nodes via `FOR UPDATE SKIP LOCKED`
2. DuckDB + PyArrow in-memory
3. Parallel teacher calls (Ollama `phi3.5:3.8b` / OpenRouter cloud)
4. Quality gate (0.35-0.98)
5. Persist: `metadata.distilled=true`, 25+ v2 metadata fields, LanceDB sync

**`corporation_self_learning.py`** — самообучение корпорации (каждые 6ч):
- Анализ ошибок → метрики производительности → генерация улучшений → применение → `corporation_learning_log`

## Skills System (78 skills)

**Location:** `knowledge_os/app/skills/` — 78 bundled + 17 procedural
**Format:** `SKILL.md` с YAML frontmatter (name, description, version, metadata)

**Selection:** `worker_memory.py` — role-based + relevance-based (keyword overlap), top-3 навыка вставляются в system prompt эксперта.

**Examples:** code-review, python-development, backend-development, swarm-intelligence, tree-of-thoughts, extended-thinking, mentorship-engine, adversarial-red-teaming, etc.

**Управление:**
- `POST /api/experts/skills/reload` — hot-reload
- `GET /api/experts/skills/categories` — list by category

## Board of Directors

**`strategic_board.py`** (723 строк) — собирает совет директоров:
- Консультирует multiple expert "directors" через LLM
- Выдаёт структурированные решения (decision, rationale, risks, confidence, action items)
- Сохраняет в `board_decisions` таблицу

**`board_scheduler.py`** — демон, запускает заседание каждые 6ч
- **API:** `POST /api/board/consult`
- **Интеграция:** `enhanced_orchestrator.py` → `consult_board()` для эскалации

## Swarm Intelligence (роевая система)

**`swarm_intelligence.py`** (314 строк) — Particle Swarm Optimization:
- **Island Model** — группы агентов в специализированных кластерах
- **Роли:** explorer (разведчик), skeptic (оппонент), elite (лучшие)
- Модель: `smollm2:360m` (быстрый Ollama)

**`swarm_studio.py`** — Web UI мониторинг роя (порт 8006)
**Вызов:** `EnhancedOrchestratorV2` при complexity > 0.7

## Constitutional Court

**`constitutional_court.py`** (114 строк) — «Верховный суд»:
- Проверяет решения экспертов против **Цифровой Конституции** (5 принципов: Data-Driven, Security First, Predictive Correction, Scalability, Constitutional Honesty)
- Вызывается `adversarial_critic.py` при Trust Gate (priority >= 8)

**`constitutional_rewards.py`** (230 строк) — штрафы/награды за поведение агентов.

## Additional Security & Monitoring

- **Safety Checker** (`safety_checker.py`): regex-фильтр опасных паттернов (eval, exec, rm -rf, DROP TABLE), вызывается после LLM
- **Anomaly Detector** (`anomaly_detector.py`): DDoS, brute force, SQLi/XSS/command injection — до LLM
- **Self Check System** (`self_check_system.py`): health check PostgreSQL, Redis, MLX, Ollama, Docker — каждые 60с, авто-фикс
- **Performance Watchdog** (`performance_watchdog.py`): мониторинг производительности

## Memory Systems

- **Episodic Memory** (`episodic_memory.py`): `EpisodicMemoryManager` — пользовательские предпочтения, паттерны, решения. Таблица `episodic_memory`.
- **Journal Manager** (`memory/journal_manager.py`): `ExpertJournalManager` — память эксперта о выполненных задачах. Таблица `expert_journals`.
- **Experience Retriever** (`experience_retriever.py`): ищет релевантные mentorship_note и failed задачи для проактивных предупреждений.
- **Hierarchical / Collective / Long-term memory** — иерархия памяти

## Explicit Handoffs (передача задач между агентами)

**`explicit_handoffs.py`** (379 строк) — `HandoffManager`:
- `Handoff` dataclass: from_agent, to_agent, task, context, deadline, priority
- Contract enforcement (Singularity 28.0)
- Auto-escalation при превышении deadline
- Интегрирован в `ai_core.py` и `expert_worker.py`

## Task Result Validator

**`task_result_validator.py`** (64 строк) — быстрый quality gate:
- Reject empty/null (0.0)
- Detect error indicators (0.2)
- Word overlap relevance
- Длинные ответы бонус (>=100 chars +0.1)
- Порог: score >= 0.5 = valid

## MLX Config

**`mlx_config.py`** (238 строк) — управление MLX моделями:
- Профили: reasoning, coding, fast, default
- Мониторинг GPU памяти Apple Metal
- GC при 98% заполнении

## Experts & Department Heads

- **Эксперты в БД (85+):** Роман (heavy), Анна (verify), Виктория, Инна, Юлия, Татьяна (Technical Writer) и др.
- **Department Heads:** `department_heads_system.py` — главы отделов (Documentation → Татьяна)
- **Organizational Structure:** `organizational_structure.py` — полная оргструктура
- **Aliases:** `expert_aliases.py` — разрешение имён (вика → Виктория, таня → Татьяна)

## Testing
```bash
pytest knowledge_os/tests/
```

### Reproducible Test Bootstrap (P0)
```bash
# From repository root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r backend/requirements-dev.txt -r knowledge_os/requirements-test.txt

# Verification
python -m pytest backend/app/tests -q
python -m pytest knowledge_os/tests -q
```

Notes:
- `knowledge_os/requirements-test.txt` is the canonical dependency set for test runs.
- It intentionally excludes heavyweight optional runtime integrations that are not needed by the test suites.

## Env Configuration
- Main config: `.env` in knowledge_os/
- Model settings: `VICTORIA_MODEL`, `VICTORIA_MLX_BRAIN=true`
- Timeouts: `MLX_GENERATION_TIMEOUT=600`, `SMART_WORKER_MAX_PENDING=1000`
- Distillation: `DISTILL_FORCE_BATCH_SIZE`, `DISTILL_LLM_CONCURRENCY=1`, `DISTILL_CLOUD_MODEL`
- Nightly: `NIGHTLY_INTERVAL_SEC=86400`, `NIGHTLY_DISTILL_TARGET_ELIGIBLE=5`

## Advanced Components (Singularity 28.X)

### Symbol Tuning (symbol_tuner.py)
- 8 behavior symbols: concise, detailed, creative, diplomatic, technical, educational, fast, safe
- Usage: `from symbol_tuner import get_symbol_tuner; tuner = get_symbol_tuner()`

### Constitutional Rewards (constitutional_rewards.py)
- Penalties for: hallucination (-0.5), ignored_data (-0.3), security_risk (-0.4)
- Rewards for: constitutional_compliance (+0.3), self_correction (+0.2), helped_user (+0.5)
- Usage: `from constitutional_rewards import get_constitutional_rewards`

### Toil Detection (toil_detector.py)
- Auto-detects repetitive tasks
- Usage: `from toil_detector import get_toil_detector; detector = get_toil_detector()`

### Wisdom Pipeline (agent_ab_testing.py)
- Auto-generates wisdom rules from A/B results
- Usage: `ab_test = get_agent_ab_testing(); await ab_test.generate_wisdom_rules(7)`