# Victoria session memory Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkbox tracking.

**Goal:** Cross-session chat continuity via stable user key + LTM (no ephemeral `openai-{uuid}`).

**Architecture:** Resolve `user_key` from headers / body.user / env / `atra-default`; set `TaskRequest.session_id` and LTM lookups to that key; enable `LONG_TERM_MEMORY_ENABLED` on victoria-agent. Memory only after live-fact early exits.

**Tech Stack:** FastAPI `victoria_server.py`, `knowledge_os` LTM, docker-compose.agents.yml

**Spec:** `docs/plans/2026-11-21-victoria-session-memory-design.md`

## Global Constraints

- Do not inject memory before live-fact / fixed-token / file-check
- TTC 420 / Ollama slots unchanged
- No mypy ignore reintroduction
- Phase 2 experience inject out of scope

---

### Task 1: Resolve chat user key + wire chat session_id

**Files:**

- Modify: `src/agents/bridge/victoria_server.py`
- Create: `knowledge_os/tests/test_chat_user_key.py`

- [x] Add optional `user: Optional[str] = None` on `ChatCompletionRequest`
- [x] Add `_resolve_chat_user_key(request, req) -> str` (headers `X-Victoria-User` / `X-Session-Id`, then `request.user`, then `VICTORIA_CHAT_USER_KEY`, then `atra-default`)
- [x] Replace `session_id=f"openai-{correlation_id[:8]}"` and LTM `user_key=f"openai-..."` with resolved key
- [x] Unit test key resolution priority
- [ ] Commit `feat(chat): stable user key for session memory`

### Task 2: Enable LTM in compose

**Files:**

- Modify: `knowledge_os/docker-compose.agents.yml` (victoria-agent environment)

- [ ] Add `LONG_TERM_MEMORY_ENABLED: "true"`
- [ ] Add `VICTORIA_CHAT_USER_KEY: ${VICTORIA_CHAT_USER_KEY:-atra-default}`
- [ ] Commit `chore(compose): enable VictoriaTM for victoria-agent`

### Task 3: Verify + restart

- [ ] pytest `test_chat_user_key.py` + `test_fact_seeking_route.py`
- [ ] `docker restart victoria-agent`; health ok
- [ ] Two curls with same `X-Victoria-User` after a non-simple exchange — LTM path uses same key (log or unit evidence)

---
