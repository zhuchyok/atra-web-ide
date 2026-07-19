# Expert Dialogue Full Path — Design (2026-07-19)

## Goal
Restore real expert dialogue engines as the default path; keep lightweight only as bounded fallback.

## Approach (chosen)
**Full-first + layered fallback**
1. Run mode engine (`ExpertCouncil` / `MultiAgentDebate` / `CollectiveBrainstorming`) with timeout.
2. On failure/timeout → lightweight Victoria path.
3. On lightweight failure → safe API fallback (never hang / no bare 500).

Opt-in fast path: `prefer_lightweight=true` (or env `EXPERT_DIALOGUE_PREFER_LIGHTWEIGHT=true`).

## Engine hardening
- Council: cap experts (`COUNCIL_MAX_EXPERTS`, default 4) for SLA.
- Debate: resilient LLM calls (`category=fast`), structured history → API opinions.
- Return contract: `final_decision`, `debate_history`, `participants`, `opinions`, `engine_used`, `lightweight_used`, `fallback_used`.

## Success criteria
- `POST /api/expert-dialogue/start` with default flags → `engine_used` in {council,debate,brainstorm}, not lightweight.
- `prefer_lightweight=true` → lightweight within ~12s.
- Full path timeout → falls back without 500.
- Participants/opinions non-empty when full engine succeeds.

## Verification (2026-07-19) — passed
| Case | engine_used | lw | ops | ~time |
| ---- | ----------- | -- | --- | ----- |
| debate force_full | debate | false | 3 | 83s |
| sequential force_full | council | false | 3 | 89s |
| prefer_lightweight | lightweight | true | 1 | 8s |
| default debate | debate | false | 3 | 58s |
| collaboration force_full | brainstorm | false | 3 | 50s |
