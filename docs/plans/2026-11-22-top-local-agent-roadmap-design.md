# Design: Top local agent roadmap (A+B+C+D)

Date: 2026-11-22  
Status: **approved direction** (user «нам нужно все» + «го» /expert) — phased delivery, not big-bang  
Scope: make Victoria feel like a top local agent (world 2026: thin harness, tools/MCP, evidence loop, memory) without breaking live slot contract.

## Goal

One local Twin: fast when possible, tools with proof, code with tests, memory that sticks — **STRICT_LOCAL**, TTC p95 threshold **420 unchanged**, slots **11434 qwen38 / 11437 phi+nomic / 11436 coder**.

## Non-goals (this program)

- Cloud bypass / replace local brain with API
- Raise TTC 420
- Dual-load canary + latest or day-load 120B
- Rewrite to CrewAI/LangGraph as the core runtime

## Constraint: “all” = sequenced waves

| Wave  | Theme                   | World parallel                   | Depends on                             |
| ----- | ----------------------- | -------------------------------- | -------------------------------------- |
| **0** | Night heavy brain       | bigger model off-hours           | pull `gpt-oss:120b` (in flight)        |
| **1** | **A** Speed UX          | prefix/cache + less silent async | live think:false (done)                |
| **2** | **C** Hands/MCP approve | MCP hosts + tool gates           | Wave 1 stable chat                     |
| **3** | **B** Code→test→proof   | Cursor-like harness              | tools + sync path                      |
| **4** | **D** Memory + LoRA     | personalization                  | session memory live; night battle data |

## Baseline (2026-11-22 facts)

- Live: `victoria-qwen38:latest` @16384, xhigh **Modelfile layer** false; Jinja may still mention xhigh — gated by `think:false`
- Victoria BCANARY **20/20**; A3B canary **no-promote**
- Refusal ref01–03 deterministic
- Night: `scripts/brain_night_120b_window.sh` + Modelfile; pull via LaunchAgent `com.atra.night-120b-pull` — **real** progress ~28% / ~18 GiB of ~65 GiB (partial file size is preallocated, not “94%”)
- Session memory: design+impl docs exist (`2026-11-21-victoria-session-memory-*`)
- LoRA gate: **PASS** (`docs/audits/lora-readiness-gate.md`) — train after night corpus

## Wave 0 — Night 120B (parallel)

Sequence after pull ([Night path](891d21c6-81b3-4664-944f-cf00347ac6f7)):

1. Finish `ollama pull gpt-oss:120b` — watcher: `scripts/_night_120b_pull_until_done.sh` (create on done; **NIGHT only if `AUTO_NIGHT=1`**)
2. `ollama create victoria-night:120b -f configs/models/Modelfile.victoria-night-120b`
3. `PRECHECK` then `NIGHT` (unload MLX→coder→hands→live → ollama-direct → `configs/evals/results/brain_canary_ollama_<UTC>.json`) only 23:00–06:00; free ≥~20GB after unload
4. Morning `ROLLBACK` → pin `:latest` @16384
5. Promote: **never auto**; only if Δ≥2/20 vs day baseline

**Root cause pull** ([Root-cause](066fc08c-c4e2-4873-a1d5-566d9002ce2a)): «94%» = prealloc `ls` illusion; death = Cursor SIGTERM 143 + secondary `PROBE-RESTART` kickstart :11434. Fix: LaunchAgent sole owner; CLI `%` only; watchdog skips :11434 restart while `ollama pull` / night pipeline active.

**Pre-NIGHT gate** ([Night readiness](8f22160b-6940-47e0-b4d5-0478381164d1)): tags `gpt-oss:120b` + `victoria-night:120b` + live `:latest`; 11434 up; Victoria health; hour 23–06 or `FORCE_NIGHT=1`; unload MLX→coder→hands→live; **free ≥~20GB**; load night `@8192`; battle → `configs/evals/results/brain_canary_ollama_<UTC>.json`; no `FORCE_VICTORIA` by default; morning `ROLLBACK`.

**Done when:** PRECHECK pass; battle JSON on disk; live back on `:latest` by morning.

## Wave 1 — A Speed UX (first code wave)

