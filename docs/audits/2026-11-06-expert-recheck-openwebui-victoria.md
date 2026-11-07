# /expert Recheck — Open WebUI + Victoria

Date: 2026-11-06
Scope: repeat `/expert` runtime verification after user reports that Victoria responds with templates and does not execute real project work.

## 1) Diagnosis (facts)

- Container health is green for core services: `open-webui`, `victoria-agent`, `atra-web-ide-backend`, worker pool, Redis, PostgreSQL.
- Queue snapshot is clean:
  - `pending=0`
  - `queued=0`
  - `in_progress=0`
  - `stale_in_progress=0`
- Redis inflight/streams are clean:
  - `HLEN inflight_tasks = 0`
  - `XLEN expert_tasks:overflow = 0`
  - `XLEN expert_tasks:dedicated = 0`
- Model-port contract is respected at runtime:
  - `11434`: `victoria-qwen38:latest`
  - `11436`: `qwen3-coder:30b`
  - `11437`: `phi3.5:3.8b-stable`, `nomic-embed-text:latest`
- Root functional issue reproduced: some semantically rich Open WebUI asks were routed into deterministic live-fact responses (metrics), which looked like "template/non-Qwen behavior".

## 2) Team decision

- Team Lead (Victoria): treat this as routing bug, not only UX mismatch.
- Igor (Backend): deterministic fact path must not claim ownership/docs answers.
- Roman (DB): queue/DB are not current bottlenecks.
- Sergey (DevOps): runtime healthy, but app-level route quality needed hard guardrails.
- Anna (QA): acceptance should validate "correct answer type", not only health checks.
- Olga (Performance): avoid fallback loops that degrade answer semantics.
- Alexey (Security): prevent hallucinated authoritative answers when semantic context is required.

## 3) Applied changes

- Added guardrail in `src/agents/bridge/victoria_server.py`:
  - `_build_live_fact_answer_for_run()` now returns `None` for semantic prompts (team/docs/bible/ownership markers), preventing deterministic metric stubs for those requests.
- Restarted `victoria-agent` to apply routing fix.
- Verified Open WebUI tool routing settings:
  - `ALWAYS_ATTACH_BIBLE_CONTEXT=false` in persisted `ask_victoria` valves.
  - `USE_BACKEND_PROXY=false` remains active.

## 4) Risks and safeguards

Pre-mortem (top 3):

1. Deterministic path re-captures semantic prompts after future edits.
   - Safeguard: keep explicit semantic deny-list in `_build_live_fact_answer_for_run`.
2. LLM timeout (qwen) causes fallback and confusing "temporarily unavailable" messages.
   - Safeguard: monitor `LLM_TIMEOUT`, separate timeout handling from deterministic fact routing.
3. Green health but wrong answer type regresses unnoticed.
   - Safeguard: add E2E acceptance probes for team/docs ownership prompts after restart.

## 5) Control slice (post-change)

- `/health`:
  - `8010`: ok
  - `8080`: healthy
- Queue:
  - `pending=0`, `queued=0`, `in_progress=0`
- Error metrics:
  - `completed_24h=15`
  - `failed_24h=4` (curator mismatch tasks; not queue saturation)
- Contract:
  - Ports/models match expected runtime split (`11434/11436/11437`).
- Behavioral evidence:
  - Semantic ownership request now enters normal processing route (`/run` strategy stage), no immediate deterministic fact response.

## 6) Gate status

- `24h sustained gate`: not yet closed in this run (requires continuous observation window and evidence bundle).
- `7d stability`: not yet closed in this run (requires seven-day evidence accumulation).

Next action to close Phase 7: start/continue timed evidence collection and append daily snapshots to `docs/audits` with queue/error/contract deltas.
