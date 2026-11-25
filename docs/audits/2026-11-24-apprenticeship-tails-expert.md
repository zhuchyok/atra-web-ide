# /expert closeout — apprenticeship tails (2026-11-24)

## 1. Диагноз (факты)

| Слой                                           | Было                                                                              | Сейчас                                                                       |
| ---------------------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Probes (first/nth line, env, git_diff content) | PASS                                                                              | PASS                                                                         |
| Free-read summarize `cursor_method.md`         | LLM → sticky PgBouncer/6432 TZ                                                    | Deterministic `file_summarize_answer` — file bytes, no LLM                   |
| Crystals                                       | deny узкий; evidence goals всё равно тянули sticky                                | evidence → skip crystals; deny + `исполнению`                                |
| Experience                                     | `inject_context_enrichment` + OPENAI-API `_fetch_experience_lessons` + skill-loop | skip на evidence-tool goals                                                  |
| RAG                                            | шёл даже при LIGHTWEIGHT                                                          | skip `_get_knowledge_context` на evidence                                    |
| Слоты                                          | —                                                                                 | 11434=`victoria-qwen38:latest`, 11436=`qwen3-coder:30b`, 11437=`phi`+`nomic` |
| GATE                                           | swarm_ready (205 fact pairs)                                                      | cursor_method уже в `expert_worker` + journals filter                        |

**Root cause (Five Whys):** free-read не читал файл → LLM + experience/RAG/sticky recipe → «Принято. Переходим к исполнению ТЗ PgBouncer». Crystal-gate alone не хватало (LIGHTWEIGHT уже отключал crystals).

## 2. Решение команды

- **Виктория (TL):** детерминированный summarize + запрет «готово без файла».
- **Игорь (Backend):** `file_summarize_answer` / `is_evidence_tool_goal` в `task_detector.py`; early exit `/run`+chat.
- **Роман (DB):** experience/RAG не кормят file-goals из `knowledge_nodes`.
- **Сергей (DevOps):** restart `victoria-agent` после mount-правок; слоты по контракту.
- **Анна (QA):** pytest first-line/nth/summarize + crystals gating — 10 passed.
- **Ольга (Performance):** summarize ~4s vs 170s LLM hijack.
- **Алексей (Security):** git mutate fail-closed без изменений в этом срезе.

## 3. План дожима (закрыто в этом срезе)

1. [x] Evidence crystal + experience skip (`ai_pipeline`)
2. [x] Deny regex `исполнению`
3. [x] OPENAI-API + `_fetch_experience_lessons` + skill-loop skip
4. [x] RAG skip on evidence (`ai_core`)
5. [x] Deterministic `file_summarize_answer` + wire
6. [x] Pair verify: `pair_2026-11-24_16-43-55-086104.md` — нет PgBouncer/6432
7. [x] Swarm: `CURSOR_METHOD_PROMPT` уже prepend в `expert_worker.py`

## 4. Риски и страховки

| Pre-mortem                                              | Страховка                                      |
| ------------------------------------------------------- | ---------------------------------------------- |
| Summarize regex не поймает новый wording                | markers расширяемы; fallback LLM всё ещё gated |
| Experience skip слишком широкий                         | только evidence markers, не весь chat          |
| Absolute-truth «кристаллы = истина» при пустых crystals | residual; не блокирует summarize path          |
| Style/Night promote                                     | **не трогали** (day pin sacred)                |

Rollback: revert `task_detector` summarize + victoria early exits; env `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL` уже default true.

## 5. Контрольный срез

- Pair free-read: bullets from file, bleed scan clean
- pytest: `test_first_line_file_reply` + `test_memory_crystals_gating` → 10 passed
- Health 8010 ok; brain/coder/hands contract
- GATE=swarm_ready; method already in swarm prompts

**Не открывали:** style LoRA promote, Night 120b, 100kna P0 (закрыты ранее).

## Round 6 follow-up (subagent residuals)

Closed after [Crystal deny analysis](79269ea8-7479-4954-9041-616ad9c8399d) / [Find PgBouncer inject path](0c5840d9-d733-482a-a850-068f0380b583) / [List open method tails](1acd64d4-2972-4f64-bb9c-0f95e0d36b38):