**Problem:** `/run` → `request_async_mode` / sync-safe timeout feels like “вечно думает” even when CoT is off.

**Facts ([Async UX](adb6d3a6-43dd-4cb2-a00d-870550255547)):** conversational markers (`объясни`/`анализ`/`почему`) blocked sync_safe; chat poll ignored `stage`; preamble skip only for analysis-heavy `request_async_mode`.

**Approach (KISS) — landed + verified 2026-11-22 ~23:10:**

1. Chat path stays sync + `think:false` (already)
2. Narrow `heavy_markers` — drop conversational Q&A from sync_safe exclusion ✅
3. Always skip BG preamble on `request_async_mode` ✅
4. Chat handoff poll: log + surface last `stage` on timeout (not silent stub) ✅
5. SSE stage push on OpenAI stream (`delta.content` ⏳ + `/run` stage) ✅ (2026-11-23)

**Evidence:** `pytest knowledge_os/tests/test_wave_a_sync_safe_markers.py` 3/3; chat «Объясни коротко: зачем Blackboard…» → **2326 ms sync**, no async stub / no stage timeout. TTC 420 untouched.

**Done when:** short «объясни…» can hit sync_safe ✅; timeout stub shows `stage=…` (code path); TTC 420 untouched; no think leak.

## Wave deltas from subagents (2026-11-22)

- **C MCP** ([Wave2 MCP](a8f48055-7fee-4b86-b8d1-dbeeeb92dc1f)): stubs→local FS+`approve_writes` landed; orphan `approval_manager` / unused `ExecutionPlanExecutor`; git mutate advertised but unwired — register read `git_pr_list` first; OWUI `ENABLE_OLLAMA_API=false` ok.
- **B Code** ([Wave3 code](b0868d0d-5d5a-456e-89e9-e7706cc10823)): TDD `_ask_veronica(test_path)` bug; missing top-level `test_status`/`*_ms`; `TURN_DELIVERABLE` default off; `/run` stage never file→compile→test.
- **D Memory/LoRA** ([Memory LoRA](bef42650-2a0a-47c0-b639-1d165d878ab2)): session memory mostly live (docs stale); LoRA gate PASS but base≠qwen38 — decide fuse target before train.

### Follow-up landed after those audits

- Wave 2: `execution_plan_local.py` + `approve_writes`; `git_pr_list` registered on Victoria (mutate git still off).
- Wave 3: `_ask_veronica(test_goal)`; top-level `test_status` + `compile_ms`/`runtime_ms`/`test_ms`.

## Wave 2 — C Hands / MCP

**Problem:** OpenWebUI→11434 bypassed Victoria; world uses MCP with approve; `victoria_execute_plan` lied (`[Изменён файл]` stub).

**Approach:**

1. Keep `ENABLE_OLLAMA_API=false` default (Victoria `/v1` only) — landed
2. Expose/curate MCP tool set Victoria already has (`victoria_*`, filesystem, git) with **write approve**
3. One new MCP or wire: scoped `repo_fs` read default / write gated — **landed local:** `execution_plan_local.py` + `approve_writes` on `victoria_execute_plan`
4. Telegram/`ai_core` generate already getting `think:false` — keep parity

**Evidence (2026-11-22):** `pytest …test_wave2_execute_plan_local.py` 4/4 — sandbox escape blocked; edit without approve leaves file unchanged; approve writes.

**Done when:** OWUI Victoria path only ✅; one documented MCP write path with approve ✅ (local FS); no raw 11434 CoT in UI (chat smoke think_leak=False). Remaining: git-read MCP polish; CallMcpTool→user-filesystem optional.

## Wave 3 — B Code→test→proof

**Problem:** Top agents show evidence; we have autonomous-code / pair / Veronica tools — uneven UX.

**Approach:**

1. Default “code goal” path: autonomous-code or Veronica with `py_compile` + optional pytest
2. Fix TDD `test_goal` → Veronica ✅; emit `test_status` + top-level `*_ms` ✅
3. `TURN_DELIVERABLE` default on for autonomous-code; include `test_path` in deliverable ✅
4. Thin progress: `progress[]` + optional `task_id`→`store["stage"]` file_written→compile→runtime→test ✅

