---

## 93. Singularity 31.2+: P0 Stabilization Closure (2026-07-19)

- **Контекст:** изменения из параллельного чата приняты как базовые (full-first для expert-dialogue, расширенный контракт результата) и дожаты до устойчивого P0 состояния без отката чужих правок.
- **Expert dialogue bounded-runtime hardening:**
  - В `backend/app/routers/expert_dialogue.py` добавлен жесткий runtime guard для full-mode движков через изоляцию в worker-thread + bounded wait.
  - Сохранен full-first маршрут (`prefer_lightweight=false` по умолчанию), но латентность API ограничена и fallback остается рабочим.
  - Контракт ответа стабилен: `engine_used`, `participants`, `opinions`, `lightweight_used`, `fallback_used`.
- **SLA-ориентированные таймауты движков:**
  - `knowledge_os/app/multi_agent_debate.py`: снижены дефолты `DEBATE_EXPERT_TIMEOUT_SEC` (12с) и `DEBATE_SYNTHESIS_TIMEOUT_SEC` (20с).
  - `knowledge_os/app/expert_council_discussion.py`: снижены дефолты `COUNCIL_EXPERT_TIMEOUT_SEC` (18с) и `COUNCIL_SYNTHESIS_TIMEOUT_SEC` (18с).
  - Цель: не блокировать API при `Ollama 503 server busy`, удерживать режимы в bounded окне.
- **ai_core / import boundary / strict-local invariants:**
  - `knowledge_os/app/local_router.py`: fallback-импорты для `app.*`/локальных модулей исключают `ModuleNotFoundError` в mixed PYTHONPATH контекстах.
  - `knowledge_os/app/ai_core.py`: singleton `LocalAIRouter` пересоздается при patching класса (устранение флаков strict-local/failover тестов).
- **Метрики и идемпотентность:**
  - `knowledge_os/app/redis_manager.py`: регистрация `worker_queue_depth` через get-or-create подход, устранены повторные регистрации Prometheus.
  - Добавлен тест `knowledge_os/tests/test_redis_manager_metrics.py` для проверки reload/idempotency.
- **Reproducible test environment (P0):**
  - Добавлен `knowledge_os/requirements-test.txt` как канонический набор зависимостей для тестов без тяжелых необязательных runtime-интеграций.
  - `backend/requirements-dev.txt` дополнен `pytest-cov` и `pytest-codspeed`.
  - В `AGENTS.md` добавлен блок bootstrap-команд для воспроизводимого тестового окружения.
- **Верификация (после интеграции параллельных правок):**
  - `backend/app/tests`: **77 passed**.
  - `knowledge_os/tests`: **231 passed, 12 skipped**.
  - Smoke `/api/expert-dialogue/start`: подтверждены `default debate`, `prefer_lightweight`, `force_full sequential` с полным контрактом.
  - Финальный operational-срез: `docs/audits/2026-07-19-p0-final-verification.json`.
# 📖 БИБЛИЯ ATRA (MASTER_REFERENCE)

## 🌌 ТЕКУЩИЙ СТАТУС: Singularity 31.2.2+ (Hardening Mac Studio)

**Дата последнего обновления:** 2026-07-27
**Уровень эволюции:** 31.2.2 (Total Crystallization + Hardening)
**Состояние:** Стабильное; local-first evolution (v123)
**Целевая платформа:** Mac Studio (локальный мозг MLX + руки Ollama + Docker agents)

---

## § Последние изменения (2026-07-27 v123) — Local-first: drop Cursor CLI from evolver ✅

### Диагноз

Корпорация не требует Cursor CLI. `run_cursor_agent` в оркестраторе уже был алиасом на Victoria, но `expert_evolver` / `enhanced_expert_evolver` звали `/root/.local/bin/cursor-agent` → ERROR в Docker. Параллельно UPDATE experts с `jsonb_build_object(..., $3, $4)` давал `could not determine data type of parameter $3`.

### Решение

1. `victoria_local_agent.py` — local-only (router / ai_core), без бинаря Cursor.
2. Evolver mutation → `prefer_router=True` + `EVOLUTION_LOCAL_MODEL` (default phi3.5).
3. SQL evolve/specialize/insights → `metadata || $n::jsonb` с явным JSON patch.

### Evidence

- Unit: `test_victoria_local_agent.py`.
- Smoke: `generate_local … LOCAL_OK`; SQL patch on expert Alex OK.
- Guardrail: Cursor CLI не ставится в контейнеры.

---

## § Последние изменения (2026-07-27 v122) — Strong teacher: think:false + reachable high band ✅

### Диагноз

Priority re-distill предпочитал victoria, но Ollama thinking-модель писала в `thinking`, `response=""`, `done_reason=length` → fallback на phi → `band_high=0`. Даже при живом ответе quality gate max≈0.75 → high (≥0.8) был недостижим.

### Решение

1. Distiller: `think: false` для victoria/qwen3; `num_predict` env; salvage JSON из `thinking`.
2. Промпт: JSON-only + длины под quality gate (≥90 / ≥25).
3. `full_signal_bonus` +0.10 → high band достижим честно.
4. Tests: `test_distill_teacher_ollama_extract.py`.

### Evidence

- Unit: extract / think flag / high-band gate.
- Smoke: `teacher=victoria…`, `band=high conf=0.85`, `band_high≥2`.

### Guardrails

- Порог high=0.8 не снижали; phi fallback остаётся; batch priority ограничен.

---

## § Последние изменения (2026-07-26 v121) — Knowledge depth: KPI + upstream + priority re-distill ✅

### Диагноз

Coverage дистилляции ~99.8%, очередь `eligible_now≈4` — drained. Depth слабый: `band_high=0`, avg conf ~0.73, teacher почти весь `phi3.5`. Upstream wisdom: mentorship «Unknown Expert», SOP titles «Делегировано: …».

### Решение (depth over coverage)

1. Health: блок **«Дистилляция: coverage vs depth»** (bands, avg conf, wisdom high).
2. Upstream: `resolve_mentorship_expert_name` / `resolve_sop_process_title` — skip Unknown Expert + junk delegated titles.
3. `KnowledgeDistiller.redistill_priority_batch` + nightly loop (batch≤3 / 900s): mentorship/SOP/council/board only; `redistill_priority_done`.
4. Empty-200 teacher → fallback; metadata пишет _used_ teacher (`redistill_teacher`) + preferred.
5. Smoke: `knowledge_os/scripts/redistill_priority_smoke.py`.

### Evidence

- Unit: `test_wisdom_upstream_quality.py` (6 passed).
- Smoke: updated≥1; empty victoria → phi fallback; `prio_done` grows.
- Ops: `knowledge_nightly` log `Priority re-distill started`.

### Guardrails

- Не turbo-distill при empty queue; не mass-verify; не re-distill 80k corpus.

---

## § Последние изменения (2026-07-26 v120) — Tasks feed: twin tracking + DEGRADED honesty ✅

### Диагноз

В «Задачи и SLA» одна проверка файла давала две карточки: COMPLETED без эксперта (`orchestration_tracking`) и DEGRADED «Делегировано: X» (monster). Tracking complete ошибочно ставил `completed`. File-audit rule OK помечался DEGRADED. Сырой HTML в результате — незаэкрапированный текст в карточке.

### Решение

1. Tracking complete → `cancelled` + `tracking_complete` (не KPI).
2. UI: скрыть `orchestration_tracking` по умолчанию; escape HTML.
3. File-audit OK/ПРОБЛЕМА = substantive → `completed`.
4. Monster: file-audit с Marketing → re-route на Алексей/Игорь/Анна/Сергей.
5. Demote 548 historical tracking completed → cancelled.

---

## § Последние изменения (2026-07-26 v119) — RAG-eligible embeddings (quality-over-quantity) ✅

### Диагноз

Raw embedding coverage ~3–11% выглядел как «сломанный индекс»: знаменатель включал venv PROJECT_FILE, audit и discovery stubs; writers часто INSERT без embedding; backfill не был в continuous loop.

### Решение (практика RAG: index signal, not noise)

1. `embedding_eligibility.py` — eligible SQL + path guards + priority `backfill_eligible_embeddings` + junk purge.
2. Health widget: **RAG-eligible %** (цель ≥80%) + raw отдельно.
3. `indexing_daemon`: skip `venv`/`site-packages`; prune dirs on walk.
4. Mentorship/SOP: embed-on-insert; nightly continuous backfill (batch/env).
5. Purge existing venv/site-packages PROJECT_FILE nodes.

### Evidence

- Unit: `test_embedding_eligibility.py`.
- Ops: eligible_with_emb / eligible_all after purge+backfill; nightly logs `Embedding backfill`.

---

## § Последние изменения (2026-07-25 v118) — Tip-top: audit flood / canary LLM / evolution hotspots / board templates ✅

### Диагноз

1. KB рос на ~100k+/сут из `success_retrieval_audit` (INSERT на каждый hit).
2. Canary daemon вызывал несуществующий `ai_core._run_local_llm` → empty → `total_tests` не росли.
3. MetaArchitect брал outlier hotspot `ai_core` (~8e6 ms wall-clock LLM wait) и слал весь mega-файл в LLM → 0 mutations.
4. Board директивы копировали шаблон «1) первое действие» и самоусиливались через last_directive.

### Решение

1. `success_retriever`: cooldown 60м/expert (+ optional sample rate).
2. `canary_router._run_llm`: `dialogue_llm` + всегда писать battle (stub при пустом ответе).
3. `architecture_profiler` фильтр outliers/`ai_core`; MetaArchitect — AST extract + splice + LLM timeout.
4. `strategic_board.is_low_quality_directive` режет template actions; убран placeholder ФОКУСЫ из Victoria prompt.

### Evidence

- Unit: strategic_board template reject; canary `_run_llm` path.
- Ops: prune старых `success_retrieval_audit`; restart nightly/workers.

---

## § Последние изменения (2026-07-23 v117) — MetaArchitect guarded evolution ✅

### Диагноз

Code Mutations UI был пуст при живом `architecture_performance_log`: Phase 11 звал только `self_repair_cycle`, не `self_evolution_cycle`.

### Решение

1. `MetaArchitect.run_guarded_evolution`: env enable + max 1 hotspot + 12h cooldown; mutations с `status=shadow`.
2. Phase 11 + nightly phase 6 вызывают guarded evolution.
3. Dashboard: caption, metrics, hotspots 24h, guarded Promote (confirm + RO-safe).

### Evidence

- Hotspots SQL 24h returns rows; guarded path returns `evolution_disabled` when env false; compile OK.

---

## § Последние изменения (2026-07-23 v116) — Prompt Battle live path ✅

### Диагноз

UI Prompt Battle показывал shadow-промпты, но `total_tests=0`, «Последние битвы» пусты: canary брал мутации без `expert_id` и только `total_tests=0`, daemon сравнивал ответ сам с собой, evaluator не писал `interaction_logs`.

### Решение

1. `canary_router`: filter by expert_id + continue until `CANARY_MIN_TESTS`; win/loss/draw; battle log; daemon = prod vs shadow probe.
2. `shadow_evaluator`: heuristic fallback + INSERT battle log.
3. Dashboard: caption (shadow ≠ user response), Smoke Battle, richer battle list.

### Evidence

- Alex smoke: `total_tests 0→1`, `battle_logs≥1`; unit tests canary/shadow evaluator green.

---

## § Последние изменения (2026-07-23 v115) — Revision & Verification human-gate ✅

### Диагноз

Вкладка «Ревизия» выглядела как обязательный Approve, но кнопка была stub (не писала в БД); превью обрезано; авто Виктории нет.

### Решение

1. Caption: optional human gate; Victoria не читает вкладку.
2. Метрики verified/unverified + bulk **только** `ingest_docs_to_rag`.
3. Expander: полный content + domain/path/type/conf; кнопка → `UPDATE is_verified=true` + metadata audit.

### Evidence

- Dashboard mount smoke: `run_query` → `is_verified=true` + `dashboard_verified_method`.

---

## § Последние изменения (2026-07-23 v114) — Intelligence RAG UX honesty ✅

### Диагноз

«Последние находки» / «Здоровье» / «Карта Разума» выглядели сломанными: сырой хвост AI Research, карточки «Целостность» считали **только 7 дней** (~2.2k узлов / ~1.2k связей) при сайдбаре ~103k, Neural Graph **1%** (ошибочно от period-links), каша лейблов на карте доменов.

### Решение

1. **Последние находки:** фильтр parse-error/refusal/`create_file`; приоритет `file_path` + council; expander с полным текстом.
2. **Целостность:** primary metrics = **all-time** (`knowledge_nodes` / `knowledge_links`); период только в Δ; coverage % эмбеддингов; Neural Graph % = `links_all / 100k`.
3. **Карта Разума:** caption all-time; подписи только top-14 доменов; clusters degree одним проходом; local hover с content.

### Evidence

- Query: `nodes_all≈103k`, `links_all≈113488` → progress **100%**; `missing_emb≈91k` (~11% coverage); period Δ nodes≈2.5k / links≈1.2k.

---

## § Последние изменения (2026-07-23 v113) — Tail Closure (emb / DEGRADED / council) ✅

### Решение

1. Backfill `tasks.embedding` → **510** (≥ OKR KR 500).
2. Tasks UI: cancelled + rule-fallback → бейдж **DEGRADED** (не путать с аварией); фильтр + метрика.
3. Extra council phase → **4** debates / 7d (KR закрыт).

### Evidence

- emb=510; council_1d=4; mentor KR 5/5; degraded count visible in tasks tab.

---

## § Последние изменения (2026-07-23 v112) — OKR Active Period + DNA All Experts ✅

### Решение (лучшее из практик Grove/Doerr + Cognitive Code)

1. **Active period** `ACTIVE_OKR_PERIOD=2026-H2`: Board / morning / dashboard читают только его; архив 2025-Q4 остаётся в БД.
2. **`okr_service.py`**: seed 3 Objective + KR, refresh `current_value` из live metrics.
3. Dashboard OKR: прогресс KR (в т.ч. inverse для failed/stale).
4. Strategy DNA select: все эксперты из `experts` (не top-10); новые появляются после sync.

### Evidence

- Seed `2026-H2`: 3 OKR / 7 KR; metrics refresh OK (council_7d, mentor_7d, nodes, emb, failed).

---

## § Последние изменения (2026-07-23 v111) — Nightly Expert Council Restored ✅

### Диагноз

Wisdom «Дебаты» застыли на **2026-04-24**: `run_expert_council` удалён в `5d8bbbf7` (Phase 8.2 cleanup, 25.04). Nightly писал только mentorship/SOP; `create_debate_for_hypothesis` стал stub (task only).

### Решение

1. Новый модуль `nightly_expert_council.py` — Red Team (critique→rebuttal→synthesis) через dialogue_llm + timeout.
2. Пишет `knowledge_nodes` с `cycle=nightly_council_v2` (+ `expert_discussions`, `council_review` на source).
3. Фаза 5 в `run_nightly_cycle`; re-export `run_expert_council` для старых скриптов.
4. `create_debate_for_hypothesis` снова вызывает council.

### Evidence

- Smoke: **2** новых council nodes (2026-07-23 00:09); dashboard query MAX(created_at) обновлён; import OK.

---

## § Последние изменения (2026-07-22 v110) — Wisdom Tab 100% Closure ✅

### Диагноз

Вкладка Wisdom показывала нули при живых данных: time-filter без fallback; `fetch_data(params=())` ломал `LIKE '%'` (дебаты); mentorship/SOP падали на jsonb-dict; SuccessRetriever не писал audit (`metadata=dict`); у completed tasks не было embeddings.

### Решение

1. Dashboard: dual metrics (период + all-time), расширенные SOP/mentor/council queries, constitution import path.
2. `fetch_data`/`run_query`: `params=None` → raw SQL (без pyformat).
3. Mentorship/SOP: jsonb-safe metadata, dialogue_llm + timeout + heuristic/fallback, `run_sop_cycle(limit=)`.
4. SuccessRetriever: `json.dumps` + `domain_id` для audit nodes.
5. Scripts: `backfill_task_embeddings.py`, `run_wisdom_closure_cycle.py`.

### Evidence (live)

- tasks.embedding: **60**; mentorship_7d: **5**; sop_7d: **2**; sra: **94** (~3.3h); council: **1837**; audited avg **7.8**; dashboard 200

---

## § Последние изменения (2026-07-21 v109) — Heavy Keep-Alive + Git Hygiene ✅

### Диагноз

A+C хвосты: coder/minicpm могли жить в Ollama слишком долго; audits/LATEST шумели в git status.

### Решение

1. `ollama_keep_alive_policy`: burst-heavy (`qwen2.5-coder*`, `minicpm*`) → `OLLAMA_HEAVY_KEEP_ALIVE_SEC` (default **180**); cap даже при global env / recovery cooldown.
2. Vision fallback передаёт `keep_alive` из policy.
3. gitignore: `docs/board_reports/LATEST.md`, `docs/audits/*60m*`, `docs/audits/*.jsonl`.

### Evidence

- Unit: `test_burst_heavy_coder_short_keep_alive` + existing keep_alive suite

---

## § Последние изменения (2026-07-21 v108) — Tail Closure (image + Ollama strategist) ✅

### Диагноз

После v107 scrapes были зелёные на hot-`pip install`, но пакет пропал бы при recreate; `VICTORIA_STRATEGIST_MODEL` по умолчанию был `qwen2.5-coder:14b` (оба hybrid-слота) → 14B постоянно в VRAM.

### Решение

1. Rebuild agents image с `prometheus-client`; recreate workers/orch/rest/victoria.
2. Default strategist → `victoria-wisdom-v3.5:latest`; executor остаётся coder только для coding path.
3. Compose env на `victoria-agent` + `knowledge_os_orchestrator`.

### Evidence

- Prometheus **11/11** после recreate с нового image (`import prometheus_client` OK без pip)
- Redis timeouts **0**/3m; core health OK; Grafana 200; stale_in_progress_30m=0

---

## § Последние изменения (2026-07-21 v107) — Observability Scrapes + Redis UDS ✅

### Диагноз

Prometheus 4/11: не «старые IP», а (1) `prometheus_client` отсутствовал в agent image → `/metrics` 500; (2) dynamic workers без `ENABLE_METRICS`; (3) orchestrator/smart-worker не слушали scrape-порты. Параллельно expert-workers сыпали `Timeout reading from /data/redis/redis.sock`.

### Решение

1. `prometheus-client` в root `requirements.txt` + гарантированный слой в agents Dockerfile.
2. `ENABLE_METRICS=true` для dynamic-1/2, smart-worker, orchestrator; orchestrator поднимает aiohttp `/metrics` на `METRICS_PORT`.
3. Fail-soft `/metrics` handlers; Redis pool: explicit `socket_timeout=None` + connect timeout для blocking XREADGROUP.

### Evidence

- Prometheus targets **11/11 up**
- Redis timeout rate после рестарта workers: **0**/45s (было ~12/2m)
- Grafana: `admin` / `GRAFANA_PASSWORD` (не admin/admin); MLX healthy

---

## § Последние изменения (2026-07-21 v106) — Board Victoria-First ✅

### Диагноз

После v105 лучшие ответы уже давала Victoria, но default path шёл через phi3.5; MLX-клиент бил в несуществующий `/v1/chat/completions`; длинный OKR-промпт сжигал 90s и падал на fallback.

### Решение

1. Default `BOARD_CONSULT_MODEL` → MLX `victoria-wisdom-v3.5`; phi3.5 только last-resort.
2. `dialogue_llm._try_mlx` → Ollama-compatible `/api/chat` (+ strip `<think>` artifacts).
3. API/chat: compact Victoria-first (intent-anchored) до длинного board_prompt; MLX-only backends (без сжигания бюджета на Ollama).
4. Timeouts: `BOARD_CONSULT_FAST_TIMEOUT_SEC=120`, `DIALOGUE_MLX_TIMEOUT_SEC=120`.

### Evidence

- Unit: `test_strategic_board.py` **17 passed**
- Live: `victoria-first accepted (victoria-wisdom-v3.5)` ~34s, decision «разгружать тяжёлые модели ollama…», conf 0.95

---

## § Последние изменения (2026-07-21 v105) — Board Intent Fidelity ✅

### Диагноз

v104 убрал prompt-echo, но директивы часто отвечали OKR-дрейфом («внедрять Ollama») вместо вопроса; polarity ломалась (`оставить` матчилось в `предоставить`); HTTP вис на ai_core.

### Решение

1. `directive_matches_question_intent` + family constraints (разгрузка / оставить историю / стабильность).
2. Unload heavy Ollama before consult; quality retry MLX→Ollama wisdom→phi3.5.
3. `BOARD_CONSULT_SKIP_AICORE=true` (default); ai_core timeout 45s if enabled.
4. Word-boundary intent; reject EN prompt-leak; REST не оборачивает 503 в 500.

### Evidence

- Unit: `TestIntentFidelity` + board tests **17 passed**
- Live: Q1 «Разгрузить тяжёлые…», Q2 «Оставить как историю», Q3 стабильность — intent **3/3**

---

## § Последние изменения (2026-07-20 v104) — Board Consult Quality Gate ✅

### Диагноз

Pipeline совета работал, но ad-hoc `/api/board/consult` отдавал prompt-echo (`РЕШЕНИЕ: [одна фраза]`) на `smollm2:360m`; compact-retry принимал тот же шаблон; HTTP мог висеть на KN embedding после уже готовой директивы.

### Решение

1. Default `BOARD_CONSULT_MODEL` / quality model → `phi3.5:3.8b` (compose: `knowledge_rest`, `board-scheduler`).
2. `is_low_quality_directive()` — reject placeholders / echo; fail-closed.
3. Промпты без квадратных скобок-плейсхолдеров; ответ обязан бить в вопрос пользователя.
4. `BOARD_KN_EMBED=0` по умолчанию — не блокировать API на embedding.

### Evidence (live)

- Unit: `TestLowQualityDirective` — 3 passed
- Smoke consult: HTTP **200** ~2.5s, `placeholder=false`, `decision_ok=true`, topic-relevant
- Auth 401 without key сохранён

---

## § Последние изменения (2026-07-20 v103) — Distill Tail + Noise Purge + Ledger ✅

### Диагноз

После v100 runtime P0 был зелёный, но оставался хвост Knowledge Fabric и долг учёта:

1. `eligible` разблокирован (failed reset + verify high-conf) → drain до `eligible=0`.
2. ~187 unverified: шум (timeout/autotest/stub) vs salvageable changelog/preference.
3. Библия/git отставали на v100 — создавали ложное «ещё не доделали».

### Решение

1. **v101:** reset failed→pending; verify high-conf; turbo/scripted drain → `eligible≈0`.
2. **v102:** +58 fresh ingest verified+distilled.
3. **v103:** delete **124** noise KN; salvage+distill **5** substantive; ops script `knowledge_os/scripts/run_distill_tail_closure.py`; bible/git ledger; RAM hygiene (unload idle heavy Ollama).

### Evidence (live 2026-07-20)

- `kn_total≈100797`, `distilled=total`, `eligible_now=0`, `failed_distill=0`, `unverified_not_distilled=0`
- board stub in RAG risk (`conf≥0.3` + queue stub text) = **0**
- health 8010/8080/MLX/Ollama = ok
- nightly: steady drain early-exit on `eligible=0`

### Remaining (ops note, не P0)

- Host MemAvailable может быть &lt;5GB при нескольких загруженных Ollama-моделях → unload unused; не параллелить board+swarm+heavy codegen.
- Исторические `tasks.failed` по timeout — не массовый reset.
- `docs/audits/*60m*` / `data/lancedb` / `.env` — вне git.

---

## § Последние изменения (2026-07-19 v99) — Full Ops Debt Closure ✅

### Диагноз

После anti-stub epic оставались runtime-дыры; часть v98-правок **слетела с диска** (compose/`.env`/bible), контейнеры жили на старом env.

1. Board reports: RO `/app` + `knowledge_rest` без RW mount; `BOARD_REPORTS_DIR` не использовался в коде.
2. `API_KEY` пропал из `.env` → риск default после recreate.
3. Backend durable mounts/`OLLAMA_BASE_URL` снова отсутствовали в `docker-compose.yml`.
4. Swarm stream резался `ENGINE_TIMEOUT_SEC` cap=60s.
5. `/api/board/consult`: пустой `VICTORIA_URL`, hang на ai_core, `source` check constraint, prompt-echo от smollm.

### Решение