- Chat LTM + Omni-RAG gated on evidence goals
- Absolute-truth U-shape skipped when crystals empty / evidence
- Deny regex: `db port` / `порт` / `pgbounce`
- Mentorship/meta_wisdom skipped with experience on evidence
- `grep_line_answer` + pair `16-46-49` PASS (`:443`, not `:123`)

Still open (low): empty-body FAIL_THIN channel; live mutate-reject pair; answer truncation in pair reports.

## Round 7

- Mutate-reject live pair `17-02-48` PASS
- Empty Enhanced → salvage first/nth/summarize/grep/mutate
- Quick-tool + normalize caps 8000 → git_diff `17-03-55` keeps `process_env_fact_answer`
- Clarify override: `evidence_tool_goal_no_clarify`

## Round 8

- Bare-done egress + instruction early-refuse (`17-11-04` PASS)
- LTM recall skip on evidence goals (`ai_core`)
- Regression: git_add reject + first-line PASS
- Swarm cursor-method wired in live workers (docker grep)
- Residual: free LLM on unrelated goals can still invent recipes (out of evidence markers)

## Round 9

- Evidence egress: PgBouncer recipe → salvage/refuse (`_refuse_evidence_pgbouncer_bleed`)
- Summarize markers: `what does` / `teach about` → pair `17-18-14` file bullets
- ACCEPT_AS_LIMIT: non-evidence free LLM sticky recipes (real DB talk must still work)

## Round 9b (subagent follow-up)

From [FAIL_THIN empty-body root](87fbf831-2b4b-4431-b6c4-60fef3adc153) / [ExecutionPlan git gap](6fe78294-af63-410d-824e-14cd5f018712) / [R9 residual tails](55794184-31a8-49ea-9e71-40eaeb561270):

- BG `/run` evidence early-exit before Enhanced (`17-20-22` L3 PASS ~4s)
- Drop experience newest-fallback (`_fetch_experience_lessons` + skill-loop)
- `execution_plan_local`: block `python/bash … git` without `ATRA_ALLOW_GIT_MUTATE`
- Salvage includes `process_env_fact_answer`

## Round 10 (multi-file «найди и объясни»)

**Gap:** `grep_line_answer` = single path + `rg -n`; multi-path «Find X in A and B» fell to LLM → invent / PgBouncer risk.

**Fix (KISS):** `multi_grep_line_answer` — 2–3 `_REPO_PATH_RE` paths + quoted/`find` pattern → first hit per file as `path:line:text`; markers `найди`/`find `/`в файлах`; skips when single-path `grep_line` matches. Wired: salvage + `/run` + chat early (`strategy=multi_grep`).

**Verify:**

- pytest `test_first_line_file_reply` → 12 passed
- live pair `pair_2026-11-24_17-43-17-815308.md` — disk lines `:815` / `:1530`, ~250ms, no LLM
- Victoria-section bleed clean (pgbouncer/готово only in lesson text)
- slots 11434=`victoria-qwen38` / 11436=`qwen3-coder:30b` / 11437=`phi`+`nomic`; queue 0|0|0; inflight=0; GATE=swarm_ready

**Residual (ACCEPT):** bare «Объясни» without markers/quote still free-LLM; `tests/` outside `_REPO_PATH_RE` roots. Day pin / Night / 100kna not opened.

### R10b (subagent holes)

From [Expert R10 multi_grep review](5b900377-1cc6-4984-992f-44ec6bdd4179) / [Force-tool vs multi_grep](c43939e2-ddcb-416c-9a0b-83f0a9c7ce0d):

- `grep_line` skips when ≥2 paths; salvage/`/run`/chat try `multi_grep` before single `grep_line`
- markers: `where ` / `quote line`; pattern `Where is Token`
- `ai_pipeline` fallback markers aligned (`найди`/`find `/`в файлах`/`where `/`где `)
- pytest +2 (`rg -n` two-path, `Where is`); `/run` `strategy=multi_grep` verified live

## Round 11 (Объясни / bare tests/)

**Gap:** «Объясни Token в path1 и path2» / `Explain Token` без кавычек → multi_grep None → free LLM invent. Bare `tests/foo.py` не парсился / не резолвился (только `knowledge_os/tests/...`).

