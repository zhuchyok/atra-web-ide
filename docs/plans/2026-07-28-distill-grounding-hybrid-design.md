# Design: Hybrid Distill Grounding (v125)

## Problem

Priority re-distill quality gate scored length/structure only. Models (phi and victoria) produced high-band template wisdom ungrounded in source (e.g. “aggressively scale digital service…” on unrelated board notes).

## World practices (giants)

- **RAGAS Faithfulness** — claims must be supported by context.
- **Lexical / token overlap** — cheap proxy for attribution (industry RAG evals).
- **Mode-collapse / template detect** — reject near-duplicate canned phrases.
- **Embedding similarity** — semantic faithfulness when vectors available.
- **Fail closed** — do not write ungrounded wisdom; mark reject, do not fake `high`.

## Hybrid (recommended)

| Layer | Check                                          | Fail action                   |
| ----- | ---------------------------------------------- | ----------------------------- |
| A     | Template / known spam n-grams                  | reject                        |
| B     | Lexical overlap source ↔ (summary+instruction) | reject if below min           |
| C     | Optional embedding cosine (if embedder up)     | can rescue borderline lexical |

Pass if: **not template** AND (**lexical ≥ min** OR **embed ≥ min** when embed available; if embed unavailable, lexical alone decides).

## Defaults

- `DISTILL_GROUNDING_ENABLED=true`
- `DISTILL_GROUNDING_MIN_LEXICAL=0.12`
- `DISTILL_GROUNDING_MIN_EMBED=0.42`
- On reject: `redistill_priority_done=true`, `redistill_status=rejected_ungrounded` (no overwrite of bad summary into wisdom fields).

## Non-goals

- Full NLI entailment model (heavy).
- Mass re-score of historical corpus in v125.