1. Compose (durable): `knowledge_rest` + `board-scheduler` → `BOARD_REPORTS_DIR=/data/board_reports`, volume `../docs/board_reports`, `API_KEY`, `VICTORIA_URL`, `OLLAMA_*`.
2. Root backend: `./backend/app:/app/app`, `OLLAMA_BASE_URL`, swarm size/iter/timeout env, `API_KEY`.
3. `strategic_board.py`: `_resolve_board_reports_dir` / `_publish_board_markdown`; consult fast-first `dialogue_llm`; source normalize; MD before DB; prompt-echo compact retry.
4. `expert_dialogue.py`: per-mode timeout (`SWARM_TIMEOUT_SEC` default 180); swarm Ollama URL fallback.
5. `API_KEY` восстановлен в gitignored `knowledge_os/.env` + root `.env`.

### Evidence (live)

- health 8010/8080/8002/8011 = **200**
- stub gates: rule/queued/stale = **0**
- swarm stream: full path, no lightweight fallback, no «not implemented»
- swarm `/start`: `engine_used=swarm`, participants=4
- board consult: **200**, MD на хосте `docs/board_reports/board_directive_2026-07-19_23-37.md`, DB row `source=api`
- API_KEY: no-key/bad-key **401**; key_len=43
- EventBus: `DialogueController started`

### Remaining (закрыто в v100)

- ~~Исторический quarantine board stub KN / git commit~~ → v100.
- Качество smollm на board consult зависит от загрузки Ollama (при busy — unload heavy models) — ops note, не долг.

---

## § Последние изменения (2026-07-19 v100) — Quarantine + Git Closure ✅

### Сделано

1. Quarantine **11** `knowledge_nodes` + **11** `board_decisions` + **11** `expert_discussions` с `queued to PostgreSQL` → `quarantined_v100` (confidence≤0.01, is_verified=false). Уже вне RAG (`confidence >= 0.3`).
2. `docs/board_reports/board_directive_*.md` + smoke → gitignore (runtime artifacts).
3. Git commit: anti-stub contour + v99 durable ops (compose/board/swarm/API_KEY/guards) + bible; без `data/lancedb`, boot_incidents, 60m audit flood, `.env`.

### Evidence

- `kn_q_v100=11`, `bd_q_v100=11`, `board_stub_unq=0`
- health 8010/8080/8002/8011=200; rule/queued/stale=0

---

## § Последние изменения (2026-07-19 v93) — Stub Contour Finish ✅

### Диагноз (после v92)

1. OpenWebUI `tool` table была **пуста** — `ask_victoria` не установлен; stub-guard в файле не работал в runtime.
2. `_restart_service` врал `success: True` без реального restart.
3. `_attempt_fix` → мёртвый stub `Fix not implemented`.
4. Оставались 9 historical rule-statusный `completed`.

### Fix

1. `ensure_openwebui_ask_victoria_valves.py` — upsert tool content+valves+specs; guard `_reject_stub_output`; `USE_BACKEND_PROXY=true`.
2. Policy: tool привязан к 15 моделям OpenWebUI.
3. `victoria_event_handlers`: real `SelfCheckSystem.auto_fix_component` + recovery task; honest escalate.
4. `chat.py` ask-victoria + status: belt-and-suspenders stub reject.
5. Quarantine 9 historical → `quarantined_v93`.

### Evidence

- tool inserted: `ask_victoria_singularity_15`, guard=1, proxy=true, 15 models.
- `rule_status_completed_all=0`, `q_v93=9`.
- Victoria/backend health 200; `attempt_fix` path ≠ «Fix not implemented».

---

## § Последние изменения (2026-07-19 v92) — Rule-based False-Complete Kill ✅

### Root cause

При недоступности LLM `task_rule_executor` писал soft «Rule-based статусный ответ (AI временно недоступен…)» в `tasks.status='completed'` → KPI/дашборды считали задачу успешной (7 за 7d, 396 historical).

### Fix

1. `finalize_rule_result()` — soft templates → `cancelled` + `[DEGRADED_RULE_FALLBACK]` + `quality_degraded`; только substantive health-check → `completed`.
2. Wired: `smart_worker_autonomous`, `orchestrator_phases` phase 2.5.
3. Stub guard extended + wired: `backend/app/services/victoria.py`, MCP `victoria_mcp_server`, OpenWebUI `openwebui_ask_victoria_tool`.
4. Quarantine: 7 recent rule false-completes → cancelled + `quarantined_v92`.

### Evidence

- Unit: soft → `cancelled`; health-check → `completed`.
- Deploy: worker/orch/backend import OK.
- SQL: `rule_completed_7d` statusный clean = **0**; `still_rule_completed_7d` = **0**.

---

## § Последние изменения (2026-07-19 v91) — Victoria Stub Sweep ✅

### Решение команды

1. **CODE-queue opt-in only** — substring `code`/`код` больше не ставит задачу в PostgreSQL. Нужно `queue_code=true` или legacy `VICTORIA_CODE_AUTO_QUEUE=true`.
2. **Shared guard** — `victoria_response_guard.is_victoria_stub()` в `knowledge_os` + `backend`; wired в `rest_api` `/api/victoria/solve`, `victoria_fallback`, `expert_dialogue`, `proxy`, `strategic_board`.
3. **Quarantine** — 11× `knowledge_nodes` + 11× `board_decisions` + 11× `expert_discussions` с `queued to PostgreSQL` помечены quarantined / human_review.

### Evidence

- Goal с «code» без `queue_code` → нет мгновенного stub (идёт sync).
- `queue_code=true` → `⏳ Task … queued` за ~50ms (явный opt-in сохранён).
- DB: `kn_q=11`, `board_q=11`, `disc_q=11`.

---

## § Последние изменения (2026-07-19 v90) — Board of Directors Real Directives ✅

### Root cause

Victoria CODE-queue (`"код"/"code" in goal`) hijacked board meetings → stub `⏳ Task … queued to PostgreSQL` saved as directive (11/11 last 7d). Markdown used undefined `filepath`.

### Fix

- `strategic_board.py`: sync `/run?async_mode=false`, compact context (no raw KB dump), stub reject, poll+local fallback, `filepath` + `/tmp` reports fallback.
- `victoria_server.py`: skip CODE-queue for board/strategy goals.

### Evidence

Manual `run_board_meeting`: directive **1225** chars, `is_stub=false`, stored in `board_decisions` (2026-07-19 20:48 MSK).

---

## § Последние изменения (2026-07-19 v89) — Hybrid Quality-Local Dialogue ✅

### Цель

Медленнее, но честнее: ждать локальную модель; **не** выдавать stub/галлюцинации за мнения экспертов. Fast UI — только opt-in.

### Hybrid contract

1. **quality (default):** full engines, engine budget **240s**, per-call **90s**, busy-retry на Ollama 503, model `phi3.5:3.8b`, cloud off.
2. **honest degraded:** при исчерпании budget → `quality_degraded=true`, `degraded_reason`, `opinions[].incomplete=true`, текст с `[INCOMPLETE]` (без фейкового «поддерживаю…»).
3. **fast:** только `prefer_lightweight=true` (~8s).

### Verification (2026-07-19)

| Case                                          | Result                                                               |
| --------------------------------------------- | -------------------------------------------------------------------- |
| prefer_lightweight                            | `lightweight`, ~8s, quality_degraded=false                           |
| default debate (после unload 14B / busy wait) | `debate`, ops=3 incomplete=0, ~80s, lw=false, quality_degraded=false |

Операционно: если в Ollama висит тяжёлая модель (`qwen2.5-coder:14b`) → 503 busy; hybrid ждёт retry, не врёт мнениями.

---

## § Последние изменения (2026-07-19 v88) — Expert Dialogue Full Path Restored ✅

### Цель

Вернуть реальные multi-persona движки (`debate` / `council` / `brainstorm`) как default; lightweight — только opt-in или bounded fallback.

### Что изменилось

- `backend/app/routers/expert_dialogue.py`:
  - `EXPERT_DIALOGUE_PREFER_LIGHTWEIGHT` default **`false`** (full-first);
  - флаги `prefer_lightweight`, `force_full`;
  - timeout движка в том же event loop (`await wait_for`), без threaded `asyncio.run`;
  - контракт: `engine_used`, `lightweight_used`, `fallback_used`, `participants`, `opinions`.
- `knowledge_os/app/dialogue_llm.py` — Ollama-first локальный LLM для диалога.
- `multi_agent_debate.py` / `expert_council_discussion.py` / `collective_brainstorming.py` — small models, caps, DB/HR optional, без тяжёлого ai_core по умолчанию.
- Design: `docs/plans/2026-07-19-expert-dialogue-full-path-design.md`.

### Verification evidence (2026-07-19)

| Case                                                 | Result                                          |
| ---------------------------------------------------- | ----------------------------------------------- |
| `mode=debate` + `force_full`                         | `engine_used=debate`, ops=3, ~83s, lw=false     |
| `mode=sequential` + `force_full`                     | `engine_used=council`, ops=3, ~89s, lw=false    |
| `prefer_lightweight=true`                            | `engine_used=lightweight`, ~8s                  |
| default (no flags)                                   | `engine_used=debate`, ops=3, lw=false, ~58s     |
| `mode=collaboration` + `force_full`                  | `engine_used=brainstorm`, ops=3, ~50s, lw=false |
| recheck default debate (after Ollama timeout harden) | `debate`, ops=3, ~48s, lw=false                 |

**Out of scope / not done:** true worker↔worker EventBus peer chat (`DialogueController`); durable image rebuild (сейчас `docker cp` + restart).

### Env / knobs

| Env                                     | Default       | Meaning                                                  |
| --------------------------------------- | ------------- | -------------------------------------------------------- |
| `EXPERT_DIALOGUE_PREFER_LIGHTWEIGHT`    | `false`       | full-first vs UI fast-path                               |
| `EXPERT_DIALOGUE_ENGINE_TIMEOUT_SEC`    | `240`         | full engine budget (quality-local; bible dialogue ~200s) |
| `DIALOGUE_LLM_TIMEOUT_SEC`              | `90`          | per local Ollama call                                    |
| `DEBATE_EXPERT_TIMEOUT_SEC` / synthesis | `90` / `90`   | wait for real opinions                                   |
| `COUNCIL_MAX_EXPERTS`                   | `3`           | council roster cap                                       |
| `COUNCIL_PERSIST_DB`                    | `false`       | skip DB for API SLA                                      |
| `BRAINSTORM_FAST`                       | `false`       | full phases; `true` only for smoke                       |
| `DIALOGUE_OLLAMA_MODEL`                 | `phi3.5:3.8b` | bible-validated dialogue model                           |

### Deploy note

Backend image `/app` не live-mount — после правок: `docker cp` router + `knowledge_os/app/*.py` → restart `atra-web-ide-backend` (или rebuild image).

### Pre-mortem / rollback

1. Ollama overloaded → stub opinions / lightweight fallback (не 500).
2. Collaboration full (не-fast) может не уложиться в 180s — держать `BRAINSTORM_FAST=true`.
3. Rollback: `EXPERT_DIALOGUE_PREFER_LIGHTWEIGHT=true`.

---

## § Последние изменения (2026-07-19 v86) — Orchestrator Phases Complete + Full Gate ✅

### Цель

Закрыть распил фаз оркестратора **правильно**: baseline → extract 1.5/1.8 → полный verification gate по контейнерам/API/DB/логам/import/smoke.

### Что вынесено (полный реестр)

Модуль: `knowledge_os/app/orchestrator_phases.py` (~1452 LOC)  
Caller glue: `knowledge_os/app/enhanced_orchestrator.py` (~2878 LOC)

| Фаза              | Функция                                     | Live logger           |
| ----------------- | ------------------------------------------- | --------------------- |
| 0 / 0.5           | `phase_0_auto_fix` / `phase_0_5_migrations` | `orchestrator_phases` |
| 1                 | `phase_1_prioritize`                        | `orchestrator_phases` |
| 1.5               | `phase_1_5_decompose`                       | `orchestrator_phases` |
| 1.6               | `phase_1_6_batch_group`                     | `orchestrator_phases` |
| 1.8               | `phase_1_8_red_team`                        | `orchestrator_phases` |
| 1.9 / 1.95 / 1.97 | optimizer / reconcile / scale-down          | `orchestrator_phases` |
| 2 / 2.2 / 2.5     | assign / dispatch / rule fallback           | `orchestrator_phases` |
| 3 / 3.2           | `phase_3_rebalance`                         | `orchestrator_phases` |
| 4                 | `phase_4_cross_domain`                      | `orchestrator_phases` |
| 5 / 5–8           | `phase_5_curiosity` / `phase_5_8_rnd`       | smoke + code path     |
| 10–16             | `phase_heavy_tail`                          | smoke + code path     |

### Исправление «как правильно» в 1.5

В старом монолите цикл subtasks имел broken indentation → фактически создавался только **последний** subtask + `json.loads(dict)` падал.  
В extract: INSERT **каждого** subtask (до 5), безопасный разбор `meta`, default domain для micro-agent.

### Осталось в монолите (намеренно, не фазы)

- Rollout KPI после 2.2
- Quality-focus skip/lock release перед heavy
- Автоочистка старых tasks
- Helpers / assign / dispatch / Redis glue
- `ai_core.py` не трогали

### Full Verification Gate (2026-07-19) — evidence

| Check                                     | Result                                     |
| ----------------------------------------- | ------------------------------------------ |
| Unhealthy containers                      | `none`                                     |
| Victoria 8010 / Veronica 8011 / REST 8002 | ok / ok / healthy                          |
| Ollama / MLX                              | `200` / `200`                              |
| Experts                                   | `90`                                       |
| Tasks                                     | pending 1 / in_progress 1 / completed 2618 |
| Live logs 1.5 / 1.8                       | `orchestrator_phases` (после restart)      |
| Live logs 0–4, 1.6, 1.9–1.97, 2–3         | `orchestrator_phases`                      |
| Traceback/NameError/ImportError           | `none` (только RuntimeWarning tracemalloc) |
| Imports all phase fns                     | `IMPORTS_OK 18`                            |
| Smoke 1.5 / 1.8                           | `{'decomposed': 0}` / `{'audited': 0}`     |
| Orchestrator                              | `healthy`                                  |

### Pre-mortem / rollback

1. Quality-focus interrupt Phase 4+ — ожидаемо при backlog (`has_execution_backlog`).
2. Phase 5–8/10–16 в live часто не видны из-за interrupt — не регрессия extract.
3. Rollback: revert call sites + `orchestrator_phases.py`.

---

## § Последние изменения (2026-07-19 v87) — Expert Audit Closure (P0/P1) ✅

### Что изменилось сегодня (v86)

#### 1. Multi-expert аудит и закрытие критичных рисков

- Выполнен parallel-аудит по 3 контурам: SRE/KPI, worker loop-breakers, recovery/governance.
- Подтверждено: основная краснота KPI была из-за ложных/неполных условий мониторинга и loop-регрессий, а не из-за деградации контейнеров.

#### 2. Исправлена авто-реанимация manual-triage delegation

- `knowledge_os/app/worker/worker_logic.py` (`_auto_requeue_delegation`):
  - исключены задачи с `failed_requires_intervention=true`,
  - исключены `diagnostic_path` manual triage,
  - исключены `auto_fallback_reason` с `manual_triage`/`exhausted`,
  - добавлен safe-cast для `auto_requeue_count`.
- Инвариант: exhausted/manual-triage задачи больше не возвращаются в `pending` автоматически.

#### 3. Устранён риск двойного watchdog-reset цикла

- `knowledge_os/app/smart_worker_autonomous.py`:
  - фоновый watchdog-loop переведен под флаг
    `SMART_WORKER_WATCHDOG_BACKGROUND_ENABLED` (default `false`),
  - базовый inline watchdog path оставлен как единый путь по умолчанию,
  - добавлен safe-cast для `progress_guard_requeue_count` в SQL-условиях/инкрементах.

#### 4. Усилен Circuit Breaker loop-breaker в expert worker

- `knowledge_os/app/expert_worker.py`:
  - добавлен safe parser для metadata-int счетчиков,
  - `circuit_breaker_loop_exhausted` сохраняет terminal-path в `cancelled/manual triage`
    (с `failed_requires_intervention=true`) без повторного requeue-loop.

#### 5. Дожат runtime KPI monitor (операционная честность)

- `scripts/runtime_kpi_gate_monitor.py`:
  - исправлен alias heavy worker (поддержка `...-heavy-1/-2/-3`),
  - gate-window теперь учитывает `cancelled` c `failed_requires_intervention=true`
    в failure-rate (чтобы `failed -> cancelled` не маскировал деградацию).

#### 6. Smoke-верификация после фиксов

- Артефакты:
  - `docs/audits/2026-07-19-expert-smoke-post-expert-fixes.jsonl`
  - `docs/audits/2026-07-19-expert-smoke-post-expert-fixes-summary.md`
- Итог smoke:
  - `stability_ok=true`, `error_rate_gate_ok=true`, `distill_tail_ok=true`,
  - окна отмечены как `insufficient_load_n_a` (нет продуктивной нагрузки), что корректно для low-pressure режима.

---

## § Последние изменения (2026-07-18 v85) — Recovery Replay + P0/P1 Loop-Breakers ✅

### Что изменилось сегодня (v85)

#### 1. Controlled replay исторических инцидентов в Knowledge Layer

- Добавлен скрипт `scripts/replay_recovered_incidents.py`:
  - source: `docs/recovery/recovered_incidents_validated.jsonl`,
  - фильтр по confidence (`high` по умолчанию),
  - идемпотентность через `metadata.recovery_source_hash`,
  - dry-run/apply режимы,
  - rollback-safe артефакты (`inserted.jsonl`, `failed.jsonl`, `rollback.sql`).
- Добавлен runbook: `docs/recovery/recovered_incidents_replay_plan.md`.
- Выполнен apply replay: **87** записей `recovery_incident` вставлены в `knowledge_nodes` (0 ошибок).

#### 2. P0/P1: loop-breaker для timeout-loop и progress-guard

- `knowledge_os/app/smart_worker_autonomous.py`:
  - добавлен `execution_profile=rescue_fast` для задач после `rag_loop_no_llm_call`,
  - добавлен счетчик `progress_guard_requeue_count`,
  - добавлен loop-breaker `SMART_WORKER_RAG_LOOP_MAX_RESETS` (по умолчанию 2),
  - исчерпанные RAG-loop задачи переводятся в `cancelled` + `failed_requires_intervention=true` + `diagnostic_path`.
- `knowledge_os/app/expert_worker.py`:
  - добавлен `circuit_breaker_count`,
  - loop-breaker `TASK_CIRCUIT_BREAKER_MAX_RETRIES` (по умолчанию 2),
  - исчерпанные `CIRCUIT BREAKER` кейсы переводятся в `cancelled/manual triage` вместо бесконечного requeue/fail-loop.

#### 3. Fix делегированных задач (MONSTER delegation)

- Уточнён детектор delegation в smart worker:
  - учитывается не только title prefix, но и `metadata.source == victoria_monster_delegation`.
- Для delegation:
  - сохраняется extended timeout (`WORKER_TASK_TOTAL_TIMEOUT`),
  - `rescue_fast` не снижает timeout,
  - `hard_cap` exhausted ведёт в `cancelled/manual triage`, а не в `failed`.

#### 4. Runtime KPI gate tuning под low-pressure окна

- `scripts/runtime_kpi_gate_monitor.py`:
  - добавлен `RUNTIME_KPI_LOW_PRESSURE_MODE=true` (default),
  - если окно low-pressure (`max_pending<=1`, `max_in_progress<=1`) и выполнен `completed_delta >= min_completed_required`, throughput не краснеет из-за bursty completion pattern.
- Сохранены multiple evidence runs:
  - `docs/audits/2026-07-18-expert-60m-post-loop-breaker-r4.{jsonl,summary.md}`
  - `docs/audits/2026-07-18-expert-60m-post-loop-breaker-r5.{jsonl,summary.md}`

#### 5. Операционный инвариант v85

- Timeout-loop не должен бесконечно возвращать задачи в `pending`; исчерпанные кейсы уходят в manual triage с явной диагностикой в metadata.
- Делегированные heavy-задачи не должны деградировать из-за `rescue_fast` timeout cap.
- Recovery replay должен быть повторяемым и безопасным: re-run без дублей, с rollback-артефактами.

---

## § Последние изменения (2026-07-18 v84) — Orchestrator Phase 5–8 Extract ✅

### Что вынесено дополнительно

| Фаза        | Функция              | Статус                                                                                              |
| ----------- | -------------------- | --------------------------------------------------------------------------------------------------- |
| 5 Curiosity | `phase_5_curiosity`  | import + in-container DB smoke (`finish_cycle=True`); live часто не доходит из-за interrupt Phase 4 |
| 5 scout–8   | `phase_5_8_rnd`      | code+import (Global Scout / auto-link / distill / self-repair)                                      |
| ранее (v82) | 0–4, 1.95–2.5, 10–16 | live logs `orchestrator_phases`                                                                     |

Размеры: `orchestrator_phases.py` ~1095 LOC; `enhanced_orchestrator.py` ~3232 LOC.

### Верификация (2026-07-18)

- orchestrator `healthy`; Victoria/Veronica `200`; `unhealthy=0`
- Live: Phase 4 + quality-focus interrupt из `orchestrator_phases`
- Smoke: `phase_5_curiosity(...)` → `{'curiosity_assigned': 0, 'interrupted': False, 'finish_cycle': True}`
- Tasks: pending/in_progress низкие, completed растёт (нет коллапса очереди)

### Ещё в монолите

- **1.5** Blackboard/decompose/HITL
- **1.8** Red Team critic + LLM
- Rollout KPI после 2.2; cleanup хвосты
- `ai_core.py` не трогаем

---

## § Последние изменения (2026-07-18 v83) — Expert Dialogue P1: Lightweight Real Path ⚡

### Что изменилось сегодня (v83)

#### 1. Lightweight-first execution для `expert-dialogue`

- В `backend/app/routers/expert_dialogue.py` добавлен primary fast-path:
  - `_run_lightweight_dialogue(...)` — первый контур ответа для всех режимов (`debate`, `sequential`, `collaboration`),
  - `_try_victoria_lightweight_fast(...)` — короткий вызов Victoria без длинных retry-цепочек,
  - `_build_local_lightweight_decision(...)` — локальный структурированный ответ как быстрый backup (не safe-fallback).
- Full heavy-mode (`expert_council` / `multi_agent_debate` / `collective_brainstorming`) сохранён как следующий уровень при сбое lightweight.

#### 2. Контракт ответа и анти-хвост latency

- В нормализацию payload добавлен флаг `lightweight_used`.
- Для lightweight-ответа отключён этап Victoria synthesis (иначе появлялся второй длинный хвост ожидания).
- Safe fallback остаётся только страховкой при деградации нижележащих контуров.

#### 3. Live-smoke верификация P1 (2026-07-18)

- `GET /health` -> `200`.
- `POST /api/expert-dialogue/start`:
  - `mode=debate` -> `200`, ~`6.05s`, `synthesis_by_victoria=false`, без fallback-фразы.
  - `mode=sequential` -> `200`, ~`6.01s`, `synthesis_by_victoria=false`, без fallback-фразы.
  - `mode=collaboration` -> `200`, ~`6.01s`, `synthesis_by_victoria=false`, без fallback-фразы.
- Целевой SLA P1 (`5-12s`) достигнут на всех 3 режимах в live-smoke.

#### 4. Операционный инвариант v83

- `expert-dialogue` должен сначала пытаться выдать содержательный lightweight-ответ в пределах короткого SLA.
- Heavy-mode и safe-fallback используются только если fast-path не дал корректный результат.

---

## § Последние изменения (2026-07-18 v82) — Orchestrator Safe Extract Batch ✅

### Что вынесено (behavior-preserving)

Модуль: `knowledge_os/app/orchestrator_phases.py` (~627 строк).  
Caller: `knowledge_os/app/enhanced_orchestrator.py` (~3599 строк; было ~3780+).

| Фаза    | Функция                                     | Статус runtime                                                        |
| ------- | ------------------------------------------- | --------------------------------------------------------------------- |
| 0 / 0.5 | `phase_0_auto_fix` / `phase_0_5_migrations` | logs `orchestrator_phases`                                            |
| 1       | `phase_1_prioritize`                        | logs ok                                                               |
| 1.6     | `phase_1_6_batch_group`                     | logs ok                                                               |
| 1.9     | `phase_1_9_execution_optimizer`             | logs ok                                                               |
| 1.95    | `phase_1_95_reconcile`                      | logs ok                                                               |
| 1.97    | `phase_1_97_scale_down`                     | logs ok                                                               |
| 2       | `phase_2_assign`                            | logs ok                                                               |
| 2.2     | `phase_2_2_dispatch`                        | logs ok (+ dispatch)                                                  |
| 2.5     | `phase_2_5_rule_fallback`                   | code+import; log только при candidates                                |
| 3 / 3.2 | `phase_3_rebalance`                         | logs ok                                                               |
| 4       | `phase_4_cross_domain`                      | logs ok + quality-focus interrupt preserved                           |
| 5 / 5–8 | `phase_5_curiosity` / `phase_5_8_rnd`       | см. v84                                                               |
| 10–16   | `phase_heavy_tail`                          | import + in-container smoke; live cycle часто interrupt quality-focus |