**Fix:**

- markers + pattern: `объясни` / `explain` (+ evidence / ai_pipeline fallback)
- `_REPO_PATH_RE` + `tests`; `resolve_repo_file_path` maps `tests/` → `knowledge_os/tests/`

**Verify:**

- pytest `test_first_line_file_reply` → 16 passed
- pair `pair_2026-11-24_17-55-00-436648.md` — `:443` / `:1535`, Multi-file find
- `/run` Explain → `strategy=multi_grep` deterministic
- queue 0|0|0; inflight=0; slots contract; GATE=swarm_ready

**Residual:** голое paraphrase без Token/path markers; day pin / Night / 100kna не открывали.

## Round 12 (single-path Symbol find)

**Gap:** «Объясни/Where/Find Token в path.py» — `is_evidence_tool_goal=True`, но multi_grep требовал ≥2 paths → LLM invent path:line под evidence gate.

**Fix:** `multi_grep_line_answer` 1–3 paths; header `Symbol find` vs `Multi-file find`; single-path `rg -n` всё ещё `grep_line`.

**Verify:**

- pytest 17 passed (`test_symbol_find_single_path_obyasni`)
- pair `pair_2026-11-24_17-57-32-450943.md` — Symbol find `:443`
- `/run` Where is → `strategy=multi_grep` / `model_used=none`

**Residual next:** «quote line N of A and B» — nth_line берёт только первый path; day/Night/100kna не трогали.

## Round 13 (multi nth-line quote)

**Gap:** «Quote line 3 of A and B» → `nth_line` отдавал только первый path (evidence) → LLM invent по второму.

**Fix:** `multi_nth_line_answer` (2–3 paths, same N→`path:N:text`); `nth_line` bail при ≥2 paths; wire salvage/`/run`/chat `strategy=multi_nth`.

**Verify:**

- pytest 18 passed (`test_multi_nth_two_paths`)
- pair `pair_2026-11-24_17-59-47-932045.md` — Multi-line quote disk lines
- `/run` → `strategy=multi_nth` / `model_used=none`
- queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** разные N per file; paraphrase без line/path markers.

## Round 14 (per-path N + multi_first)

**Gap (false-proof):** «line 3 of A and line 5 of B» → multi_nth клеил N=3 на оба → B:3 вместо B:5. «First line of A and B» → только A.

**Fix:**

- `_LINE_N_PATH_PAIR_RE` → per-path N в `multi_nth_line_answer`
- `multi_first_line_answer`; `first_line` bail при ≥2 paths
- wire salvage/`/run`/chat (`multi_first`, `multi_nth`)

**Verify:**

- pytest 20 passed
- pair `pair_2026-11-24_18-02-35-733126.md` — `:3` + `:5`
- `/run` First line A+B → `strategy=multi_first`
- queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** multi-file summarize/git_diff; paraphrase без markers.

## Round 15 (multi summarize + multi git_diff)

**Gap (false-proof):** summarize A+B → только A (выглядит complete). `git_diff A and B` → LLM.

**Fix:** `_summarize_repo_file` + `multi_file_summarize_answer`; `multi_git_diff_answer`; single summarize bail ≥2 paths; wire `multi_summarize` / `multi_git_diff`.

**Verify:**

- pytest 22 passed
- pair `pair_2026-11-24_18-04-47-952962.md` — оба файла
- `/run` git_diff A+B → `strategy=multi_git_diff`
- queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** multi printenv; paraphrase без markers.

## Round 16 (multi printenv — no silent key drop)

**Gap (false-proof):** `printenv ATRA_ALLOW_GIT_MUTATE and PROJECT_ROOT` → только `ATRA_ALLOW_GIT_MUTATE=…` (`PROJECT_ROOT` не в allowlist / не собирался).

**Fix:** allowlist +`PROJECT_ROOT`/`VICTORIA_MLX_BRAIN`; `_env_keys_mentioned_in_goal` возвращает **все** упомянутые allowlisted keys.

**Verify:**

- pytest first_line+fact_seeking → 42 passed
- pair `pair_2026-11-24_18-06-14-305025.md` — оба KEY=
- `/run` has_both True; queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** non-allowlisted env names (secrets — intentional miss); paraphrase без markers.