**Done when:** 3 canned code goals E2E with proof fields (remaining soak); BCANARY code\* stay green.

## Wave 4 — D Memory + LoRA

**Problem:** session memory designed; LoRA gate PASS but not trained on refusals+fact style.

**Approach:**

1. Finish/verify session memory live (stable `X-Victoria-User` + LTM) — **smoke 2026-11-22:** same user two turns, nonce `LTM-*` recalled (`hit True`); docs Task 2 synced ([Wave4 audit](f5573067-8cd9-45ae-8161-1dbc9b5ff40d))
2. Style corpus: `scripts/build_lora_style_corpus.py` → `configs/training/style_v1/` ✅ (refusals+facts+pairs; not distilled)
3. Fuse-target gate: `evaluate_lora_gate.py --require-fuse` refuses Llama-3.2-3B / qwen2.5-3b ✅
4. Train off-live → canary battle refusal+fact → pin only if Δ≥0 (**not started**)

**Done when:** two chats same user key share LTM ✅ smoke; style corpus+gate PASS ✅; off-live train on qwen38-4bit ✅; **NO_PROMOTE** (adapter smoke refusals 2/3 think-leak; day product refusals 7/7 via `safety_refuse`). Pin only if future canary Δ≥0 on fused `:canary` tag — not `:latest`.

## Approaches considered

1. **Big-bang rewrite on LangGraph/OpenCode** — reject (throws away Swarm/Blackboard; high risk)
2. **Only bigger model** — reject as sole strategy (already saw A3B no-promote; 120B night-only)
3. **Phased A→C→B→D + Wave 0 parallel** — **chosen** (matches world: harness UX → tools → proof → personalize)

## Pre-mortem

1. Wave 1 raises sync timeout → OOM / TTC breach → keep 420; progress UX not longer sync
2. Wave 2 opens write MCP without approve → data loss → approve + refuse wipe (already)
3. Wave 4 LoRA on noisy corpus → worse refusals → eval gate on ref01–03 before pin

## Success scoreboard (program)

| Metric                 | Target                    |
| ---------------------- | ------------------------- |
| Live slots             | contract always           |
| Chat think leak        | 0                         |
| Async progress visible | ≤2s after 202             |
| BCANARY Victoria       | ≥19/20                    |
| Night battle           | logged; morning rollback  |
| LoRA                   | promote only if eval pass |

## Close-out status ([gap audit](cb0e604a-b43c-4a36-b4b0-a6804a134ed0))

| Wave | Runtime close                                                                                                                                                                                                                                            |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | Pull+create ✅; battle **8/20** (`brain_canary_ollama_20261123_155457.json`); Docker Desktop off was outage root ([audit](3edbfac1-55ac-4894-bbe4-f67a017cf5ad)); NIGHT requires Docker quit / `ALLOW_NIGHT_WITH_DOCKER=1`; day restored; **no promote** |
| 1    | Closed                                                                                                                                                                                                                                                   |
| 2    | Closed (MCP `git_pr_list` polish optional)                                                                                                                                                                                                               |
| 3    | Code closed; E2E soak ✅ (`test_status=passed`, `progress` file→compile→test, ~19s)                                                                                                                                                                      |
| 4    | LTM+corpus+fuse; train intentional OPEN                                                                                                                                                                                                                  |

**100% program** = Wave0 battle JSON + ROLLBACK + W1–3 green + W4 memory verified (LoRA train out of band).

## Direction shift (2026-11-23)

User goal: **be better**, not night 120B ritual.  
`victoria-night:120b` **PARKED** (battle 8/20, no promote, no nightly schedule).  
Day pin stays **`victoria-qwen38:latest`**. Next: day UX latency + optional style LoRA canary on qwen38 family only.

## Next action after this doc

Day-better ✅ (stream shortcuts + phi short-chat + SSE stages). Wave-4 style LoRA off-live trained → **parked NO_PROMOTE** (`configs/evals/results/brain_canary_style_COMPARE.json`). Day pin remains stock `victoria-qwen38:latest`.

**Wave-4 MLX base (local, no pull):** `~/.cache/huggingface/hub/models--mlx-community--Qwen3.8-27B-4bit` (~15G, complete); `~/mlx-models` has no qwen38.