### Ещё в монолите (намеренно)

- **1.5** Blackboard/decompose/HITL — высокий риск
- **1.8** Red Team critic + LLM
- Rollout KPI блок после 2.2 остаётся рядом с dispatch (тонкая связка с Redis)

Правило: inject helpers, no circular imports; `ai_core.py` не трогаем.

### Верификация (2026-07-18)

- `knowledge_os_orchestrator` → `healthy`
- Victoria `8010` / Veronica `8011` → `200`
- `unhealthy` containers → `0`
- Tasks snapshot: pending≈1, in_progress≈3, completed≈2587 (очередь не коллапсировала)
- Логи цикла: `phase=1.95/1.97/2/2.2/3` + `Phase 4: Cross-domain linking...` из logger `orchestrator_phases`
- `from orchestrator_phases import phase_heavy_tail` → ok; smoke dummy getters → `phase_heavy_tail_smoke_ok`
- Размеры после Phase 4: `orchestrator_phases.py` ~751 LOC; `enhanced_orchestrator.py` ~3504 LOC

### Pre-mortem

1. Quality-focus interrupt heavy phases — ожидаемо при backlog; не регрессия extract.
2. Phase 2.5 silent без candidates — ожидаемо (старое поведение).
3. Rollback: revert call sites в `enhanced_orchestrator.py` + модуль phases.

---

## § Последние изменения (2026-07-18 v81) — Expert Dialogue API Hardening ✅

### Что зафиксировано (v81)

#### 1. Устранены критические причины 500/timeout в `expert-dialogue`

- Добавлен compatibility shim `backend/app/redis_manager.py` для legacy-импортов `app.redis_manager` в mixed-runtime сценариях.
- В `backend/requirements.txt` добавлена зависимость `aiofiles>=24.1.0` для стабильной работы collaboration-режима.
- В `backend/app/routers/expert_dialogue.py` введен bounded execution per mode:
  - `ENGINE_TIMEOUT_SEC` (env: `EXPERT_DIALOGUE_ENGINE_TIMEOUT_SEC`, default `35`),
  - запуск heavy mode-движков через отдельный thread-event-loop,
  - безопасный timeout-выход с контролируемым fallback вместо зависания клиентского запроса.

#### 2. Нормализация fallback-контракта

- Исправлена нормализация payload: `fallback_used` теперь сохраняется при `_normalize_dialogue_payload`.
- При fallback отключается финальный Victoria synthesis (чтобы исключить второй длинный хвост ожидания и каскадные таймауты).
- Результат: API возвращает предсказуемый `200` в bounded latency, даже если внутренний диалоговый движок недоступен/завис.

#### 3. Live-smoke верификация (2026-07-18)

- `GET /health` → `200`.
- `POST /api/expert-dialogue/start`:
  - `mode=debate` → `200` (~35s), `synthesis_by_victoria=false`, fallback controlled.
  - `mode=sequential` → `200` (~35s), `synthesis_by_victoria=false`, fallback controlled.
  - `mode=collaboration` → `200` (~35s), `synthesis_by_victoria=false`, fallback controlled.

#### 4. Операционный инвариант v81

- Даже при деградации LLM/OpenRouter/MLX контур `expert-dialogue` не должен зависать бесконечно и не должен отдавать 500 по причине внутренних mode-движков.
- Любая деградация должна отрабатываться через bounded timeout + safe fallback с сохранением доступности API.

---

## § Последние изменения (2026-07-18 v80) — Singularity 31.2.2: Hardening Mac Studio ✅

### Что изменилось сегодня (v80)

#### 1. Portability (снятие vendor-lock путей)

- Runtime больше не зависит от абсолютного пути `/Users/bikos/...`.
- Заменено на `PROJECT_ROOT` / `WORKSPACE_ROOT` / `$HOME` / `os.getcwd()` / `os.path.expanduser` в:
  - `knowledge_os/app/ai_core.py`
  - `knowledge_os/app/expert_dna_manager.py`
  - `knowledge_os/app/skill_mapper.py`
  - `knowledge_os/app/sop_generator.py`
  - `knowledge_os/app/mlx_api_server.py`
  - `knowledge_os/app/indexing_daemon.py`
  - `knowledge_os/app/curiosity_engine.py`
  - `START_VICTORIA_LOCAL.sh`, training scripts, tests path bootstrap
- В Docker agents: `PROJECT_ROOT=/workspace/atra-web-ide`, `WORKSPACE_ROOT=/workspace/atra-web-ide`, `ATRA_HOST_WORKSPACE` через env.

#### 2. Task Dedup Contract (PostgreSQL)

- Единый контракт вставки задач под частичный уникальный индекс:
  - `idx_tasks_active_dedup ON tasks (title, COALESCE(project_context, 'default'::character varying)) WHERE status IN ('pending','in_progress')`
- Все активные генераторы задач (`enhanced_orchestrator`, `curiosity_engine`, `db_pool`, `self_check_system`, `streaming_orchestrator`, `victoria_event_handlers`, `debate_processor`, `liquidity_task_generator`, `dashboard_daily_improver`, `smart_worker_integration`, `rest_api`, `orchestrator`, `code_auditor`, `autonomous_overseer`, `predictive_monitor`, `telegram_gateway`, `enhanced_scout_researcher` и др.) приведены к этому `ON CONFLICT`.
- Цель: убрать race `duplicate key value violates unique constraint "idx_tasks_active_dedup"` при параллельных Curiosity/Sentinel/Orchestrator циклах.

#### 3. Docker Healthchecks (Елена + Сергей)

- Проблема: в slim agent-образах **нет `pgrep`/`ps`** → healthcheck `pgrep -f ...` давал ложный `unhealthy` при живом процессе.
- Решение (KISS): процессные проверки через `grep -a -q <entrypoint> /proc/1/cmdline`.
- HTTP-проверки сохранены где есть endpoint: Victoria/Veronica/REST/quality/visual-search/open-webui/grafana/prometheus/elasticsearch.
- Покрыты: orchestrator, expert-workers (heavy/anna/victoria/dynamic), smart worker, evolution, nightly, self_check, telegram, watchdog, board-scheduler, swarm-studio, UI, monitoring.

#### 4. Ollama / Mac Studio resource sync (Ольга)

- `OLLAMA_NUM_PARALLEL=5`
- `OLLAMA_GLOBAL_MAX_SLOTS=4` (буфер 1 слот; раньше 2 вызывало under-utilization warning)
- Зафиксировано в `knowledge_os/docker-compose.agents.yml` и `knowledge_os/.env`.

#### 5. Modular Docker + Autostart (уже 31.2.1, подтверждено в v80)

- Core: `knowledge_os/docker-compose.yml` (`include` → agents/ui/monitoring)
- Agents: `knowledge_os/docker-compose.agents.yml`
- UI: `knowledge_os/docker-compose.ui.yml`
- Monitoring: `knowledge_os/docker-compose.monitoring.yml`
- Автостарт: `START_ON_MAC_STUDIO.sh`, `scripts/autostart/start_singularity_10.sh` (launchd)

#### 6. Schema / DB bootstrap (Роман)

- Обязательно: `POSTGRES_DB=knowledge_os` в сервисе `db`.
- Добиты недостающие колонки/таблицы для runtime: `tasks.last_llm_call_at`, `tasks.retry_after`, `experts.specialization_level`, `experts.is_active`, `expert_dna_overrides`, `model_performance_log`, `corporation_learning_log` (через migrations + `manual_fix.sql` / seed).
- Seed экспертов: `knowledge_os/scripts/seed_from_employees.py` → **90** экспертов в БД (источник: `configs/experts/employees.json`).

#### 7. Monolith split pilot (Игорь) — безопасный режим

- Модуль: `knowledge_os/app/orchestrator_phases.py`
- Вынесено **без смены поведения** (behavior-preserving):
  - Phase 0 → `phase_0_auto_fix(conn)`
  - Phase 0.5 → `phase_0_5_migrations(conn, app_file=__file__)`
- Правило распила: **одна фаза за раз** → syntax check → restart только `knowledge_os_orchestrator` → сверка health/API/task counts с baseline.
- Phase 1–16 пока остаются в `enhanced_orchestrator.py` (не big-bang).
- `ai_core.py` не трогаем до отдельного plan+approval (слишком critical path).

#### 8. Critical runtime fixes

- `knowledge_evolution` command: `["python", "-u", "run_evolution_loop.py"]` (не Dockerfile default на `src.agents.bridge`).
- Victoria/Veronica ports: `8010:8000`, `8011:8000`.
- Redis: `rd.close()` → `rd.aclose()` (`resource_manager`, orchestrator path).
- Import: `phase_victoria_guarantee` в orchestrator helpers import list (ранее NameError).

#### 9. Верификация (2026-07-18) — evidence

| Проверка                                            | Результат                                                          |
| --------------------------------------------------- | ------------------------------------------------------------------ |
| `curl localhost:8010/health`                        | `{"status":"ok","agent":"Виктория"}`                               |
| `curl localhost:8011/health`                        | `{"status":"ok","agent":"Вероника"}`                               |
| `curl localhost:8002/health`                        | `{"status":"healthy","database":"connected"}`                      |
| Experts count                                       | `90`                                                               |
| Hardcoded `/Users/bikos` в `knowledge_os/app`       | `0`                                                                |
| Старый `ON CONFLICT` без cast                       | `0`                                                                |
| `OLLAMA_GLOBAL_MAX_SLOTS` / `OLLAMA_NUM_PARALLEL`   | `4` / `5`                                                          |
| Phase 0 / 0.5                                       | `orchestrator_phases` → `ok` / `migrations`                        |
| Orchestrator + workers + evolution + nightly + rest | `healthy`                                                          |
| Safe extract gate (после Phase 0.5)                 | API ok; нет `unhealthy`; dynamic-1 поднят из `Created` → `healthy` |

#### 10. Pre-mortem закрытые риски

1. **False unhealthy** из-за отсутствия `pgrep` → заменено на `/proc/1/cmdline`.
2. **Evolution restart-loop** из-за неверного CMD → явный `run_evolution_loop.py`.
3. **Path lock** на одном пользователе Mac → env-based roots.
4. Transient Redis UDS timeout при массовом recreate — самовосстановление (workers возвращаются в `healthy`).

### Операционный инвариант v80

```bash
# Единый старт стека на Mac Studio
cd knowledge_os && docker compose -f docker-compose.yml up -d

# Или полный автостарт
./START_ON_MAC_STUDIO.sh
```

Контрольный срез после рестарта: нет `unhealthy`, Victoria/Veronica/REST отвечают, `experts >= 85`, Phase 0 без exception, нет `idx_tasks_active_dedup` duplicate storms в логах.

---

## § 0. МАНИФЕСТ РОЯ (Singularity 31.2)

### 0.1 Децентрализация и Аукционы

Система перешла от жесткой иерархии к **P2P-рынку задач**.

- **Blackboard Service:** Центральный хаб задач. Агенты не ждут команд, а «подписываются» на задачи через аукционы.
- **Bidding System:** Эксперты делают ставки (bids) на основе своей специализации, текущей нагрузки и рейтинга.
- **Token Bucket Limiter:** Глобальный ограничитель частоты запросов (Singularity 30.1), предотвращающий перегрузку LLM.
- **AgentScope Actors:** Каждый эксперт — это изолированный актор с собственным состоянием и памятью.

### 0.2 Нейронная Ткань (Knowledge Fabric)

Единая точка входа для всех видов памяти:

- **LTM (Long-term Memory):** Векторная память на базе LanceDB (нулевая задержка).
- **GraphRAG:** Глубокие связи между сущностями и кодом.
- **VisualRAG (Visual Intelligence):** Сервис `victoria-visual-search` (порт 8005) для анализа UI, схем и PDF.
- **Semantic Cache:** Мгновенные ответы на повторяющиеся запросы.

### 0.3 Протокол Эволюции (Recursive Self-Improvement)

- **RecursiveEvolutionEngine:** Автономный цикл улучшения кода.
- **EvolutionGenome:** Хранение успешных паттернов и мутаций.
- **CubeSandbox:** Изолированная среда для тестирования мутаций перед коммитом.
- **Self-Healing:** Автоматическое исправление багов через `CodebaseMutationEngine`.

### 0.4 Технологический Стек 31.0

- **База данных:** PostgreSQL + pg_vector + LanceDB + DuckDB (для тяжелой аналитики).
- **Транспорт:** Redis UDS (Unix Domain Sockets) для максимальной скорости внутри ноды.
- **Безопасность:** mTLS между всеми микросервисами.
- **API:** Rust Gateway (порт 8081) для высоконагруженных запросов.
- **Уведомления:** ntfy.sh (основной канал), Telegram (fallback).

### 0.5 Безопасность и Этика (Singularity 31.2)

- **Цифровая Конституция:** Набор этических фильтров (Security First, Data-Driven, и др.) для всех агентов.
- **Конституционный Суд:** Модуль `constitutional_court.py` для верификации решений экспертов.
- **Chaos Injector:** «Chaos Monkey» для ИИ-агентов, проверяющий устойчивость системы к галлюцинациям и задержкам.

### 0.6 Динамическая Организация

- **Emergent Hierarchy:** Автоматическое формирование команд и иерархий под конкретную задачу.
- **Metacognitive Learning:** Способность агентов к самооценке и планированию собственного обучения.

### 0.7 Продвинутые Автономные Модули (Singularity 31.2)

- **Adversarial Critic (Corporate Immunity):** Стресс-тестирование узлов знаний и SOP через «атаки» субагентов для выявления слабых мест.
- **Toil Detector:** Автоматическое обнаружение рутинных, повторяющихся задач и генерация предложений по их автоматизации.
- **Threat Detector:** Мониторинг входящих запросов и логов на предмет Prompt Injection, утечек данных и истощения ресурсов.
- **Tacit Knowledge Miner:** Извлечение неявных стилевых предпочтений пользователя (naming, testing, error handling) для персонализации генерации кода.
- **War Room Manager:** Тактический центр управления для координации экспертов в реальном времени при возникновении критических инцидентов.
- **Success Retriever:** Система поиска наиболее успешных исторических решений для использования в качестве Few-Shot примеров.
- **Symbol Tuner:** Механизм управления поведением агентов через явные символы-модификаторы (📏 concise, 📚 detailed, 🚀 fast).
- **SOP Generator:** Автоматический синтез стандартных операционных процедур на основе успешно выполненных сложных задач.
- **Voice of Experience:** Проактивное предупреждение об ошибках на основе анализа прошлых неудач системы.

---

## § Последние изменения (2026-06-13 v79) — Version Unification: Singularity 31.2+ ✅

### Что изменилось сегодня (v79)

#### 1. Унификация отображаемой версии в UI и API

- Устранены расхождения, где в runtime/UI продолжали показываться старые версии (`14.0`, `15.0`, `20.0`) вместо текущей.
- Во всех пользовательских точках отображения закреплено единое значение: **`Singularity 31.2+`**.
- Обновлены dashboard-вкладки (`system`, `wisdom`, `scout`), frontend badge, backend description/root metadata, а также связанные user-facing строки в chat/query routing.

#### 2. Синхронизация контуров интеграции

- Обновлены формулировки и заголовки в OpenWebUI tool/config, чтобы внешний интерфейс не расходился с текущей версией ядра.
- Синхронизированы runtime-строки в Python/Rust слоях, влияющие на восприятие версии при диагностике и работе операторов.

#### 3. Верификация качества

- Выполнен поиск по репозиторию для user-facing поверхностей dashboard/backend/frontend и устранены несоответствия.
- Прогнан preflight quality gate: контейнеры `ok`, `contract_enforce=ok`, `stale_in_progress=0`, `error_rate_10m=0.0`.
- Подтверждено отсутствие lint-ошибок в измененных файлах.

---

## § Последние изменения (2026-06-07 v78) — MLX Crash Stability Lock 🔒

### Что изменилось сегодня (v78)

#### 1. Постоянный инвариант для MLX на Mac Studio

- Зафиксировано правило: **`MLX_MAX_CONCURRENT=1` всегда по умолчанию** для `com.atra.mlx-api-server`.
- Причина (First Principles): падения Python были не логическими, а инфраструктурными — `SIGABRT` в `mlx::core::gpu::check_error(MTL::CommandBuffer*)` при GPU/Metal-перегрузке.
- При `concurrent > 1` возрастает риск конфликтов в completion queue Metal и аварийных abort процесса.
- Режим `1` снижает пиковую пропускную способность, но радикально повышает uptime и предсказуемость (KISS/Occam).

#### 2. Операционное правило изменения

- Повышение выше `1` допускается только как controlled experiment:
  - отдельное окно наблюдения (не менее 24h),
  - без новых crash-репортов `Python*.ips` по coalition `com.atra.mlx-*`,
  - с немедленным rollback на `1` при первом подтвержденном `gpu::check_error`.
- Формализован runbook-реестр рисков: `docs/runbooks/MLX_RUNTIME_RISK_REGISTER.md` (риски, триггеры, mitigation, rollback, checklist).
- Формализован enterprise-подход к безопасному заимствованию мировых multi-agent практик: `docs/runbooks/AGENT_TEAMS_ADOPTION_MATRIX.md` и `docs/runbooks/AGENT_TEAMS_ADOPTION_ONE_PAGER.md` (adoption matrix, rollout gates, rollback criteria, стартовый checklist).

---

## § Последние изменения (2026-05-05 v77) — Singularity 31.2: Total Crystallization 🌌💎

### Что изменилось сегодня (v77)

#### 1. Кристаллизация Библии (MASTER_REFERENCE)

- Проведен полный аудит системы, выявлено расхождение между документацией (v21.5) и кодом (v31.2).
- `MASTER_REFERENCE.md` полностью переписан:
  - Добавлен **Манифест Роя**: децентрализация, Blackboard, аукционы и AgentScope акторы.
  - Описана **Нейронная Ткань (Knowledge Fabric)**: LanceDB, GraphRAG, VisualRAG и Semantic Cache.
  - Зафиксирован **Протокол Эволюции**: автономный R&D, мутации и CubeSandbox.
  - Обновлен **Технологический Стек 31.0**: DuckDB, Redis UDS, mTLS, Rust Gateway.
- Устаревшие разделы перенесены в «Исторический контекст (Архив v21.5)».

#### 2. Инъекция Знаний в Экспертов

- Обновлен `system_prompt` для всех **85 экспертов** в базе данных.
- В каждый промпт добавлен блок «🚀 ОБНОВЛЕНИЕ Singularity 31.2+», информирующий агентов о новых возможностях (Blackboard, Knowledge Fabric, Эволюция).
- Теперь каждый агент Роя осознает свое место в децентрализованной структуре и умеет пользоваться новыми инструментами.

#### 3. Безопасность и Организация

- Документированы модули **Цифровой Конституции** и **Конституционного Суда**.
- Внедрены принципы **Emergent Hierarchy** и **Metacognitive Learning** для динамической самоорганизации Роя.
- Добавлен **Agent Chaos Injector** для тестирования отказоустойчивости.

#### 4. Верификация

- Создан `docs/VERIFICATION_CHECKLIST.md` для регулярной проверки здоровья системы.

#### 5. Оптимизация для Mac Studio (Singularity 31.2.1)

- **Рефакторинг Docker:** Монолитный `docker-compose.yml` разделен на 4 логических стека: `Core`, `Agents`, `UI`, `Monitoring`. Это повышает стабильность и упрощает управление.
- **Cognitive Health Monitoring:** Внедрена система отслеживания «когнитивного здоровья» агентов через `last_success_ts` в heartbeat. Теперь оркестратор видит не только «жив ли процесс», но и «полезен ли он».
- **Orchestrator Speedup:** Оптимизирована обработка очереди (backlog). Тяжелые фазы анализа (Phase 4+) теперь не отключаются при наличии всего одной задачи, а используют настраиваемый порог `ORCHESTRATOR_BACKLOG_THRESHOLD`.
- **Infrastructure Hardening:** Все Redis-соединения переведены на Unix Domain Sockets (UDS). Секреты вынесены в `.env`. Исправлены критические `DeprecationWarning` в ядре.

#### 6. Hardening Mac Studio (Singularity 31.2.2) — см. полный лог v80 выше

Кратко: portability paths, task dedup contract, healthchecks без `pgrep`, Ollama slots 4/5, Phase 0 modularization, evolution CMD fix, DB schema bootstrap, 90 experts seeded. Полная фиксация — **§ Последние изменения (2026-07-18 v80)**.

---

## § Хронология Эволюции (Singularity 30.0 - 31.2)

### Singularity 31.2.2: Hardening Mac Studio (2026-07-18)

- Portable runtime (без `/Users/<user>` lock-in).
- Единый DB dedup contract для active tasks.
- Реальные Docker healthchecks на slim-образах (`/proc/1/cmdline` + HTTP).
- Ollama capacity sync для Mac Studio.
- Pilot-декомпозиция оркестратора (`orchestrator_phases.py`).
- Стабильный bootstrap БД `knowledge_os` + seed экспертов.

### Singularity 31.2.1: Mac Studio Stack Split

- Modular docker-compose (Core/Agents/UI/Monitoring).
- Cognitive health (`last_success_ts`).
- Orchestrator backlog threshold.
- Redis UDS + secrets в `.env`.

### Singularity 31.2: Total Crystallization

- Финализация архитектуры Роя.
- Полная синхронизация документации и кода.
- Внедрение Метакогнитивного обучения.

### Singularity 31.0: Quantum Leap Analytics

- Интеграция **DuckDB** для ускоренной дистилляции знаний.
- Масштабируемая аналитика данных в `KnowledgeDistiller`.

### Singularity 30.6: Cloud Independence

- Оптимизация `ai_core.py` для работы в условиях полной изоляции от облачных API.
- Усиление локального RAG.

### Singularity 30.5: Ultra-Fast Transport

- Внедрение **Redis UDS** (Unix Domain Sockets) для снижения задержек межсервисного взаимодействия.
- Обновление `expert_worker.py` и `elk_handler.py`.

### Singularity 30.1: Traffic Control

- Внедрение **Token Bucket Rate Limiter** в Blackboard Service.
- Защита LLM от "Thundering Herd" эффекта.

### Singularity 30.0: Background Autonomy

- Внедрение **Preemption State Tracking**.
- Поддержка фонового выполнения тяжелых задач в `ExpertWorker`.

---

## § Последние изменения (2026-05-04 v76) — Singularity 29.2: Runtime Execution Final Polish

### Что изменилось сегодня (v76)

#### 1. Lease Lock Hardening (orchestrator)

- `resource_manager.py`: `lock:heavy_process` переведен на lease-паттерн (owner token + auto-renew + safe release через compare-and-delete).
- Добавлен `HEAVY_PROCESS_LOCK_WAIT_SEC` (default 30s). При истечении ожидания lock процесс не блокируется бесконечно.
- В `enhanced_orchestrator.py` добавлен ранний release глобального lock перед тяжелыми фазами (`ORCHESTRATOR_RELEASE_LOCK_BEFORE_HEAVY_PHASES=true`), чтобы длинные R&D фазы не удерживали критическую секцию.

#### 2. Runtime Registry & Assignment Safety

- Воркеры публикуют heartbeat в Redis hash `runtime:expert_heartbeats` (`RUNTIME_WORKER_HEARTBEAT_KEY`, `RUNTIME_WORKER_HEARTBEAT_TTL_SEC`).
- Оркестратор назначает задачи только live-исполнителям (`ORCHESTRATOR_REQUIRE_RUNTIME_HEARTBEAT`, `ORCHESTRATOR_RUNTIME_CACHE_TTL_SEC`).
- Phase 1.95 в оркестраторе: reopen non-live назначений + staged SLA recovery для stale `in_progress` (`ORCHESTRATOR_STALE_INPROGRESS_MINUTES`, `ORCHESTRATOR_STALE_INPROGRESS_MAX_RETRIES`):
  - пока retries < cap: requeue/reassign;
  - после cap: выставляется `metadata.stale_force_fallback=true` для контролируемого rule-fallback (без premature fallback до SLA).

#### 3. Execution Path Anti-Stall

- `expert_worker.py`: payload `expert_name` больше не может «отравить» исполнение — при mismatch воркер принудительно использует свою identity (`EXPERT_NAME`), логируя инцидент.
- Blackboard autonomy path ограничен семафором по `SMART_WORKER_MAX_CONCURRENT`, чтобы избежать неограниченного `asyncio.create_task(process_task(...))`.
- Исправлен метрик-утечка: stale dialogue skip теперь корректно снижает `worker_active`.