## Round 17 (single git_diff + line range)

**Gap:** `git_diff path` (1 file) и `Quote lines 3-5 of path` — evidence, early=None → LLM invent.

**Fix:** `git_diff_answer` (1 path) + shared `_git_diff_one`; `line_range_file_answer` (A–B inclusive); wire salvage/`/run`/chat.

**Verify:**

- pytest 25 passed
- pair `pair_2026-11-24_18-09-12-086132.md` — `:3`–`:5`
- `/run` git_diff → `strategy=git_diff` / `model_used=none`
- queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** git_status; file-exists; compare-two paraphrase; first N lines (N≠1 range without «lines»).

## Round 17b (subagent false-proof follow-up)

From [R16 invent](229e9bd7-84e3-4fec-9240-ae585810e170) / [R11 residual](404b1fb8-8dc1-481f-aea1-d05fa0c9eb4f) / [R15 invent rank](6a4123d9-70e9-4012-8f4c-2209cec1a36f):

- `ATRA_ALLOW_GIT_PULL` no longer invents MUTATE/PUSH (bare `atra_allow_git` only)
- `tests/` added to `_FIRST_LINE` / `_NTH` / `_GREP_LINE` regexes
- path-before-N pairs + bail when ≥2 Ns without pairs; multi_first yields mixed first+Nth
- pytest 47 passed (first_line + fact_seeking)

## Round 18 (file_exists + git_status)

**Gap:** EN `does file … exist?` — не evidence / не early → LLM invent EXISTS. `git_status` — evidence, без sync early.

**Fix:** `file_exists_answer` (`path: EXISTS|MISSING`); `git_status_answer`; evidence + ai_pipeline markers; wire salvage/`/run`/chat.

**Verify:**

- pytest 30 passed (`test_first_line_file_reply`)
- pair `pair_2026-11-24_18-28-28-142762.md` — EXISTS
- `/run` git_status → `strategy=git_status`
- queue 0|0|0; GATE=swarm_ready; day pin sacred

**Residual:** compare-two content; paraphrase без markers.

## Round 18b (summarize/compare false-proof)

From [R18 residual rank](829d4f68-5d59-4adc-bb43-4dd89c6755a0) ([R18 design](7e4c44da-ed41-4646-b8cd-b4432ac9b7c8) wire already done in R18):

- `What does SYMBOL do in PATH` → bail summarize; `multi_grep` via `what does … do`
- `Compare`/`сравни` → bail multi_summarize; `file_compare_answer` (sha256 short → IDENTICAL/DIFFER)
- pytest 32; pair + `/run` file_compare verified

## Round 19 (colloquial locate)

**Gap:** `Quote the line with TOKEN`, `На какой строке TOKEN`, `Read first 5 lines`, `top of A and B` → early=None → LLM invent.

**Fix:**

- `multi_grep_line_answer`: markers + extract for quote/line with / на какой строке / is TOKEN in
- `line_range_file_answer`: `first|первые|первых N lines|строк`
- `multi_first_line_answer`: `top of` / beginning / opening
- evidence + ai_pipeline markers (без широкого `first `)

**Verify:**

- pytest 36 → then 41 after R19b
- pair `pair_2026-11-24_18-33-55-054481.md` — Symbol find `process_env_fact_answer`
- `/run` Quote→`multi_grep`; first 5→`line_range`; top A+B→`multi_first`; model_used=none
- GATE=swarm_ready; day pin `victoria-qwen38*`

**Residual (subagent invent):** false-proof `what line contains` / `Where does X live`; single `top of`; `Is X defined in`; `в какой строке`.

## Round 19b (false-proof + miss colloquial)

**Gap (false-proof):** `what line contains TOKEN` → TOKEN=`contains`; `Where does TOKEN live` → TOKEN=`does`.

**Fix:** `where does TOKEN` before generic where; quote/what-line allow contains/containing; blacklist does/contains/containing/live/defined; `TOKEN defined in`; `(на|в) какой строке`; single-file `top of` → `first_line_file_answer`.

**Verify:**

- pytest 41 passed (`test_first_line_file_reply`)
- pair `pair_2026-11-24_18-37-07-850842.md` — Where does… → Symbol find `process_env_fact_answer`
- `/run` contains / defined in / в какой строке → `multi_grep`; single top of → `first_line_file`; model_used=none
- GATE=swarm_ready

