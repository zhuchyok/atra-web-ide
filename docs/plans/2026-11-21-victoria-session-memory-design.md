# Design: Victoria cross-session memory (stable key + LTM)

Date: 2026-11-21  
Status: draft — awaiting user review before implementation plan  
Scope: iteration A (межсессии). Phase 2 (top-N `kind=experience` inject) out of scope here.

## Problem

Chat `/v1/chat/completions` sets `session_id=f"openai-{correlation_id[:8]}"` every request → session_context / LTM never hitch across chats.  
`LONG_TERM_MEMORY_ENABLED` defaults to `false` (module load ~1546) and **gates only** `/run` helpers `_get_long_term_memory_context` / `_save_long_term_memory` (~7317+).  
Chat path already has a **parallel** inline LTM read (~13364) and save (~13936 / stream ~13615) that **do not check** that flag — they already call `get_recent_threads` / `save_thread` with the ephemeral `openai-{correlation_id[:8]}` key. Continuity failure on chat is the unstable key, not the flag alone.  
Result: Виктория «знакомится заново»; 157K RAG ≠ personal continuity.

## Goals

1. Two chat requests with the same user key share LTM / session_context.
2. Different keys stay isolated.
3. Live-fact / fixed-token / file-check paths unchanged (no memory before fact-probe).
4. Latency: memory block ≤ ~600 chars; skip on simple/fact paths.

## Non-goals

- LoRA / bigger brain
- Mass experience inject into every `/run` (phase 2)
- Untracking `curator_tasks.txt`
- Changing TTC 420 / Ollama slot contract

## Approach (approved direction)

**Stable user key + enable LTM** (approach 1). Not hybrid experience-yet.

### §1 — Key resolution (chat)

Resolve `user_key` in order:

1. Header `X-Victoria-User` or `X-Session-Id` (if present and non-empty) — from FastAPI `req` already passed to `chat_completions`
2. OpenAI-compatible `user` on request body — **`ChatCompletionRequest` currently has no `user` field** (only `model`, `messages`, `stream`, `temperature`, `max_tokens`); add `user: Optional[str] = None` to accept it
3. Env `VICTORIA_CHAT_USER_KEY`
4. Fallback `atra-default`

Never use per-request `correlation_id` as the sole session identity.

`TaskRequest.session_id` for chat ← this `user_key` (optionally suffix project: `{user_key}:{project}` if project_context set — KISS: start with bare `user_key`).  
Same `user_key` must replace ephemeral id in: `TaskRequest.session_id` (~13354), chat LTM get (~13383), non-stream save (~13948), stream save (~13626).

### §2 — Read / write

- Flip live LTM for `/run` helpers: add `LONG_TERM_MEMORY_ENABLED: "true"` (or `${LONG_TERM_MEMORY_ENABLED:-true}`) under **`victoria-agent.environment`** in `knowledge_os/docker-compose.agents.yml` — key is **absent** from that block today; uncommenting repo-root `.env` alone is insufficient (no `env_file`, WORKDIR `/app`, `load_dotenv()` does not see `/workspace/atra-web-ide/.env`). Optionally also set `LONG_TERM_MEMORY_ENABLED=true` in repo-root `.env` for host runs / compose interpolation.
- Chat LTM: keep or migrate the inline block (~13364+) onto stable `user_key`; do **not** assume chat already goes through `_get_long_term_memory_context` — it does not. Prefer consolidating onto helpers (flag + `max_chars=600`) to avoid double channels once `/run` LTM is on.
- Stream save (~13615–13632): today `save_thread` is nested under the ImportError fallback branch (likely dead); fix when wiring stable key.
- Insert / inject only **after** early returns (file-check, fixed-token, live-fact ~13181–13247). Current chat inject prepends into `goal` after those returns (~13392); Prefer Enhanced `long_term_memory` context on `/run` path; do not prepend into `goal` before `_build_live_fact_answer_for_run`.

### §3 — Success criteria

| Check              | Pass                                                                                              |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| Unit / integration | Same `user_key` → second request sees LTM or session summary non-empty after first saved exchange |
| Isolation          | Different `user_key` → no cross-leak in test                                                      |
| Fact-probe         | `curl` health / metrics ask still short-circuits without LTM await                                |
| Regression         | `test_fact_seeking_route` still green; no new mypy ignore                                         |

## Risks

| Risk                                          | Mitigation                                                                                       |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Double inject (LTM + chat_history + RAG)      | Cap LTM chars; one channel on chat LLM path                                                      |
| Shared `atra-default` mixes curator/OpenWebUI | Document header override; later split keys                                                       |
| LTM empty at first                            | Seed via normal successful exchanges; optional one-shot from recent pair lessons later (phase 2) |

## Phase 2 (later)

Reuse `_fetch_experience_lessons` into Enhanced/chat after stable key lands.

## References

- Explore: experience map + prompt assembly (2026-11-21 curator session)
- Code: `victoria_server.py` chat ~12892, LTM ~1546 / ~7317, ephemeral id ~13354