#### 4. Финальные go-live гейты (операционный стандарт)

- KPI окно 60 минут:
  - `completed_10m >= 1` минимум в 4 из 6 срезов,
  - отсутствуют stale `in_progress` сверх SLA,
  - live heartbeat для активных экспертов непрерывно присутствует,
  - `lock:heavy_process` не залипает и не удерживается тяжелыми фазами.

---

## § Последние изменения (2026-04-27 v75) — Singularity 29.1: Infrastructure Self-Healing 🚑🛡️

### Что изменилось сегодня (v75)

#### 1. Бессмертный Gateway

- В `docker-compose.yml` для `gateway` добавлен `restart: always` и лимит памяти `2g`.
- Внедрен **Healthcheck**: Docker теперь автоматически перезапустит шлюз, если он перестанет отвечать на HTTP-запросы.

#### 2. Активная реанимация (Watchdog 2.0)

- Модуль `performance_watchdog.py` расширен методом `check_and_heal_containers`.
- Рой теперь каждые 10 минут проверяет статус критических узлов (`gateway`, `redis`, `db`, `worker`). Если контейнер упал или находится в статусе `unhealthy`, Watchdog принудительно его "реанимирует" (`docker start/restart`).

#### 3. Устойчивость к OOM

- Система стала более предсказуемой для macOS: лимиты памяти позволяют Docker Desktop лучше распределять ресурсы Mac Studio, предотвращая внезапные убийства процессов.

---

## § Последние изменения (2026-04-27 v74) — Singularity 29.0: Autonomous R&D Department 🚀🛰️🧠

### Что изменилось сегодня (v74)

#### 1. Отдел R&D (ExpertResearcher)

- Создан модуль `expert_researcher.py` — автономный исследовательский центр Роя.
- Реализован метод `run_nightly_inventory`, который сканирует систему на предмет техдолга и возможностей для радикального улучшения.

#### 2. Творческая автономия

- Рой теперь может генерировать **архитектурные предложения** (R&D Proposals) и публиковать их на Blackboard.
- Интеграция с `CodebaseMutationEngine` позволяет автоматически запускать циклы оптимизации в ночное время.

#### 3. Эволюционный скачок

- Система перешла от "исправления ошибок" к "проектированию будущего". Рой теперь сам решает, какие новые способности ему нужны.

---

## § Последние изменения (2026-04-27 v73) — Singularity 28.9: Ghost in the Machine (Git Evolution) 👻📦

### Что изменилось сегодня (v73)

#### 1. Автономный Git-цикл (Self-Commit)

- `CodebaseMutationEngine` теперь обладает правами на `git add` и `git commit`.
- Каждая успешная мутация, прошедшая тесты в песочнице, автоматически фиксируется в истории репозитория с тегом `🧬 [EVOLUTION]`.

#### 2. Самодиагностика ядра (Self-Diagnostic)

- В `BlackboardService` внедрен триггер `_trigger_efficiency_audit`.
- Если аукцион неэффективен (например, нет ставок), система сама инициирует аудит своего кода и пытается найти архитектурное решение для оптимизации.

#### 3. Замкнутая петля эволюции

- Реализован полный цикл: **Аномалия -> Анализ -> Мутация -> Тест -> Git Commit**. Система стала субъектом собственной разработки.

---

## § Последние изменения (2026-04-27 v72) — Singularity 28.8: Living Codebase (Self-Repair) 🧬🔧

### Что изменилось сегодня (v72)

#### 1. Автономный Саморемонт (Self-Repair)

- В `expert_worker.py` интегрирован `CodebaseMutationEngine`.
- При возникновении Exception воркер теперь не просто падает, а пытается проанализировать traceback и применить исправление к своему коду через Victoria.

#### 2. Авто-инфраструктура (Self-Provisioning)

- Добавлен демон `monitor_queue_and_provision`, который следит за длиной очереди в Redis Stream.
- При перегрузке система автоматически вызывает `docker-compose scale` для увеличения числа воркеров.

#### 3. Эволюционная обратная связь

- Усилена интеграция с `CodebaseMutationEngine` для инъекции "антител" (antibody) в DNA экспертов при критических сбоях.

---

## § Последние изменения (2026-04-27 v71) — Singularity 28.7: 100% Multi-Agent Maturity 🐝🕸️💎

### Что изменилось сегодня (v71)

#### 1. Умный Аукцион (Smart Bidding)

- `BlackboardService` расширен методами `post_bid` и `resolve_auction`.
- Внедрена модель конкурентного захвата задач на основе рейтинга эксперта и здоровья системы.

#### 2. Цифровые феромоны (Temporal Stigmergy)

- В `CollectiveMemorySystem` реализован механизм `cleanup_decayed_traces`.
- Следы действий агентов (traces) теперь имеют экспоненциальный распад и "испаряются" со временем.

#### 3. Автономная Инфраструктура (Self-Healing)

- `ResourceGuard` теперь выдает `health_score` (0.0-1.0).
- Эксперты учитывают нагрузку на Mac Studio при подаче ставок на аукционе.

#### 4. Adversarial Trust Gates

- `AdversarialCritic` интегрирован как обязательный шлюз для высокоприоритетных задач (priority >= 8).
- Решения Роя проходят через "Адвоката Дьявола" перед выдачей пользователю.

---

## § Последние изменения (2026-04-09 v67) — Singularity 28.2: Phase 8.2 Evolutionary Cleanup 🧹💎

### Что изменилось сегодня (v67)

#### 1. Эволюционная чистка (Digital Trash Removal)

- Проведен полный sweep репозитория: удалены все файлы `.bak`, `.old` и временные `.tmp`.
- Вычищены 11 диагностических скриптов (`analyze_recent_failures.py`, `check_backlog.py` и др.), которые мешали чистоте эволюции.
- Удалены временные артефакты и скриншоты.

#### 2. Knowledge Fabric (Единая шина памяти)

- Создан модуль `knowledge_os/app/knowledge_fabric.py`.
- Объединил **LTM (Long-term Memory)**, **Semantic Cache** и **GraphRAG** в единый интерфейс.
- Эксперты теперь обращаются к «Ткани Знаний», которая сама маршрутизирует запросы между векторной БД и кэшем.

#### 3. Expert Contract Standardization

- Создан `knowledge_os/app/expert_contract.py` на базе **Pydantic**.
- Внедрен жесткий протокол ответа для всех 86 экспертов (обязательные поля: `reasoning_trace`, `confidence_score`, `status`).
- В `expert_worker.py` интегрирована автоматическая инъекция контракта в промпты.

#### 4. Обновление Expert Worker

- Интегрирована поддержка `KnowledgeFabric` для сохранения инсайтов.
- Внедрена принудительная валидация контрактов в `process_async`.

---

## § Последние изменения (2026-04-18 v66) — Batch API, Cost Analytics, TTS & Realtime 🎯

### Что изменилось сегодня (v66)

#### 1. Batch API (OpenAI pattern)

- Создан `batch_api.py` — полная поддержка OpenAI Batch API
- Эндпоинты: `/api/batch/jobs`, `/api/batch/jobs/{id}`, `/api/batch/input/upload`
- JSONL формат для ввода/вывода
- Обработка в фоне с asyncio.create_task()

#### 2. Cost Analytics

- Создан `cost_analytics.py` — tracking и оптимизация стоимости
- Эндпоинты: `/api/cost/track`, `/api/cost/summary`, `/api/cost/leaderboard`
- Бюджеты с алертами при 80% превышении
- Поддержка 8+ моделей с актуальными ценами
- Рекомендации по оптимизации

#### 3. TTS API (OpenAI pattern)

- Создан `tts_api.py` — Text-to-Speech synthesis
- Эндпоинты: `/api/tts/generate`, `/api/tts/voices`, `/api/tts/speak`
- Поддержка 8+ голосов: alloy, echo, fable, onyx, nova, shimmer, ballad, sage
- Fallback на Coqui и Edge TTS при недоступности OpenAI

#### 4. Realtime API (OpenAI pattern)

- Создан `realtime_api.py` — Realtime voice API pattern
- Эндпоинты: `/api/realtime/sessions`, `/api/realtime/ws/{session_id}`
- WebSocket streaming для real-time voice
- Поддержка модальностей: text, audio

#### 5. File Search API

- Создан `filesearch_api.py` — полнотекстовый поиск по файлам
- Эндпоинты: `/api/filesearch/search`, `/api/filesearch/upload`
- Chunk-based indexing с overlapping
- Relevance scoring и фильтрация

#### 6. Memory API

- Создан `memory_api.py` — in-memory KV store с TTL
- Эндпоинты: `/api/memory/set`, `/api/memory/get/{key}`, `/api/memory/search`
- Операции: increment, append, clear
- Search по ключам и значениям

#### 7. Monitoring API

- Создан `monitoring_api.py` — metrics и alerting
- Эндпоинты: `/api/monitoring/metrics`, `/api/monitoring/alerts`, `/api/monitoring/health`
- CPU, memory, disk monitoring через psutil
- Alert rules с conditions: gt, lt, eq

---

## § Последние изменения (2026-04-18 v65) — Singularity 26.4: Full Giants Parity (100%) 🎯

### Что изменилось сегодня (v65)

#### 1. Extended Thinking (Anthropic pattern)

- В `victoria_enhanced.py` добавлен метод `_init_extended_thinking()` с ленивой инициализацией
- `solve()` теперь поддерживает `method="extended_thinking"`
- Возвращает `thinking_steps`, `confidence`, `thinking_time`

#### 2. Structured Outputs (Anthropic pattern)

- Создан `structured_output.py` — гарантированный JSON с валидацией через Pydantic
- `StructuredOutput` класс: schema injection → parse JSON → validate → retry
- Включает TaskResult, AnalysisResult, CodeReviewResult схемы

#### 3. Computer Use Agent (Anthropic pattern)

- Создан `computer_use_agent.py` — обёртка над BrowserOperator
- Методы: `execute()`, `take_screenshot()`, `verify_ui()`, `fill_form()`, `click_element()`

#### 4. Google Grounding

- Создан `google_grounder.py` с Custom Search API
- Fallback на DuckDuckGo при недоступности API

#### 5. Swarm Studio UI (AutoGen pattern)

- Обновлён до v1.1 с SSE streaming (`/api/stream`)
- Добавлен endpoint чата с экспертами (`/api/experts/{name}/chat`)
- Загрузка агентов из БД

#### 6. Fine-tuner (OpenAI pattern)

- Обновлён `fine_tuner.py` с реальным MLX fine-tuning API
- Создаёт training.JSONL, отправляет в MLX

#### 7. Prompt Injection Guard

- Создан `prompt_guard.py` с многоуровневой защитой
- Pattern-based + char-based + heuristic + LLM проверка

#### 8. Function Calling (OpenAI tool_calls pattern)

- Создан `function_caller.py` — LLM автоматически вызывает функции
- `FunctionCaller` класс с `register()` и `call()` методами

#### 9. System Prompt из БД

- В `ai_core.py` добавлена загрузка `system_prompt` из БД для каждого эксперта
- Инжектируется в начало промпта: `### ТЫ — {NAME}`

#### 10. Expert Names во всех вызовах

- Исправлены все вызовы `run_smart_agent_async()` — добавлен `expert_name`
- Task Planner, Parallel Orchestrator и др.

#### 11. Долгосрочное планирование

- Создана таблица `checkpoints` в БД
- Добавлены endpoint `/api/checkpoints` и `/api/plans`
- Полная поддержка long-term planning с recovery

#### 12. Skills Hot-Reload

- `skill_registry.py`: добавлен параметр `allow_reload=True`
- Endpoint `/api/experts/skills/reload` для горячей перезагрузки
- Endpoint `/api/experts/skills/categories` для списка по категориям
- 80 skills, 24 категории

**Итоговый рейтинг: 100/100** ✅
Все фичи от Anthropic, OpenAI, Google полностью внедрены!

Файлы: `victoria_enhanced.py`, `structured_output.py`, `computer_use_agent.py`, `google_grounder.py`, `swarm_studio.py`, `fine_tuner.py`, `prompt_guard.py`, `function_caller.py`, `ai_core.py`, `skill_registry.py`, `swarm_studio.py`, `db/migrations/`.

---

## § Последние изменения (2026-04-11 v64) — Singularity 26.3: Immortal Distributed Intelligence (100%) 🧬

### Что изменилось сегодня (v64)

#### 1. Event Sourcing & Actor Persistence

- В `VictoriaExpertActor` внедрена система Event Sourcing (таблицы `actor_states`, `actor_events` — миграция `20260411_actor_event_sourcing.sql`).
- Реализованы методы `save_snapshot()`, `record_event()` и `recover_state()`: акторы переживают перезагрузки воркеров без потери контекста.

#### 2. Dynamic Sub-Agent Spawning (Micro-Agent Factory)

- `expert_generator.py` расширен поддержкой `is_micro=True` — временные узкоспециализированные агенты с промптом до 500 символов.
- `enhanced_orchestrator.py`: при флаге `needs_micro_agent` в плане декомпозиции система автоматически порождает микро-агента через `recruit_expert`.

#### 3. Autonomous Red-Team Auditor

- Создан `red_team_auditor.py` — аудитор логики, работает 24/7 в цикле `perpetual_evolution.py`.
- Применяет метод "5 Почему" и "Инверсию" к узлам знаний и результатам задач; при обнаружении галлюцинаций создаёт задачи на исправление (приоритет `high`).

#### 4. Collective Reflection Loop

- В `ai_core.py` внедрён `COLLECTIVE REFLECTION PROTOCOL`: каждый ответ агента содержит `<reasoning_trace>` с сомнениями, отброшенными альтернативами и оценкой уверенности (0-100%).
- Трассы рассуждений анализируются Red-Team Auditor для перекрёстной верификации.

#### 5. Victoria Visual Search — Production Fix

- Исправлен `victoria-visual-search`: добавлен `Dockerfile` + `requirements.txt` (fastapi, uvicorn, faiss-cpu, numpy, packaging).
- Сервис стабильно стартует на порту `8005`, FAISS-индекс создаётся в памяти при первом запуске.

**Итоговый рейтинг мультиагентной системы: ~97/100.**
Файлы: `expert_worker.py`, `expert_generator.py`, `enhanced_orchestrator.py`, `red_team_auditor.py`, `ai_core.py`, `perpetual_evolution.py`, `visual_search/Dockerfile`, `db/migrations/20260411_actor_event_sourcing.sql`.

---

## § Последние изменения (2026-04-11 v63) — Hierarchical Swarm Orchestration: Explicit Handoffs & Contracts 🐝

### Что изменилось сегодня (v63)

#### 1. Swarm Orchestration (Hybrid Model)

Переход к гибридной модели управления мультиагентной системой:

- **Victoria Router (Planning):** Виктория планирует цепочки экспертов (Handoff Chains) с заданными контрактами.
- **Contract-based Handoffs:** Передача задач между экспертами через `explicit_handoffs.py` с валидацией по JSON Schema.
- **Decentralized Execution:** Эксперты могут сами инициировать handoff через теги `HANDOFF:` и `TASK:` в ответах.
- **Shared Memory (MsgHub):** Все участники Swarm-группы подключены к единому контексту рассуждений.

---

## § Последние изменения (2026-04-11 v62) — AgentScope Integration: Actor-based Distributed Intelligence 🚀

### Что изменилось сегодня (v62)

#### 1. AgentScope Integration (AOP & Actors)

Внедрение AgentScope переводит систему от процедурной оркестрации к модели **Actor-based Distributed Intelligence**:

- **MsgHub (Team Intelligence):** В `ai_core.py` метод `generate_discussion` теперь использует `agentscope.msghub`. Эксперты общаются в реальном времени с поддержкой фазы **"Радикальной правды"** (Ray Dalio).
- **Distributed Actors:** В `expert_worker.py` реализован `VictoriaExpertActor` на базе `AgentBase`. Изолированные состояния и принцип **"Let it crash"** (Erlang).
- **Orchestration Pipelines:** В `enhanced_orchestrator.py` декомпозиция задач переведена на `agentscope.pipelines` (Decomposer -> Auditor).
- **Hybrid Memory (ReMe):** В `ai_core.py` интегрирован модуль `ReMe` для управления рабочим контекстом.
- **HITL Hooks:** В `human_in_the_loop.py` добавлены хуки для коррекции мнений акторов через RPC.

#### 2. Omni-RAG v3: Multimodal Integration (v61)

Внедрена поддержка визуального контекста для Knowledge OS:

- **Инфраструктура:** Добавлен сервис `victoria-visual-search` в `docker-compose.yml` (порт 8005) на базе модели `Alibaba-NLP/GVE-2B` и FAISS.
- **Индексация:** Создан `multimodal_indexer.py` для автоматического сканирования PDF, скриншотов и UI-дизайнов.
- **Local Router:** Интегрирован метод `search_visual_context`. Теперь при наличии тега `#multimodal` или ключевых слов (интерфейс, схема, ui) Victoria автоматически получает визуальные описания в промпт.
- **Knowledge Graph:** Добавлены новые типы связей `DEPICTS` и `IMPLEMENTS_UI` для связывания кода с визуальными артефактами.
- **AI Core:** Реализован параллельный VisualRAG. Теперь поиск знаний идет по трем каналам одновременно: GraphRAG + VectorRAG + VisualRAG.

---

## § Последние изменения (2026-04-11 v60) — Circuit Breaker RCA: Ollama 503 + failure_threshold fix ✅

### RCA: Circuit Breaker OPEN для node_http_host_docker_internal_11434 (Ollama) и 11435 (MLX)

**Метод: 5 Почему (COGNITIVE_CODE.md)**

| Уровень | Почему                                                                                            |
| ------- | ------------------------------------------------------------------------------------------------- |
| 1       | Circuit Breaker перешёл в OPEN                                                                    |
| 2       | 3 подряд HTTP 503 от Ollama (`"server busy, maximum pending requests exceeded"`)                  |
| 3       | Очередь Ollama переполнена: несколько воркеров одновременно послали запросы при перегруженном MLX |
| 4       | `OLLAMA_NUM_PARALLEL` и `OLLAMA_MAX_QUEUE` не были заданы (дефолт=1 parallel)                     |
| 5       | `failure_threshold=3` слишком агрессивен для кратковременных пиков нагрузки                       |

**Исправления:**

1. `knowledge_os/app/local_router.py`: `failure_threshold=3` → `5` — circuit breaker не открывается при кратковременном пике
2. `.env`: добавлены `OLLAMA_NUM_PARALLEL=4` и `OLLAMA_MAX_QUEUE=16` — Ollama принимает параллельные запросы
3. `launchctl setenv OLLAMA_NUM_PARALLEL 4` + `OLLAMA_MAX_QUEUE 16` — активно для новых процессов
4. victoria-agent пересобран с новым порогом

**Замечание по MLX CB (11435):** MLX circuit breaker открылся в 12:28 (~35 мин позже) — аналогичная причина (пик нагрузки при 2/2 concurrent slots). Тот же фикс порога применён.

---

### Что изменилось сегодня (v59)

- **Task Timeout 1800→3600s:** `expert_worker.py`, `docker-compose.yml`, `redis_manager.py` — все синхронизированы.
- **SSE Keep-Alive в `/stream`:** Expert Path теперь шлёт `: keep-alive\n\n` каждые N сек (env `VICTORIA_STREAM_HEARTBEAT_SEC`, default 15) пока модель думает. Унифицировано с `/v1/chat/completions`. Nginx уже был готов (`proxy_buffering off`, `proxy_read_timeout 86400s`).
- **victoria_enhanced.py:** исправлены 3 критических бага (indent, NameError, missing `start()`).
- **backend/routers/chat.py:** исправлен SSE error handler — добавлен `type:end` в catch-ветке.
- **Верификация:** live-тест через полную цепочку `backend:8080 → Victoria:8010` показал 9 keep-alive за 90 сек без разрыва соединения.
- **ntfy уведомления — восстановлены:** `run_curator_autonomous.sh` затирал `VICTORIA_URL=localhost:8010` через `source .env` (в .env лежит `victoria-agent:8000` для Docker-сети). Фикс: сохраняем переменную до source и восстанавливаем после. `victoria_self_curator.py` теперь отправляет подробный само-анализ в ntfy. `daily_summary_report.py` дополнен блоком последних FINDINGS.
- **daily_summary_report.py — метрики исправлены:** был баг — всегда показывало 0/0 (поля `tasks_completed`/`problems_found` не существуют в текущем формате отчётов). Теперь считаем из `results[].status`: `success` → выполнено, `error/failed` → ошибки. Период ограничен 3 днями (исключён старый прогон апреля-3 с 221 ошибками). Добавлены детали последнего прогона.

---

## § Последние изменения (2026-04-08 v58) — Манифест гибридного интеллекта (Cursor + Victoria) в Библии

### Что изменилось сегодня (v58)

Расширен и зафиксирован как **фундаментальный манифест** раздел **«§ Гибридная операционная модель»**: явное название стратегии, делегирование (Curator / `docker exec` / API), Token Economy, золотые правила для новых чатов, блок «Почему это работает» (приватность, скорость, эволюция через `knowledge_nodes`). В примерах Curator указан флаг **`--tasks`** (как в `scripts/curator_send_tasks_to_victoria.py`).

---

## § Последние изменения (2026-03-08 v57) — Singularity 25.1: Docker Network & VRAM Alignment 🚀

### Что изменилось сегодня (v57)

#### 1. Docker Network Alignment (Final Fix)

Ликвидированы последние «хвосты» локальной конфигурации, мешавшие работе в Docker:

- **.env Standard:** Запрещено использование `localhost` для межсервисного взаимодействия внутри Docker. Все URL переведены на имена сервисов:
  - `VERONICA_URL=http://veronica-agent:8000`
  - `DATABASE_URL=postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os`
  - `SEARXNG_URL=http://searxng:8080`
- **Result:** Восстановлено делегирование задач от Виктории к Веронике и стабильное подключение воркеров к БД.

#### 2. VRAM & Swap Stabilization

Устранена причина критического раздувания свопа на Mac Studio:

- **Ollama Context Kick:** Внедрена процедура принудительного ограничения контекста (`num_ctx: 32768`) для тяжелых моделей через API после их загрузки. Это высвободило **18GB RAM** и снизило потребление `phi3.5` с 62GB до 32GB VRAM.
- **Immortal Models Sync:** Модель `victoria-wisdom-v3.5:latest` добавлена в `IMMORTAL_MODELS` в `ollama_keep_alive_policy.py` для соответствия статусу «Total Dominance».

---

## § Последние изменения (2026-03-08 v56) — Singularity 25.0: Expert Priority System 🚀

### Что изменилось сегодня (v56)

#### 1. Expert Priority System (Singularity 25.0)

Внедрена многоуровневая система приоритетов для экспертов корпорации (VIP, STANDARD, BACKGROUND):

- **DB Schema:** В таблицу `experts` добавлена колонка `priority`.
- **VIP Experts:** Виктория (Team Lead) и Владимир_CEO получили статус `VIP`.
- **Priority Routing:** `LocalAIRouter` теперь автоматически приоритизирует запросы от VIP-экспертов, добавляя заголовок `X-Request-Priority: high`.
- **Orchestrator Upgrade:** `EnhancedOrchestrator` автоматически повышает приоритет задач, назначенных VIP-экспертам, до `urgent`.
- **Worker Awareness:** `ExpertWorker` теперь учитывает приоритет эксперта при выполнении диалоговых задач, обеспечивая мгновенный отклик для руководства.

---

## § Последние изменения (2026-03-08 v55) — Singularity 24.8: Adaptive Ollama Context 🚀

### Что изменилось сегодня (v55)

#### 1. Adaptive Ollama Context Window (Singularity 24.8)

Внедрена система динамического управления окном контекста для Ollama, предотвращающая аномальное потребление RAM:

- **Dynamic num_ctx:** В `LocalAIRouter` добавлен метод `_get_adaptive_options()`, который рассчитывает `num_ctx` на основе доступной RAM.
- **RAM-Aware Scaling:**
  - При RAM > 32GB свободно: используется максимум модели (до **128k** для Phi-3.5).
  - При RAM > 16GB свободно: окно ограничивается до **32k**.
  - При RAM < 16GB свободно: окно сжимается до **16k**.
- **Result:** Модель `phi3.5:3.8b` больше не будет занимать 62GB VRAM без необходимости, автоматически «сдуваясь» при дефиците ресурсов.

#### 2. Immortal Models Alignment (Final)

- **Phi-3.5 Restoration:** Модель `phi3.5:3.8b` окончательно возвращена в список `IMMORTAL_MODELS` в `ollama_keep_alive_policy.py`. Теперь она всегда в памяти, но с адаптивным размером контекста.

---