**Residual:** word-number `first five lines` (digit-only N); paraphrase без markers; list_directory early (optional).

## Round 20 (list_directory + line-locate false-proof)

From invent scan residual + Quote-the-line confirm (widen already on disk).

**Gap:**

- `list_directory src/agents/bridge` — FREE_MISS → LLM invent trees
- `What line number is TOKEN on` → pat=`number` (false-proof)
- `На какой строке определён TOKEN` → miss-to-LLM
- `Does file_exists_answer exist in PATH` → `file_exists` EXISTS (false-proof)

**Fix:**

- `list_directory_answer` + `_REPO_DIR_RE` + `resolve_repo_dir_path`; evidence markers; wire salvage/`/run`/chat `strategy=list_directory`
- salvage/sync: multi_grep **before** file_exists
- extract `what line number is TOKEN`; `(на|в) какой строке определён TOKEN`; `Does TOKEN exist in`; blacklist `number`/`on`/`определён`
- `file_exists_answer` bails on symbol-in-file asks

**Verify:**

- pytest 45 passed
- pair `pair_2026-11-24_18-42-27-498945.md` — `task_detector.py` in listing
- `/run` list_directory / multi_grep ×3; model_used=none; queue 0; inflight 0; GATE=swarm_ready

**Residual:** word-number `first five lines`; bare `ls` without allowlisted dir; paraphrase без markers.

## Round 21 (word-N + bare ls refuse + XOR -stable)

From user tail + [word-N invent](cb839596-4480-4b02-9496-7abc8585ea65) + [11437 XOR](9aeb212a-6035-4965-a3e0-c20420a10cf0).

**Gap:**

- `first five` / `первые пять` → digit-only regex → LLM
- bare `ls` → FREE_MISS → LLM invent trees
- 11437 tags show both phis (looked like XOR breach)

**Fix:**

- `_WORD_TO_INT` one..ten + RU; `line_range` accepts word-N
- bare list markers without `_REPO_DIR_RE` → deterministic Error (allowlisted dir required)
- `ollama_wisdom_guard._should_unload_hands`: unload any phi\*stable (tags≠VRAM; live `/api/ps` was already base+nomic)

**Verify:**

- pytest first_line+coder_slot → 69 passed, 1 skipped
- pair `pair_2026-11-25_07-09-05-719309.md` — lines 1–5
- `/run` first five / первые пять → `line_range`; bare `ls` → `list_directory` Error; `ls src/agents/bridge` → names
- 11437 `/api/ps` = `phi3.5:3.8b` + `nomic` only; queue 0; GATE=swarm_ready

**Residual:** paraphrase без markers; eleven+ word-N (intentional None).

## Round 22 (false-proof locate + colloquial range)

From [post-R21 invent](5f734b20-eb16-49b0-ac6c-5eeb262bac8c).

**Gap (false-proof):**

- `Locate definition of TOKEN` → TOKEN=`definition` → `_definitional` hit
- `Find where TOKEN is declared` → TOKEN=`declared` → false absence under evidence

**Gap (miss):** `где лежит`; `top five lines`; `which line has`; `lines 1 through 5`; `head -n 5`

**Fix:** extract `locate definition of` / `where TOKEN is declared|defined`; `где лежит|находится`; `which line` / `line containing`; blacklist definition/declared/…; `line_range` + `top|opening` + `through` + `head -n`

**Verify:**

- pytest 55 passed (`test_first_line_file_reply`)
- pair `pair_2026-11-25_07-14-15-708686.md` Locate definition → `:490` `process_env_fact_answer`
- `/run` multi_grep/line_range; model_used=none; queue 0; GATE=swarm_ready; 11437 `/api/ps` base+nomic

**Residual:** paraphrase без path; `opening lines` без N; word-N > ten.

## Round 23 (Where can I find + definition/opening paraphrases)

From [post-R22 invent](1dc842c7-a6af-4388-893b-cb23db0e1133); regression [R19–R22 smoke](1edafe52-a7e5-434b-af5f-5bd6c5e730d6) green.

