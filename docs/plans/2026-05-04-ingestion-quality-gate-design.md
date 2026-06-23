# Ingestion Quality Gate Design (Fail-Closed)

Date: 2026-05-04  
Status: Draft approved in brainstorm, awaiting user review  
Owner: Victoria Swarm (Team Lead + DB + QA + Performance)

## 1) Context and Problem

The system currently suffers from low-quality knowledge nodes created during ingestion:

- prompt artifacts and service text are saved as knowledge;
- mixed content types (instruction + role-play + context) are stored as a single node;
- malformed text propagates into distillation, increasing parse errors and fallback usage.

Distillation is now resilient (no hard crash), but this is a downstream safety net.  
Root cause is upstream: ingestion accepts too much noisy content.

## 2) Goal

Adopt a strict creation policy:

- reject all suspicious content at node creation stage (fail-closed);
- allow only semantically clean, structurally useful nodes into `knowledge_nodes`;
- preserve Mac Studio stability and avoid heavy runtime overhead.

Non-goal:

- no broad refactor of distillation in this phase;
- no quality uplift of already accepted historical nodes in this phase.

## 3) Selected Approach

Chosen: **Hybrid Gate** (recommended)

- deterministic hard rules first (cheap and fast);
- LLM Judge only for borderline candidates;
- final decision is strict: invalid judge output defaults to reject.

This keeps cost low while minimizing false acceptance.

## 4) Architecture

Pipeline:

1. `Raw Candidate` arrives from source.
2. `Hard Rule Filter` runs synchronous checks.
3. Router outputs one of: `accept`, `reject`, `borderline`.
4. `LLM Judge` processes only `borderline`.
5. Final write:
   - accepted -> `knowledge_nodes`
   - rejected -> `knowledge_reject_log` (reason + evidence).

Design principles:

- fail-closed by default;
- deterministic-first gating;
- auditable decisions for every reject.

## 5) Accept / Reject Criteria

### Accept requires all:

- coherent standalone knowledge (not a fragment);
- at least 2 of 3: fact / conclusion / action;
- no prompt/system wrappers;
- length in configured range (default: 200..4000 chars);
- low symbol noise and low repetition;
- no near-duplicate fingerprint.

### Immediate reject:

- prompt artifacts (`Role/Tone/Strategy`, `Ты - ...`, "return JSON", etc.);
- logs/tracebacks/config fragments;
- broken/incomplete snippets;
- semantic emptiness (generic filler text);
- duplicate or near-duplicate.

### Borderline:

- potentially useful but uncertain semantic quality;
- partially noisy but salvageable.

Borderline must go through Judge.  
Judge timeout/invalid format -> reject.

Default Judge runtime policy:

- timeout: 8s per candidate;
- retries: 1;
- output contract: `decision`, `reason`, `quality_score`;
- invalid/missing required fields: reject (fail-closed).

## 6) Metrics, SLO, and Auto-Protection

Primary SLO:

- `distill_parse_error_rate < 10%`
- `distill_fallback_rate < 8%`
- `goodput (verified/processed) > 70%`

Ingestion metrics:

- `nodes_ingested_total`
- `nodes_rejected_total` by reason
- `nodes_borderline_total`
- `judge_accept/reject/invalid_total`

Auto-reactions:

- fallback > 15% for 3 cycles -> safe mode (reduce batch/concurrency);
- judge invalid > 10% -> fail-closed strict reject for borderline;
- goodput < 50% for 5 cycles -> pause intake, sanitation-only pass.

## 7) Rollout Plan (Mac Studio Safe)

Phase A (shadow mode, read-only decisions):

- run gate without enforcing writes;
- collect decision stats and false reject sample.

Phase B (10% enforce):

- enforce reject/accept on small portion;
- track quality and throughput delta.

Phase C (50% enforce):

- enable for half of candidates;
- monitor CPU/RAM, queue latency, fallback rate.

Phase D (100% enforce):

- full fail-closed ingestion policy;
- keep rollback toggle available.

Rollback condition:

- if throughput drops by >25% vs previous phase median for 30 minutes, revert to previous phase;
- if reject rate spikes >80% for 3 consecutive windows (10 min each), revert to previous phase;
- if Mac Studio free RAM stays <6GB for 15 minutes after gate rollout, revert to previous phase.

## 8) Data Model Additions

Add ingestion quality metadata:

- `ingest_quality_tier` (`tier_a`, `tier_b`, `tier_c`);
- `ingest_decision_reason`;
- `ingest_source_type`;
- `ingest_fingerprint`.

Rejected candidates should be stored in audit table/log with:

- raw snippet hash;
- reject reason code;
- gate stage that rejected it.

## 9) Risks and Mitigations

Risk: over-rejection of useful knowledge.  
Mitigation: shadow mode + sampled review + threshold tuning.

Risk: Judge drift/instability.  
Mitigation: deterministic-first routing, invalid judge -> reject, weekly judge quality test set.

Risk: added latency on ingestion.  
Mitigation: Judge only for borderline subset, strict timeout and async queue.

## 10) Definition of Done

Done when:

- ingestion gate enforces fail-closed at 100%;
- fallback rate stabilizes below target;
- parse-error trend decreases materially;
- no new infinite noisy-node loops in distillation;
- audit logs show clear reject reasons for all dropped candidates.