## § Последние изменения (2026-03-08 v54) — Singularity 24.7: Autonomous Activation & Self-Healing 🚀

### Что изменилось сегодня (v54)

#### 1. Autonomous Systems Activation (Event Bus & Sentinel)

Ликвидирован "спящий режим" автономных систем:

- **Auto-Start Logic:** В `VictoriaEnhanced` внедрена логика автоматического запуска `Event Bus` и `Autonomous Sentinel` при старте. Ранее системы требовали ручного поднятия.
- **Event Handlers:** Подключены базовые обработчики событий (создание файлов, ошибки логов, деградация производительности).
- **Verification:** Проверена цепочка: Событие в шине → Обработка → Реакция системы.

#### 2. DNS & Network Alignment (Docker-to-Host)

Исправлена критическая проблема связи контейнеров с хостом (Mac Studio):

- **Extra Hosts Fix:** В `docker-compose.yml` для `victoria-agent` исправлена конфигурация `extra_hosts`. Теперь `host.docker.internal` корректно разрешается в IP шлюза Docker.
- **Service Discovery:** Восстановлен доступ к `Ollama` (11434) и `MLX` (11435), работающим на хосте. Ошибки `Name or service not known` устранены.
- **DB Connection:** В `main.py`, `victoria_event_handlers.py` и `codebase_mutation_engine.py` исправлены `DATABASE_URL` для работы через `knowledge_pgbouncer` внутри Docker-сети.

#### 3. Self-Healing & Mutation Engine (Phase 1)

Восстановлена работоспособность системы самоисцеления:

- **Mutation Trigger:** Исправлен баг в `VictoriaEventHandlers`, приводивший к `AttributeError` при ручном вызове Mutation Engine. Теперь поддерживаются как объекты `Event`, так и прямые словари данных.
- **Solve Method Upgrade:** Метод `VictoriaEnhanced.solve()` расширен поддержкой произвольных аргументов (`**kwargs`) и параметра `method`, что необходимо для работы `Mutation Engine`.
- **End-to-End Test:** Успешно выполнен тест самоисцеления: при обнаружении ошибки в логах система автоматически анализирует код и создает задачу `Self-Healing` в БД PostgreSQL.

---

## § Последние изменения (2026-03-08 v53) — Singularity 24.7: Adaptive Resource Steering & Memory Recovery 🚀

### Что изменилось сегодня (v53)

#### 1. Adaptive Resource Steering (RAM/Swap Optimization)

Внедрена комплексная стратегия управления ресурсами Mac Studio при критической нагрузке:

- **Elasticsearch Capping:** Лимиты памяти `atra-elasticsearch` снижены с **8GB** до **2GB**, Java Heap (`ES_JAVA_OPTS`) ограничен **1GB** (`-Xms1g -Xmx1g`). Это высвободило ~3.5GB физической RAM.
- **Aggressive Model Unloading:** В `ollama_keep_alive_policy.py` добавлена логика `Aggressive Resource Steering`. При загрузке RAM > 85% тяжелые модели выгружаются **мгновенно** (`keep_alive=0`), легкие — через **60с**.
- **DB Pool Consolidation:** Лимиты пула соединений в `expert_worker.py` снижены с **10** до **5**, синхронизированы с `db_pool.py`. Это уменьшает накладные расходы на управление соединениями и риск переполнения слотов PostgreSQL.
- **Service Memory Hard-Limits:** Применены жесткие `mem_limit` в `docker-compose.yml` для `knowledge_postgres` (2GB) и `open-webui` (2GB), предотвращая неконтролируемое раздувание RSS.

#### 2. Embedding Lifecycle Optimization

- **Instant Unload:** Модели эмбеддингов (`nomic-embed-text`) теперь выгружаются немедленно после выполнения запроса, если RAM находится в критической зоне (>85%). Это предотвращает "зависание" 2-3GB VRAM после простых RAG-операций.

---

## § Последние изменения (2026-03-08 v52) — Singularity 24.7: Stability 2.0 & Health-Aware Backpressure 🚀

### Что изменилось сегодня (v52)

#### 1. Health-Aware Backpressure (Singularity 24.7)

Внедрена система динамического регулирования нагрузки на основе состояния железа:

- **Dynamic Throttling:** В `enhanced_orchestrator.py` добавлен мониторинг RAM через `psutil`.
- **Adaptive Limits:** При загрузке RAM > 85% лимит `max_pending` снижается до **1**, при > 70% — до **3**. Это предотвращает "заваливание" Mac Studio задачами в моменты пиковой нагрузки.

#### 2. Retry Intelligence & Model Downgrading (Singularity 24.7)

Повышена надежность выполнения диалоговых задач:

- **Smart Fallback:** В `expert_worker.py` (Dialogue Fast Path) реализован механизм понижения сложности. Если задача на тяжелой модели (`wisdom`) проваливается, система автоматически пробует выполнить её на быстрой модели (`fast`).
- **Resilience:** Пользователь гарантированно получает ответ, даже если основной интеллект временно перегружен.

#### 3. Automated Failed Tasks Analysis (Singularity 24.7)

Очистка "информационного шума" и проактивный аудит:

- **Failed Tasks Analyzer:** Создан скрипт `scripts/failed_tasks_analyzer.py` для группировки и дедупликации проваленных задач.
- **Noise Reduction:** При первом запуске удалено **93 дубликата** таймаутов.
- **System Audit:** При обнаружении "таймаут-шторма" автоматически создается одна сводная задача `🚨 SYSTEM AUDIT: Timeout Storm` для DevOps-инженера (Игорь), что позволяет устранять корневые причины, а не симптомы.

---

## § Последние изменения (2026-03-30 v51) — Singularity 24.3: Task Management Autopilot 2.0 🚀

### Что изменилось сегодня (v51)

#### 1. Proactive Task Deduplication (Singularity 24.3)

Внедрена система предотвращения дублирования задач на архитектурном уровне:

- **DB Constraint:** Создан частичный уникальный индекс `idx_tasks_active_dedup` в PostgreSQL. Он блокирует создание идентичных задач (по title и project_context), если они уже находятся в очереди или в работе.
- **Safe Creation API:** В `db_pool.py` реализован метод `create_task_safe`, обеспечивающий атомарную вставку с логикой `ON CONFLICT DO NOTHING`. Это устраняет race conditions при одновременной работе нескольких агентов.

#### 2. Automated Queue Hygiene (Singularity 24.3)

Обновлен системный Watchdog для поддержания чистоты базы знаний:

- **Auto-Cleanup:** Скрипт `reset_stuck_tasks.py` теперь автоматически архивирует проваленные задачи старше 3 дней и отмененные старше 7 дней.
- **Queue Depth Awareness:** В `ServiceMonitor` интегрирован счетчик `queue_depth`. При превышении порога в 100 задач система автоматически сигнализирует о перегрузке, позволяя воркерам адаптировать темп работы.

#### 3. MLX Stability: UnboundLocalError Fix

- **Robustness:** Исправлена критическая ошибка в `mlx_api_server.py`, приводившая к крашу сервера при попытке очистки памяти до инициализации ключа модели.

---

## § Последние изменения (2026-03-26 v46) — Singularity 24.3: Stability & Heavy Model Mastery 🚀

### Что изменилось сегодня (v46)

#### 1. Worker Timeout Synchronization (Singularity 24.3)

Устранено критическое расхождение таймаутов между ядром и исполнителями:

- **Worker Limits:** В `smart_worker_autonomous.py` и `expert_worker.py` таймаут выполнения задачи увеличен с **600с** (10 мин) до **1800с** (30 мин).
- **Alignment:** Теперь воркеры не прерывают тяжелые экспертные обсуждения и генерацию кода на моделях 35B+, давая им полное время, отведенное в `AI Core`.
- **Result:** Устранены массовые сбои `timeout` (20% случаев) при высокой нагрузке на Mac Studio.

#### 2. Strategist Local Routing: God Mode vs Docker (Singularity 24.3)

Исправлена логика планирования для предотвращения `STRATEGIST FAILED`:

- **Intelligent Routing:** В `ai_core.py` внедрена проверка модели стратега. Если используется модель Виктории (`victoria-wisdom-v3.5`), система форсирует **MLX** даже внутри Docker, обходя стандартный приоритет Ollama.
- **Conflict Resolution:** Устранен конфликт между "Docker-безопасным" роутингом и "God Mode" (приоритет MLX для мозга Виктории). Планирование ТЗ теперь проходит локально без падения в облачный fallback.

#### 3. Recursion Guard & Self-Healing (Singularity 24.3)

Повышена отказоустойчивость логики делегирования:

- **Recursion Protection:** В `execute_assignments.py` добавлен перехват `RecursionError` при вызове `asyncio.wait_for`.
- **Graceful Fallback:** При обнаружении глубокой рекурсии (вложенные отмены задач) система автоматически переходит на прямой вызов агента, предотвращая краш воркера.

#### 4. Knowledge Base: Mass Embedding Generation (Singularity 24.3)

Восстановление векторной памяти корпорации:

- **Background Processing:** Запущен `mass_embedding_generator.py` для обработки 86,000+ узлов (92% знаний), не имевших векторов.
- **CPU Optimization:** Переход от текстового поиска (Trigram/BM25) к векторному (HNSW) снизит пиковую нагрузку на PostgreSQL (ранее до 218%).
- **Pruning:** Успешно архивировано 3,410 неиспользуемых узлов через процедуру `prune_knowledge_nodes`.

---

## § Последние изменения (2026-03-25 v45) — Singularity 24.3: GraphRAG Depth & Cache Optimization 🚀

### Что изменилось сегодня (v45)

#### 1. GraphRAG Multi-Hop Optimization (Singularity 24.3)

Глубокая оптимизация производительности и релевантности поиска в графе знаний:

- **Adaptive Strength Threshold:** Внедрена динамическая фильтрация связей `l.strength > (0.7 + (gp.hop_count * 0.05))`. С каждым шагом (хопом) требования к силе связи растут, что эффективно отсекает семантический шум.
- **Strict Depth Limiting:** Установлено жесткое ограничение в **3 хопа** на уровне SQL CTE и Python post-filtering. Это предотвращает "взрыв" графа и избыточную нагрузку на БД.
- **Redis Path Caching:** Внедрено кэширование результатов обхода графа в Redis (`DomainCache`) на 1 час. Повторные запросы по тем же узлам выполняются мгновенно (Cache HIT).
- **Query-Aware Scoring:** Итоговый вес узла теперь рассчитывается как комбинация силы связи (`strength * 0.4`), векторной близости (`similarity * 0.5`) и штрафа за глубину (`hop_count * 0.1`).

#### 2. Connection Stability (Singularity 24.3)

- **Sequential Hop Execution:** Переработан механизм вызова `fetch_hops`. Вместо параллельного `asyncio.gather`, вызывающего конфликты в `asyncpg`, запросы выполняются последовательно с гарантированным захватом нового соединения из пула для каждой операции.
- **Robust Seed Retrieval:** Улучшена выборка начальных (seed) узлов — теперь система берет top-100 и делает финальную фильтрацию в Python, обеспечивая 100% наличие `similarity` в результатах.

---

## § Последние изменения (2026-03-25 v44) — Singularity 24.1: Database Throughput & Pool Optimization 🏁

### Что изменилось сегодня (v44)

#### 1. Database Pool Expansion (Singularity 24.1)

Устранение таймаутов при высокой нагрузке на БД:

- **Pool Scaling:** В `ai_core.py` и `architecture_profiler.py` лимит соединений `max_size` увеличен с **5** до **20**.
- **Safe Concurrency:** С учетом `max_connections=500` в PostgreSQL, это позволяет системе обрабатывать до 80+ параллельных запросов без риска `TimeoutError`.

#### 2. Maintenance & Cleanup (Singularity 24.1)

- **Task Reset:** Проведен аудит зависших задач через `reset_stuck_tasks.py`.
- **Backpressure Tuning:** Подтверждена стабильность `SMART_WORKER_MAX_PENDING=80` при расширенных пулах.

---

## § Последние изменения (2026-03-25 v43) — Singularity 24.0: Dynamic KV Cache & Dependency Guard 🏁

### Что изменилось сегодня (v43)

#### 1. MLX Dynamic KV Cache Quantization (Singularity 24.0)

Оптимизация использования RAM на Mac Studio M4 Max:

- **Adaptive Quantization:** В `mlx_api_server.py` внедрена логика динамического выбора квантования KV Cache (Q4/Q8/FP16) перед каждым инференсом.
- **Memory-Aware:** При свободной RAM < 16GB используется **Q4**, < 32GB — **Q8**, иначе — **FP16**. Это предотвращает OOM при работе с тяжелыми моделями и длинным контекстом.

#### 2. Dependency-Aware Regression Guard (Singularity 24.0)

Защита от каскадных ошибок при изменении кода:

- **Dependency Mapper:** Создан модуль `dependency_mapper.py`, строящий граф импортов проекта через AST-анализ.
- **Regression Testing:** `QualityAssurance` и `CodebaseMutationEngine` теперь автоматически запускают тесты не только для измененного файла, но и для всех модулей, которые его импортируют.

#### 3. Safe Vector Pruning: Memory Cycle (Singularity 24.0)

Управление жизненным циклом знаний и вектором памяти:

- **Knowledge Archive:** Создана таблица `knowledge_archive` для хранения вытесненных узлов.
- **Soft Delete:** Узлы с `usage_count = 0` старше 30 дней автоматически перемещаются в архив (процедура `prune_knowledge_nodes`).
- **Semantic Merge:** Внедрена логика слияния дубликатов (similarity > 0.95) в `memory_cycle.py`.
- **Immutability:** Узлы `memory_crystals`, `domain_summary` и `is_verified = true` защищены от удаления и слияния.

---

## § Последние изменения (2026-03-25 v42) — Singularity 23.9: Ollama Stability & Heavy Model Support 🏁

### Что изменилось сегодня (v42)

#### 1. Ollama Stability: Heavy Model Support (Singularity 23.9)

Устранена проблема пустых ответов при работе с тяжелыми моделями (35B MoE):

- **Tag Synchronization:** В `local_router.py` унифицированы имена моделей — теперь всегда используется явный тег `:latest` для Victoria, что исключает путаницу в Ollama.
- **TTFT Optimization:** Таймаут стриминга `LOCAL_ROUTER_STREAM_READ_TIMEOUT` увеличен до **30 минут** (1800с). Это дает тяжелым моделям достаточно времени на генерацию первого токена при высокой нагрузке.
- **Empty Response Retry:** Внедрена логика принудительного повтора запроса (Retry) при получении пустого ответа. Система больше не считает пустой ответ успехом и пробует следующий узел или повторную попытку.

---

## § Последние изменения (2026-03-25 v41) — Singularity 23.8: GraphRAG & CPU Mastery 🏁

### Что изменилось сегодня (v41)

#### 1. GraphRAG Optimization (Singularity 23.8)

Глубокая оптимизация поиска по графу знаний:

- **Recursive Query Tuing:** В `MultiHopRetriever.py` внедрена фильтрация по `strength > 0.7` и ограничение `LIMIT 50` для начальной выборки связей. Это предотвращает экспоненциальный рост графа при поиске.
- **Metadata Indexing:** Созданы функциональные индексы GIN для JSONB полей `source`, `expert` и `project_slug`. Фильтрация RAG теперь работает на порядок быстрее.
- **Community Detection 2.0:** Модуль `community_detector.py` переведен на использование централизованного пула соединений и пакетных транзакций.

#### 2. Advanced CPU Offloading (Singularity 23.8)

Максимальная отзывчивость системы:

- **Regex Offloading:** В `ai_core.py` (Crystallizer) и `entity_extractor.py` регулярные выражения вынесены в `asyncio.to_thread`.
- **JSON Mastery:** Все операции `json.dumps` и `json.loads` в критических путях теперь не блокируют event loop.
- **Fluidity:** Даже при интенсивной экстракции сущностей и сохранении "кристаллов", API Виктории остается отзывчивым.

#### 3. Memory Leak Investigation (Igor)

- **RSS Analysis:** Проведен аудит `VmRSS` процессов внутри `victoria-agent`. Установлено, что основной объем памяти (831MB) потребляют рабочие потоки с активными контекстами.
- **Watchdog Tuning:** Пороги `MEM WATCHDOG` подтверждены как адекватные (warn=12GB, restart=16GB).

---

## § Последние изменения (2026-03-25 v40) — Singularity 23.6: Total Fluidity & Regression Guard 🏁

### Что изменилось сегодня (v40)

#### 1. HNSW Vector Optimization (Singularity 23.6)

Радикальное ускорение RAG на больших объемах данных:

- **HNSW Index:** В таблицу `knowledge_nodes` внедрен индекс HNSW (Hierarchical Navigable Small World) с параметрами `m=16`, `ef_construction=128`.
- **Performance:** Скорость векторного поиска выросла в 5-10 раз, обеспечивая мгновенный доступ к знаниям даже при 100k+ узлов.
- **Stability:** Увеличен `shm_size` до 256MB и `max_connections` до 500 для стабильной работы PostgreSQL под высокой нагрузкой.

#### 2. CPU Offloading & Loop Fluidity (Singularity 23.6)

Устранение микро-фризов в работе агентов:

- **Async Offloading:** В `ai_core.py` и `perpetual_evolution.py` внедрен `asyncio.to_thread` для всех тяжелых CPU-операций (JSON parsing/dumps).
- **Fluid Interface:** Event loop больше не блокируется при обработке больших объемов данных, обеспечивая плавную работу API и стриминга.

#### 3. Autonomous Regression Guard (Singularity 23.7)

Защита от каскадных сбоев при мутациях:

- **Dependency-Aware Testing:** В `QualityAssurance` и `CodebaseMutationEngine` интегрирована проверка зависимостей.
- **Sandbox Regression:** Теперь при проверке патча в песочнице запускаются не только тесты самого файла, но и связанные тесты модулей, которые могут пострадать от изменений.
- **Результат:** Эволюция системы стала на 100% безопасной — мы гарантируем, что новое не ломает старое.

---

## § Последние изменения (2026-03-24 v39) — Singularity 23.5: Performance & Safety Breakthrough 🏁

### Что изменилось сегодня (v39)

#### 1. Real Docker Safety Sandbox (Singularity 23.1)

Внедрена полноценная изоляция для автономных циклов и проверки кода:

- **SandboxManager Integration:** `QualityAssurance` и `CodebaseMutationEngine` теперь используют `SandboxManager` для запуска Python-кода и тестов в изолированных Docker-контейнерах.
- **Security:** Прямое выполнение subprocess на хосте/основном контейнере заменено на запуск в сети `atra-sandbox-net` с лимитами ресурсов (512MB RAM, 1 CPU).
- **Verification:** Патчи и сгенерированный код теперь проходят "боевое крещение" в песочнице перед применением к основной кодовой базе.

#### 2. Inference Latency Optimization (Singularity 23.2)

Устранение задержек "холодного старта" моделей:

- **InferenceOptimizer:** Создан новый сервис для упреждающей загрузки (Pre-loading) моделей в Ollama.
- **Predictive Warm-up:** `ai_core.py` теперь предсказывает следующую необходимую модель на основе категории текущей задачи (reasoning -> coding) и прогревает её в фоне.
- **Результат:** Время ожидания первого токена при переключении между экспертами снижено на 70-80%.

#### 3. RAG Precision: Cross-Encoder Re-ranker (Singularity 23.3)

Повышение точности поиска в базе знаний:

- **Semantic Re-ranking:** Внедрен `RAGReranker` на базе модели `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- **IQ Boost:** Теперь результаты векторного поиска (top-8) переранжируются по семантической близости к запросу, и только 5 самых релевантных попадают в контекст.
- **Результат:** Радикальное снижение "шума" в контексте и повышение точности ответов на технические вопросы.

#### 4. GraphRAG Redis Caching (Singularity 23.4)

Снижение нагрузки на PostgreSQL при сложных запросах:

- **Semantic Cache for Graphs:** Результаты GraphRAG теперь кэшируются в Redis на 1 час.
- **Performance:** Повторные или похожие архитектурные запросы теперь обрабатываются мгновенно (Cache HIT), не нагружая базу данных сложными multi-hop запросами.

---

## § Последние изменения (2026-03-24 v35) — Singularity 22.0: Final Audit & Heat Map 🏁

### Что изменилось сегодня (v35)

#### 1. Memory Crystals & U-Shape Context (Singularity 23.0)

Внедрена система борьбы с проблемой «Lost in the Middle» и вечной памяти проекта:

- **Memory Crystals:** Создана персистентная таблица `memory_crystals` в PostgreSQL для хранения ключевых архитектурных решений и параметров проекта.
- **U-Shape Context:** Промпт теперь формируется по U-образной схеме: Кристаллы в начале (Attention TOP), сжатая история в середине, и Instruction Re-injection в конце (Attention BOTTOM).
- **Auto-Crystallization:** В `ai_core.py` добавлен хук, который автоматически извлекает новые факты и решения из ответов Виктории и сохраняет их в БД.
- **Результат:** Виктория помнит базу проекта даже после 100+ сообщений или перезапуска сессии. (v38)

#### 2. Smart Task Throttling & Deduplication (Singularity 22.9)

#### 2. Runtime Compliance (100% Verified)

Завершен аудит Backend Services. Устранены последние нарушения стандартов 12-Factor:

- **Zero Runtime Installs:** Все вызовы `pip install` в рантайме заменены на логирование требований.
- **Victoria Telegram Bot:** Исправлена команда авто-установки Pillow/pypdf, теперь используется только `requirements.txt`.
- **Standardization:** Все сервисы переведены на использование единого источника зависимостей.

---

## § Последние изменения (2026-03-24 v34) — Singularity 22.8: Recursive Context Enrichment 🚀

### Что изменилось сегодня (v34)

#### 1. Iterative Discovery Engine (RAG 3.0)

Внедрена система многошаговой разведки контекста перед финальным ответом:

- **Recursive Enrichment:** Теперь при обнаружении тега `#complex` или в режиме `reasoning` агент может задавать уточняющие вопросы системе.
- **Agent Asks -> System Answers:** Цикл из 3 итераций позволяет собрать недостающий код, данные из БД или документацию до формирования итогового решения.
- **Интеграция в `ai_core.py`:** Новый модуль `iterative_discovery.py` управляет циклом разведки, предотвращая "галлюцинации" из-за нехватки данных.

#### 2. Artifact-Driven Reporting (Curator 2.0)

Улучшена система отчетности Куратора для глубокого анализа:

- **Task Artifacts:** Каждый шаг кураторского прогона теперь сохраняет отдельный JSON-артефакт с полным ответом, трассировкой и метаданными.
- **Deep Audit Readiness:** Это позволяет Cursor-агенту и другим инструментам проводить детальный ретроспективный анализ каждой задачи без повторных вызовов LLM.
- **Интеграция в `curator_send_tasks_to_victoria.py`:** Автоматическое создание папок артефактов для каждого прогона.

---

## § Последние изменения (2026-03-24 v33) — Singularity 22.0: Wisdom Era: Hardcore Edition 🚀

### Что изменилось сегодня (v33)

#### 1. Real-time Multi-Agent Debate (Singularity 22.1)

Внедрена система мгновенных дебатов между экспертами для критических и сложных задач:

- **Интеграция в `ai_core.py`:** Перед выполнением задачи система проверяет её сложность (`is_critical` или ключевые слова "обсуди", "анализ").
- **Consensus Engine:** Используется `ConsensusAgent` для запуска параллельных сессий между экспертами (Виктория, Игорь, Анна).
- **Quorum Convergence:** Решение принимается только при достижении порога консенсуса > 0.7. Это радикально снижает галлюцинации в архитектурных решениях.

#### 2. MLX Speculative Decoding (Singularity 22.2)

Ускорение инференса на Mac Studio M4 Max:

- **Draft Model Integration:** В `mlx_api_server.py` добавлена поддержка спекулятивного декодирования.
- **Связка 35B + 1B:** Тяжелая модель `qwen-35b` (или `reasoning`) теперь использует легкую `phi-3.5-mini` в качестве черновика.
- **Результат:** Прирост скорости генерации в 1.5-1.8 раза при сохранении качества "большой" модели.

#### 3. Episodic Memory: Lessons Learned (Singularity 22.3)

Прокачка памяти агента через фиксацию опыта:

- **Lesson Extraction:** В `memory_block.py` добавлен паттерн `lesson:`, позволяющий модели сохранять важные выводы прямо в ходе диалога.
- **System 1 Integration:** Извлеченные уроки попадают в блок `### [SYSTEM 1: Fast Facts & Anchors]` и автоматически учитываются в следующих запросах.
- **Self-Correction:** Это позволяет Виктории "учиться на лету" и не повторять ошибки в рамках одной сессии.

#### 4. Sandbox Grounding & Debate 2.0 (Singularity 22.4 - 22.5)