**Gap (false-proof):** `Where can I find TOKEN` → TOKEN=`can` → canary `:31`.

**Gap (miss / soft FP):** `Find the definition of`; `What line is TOKEN on`; `opening lines` / `first few`; `где объявлен`; `what files are in`; first_line hijack when N>1 with top/opening.

**Fix:** modal where-can extract + blacklist can/might/…; broaden definition-of; what line is TOKEN; opening/few → range 1–5; first_line bail if count; где объявлен / строчке; list markers what files.

**Verify:**

- pytest 61 passed
- pair `pair_2026-11-25_07-18-33-681286.md` Where can I find → `:490` process_env_fact_answer
- `/run` multi_grep/line_range ×5; model_used=none; queue 0; 11437 `/api/ps` base+nomic; GATE=swarm_ready

**Residual:** last/tail N lines; wc -l; paraphrase без path; word-N > ten.

## Round 24 (last/tail + wc -l + pathless refuse)

From [post-R23 invent](46c7372a-dabc-4fbc-a755-007a154ffa72); [R21–R23 smoke](302a0d8d-57a5-4e99-ab4e-e0970b602ef7) OK.

**Gap:**

- false-proof: `last N + first/top` → `first_line` only
- miss: `last 5` / `tail -n` / `wc -l` / pathless evidence locate / `eleven` / `строчке` / bare `grep TOKEN`

**Fix:**

- `first_line` bail on last/tail/bottom
- `line_range` last/tail/bottom/последн/from end
- `line_count_file_answer` + wire salvage/`/run`/chat
- pathless multi_grep → Error path required
- `_WORD_TO_INT` 11–20 EN/RU; marker `на какой стро`; bare grep/rg/highlight

**Verify:**

- pytest 67 passed
- pair `pair_2026-11-25_07-25-03-415482.md` — last 5 lines (`:2481`–`:2485`)
- `/run` line_range / line_count / pathless Error; model_used=none; queue 0; 11437 `/api/ps` base+nomic; GATE=swarm_ready

**Residual:** mixed last+first still returns last window only; paraphrase без markers; word-N > twenty.

## Round 25 (dual first+last + multi_first bail)

From [post-R24 invent](25a50138-1736-458a-97a8-81386251fde7); [R22–R24 smoke](f3b3b358-a6b7-4606-b163-53f900236404) OK.

**Gap (false-proof):**

- `multi_first` stamped B:1 on first+last multi-path
- `line_range` collapsed first+last to one window

**Gap (miss):** `number of lines`; `trailing N`; `thirty`; `PATH contain TOKEN`

**Fix:** multi_first bail on last/tail; dual-window concat (`first A and last B` / `last … and first line`); line_count markers; trailing/ending; thirty/twenty-five; contain/mentioned extract.

**Verify:**

- pytest 73 passed
- pair `pair_2026-11-25_07-30-07-882201.md` — 10 lines (`:1`–`:5` + `:2569`–`:2573`)
- `/run` dual / number of lines / contain; model_used=none; queue 0; 11437 `/api/ps` base+nomic; GATE=swarm_ready

**Residual:** sed -n; context before/after symbol; git blame; word-N sparse above 30.

## Round 26 (sed / context± / blame / forty)

From [post-R25 invent](9c0c2d01-9b4c-43e1-9d7d-057969e24eca); [R24–R25 smoke](442c3023-a3e9-4c6b-bded-1572c4b3bf57) OK.

**Gap (false-proof):** blame / next-after / ±around hijacked by nth/multi_grep.

**Gap (miss):** `sed -n 'A,Bp'`; context±TOKEN; git blame; word-N forty/fifty.

**Fix:** nth/multi_grep bail on blame/window; `line_range` sed + next-after + ±around line; multi_grep ctx window (-C / before-after); `git_blame_answer` (-L / symbol, refuse bare path); forty/fifty/sixty.

**Verify:**

- pytest 79 passed
- pair `pair_2026-11-25_16-56-59-714601.md` — context± around `:490`
- `/run` sed / context / blame / forty / next-after; model_used=none; queue 0; 11437 `/api/ps` base+nomic; GATE=swarm_ready

**Residual:** awk/pipe sed variants; function-body paraphrase; sparse word-N > 60.