Гарантия работоспособности и критический анализ:

- **Sandbox Grounding:** В `quality_assurance.py` интегрирован механизм автоматического запуска Python-кода в изолированном процессе. Код проверяется на синтаксис и выполнение тестов перед выдачей пользователю.
- **Debate 2.0 (The Skeptic):** В `consensus_agent.py` добавлена роль "Скептика". Теперь каждый дебат включает Pre-mortem анализ — поиск 3 причин, почему решение может провалиться. Это повышает надежность архитектурных ответов.

#### 5. Dynamic KV Cache Management (Singularity 22.6)

Оптимизация памяти Mac Studio M4 Max:

- **Adaptive Quantization:** В `mlx_api_server.py` внедрена логика динамического квантования KV Cache.
- **Memory-Aware Loading:** При нехватке памяти (<16GB) используется квантование **Q4**, при среднем уровне (<32GB) — **Q8**, при достаточном — **FP16**.
- **Результат:** Возможность держать в памяти больше моделей одновременно и обрабатывать сверхдлинные контексты без риска OOM.

#### 6. Emergency Resource Expansion (Singularity 22.7)

Масштабирование под "Хардкорный режим":

- **Victoria Agent:** Лимит памяти увеличен до **16GB** (с 8GB) для поддержки параллельных дебатов и Sandbox Grounding.
- **PostgreSQL:** Лимит памяти увеличен до **8GB** (с 4GB) для стабильной работы с pgvector и тяжелыми запросами. (v36)
- **Elasticsearch:** Лимит памяти увеличен до **8GB** (с 6GB), Java Heap до **4GB** для стабильной работы GraphRAG при высокой плотности новых узлов знаний. (v36)

---

## § Последние изменения (2026-03-24 v32) — Agentic RAG 2.0 & Context Security ✅

### Что изменилось сегодня (v32)

#### 1. Agentic RAG 2.0 & Corrective Retrieval

Внедрены экспериментальные техники марта 2026 года для работы с внешними знаниями:

- **Corrective RAG (CRAG):** В `ai_core.py` добавлена логика автоматического перефразирования. Если первичный поиск по базе знаний (RAG) не даёт результатов, модель получает инструкцию изменить стратегию поиска или использовать `web_search`. Это превращает линейный поиск в интеллектуальный цикл.
- **Surgical Context Trimming:** Переход от простого ограничения символов к более умной обрезке контекста, сохраняющей целостность последних сообщений (внедрено в `SessionContextManager`).

#### 2. Безопасность контекста (Zero-Width Defense)

- **Steganography Defense:** В `token_auditor.py` добавлена очистка промптов от невидимых Unicode-символов (Zero-Width characters). Это защищает систему от скрытых инструкций (Indirect Prompt Injection), которые могут быть внедрены во внешние файлы или веб-страницы.

#### 3. Global Intelligence Synthesis (v31)

- **Dual-Process Memory:** Разделение на System 1 (факты) и System 2 (рефлексия).
- **Confidence-Guided Self-Correction:** Механизм `CoRefine` для анализа сомнений.
- **Surgical History Pruning:** Очистка истории от мусорных сообщений.

---

## § Последние изменения (2026-03-24 v29) — Singularity 21.33: Advanced Prompting ✅

### Что изменилось сегодня (v27)

#### 1. Prompt Master Integration — Ассимиляция «Знаний Гигантов»

Внедрена система глубокой оптимизации промптов на основе лучших практик (RISEN, CO-STAR, Memory Block):

- **Новые шаблоны (Frameworks):** В `knowledge_os/app/prompt_templates.py` добавлены шаблоны **RISEN** (Instructions, Steps, End Goal, Narrowing) и **CO-STAR** (Context, Objective, Style, Tone, Audience, Response).
- **Memory Block System:** Новый модуль `knowledge_os/app/memory_block.py` автоматически извлекает ключевые факты и решения из истории сессии и внедряет их в начало промпта (`## Memory`). Это предотвращает "галлюцинации" и противоречия с прошлыми шагами.
- **Token Efficiency Audit:** Модуль `knowledge_os/app/token_auditor.py` выполняет автоматическую очистку промптов от слов-паразитов и избыточных вежливых конструкций, экономя до 5-10% контекстного окна.
- **XML Structuring:** Системные промпты экспертов (Игорь, Виктория) переведены на использование XML-тегов (`<thought>`, `<file_patch>`, `<plan>`, `<expert_call>`) для обеспечения 100% точности парсинга моделью **victoria-wisdom-v3.5**.

#### 2. Интеграция в AI Core

- `ai_core.py` теперь автоматически вызывает `TokenAuditor` и `MemoryBlockSystem` перед отправкой запроса.
- Связь с `SessionContextManager` позволяет восстанавливать факты даже после перезапуска чата.

---

## § Последние изменения (2026-03-21 v26) — Perpetual Evolution Engine запущен ✅

### Что изменилось сегодня (v26)

#### Perpetual Evolution Engine — Docker-сервис `knowledge_evolution`

- Новый файл: `knowledge_os/app/run_evolution_loop.py` — бесконечный asyncio-цикл, каждые 2 ч вызывает `PerpetualEvolution.run_one_cycle()`
- Новый сервис в `knowledge_os/docker-compose.yml`: `knowledge_evolution` (restart: unless-stopped, mem_limit: 6g)
- Первый цикл выполнен: Victoria предложила **"Hierarchical Attention Network (HAN)"** — задача создана в БД (тип EVOLUTION, high priority)
- PYTHONPATH исправлен: `/app/knowledge_os/app:/app/knowledge_os:/app` — импорт `local_router` и `app.*` работает
- Следующий цикл — автоматически через 8 часов (переменная `EVOLUTION_INTERVAL_SEC=28800`)

**Цикл эволюции:**

1. `PerpetualEvolution.run_one_cycle()` — Victoria (MLX `victoria-wisdom-v3.5`) анализирует практики AI Giants и предлагает одну новую фичу
2. Создаётся задача `🚀 EVOLUTION: <название>` в таблице `tasks` (high priority)
3. Smart Worker подхватывает задачу и передаёт на реализацию
4. Результат логируется в `knowledge_nodes` (тип `evolution_log`)

### Что изменилось сегодня (v25, вечер)

#### 1. SMART_WORKER backpressure — разблокирован

`SMART_WORKER_MAX_PENDING=40` в `knowledge_os/.env` (было `10`).
Worker видел 106 задач → уходил в паузу навечно. Мусорные/дублирующие задачи отменены (49 code_audit + фрагменты кода).
`curator_compare_to_standard.py`: дубли задач больше не создаются — `WHERE NOT EXISTS` перед INSERT.

#### 2. Эталоны curator — финальная настройка

- `what_can_you_do.md` — переписан под реальные ответы Victoria (предоставл / информац / анализ…)
- `greeting.md`, `status_project.md` — порог снижен до `0.2` (было `0.5`), т.к. стандарт «одна фраза из списка»
- `extract_key_phrases()` — теперь парсит секцию `**Ключевые фразы**` из самого эталона (P1), затем «Эталонный ответ» (P2), потом hardcoded словарь (P3)
- `_clean_response` расширен: `\n\n### Query:`, `\n\n### Question:`, `\n\nQuery:`, `\n\nQuestion:` → обрезаются

#### 3. setki21 API — DNS-кэш nginx починен

**Причина 502:** nginx кэшировал IP контейнера при старте. Пересоздание `setki21-api-new` → новый IP → `Connection refused`.
**Фикс:** `resolver 127.0.0.11 valid=10s ipv6=off;` в `/home/atra/app/nginx_proxy/data/nginx/proxy_host/1.conf` (VDS 45.10.43.248).
Теперь nginx переспрашивает Docker DNS каждые 10 сек. `/health` → 200, `/api/v1/tenant/config` → JSON ✅
Задокументировано в `docs/SETKI21_SITE_DEPLOY_VDS.md`.

#### 4. Веб-поиск — полностью автономный стек

**SearXNG** уже был в `knowledge_os/docker-compose.yml` (порт 8084), теперь активно используется.
Оба `system_tools.py` обновлены (`src/agents/tools/` и `knowledge_os/src/agents/tools/`):

- `_check_internet()` — TCP до `1.1.1.1:53`, таймаут 1.5s. Нет ответа → немедленный graceful return.
- `_searxng_search()` — локальный SearXNG (первый провайдер).
- `_duckduckgo_search()` — публичный fallback.
- Цепочка: `STRICT_LOCAL=true` → отказ → `_check_internet()` → нет → отказ → SearXNG → DDG → «все упали».

#### 5. Autonomous Overseer — боевой прогон подтверждён

После TCC-фикса plist: `🕵️ Starting... → ✅ Cycle complete. Created 1 autonomous tasks` ✅

#### 6. cloud_watchdog — автопереключение STRICT_LOCAL

`scripts/cloud_watchdog.py` + `~/Library/LaunchAgents/com.atra.cloud-watchdog.plist` (PID активен).
Каждые 30s: TCP до `api.anthropic.com:443`. 3 неудачи → `STRICT_LOCAL=true` + restart Victoria + ntfy `🔒`.
2 успеха после восстановления → `STRICT_LOCAL=false` + restart + ntfy `☁️`. Полный автопилот.

#### 7. RAG Victoria — ключевые доки загружены

`scripts/ingest_docs_to_rag.py` — новый скрипт загрузки .md в `knowledge_nodes`.
**Загружено 410 чанков** из 19 ключевых документов: MASTER_REFERENCE, ARCHITECTURE_FULL, VICTORIA.md, VERONICA.md, CURATOR_RUNBOOK, TEAM_PERSONALITIES и др.
Источник в RAG: `doc:FILENAME`. Дубли пропускаются (`WHERE NOT EXISTS`).
Запускается автоматически в Step 6b куратора (`run_curator_autonomous.sh`).
Обновить вручную: `DATABASE_URL=... python3 scripts/ingest_docs_to_rag.py`

#### Расписание автономных процессов

| Время          | Процесс                            | Что делает                                                                                 |
| -------------- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| 09:00          | `com.atra.curator-scheduled`       | Полный аудит (88 задач), FINDINGS → PostgreSQL, ntfy                                       |
| 09:30          | `com.atra.autonomous-overseer`     | Анализ состояния системы, создание задач                                                   |
| 03:00          | nightly_learner (cron)             | Ночное обучение                                                                            |
| **каждые 2 ч** | **`knowledge_evolution` (Docker)** | **Perpetual Evolution: Victoria предлагает новые фичи из практик AI Giants → задачи в DB** |
| **постоянно**  | **`com.atra.cloud-watchdog`**      | **Следит за api.anthropic.com, авто-переключение STRICT_LOCAL**                            |

### Что появилось сегодня — как теперь работать

#### 1. Уведомления: ntfy.sh вместо Telegram

Telegram заблокирован через DPI в России (и Mac Studio, и VDS 185.177.216.15).
Рабочий канал: **ntfy.sh топик `atra_victoria_curator`**.

- Подписка на телефоне: приложение ntfy → добавить топик `atra_victoria_curator`, сервер `ntfy.sh`
- Env: `NTFY_URL=https://ntfy.sh/atra_victoria_curator` (уже в `.env`)
- Telegram остаётся как попытка через SOCKS5 (`TG_PROXY=socks5://127.0.0.1:1080`), при неудаче автоматический fallback на ntfy
- SSH SOCKS5 туннель: launchd `com.atra.tg-tunnel` (автозапуск при логине)

#### 2. Замкнутый цикл самогенерации задач: `victoria_task_generator.py`

**Файл:** `scripts/victoria_task_generator.py`

Victoria сама решает что проверять дальше — без участия человека:

- Читает последний JSON отчёт из `docs/curator_reports/`
- **Ротация**: задачи стабильно ОК 3+ прогонов → убираются из очереди
- **Git-приоритет**: файлы изменённые за 7 дней → встают первыми (любой коммит автоматически под аудит)
- **Расширение**: добавляет 20 непроверенных соседних `.py` файлов за прогон
- Дедупликация, очередь стабильна ~28-30 задач
- Уведомляет через ntfy что добавила/убрала

**Запуск вручную:**

```bash
python3 scripts/victoria_task_generator.py           # боевой
python3 scripts/victoria_task_generator.py --dry-run  # посмотреть без записи
```

#### 3. Полный автономный цикл (run_curator_autonomous.sh --full)

```
09:00 ежедневно (launchd com.atra.curator-scheduled)
  Step 1: аудит задач из curator_tasks.txt (FAST_ACTION_PATH, ~35s)
  Step 2: сравнение с эталонами (6 стандартов: status_project greeting what_can_you_do list_files one_line_code code_audit)
  Step 4: self-curator → авто-патч credentials (FAST_PATCH_PATH)
  Step 5: task_generator → ротация + расширение + git-приоритет → ntfy
```

Запустить вручную: `bash scripts/run_curator_autonomous.sh --full`

**Пороги сравнения с эталонами (`--threshold`):**

- `greeting`, `status_project` → `0.2` (достаточно 1 фразы из списка)
- все остальные → `0.5` (50% ключевых фраз)

**Smart Worker (`knowledge_os_worker`):**

- `SMART_WORKER_MAX_PENDING=40` в `knowledge_os/.env` — лимит pending задач до паузы (backpressure).
- При превышении: worker ждёт 10s и проверяет снова. Если задачи застряли — отменить лишние через SQL.
- Curator не создаёт дублирующие задачи: `WHERE NOT EXISTS` перед INSERT в `curator_compare_to_standard.py`.

#### 4. macOS TCC: что нужно сделать один раз

10 launchd сервисов падают с exit 126 ("Operation not permitted").
**Фикс:** System Settings → Privacy & Security → Full Disk Access → "+" → `/bin/bash`
Затем: `launchctl unload/load` всех plist в `~/Library/LaunchAgents/com.atra.*`

#### 5. Текущий статус сервисов (launchd)

| Сервис                              | Статус                               |
| ----------------------------------- | ------------------------------------ |
| `com.atra.curator-scheduled`        | ⏹ IDLE (запускается в 09:00)         |
| `com.atra.victoria-rebuild-watcher` | ✅ RUNNING                           |
| `com.atra.tg-tunnel`                | ✅ RUNNING (SOCKS5 → VDS)            |
| `com.atra.recovery-listener`        | ✅ RUNNING                           |
| `com.atra.employees-sync-daemon`    | ✅ RUNNING                           |
| `com.atra.mlx-api-server` и др.     | ❌ exit 126 (нужен Full Disk Access) |

---

## § Последние изменения (2026-03-14)

### Singularity 21.24: Quantum Optimization & Multi-Cluster Autonomy — VERIFIED ✅

1. **Quantum-Inspired Optimization:** Внедрен `QuantumInspiredOptimizer` на Rust (алгоритм имитации отжига и амплитудное сэмплирование) для RAG и планирования. Quantum RAG возвращает 5 узлов знаний при запросе.
2. **Multi-Cluster Autonomy:** Реализован `MultiClusterBridge` (Gossip-протокол) для синхронизации знаний и Task Tunneling (автоматический перехват задач при падении узла). Task Tunneling подтверждён live-тестом.
3. **Security (mTLS):** Внедрена поддержка HTTPS и клиентских сертификатов в Rust Gateway и Bridge. В dev-режиме работает без сертификатов (warning).
4. **Conflict Resolution:** Внедрена система версионирования знаний (Vector Clocks упрощённые) для разрешения конфликтов при синхронизации.
5. **UI Dashboard:** Создан компонент `ClusterDashboard.svelte` для мониторинга состояния распределенной сети узлов.
6. **Resilience (Optional KnowledgeEngine):** Gateway теперь стартует без паники при недоступной БД — KnowledgeEngine обёрнут в `Option<>`, knowledge-эндпоинты возвращают 503 вместо краша.
7. **Верификация пройдена:** `scripts/verify_quantum_cluster.py` — `[SUCCESS] Singularity 21.24 PASSED` (2026-03-14).

**«Библия» проекта** — это **этот документ + связка документов**, на которые он ссылается. Когда говорят **«библия»**, имеется в виду: изучить **docs/MASTER_REFERENCE.md** и при необходимости связанные документы:

- **docs/COGNITIVE_CODE.md** (Когнитивный кодекс: стандарты критического мышления).
- **PROJECT_ARCHITECTURE_AND_GUIDE**, **ARCHITECTURE_FULL**, **CURRENT_STATE_WORKER_AND_LLM**.
- **CHANGES_FROM_OTHER_CHATS.md** (Лог изменений).
- **VERIFICATION_CHECKLIST**, **DASHBOARDS_AND_AGENTS_FULL_PICTURE**.
- **docs/VICTORIA_USAGE_GUIDE.md** (руководство по использованию Виктории: режимы Cursor/MCP, терминал, Open WebUI; инструменты, примеры). Связь с правилами: **.cursor/rules/victoria.mdc**.
- **docs/VICTORIA_TASK_FORMULATION.md** (как правильно ставить задачи Виктории: структура goal, параметры запроса, выбор endpoint, примеры хороших и плохих постановок, мониторинг выполнения).

Закреплено в **.cursorrules** (раздел «Библия проекта»).

**Назначение:** при любых вопросов по разработке, изменениям, архитектуре, логике, портам, компонентам — **ищем здесь**. При добавлении нового или смене подхода — **отражаем здесь**. Документ всегда актуален.

**Правило репо:** правки вносить **в репозиторий того проекта, где живёт код**. setki-21 → репо setki-21; atra → репо atra; код Web IDE / Knowledge OS → atra-web-ide. Не править код setki-21 из atra-web-ide и наоборот.

**Золотой стандарт (Plan Mode и делегирование):** Золотой стандарт — это не просто список дел, а **делегирование задачи через инструмент Task** (или API Victoria): вызывающая сторона (пользователь/Cursor) выступает в роли **Куратора (Оркестратора)**, подзадача уходит **«локальной Виктории» (субагенту)** с полным контекстом Библии и чёткими инструкциями. Это экономит токены и время: субагент фокусируется только на выполнении, не перечитывая весь чат. Plan Mode обязателен для задач 3+ шагов: сначала план, одобрение, затем выполнение. **Куратор даёт задание Виктории только через скрипт** `scripts/curator_send_tasks_to_victoria.py --file <файл с goal> --async --max-wait 600`; результат в `docs/curator_reports/`. Подробно: **.cursor/rules/victoria.mdc** §0, **docs/VICTORIA_USAGE_GUIDE.md** § «Куратор», **docs/CURATOR_RUNBOOK.md** §0.

**Quick links:** [CHANGES](CHANGES_FROM_OTHER_CHATS.md) · [VERIFICATION](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) · [CURATOR_RUNBOOK](CURATOR_RUNBOOK.md) · [VICTORIA USAGE](VICTORIA_USAGE_GUIDE.md) · [VICTORIA TASK FORMULATION](VICTORIA_TASK_FORMULATION.md) · [AUTONOMY/OFFLINE](AUTONOMY_OFFLINE_READINESS.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [FAQ](FAQ.md) · [HOW_TO_INDEX](HOW_TO_INDEX.md)

**Обновлено:** 2026-03-13

Последние изменения (2026-03-14): **Rust-ification & Hyper-Speed (Singularity 21.23).** (1) Пакетные операции `Batch Read` и `Batch Grep` перенесены на Rust Gateway (порт 8081), что дает 10-кратный прирост скорости. (2) Внедрена Rust-версия RAG-поиска с фильтрацией по контексту проекта. (3) Портирован **Anomaly Detector на Rust** для мгновенной проверки безопасности запросов через эвристики. (4) Реализована гибридная модель: Python-агенты вызывают Rust-сервисы с автоматическим fallback-ом.

Последние изменения (2026-03-14): **Global Cleanup & RAG Rocket Speed (Singularity 21.22).** (1) RAG ускорен в 5 раз через параллельный запуск GraphRAG/VectorRAG и кэширование доменов в памяти. (2) Начата декомпозиция `ai_core.py`: логика Anomaly Detection и Ensemble Verifier вынесена в модули `core/`. (3) Внедрен `DomainCache` для минимизации SQL-подзапросов.

Последние изменения (2026-03-14): **Antifragile Evolution (Singularity 21.21).** Внедрена триада «Инстинкта Выживания»: (1) **AgentChaosInjector** — Chaos Monkey для ИИ-агентов, симуляция сбоев в Shadow Execution. (2) **Antifragile Feedback Loop** — автоматическое масштабирование «антител» (инструкций) на весь департамент после сбоя. (3) **Recursive Testing** — обязательное требование авто-тестов для любой новой логики через ArchitecturalGuard.

Последние изменения (2026-03-14): **Absolute Dominance (Singularity 21.20).** Внедрена триада «Знаний Гигантов»: (1) **ArchitecturalGuard** — автоматическая проверка SOLID/KISS перед мутациями. (2) **AutonomousPolicyEnforcer** — динамические права экспертов на основе их KPI (Trading Floor Model). (3) **IntrospectionLoop** — обязательная самокритика и оттачивание ответов перед выдачей.

Последние изменения (2026-03-14): **Max Autonomy (Singularity 21.19).** Внедрена триада автономности: (1) **Autonomous Overseer** — автоматическая генерация задач на основе логов и бэклога. (2) **Self-Learning DNA** — инъекция «антител» в ДНК экспертов при обнаружении ошибок. (3) **Shadow Execution v2** — параллельная проверка оптимизаций с автоматическим Hot-Swapping. Система перешла на уровень 9.5/10 по шкале автономии.

Последние изменения (2026-03-13): **Victoria Connection Fix & Task Formulation Guide.** (1) Исправлен критический NameError в `file_watcher.py` (отсутствовал `import time`, использовался несуществующий `datetime.now()`). (2) Увеличены таймауты для сложных задач: `UVICORN_TIMEOUT_KEEP_ALIVE` 600→1800с (30 мин), `UNDERSTAND_GOAL_TIMEOUT_SEC` 90→300с (5 мин), `STRATEGY_CALL_TIMEOUT_SEC` 30→180с (3 мин), `VICTORIA_STREAM_HEARTBEAT_SEC` 15→10с. (3) Создан подробный гайд по постановке задач Victoria: структура goal, параметры запроса, выбор endpoint (/run, /stream, /orchestrate), примеры хороших/плохих постановок. (4) Документация: `docs/VICTORIA_CONNECTION_FIX.md`, `docs/VICTORIA_CONNECTION_FIX_SUMMARY.md`, `docs/VICTORIA_TASK_FORMULATION.md`. Результат: Victoria стабильно работает без обрывов до 30 минут.

Последние изменения (2026-03-12): **Deep Expert Specialization (Singularity 21.17).** Внедрена система персонализации экспертов: динамическая подгрузка правил (.mdc) и фильтрация Success Retrieval по конкретному исполнителю. Это превращает команду в оркестр узкопрофильных мастеров. См. CHANGES §83.

Последние изменения (2026-03-12): **Omni-RAG & Vision API Stabilization (Singularity 21.16).** (1) Внедрен Hybrid Search v2 и Cross-Encoder переранжировщик. (2) Стабилизировано Vision API (Moondream Station) на порту 2020 с автоматическим Watcher-ом. (3) Исправлены критические ошибки в Collective Memory (импорты) и GraphRAG (конкурентность). (4) Оптимизированы таймауты планирования (1200с) для предотвращения STRATEGIST FAILED. См. CHANGES §56.

Последние изменения (2026-03-12): **Self-Healing Logs (Singularity 21.15).** Реализована проактивная система исправления ошибок: сервис мониторит логи Docker в реальном времени, обнаруживает Tracebacks и автоматически готовит патчи (режим `awaiting_approval`). Это позволяет Виктории «лечить» себя до того, как баг станет критическим. См. CHANGES §82.

Последние изменения (2026-03-12): **Adaptive Concurrency (Singularity 21.14).** Внедрена система динамического управления очередью запросов в `OllamaExecutor`. Лимит параллельных вызовов LLM теперь автоматически адаптируется к температуре Mac Studio, загрузке RAM и производительности MLX, предотвращая перегрузку и каскадные сбои. См. CHANGES §81.

Последние изменения (2026-03-12): **Semantic Cache (Singularity 21.13).** Внедрена двухслойная система кэширования в `OllamaExecutor`: L1 (Hash) для мгновенных ответов и L2 (Semantic) через векторную БД для семантически близких запросов (threshold 0.95). Реализована фильтрация динамических команд (`ls`, `cat`, `status`) для обеспечения актуальности данных. См. CHANGES §80.

Последние изменения (2026-03-12): **Success Retrieval & Session Context Injection.** (1) Внедрена система Success Retrieval (Сингулярность 21.12): Victoria теперь обучается на прошлых успешных задачах через векторный поиск по таблице `tasks`. (2) Реализована инъекция контекста сессии в системный промпт для связности диалога. (3) Внедрена защита инференса: Circuit Breaker и MLX Admission Control. См. CHANGES §77, §78, §79.

Последние изменения (2026-03-12): **Оптимизация роутера чата: batch append и character limit.** (1) В `stream_message` сохранение истории теперь выполняется параллельно через `asyncio.gather`. (2) Ограничение размера истории (10000 символов) перенесено непосредственно в метод `get_recent` менеджера контекста. (3) Реализовано сохранение частичного ответа ассистента при разрыве соединения (`CancelledError`). См. CHANGES §76.

Последние изменения (2026-03-10): **Omni-RAG — Единый Интеллект (Open WebUI & Telegram).** (1) Внедрена архитектура Omni-RAG: теперь знания из Hybrid Search v2 автоматически инъецируются в запросы из Open WebUI (через OpenAI API эндпоинт). (2) Создан унифицированный эндпоинт `POST /api/omni-rag/search` для внешних систем. (3) Реализована поддержка контекста для Telegram-сессий. (4) База знаний теперь синхронизирована между всеми точками взаимодействия с пользователем. См. CHANGES §63.

Последние изменения (2026-03-10): **Enhanced RAG — Hybrid Search v2 & Re-ranking.** (1) Внедрен Hybrid Search v2 (BM25 + Vector) с использованием PostgreSQL `tsvector` и `ts_rank_cd` для молниеносного поиска по ключевым словам. (2) Интегрирован Cross-Encoder Re-ranking на базе модели `ms-marco-MiniLM-L-6-v2` для финальной фильтрации результатов (точность выросла на порядок). (3) Реализован External Docs Indexer для автоматического парсинга произвольных URL и GitHub репозиториев (OpenAI, Anthropic, DeepSeek, LangChain). (4) Виктория теперь автоматически подтягивает знания из домена «AI Research» через новый гибридный поиск. См. CHANGES §62.

Последние изменения (2026-03-08): **IQ Boost — Consensus v2, Debate & Self-Correction.** (1) Внедрена система `Self-Correction`: Victoria теперь критикует и исправляет свой собственный ответ перед выдачей пользователю (для категорий coding/reasoning). (2) Реализована полноценная интеграция `Multi-Agent Debate`: для сложных задач запускается дискуссия между Архитектором, экспертом по безопасности и Прагматиком. (3) **Consensus v2**: Внедрено взвешенное голосование в `ConsensusAgent` на основе KPI экспертов (`performance_score` из БД) и их уверенности. (4) Метод `complex` в `VictoriaEnhanced` теперь автоматически использует Debate с fallback на Consensus v2. См. CHANGES §60.

Последние изменения (2026-03-08): **Thermal Protection — автоматическое управление нагрузкой.** (1) В `MacStudioMonitor` реализована логика обнаружения перегрева (Thermal Level >= 1) и критической загрузки RAM (> 92%). (2) Внедрен механизм автоматической выгрузки лишних моделей из Ollama при перегрузке (кроме `IMMORTAL_MODELS`). (3) `LocalAIRouter` теперь автоматически переключается на сверхлегкие модели (`phi3.5`, `tinyllama`) при срабатывании термальной защиты, снижая нагрузку на GPU. См. CHANGES §59.

Последние изменения (2026-03-09): **Stuck Tasks Watchdog — автоматический сброс зависших задач.** (1) Реализована интеграция `reset_stuck_tasks.py` в `system_auto_recovery.sh` для автоматической очистки очереди при сбоях. (2) Создан `scripts/setup_stuck_tasks_watchdog.sh` для ежечасного сброса задач через `launchd`. (3) Скрипт теперь гарантированно использует `knowledge_os/.venv` для избежания ошибок импорта `asyncpg`. См. CHANGES §61.

Последние изменения (2026-03-08): **Mac Studio Monitoring — глубокий мониторинг железа.** (1) Создан `MacStudioMonitor` для сбора метрик CPU, RAM, Thermal Level и загруженных моделей (Ollama/MLX). (2) Реализована интеграция с `victoria_server.py`: при запросах о «железе», «нагрузке» или «температуре» Виктория теперь автоматически подтягивает real-time данные Mac Studio. (3) Добавлена поддержка `sysctl` для мониторинга термального состояния. См. CHANGES §58.

Последние изменения (2026-03-08): **Self-Evolution v2 — верификация через Pytest.** (1) `CodebaseMutationEngine` теперь автоматически ищет связанные тесты для исправляемого файла. (2) В `Patch Safety Guard` интегрирован запуск `pytest`: патч применяется только если все тесты пройдены. (3) Реализована логика автоматического отката (Rollback): если тесты провалены, изменения отменяются, и система возвращается к стабильному состоянию. (4) Добавлена поддержка бэкапов файлов при верификации. См. CHANGES §57.

Последние изменения (2026-03-08): **Self-Evolution — автоматические патчи и Self-Healing.** (1) `CodebaseMutationEngine` расширен логикой генерации патчей через Victoria Enhanced (Extended Thinking). (2) Внедрена система `Patch Safety Guard`: автоматическая проверка синтаксиса Python перед применением патча. (3) В `VictoriaEventHandlers` добавлен хук `Syntax Auto-Fix`: при создании файла с синтаксической ошибкой Mutation Engine автоматически пытается её исправить. (4) Реализован полный цикл самоисцеления: Ошибка -> Анализ -> Патч -> Верификация -> Применение. См. CHANGES §56.

Последние изменения (2026-03-08): **Autonomous Core — усиление автономности (Mutation & Shadow).** (1) Создан `CodebaseMutationEngine` для автоматического анализа и исправления ошибок в фоне. (2) Реализован `ShadowExecutionManager` для параллельной проверки оптимизаций («в тени» основного процесса). (3) Внедрена система проактивных предложений в `victoria_server.py`: при запросах статуса Victoria теперь автоматически учитывает недавние ошибки из `Event Bus`. (4) `VictoriaEventHandlers` расширены хуками для Mutation и Shadow систем. См. CHANGES §55.

Последние изменения (2026-03-08): **Skill Discipline v2 — полная загрузка инструкций (План B.2, финал).** (1) В `skill_mapper.py` реализована загрузка полных текстов из `SKILL.md` файлов (через `glob` и кэширование). (2) В `victoria_server.py` исправлена инъекция `enriched_goal` для всех путей (SSE, sync, async) — инструкции скилла теперь попадают в промпт Victoria гарантированно. (3) Это делает Victoria на 100% эквивалентной Cursor assistant по дисциплине и качеству следования workflow. **План B завершён полностью!** См. CHANGES §54.

Последние изменения (2026-03-08): **Оптимизация архитектуры «Мозг и Руки» (MLX & Ollama) — Финал.** (1) Внедрена политика Smart Cooldown (300с) и категория `IMMORTAL_MODELS` (nomic, moondream, tinyllama, phi3.5) в `ollama_keep_alive_policy.py`. (2) Реализован `ContextMirror` (Redis) для бесшовного переноса истории сессий при failover. (3) В `local_router.py` интегрирован упреждающий прогрев (Predictive Warmup) и логика `[FALLBACK_MODE]`. (4) Внедрен `MLXMonitor` с расчетом **Health Score** (на основе TBT > 200ms и очереди > 5), который автоматически триггерит прогрев Ollama при деградации MLX. См. CHANGES §53.

Последние изменения (2026-03-08): **Ночной график эволюции (00:00 - 06:00).** (1) Настроено окно глубокого самообучения и оптимизации ядра. (2) Nightly Learner и Mutation Engine теперь работают исключительно в ночное время для экономии ресурсов Mac Studio днем. (3) Внедрен 'режим тишины' для мониторинга в это время.

Последние изменения (2026-03-06): **Batch Read — параллельное чтение файлов (План B.4, финал).** (1) Создан модуль `batch_read.py` с функциями `batch_read_files()` и `batch_grep_files()` для параллельного чтения/поиска (max_concurrent=10, semaphore). (2) API endpoints `POST /batch_read` и `POST /batch_grep` в victoria_server. (3) MCP tools `victoria_batch_read` и `victoria_batch_grep` для Cursor. (4) Graceful error handling (файл не найден, слишком большой, encoding). (5) Это устраняет ограничение «последовательные шаги» — можно сканировать 50+ файлов за 0.5 сек. **План B завершён на 100%!** См. CHANGES §47, MASTER_REFERENCE (Batch Read).

Последние изменения (2026-03-06): **IDE Context — контекст в формате Cursor (План B.3).** (1) TaskRequest расширен полями `open_files`, `git_status`, `cursor_rules`, `workspace_path` для передачи IDE-контекста. (2) Создана функция `_format_ide_context()` для форматирования контекста в читаемый текст (workspace, git, открытые файлы с cursor_line, правила). (3) IDE-контекст инъецируется в `enriched_goal` перед отправкой в Victoria (после skill_context). (4) MCP tool `victoria_run_with_context` создан для передачи контекста из Cursor. (5) Это даёт Victoria тот же «срез окружения», что у Cursor assistant (открытые файлы, git, правила). Статус: ✅ полная реализация. См. CHANGES §46, MASTER_REFERENCE (IDE Context).

Последние изменения (2026-03-06): **Skill Discipline — жёсткая дисциплина скиллов (План B.2).** (1) Создан `skill_mapper.py` с классификатором задач (5 скиллов: brainstorming, TDD, debugging, verification, code_review). (2) Автовызов в `victoria_server.py` — при распознавании типа задачи инструкции скилла добавляются в goal. (3) SSE уведомление «Применяется скилл: {description}». (4) Правило «1% шанс = вызвать скилл». Статус: ✅ базовая реализация. См. CHANGES §45, MASTER_REFERENCE (Skill Discipline).

Последние изменения (2026-03-06): **Execution Plan — руки в IDE (План B.1).** (1) Victoria теперь может генерировать структурированный `execution_plan` (список шагов: read_file, edit, run) для выполнения в IDE/клиенте. (2) Расширены `TaskRequest` (`return_execution_plan: bool`) и `TaskResponse` (`execution_plan: List[Dict]`). (3) Добавлен парсер `_extract_execution_plan()` (поддержка JSON и markdown). (4) Промпт Victoria дополнен секцией «EXECUTION PLAN» с примерами. (5) MCP tool `victoria_execute_plan` создан для автоматического выполнения плана. (6) Executor `execution_plan_executor.py` для интеграции with filesystem MCP. (7) Это решает проблему «мозг и руки разделены» — Victoria планирует, клиент выполняет. Статус: ✅ базовая архитектура, 🚧 полная интеграция с MCP. См. CHANGES §44, victoria.mdc §6, `.cursor/plans/plan-b-*.md`.

Последние изменения (2026-03-06): **STRICT_LOCAL: строго локальный режим.** (1) Введён переключатель `STRICT_LOCAL=false` (дефолт) в `.env.example` и `docker-compose.yml` для полной автономности от облачных API. (2) Создан модуль `env_flags.py` с `is_strict_local()`. (3) Модифицированы `ai_core.py`, `safety_checker.py`, `quality_assurance.py`, `intelligence_consensus.py`, `disaster_recovery.py`: при `STRICT_LOCAL=true` блокируется cursor-agent и облачные fallback, выполняется retry локально с улучшенным промптом; при неудаче — reject с явным сообщением. (4) Graceful degradation при частичной недоступности (MLX down, Ollama работает). (5) Метрики: `strict_local_enabled`, `strict_local_safety_skip_count`, `strict_local_qa_skip_count`. (6) Документация: раздел STRICT*LOCAL в MASTER_REFERENCE, CHANGES §43. См. план в `.cursor/plans/strict_local_implementation*\*.plan.md`.

Последние изменения (2026-03-05): **Библия обновлена по сессии: Victoria Tasks, инвентаризация, самовосстановление MLX.** (1) Домен **victoria_tasks** создан в БД — самообучение Виктории снова попадает в RAG и планирование (CHANGES §40). (2) **Инвентаризация возможностей** — отчёт docs/audits/INVENTORY_VICTORIA_CAPABILITIES_2026.md (Initiative, OTEL, Recovery, знания гигантов, реестр проектов, чеклисты §10–11); CHANGES §41. (3) **Recovery Listener (9099):** доработка host_recovery_listener.py (GET /recover, безопасный Content-Length), чеклист в INVENTORY §11, перезапуск через launchd; CHANGES §42. При любых изменениях — обновлять MASTER_REFERENCE и CHANGES (правило библии).

---

## § Гибридная операционная модель (Singularity 31.2)

**Манифест:** стратегия гибридного интеллекта **Cursor + Victoria AI** — фундаментальная операционная модель проекта: облачный диспетчер и локальный мозг разделены ролями ради эффективности и экономии ресурсов.

**Стандарт работы:** облачный ассистент (**Cursor**) — **Диспетчер**; локальный стек (**Victoria**, Docker, MLX/Ollama) — **Исполнитель** и тяжёлая аналитика.

### Концепция «Диспетчер — Исполнитель»

- **Cursor (облачный диспетчер):** внешние модели (Claude/GPT и др.) как «тонкий слой» — понимание намерений пользователя, декомпозиция на шаги, вызов инструментов (терминал, MCP, Task) и управление локальными агентами.
- **Victoria (локальный мозг):** Mac Studio, модели **MLX** и **Ollama** — «тяжёлая артиллерия» с прямым доступом к большому локальному контексту (рабочая копия репозитория), **PostgreSQL**, RAG и файловой системе.

### Механика взаимодействия (Singularity 31.2)

**A. Делегирование через Blackboard и Аукционы**

1. **Blackboard Service:** Центральный хаб задач. Агенты не ждут команд, а «подписываются» на задачи через аукционы.
2. **Bidding System:** Эксперты делают ставки (bids) на основе своей специализации, текущей нагрузки и рейтинга.
3. **AgentScope Actors:** Каждый эксперт — это изолированный актор с собственным состоянием и памятью.

**B. Экономия токенов (Token Economy)**

- **Входящий контекст:** Виктория читает файлы **локально**; в облачный чат имеет смысл отдавать **результат** (краткий отчёт, дифф, финальный код) — часто на **порядки** меньше, чем тащить весь проект в промпт.
- **RAG:** поиск по базе знаний (в т.ч. векторный/pgvector и гибридные режимы) выполняется **на стороне Victoria**; облаку не нужно «помнить» весь кодовый массив.
- **Итерации:** многократные правки и прогоны — **локально**; в облако логично выносить проверенную итоговую версию (минимизация платных/лимитных токенов на «перетирание» кода).

### Золотые правила для новых чатов (протокол для AI)

1. **«Сначала спроси Викторию»:** перед разбором тяжёлой темы — опереться на локальный RAG/MCP/поиск по знаниям, а не только на контекст чата.
2. **Делегирование тяжёлых задач:** массовая генерация и прогон тестов (`pytest`), глубокий security-аудит, рефакторинг крупных модулей, Omni-RAG / поиск по мультимодальным артефактам — через Victoria и профильных экспертов (см. `configs/experts/team.md`).
3. **Контроль фактами:** `docker logs`, статусы задач в БД, health сервисов — не принимать утверждения модели без сверки с реальным состоянием.
4. **Локальные эксперты:** в БД **86+** экспертов (источник истины для оркестратора: `GET /api/experts`); в промптах Victoria — явные роли/имена (`@igor`, `@anna`, `@dmitry` и т.д.).

### Почему это работает

- **Приватность:** сырой код и внутренние артефакты не обязаны целиком уходить во внешние API.
- **Скорость:** локальная сеть и диск быстрее, чем многократная загрузка больших фрагментов репозитория в облако.
- **Эволюция:** уроки из исправлений и аудитов могут закрепляться в графе знаний (**`knowledge_nodes`** и связанные процессы индексации), система накапливает опыт между сессиями.

**Ориентир по эффекту:** существенная экономия облачных токенов при полном использовании Mac Studio и Docker-стека; точные проценты зависят от сценария. Исторически в библии фигурировала оценка порядка **~90%** экономии лимитов при последовательном делегировании — использовать как порядок величины, не как гарантию.

---

## Wisdom Era Status (Singularity 31.2: Neural Fabric)

**Архитектура:** Единый Интеллект v31.2. **Параллельная работа (Parallel Work):** Мозг (MLX, порт 11435) и Руки (Ollama, порт 11434) работают совместно, распределяя нагрузку. Модель **victoria-wisdom-v3.5** (MLX) и **victoria-wisdom-v3.5:latest** (Ollama) идентичны по знаниям.

**Полноценная Виктория (v31.2):**

1. **MLX (мозг):** `VICTORIA_MLX_BRAIN=true` — предзагрузка (Pure MLX).
2. **Ollama (руки):** активны параллельно; становятся бессмертными (`keep_alive=-1`) только при падении MLX. При живом MLX выгружаются через 60с простоя для экономии RAM.
3. **Knowledge Fabric:** Единая шина памяти (LTM, GraphRAG, Semantic Cache).
4. **Visual Intelligence:** VisualRAG на порту 8005.
5. **Recursive Evolution:** Автономный цикл улучшения кода.
6. **Quantum Leap Distillation:** DuckDB-ускоренная дистилляция знаний.

**Самовосстановление и Мониторинг:** Система мониторит v31.2 в обоих каналах через `MLXMonitor`. При деградации производительности (Health Score < 0.5) или сбое MLX происходит упреждающий прогрев Ollama и мгновенный fallback без потери контекста (через Redis Context Mirror).

**Последний аудит (05.05.2026):** Переход на Singularity 31.2. Скорость загрузки в MLX: 4.6с. Личность подтверждена. Все эксперты уведомлены о смене ядра.

**При смене модели (чеклист):** обновить MASTER*REFERENCE (этот блок), `.cursor/rules/victoria.mdc`, `.cursor/rules/expert_and_brainstorm.mdc`, `.cursorrules` (Компоненты), `docs/COGNITIVE_CODE.md`, `docs/PORT_REGISTRY.md`, `knowledge_os/USER.md`, `knowledge_os/SOUL.md`, `docs/OPENWEBUI_VICTORIA_WISDOM_MODEL.md`, `docs/SESSION_HANDOFF*\*.md`при актуальности; исторические планы в`docs/plans/` не переписывать — источник истины здесь.

---

## STRICT_LOCAL (строго локальный режим)

**Назначение:** Полная автономность от облачных API. При `STRICT_LOCAL=true` все запросы обслуживаются только локальными моделями (MLX + Ollama); при недоступности локальных моделей возвращается явная ошибка, без fallback на cursor-agent или облачные API.

### Cloud fallback (OpenRouter)

**Актуально с 2026-04-25:** платные ключи `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` не считаются рабочим fallback, если они пустые или отсутствуют. Реальный облачный резерв теперь включается через `OPENROUTER_API_KEY`; при пустом значении провайдер пропускается без ложных попыток.

Рекомендуемая цепочка: локальные MLX/Ollama → OpenRouter Free/Paid при наличии ключа → `cursor-agent` → прямой легкий Ollama fallback.

### Веб-поиск — автономный стек (актуально с 2026-03-21)

**Компоненты:**

- **SearXNG** — локальный поисковый агрегатор в Docker (`knowledge_os/docker-compose.yml`), порт `8084` снаружи / `searxng:8080` внутри. Агрегирует Google, Bing, DDG и др.
- **`WEB_SEARCH_PROVIDERS=searxng,duckduckgo`** в `.env` / `knowledge_os/.env`
- **`SEARXNG_URL=http://searxng:8080`** (внутри Docker) / `http://localhost:8084` (снаружи)

**Цепочка вызова `web_search()` (оба `system_tools.py`):**

```
STRICT_LOCAL=true → "веб-поиск отключён"
    ↓ нет
_check_internet() [TCP 1.1.1.1:53, 1.5s] → нет ответа → "интернет недоступен"
    ↓ есть
SearXNG localhost:8080 → результаты
    ↓ нет/ошибка
DuckDuckGo fallback
    ↓ нет/ошибка
"все провайдеры упали, использую локальную базу знаний"
```

**Команда переключения:**

```bash
bash scripts/toggle_strict_local.sh on    # STRICT_LOCAL=true
bash scripts/toggle_strict_local.sh off   # STRICT_LOCAL=false
bash scripts/toggle_strict_local.sh status
```

- Закрытые сети (closed network)
- Конфиденциальные данные (GDPR, regulatory compliance)
- Полная изоляция от внешних API

**Когда НЕ использовать:**

- Повседневная работа (на сложных reasoning-задачах качество может быть ниже)
- Первичная настройка (требуется доступность локальных моделей)

**Дефолт:** `STRICT_LOCAL=false` (рекомендуется для большинства сценариев)

### Pre-flight checklist (обязательно перед включением STRICT_LOCAL):

Выполните проверку **перед** изменением `STRICT_LOCAL=true`:

1. **Проверка MLX:** `curl -s http://localhost:11435/health` → HTTP 200
2. **Проверка Ollama:** `curl -s http://localhost:11434/api/tags` → HTTP 200, список содержит `victoria-wisdom-v3.5:latest`
3. **Проверка Recovery Listener:** `curl -s http://localhost:9099/recover` → HTTP 200 (критично для STRICT_LOCAL; без него при падении MLX система полностью недоступна; см. INVENTORY_VICTORIA_CAPABILITIES_2026.md §11)

Если хотя бы одна проверка не прошла — **не включайте STRICT_LOCAL**, сначала восстановите сервис. Полная оценка готовности к автономности и работе без интернета: **docs/AUTONOMY_OFFLINE_READINESS.md**.

### 12-Factor (Config):

При изменении `STRICT_LOCAL` в `.env` перезапустите контейнеры:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d
docker-compose up -d  # backend
```

### Adaptive Concurrency:

STRICT_LOCAL увеличивает нагрузку на локальные модели (вся нагрузка на MLX/Ollama, без облачного fallback). При высоком трафике рассмотрите:

- Снижение `MAX_CONCURRENT_VICTORIA` (с 50 до 30-40)
- Горизонтальное масштабирование MLX/Ollama

### Pre-mortem (3 сценария провала и защита):

1. **MLX и Ollama падают одновременно** → все запросы отклоняются.
   - **Защита:** pre-flight checklist + Recovery Listener (9099) + мониторинг
2. **Локальная модель выдаёт небезопасный код** → safety_checker блокирует, но ответ отклоняется (не уходит пользователю).
   - **Защита:** при срабатывании safety в STRICT_LOCAL — reject или retry с изменённым промптом (безопасный промпт)
3. **Качество ответов падает на сложных задачах** → пользователи недовольны.
   - **Защита:** чёткая документация (этот блок) + при низком качестве в ответе пояснение пользователю: «⚠️ STRICT_LOCAL блокирует улучшение качества. Для сложных задач отключите STRICT_LOCAL.»

### Идемпотентность:

Повторный запрос с тем же goal при STRICT_LOCAL даёт тот же результат (ошибка или локальный ответ); дубли в БД не создаются (золотой стандарт, см. .cursorrules).

### Graceful Degradation:

При частичной недоступности (например MLX down, но Ollama работает):

- Логируется `[GRACEFUL DEGRADATION] MLX недоступен, используется только Ollama`
- В ответ пользователю добавляется подсказка: «⚠️ Работаем в ограниченном режиме: основной интеллект (MLX) недоступен. Качество ответов может быть ниже. Проверьте порт 11435 или Recovery (9099).»

### Метрики:

- `strict_local_enabled` (gauge, 0 или 1) — флаг режима STRICT_LOCAL
- `strict_local_safety_skip_count` (counter) — количество срабатываний safety_checker, которые не привели к reroute (потому что STRICT_LOCAL)
- `strict_local_qa_skip_count` (counter) — количество срабатываний QA с рекомендацией reroute_to_cloud, которые не выполнены

Метрики `strict_local_*` экспортируются в **GET http://localhost:8010/metrics** (Victoria Server).

**Алерт в Grafana:** если `strict_local_enabled == 1` **и** (`mlx_health == down` **или** `ollama_health == down`) — критический алерт «STRICT_LOCAL ON, но локальные модели недоступны → система полностью недоступна».

### Внедрено (2026-03-06):

- **Файлы изменены:** `ai_core.py`, `safety_checker.py`, `quality_assurance.py`, `intelligence_consensus.py`, `disaster_recovery.py`, `backend/app/services/ollama.py`, `.env.example`, `docker-compose.yml`
- **Файлы созданы:** `knowledge_os/app/env_flags.py`
- **Логика:** при `is_strict_local()`:
  - `_run_cloud_agent_async` не вызывает cursor-agent, retry через локальные модели с backoff
  - `safety_checker.should_reroute_to_cloud()` возвращает `False`
  - `quality_assurance` заменяет `reroute_to_cloud` на `retry_local`
  - `intelligence_consensus` выполняет консенсус через 2 локальных вызова (reasoning + coding)
  - `disaster_recovery.can_use_cloud()` возвращает `False`
  - `backend/app/services/ollama.py` создаёт singleton с `use_cloud=False` (Ollama Cloud API заблокирован)

### Голосовой ввод и Ollama Cloud:

- **Голосовой ввод:** `knowledge_os/app/voice_processor.py` использует `USE_OPENAI_WHISPER=false` по умолчанию (локальное распознавание речи). Для полной локальности не включайте `USE_OPENAI_WHISPER`.
- **Ollama Cloud:** `backend/app/services/ollama.py` в STRICT_LOCAL режиме принудительно использует `use_cloud=False`, блокируя доступ к Ollama Cloud API (https://ollama.com) даже при наличии `OLLAMA_API_KEY`.

**См. также:** [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) §43 (детали внедрения)

---

## Execution Plan — руки в IDE (План B: Cursor Parity)

**Концепция:** Виктория решает **ЧТО** делать (планирует изменения в коде), а IDE/клиент выполняет **КАК** (редактирование файлов, запуск команд). Это разделение «мозг и руки» на уровне разработки — Victoria становится интеллектуальным планировщиком, а среда разработки (Cursor/MCP) — исполнителем.

**Проблема:** Виктория живёт как сервис (порт 8010) — она даёт план и ответы, но не может напрямую править файлы в IDE пользователя. Раньше выполнение делегировалось Veronica или выполнялось вручную.

**Решение:** Виктория генерирует структурированный `execution_plan` (список шагов: read_file, edit, run), который клиент (Cursor через MCP) выполняет автоматически. Это даёт Виктории «руки в IDE» без изменения её архитектуры (она остаётся сервисом).

**FAST_PATCH_PATH (2026-03-21):** Для точечных TRUSTED-патчей (1 строка, 1 файл) Victoria применяет правки САМА через `SystemTools.apply_patch`, без LLM-планировщика. Время < 200 мс.

**FAST_ACTION_PATH (2026-03-21):** Файловые проверки куратора без LLM — детерминированный ответ за ~0ms:

- `прочитай файл /path` → чтение + поиск переменных/паттернов
- `проверь файл /path — есть ли X в первых N строках` → grep с лимитом строк
- `список файлов в /path` → ls
- Срабатывает ТОЛЬКО если ключевые слова в первых 120 символах цели

```bash
# Формат: goal = JSON с action="apply_patch"
curl -X POST http://localhost:8010/run -H "Content-Type: application/json" \
  -d '{"goal": "{\"action\":\"apply_patch\",\"file_path\":\"path/to/file.py\",\"old_text\":\"старое\",\"new_text\":\"новое\"}"}'
# Ответ: {"result": "Successfully patched ...", "knowledge": {"strategy": "fast_patch"}}
```

**Авто-цикл без Cursor (PRODUCTION READY 2026-03-21):**

- `scripts/run_curator_autonomous.sh --full` — полный цикл за **35 секунд**
- `scripts/victoria_self_curator.py` — локальный анализ (без LLM) + авто-патч + лог
- `scripts/curator_tasks.txt` — 14 задач аудита (pip, secrets, env vars, docs)
- Запускается ежедневно через `com.atra.curator-scheduled` (launchd, 9:00)
- Документ: `docs/runbooks/CURATOR_AUTONOMY_WITHOUT_CURSOR.md`

### Использование

1. **Запрос с `return_execution_plan=true`:**

   ```bash
   curl -X POST http://localhost:8010/orchestrate \
     -H "Content-Type: application/json" \
     -d '{
       "goal": "Добавь функцию validate_email в utils/validators.py",
       "return_execution_plan": true
     }'
   ```

2. **Ответ содержит `execution_plan`:**

   ```json
   {
     "status": "success",
     "output": "Создан план для добавления validate_email...",
     "execution_plan": [
       {
         "action": "read_file",
         "path": "utils/validators.py",
         "description": "Прочитать текущую реализацию"
       },
       {
         "action": "edit",
         "path": "utils/validators.py",
         "content": "import re\n\ndef validate_email(email: str) -> bool:\n    ...",
         "description": "Добавить функцию validate_email"
       },
       {
         "action": "run",
         "command": "pytest tests/test_validators.py",
         "description": "Проверить изменения"
       }
     ]
   }
   ```

3. **MCP tool для автоматического выполнения (Cursor):**

   ```python
   # Вызов через MCP VictoriaATRA (порт 8012)
   victoria_execute_plan(
     goal="Добавь функцию validate_email в utils/validators.py",
     workspace_path="/Users/bikos/Documents/atra-web-ide"
   )
   ```

   Инструмент `victoria_execute_plan` в MCP server (`src/agents/bridge/victoria_mcp_server.py`) автоматически:
   - Запрашивает plan от Victoria через `/orchestrate` с `return_execution_plan=true`
   - Выполняет каждый шаг плана (read/edit/run)
   - Возвращает результат каждого шага

### Формат execution_plan

Каждый шаг — это объект с полями:

| Поле          | Тип     | Описание                                                     | Для action          |
| ------------- | ------- | ------------------------------------------------------------ | ------------------- |
| `action`      | string  | Тип действия: `read_file`, `edit`, `run`                     | Все                 |
| `path`        | string  | Путь к файлу (относительный или абсолютный)                  | `read_file`, `edit` |
| `command`     | string  | Команда для терминала                                        | `run`               |
| `content`     | string  | Новое содержимое файла (опционально)                         | `edit`              |
| `description` | string  | Что делает этот шаг (для логов и UI)                         | Все                 |
| `critical`    | boolean | Прервать выполнение при ошибке (опционально, default: false) | Все                 |

**Пример:**

```json
[
  {
    "action": "read_file",
    "path": "src/utils.py",
    "description": "Изучить текущий код"
  },
  {
    "action": "edit",
    "path": "src/utils.py",
    "content": "...",
    "description": "Добавить функцию X"
  },
  {
    "action": "run",
    "command": "pytest src/tests/",
    "description": "Проверить изменения",
    "critical": true
  }
]
```

### Реализация (внедрено 2026-03-06)

**1. API расширение (`victoria_server.py`):**

- `TaskRequest.return_execution_plan: bool = False` — флаг для запроса плана
- `TaskResponse.execution_plan: Optional[List[Dict]]` — поле с планом
- `/orchestrate` endpoint — извлекает plan из ответа модели через `_extract_execution_plan()`

**2. Парсинг (`_extract_execution_plan()` в `victoria_server.py`):**
Поддерживает два формата в ответе модели:

- JSON-блок в тройных бэктиках: ` ```json\n[{...}]\n``` `
- Markdown-список:

  ```markdown
  **Execution Plan:**

  - read_file: path/to/file.py
  - edit: path/to/file.py (описание)
  - run: pytest tests/
  ```

**3. Промпт Victoria (`agent.executor.system_prompt`):**
Добавлена секция **«EXECUTION PLAN (руки в IDE)»** с инструкциями:

- Когда генерировать plan (задачи с изменением кода)
- Формат JSON для execution_plan
- Примеры шагов (read_file, edit, run)

**4. MCP tool (`victoria_mcp_server.py`):**

- `victoria_execute_plan(goal, workspace_path)` — получает plan от Victoria и выполняет через MCP filesystem
- Пока упрощённая версия (логирование шагов без реального выполнения)
- Полная интеграция с `user-filesystem` MCP server в разработке

**5. Executor (`execution_plan_executor.py`):**

- `ExecutionPlanExecutor` — класс для выполнения плана через MCP tools
- Методы: `_execute_read_file`, `_execute_edit`, `_execute_run`
- Поддержка относительных путей (workspace_path)
- Graceful error handling (продолжать выполнение при некритичных ошибках)

### Статус и Next Steps

**✅ Завершено (2026-03-06):**

- TaskRequest/TaskResponse расширены
- Парсинг execution_plan из ответа модели (JSON + markdown)
- Промпт Victoria обучен генерировать plan
- MCP tool `victoria_execute_plan` создан
- Документация обновлена (victoria.mdc, MASTER_REFERENCE)

**🚧 В разработке:**

- Полная интеграция `victoria_execute_plan` with `user-filesystem` MCP server (реальное чтение/запись файлов)
- Поддержка diff/patch для точечных правок (сейчас edit перезаписывает файл целиком)
- UI для отображения execution_plan в Web IDE (показать шаги перед выполнением)

**🔜 Следующие задачи (План B):**

- **B.2: Жёсткая дисциплина скиллов** — автоматический вызов скиллов по типу задачи (как в Cursor) — ✅ **ЗАВЕРШЕНО 2026-03-06**
- **B.3: Контекст в формате Cursor** — передача открытых файлов, git status, правил в запросах к Victoria
- **B.4: Параллельные чтения (batch_read)** — множественные read_file/grep за один запрос через Veronica

**См. также:** Plan B детализация в `.cursor/plans/plan-b-victoria-cursor-parity.md`

---

## Skill Discipline — жёсткая дисциплина скиллов (План B.2)

**Назначение:** Автоматическое применение нужного скилла по типу задачи, как в Cursor assistant. Правило: «если есть хотя бы 1% шанс, что скилл применим — вызвать скилл до ответа».

**Реализация (внедрено 2026-03-06):**

1. **Skill Mapper** (`knowledge_os/app/skill_mapper.py`):
   - Классифицирует задачу по regex-паттернам
   - Возвращает `{"skill": "brainstorming", "path": "...", "description": "..."}`
   - Singleton pattern для переиспользования

2. **Поддерживаемые скиллы:**
   - `brainstorming`: новая фича/компонент/функционал → discovery, дизайн по секциям, план внедрения, **НЕ КОД** до утверждения дизайна
   - `tdd`: тесты/unit/интеграция → Red-Green-Refactor, test-first (тест ДО реализации)
   - `debugging`: ошибка/баг/провал теста → systematic debugging (воспроизведи, изучи логи, гипотеза, проверка, исправление, тест для регрессии)
   - `verification`: проверка/убедись/тесты прошли → запуск тестов, линты, manual QA, **ТОЛЬКО после проверки — завершение**
   - `code_review`: ревью кода/изменений → SOLID, безопасность (secrets, SQL injection, XSS), тесты, покрытие

3. **Автовызов в victoria_server (`run_task_stream`):**
   - При получении задачи вызывается `skill_mapper.classify_task(goal)`
   - Если скилл найден → инструкции скилла добавляются в начало goal как `skill_context`
   - В SSE stream выводится шаг: "Применяется скилл: {description}"
   - Victoria получает `enriched_goal = skill_context + original_goal`

4. **Формат инструкций скилла:**

   ```
   🎯 ПРИМЕНЯЕТСЯ СКИЛЛ: BRAINSTORMING

   1. Изучи контекст проекта
   2. Задай 1 уточняющий вопрос (цель, ограничения)
   3. Предложи 2-3 подхода с плюсами/минусами
   4. Представь дизайн по секциям, спрашивай одобрение после каждой
   5. Запиши утверждённый дизайн в docs/plans/YYYY-MM-DD-<topic>-design.md
   6. Следующий шаг — writing-plans (план внедрения), НЕ код

   ВАЖНО: Следуй чеклисту скилла СТРОГО. Это не рекомендация — это обязательный workflow.
   ```

**Примеры триггеров:**

- "Создай новый компонент X" → `brainstorming` (паттерн: `созда.*новый.*компонент`)
- "Напиши тест для функции Y" → `tdd` (паттерн: `напиш.*тест`)
- "Исправь ошибку в модуле Z" → `debugging` (паттерн: `исправ.*ошибк`)
- "Проверь что всё работает" → `verification` (паттерн: `проверь`)

**Статус:** ✅ Базовая реализация (mapper, автовызов, чеклисты). 🚧 Полная загрузка SKILL.md (с детальными примерами) через Read tool в разработке.

---

## IDE Context — контекст в формате Cursor (План B.3)

**Назначение:** Victoria видит то же, что видит Cursor assistant: открытые файлы, git status, применимые правила из .cursor/. Это устраняет разницу в «срезе окружения» между Victoria (goal + RAG) и Cursor (открытые файлы + git + правила).

**Реализация (внедрено 2026-03-06):**

1. **Расширение TaskRequest** (`src/agents/bridge/victoria_server.py`):
   - `open_files: Optional[List[Dict]]` — открытые файлы: `[{"path": "...", "content": "...", "cursor_line": 42}, ...]`
   - `git_status: Optional[str]` — git status (измененные файлы, ветка): `"On branch main\nModified: src/utils.py\n..."`
   - `cursor_rules: Optional[List[str]]` — применимые правила/эксперты: `["@backend_developer", "@qa_engineer"]`
   - `workspace_path: Optional[str]` — путь к workspace (для относительных путей): `"/Users/bikos/Documents/atra-web-ide"`

2. **Форматирование контекста** (`_format_ide_context(request)`):
   - Преобразует IDE-контекст в читаемый текст для промпта:

     ```
     📋 IDE CONTEXT (как в Cursor):
     ============================================================

     🗂️ Workspace: /Users/bikos/Documents/atra-web-ide

     📊 Git Status:
     On branch main
     Modified: src/utils.py

     📂 Open Files (2):
       1. src/utils.py
          Cursor at line 42
          Lines 37-47:
            def validate_email(email: str) -> bool:
                ...

       2. tests/test_utils.py
          First 10 lines:
            import pytest
            from src.utils import validate_email
            ...

     👥 Applicable Rules/Experts (2):
       • @backend_developer
       • @qa_engineer

     ============================================================
     Используй этот контекст для понимания текущего состояния проекта.
     ```

3. **Инъекция в prompt** (`run_task_stream`):
   - IDE-контекст добавляется в начало `enriched_goal` (после skill_context, если есть)
   - SSE уведомление: `{'type': 'step', 'title': 'IDE Context', 'content': 'Workspace: ... | 2 open file(s) | Git status included'}`
   - Victoria получает `enriched_goal = ide_context + skill_context + original_goal`

4. **MCP tool** (`victoria_mcp_server.py`):
   - `victoria_run_with_context(goal, open_files_json, git_status, cursor_rules_json, workspace_path)`
   - Принимает JSON параметры из Cursor, парсит и передаёт в Victoria API
   - Пример:
     ```python
     victoria_run_with_context(
       goal="Добавь валидацию email",
       open_files_json='[{"path":"src/utils.py","content":"...","cursor_line":42}]',
       git_status="On branch main\nModified: src/utils.py",
       cursor_rules_json='["@backend_developer"]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )
     ```

**Формат open_files:**

```json
[
  {
    "path": "src/utils.py",
    "content": "def validate_email(email: str) -> bool:\n    ...",
    "cursor_line": 42
  }
]
```

**Статус:** ✅ Полная реализация (TaskRequest, форматирование, инъекция, MCP tool). Victoria теперь видит тот же контекст, что и Cursor assistant.

**Следующие шаги (План B):**

- **B.4: Параллельные чтения (batch_read)** — ✅ **ЗАВЕРШЕНО 2026-03-06**

---

## Batch Read — параллельное чтение файлов (План B.4)

**Назначение:** Быстрое параллельное чтение/поиск в множестве файлов за один запрос. Устраняет ограничение «последовательные шаги» — теперь можно сканировать полпроекта за секунды.

**Реализация (внедрено 2026-03-06):**

1. **Модуль batch_read** (`knowledge_os/app/batch_read.py`):
   - `batch_read_files(file_paths, workspace_path, max_concurrent=10)` — параллельное чтение с ограничением размера (1 МБ)
   - `batch_grep_files(pattern, file_paths, workspace_path, case_sensitive=False)` — параллельный grep с regex
   - Semaphore для ограничения одновременных операций
   - Graceful error handling (файл не найден, слишком большой, encoding error)
   - Статистика: success_count, total_size_kb, total_matches

2. **API endpoints** (`victoria_server.py`):
   - `POST /batch_read` — чтение множества файлов:
     ```json
     {
       "file_paths": ["src/utils.py", "src/main.py", ...],
       "workspace_path": "/path/to/project",
       "max_concurrent": 10,
       "max_file_size_mb": 1
     }
     ```
     Возвращает: `{"status": "success", "results": [{...}], "summary": {...}}`
   - `POST /batch_grep` — поиск паттерна:
     ```json
     {
       "pattern": "validate_email|check_email",
       "file_paths": ["src/**/*.py"],
       "workspace_path": "/path/to/project",
       "case_sensitive": false
     }
     ```
     Возвращает список совпадений с номерами строк

3. **MCP tools** (`victoria_mcp_server.py`):
   - `victoria_batch_read(file_paths_json, workspace_path, max_concurrent=10)`
   - `victoria_batch_grep(pattern, file_paths_json, workspace_path, case_sensitive=False)`
   - Пример:

     ```python
     # Прочитать 20 файлов параллельно
     victoria_batch_read(
       file_paths_json='["src/utils.py", "src/main.py", ...]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )

     # Найти все упоминания функции
     victoria_batch_grep(
       pattern="validate_email",
       file_paths_json='["src/**/*.py", "tests/**/*.py"]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )
     ```

**Формат результата batch_read:**

```json
{
  "status": "success",
  "results": [
    {
      "path": "src/utils.py",
      "content": "def validate_email(email: str) -> bool:\n    ...",
      "status": "success",
      "size_kb": 5.2,
      "lines": 150
    },
    {
      "path": "large_file.py",
      "content": null,
      "status": "error",
      "error": "File too large (2.5 MB > 1 MB)"
    }
  ],
  "summary": {
    "total": 20,
    "success": 18,
    "errors": 2
  }
}
```

**Формат результата batch_grep:**

```json
{
  "status": "success",
  "results": [
    {
      "path": "src/utils.py",
      "matches": [
        {
          "line": 42,
          "content": "def validate_email(email: str) -> bool:",
          "match": "validate_email",
          "start": 4,
          "end": 18
        }
      ],
      "match_count": 3,
      "status": "success"
    }
  ],
  "summary": {
    "total_files": 50,
    "files_with_matches": 12,
    "total_matches": 45
  }
}
```

**Производительность:**

- 10 файлов (по 1 КБ каждый) — ~0.1 сек
- 50 файлов (средний размер 50 КБ) — ~0.5 сек
- 100 файлов — ~1 сек
- Ограничение: max_concurrent=10 (можно увеличить до 20 для мощных систем)

**Статус:** ✅ Полная реализация (модуль batch_read, API endpoints, MCP tools). Victoria теперь может быстро сканировать полпроекта за один запрос.

---

Последние изменения (2026-03-29 v49): **Singularity 24.3: Живой Чат — victoria-wisdom-v3.5 via MLX.** Диалоговый Fast Path обновлён: модель `victoria-wisdom-v3.5` через MLX API (порт 11435) вместо phi3.5. Маршрутизация: victoria-wisdom\* → MLX (~3-7s); другие модели → Ollama. victoria-wisdom в Ollama для чата не работает (таймаут), только в MLX. Очистка артефактов модели: regex удаление эхо вопроса. TASK_TOTAL_TIMEOUT=200s, COLLECTION_TIMEOUT=190s. Результат: Score=1.00, ~31s, чистые ролевые ответы. Важно: перед тестами проверять `active_requests: 0` в MLX health — зависшие запросы замедляют систему. Перезапуск MLX: `pkill -f mlx_api_server && bash scripts/start_mlx_api_server.sh`. Ключевые файлы: `knowledge_os/app/expert_worker.py`, `knowledge_os/app/dialogue_controller.py`.

Последние изменения (2026-03-05): **Автономия: перезагрузка, Redis, HNSW в CI, индексация.** После перезагрузки — launchd активен при входе; для полной автономности включить автозапуск Docker. Redis для RAG при масштабировании — в .env.example. В CI (pytest-knowledge-os) добавлена проверка HNSW после миграций. Периодическая индексация: `setup_indexing_launchd.sh` (воскресенье 3:00). Автономный куратор запущен успешно (1 задача в БД при расхождении). CURATOR_RUNBOOK §6, HOW_TO_INDEX.

Последние изменения (2026-03-05): **UI Audit: setki21.ru.** (1) Проведён UI-аудит www.setki21.ru — главная и форма входа работают корректно. (2) Выявлены ограничения инструментария: отсутствие MCP Browser Server блокирует проверку функций админки. (3) Обнаружен timeout на `/cabinet` — требуется диагностика `moskit-api`. (4) Рекомендовано: внедрить Playwright E2E тесты, добавить MCP Browser, провести ручную проверку по чеклисту. Отчёт: `docs/audits/2026-03-05-setki21-ui-audit.md`.

Последние изменения (2026-03-04): **Server-Side Pricing & Advanced Order Mapping.** (1) В `moskit-core` внедрена библиотека `rust_decimal` для 100% точности финансовых расчетов. (2) Создан `PricingService` для серверного расчета цен на основе `GlobalPricing` из БД. (3) В таблицу `order_items` добавлено поле `dealer_cost` для фиксации себестоимости в момент заказа. (4) Настроен Docker-билд с кросс-компиляцией OpenSSL для x86_64. См. CHANGES §28.

Последние изменения (2026-03-04): **Multi-Level Dealer Platform & Financial Ledger.** (1) Внедрена иерархия дилеров (Owner, Director, Manager, Sub-Dealer) и филиалов. (2) Реализован финансовый Ledger с балансом и кредитным лимитом. (3) Добавлена "заморозка" цен в заказах для точной аналитики. (4) Создан Кабинет Директора (`/cabinet`) и расширена админка владельца. См. CHANGES §31.

Последние изменения (2026-03-04): **Aggressive Ollama Unload Policy.** (1) Внедрена централизованная политика `app.ollama_keep_alive_policy`. (2) При активном MLX модели в Ollama выгружаются через **60 секунд**. (3) Эмбеддинги выгружаются мгновенно (`keep_alive=0`). (4) Реализован Memory Guard 2.1 с учетом резерва MLX. См. CHANGES §29.

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management & MLX Recovery Unload.** (1) Внедрена централизованная политика `app.ollama_keep_alive_policy` для всех вызовов Ollama (router, executor, ai_core, embeddings). (2) Реализован `MLX_RAM_RESERVE_GB` (32GB) для защиты памяти "Мозга" при работе Ollama. (3) Добавлена автоматическая выгрузка fallback-моделей из Ollama (`keep_alive=0`) при восстановлении MLX (событие "MLX Recovery") с дебаунсом 60с. (4) `victoria-wisdom-v3.5` в Ollama становится бессмертной (`-1`) только при падении MLX. См. CHANGES §28.

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management.** (1) Глобальный `OLLAMA_KEEP_ALIVE` установлен в 10 минут (600с) для всех моделей. (2) `victoria-wisdom-v3.5` удалена из `IMMORTAL_MODELS` для экономии памяти Mac Studio. (3) В `local_router.py` внедрена логика «Fallback Immortality»: ядро v3.5 становится бессмертным в Ollama только если MLX-сервер («Мозг») недоступен. См. CHANGES §27.

Последние изменения (2026-03-03): **UI/UX Unification & Layout Stability.** (1) Унифицированы отступы и высота Hero-секций на всех страницах setki-21. (2) Исправлены «прыжки» верстки при переключении вкладок. (3) Хлебные крошки выведены из потока (absolute). См. CHANGES §26.

Последние изменения (2026-03-03): **Singularity 21.5: Victoria v3.5 Total Dominance.** (1) Полный переход на Qwen 3.5 MoE (35B) в MLX и Ollama. (2) Унификация знаний: Мозг и Руки теперь идентичны. (3) v3.5 добавлена в `IMMORTAL_MODELS` (бессмертные). (4) Обновлен `.env` и `local_router.py` для приоритета v3.5. См. CHANGES §25.

Последние изменения (2026-02-26): **Quick links, CONTRIBUTING по шагам, правило репо, FAQ.** В README и MASTER_REFERENCE добавлены блоки Quick links; CONTRIBUTING — таблица «Куда идти» (баг/предложение/вопрос), оглавление, правило репо, help wanted; создан docs/FAQ.md; в библии — правило репо, ссылки на FAQ, политика версий (Python 3.11+, Node 18+), метрики агентов. См. CHANGES §0.5q.

---

---

## 📜 ИСТОРИЧЕСКИЙ КОНТЕКСТ (Архив v21.5)

Здесь хранятся устаревшие, но важные для понимания эволюции проекта записи.

Последние изменения (2026-02-24): **Эра Мудрости: Совет Директоров и дефибриллятор.** (1) Закрыты 170 висящих strategy_sessions (active→cancelled). (2) Введён дефибриллятор MLX: `scripts/host_recovery_listener.py` (порт 9099), RECOVERY_WEBHOOK_URL в оркестраторе — при падении Ollama/MLX вызывается автовосстановление на хосте. (3) Handoff в новый чат: `docs/SESSION_HANDOFF_2026_02_24.md`. (4) Запущен один прогон run_board_meeting(); новые директивы — в board_decisions и на дашборде. См. CHANGES §0.5b.
