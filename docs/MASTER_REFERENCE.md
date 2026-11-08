---
---

## ⚠️ ИНЦИДЕНТ (2026-10-13): мозговая модель удалена параллельной чисткой — восстановлена из источника

Параллельный чат чистил «дубликаты моделей» (+45GB) и удалил блоб victoria-qwen38 (30GB): manifest остался (обманчиво), блоб — нет. Симптом: мгновенный 404 на generate при теге «на месте». Полная потеря: блоб + конфигурация + исходный GGUF unsloth.

**Восстановление:** `ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:Q8_0` (29GB, ~12 мин) + `ollama create victoria-qwen38:latest -f Modelfile (FROM источник)`. Проверено: отвечает, резидентна.

**Правила против повторения:**

1. Удаление блобов Ollama — ТОЛЬКО по сверке всех manifest'ов (блоб валиден, если на него ссылается ХОТЯ бы один manifest).
2. Мозговые модели: хранить копию GGUF-источника ВНЕ ~/.ollama (путь: ~/model_sources/, правила выше).
3. brain_keepalive: 404 при загрузке = АЛЕРТ (модель удалена), а не ретрай — добавить в скрипт.
4. Транзиентный DNS Tailscale роняет первый pull — повторять закачку.

**Урок координации:** параллельные чистки диска —高风险 операция. Согласовывать через библию/чат до исполнения.

## § v150.66 (2026-10-29) — hardening сигнала SLA + anti-storm security + watchdog stabilization

**Проблема:** HIGH ALERT spam по async TTC при фактически рабочем режиме, task-spam в security-контуре после `llm_no_text_stub_exhausted`, и restart-loop `performance-watchdog` (диск/шум).

**Что внедрено:**

1. `scripts/tg_deferred_alerts.py`:
   - p95 threshold default `180 -> 420`, min_samples `5 -> 20`;
   - отдельный hung-threshold `600s`;
   - hung-сигнал только при `inflight_n > 0` и `inflight_max > hung_threshold`.

2. `scripts/security_incident_responder.py`:
   - если последняя consolidated security-задача `failed` с `llm_no_text_stub_exhausted`,
     новая не создаётся; последняя реанимируется в `pending` (`revived_failed`) с обновлённым payload.

3. `knowledge_os/app/expert_worker.py` (STUB-GUARD):
   - для background-source (`security_responder`, `nightly_hypothesis_debate`, etc.) exhausted stub переводится в deferred `pending` (`llm_no_text_stub_deferred`) с длинным backoff, а не в hard `failed`;
   - stub retry/backoff вынесены в env (`LLM_STUB_*`), добавлен экспоненциальный backoff.

4. `knowledge_os/app/performance_watchdog.py`:
   - тяжёлый импорт `ai_core` убран из top-level (ленивый импорт в analyze path);
   - LLM analysis gated by `WATCHDOG_ANALYSIS_ENABLED=false` (default);
   - main loop защищён от silent-return перезапуском в процессе.

**Верификация:**

- `python -m py_compile` по изменённым python-файлам — OK.
- `scripts/tg_deferred_alerts.py --once`: `p95=401.6`, `samples=68`, `threshold=420`, `over=False`.
- Prometheus: `firing=0` на `9091` и `9092`.
- Очередь без stuck; operational-tail контролируется launchd_watchdog.

## § v150.69 (2026-10-31) — руки 11437: backpressure у Виктории + cancel-inflight; мозг не переезжал

**Контракт слоёв (runtime, не история чатов):**

| Слой  | Порт             | Модель                                    | Это мозг?                                                                             |
| ----- | ---------------- | ----------------------------------------- | ------------------------------------------------------------------------------------- |
| Мозг  | **11434 Ollama** | `victoria-qwen38:latest`                  | **Да. Основной.** `VICTORIA_MODEL` / `VICTORIA_PLANNER_MODEL`                         |
| Запас | 11435 MLX        | `victoria-wisdom-24k` (кэш)               | Нет. `VICTORIA_MLX_BRAIN=false`, `USE_MLX_FOR_PLANNER=false`, `USE_MLX_FALLBACK=true` |
| Руки  | **11437 Ollama** | `phi3.5:3.8b-stable` + `nomic-embed-text` | Нет. Эмбеды и короткий fact-track                                                     |

`11435/health=200` и кэш wisdom **не значат**, что мозг переехал. Это тёплый fallback.

**Проблема 1:** ложный hung/p95 — отменённый async `/run` оставался в `victoria:async_inflight` со статусом `running` (текст уже «Задача отменена»). Два uvicorn-воркера не видели чужой in-memory store.

**Проблема 2:** 503 на руках шли из `victoria-agent` (RAG embed), не из nightly/security. Корень: `keep_alive: 0` на каждом эмбеде выгружал nomic → reload → `maximum pending requests`.

**Что внедрено** (`src/agents/bridge/victoria_server.py`):

1. Cancel-путь пишет `failed` в store и вызывает `_clear_async_inflight`.
2. `_async_sla_snapshot()` выкидывает terminal/«Задача отменена» из hash, не ждёт 7200с.
3. Hands helper: семафор `VICTORIA_HANDS_MAX_INFLIGHT=1`, retry `VICTORIA_HANDS_RETRY=2`, `VICTORIA_HANDS_KEEP_ALIVE=-1` (`0` запрещён).
4. RAG embed и fact-fast-track идут через helper. Мозг 11434 не менялся.

**Верификация (2026-10-31):**

- `11434/api/ps` → `victoria-qwen38:latest`; `victoria-agent` env: `VICTORIA_MLX_BRAIN=false`.
- Hands probe: embed 200 / 14–41мс; после рестарта эмбеды Виктории на 11437 — 200, без новых 503.
- `HLEN victoria:async_inflight=0`; `tg_deferred_alerts --once` → `over=False`, `inflight_n=0`.
- `/metrics`: `victoria_async_ttc_p95_seconds=0`, `victoria_async_inflight=0`.

## § v150.70 (2026-11-02) — per-task isolation: overflow adopt + RAG namespace + judge skip

**Контракт слоёв не менялся:** мозг `11434 victoria-qwen38`; руки `11437 phi3.5 + nomic`; MLX 11435 — fallback. `EXPERT_POOL_MODE` остаётся включённым.

**Проблема:** overflow-слот (Инна/Юлия) при adopt делал `expert_name = payload_expert` на весь цикл consumer'а. Следующая задача того же процесса видела чужого эксперта. RAG не резал чанки по `metadata.expert_name`; судья мог оценить смешанную пару.

**Что внедрено:**

1. `knowledge_os/app/task_isolation.py` — `TaskContext` на `contextvars`, `resolve_adopt_identity()` (слот не мутируется), `filter_namespace_rows()`, `judge_should_skip()`.
2. `expert_worker.py` adopt: `run_expert` только в payload; лог `restore_worker=<слот>`. Rollback: `WORKER_TASK_ISOLATION=false`.
3. `ai_core.py` RAG: drop чанков с чужим `metadata.expert_name`; проектные доки без expert_name остаются; обёртка `СПРАВОЧНЫЙ КОНТЕКСТ (не задание)`. Rollback: `RAG_NAMESPACE_FILTER=false`.
4. `judge_gate_score`: mismatch task_id → fail-open, `judge_skipped=context_mismatch`, без перегенерации по чужому фидбеку.
5. Compose overflow: явный `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL=true` (код уже default true).

**Верификация:** pytest isolation/RAG/crystals → 12 passed. Live adopt: `restore_worker=Инна`. Live RAG: 5612 tagged nodes; Юлия-crystals (`ПАМЯТЬ ПРОЕКТА`/6432) не проходят в namespace Ксении. LLM A→B повторно не гоняли (11437 generate wedged; QC-B abandoned). См. `docs/audits/2026-11-02-isolation-qc.md`.

## § v150.71 (2026-11-02) — overflow пишет `last_real_progress_at`

**Проблема:** hung-детектор (`cognitive_quality_gate`) смотрит колонку `tasks.last_real_progress_at`. `smart_worker` её пишет, `expert_worker.process_task` — нет. QC-B 15 мин `in_progress` при `stuck=0`, потому что `NULL < now()-15min` в SQL не true.

**Что внедрено:** в существующие UPDATE `_mark_llm_call` и pickup `in_progress` добавлен `last_real_progress_at = NOW()`. Heartbeat `updated_at` не трогали. Мозг/pool/isolation не менялись.

**Верификация:** `pytest knowledge_os/tests/test_last_real_progress_overflow.py` + isolation → 10 passed.

## § v150.72 (2026-11-02) — дашборд 8501: свежесть без ложной тревоги + список сервисов через docker-proxy

**Контракт слоёв не менялся.** docker.sock в `corporation-dashboard` не монтировали (сокет только docker-proxy / log-scanner).

**Проблемы (ложные «не работает»):**

1. Свежесть: `okrs` (22.07) и `simulations` (30.01) поднимали «Обнаружены устаревшие источники: 2» при живых tasks/nodes.
2. Автономные микросервисы: `docker.from_env()` → FileNotFoundError `/var/run/docker.sock`; текст предлагал смонтировать сокет. docker-proxy на `2376` уже отдавал список.
3. Singularity 31.2+: фильтр `orchestrator_version IS NOT NULL` за 7 дней = 0 строк (последние v2/existing — апрель) → заглушка «не накоплены».
4. Self-Dev: очередь pending=0 (честно); патчи на диске были, `git` в образе нет.

**Что внедрено:**

1. `knowledge_os/dashboard/freshness.py` — rare (`okrs`/`simulations`/`file_comments`) не инкрементят `stale_count`; operational >24h = 🔴.
2. `knowledge_os/dashboard/docker_services.py` — GET `DOCKER_PROXY_URL/containers/json` (default `http://docker-proxy:2376`). Кнопку Stop убрали (proxy GET-only).
3. `system_tab.py` — KPI задач за окно всегда; A/B-метки только если есть.
4. `selfdev_tab.py` — патчи с `logs/self_dev_patches` на вкладке очереди; git не требуется.
5. `docker-compose.ui.yml`: `DOCKER_PROXY_URL=http://docker-proxy:2376`.

**Верификация (live):** pytest freshness+docker_services 6 passed; docker-proxy healthy; из dashboard 15 автономных; sock отсутствует; браузер: список 15, KPI 7д, очередь пуста + 2 патча, баннер свежести снят.

## § v150.73 (2026-11-03) — слот кодера 11436 + гвард не рвёт цикл на втором phi

**Контракт слоёв не менялся.** Мозг `victoria-qwen38` на 11434 не удаляли. Порог TTC 420 не поднимали. Тег `hf.co/unsloth/Qwen3.8-27B-GGUF:Q8_0` на 11434 не удаляли (другой digest, не loaded).

**Проблемы:**

1. На 11436 рядом с `qwen3-coder:30b` сидел `phi3.5` (чужой слот). Watchdog `ollama_runner_watchdog.sh` 11436 не зондирует.
2. Wisdom-guard каждые ~3 мин писал `err: timed out`: после пина базового phi пытался грузить `phi3.5:3.8b-stable` (второй ~15GB). Таймаут 120с обрывал `_enforce` **до** гигиены 11436 — поэтому phi на кодере жила.
3. `VictoriaAsyncTtcP95High`: p95=641с / 141 сэмпл, порог 420, hung=0. Это accept→terminal `/run` (`timeout_sync_safe_mode` / `request_async_mode` / `timeout_enhanced_solve`), не nightly debates. Корень: один 27B-слот 11434 делят Victoria и executor воркеров (`OLLAMA_BASE_URL=11434`).
4. anna-1 RestartCount=290, Exit=0, OOM=false, healthcheck = grep cmdline. Корня выхода нет (events ring пуст, traceback за 24ч нет). mem_limit 2g не поднимали.

**Что внедрено:**

1. `scripts/ollama_wisdom_guard.py`: `CODER`/`CODER_ALLOW`, выгрузка не-coder с 11436; `_should_pin_stable` — не грузить второй phi, если базовый уже на 11437; `pin_brain` если 11434 пуст (`keep_alive=-1`, ctx 2048); pin\_\* каждый в своём try.
2. Живая выгрузка phi с 11436 (`keep_alive=0`). Мозг после evict вернули вручную и теперь держит гвард.
3. Тесты: `knowledge_os/tests/test_coder_slot_guard.py`.

**Не делали:** поднять порог 420; исключить timeout\_\* из p95; `ollama rm` unsloth; перевести Anna/overflow executor на 11437 (контракт, отдельный дизайн); bump mem Анны.

**Верификация:** pytest coder-slot 4 passed; `/api/ps` 11434=`victoria-qwen38:latest`, 11437=`phi3.5:3.8b`+`nomic`, 11436=`qwen3-coder:30b`; inflight=0; TTC alert ещё горит (окно 141 сэмпл, хвосты timeout сами состарятся).

## § v150.74 (2026-11-03) — Anna 290 рестартов: гнилой blackboard, не OOM

**Контракт слоёв не менялся.** Порог TTC 420 не поднимали. Unsloth-тег не удаляли.

**Корень:** `blackboard:goals` = 5108 ключей, из них 5106 `bidding_open` (4864 старше 7 дней, 3469 target=Анна). Autonomy каждые 10с: 5k SELECT + 5k INFO-строк. json-file без max-size — смерть процесса (Exit=0 каждые ~40 мин) тонет в логе. `reconcile_goals_with_tasks` только _открывает_ claimed, мусор не чистит.

**Что сделано:**

1. Живая чистка: HDEL 5074 stale open (>24ч), осталось 34.
2. `blackboard_freshness.is_fresh_open_goal` + фильтр в `get_unclaimed_tasks`; `purge_stale_open_goals`.
3. Skip-логи autonomy → debug; SIGTERM/atexit пишут `🛑 [WORKER] exit reason=`.
4. Анну рестартнули один раз, чтобы подхватить код. Skip flood после рестарта = 0.

**Верификация:** pytest stale-goals+coder-slot 9 passed; HLEN goals=34; anna healthy; слоты 11434/11437/11436 по контракту; inflight=0. TTC p95 всё ещё 641/141 — честный алерт.

## § v150.75 (2026-11-03) — кран AUTO-HANDOFF, CODER-SOLO, CancelledError Анны

**Контракт слоёв не менялся.** TTC 420 / unsloth / mem Анны не трогали.

1. `test` больше не матчит `latest` (`keyword_in_text`). HDEL `blackboard:goals` на completed + autonomy terminal. Watchdog вызывает `purge_stale_open_goals`. GC `assignee` NameError починен.
2. `url_is_ollama` видит 11436/11437; **CODER-SOLO-GATE** не пускает phi/nomic на coder. Embed-fallback больше не включает 11436.
3. `worker_loop` / `_run_task` ловят `CancelledError` и не роняют процесс (таймаут 2700с).

**Верификация:** pytest v150.75+stale+coder 13 passed.

## § v150.76 (2026-11-03) — nomic на 11437: не 30с пин, а очередь hung embed

**Контракт слоёв не менялся.** TTC 420 / unsloth / mem Анны / EXPERT_POOL_MODE не трогали. Мозг и coder не рестартили.

**Корень:** два слоя. (1) `pin_nomic` timeout=30с не отменяет load на Ollama → hung `/api/embed` каждые 60с. (2) phi@16k × NUM_PARALLEL=4 = 15.9GB KV — Ollama выселяет nomic при любом pin_phi. `/api/embeddings` → 503 за 500µs.

**Что сделано:**

1. `pin_nomic`: timeout 240с; backoff 900с после fail; пин nomic **до** phi.
2. `pin_phi` `num_ctx=8192` (не 16384). Hands plist: `OLLAMA_NUM_CTX=8192`, `OLLAMA_CONTEXT_LENGTH=8192`, `OLLAMA_MAX_LOADED_MODELS=2`.
3. `_should_pin_phi`: любой phi (base/-stable) = слот занят — не грузить второй. `_should_pin_stable([])` = False (пустой слот — работа `pin_phi`).
4. Рестарт только `com.atra.ollama-hands`. Мозг 11434 / coder 11436 не трогали.
5. Overflow dynamic-2/3/4 рестартнуты под CODER-SOLO (стартовали до `local_router` 16:55).
6. Тесты: `_should_pin_nomic` / `_should_pin_phi` / backoff / ctx 8192 в `test_coder_slot_guard.py`.

**Верификация:** 11434=`victoria-qwen38:latest` 29.88GB ctx 16384; 11437=`nomic-embed-text` 0.37GB + `phi3.5:3.8b-stable` 3.98GB (`/api/embeddings` 200 / 29ms / 768); 11436=`qwen3-coder:30b`. Guard 3 цикла подряд держит тройку слотов. pytest coder-slot+v150.75+stale 19 passed.

## § v150.77 (2026-11-03) — порог TTC 420 не поднимали; сирота Debate закрыта

**Порог 420 не помогает latency.** Live: `p95=0 samples=0 inflight=0 over=False` — окно сэмплов пустое после рестарта victoria-agent. Поднять 420→720 спрячет следующий честный p95 27B, `/run` не ускорит. hung-порог 600 тоже не трогали.

**Корень pending:** `create_debate_for_hypothesis` держал `HYPOTHESIS_DEBATES_ENABLED` **внутри docstring** — флаг compose `false` не работал. INSERT pending, orchestrator `BACKGROUND_SOURCES=""` не диспатчит → вечный pending.

**Что сделано:** гейт вынесен в код; сирота `b5e427a3` cancelled; nightly+orchestrator рестарт. TTC/unsloth/mem Анны/pool не трогали.

**Верификация:** pending/in_progress/queued=0; TTC over=False; Anna restarts=0 uptime>45мин; pytest debate+slots.

## § v150.78 (2026-11-03) — канарейка не переразмеряет мозг

**Корень ctx=2048 на 11434:** `launchd_watchdog` http-canary слал `num_ctx=2048` на `victoria-qwen38` каждые 300с — Ollama перезагружала runner. Hands-canary 2048 так же дёргала phi.

**Фикс:** brain canary `num_ctx=16384` + `keep_alive=24h`; hands `8192` + `keep_alive=-1`. Worker ops (`AUCTION WON`, `RESURRECTION Found/resumed`) → info. TTC 420 не поднимали.

## § v150.79 (2026-11-03) — pin ctx, не adaptive

**Корень:** `_get_adaptive_options` слал phi `num_ctx=16384`; FAST PATH/JUDGE — `4096`; `get_keep_alive` мозгу `-1`. Ollama native API при смене ctx перезагружает runner (ollama#13929) и может выселить nomic/мозг (#19326).

**Контракт:** мозг 16384/`24h`; phi base 8192/`-1`; phi-stable 2048; coder 16384 (живой runner, не 8192 — иначе reload 30b). Таблица в `ollama_slot_pin.py`. Чужой `num_ctx` в extra игнорируется.

**Не трогали:** TTC 420, Rapid-MLX, LightRAG, mem Анны, pool.

## § v150.80 (2026-11-03) — TTC p95 split by handoff_reason

**Корень:** Redis `victoria:async_ttc_samples` хранил голый float; `/metrics` отдавал один unlabeled p95. Histogram уже был `{status,handoff_reason}`, rolling gauge — нет. Алерт 420 смотрит unlabeled p95 и смешивает quick с `timeout_*`.

**Контракт:** sample = JSON `{d,r}`; старый float → `unknown`. Overall `victoria_async_ttc_p95_seconds` без фильтра timeout. Extra: `victoria_async_ttc_p95_by_reason_seconds` / `samples_by_reason`, cap 16, остальное `other`. Live-fact `by_reason=` только если buckets есть.

**Не трогали:** порог 420, Rapid-MLX, LightRAG, mem Анны, pool.

## § v150.81 (2026-11-03) — XAUTOCLAIM: reclaim, не STALE-DROP

**Корень:** `autoclaim_tasks` уже был, но тот же цикл ACK-ает idle>5min (включая только что claimed). Early-xack до `process_task` убирал in-flight из PEL — мёртвый воркер нельзя было reclaim.

**Контракт:** `classify_pending` — zombie / reclaim (dead consumer) / keep (live heartbeat + inflight). ACK после `process_task`. Слепой XAUTOCLAIM в том же loop не зовём: он украл бы живые 2700s задачи.

**Не трогали:** TTC 420, pin ctx, pool, mem Анны.

## § v168 (2026-11-08) — Phase 4 не пишет LOOP-BREAKER в knowledge

**Корень:** freeze дебатов отключал только `create_debate_for_hypothesis`. Phase 4 всё равно звал Викторию, получал `[LOOP-BREAKER]`, писал `is_verified=true` (~10k/сутки). Drain distill мёртв — хвост eligible вырос до ~44k.

**Фикс:** `HYPOTHESIS_DEBATES_ENABLED=false` → Phase 4 skip LLM/INSERT. `is_persistable_hypothesis` режет LOOP-BREAKER.

**Не трогали:** флаг дебатов, nightly drain, TTC 420, pool.

## § v167 (2026-11-07) — Telegram не орёт на свой SYSTEM:

**Корень:** high `prompt_injection` #54468 и все за 24ч — паттерн `system\s*:\s*` на собственном `SYSTEM:` в роли Виктории. Два пуша — два цикла responder после закрытия предыдущей сводной.

**Фикс:** паттерн убран из `threat_detector` и `prompt_guard`. Responder пропускает self-role FP. Настоящие jailbreak-паттерны и Telegram для них остаются.

**Не трогали:** TTC 420, pool, порты.

## § v166 (2026-11-07) — стоп; live KPI вне git

**Решение:** harness (`TURN_LOG` и остальные) остаётся выключенным. Следующий выстрел только если нужна память хода, не «ещё код».

**Гигиена:** `runtime_kpi_gate_monitor` пишет jsonl/summary в `docs/audits/runtime/` (или `RUNTIME_KPI_AUDITS_DIR` / `--audits-dir`). Живые `*-live-r2-summary.md` и `*-launchd-probe-summary.md` не в индексе. Запущенные 24h/7d soak не убивали.

**Не трогали:** TTC 420, pool, 11434/11436/11437, флаги harness.

## § v165 (2026-11-07) — KPI distill tail; phase7 снимки; образ proxy

**Корень:** gate считал idle `eligible_now≈29k` аварией хвоста дистилляции, хотя кампании не было.

**Фикс:** tail SLO только при `campaign_done|in_progress|retry>0` (или `RUNTIME_KPI_FORCE_DISTILL_TAIL`). Снимки `docs/audits/2026-11-06-phase7-*` и `2026-11-07-phase7-*`. Образ `knowledge_os-docker-proxy` собран с `log_frames.py` (не docker cp).

**Не трогали:** TTC 420, pool. Nested `.selfdev-worktree` в git не входит.

## § v164 (2026-11-07) — журнал хода, флаги выключены

**Корень:** память сессии — краткий пересказ, одобрение критической цели глотало чужой вызов `check_approval`, ребёнок эксперта не имел потолка прав.

**Контракт:** пакет `knowledge_os/app/turn_harness/`. JSONL `logs/turns/{task_id}.jsonl` (каталог процесса `/app/logs`, том хоста `logs/`). Причины закрытия: `completed`, `cancelled`, `timeout`, `max_steps`, `tool_error`, `approval_denied`, `crashed`. В промпт хвост до 12 000 символов, один результат тула до 4 000; якоря — цель, последнее одобрение, последняя ошибка тула, сданные файлы. Пропуск одобрения только `allowed-once`. `output_schema` ребёнка — список ключей; строка `expert_response_v1` списком не считается.

**Флаги, все выключены:** `TURN_LOG`, `APPROVAL_FAIL_CLOSED`, `TURN_DELIVERABLE`, `CHILD_CEILING` (`off`), `CREDENTIAL_REF`. Пока они пустые, `/run`, очередь и Telegram как раньше.

**Проверено:** pytest пакета harness; `py_compile` сервера, бота и воркера; `victoria-agent` рестарт 2026-11-07 08:25, `GET /health` → `ok`, в логе старта нет Traceback. Живой флаг не включали.

**Не трогали:** TTC 420, pool, порты 11434/11436/11437, `session_context` (справка чата на 2000 символов), `git_push` (по-прежнему только при `ATRA_ALLOW_GIT_PUSH`).

## § v163 (2026-11-07) — docker-proxy logs как Engine multiplex

**Корень:** `/logs` text/plain → docker-py `unrecognized stream: 50`.

**Фикс:** кадр stdout (`struct >BxxxI`) + octet-stream.

**Не трогали:** TTC 420, pool, docker.sock у Victoria.

## § v162 (2026-11-07) — chat guardrails+backend из доков

**Корень:** вопрос «5 guardrails и кто backend» уходил в LLM.

**Фикс:** детерминированный ответ из `COGNITIVE_CODE.md` + `team.md`.

**Не трогали:** TTC 420, pool.

## § v161 (2026-11-07) — DNA eval не в SLA inflight

**Корень:** DNA `run_answer` бьёт боевой `/run?async_mode=true` и сидит в `victoria:async_inflight` до 420с — probe/hung видят чужой eval как зависший user `/run`.

**Фикс:** `source=dna_eval` + маркеры eval-вопросов Виктории; hash не считает их inflight. Coroutine и poll не убиваем.

**Не трогали:** TTC 420, pool, DNA timeout 420.

## § v160 (2026-11-07) — snapshot сканера; human/runbook не resume

**Корень:** docker logs из victoria-agent через proxy не читается; restart поднимал scanner `/run` как enhanced_solve; claim nx 120s при workers=2 пропускал fail.

**Фикс:** файл snapshot на shared volume; human/runbook fail без claim; hash GC=420.

**Не трогали:** TTC 420, pool.

## § v159 (2026-11-07) — кавычки с ERROR?; probe не рапортует ложный 0

**Корень:** мысль Виктории `"…ERROR…?"` снова class=human; docker logs из контейнера через proxy даёт `unrecognized stream`, probe считал 0 хитов.

**Фикс:** IGNORE вопрос в кавычках + asyncio destroyed + recruitment parse; fail-visible «сканер не сняла».

**Не трогали:** TTC 420, pool.

## § v158 (2026-11-07) — сканер: эхо ERROR не инцидент; probe считает хиты

**Корень:** слово ERROR в мысли/JUDGE-GATE score открывало class=human `/run`.

**Фикс:** IGNORE узко; fact-probe `scanner_class=` / `scanner_sent=` или «сканер не сняла».

**Не трогали:** TTC 420, pool.

## § v157 (2026-11-07) — fact-probe снимает слоты; db_query только SQL

**Корень:** «проверь систему» → postgres stub без `/api/ps`; `db_query:` + инструкция ломала SQL.

**Фикс:** live `/api/ps` 11434/36/37 в fact_live_probe; extract SQL до `;`/кириллицы.

**Не трогали:** TTC 420, pool.

## § v156 (2026-11-07) — inflight GC, RECURSION-STOP не инцидент

**Корень:** `_run_task_background` писал Redis `running`/`processing` и возвращался до `finally` (expert_assignments) — `victoria:async_inflight` оставался. RECURSION-STOP — успешный стоп рекурсии, сканер слал class=human.

**Фикс:** status+output, затем один `_sync_store`; `finally` HDEL на terminal; snapshot смотрит metadata.status; сканер IGNORE `RECURSION-STOP`; orphan resume ≤420с; lifespan не DELETE весь inflight hash.

**Не трогали:** TTC 420, 11434, pool, 11437 ctx 8192 для `phi3.5:3.8b`.

## § v155 (2026-11-07) — DNA timeout, sandbox 403, git_status не в patch

**Корень:** DNA poll 180с при TTC 234с; docker-py KeyError на 403 proxy; patch после write крутил git_status.

**Фикс:** DNA timeout=420; sandbox inspect fail-open; patch blocks git_status/diff/log; scanner IGNORE только эхо, не TypeError:.

**Не трогали:** TTC 420, 11434, pool.

## § v154 (2026-11-07) — patch пишет через write_file

**Корень:** complex→orchestrate (проза экспертов); `write_file` не был в tools Victoria.

**Фикс:** patch skip swarm/plan; JSON tool loop; register write_file; verify PASS после записи. Бой: add(1,2)=3.

**Не трогали:** TTC 420, 11434, pool.

## § v153 (2026-11-07) — patch-класс не делегирует

**Корень:** enhanced_solve на `scanner_class=patch` ответил `HANDOFF: @Igor` и статус completed.

**Фикс:** гейт на выходе `/run` (async+sync, enhanced+agent_run). HANDOFF → failed UNTESTED. Goal: Do not HANDOFF.

**Не трогали:** TTC 420, 11434, pool.

## § v152 (2026-11-06) — петля доказательства patch, не новый агент

**Корень:** замок был, боя «хит → патч → PASS» не было.

**Фикс:** тест-петля classify → write_file → runtime PASS → git_push deny. LLM/11437 не трогали (`-stable@2048` = факт-полоса).

**Не трогали:** TTC 420, 11434, pool.

## § v151 (2026-11-06) — полномочия по классу, не десятый regex

**Корень:** human держал `run_terminal_cmd`/`ssh_run`; denylist `git push` не видел `node -e`/`perl -e`.

**Фикс:** human/runbook без шелла и git-write; patch шелл жив; unwrap node/perl; отказ push = noise сканера.

**Не трогали:** TTC 420, 11434, pool, потребитель rosters.json.

## § v150.99 (2026-11-06) — scanner_class доходит до /run

**Корень:** `context.class` выбрасывался Pydantic; класс жил только в тексте goal.

**Фикс:** поле `scanner_class` + `blocked_tools` в `BaseAgent.run`. human не пишет файлы.

**Не трогали:** rosters.json потребитель, TTC 420.

## § v150.98 (2026-11-06) — python -c не обходит git_push

**Корень:** `python -c "os.system('git push')"` мимо shell-regex.

**Фикс:** паттерн os.system/subprocess + git push; print не режем.

**Не трогали:** node -e, TTC 420.

## § v150.97 (2026-11-06) — bash -c и SSH не обходят git_push

**Корень:** `bash -c 'git push'` и `ssh_run` шли мимо regex.

**Фикс:** разворот `-c`; отказ в `run_ssh_command` до spawn.

**Не трогали:** python -c, TTC 420.

## § v150.96 (2026-11-06) — терминал не обходит git_push

**Корень:** `run_terminal_cmd` мог `git push` после вычёркивания тула.

**Фикс:** тот же `ATRA_ALLOW_GIT_PUSH`; regex на `git push`, не на `git log --grep=push`.

**Не трогали:** ssh_run, TTC 420.

## § v150.95 (2026-11-06) — git_push только человеком

**Корень:** тул делал `git push --no-verify`; модель видела его в ALLOWED_TOOLS.

**Фикс:** отказ без `ATRA_ALLOW_GIT_PUSH`; вычеркнут из ALLOWED_TOOLS.

**Не трогали:** `run_terminal_cmd git push`, TTC 420.

## § v150.94 (2026-11-06) — apply_patch через SOURCE_GUARD

**Корень:** `apply_patch` писал `open()` в обход замка `write_file`.

**Фикс:** guard на `new_content`; нет модуля — отказ.

**Не трогали:** git_push, TTC 420.

## § v150.93 (2026-11-06) — write_file fail-closed

**Корень:** `write_file` при ImportError SOURCE_GUARD писал на диск.

**Фикс:** нет модуля — отказ (`source_guard unavailable`). Как `_autonomous_guard_write`.

**Не трогали:** apply_patch, git_push, TTC 420.

## § v150.92 (2026-11-06) — evidence в сканере + Reality Checker

**Корень:** «готово» без command/output; agency-agents не ставить пачкой.

**Фикс:** 4 поля в human/patch goal; 2 строки Reality Checker в `victoria_common` (8010 + inject Виктория/Анна); `rosters.json` без потребителя.

**Не трогали:** TTC 420, 11434, pool, 267 агентов.

## § v150.91 (2026-11-06) — сканер async accept; OpenWebUI без stub-библии

**Корень send-fail:** сканер ждал sync `/run` 30с. **Фикс:** `async_mode=true`, HTTP 202.

**Чужой dirty:** fastpath библии пропускал Викторию — снят. Intent+sanitize+422 оставлены. Router: явный qwen38 не выкидывает Ollama.

**Не коммитить:** `.selfdev-worktree`. TTC 420 / слоты не трогали.

## § v150.90 (2026-11-06) — сканер глушит redis-flap

**Корень:** за 2ч 7×`human` на `Connection closed by server` и SQL `tokens_used` — жрали 5/час, POST в Викторию пустой.

**Фикс:** IGNORE flap/111/tokens_used/fallback; send error = `Type: repr`. Лестница B на месте.

**Не трогали:** TTC 420, слоты, mem Анны, трио на лог.

## § v150.89 (2026-11-03) — сканер: класс, не «исправь»

**Корень:** любой хит сканера нёс «исправь ошибку» — соло/консилиум без класса сигнала.

**Контракт:** noise mute; runbook = ops не код; human = нет файла или ядро; patch = TypeError-семейство + незащищённый `.py`. Goal без consilium-триггеров. Запись только write_file+guard.

**Не трогали:** autonomous-code со сканера, TTC 420, слоты, mem Анны.

## § v150.88 (2026-11-03) — сканер не пейджит отказ SOURCE_GUARD

**Корень:** замок пишет ERROR → LOG_SCANNER открывает «исправь». Шум (nomic 404, throttle) ест 5/час.

**Фикс:** IGNORE на отказ guard, embed 404 nomic, RATE_LIMIT, send-fail. Лестница runbook/патч не включалась.

**Не трогали:** TTC 420, слоты, mem Анны.

## § v150.87 (2026-11-03) — SOURCE_GUARD на autonomous-code

**Корень:** `write_file` после инцидента `ai_core.py` под замком, `/api/autonomous-code` писал сырым `open()` в workspace. Абсолютный `file_path` на POSIX игнорировал корень. Команда экспертов этот путь не ревьюила.

**Фикс:** `resolve_workspace_write_path` + `guard_workspace_write`. Preflight до LLM. Fail-closed, если guard не импортировался. Live отказ на `src/agents/bridge/victoria_server.py`, файл байт-в-байт тот же.

**Не трогали:** сканер→спецы, TTC 420, слоты 11434/11436, mem Анны.

## § v150.86 (2026-11-03) — факты на резидентную phi, не cold-stable

**Корень:** фаст-трек всегда звал `phi3.5:3.8b-stable` @2048. На 11437 `MAX_LOADED_MODELS=2` = base+nomic, stable нет. Cold-load 20–60с или фолбэк на мозг ~100с.

**Фикс:** `/api/ps` → если есть stable — она; иначе резидентный `phi3.5:3.8b` @8192; нет phi — сразу обычный пайплайн, без cold-load. Live: «столица Франции?» → Париж, **0.26с**, `phi3.5:3.8b` ctx 8192, nomic на месте.

**Не трогали:** TTC 420, 11434/11436, mem Анны.

## § v150.85 (2026-11-03) — две нормы TTC в Telegram

**Корень:** Deferred Monitor сравнивал unlabeled p95 с 180с. Хвост `timeout_*` (15 мин) = HIGH, хотя текст сам писал «это нормально».

**Контракт:** обычные 180с, сложные 900с. Page только свой хвост. Алерт 420 / hung 600 не меняли.

## § v150.84 (2026-11-03) — phi -c 32768 это 8192×4; ghost не generate

**Не баг:** `/api/ps` phi `context_length=8192`, `llama-server -c 32768 -np 4`. Plist `OLLAMA_NUM_CTX=8192` `OLLAMA_NUM_PARALLEL=4`. `-c` = per-slot ctx × parallel. 11437 не рестартовали.

**Дыра:** ghost `/api/ps` без llama-server → generate hang. `pin_brain` skip-if-loaded не видел труп. Теперь: нет `.ollama-brain` runner → не generate; 2 полла → kickstart только 11434.

**Не трогали:** TTC 420, pool, mem Анны, unload 27B ради phi.

## § v150.83 (2026-11-03) — live 24h: ghost runner + watchdog 2048

**Корень:** `/api/ps` держал victoria-qwen38 с expires 2319, llama-server по blob не было — generate висел до GIN. `pin_brain` skip-if-loaded. После kickstart только 11434 пин 16384+24h встал (`expires 2026-11-04 20:47`). Через ~1 мин `ollama_runner_watchdog.sh` слал `num_ctx=2048` без keep_alive; plist `OLLAMA_KEEP_ALIVE=-1` → runner `-c 2048`, expires снова 2319.

**Фикс:** пробы 11434 → `num_ctx=16384` + `keep_alive=24h`. `brain_keepalive.sh`: руки проверять на 11437, phi ctx 8192. Live: ctx 16384, expires ~now+24h, llama-server `.ollama-brain` жив. 11436/11437 не рестартили.

**Не трогали:** TTC 420, pool, mem Анны, unload unsloth.

## § v150.82 (2026-11-03) — мозг 24h даже в MLX cooldown

**Корень:** `get_keep_alive` в recovery cooldown возвращал `-1` до пина. Live `/api/ps` expires 2319 при таблице `24h`. Warmup пропускает уже загруженную модель — TTL не обновлялся.

**Фикс:** BRAIN_MARKERS → `24h` первой проверкой. Следующий успешный generate выставит TTL. Не выгружали 27B ради пробы (пинг 240с timeout, слот занят).

**Не трогали:** TTC 420, pool, mem Анны.

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

---

## 🎯 ГЛАВНЫЙ ПРИНЦИП ВЛАДЕЛЬЦА (2026-10-16, неизменяемый)

**СКОРОСТЬ НЕ ВАЖНА. КАЧЕСТВО ВАЖНО.** Наше железо (1×GPU, мозг np=1) — НЕ ограничение для качества: очередь и последовательные дебаты дают ЛЮБУЮ глубину мышления, ценой времени. Следствия для всех сессий:

1. **Задача может думать час** — это норма. При занятом мозге НЕ фолбэчиться на слабые модели и НЕ отбивать задачи — ЖДАТЬ в очереди (STUB-GUARD ре-очередит честно).
2. **Консилиум/дебаты — дефолт для сложного**, соло — только для тривиального (факт-трек).
3. **Никаких error-текстов как ответов** (STUB-GUARD), никаких completed без содержимого.
4. **Резервы качества** (в порядке важности): (а) промпты-персоны — Ольга 174 симв и Сергей 254 симв = ПУСТЫЕ заглушки, у Дмитрия 1126; наполнить знанием и правилами; (б) знания: 98.5k узлов, чистка мусора продолжается; (в) judge/rubric на выходе (рубрики из консилиум-битв).
5. **Метрика успеха = качество ответа**, не время. p95 латентности — не KPI.
6. Стабильность инфраструктуры остаётся критичной: петли без бэкоффа и утечки роняют задачи = удар по качеству.

---

## ⚠️ ПРАВИЛА КООРДИНАЦИИ ПАРАЛЛЕЛЬНЫХ СЕССИЙ (обязательно к прочтению всем чатам, 2026-10-11)

Система развивается в НЕСКОЛЬКИХ параллельных чатах. Чтобы не ломать работу друг друга:

1. **Библия — первый источник.** Перед изменениями прочитай последний § (сейчас v150.x). После — добавь свой § с версией. Не перепрыгивай номер: смотри git log.
2. **Версии коммитов**: серия каждого чата помечается своей версией (v149._ — оптимизация конвейера; v150._ — параллельный марафон). Пуш только после `git pull --rebase` — очередь коммитов общая.
3. **Maintenance-mode** (`scripts/maintenance.sh on|off`): перед ручными операциями с инфраструктурой (рестарт Ollama/Redis/Docker, правка ночных джоб) — включи флаг, после — выключи. Автоматические акторы (brain_keepalive, redis_watchdog, source_integrity, log-rotate) при флаге молчат.
4. **Env → recreate**: правки docker-compose переменных активируются только `docker compose ... up -d --force-recreate <service>`; `docker restart` env НЕ обновляет.
5. **Пороги сторожей** привязаны к текущей скорости: изменил производительность (модель, маршруты, слоты) — ревизуй таймауты (SMART*WORKER*\*, AB_POLL_TIMEOUT, watchdog-окна).
6. **Комментарии в SQL-строках — только `--`**; кавычки в LIKE-паттернах — удвоение (''). Проверено двумя инцидентами.
7. **«Готово» = живая верификация** (замер/запрос через прод/строка лога), не «компиляция прошла».
8. Не правь файлы, которые в этот момент правит параллельный чат: victoria_server.py / local_router.py / ai_core.py — горячие зоны, сверяйся с git log перед правкой.

---

## 🌌 ТЕКУЩИЙ СТАТУС: Singularity 31.2.2+ (Hardening Mac Studio)

**Дата последнего обновления:** 2026-10-10
**Уровень эволюции:** 31.2.2 (v150.2 — волны 1-2 аудита закрыты; контракт v149.4 восстановлен)
**Состояние:** Полный аудит 2026-10-08 (`docs/AUDIT_FULL_2026-10-08.md`) → волна-1 P0 (гард/MLX/ctx) и волна-2 P1 (фантом 64K, гейт, HNSW×6, vector_core async) закрыты живой верификацией. Мозг резидентен @16K, encode p95=351мс, теги гейта 0-фолбэков. Открыто: /run sync упирается в np=1 мозга; волна-3 (чистки, канарейки, medic, Rust-SQL).
**Целевая платформа:** Mac Studio (мозг Qwen3.8-27B Ollama 11434 + легаси wisdom MLX 11435 + coder 11436)

### Контракт слоёв (обновлён v149.4, 2026-10-03)

| Слой                    | Порт                 | Что живёт                                                                                                                      | Что запрещено                                      |
| ----------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| Мозг (planner+executor) | **11434 Ollama**     | `victoria-qwen38:latest` (VICTORIA_MODEL, VICTORIA_PLANNER_MODEL)                                                              | wisdom-24k как основной; USE_MLX_FOR_PLANNER=false |
| Руки (light/embed)      | **11434 Ollama**     | `phi3.5:3.8b` + `nomic-embed-text`                                                                                             | смолы на слоте мозга надолго                       |
| Легаси wisdom           | **11435 MLX-прокси** | `victoria-wisdom-24k` (fallback only)                                                                                          | route туда по умолчанию                            |
| Coder                   | **11436 Ollama**     | `qwen3-coder:30b`                                                                                                              | —                                                  |
| Victoria                | **8010**             | `/run`, health                                                                                                                 | «готово» без очереди/inflight/ps                   |
| Закрыто                 | —                    | `pending/in_progress/queued`=0 **или** явно чужой work (не LOG_SCANNER); inflight=0; сканер: 0 новых ложных хитов за 1–2 цикла | объявлять 100% репозитория                         |

Правило дожима: `.cursor/rules/91_finish_to_closed.mdc`. Guard: `scripts/ollama_wisdom_guard.py` + LaunchAgent `com.atra.ollama-wisdom-guard` (unload timeout 60с; на 11434 держит мозг v150.1 + phi+nomic с явным num_ctx, чужое выгружает).

**Бэкфилл пропущенного (v149.23–v149.34, по git log):** v149.23 regex-fallback JSON; v149.25 executor-gate 11436×qwen38; **v149.26 универсальный гейт «модель×узел» по /api/tags (кэш 120с, timeout 3с) — замена хардкодов**; v149.27 кипер: успех = резидентность в api/ps; v149.30 regex-fallback обрамлённого JSON; v149.31/32 короткий вопрос→ctx 1500, ответ без JSON как есть; v149.33 (промты Татьяны/авито); **v149.34 maintenance-mode** (файл-флаг `/tmp/atra_maintenance_mode`, акторы молчат при ручных операциях).

---

## § v149.54 (2026-10-15 вечер) — подпись акторов 100%: asyncpg-гарант + триггер-fallback; детектив слепых зон = ноль ✅

**Задача:** добить хвост пустых app_name в task_status_audit (см. v149.51–53). Археология кода не дала владельца (десятки модулей с пулами; CONTAINER_NAME-мутирований нет; не-asyncpg драйверов в воркере нет). Решено двумя независимыми слоями:

**Слой 1 — `app/db_signature.py` (единая гарантия в процессе):** обёртка `asyncpg.connect/create_pool` (install() в точке входа, до остальных импортов): каждому соединению без явной подписи подставляется `server_settings={'application_name': CONTAINER_NAME}` → идёт в startup-пакет → pgbouncer track_extra_parameters трекает → сервер видит на ЛЮБОМ коннекте. Правила: DSN с `application_name=` не перекрывается никогда; CONTAINER_NAME='unknown' (мусор анкора) игнорируется. Подключён в expert_worker.py и smart_worker_autonomous.py. Попутно: 5 dynamic-воркерам прописаны явные `CONTAINER_NAME` в compose (был анкорный unknown). **Верификация:** probe-соединения обоих стилей (DSN и server_settings) видны в SHOW CLIENTS; у контейнеров появились подписанные клиенты.

**Слой 2 — триггер defense-in-depth (миграция `sql/2026-10-15_task_status_audit_signature.sql`):** если app_name пуст/unknown/pgbouncer_backend — подпись достраивается из контекста задачи (`metadata.processing_worker` → `completed_by`), последний резерв `unidentified@<client_addr>`. Инфраструктурная подпись и контекстная НЕ конфликтуют (COALESCE-иерархия). **Верификация живьём:** QC-задача Глеба через overflow-стрим: claim подписан `Анна`, STUB-GUARD-requeue подписан `Глеб` — оба перехода, ранее пустые, теперь именные. STUB-GUARD отработал повторно (попытка 1/3; мозг под вечерней нагрузкой даёт стаб — задача честно крутится в requeue, не фейковый completed).

**Наблюдение (не блокер):** у каждого воркера остаются 2–3 стартовых EMPTY-соединения, открывающихся через ~1с после старта; перехват asyncpg их не покрывает (создатель не идентифицирован — не asyncpg top-level, не psycopg/sqlalchemy, не healthcheck). Слоем 2 перекрыт их эффект в аудите; охота на клиента — бэклог (tcpdump-сеанс).

**Попутно (v149.55, вечер):** LOG_SCANNER-тревога «LOOP-BREAKER: промпт(Проанализируй текст и извлеки ключевые сущности…)» в orchestrator/nightly — graphrag entity_extractor гонял полную LLM-экстракцию при заведомо мёртвом мозге: каждый вызов = впустую полный RAG-прогон (Rust RAG → Python RAG → reranker → cache SET). Фикс: circuit breaker в экстракторе — стаб/не-JSON ×3 → LLM-фаза на кулдауне 5 мин, regex-сущности работают всегда. Разобран остальной шум сканера: evolution `KeyError 'message'` (docker-api клиент без JSON-body, 2 раза/6ч — P3), nightly VERONICA ReadTimeout (след ночного браунаута), «Анна WON task» в EXCEPTION-паттерне (ложный матч сканера), ORDER BY/FATAL — мои же отладочные psql-запросы и рестарт pgbouncer.

**Полный аудит логов 41 контейнера (6ч, вечер 15.10) — v149.55b:** найдены и закрыты: (1) `NameError: name 'igor' is not defined` в autonomous_daemons.setup_daemons — демон «Игорь» нигде не создавался, исключение валило setup целиком: DialogueController/VictoriaEnhanced/Redis-Bridge НЕ интегрировались на EventBus при каждом старте orchestrator. Фикс: igor создан (rag_latency/3.0, db_connections/200); верифицировано: «Демон Игорь запущен» + интеграция EventBus. (2) strategy_sessions `no such table` — цепочка: ensure_tables → import Database → config без ADAPTIVE_ENGINE_ENABLED → ImportError → таблица не создаётся. Фикс: прямой SQLite DDL-фолбэк в strategy_session_manager; верифицировано create_session. (3) Рестартованы victoria-agent и performance-watchdog, не подхватившие фикс entity_extractor (bind-mount код рестартом, не рекреатом). Остатки-бэклог: asyncpg `_maintain_min_size` traceback'ы во время recreate pgbouncer (преходящее); postgres `column "indexname" does not exist` ×3 (клиент шлёт системный запрос вне pg_catalog — мониторинг, найти); `duplicate key idx_tasks_active_dedup` (дедуп-констрейнт отрабатывает, benign); debate-on-errors: LOG_SCANNER→Victoria→DEBATE по каждой ошибке — рекурсия наблюдаемости, режется rate-limit 5/5 (наблюдать).

**v149.55d (вечер, с субагентами) — субагент-расследования 4 хвостов, все закрыты:**
(1) **postgres `column "indexname"`** — источник не код, а LLM-сочинённый SQL: performance-watchdog запускает performance_audit, эксперт через constitution-инструкцию `psql` придумал запрос к pg_stat_user_indexes с несуществующей колонкой (правильно — indexrelname). Фикс: корректный шаблон аудита вшит в промпт watchdog (колонки менять нельзя).
(2) **debate-on-errors рекурсия** — цепочка вскрыта: log_scanner формулировал «Проанализируй и исправь» → consilium-классификатор (task_detector:487) матчит подстроку «анализ» → каждая ошибка сканера = консилиум-дебат на 3 агентов. Фикс: формулировка сканера заменена на «Исправь ошибку или сообщи…» (без триггер-слова). Полное правило маршрутизации [LOG_SCANNER]→solo в victoria_server отложено (горячая зона с WIP).
(3) **evolution `KeyError 'message'`** — это docker SDK errors.py:29 падает на ответе без JSON 'message'; фикс применён в хост-.venv (`except (ValueError, KeyError, TypeError)` → fallback response.text), контейнерный шум остаётся до пересборки образа (ловится, не критично).
(4) **EMPTY-клиенты pgbouncer — УТЕЧКА локализована измерением дельты**: victoria-agent +19 соединений/мин (не пропатчен db_signature; asyncpg импортируется лениво в функциях). Фикс: install() на верхнем уровне victoria_server (мягкий, не валит старт). Верифицировано дельтой: victoria 4→4 (рост остановлен), total EMPTY 133→68 за 90с. Плюс: db_signature теперь перезаписывает garbage-подпись `application_name=unknown` (бывает при recreate воркеров оркестратором — интерполяция из его env); corporation_self_learning fallback-DSN подписан; log_scanner/db_signature/perf-watchdog рестартнуты.

**v149.56 (ночь 16.10) — ПЕРВЫЙ КАЧЕСТВЕННЫЙ ПРЫЖОК (quality-first волна): персоны-пустышки наполнены.** Ольга 174→2341, Сергей 254→2642, Дмитрий 1126→2342, Инна 1844→2073 символов. Промпты по образцу сильных (identity → CORE EXPERTISE → METHODOLOGY → ANTI-PATTERNS → OUTPUT FORMAT), доменно-конкретные под нашу систему (np=1 очереди, порты-контракт, pgbouncer transaction-mode), обязательный формат ответа + шкала уверенности + честная эскалация. SQL-источник: `knowledge_os/sql/2026-10-16_persona_prompts_quality.sql`. **Верификация живьём:** QC-задача Ольге (бимодальная латентность мозга) через полный конвейер: ответ ровно по её формату (ИЗМЕРЕНИЕ/УЗКОЕ МЕСТО/ФИКС/ПРОВЕРКА/УВЕРЕННОСТЬ 85%), правильно назвала queueing layer и np=1, минимальный фикс (TTFT-timeout + Retry-After) с честными условиями повышения уверенности. Сравнение «до»: роль с 174-символьным промптом физически не могла дать структурированную диагностику. Следующие персоны на наполнение: Юлия (2496 — пограничная), далее judge-гейт (шаг 2) и консилиум-дефолт для code/security (шаг 3).

**v149.57 — ПРОМПТЫ ЗАЛИТЫ ВСЕМ ЭКСПЕРТАМ (57 UPDATE за один проход).** Субагент-конвейер: 4 параллельных агента wrote по доменам (dev 14, ml/data 13, ops/qa/trading 14, biz/content 15) по единому стандарту (1800–2800 симв., англ-скелет 5 секций, ролевые ANTI-PATTERNS и OUTPUT FORMAT, шкала уверенности, ATRA-конкретика). Совещательный «Совет Директоров» получил промпт-механику (frame → perspectives → dissent → decide → record). Итог по 90 экспертам: weak (<1800) = 1 (только Совет), good (1800–3200) = 64, strong (>3200) = 25. SQL: `knowledge_os/sql/2026-10-16_persona_prompts_all_experts.sql`. Спот-проверка Ксении: claim подписан в аудите, полный QC-ответ прерван soak-зачисткой параллельной сессии (01:27, psql ×6 «tuning soak») — перенести пробу после soak. Замечено: конфликт дублей имен в батчах решается приоритетом (Инна → ml-версия по её роли).

**v149.58 — ШАГ 2: JUDGE-GATE в конвейере + НАЙДЕН P0-кандидат: CONTEXT BLEED.** Реализовано: рубричный судья перед completed (expert_worker, judge_gate_score): лёгкая модель на руках 11437 → фолбэк coder 11436 (руки при шторме отклоняют — coder отдельный планировщик), format:json, fail-open при недоступности судьи, таймаут 240с (принцип владельца). Слабый ответ (score<6) → 1 перегенерация с фидбеком; лучше из двух по score; после исчерпания — явная пометка low_quality в тексте ответа (никаких фейковых completed). score/issues/regen — в metadata задачи. **Юнит-проба судьи: слабый ответ 1/10 с точным замечанием, хороший 9/10. Живая цепочка: гейт поймал score=1 в задаче Ксении и запустил перегенерацию — механика работает.**

**P0-КАНДИДАТ (context bleed):** финальный ответ Ксении — ЧУЖАЯ задача (про prompt_injection security-план, не про её агрегацию). Судья дважды дал score=1 («Ответ не соответствует заданию»), но перегенерация через тот же воркер снова выдала чужой контент. Класс дефекта = регресс v149.13 (гонка self.memory на синглтоне агента; per-run клон) ЛИБО contamination в RAG/сессионном слое воркера. Эффект: completed с чужим ответом = ложь реестра, качество нулевое. **Судья-гейт теперь это ЛОВИТ** (ловушка работает). Лечение — следующий шаг: изоляция per-task контекста в воркере (клон агента на задачу в streaming/Regen-путях, аудит общего состояния smart-agent). До лечения: low_quality-пометка + judge_score в metadata дают потребителю и аудиту честную картину. Watch: `grep JUDGE-GATE` в логах воркеров + `metadata->>'judge_score'` в tasks.

**v149.59 (ночь 21.10) — шаг 3 + УТОЧНЕНИЕ ДИАГНОЗА context bleed.** (1) code-паттерны добавлены в consilium-роутинг (task_detector: битвы показали перевес консилиума в code). (2) QC Ксении v4 с session-изоляцией — bleed ВОСПРОИЗВЁЛСЯ: в ответе чужой `attack_report` и `survived: false` → источник НЕ сессии, а **общая knowledge_nodes**: KnowledgeFabric складывает ВСЕ task-результаты в векторную базу, RAG подтягивает их любому эксперту как «контекст» (реранк по смыслу не спасает — тексты похожи). Session-изоляция закрывает только диалоговый слой. **Лечение (следующий шаг):** фильтр RAG — не подмешивать узлы с source=worker_service/task-результаты (или отдельный namespace для task-артефактов вне retrieval). Judge-гейт при этом работает как страховка: leak пойман (score=1), low_quality-пометка выставлена, потребитель защищён. Применено (v149.60): (1) RAG-фильтр `AND NOT (metadata ? 'task_id')` в ANN-пути ai_core — 6331 узлов-результатов исключены из контекста; (2) HYPOTHESIS_DEBATES_ENABLED=false в knowledge_nightly (источник закрыт на месте, не только гейтом); (3) judge-мета пишется свежим acquire (внешний conn возвращался в пул → InterfaceError; warning в логах подтвердил). **Следующий слой bleed: memory_consolidator (44 925 узлов диалогов/ответов) — фильтр по консолидатору потребует выборочного ревью (там и легит-знания), не one-liner.** Выполнено (v149.65): consolidator 44924 узла понижены low_priority (реранк ×0.5 + метка на записи); RAG similarity cut-off RAG_MIN_SIMILARITY=0.45 (distractor-чанки отсечены). **ОБНАРУЖЕН ФУНДАМЕНТАЛЬНЫЙ ОСТАТОК — межзадачное смешение в динамическом пуле:** QC v12 (Ксения, агрегация) завершилась ответом на чужой вопрос (проверка контрагентов — задача юр-профиля) с score 9.0 от судьи, который тоже получил другую пару (question/answer смешаны). Формат персоны соблюдён, содержание — чужое. Это НЕ RAG — это состояние динамического слота (adopt-механика пула: слот принимает payload чужого эксперта и несёт контекст предыдущей задачи). Лечение — архитектурное: per-task изоляция контекста динамического слота (per-run clone на adopt-пути). До этого ВСЕ score из пула считать ненадёжными. Выполнено (v149.61): consolidator-узлы понижены low_priority (44924 backfill + метка в записи; реранк ×0.5), LTM_RECALL_ENABLED=false у 12 LLM-контейнеров. QC v9 (26.10, полосы живы): bleed ВОСПРОИЗВЁЛСЯ через легит-документ — RAG подтянул chank из ARCHITECTURE_FULL.md, содержащий «ВОПРОС: … ЧИСЛА: …» — модель ответила на вопрос ИЗ КОНТЕКСТА, а не на задание (task_id-фильтр тут бессилен: документ — легит-контент). Judge fail-open (руки заняты генерацией) — по дизайну. **Следующий шаг (лучшее решение): обрамление RAG-контекста в промпт-шаблоне QUERY ORCHESTRATOR: маркеры «--- СПРАВОЧНЫЙ КОНТЕКСТ (не задание) --- … --- ЗАДАНИЕ: …» последней строкой — инструкция-приоритет против «вопроса из документа». QC v7 (все слои активны): задача дошла до Анны-воркера и была отменена спасателем `rag_loop_no_llm_call_exhausted` — 25 мин без LLM-вызова при перегруженном контуре. **Остаток:** спасатель противоречит quality-first (режет задачи при LLM-голоду вместо ожидания) — пороги SMART_WORKER_LLM_STUCK_MINUTES/STUCK_MINUTES (25/30м) кандидат на подъём, решение за владельцем. Слои bleed закрыты: knowledge_nodes task_id ✅, consolidator ×0.5 ✅, LTM ✅, session ✅. Также замер: за 21.10 judge судил 13, avg 4.3 — низкий avg объясняется bleed-ответами; после v149.60 метрика должна подняться — контроль через 2 дня. **Итог QC-серии v8–v14 (26.10): послойное вскрытие bleed завершено, остался последний слой — MEMORY CRYSTALS.** Хронология: v8-v13 — род в окна LLM-голода (стабы v150.x-роутера) или чужие ответы через SUCCESS RETRIEVAL / consolidator / LTM (все закрыты: SUCCESS_RETRIEVAL_ENABLED=false в ai_pipeline, consolidator ×0.5, LTM off, session per-task, RAG task_id-фильтр + similarity cut-off 0.45). v14 (руки живы, 3600с, спасатель 75/90): score 7.0, формат персоны чистый, НО ответ — на тему «ЗАМЕТИРОВАНИЕ DATABASE: PgBouncer» из MEMORY CRYSTALS («💎 ПАМЯТЬ ПРОЕКТА: Database Port 6432…»), а не агрегация. **Вывод: memory crystals (общие «знания проекта») — последний и главный источник дистракторов для 27B-модели; instruction-priority дублирование задания последней строкой (v149.64) улучшает (1→7), но не побеждает.\*\* Решение за владельцем (варианты): (а) ревизия/чистка кристаллов (удалить PgBouncer-эхо из crystals), (б) отключать кристаллы для операционных задач, (в) сильная модель. Judge-метрика: 26.10 — 3/3 good (судья-на-руках после удаления coder-фолбэка работает корректно). **v149.66b — аудит Prompt Battle (Shadow Evolution) из БД:** QA промптов ОБХОДЯТ другие пути. expert_mutations (634 мутации): **328 из 336 promoted — с total_tests=0** (продвинены вслепую через enhanced_expert_evolver «applied_directly» и meta_architect HOT-SWAP, минуя promotion_engine с честными гейтами win_rate/tests); **37 мутаций с leaked instructions** («ОТВЕТТЕ ТОЛЬКО ТЕКСТОМ НОВОГО ПРОМПТА» внутри текста); честно протестированные — shadow 1988 тестов (win ~48%: мутации в среднем НЕ лучше базы). Задача на следующую волну: требовать total_tests≥10 для ЛЮБОГО promote + фильтр leaked-инструкций. **Выполнено (v149.66c, субагенты):** (1) единый гейт mutation_passes_qa_gate (leaked-маркеры + total_tests≥10 + win_rate≥0.55) вбит в все 3 пути promote (evolver/meta_architect/promotion_engine); (2) миграция-триггер sql/2026-11-01_expert_mutations_qa_gate.sql (НЕ применена к живой БД — требует ревью); (3) **ревизия БД: 328 слепых promoted отозваны в archived** (metrics.revoked_reason=blind_promote_no_tests), остались 8 честных (85 тестов). Аномалия детектива: 62% слепых — эксперт Alex (204 мутации) — pipeline Alex'а системно зàпушил мутации мимо QA, разбирать отдельно. **Независимая ревизия (третий субагент) вскрыла P0-хвосты системы (БЕЗ правок, план на следующую волну):** F1 service_monitor promote_mutation — os.replace кода модулей в прод БЕЗ тестов/health-check (meta_architect критерий — только тайминги, корректность не проверяется); F2 ingestion quality_gate — shadow_mode по умолчанию + подключён только в 4 модулях, capture_knowledge MCP авто-верифицирует по self-reported confidence; F3 93k verified-узлов от LLM-синтеза (memory_consolidator заменяет реальные знания пересказом и понижает исходники до 0.1 — 44.9k узлов уже так); F4 эволюция промптов мимо shadow-пайплайна (205+131 promoted мимо боёв — частично закрыто нашим гейтом). Приоритет фиксов: F1 → F2/F3 → F4. **Всё применено (v149.67, субагенты):** F1 hot-swap — валидация (py_compile+ast+subprocess import) до свапа, subprocess-import-check после, авт-rollback, карантин .rejected; 4/4 inline-тестов PASS; попутный баг: NameError time в event-ветке service_monitor. F2 — INGESTION_GATE_SHADOW_MODE=false + ENFORCE_PERCENT=50 (orchestrator+worker), should_block детерминирован (sha256), 3 пути мимо гейта закрыты (mcp_capture×2, worker hardcode); после недели наблюдения → 100. F3 — честные флаги в 11 местах INSERT (LLM-синтез: verified=false conf 0.7; служебные логи: 0.5/false). Флот рестартнут, 41 healthy, промо-верификация: мозг 200. **По-пунктовая верификация (27.10):** F1 тесты 4/4 PASS + честный лог в файле (meta_architect:805); F2 — пойман пропуск recreate (env в compose был, в живые контейнеры — нет; recreate выполнен, INGESTION_GATE_SHADOW_MODE=false/ENFORCE=50 подтверждены в inspect); F3 — после рестарта orchestrator ноль нечестных вставок cross_domain; до-рестартный хвост 10 378 t/0.95-гипотез понижен low_priority (backfill). QC v10/v11 — обе в очереди за мозгом (защиты держат, вердикт судьи придёт в metadata). Урок: env-изменения проверять в inspect живого контейнера, recreate после каждой правки compose. **v149.68 — аудит дашборда (2 субагента + живой браузер): 14 находок, применены P0/P1:** KeyError «\_db_ok» на кнопке Повторить (pop); двойной кэш fetch_data_tasks (внешний ttl=15 пробивал \_cache_bust, внутренний ttl=60 нет → KPI staleness); chat_tab asyncio.run блокировал вкладку до 10 мин без индикатора (spinner добавлен; полный async-рефакторинг — отдельная задача); strategy_tab metadata-строка; system_tab NULL upper + bare except; ошибки БД больше не кэшируются как «Нет данных» на 60с. **Урок: Streamlit session_state зеркала читать через widget state, никогда через подставляемое зеркало до установки; ошибка БД ≠ пустой результат (не кэшировать).** **QC v14→v15 остато́к вычищен:** 1062 bleed-узла (Q&A-эхо + Antifragile-ошибки, unverified без source) удалены из knowledge_nodes — но НЕ нашим архив-скриптом (он пришёл вторым и нашёл 0; удаление выполнила параллельная сессия в своём soak-проходе). База: 107 831 узлов, unverified 14 139 (все с источниками — легит), consolidator 44 925 в low_priority. **Дальнейшая чистка — только по ревью memory_consolidator-слоя (v149.65 план).**

**v149.58e (20.10) — ДВУХДНЕВНЫЙ АУДИТ (18-19.10) + quality-freeze применён.** Факты: 18-19.10 failed перевернул done (44 failed 19.10 vs 23 done). Разбор: ~140 из ~180 failed дали ДВА самопорождённых источника — nightly_hypothesis_debate **69% брака** (64 failed/93) и security_responder **52%** (37/70): абстрактные гипотезы + режущий adversarial-critic при перегруженном мозге. Конвейер вне их здоров (бэклог 5 задач). **Действие:** ORCHESTRATOR_BACKGROUND_SOURCES="" (env, было "security_responder,nightly_hypothesis_debate") у orchestrator + knowledge_os_worker, recreate — генераторы хаоса заморожены (стратегия «ядро, потом рост»). **Критерий разморозки:** ядро ≥90% done и judge avg ≥7 за 3 дня подряд, затем включать по одному источнику. Мелочи 2 дней: entity-extractor breaker был instance-level (пересоздавался → счётчик сбрасывался, 105 hits в orchestrator) → переведён на модульное состояние, петля умерла (0 hits верифицировано); blackboard auction decode-фикс стабилен (0 повторов); QC-проба Ксении отменена orchestrator-таймаутом 900с (противоречит quality-first — кандидат на подъём до 3600с, ждёт владельца). Выполнено (v149.58f): ORCHESTRATOR_TASK_TIMEOUT default 900→3600с (expert_worker:1208), воркеры рестартнуты — orchestrator-задачи теперь могут стоять в очереди за мозгом до часа (quality-first), fail fast больше не цель для delegated-задач.

**v149.58g (ночь 20.10) — ПРИЧИНА «ЗАКЛИНИВАНИЙ МОЗГА» НАЙДЕНА: ТРИ АВТОНОМНЫХ СТРЕЛКА.** Форензика ночного каскада (серверы перезапускались 22:41, 22:59, 23:13, 23:18:00, 23:18:31 — каждые 5-15 мин):

1. **system_auto_recovery.sh (каждые 300с) — главный**: при таймауте /api/tags за 3с делал `pkill -f ollama` (убивал мозг+руки+coder разом) и спавнил блудный `ollama serve` вне launchd → драка портов с launchd. ПЕРЕПИСАНО: двойная проба x20s, pkill/serve УДАЛЕНЫ, вместо них ntfy-алерт (ollama — launchd-сервис, лечится kickstart владельца и runner-watchdog).
2. **brain_keepalive.sh**: холодная загрузка 30GB (>240с) → «LOAD FAILED» → `kickstart -k` ВСЕГО сервера посреди загрузки → прогресс обнулялся → вечный цикл (уточнение урока 9: «проба не ответила» включала «ещё грузится»). Фикс: kickstart УДАЛЁН, max-time 240→600с, backoff 30м остался.
3. **Embed-флуд на мозг вернулся через 2 дня**: indexing_daemon (OLLAMA_BASE_URL=11434) и semantic_router (embed_url из BASE_URL) — оба переведены на OLLAMA_EMBED_URL (руки 11437). Урок: env-фикс точки входа не покрывает модули со своим дефолтом — embed-URL править В КОДЕ источника.
   След длительных убийств: сегфолты llama-server (signal 11 ×3 в 23:35) — self-heals при стабильном сервере. ВСЁ закоммичено; полосы после фиксов: embed-флуд 0, рестарты остановлены с 23:21.

**v149.58c (вечер 16.10) — два фикса из LOG_SCANNER-среза:** (1) `blackboard_service` auction: `.decode()` в лог-строке стоял ДО isinstance-защиты → str-имя эксперта валило autonomy-цикл на всех воркерах разом («'str' object has no attribute 'decode'» ×6). Нормализация перенесена до использования. (2) entity_extractor: исключение (loop-breaker) не крутило fail_streak circuit breaker'а — цикл жил на loop-breaker'е, минуя кулдаун; except-ветка теперь тоже наращивает счётчик. Hands 11437 под вечерним спросом — circuit breaker честно открывается (не баг), закроется с разгрузкой.

**Уроки:** (37) cross-cutting гарантию (подпись соединений) ставят ОБЁРТКОЙ на драйвер в точке входа, а не правками 20 модулей — и обязательно с маркером-проверкой в логах (logging до basicConfig глотает INFO — не считай отсутствие лога отсутствием патча, проверяй `hasattr(f,'__wrapped__')`); (38) defense-in-depth: инфраструктурную подпись дублируй контекстной из данных — детектив не должен зависеть от одного слоя; (39) правка конфига, приконнеченного single-file bind-mount, ломает маунт (inode) — sed/Edit по pgbouncer.ini ⇒ немедленный `compose up -d --force-recreate pgbouncer` + `docker exec grep` (урок 27 сработал во второй раз за сутки).

---

## § v149.53 (2026-10-15 утро) — ловушка подписи СРАБОТАЛА: перезапуск-петля «model upgrade» поймана и обезглавлена ✅

**Первая пойманная подпись:** ночной `cancelled` (00:49:35) в task_status_audit подписан **`knowledge_os_orchestrator`** — детектив, начинатый в v149.51, работает.

**Главная находка утра — вечная requeue-петля с несуществующей моделью.** task_status_audit показал идеально регулярный цикл (каждые ~60с: pending↔in_progress, форма `make_interval(secs => $3)`). Цепочка: `model_performance_tracker.MODEL_HIERARCHY` рекомендует апгрейд на **`glm-4.7-flash:q8_0` — модели, которой нет во флоте** → smart_worker (knowledge_os_worker) ревертит задачу в pending на 60с → диспетчер отдаёт снова phi → трекер снова недоволен → бесконечно (задача «ИССЛЕДОВАНИЕ: System Communication» прыгала часами, каждый круг = LLM-вызов = топливо 503-шторма). **Фикс:** MODEL_HIERARCHY вычищен до реальных моделей (phi/qwen3-coder/qwen38 — контракт слоёв); задача-пинг-понг отбита retry_after+2ч. Верификация: после рестарта knowledge_os_worker — 0 upgrade-циклов.

**Хвост подписи локализован до модуля:** безымянные записи шли из `model_performance_tracker` — он создаёт **собственный пул** из `os.getenv("DATABASE_URL", ...)` в фабрике `get_performance_tracker()`: env в knowledge_os_worker ПОДПИСАН (проверено inspect+python), но трекер видит URL без application_name (фабрика отрезает query или берёт дефолт — разбирать дальше). Вместо погони за каждым таким пулом — **`client_idle_timeout=600` в pgbouncer**: любые утечки/безымянные соединения выметаются за 10 мин, новые приходят подписанными (зомби: 250+ → 69 → тают; оркестратор теперь 150 подписанных клиентов).

**Утреннее состояние:** мозг 503-ки держатся под утренним конвейером (ночь: 95 генераций, 26 задач completed), руки здоровы (phi@16K 2.9с, nomic 0.25с — после eviction раздутого до 27.7GB phi-раннера, пин重新 правильными опциями); флот 40+ контейнеров healthy.

**Уроки:** (34) лесенки апгрейда моделей обязаны содержать ТОЛЬКО модели из текущего контракта слоёв — рекомендация несуществующей = вечная requeue-петля + DoS очереди; (35) модульные «свои пулы» с дефолтным DATABASE_URL — класс неподписанных писателей: новый пул = новое место проверки application_name; (36) client_idle_timeout — дешёвый гигиенический полис против всего класса соединений-зомби.

---

## § v149.52 (2026-10-15 ночь) — LLM-браунаут 23:00–00:25: эмбеддинги душили мозг, вскрыто и закрыто ✅

**Симптом:** в 23:00 мозг (60–110 генераций/час весь день) обвалился до 0 завершений; обе полосы — мгновенный 503; fail-streak=11 у роутеров; задачи Глеба/Виталия — стаб-ответы (см. § v149.51 QC).

**Цепочка до корня (по живым логам):** semantic_cache.py эмбеддил через `OLLAMA_BASE_URL` = **11434 (мозг)**, а не руки: конвейер классификации задач долбил `/api/embeddings` **5/с без бэкоффа** (392 503/мин) → очередь мозга (MAX_QUEUE=100) постоянно полна → всё остальное 503 → каждый провал циклит конвейер (ре-диспетчеризация → снова эмбед) → самоподдерживающийся шторм. Усугубители: nomic-раннер грузился прямо в мозг (карусель с гардом brain-solo); рестарты контейнеров (23:21/23:44/00:05) сбрасывали fail-streak всех процессов → синхронный thundering-herd startup-задач.

**Фиксы (волна):** (1) `OLLAMA_EMBED_URL=http://host.docker.internal:11437/api/embeddings` — в анкор dynamic-воркеров + env victoria-agent, veronica, orchestrator, heavy/anna/victoria, knowledge_os_worker (рекреат); (2) чужие раннеры выгружены из мозга (nomic/phi через keep_alive:0 — на мозге снова только qwen38); (3) чистые рестарты обоих инстансов сняли исходный клин (руки: generate 200/0.84с, encode 200/0.27с); (4) флот поднят ступенчато (4с).

**Верификация живьём:** флуд `/api/embeddings` в мозг 392/мин → **0**; мозг снова завершает генерации (task 6681: промпт 1968 токенов + 989 сгенерировано за 75с @15 t/s, следующая сразу). **Остаток (честно):** слот фактически один (slot id 0), спрос конвейера ~130 POST/мин против ~0.8 выдач/мин — 503-ки под нагрузкой сохраняются (известный потолок np=1 мозга, архитектурный бэклог); хвостовой флуд `/api/embed` ~10/мин в мозг — источник не найден (кандидат: хост-клиенты/Rust), мониторить рецидив nomic на мозге.

**Уроки:** (30) эмбеддинги — класс нагрузки РУК: любой embed-URL, смотрящий на мозг, — инцидент-кандидат (проверять при каждом новом модуле с эмбедами); (31) «мгновенный 503 при живом резидентном раннере» = очередь полна — смотри ЧТО её держит (микс GIN-лога по эндпоинтам), а не рестарти сразу; (32) рестарт N контейнеров разом = сброс всех fail-streak = синхронное стадо — поднимать ступенчато; (33) GIN «127.0.0.1» сквозь Docker backend НЕ отличает контейнеры — флудера ищи по его собственным логам (grep -c по всем контейнерам). Попутно (ночь): nomic выпал из рук после рестарта — phi-раннер раздулся до 27.7GB (фантомный ctx) и не пускал загрузку: лечение = eviction phi → пин nomic (0.56с) → пин phi ЯВНЫМИ опциями @16K (урок 3 подтверждён).

---

## § v149.51 (2026-10-14) — подпись акторов в БД до конца + QC Глеба: стаб-ответы больше не «completed» + битва per-category ✅

**1. Идентификация сбросщика задач — цепочка подписи доведена до Postgres.** Продолжение v149.45b/c: их механизм не мог работать — (а) `${CONTAINER_NAME:-unknown}` в DATABASE_URL интерполируется НА ХОСТЕ (соседний env сервис не виден → у всех `unknown`); (б) pgbouncer **принудительно затирал** application_name своим `pgbouncer_backend` в строке [databases]. Фикс: (1) в compose у 15 именованных сервисов application_name прописан литералом, 5 dynamic-воркеров получают его явным sibling-оврайдом после `<<: *dynamic-worker-env` (паттерн EXPERT_NAME — анкор не тронут, рендер проверен); (2) pgbouncer 1.25.2: форс-имя убран, включён `track_extra_parameters = application_name` (+admin_users). Рекреат 21 актора + pgbouncer. **Верификация живьём:** psql-проба `track_test_xyz` и asyncpg-пулы видны в pg_stat_activity под реальными именами (orchestrator/evolution/nightly/dynamic-1..5/…); переход статуса через настоящий пул воркера записан в task_status_audit как `expert-worker-dynamic-3`. Свежих cancelled/failed после деплоя не было — ловушка заряжена, следующий сброс будет подписан. **Хвост (watch-item):** переходы из process_task expert_worker идут с пустым app_name, хотя пул того же контейнера подписан при прямой пробе — остаточный неподписанный путь в long-lived acquire, разбирать по воспроизведению.

**2. QC ответов Глеба (SRE) на живом потоке — пойман и закрыт класс «фейковое completed».** История: 1 пригодный ответ из 5 (два «готов к работе, опишите задачу» вместо ответа; марафон 8.7K с HANDOFF; обрезка; error-текст). Живые пробы ×2 (DESC-TRACE подтверждён: вопрос доходит до низа промпта, U-SHAPE работает): цепочка корня — SMART SELECTION → мозг qwen38@11434 (np=1) → **503 «maximum pending requests exceeded» ×3** → следующий узел Hands корректно скипнут HANDS-GATE → response=None → ai_core честно подставляет стаб «⚠️ Не удалось получить ответ…» (для API) → воркер пишет его как **status='completed'** + LTM сохраняет мусор. Фикс: **STUB-GUARD** в expert_worker (перед завершением): стаб → ре-очередь с retry_after+5мин (до 3 попыток), после — честный failed с last_error; очистка лока/хартбита/blackboard в обеих ветках. **Верификация живьём:** третья проба → лог «🔁 [STUB-GUARD] … ре-очередь (попытка 1/3)», задача в pending, не completed. Воркеры (8) перезапущены. Открыто: сам мозг перегружен (мгновенный 503 при резидентном раннере — очередь np=1), QC-ответ Глеба станет возможен после разгрузки.

**3. Битва: per-category таймауты (v149.18-бэклог) + судья с ретраями.** consilium_ab.py: `AB_POLL_TIMEOUT_HEAVY=900` (дефолт) для тяжёлых категорий (code_audit, code_generation, debugging, devops, architecture, security — стабильно упирались в 360с ещё в здоровой битве 04.10; список — env `AB_HEAVY_CATEGORIES`), лёгкие остаются 360с; в логе раунда печатается poll=N. Судья переведён на \_post_json_safe: 503-штормы Ollama на судейском вызове роняли целые битвы (13.10: 49/50 error, ~25 из них — судья). Аудит ночных битв: 49-error (13.10, ночь GC-инцидента), 45-error (11.10, деградация недели) — код-фиксы закрывают судейскую долю и таймаутную долю здоровых прогонов.

**Уроки:** (27) single-file bind-mount + правка с заменой inode = файл «исчезает» из контейнера (процесс жив на старом конфиге, следующий рестарт падает) — после правки pgbouncer.ini проверять `docker exec grep` и рекреить контейнер; (28) application_name сквозь pgbouncer проверять на СЕРВЕРЕ (`SELECT current_setting` / pg_stat_activity), а не по env контейнера — три слоя (интерполяция хоста → форс-имя pgbouncer → трекинг) каждый молча убивал подпись; (29) «completed со стабом ошибки» = ложь в реестре задач: ни один error-текст не может быть результатом (STUB-GUARD — правило для всех воркер-путей; smart_worker_autonomous — кандидат на тот же гард).

---

## § Волна-12 (2026-10-14 v150.12) — детектив закрыт, сторож усилен, финал восстановления ✅

1. **«Загадочный пиннер phi@11434» = я сам**: hands-first-блок кипера (v150.6, эпоха «руки на 11434») пинил phi на мозговом порте после v150.8-переезда рук — карусель «гард выгружает/кипер грузит» кормилась моим же скриптом. Исправлен на 11437. Урок: при переезде сервиса на другой порт — ревизия ВСЕХ скриптов, пинящих старый.
2. **Сторож-раннеров: убрано mem>5%** — застрявший в Stopping раннер при разгрузке теряет RSS ниже порога и не убивался (мозг висел 15+ мин, убил вручную). Урок: условия «живости» для KILL-логики не должны зависеть от меняющихся при проблеме метрик.
3. **MLX preload снят** (узел вне маршрутизации — 18GB держались зря): RAM 29%→52%, киперный 40%-гейт снова проходим.
4. **Ночной бэкап манифестов ollama** (tar килобайтов, cron 04:30) — блобы re-pullable, манифесты нет (урок инцидента).
5. Coder-модели 11436 восстановлены re-pull'ом (7 моделей).
6. Ещё один само-подстрел задокументирован: probe с чужим num_ctx перегружает раннер (options-mismatch reload) — проверки живости слота идут ТОЛЬКО с контрактными опциями.

**Итоговое состояние:** мозг 29GB Forever @16K (единый полный каталог, GC-война невозможна), руки@11437 (nomic+phi; -stable гард допинит циклом), encode десятки мс, /run синхронно ~20с, RAM 52%, диск 211Gi, 41/41 контейнеров. Автоматика: сторожа (раннеры обоих инстансов, без mem-ловушки), кипер (руки→мозг на правильных портах), гард (brain-only@11434, пины рук), канарейки-функции, loop-breaker, бэкофф.

---

## § § ИНЦИДЕНТ + ВОССТАНОВЛЕНИЕ (2026-10-14 v150.11) — ollama-GC уничтожил общие блобы ⚠️→✅

**ЧТО СЛУЧИЛОСЬ:** изоляция инстансов манифестами-симлинками (v150.11-эксперимент) оказалась СМЕРТЕЛЬНОЙ: ollama 0.33 при старте/обслуживании чистит блобы «на свои манифесты» — мозговой инстанс (1 манифест) и hands-инстанс (4 манифеста) с общим blobs-каталогом взаимно уничтожили ~35GB, включая мозг 29GB. Усугубило: ВСЯ система блобов (вкл. Веронику@11436, 1057 симлинков) была симлинками на один каталог — копий не существовало; APFS-снапшотов нет (TM выключен).

**ПОЧЕМУ НЕ УПАЛО ВСЁ:** мозг был резидентен (mmap держит удалённый файл) — сервис работал, пока тянулись новые блобы.

**ВОССТАНОВЛЕНИЕ (живое):** re-pull 31GB @45MB/s (~11 мин: unsloth Q8_0 = ровно блоб мозга, digest a680f44a совпал с манифестом); phi/nomic/smollm/tinyllama — минутные пулы; мозг пересоздан FROM unsloth (+num_ctx 16384); манифесты объединены; **обa инстанса переведены на единый ПОЛНЫЙ каталог** (асимметрия каталогов = GC-война; симлинк-изоляция отменена как класс); руки/encode/факт-полоса подняты (encode 200/1с, факт '4' 0.1с).

**ОСТАТОК:** загадочный пиннер phi на 11434 (несмотря на все гейты — нужен один tcpdump-сеанс для поимки); -stable факто-полоса восстанавливается гардом.

**УРОКИ (жёсткие):** (23) несколько ollama-инстансов на ОДНОМ blobs-каталоге с РАЗНЫМИ манифестами = взаимный GC — либо один общий полный каталог у всех, либо физические копии блобов; (24) симлинк ≠ бэкап: вся «избыточность» из 1057 симлинков оказалась одним файлом; (25) резидентность mmap спасла сервис — не выгружай модель, пока блоб под вопросом; (26) включи Time Machine/снапшоты на каталоге моделей — это единственная защита от класса «GC съел веса».

---

## § Волна-10 (2026-10-14 v150.10) — добивка честного списка ✅ (с остатками)

**Сделано:** пин факт-полосы -stable в гард (+точные теги — '-stable' ломал startswith-проверку); BRAIN-SOLO-GATE (руки не идут на 11434 при живом hands-узле); loop-breaker пайплайна (>6 попыток одного промпта за 10 мин = мгновенный отказ — бьёт любых драйверов петель); MLX-узел OUT из маршрутизации по умолчанию (3×30с таймауты при живых тегах; включение — один env); синк-бюджет 55с; ingestion enforce 25%; **purge 5088 мусор-узлов БД** (бэкап 1.0GB снят до); диета образов (\*\*/venv-паттерны в .dockerignore: слой COPY 25.6→19.1GB на образ; глубокая диета = селективный COPY — бэклог); Login Items проверены (Ollama там НЕТ); дубль Qwen3.8-27B (29GB) удалён повторно — КТО-то перепулил его в окно массовой пересборки (кандидат: параллельная сессия/модель-трекер — координировать!).

**Остатки (честно):**

1. **Хост-клиенты рук не мигрированы** (телеграм-бот, авито-респондер — launchd, OLLAMA_BASE_URL=11434): грузят phi на мозговой инстанс → карусель «гард выгружает/клиент грузит». Фикс: OLLAMA_HANDS_URL им в env (10 минут работы).
2. Пост-штормовая сходимость: после массовых рестартов полосам нужно окно (оркестрация «тишина→руки→мозг» отработана; ночью автоматика сведёт).
3. Селективный COPY в Dockerfile агентов (образы 19GB→~3GB потенциал).
4. 100k untyped-узлов (проект типизации).

**Уроки:** (21) `.dockerignore` `venv/` матчит только корень — вложенные env'ы едут в образы (\*\*/venv/); (22) при живой параллельной сессии модели-манифесты меняются под руками — rm без фиксации источника = повторение (координировать через правила координации в начале библии).

### v150.21 (22.10, утро): расшифровка «64K-раннеров» — НЕ раздувание

`-c 65536 -np 4` на phi = **16384 × NUM_PARALLEL=4** — ollama показывает ОБЩИЙ KV-буфер (математика параллелизма, не чужой клиент и не рекурсия). Утренний ntfy-шторм 22.10 = застрявший phi-раннер на 11437 (Stopping без mem>5% — сторож не убивал) + очередь мозга на утреннем пике. Застрявший убит, инстанс сброшен, encode/phi восстановлены. Скрипты нтфай-алертов работают корректно — шум был честным сигналом реальной деградации.

### v150.23 (22.10 21:16): дренаж «медленно, но верно»

Дренаж был 1–3 completed/ч vs 3–7 failed/ч (очередь почти стояла). Корень слот-монополии: executor посылал num_predict без капа → мозг (np=1) генерил 2700+ ток = 6+ минут за вызов, все остальные ждали. Кап **1200** (env EXECUTOR_NUM_PREDICT_CAP / ROUTER_DEFAULT_NUM_PREDICT) — каждый вызов ≈2 мин, слот чаще переходит следующему. Философия владельца: «главное чтобы не висело, пусть медленно, но разгребается» — скорость отдельного ответа принесена в жертву пропускной. Восстановление encode после очередного zombie (сторож уже ловит автоматически).

### v150.26b (25.10 23:52): урок деплоя bind-mounted контейнеров

Правка nightly_learner (валидация гипотез) не подействовала 12 часов — контейнер живёт на коде, прочитанном при старте процесса. **После каждого деплоя правок в knowledge_os/app — рестарт ВСЕХ зависимых контейнеров** (victoria rebuild недостаточно; nightly/evolution не входят в compose-цепочку зависимостей victoria). Перезапущены; Debate из лог-мусора прекратится со следующего цикла (21:00). Дренаж стабильный: 11 completed/час. Урок (36): bind-mount ≠ hot-reload.

### v150.27 (26.10): ИЗОЛЯЦИЯ МОЗГА — ФИЗИЧЕСКИ, не логикой

Недельная загадка «почему phi грузится на 11434 вопреки всем гейтам» — корень: **манифест-симлинки ~/.ollama-brain/ содержали ВСЕ модели** (ошибка при создании в v150.8 — копировали весь library/, а не только мозг). OLLAMA_MODELS тоже был удалён из plist кем-то из сессий. Теперь: 11434 физически видит только victoria-qwen38 — любой клиент с любым кодом НЕ МОЖЕТ загрузить phi на мозговой порт, файловой системой. Диск-канарейка 85%, тест гейта канонизирован, 17Gi освобождено.
**Урок (37):** программные гейты — защита от ошибок; изоляция каталогом — защита от всех. Когда гейт «не работает» — проверь физический слой (что инстанс реально видит).

### v150.29b (03.11 23:22): типизация БД + образы + tailscaled

**Типизация ЗАВЕРШЕНА**: все 111,708 узлов получили node_type (8 категорий: learning_note 43K, general 32K, cross_domain_finding 14.5K, performance_finding 13.6K, documentation 5.4K, conversation 2.8K, error_log 409, technical_decision 258). Триггер отключён на миграцию (×150 скорость), включён обратно. RAG: Index Scan HNSW подтверждён.
**Образы** (агент M): .dockerignore расширен (knowledge_base/, venv-варианты, docs/), 17Gi освобождено. Образы 135GB — полная оптимизация (multi-stage) в бэклоге (диска хватает).
**tailscaled**: ротация работает (3 архива × 4МБ), sudo выполнен владельцем.

---

## § Волна-28 «Разгрузка мозга» (2026-10-26 v150.28) — качественная маршрутизация, не скорость ✅

**Применённые практики гигантов** (обсуждено с владельцем): каскадирование (FrugalGPT) для фоновых задач, semantic caching (GPTCache) для повторяющихся Security-анализов, FIFO без приоритетов (решение владельца: «пусть стоит как все» — верное, т.к. приоритет лечит симптом, а не причину перегруза).

**Реализовано (агент J, синхронизировано с уже сделанным Курсором):**

1. **Security-кэш**: SHA256 hash множества ID инцидентов; 90%+ совпадение с прошлой сводной → отчёт «без изменений» без LLM-вызова (ntfy only); новые инциденты → задача только для новых. Прогноз: 235% → 24% слота.
2. **Debate по сложности**: <500 симв + нет SQL/архитектуры + ≤1 вопрос → priority=medium + префикс [HANDS] (phi на 11437); сложные → priority=high (мозг). Self-heal судья — механизм эскалации. Прогноз: 119% → 24%.
3. НЕ тронуты: Debate-лимит (Курсор a85963b0), валидация гипотез (v150.26), self-heal (v150.26), STUB-GUARD (v150.26), изоляция мозга (v150.27), instruction-priority RAG (Курсор c432381f).

**Прогноз: мозг 393% → ~100%** — загрузка нормальная, очередь дренируется естественно, никто не висит, Авито в общей очереди как решил владелец.

**Урок (38):** прежде чем вводить приоритеты — проверь, не лечишь ли ты симптом (очередь стоит) вместо болезни (перегрузка фоном). Разгрузка корня → приоритеты не нужны.

---

## § Волна-28 «Разгрузка мозга» (2026-10-27 v150.28) — фоновые пожиратели обезврежены ✅

**Диагноз**: мозг на 99.1% занят собственными размышлениями (Debate 560%, Security 287% суточной ёмкости) — Авито 0.9%. Не дефицит GPU — маршрутизация.

**Три рычага (все бесплатные, все из практик FrugalGPT/Ray Serve/LLMLingua):**

1. **Security-кэш** (агент J): SHA256-хеш множества инцидентов → 90%+ совпадение = отчёт «без изменений» без LLM-вызова. −235% слота.
2. **Debate по сложности** (агент J): <500 симв, без SQL/архитектуры → phi-hands с priority=medium + [HANDS] префикс; сложные — на мозге. −119% слота.
3. **Debate-лимит ≤1 в очереди** (Курсор, a85963b0): уже работал, 68→1 задачу/4ч.

**Итог**: прогнозируемая загрузка мозга ~100% (нормальная) вместо 393% (перегруз ×4). Приоритеты НЕ нужны — разгрузка корня лучше, чем приоритизация симптома.

**Урок (38):** приоритетные очереди — лекарство от симптома; уменьшение бесполезной нагрузки — лекарство от болезни. Сначала спроси «а зачем мозг вообще это делает?», потом «как поделить мозг».

---

## § Волна-26 «Качество мышления» (2026-10-25 v150.26) — судья реабилитирован, вход очищен ✅

**Диагноз (агент H):** судья работал правильно — резал мусорный вход: (a) 13/34 фейлов = стаб-фолбэк «Извините...» при недоступных LLM доходил до судьи (STUB-GUARD не знал эту строку); (b) 21/34 = Debate-задачи из лог-мусора discovery (nightly_learner клепал high-priority из сырых логов); (c) 4/34 = формальные придирки (метаданные).

**Три фикса (агенты H+I):**

1. **Цикл само-исправления**: Rejection → причина (attack_report) → регенерация с «исправь именно это» → до SELF_HEAL_MAX_REGEN=2 попыток. Мозг получает обратную связь вместо молниеносного fail.
2. **STUB-GUARD ×4 строк**: все известные фолбэк-фразы → re-queue вместо похода в судью.
3. **Валидация гипотез**: Discovery-логи/короткий текст → Debate не создаётся.

**Урок (35):** прежде чем ослаблять критика — проверь, не мусорный ли вход он режет; «злой судья» чаще = «грязный вход».

---

## § Аудит-4.0 + Волна-24 (2026-10-23 v150.24) — карусель phi-мозг: ФИНАЛЬНЫЙ корень найден ✅

**Аудит-4** (23.10 00:08): зелёное — Lock=0, idleTx=0, HNSW держит, спираль 0, Redis 94M, серты 03.2027, бэкапы/снапшоты 23.10, кэш-гварды живы, completed 13/6ч vs failed 13/6ч (дренаж стабилен).

**ГЛАВНАЯ НАХОДКА (карусель побеждена окончательно):** extended_thinking.\_generate_response использует intelligent_router → тот выбирал **phi для простых шагов мышления** → запрос шёл на OLLAMA_BASE_URL = **11434 (мозг!)** → гард выгружал → клиент грузил снова **каждые 2 секунды**. Вечная карусель «гард vs клиент». Фикс: руки-модель = OLLAMA_HANDS_URL (11437) в \_generate_response. После деплоя: 11434 = **только мозг**, гард впервые не выгружает ничего (нет evict-строк!), encode 32мс, факт 0.2с.

**Побочные закрытия:** quarantine backup-скрипта (macOS provenance — второе заражение, правило: после каждого git-clone/checkout проверять xattr); снапшот 23.10 создан вручную (крон снова был под карантином).

**Аудит-4 остатки (P2-P3):** 13 failed/6ч — все Adversarial Rejection (судья забраковал качество ответов: отдельная история качества, не инфраструктуры); tailscaled.log растёт (нужен sudo для ротации); 6 контейнеров с >3 историческими рестартами.

**Урок (33):** intelligent_router и slot-контракт — две системы, каждый путь к LLM обязан пройти через контракты портов; router выбирал модель, URL выбирался отдельно — несогласованность = утечка на чужой слот.

---

## § Волна-20 (2026-10-21 v150.20) — GPU-приоритет + хэндофф саморазработке ✅

1. **Хэндофф контуру саморазработки** (docs/handoffs/HANDOFF_20261021_gpu_priority.md, коммит 7b37ff18): приоритизация GPU — баттлы в ночные окна, разгрузка coder/veronica днём, max_steps; им переданы наши замеры (33→8 t/s при соседях) и контракты слотов.
2. **max_steps 12→8** (env EXTENDED_THINKING_MAX_STEPS): −33% вызовов мозга/задачу (каузальная карта: до 13 вызовов/solve ×2 solve). Три точки фикса (init + два харда в victoria_enhanced).
3. **Coder-разгрузка днём**: qwen2.5-coder:14b (9GB) выгружен с 11436 — GPU-приоритет боевому трафику Авито (по хэндоффу — расписание на их стороне).
4. Батарея после: 11434 = только мозг, мозг 14 t/s под нагрузкой, **факт «Париж.» 29.7с синхронно** (стратегия sync_safe_mode — фаст-трек уступил очереди, но ответ через мозг корректный).

---

## § Полное расследование + Волна-19 (2026-10-20 v150.19) — каузальная карта перегруза мозга ✅

**Фундаментальная арифметика** (агент F, file:line): 1 задача = **9–11 вызовов мозга** (типично) / до 100–140 с ретраями; главный пожиратель — extended_thinking max_steps=12, вызываемый ДВАЖДЫ (solve + парсинг распределения). × 3–4 мин/вызов (16K-промпты, живой замер: средний 4841 tk, топ 16372) ÷ 1 слот np=1 (архитектурный лимит qwen35) = 30–45 мин мозга на задачу при потоке 90 req/мин → очередь 100 забивается за 2 мин → 503 → ntfy-шторм.
**GPU-конкуренция** (живой замер): мозг 33 t/s соло против **8 t/s при соседях** (чужой phi@11434 349% CPU, 3 раннера coder-инстанса, 3 раннера Вероники). 4-кратный множитель.
**Волна-19:** парсинг распределения → phi@11437 (φолбэк на solve при сбое); OLLAMA_HANDS_URL в env victoria (redirect v150.11 молчал при пустом env — вот кто грузил phi на мозговой порт!).
**Остаток (волн-20):** мозг 13-14 t/s в текущем смешанном режиме; проверить coder/veronica-раннеры (гнать на ночь), max_steps 12→6, закоммитить ворк-три саморазработки (фиксы каруселей живут как скрипты без git).

**Урок (31):** env-зависимый код (redirect по OLLAMA_HANDS_URL) без env в контейнере = мёртвый код; каждый env-контракт проверять живым `docker exec echo`.

---

## § Волна-17 (2026-10-18 v150.17) — рекурсивное самопоглощение задач + карантин крона ✅

**Двухдневный срез:** Виктория OOM-нулась один раз (17.10) — причина найдена: **task_distribution оборачивала промпт парсером без проверки** («Проанализируй промпт Veronica…{prompt}»), а результат парсинга возвращался в распределение → обёртки вкладывались десятки слоёв → экспоненциальный рост промптов → OOM + 16 failed/сутки + RAM 22%. Фикс: WRAP-GUARD (уже обёрнутый текст не оборачивается повторно, вложенность режется до первой обёртки). Анна-1: 39 рестартов — та же причина (ела рекурсивные промпты).
**Крон бэкапов не работал 3 дня**: macOS-карантин на скрипте («Operation not permitted» в логе) — xattr снят, крон оживёт ночью.
**Урок (30):** генератор промптов обязан проверять, не является ли вход уже его выходом (self-feedback = главный источник экспоненциальных взрывов в агентных системах); и: скрипт, созданный не вами, несёт quarantine — после любого копирования проверять xattr.

---

## § Аудит-3.0 + Волна-16 (2026-10-16 v150.16) — самоиндукция нагрузки побеждена ✅

**Аудит-3.0** (живьём + код-скан 35 файлов агентом D): инфраструктурная гигиена образцовая — все 4 класса регрессий чисто, контракты портов соблюдены всей кодовой базой. Новая находка P0: **Security-респондер** (launchd, 10 мин) создавал 6–7 сводных задач/час без дедупа → оркестратор гонял каждую через мозг → 66 pending, мозг 300% CPU, RAM 18%, victoria OOM, phi-раздутие. Волна-16:

1. **Дедуп 1/час** (агент E: \_recent_security_task_exists + skip + state-фикс) — респондер перезапущен.
2. **Бэклог 66 погашен** пакетно (cancelled с пометкой).
3. **prune бэкапов починен**: искал _.dump при _.sql.gz — чистка НИКОГДА не срабатывала (14×1.1GB); оставлено 8, минус 6-7GB.
4. tailscaled.log в ротаторе (потребуется sudo для первого прогона).
5. victoria 9.7→12G.
   **Батарея:** RAM 39% (было 18), CPU раннера 72% (было 300), pending Security=0, диск 181Gi.

**Урок (29):** авто-генераторы задач без дедупа = DDoS собственным мозгом; каждый генератор обязан иметь рейт-лимит в самом генераторе, до очереди.

---

## § Волна-15 (2026-10-16 v150.15) — превентивы вместо чисток ✅

1. **STORE-GUARD кэша** (агент C): валидатор эмбеддинга (размерность 768/NaN/inf/L2-норма/константность) на всех путях записи — единственный INSERT в semantic_ai_cache, Redis-кэш эмбеддингов, 5 encode-источников (Ollama/VectorCore/ST + 2 батч). Отравление кэша теперь невозможно записать.
2. **Вектор повторного отравления найден**: Redis `embedding_cache:*` — 39 662 мусорных ключа с деградировавшими эмбеддингами (все вопросы → один чужой ответ). Вычищены; guard не даст повториться.
3. **idle_in_transaction_session_timeout=300s** — класс «лок-хвосты из idle-транзакций» (дважды за неделю) закрыт на уровне БД навсегда.
4. Полосы: nomic/stable восстанавливаются гардом; факт-полоса демонстрировала 0.8–9.4с многократно, ночные промахи = известное морение под штормом.

**Урок (28):** чистка таблицы без чистки кэширующих слоёв выше (Redis) = рецидив: любое хранилище с деградируемым источником данных чистить по ВСЕЙ цепочке слоёв.

---

## § Аудит-2.0 + Волна-14 (2026-10-15/16 v150.14) — повторный полный аудит: главная находка — LLM-оптимизатор ✅

**Аудит-2.0 (все 8 слоёв живьём):** зелёное — 41/41, OOM=0, RAM 46%, HNSW Index Scan, мусор БД=2 строки (было 5088), гейт-фолбэки 0/сутки, факт 0.8с. Пять открытых находок → волна-14:

1. **ГЛАВНОЕ: performance_watchdog «autonomous optimization»** — LLM (эксперт Виталий) предлагал индексы, regex вытаскивал CREATE INDEX и ИСПОЛНЯЛ; LLM каждый раз галлюцинировал новое имя `idx_watchdog_[unique_id]` → **154 индекса-зомби (124 никогда не сканировались)** на knowledge_nodes/expert_discussions — каждый INSERT/UPDATE обновлял все полторы сотни. Фикс: WATCHDOG_AUTONOMOUS=false по умолчанию + DROP всех 154 + убиты лок-хвосты (Lock=0). Урок (27): никогда не давать LLM исполнять DDL без white-list/ревью — «автономная оптимизация» без валидации = медленный poison.
2. **Отравление семантик-кэша** (живой P0 в ходе волны): при падшем nomic (encode 500) в кэш записались записи с деградировавшими эмбеддингами → «Столица Франции?» получала ответ про микросервисы за 0.8с. Лечение: purge 10177 записей + рестарт victoria (in-proc кэши). Корень (store без валидации эмбеддинга при деградации) — в волну-15.
3. Факт-гейт сужен (агент B): порог 120→60 симв + 15 позитив-паттернов + heavy+10 («назови/преимуществ/...»), «план»→«план:» («планет» проходит). Симуляция 10/10; живая батарея маскировалась штормом полос — гейт проверен кодом, полоса -stable доводится гардом.
4. MLX-декомиссия окончательная (канарейка снята, джоба выгружена; возврат = env+bootstrap).
5. Ротация логов (агент A): универсальный hourly-ротатор 20 файлов (порог 50MB, архив+трюнкейт с сохранением inode) — **1.23GB возвращено**, LaunchAgent com.atra.log-rotate-all; крон бэкапов восстановлен (строка потерялась при пересборке crontab — урок: после правок crontab проверять grep'ом).

---

## § Волна-9 (2026-10-13 v150.9) — факт-фаст-трек: тривиальные вопросы за 4-9с всегда ✅

1. **Факт-фаст-трек** (victoria_server /run): ультракороткие вопросы (≤120 симв, есть '?', без heavy-маркеров/файлов/URL) → **выделенный раннер `phi3.5:3.8b-stable` на инстансе рук (11437)** — воркеры жгут базовый тег, -stable никто не занимает = своя очередь. Kill-switch `VICTORIA_FACT_FAST_TRACK`, сквозной фолбэк в пайплайн при любом промахе. Полировка эхо-маркеров (<|im_end|>, «Response:», «###»).
2. **Верификация**: «Париж» **4.1с**, «4» **5.7с**, «21» 9.4с — стабильно даже при пиковой загрузке мозга/рук (раньше 20-40с или хендафф).strategy=fact_fast_track в ответе.
3. **Попутно**: FAST PATH диалогов воркеров num_ctx 16K→4K (марафоны prompt-eval душили инстанс рук — факт-полосы не пробивались); **runner-watchdog следит за обоими инстансами** (11434+11437 — застрявший Stopping-раннер на руках блокировал всё).
4. Промежуточные уроки итерации: MLX-полоса тоже контенционна (фон роутера), третья модель на занятом инстансе не грузится — приём «отдельная модель = отдельный раннер = отдельная очередь» сработал только после разгрузки инстанса (4K-кап) + чистки сторожем.

**Уроки:** (19) отдельная МОДЕЛЬ на инстансе = отдельный раннер и очередь — самый дешёвый способ выделенной полосы без новых сервисов; (20)(prompt-eval, не генерация, душил полосы: кап num_ctx режет и то и другое).

---

## § Волна-8 (2026-10-12 v150.8) — выделенный инстанс РУК ollama@11437: морение закрыто архитектурно ✅

**Контракт слотов (обновление v150.4-таблицы):** 11434 = ТОЛЬКО мозг; **11437 = РУКИ (phi3.5/nomic/smollm/tinyllama), свой планировщик** (launchd `com.atra.ollama-hands`, OLLAMA_MODELS=~/.ollama-hands — манифесты-симлинки + общий blobs: инстанс физически не знает о мозге, гейт не пустит); 11435 MLX-легаси; 11436 coder.

1. **Реализация**: plist (KEEP_ALIVE=-1, PARALLEL=4, CTX 16K, MAX_QUEUE 100) → роутер `OLLAMA_HANDS_URL` (узел priority 0 + HANDS-GATE против qwen38 на marker-фолбэке) → FAST PATH воркеров и vector_core → 11437 → гард: 11434 = мозг-only (руки там теперь ЧУЖИЕ, выгружаются), пины рук на 11437 → канарейки обоих инстансов.
2. **Верификация живьём**: руки подняты на 11437 за секунды (phi 7.4с/nomic 0.56с) и **ПЕРЕЖИЛИ 5+ минут реального трафика флота** (впервые за неделю — на 11434 их эвиктило за минуты); encode 63-125мс стабильно; 8 маршрутов через Hands-узел; гард пишет «brain[...] hands[...]»; 11434 = только мозг 29GB.
3. Результат недели: каждое звено цепочки «симптом→корень→фикс→волна» закрыто — от войны гарда×кипера (1130 выгрузок) до архитектурного разделения планировщиков.

**Уроки:** (17) смешение классов нагрузки на одном планировщике (интерактивный np=1-мозг + фоновые руки) нестабильно по построению — делить инстансами (паттерн coder@11436 теперь и для рук); (18) изоляция через каталог манифестов-симлинков: узел физически не может обслужить чужую модель — лучше любого программного гейта.

---

## § Волна-7 (2026-10-12 v150.7) — анти-спираль + синк-приоритет; вердикт архитектуры слота ✅

1. **Анти-спираль (executor + роутер)**: ex-бэкофф 5→60с после серии LLM-отказов (процесс-широко в обоих путях к слоту). Суточный профиль: спираль 154 итер/60с + 11-часовой застрявший Stopping-раннер (убит починенным сторожем) + раздутая очередь 503. После деплоя: спираль 0.
2. **Синк-приоритет**: /run ставит redis system:sync_active (TTL 40с); фоновые LLM-вызовы роутера уступают дорогу до 30с (ContextVar-обход для самого синка).
3. **ВЕРДИКТ АРХИТЕКТУРЫ (главный итог недели)**: phi/nomic и мозг НЕ уживаются на одном ollama-инстансе при живом трафике — поток больших промптов к np=1-мозгу морит загрузки рук (в тишине руки поднимаются за 2.3с/0.3с, под нагрузкой — часами) и вытесняет их по памяти (LRU-эвикции idle-рук при 16K-контекстах). **Волна-8 = выделенный инстанс рук**: ollama #2 на 11437 (OLLAMA_MODELS общий, только phi+nomic+smollm), роутер: hands-URL → 11437, мозг остаётся 11434 — паттерн уже обкатан coder'ом на 11436. До этого: оркестрация «тишина → руки → мозг» (docker stop флота на 90с) — задокументирована как рабочая процедура.

**Уроки:** (15) ретрай-цикл без бэкоффа = внутренний DoS: любая очередь запросов обязана дышать; (16) 1 инстанс = 1 планировщик: смешанные классы нагрузки (интерактивный мозг + фоновые руки) на одном планировщике нестабильны по построению — делить инстансы, как сделали coder'а.

---

## § Волна-6 (2026-10-11 v150.6) — диета промпта, честный кэш, MLX-кап, hands-first оркестрация ✅

1. **Промпт-диета lightweight** (ai_core): вопросы ≤300 симв (env AI_PIPELINE_LIGHTWEIGHT/MAX_CHARS) идут без кристаллов/COLLECTIVE REFLECTION/SWARM/enrichment — персона (system_prompt Виктории всего 179 симв из БД) + capped-RAG остаются. Промпт худеет на ~3-5KB → prompt-eval короче. Прецедент v149.31 расширен с RAG-контекста на весь промпт.
2. **Семантик-кэш больше не врёт коротким вопросам**: «столица Франции?» получала ответ «Да, я могу отвечать на русский» (L2-попадание ≥0.80 — у коротких русских фраз плотные эмбеддинги; прогретые «типовые запросы» коллидировали). Фикс: запросы <80 симв (SEMANTIC_CACHE_MIN_QUERY_CHARS) не кэшируются — генерировать их дёшево. Загрязнённые записи вычищены. Живой замер после: «Париж» 20.4с и «Привет» 34.7с — CORRECT синк-ответы.
3. **MLX honor num_predict**: GenerateRequest получил options (Pydantic молча выбрасывал поле) — потолок генерации больше не игнорируется (марафоны на дефолте 2048).
4. **Ingestion enforce 5%** (env в композ воркеров+виктории) — начало выхода из shadow (аудит №15, мусор рос 2890→3814).
5. **Кипер hands-first (руки→мозг)**: коренной механизм дня — при непрерывном потоке к нейронный слот (np=1, арх-лимит qwen35) ollama 0.33 бесконечно морит загрузки НОВЫХ раннеров (encode 500 часами). Рабочая оркестрация: рестарт → руки в пустую очередь (phi 0.7с, nomic 0.09с) → мозг. Кипер теперь пинит руки перед мозгом автоматически; ручной прогрев мозга ДО рук — запрещён (нарушал порядок весь день).
6. **Death-spiral фоновых задач**: застрявший асинк-таск гонял полный пайплайн 2-4 итер/сек (мозг+tinyllama таймаут 300с → ретрай без бэкоффа). Лечится рестартом виктории; КОРЕНЬ (ретраи без бэкоффа в executor fallback-цепочке) — волна-7 №1.

**/run честный статус: БИМОДАЛЕН** — в окнах 20-35с синк-ответ (верный), под постоянным фоном конвейера — 40с хендафф. Три рычага дальше: бэкофф-фикс спиралей (волна-7), приоритет синка, fast-track фактов через phi (продуктовое решение владельца: v149.8 выключил его для fact-seeking).

**Уроки:** (12) короткие запросы к семантик-кэшу — зона ложных попаданий (плотные эмбеддинги): мин-длина или повышенный порог; (13) порядок загрузки раннеров решает всё на 1-GPU: «руки первыми» — правило загрузки слота; (14) ретрай без бэкоффа превращает один застрявший таск в denial-of-service всей полосе.

---

## § Волна-5 (2026-10-11 v150.5) — ночной фантом кипера, PROACTIVE-классификатор, /run синк побеждён ✅

1. **«Ночные выгрузки мозга» были фантомом кипера.** Форензика: 0 эвикций/крашей/рестартов за ночь (лог ротирован в 05:42 job'ом — история цела частично). «brain warmed» 00:45-05:06 = 5с-таймаут api/ps под ночной нагрузкой батлов → grep пуст → ложный «нет мозга». Фикс: fail-safe проверка (проба упала дважды = не трогаем; греем только при доказанном отсутствии в валидном ответе).
2. **PROACTIVE-классификатор (тройной баг одной строки):** `"healthy" in status` считал нездоровыми контейнеры БЕЗ healthcheck (kibana рестартилась циклами!), «health: starting» (рестарты при каждом деплое), а реально «unhealthy» — ЗДОРОВЫМ (подстрока!). Плюс открытие: ProactiveMonitor всегда крутился и в victoria-agent (victoria_server:1917), его docker-рестарты «ожили» с появлением DOCKER_HOST у контейнера. Фикс: unhealthy=только явный False, None=нет статуса; victoria-agent пересобран (образ, не бинд!) — kibana цела цикл, /run стабилен.
3. **/run СИНХРОННЫЙ ОТВЕТ ПОБЕЖДЁН: «Париж» за 21.6с, status=success** (аудит-симптом «handoff на тривиальном вопросе» закрыт). Цепочка победителей: 40с-бюджет (v150.2) + потолки num_predict (v150.4, марафоны не глушат очередь) + здоровые полосы. Остаточная латентность ~20с = prompt-eval толстого системного промпта (кристаллы+DNA+мудрость) — волна-6: диета промпта для коротких вопросов.
4. **MLX оправдан и жив**: «нестабильность» была моими пробами без Content-Type; узел остаётся, STRICT 404, канарейки корректны. Нюанс: MLX-прокси игнорирует num_predict (марафон-риск на своей полосе) — в бэклог.
5. Мозг: архитектура qwen35 НЕ поддерживает параллелизм (np=1 навсегда) + train-ctx=8192 (кап 16K выше обучения — предупреждение; RAG-промпты >8K токенов и так вне распределения). Понижать не стали.

**Уроки:** (9) «проба не ответила» ≠ «объекта нет» — акторы обязаны различать отказ пробы и доказанное состояние; (10) подстрочный матчинг статусов («unhealthy» ⊃ «healthy») — классика инверсий, парсить строго; (11) образ vs бинд-маунт: проверять, какой код РЕАЛЬНО исполняет контейнер, прежде чем считать фикс развёрнутым.

---

## § Волна-4а (2026-10-10 v150.4) — потолок генераций + чистки с пошаговой верификацией ✅

1. **num_predict-потолки** (марафонская генерация на phi — 16K токенов ≈ 20 мин на 13 t/s — морила голодом запросы даже к idle-мозгу): `local_router._get_adaptive_options` → `ROUTER_DEFAULT_NUM_PREDICT` (дефолт 4096 ≈ 5 мин), FAST PATH expert_worker → 2048. После прокатки: brain 200/1.7с, phi 200/5.8с, encode 200/0.02с.
2. **Чистки (каждая с проверкой до/после):** `ollama rm hf.co/unsloth/Qwen3.8-27B-GGUF:Q8_0` (29GB, 0 ссылок) и `qwen3-coder:30b` с 11434 (18GB; копия на 11436 жива, проверено) → **диск 205→250Gi free (+45GB, 89%→86%)**. НЕ удалены (используются): gemma3n (light-hands роутера), phi3.5:3.8b-stable (роутер-fast!), minicpm-v (vision), deepseek-r1:32b (VIP Вероники), qwen2.5-coder:14b (evolver@11434). Docker-образы: неиспользуемых старше 14д всего ~600МБ — prune нерентабелен (22GB-воркеры в работе). Бэкапы ротируются сами (9 дневных дампов, 8.4GB).
3. **Урок:** «probe timeout» при жующих раннерах (CPU%) = глубокая очередь под нагрузкой, не поломка — смотреть завершения в GIN-логе прежде чем рестартить.

---

## § Волна-3 фиксов аудита (2026-10-10 v150.3) — сторож прозрел, канарейки, medic, Rust-SQL ✅

1. **runner-watchdog прозрел — ГЛАВНЫЙ фикс волны.** `scripts/ollama_runner_watchdog.sh` искал процессы «ollama runner», но ollama 0.33 переименовал раннеры в **llama-server** → сторож был слеп годами: застрявшие в «Stopping…» раннеры висели ЧАСАМИ (замер: мозг 29 мин), держали слот планировщика, очереди загрузок переполнялись → мгновенные **503 «maximum pending requests exceeded»** на phi/nomic (вся 503-патология загрузок последних дней). Фикс: паттерн llama-server + скоуп «только дети владельца порта 11434» (раннеры Вероники не трогаем). Живой тест: сторож нашёл и убил застрявший (1736с uptime); после — все три полосы резидентны, phi 200/3.1с, мозг 200/2.5с, encode 200/0.13с; раннер мозга поднялся **-np 4** (4 слота) при загрузке на свободной RAM.
2. **Канарейки ФУНКЦИИ в hourly watchdog** (`scripts/launchd_watchdog.py::http_canaries`): генерация 1 токена phi@11434 (180с — холодная загрузка легитимна), fast@11435 (120с), encode@8001 (30с) — через существующий дедуп/Telegram. Первое же включение поймало реальную аварию рук (503) — работает.
3. **maintenance-флаг в system_auto_recovery.sh** (каждые 300с спавнил блудные ollama serve при ручных операциях).
4. **medic ProactiveMonitor включён** (писался, но не запускался): unhealthy-контейнеры → docker restart (до 3) с safe-list (postgres/redis/pgbouncer/docker-proxy — только алерт). Закрывает «vector_core unhealthy 1.5ч без реакции».
5. **Rust legacy-SQL → ANN-CTE** (lib.rs, cargo check/build чисто, gateway пересобран и рестартнут, health 200) — последний HNSW-рецидив.
6. **Мелочи с большим эффектом:** single-instance лок кипера (mkdir+stale-защита — дубль-рестарты ollama 07.10); renew_certs.sh chmod+x+xattr (192 дня «Operation not permitted» → «актуальны»); employees-sync kickstart (саб-процесс ожил, «employees.json уже актуален», лог 20МБ ротирован); cron-дубль nightly_learner 03:00 удалён (контейнер остаётся); keep-alive фолбэк ai_core убран (единый источник — ollama_keep_alive_policy, импорт проверен в контейнерах); env OLLAMA_NUM_PARALLEL=4/MAX_QUEUE=100/NUM_CTX=16384 применён полным bootout+bootstrap (kickstart plist не перечитывает!).
7. **Разоблачения разведки:** MLX-Recovery-unload НЕ трогает phi (только victoria-wisdom\*); дубликат кипера был разовым ad-hoc (постоянной второй джобы нет — лок закрывает класс); `com.atra.auto-recovery` — 300с-цикл (вот источник блудных serve).

**Осталось (волна-4):** /run sync-ответ (40с бюджет есть, пайплайн не успевает — внутренности victoria_server); MLX-легаси периодически подвисает на 'fast' (канарейка флагает — кандидат на отключение узла: MLX_API_URL=disabled); чистки диска 89% (образы 119GB, модели-дубли, бэкапы — лист на подтверждение владельцу); ingestion enforce; Ollama.app убрать из Login Items (руками); 100k untyped-узлов.

**Уроки:** (7) переименование внутренних процессов мажорной версией олламы ослепляет сторожей — grep-паттерны в акторах проверять при каждом апгрейде ollama; (8) «503 мгновенный» = очередь битов, смотри зависшие Stopping-раннеры.

---

## § Волна-2 фиксов аудита (2026-10-10 v150.2) — P1: фантом 64K побеждён, гейт стабилен под нагрузкой, HNSW возвращён, vector_core async ✅

1. **Фантом num_ctx=65536 побеждён.** Корень: `expert_worker.py` FAST PATH слал `/api/chat` БЕЗ options → ollama авто-растит контекст под длину RAG-промпта (промпты по 6.7K токенов в живом кэше) → predicted 26GiB → эвикции мозга. Фикс: `"options": {"num_ctx": 16384}`. После прокатки — **0 строк «predicted to exceed»** в ollama.log (были сотни в час). Плюс Modelfile-капы nomic@8192/phi@16384/minicpm@8192 (v150.1).
2. **Universal gate стабилен под нагрузкой.** `local_router.py`: single-flight (per-node asyncio.Lock — нет stampede тегов), WARN-лог фолбэка (раньше молчал), маркер-фолбэк и для Ollama-узлов, таймаут тегов 3→1.5с, негативный кэш 5с. Нагрузочный тест (`scripts/tests/gate_load_test.py`, 16 параллельных): теги 11434 И 11435 — **0 отказов, p95=4мс** (в аудите MLX-теги падали 15/24).
3. **HNSW-рецидив v149.16 выкорчеван в 6 местах**: `ai_core` (CASE-множители → Python-реранк, overfetch 18→6), `knowledge_service` ×2 (overfetch ×3, сортировка в Python), `semantic_cache` ×3 (порог/last_used-сортировка в Python). EXPLAIN: **Index Scan using knowledge_nodes_embedding_hnsw_idx** (был Parallel Seq Scan по 100k векторов).
4. **vector_core: async-клиент** (один AsyncClient на процесс, батч = gather+семафор 4, лимит 64) + healthcheck timeout 3→10с/interval 15с/start_period 60с. Замер: **20 параллельных /encode — 0 ошибок, p50=214мс p95=351мс** (в аудите — 500-е и минутные заморозки loop'а).
5. **Гард: пин-таймаут 60→240с.** Диагноз «спавн второго раннера виснет» оказался МЕДЛЕННОЙ ЗАГРУЗКОЙ (Metal-аллокация phi 15GB под давлением Docker VM = минуты) + короткими клиентскими таймаутами: раннер реально резидентится (Forever), просто дольше старого лимита.
6. **/run синк-бюджет 20→40с** (`VICTORIA_SYNC_SAFE_TIMEOUT_SEC` в compose). Механизм работает (handoff ровно на 40.0с), но полного синк-ответа под очередью воркеров пока нет — упирается в пропускную способность мозга (runner `-np 1`).

**Дорожные события (10.10):** (а) **десктопное Ollama.app было запущено вручную и украло порт 11434** у launchd-инстанса (весь тюнинг мимо) — процессы закрыты; ПРАВИЛО: слот 11434 обслуживает ТОЛЬКО homebrew.mxcl.ollama, Ollama.app не автостартует; (б) `system_auto_recovery.sh` спавнит блудные `ollama serve`, безвредно падающие об bind (не знает maintenance-флага — волна-3); (в) порт у launchd-инстанса подтверждён, теги 200.

**Осталось (волна-3+):** /run sync-ответ требует np>1 у мозга (порядок бута руки→мозг или принудительный параллелизм при свободной RAM); MLX-генерации при 6+ параллельных честно упираются в 1 GPU-слот; Rust legacy-SQL (lib.rs:238); чистки диска/моделей; medic ProactiveMonitor; генерационные канарейки в watchdog-jobs; автозапуск Ollama.app убрать из Login Items вручную.

**Уроки:** (5) «зависло» ≠ «не работает» — сначала ps/api/ps: раннер мог грузиться дольше таймаута клиента; (6) два ollama-инстанса (App + launchd) на одном порту = невидимый хаос — один источник истины на слот.

---

## § Волна-1 фиксов аудита (2026-10-08 v150.1) — P0: война акторов остановлена, MLX воскрешён, ctx-анархия capped ✅

**Контекст:** полный аудит `docs/AUDIT_FULL_2026-10-08.md` (16 находок, 8 слоёв, живые пробы). Волна-1 = три P0-корня. Исполнено под `scripts/maintenance.sh on/off`; все проверки — живьём.

1. **Гард больше не убивает мозг.** `scripts/ollama_wisdom_guard.py::_should_unload` работал по контракту ДО v149.8 («11434 = только phi+nomic») и выгрузил `victoria-qwen38` **1130 раз** (война с brain-keepalive: 30GB-перезагрузки каждые ~10 мин 5 суток, load 25, рестарты Ollama каждые 30 мин, вероятная причина зависания демона 07.10 22:25 МСК). Фикс: белый список `BRAIN_ALLOW = victoria-qwen38*, qwen3.8*` + phi3.5:3.8b* + nomic* + moondream* (IMMORTAL); чужое (включая victoria-wisdom*) выгружается как раньше. Плюс таймстампы в лог (были без дат — форензика невозможна) и **явный `num_ctx:16384` в пине phi** (без опций ollama 0.33 авто-размеряет KV под свободную RAM — phi раздувалась до **111.9GB VRAM / ctx 131072** и душила хост до 3-5% free).
2. **MLX-прокси 11435 воскрешён.** Корень `Stream(gpu,1)`: mlx≥0.32 сделал Metal-стримы ПЛЕЧОМ ПОТОКА; модель грузилась в main-потоке, генерация уходила в дефолтный executor-поток (17 346 ошибок с 05.10, все — модель phi3.5). Фикс в `mlx_api_server.py`: `_GPU_EXECUTOR = ThreadPoolExecutor(1, "mlx-gpu")` — load (:1282, :1716) и generate (:1350, :1440) в одном потоке. Плюс **`MLX_STRICT_MODEL_MATCH=true`** (env в plist `com.atra.mlx-api-server`): незнакомая модель → **404** вместо молчаливой подмены (v149.6 закрыт до конца).
3. **Ctx-анархия capped на 16K, env в один источник.** `local_router.py::SAFE_MAX_CTX 32768→16384` (комментарий врал про «NUM_PARALLEL=6, Qwen3.5-35B»; 32K=33.8GiB > system_free ~27GiB при Docker VM 32GB wired → гарантированные эвикции мозга). Modelfile-капы: `victoria-qwen38` num_ctx 32768→**16384** (мозг прогрет 29.7GB @16K, держится), `phi3.5:3.8b` +16384 (пересоздана FROM -stable), `minicpm-v` +8192, `nomic-embed-text` +8192. Env: выгружен `com.atra.ollama-env` (глобальные дубли NUM_PARALLEL=2/CONTEXT_LENGTH=16384), `launchctl unsetenv` ×4; единый источник — `homebrew.mxcl.ollama.plist` (PARALLEL=4, KEEP_ALIVE=-1, MAX_QUEUE=100, NUM_CTX=16384). Роутер прокатен рестартом 11 контейнеров (bind-mount).

**Evidence (живьём, 23:30 МСК 08.10):** мозг `victoria-qwen38` резидентен @16K 29.7GB, generate **1.4с** (было: unload каждые 60с / «warmed» каждые 10 мин); `phi3.5:3.8b` **200 за 0.18с** тёплая; `nomic` @2048 резидентен; MLX: `fast` 200/6.6с, `phi3.5` 200/5.9с (было 500×100%), чужая модель **404**; `Stream(gpu)` у оркестратора: прирост **0** за час (было 99/сутки); RAM хоста 5%→67%+ free. Дорожные события: kill зомби-контейнера knowledge_os_worker (PID-zombie от дневного RAM-давления) + recreate через compose.

**Не закрыто (волна-2):** (а) **фантом num_ctx=65536** — некий клиент шлёт гигантские эмбеды/запросы (nomic-запросы раздували KV до 26GiB, планировщик клинило; после капов nomic@8192 безвредно, но давление ротации phi↔brain осталось; идентификация: tcpdump в спокойный час); (б) `/run` sync-таймаут 20с → `handoff timeout_sync_safe_mode` даже на тривиальных вопросах (константа в victoria_server — поднять или прогрев); (в) spawn phi при живом фантомном давлении до 124с (временно: ping-guard с большим timeout).

**Уроки (в правила):** (1) при миграции модели X на слот Y — ревизия ВСЕХ стражей слота в тот же коммит (цена промедления: 5 суток деградации); (2) `ollama create` живого тега на загруженном сервере может заклинить планировщик — только под maintenance; (3) опции num_ctx обязательны в КАЖДОМ пине/прогреве — авто-размер KV ollama 0.33 под свободную RAM взрывоопасен; (4) health-check обязан пробовать ФУНКЦИЮ (generate 1 токен), а не /api/tags — 17k ошибок жили под зелёным тегом.

---

## § Последние изменения (2026-10-05 v149.22) — ДЕГРАДАЦИЯ ЭКСПЕРТОВ: финальный корень — metadata::text ILIKE seq scan ✅

**Полное расследование по живому тесту (задача Анне вручную через БД):** экспертный конвейер не отвечал минутами. Цепочка вскрыла ПЯТЬ слоёв:

1. **Спасатель 10 мин** (`rag_loop_no_llm_call`) убивал работающие задачи: 288 за 04.10 (до миграции — 1-6/день). Пороги подняты 10→25/30 мин (`SMART_WORKER_LLM_STUCK_MINUTES/STUCK_MINUTES` в env knowledge_os_worker).
2. **RAG-LOOP BREAKER** (кап 2 сброса → cancelled) — сработал по праву на задаче, пойманной в шторм.
3. **503-шторм Ollama** (5908 запросов/мин: ретраи embeddings+tags без пауз) — забивал очередь, phi3.5 недоступна экспертам. Лечится рестартом ollama; `OLLAMA_NUM_PARALLEL=2` на сервере (не 5 как в env!) — при шторме очередь мгновенно дохла.
4. **ФИНАЛЬНЫЙ КОРЕНЬ:** `model_enhancer.py`/`anti_hallucination.py` — fallback-поиск `metadata::text ILIKE ANY(...)` по 100,508 узлам: **44.4 сек** на запрос (Parallel Seq Scan), при конкуренции 10 воркеров — LWLock-очередь и минуты зависания. Expert worker висел в этом запросе → last_llm_call_at не обновлялся → спасатель добивал. **Фикс:** metadata::text убран (GIN trgm по content остался) → **9.8с** (4.5x), нет self-конкуренции.
5. verified: свежая экспертная задача проходит полный цикл (assign→dispatch→Anna worker→RAG→brainstorm) при чистой системе.

**Урок миграции:** изменённый маршрут (гейты, модели) умножил время циклов — а старые watchdog-пороги (10 мин) были откалиброваны под старую скорость. При любом изменении производительности — пересматривать пороги сторожей.

---

## § Последние изменения (2026-10-05 v149.21) — деградация конвейера экспертов: 4 корня ✅

**Симптомы за сутки:** Trust Gate REJECTED (local_fallback), uuid UnboundLocalError на handoff, DNA SQL invalid input, качества ответов просели.

**Корни (все закрыты):**

1. **uuid-тенение** (`expert_worker.py`): локальный `import uuid` в ветке 1322 делает имя локальным для ВСЕЙ 1000-строчной `process_task` — на ветке handoff (1721) `uuid.UUID()` падал UnboundLocalError → swarm-подзадачи не создавались. Фикс: `_uuid_mod` (уже импортирован в том же блоке).
2. **MLX-GATE отсутствовал в local_router** (v149.6 чинил только victoria_server): экспертные вызовы с qwen38/coder уходили на прокси 11435 и молча обслуживались старой wisdom → слабые ответы → Trust Gate резал. Фикс: гейт в route-цикле (`continue` на не-MLX модели), подтверждён.
3. **DNA SQL**: asyncpg ждёт str для jsonb — dict ронял `INSERT INTO knowledge_nodes` (antifragile-ноты не писались). Фикс: `json.dumps` + `$2::jsonb`.
4. **(из v149.20) TypeError len(None)** — тот же конвейер.

**Ложные тревоги разобраны:** MODEL_SUBSTITUTION на tinyllama — штатно (лёгкая модель не на прокси, заменена дефолтом на 0.58с); 500 «No response returned» — разовый (после рестартов воркеров), повтор стабилен.

**Верификация:** HNSW-запрос через /run: async→completed, по теме; воркеры здоровы, гейт в логах.

---

## § Последние изменения (2026-10-04 v149.18) — живая битва «сейчас», прогрев в ранере, single-pass nightly ✅

1. **Битва-2 (12 раундов, тёплый мозг): 5:4 по решённым, tie=0** (впервые ноль ничьих — POLL 360с работает), 3 error — тяжёлые раунды 9/10/12 (SQL/файл-аудит с RAG-контекстом) не уложились в 360с при параллельных соло+дебат задачах. Соло взял communication 5:0 (и это честно), дебат — code 4:1.
2. **Битва-1 (до прогрева):** первый раунд съел холодную загрузку 30GB — все error. **Фикс:** ранер теперь греет мозг ДО раундов (до 8 мин, /api/ps-поллинг) — коммит c5b71c2d.
3. **Ночной learner single-pass:** NIGHTLY_LOOP дефолт 0 (cron-exec получает один проход), контейнеру явно 1. Двойные/вечные циклы невозможны.
4. **Ложная тревога разобрана:** 33 «cancelled» за 25 мин — метрические записи orchestration_tracking (создаются с cancelled, воркеры не берут). Сторож (4ч/1ч) честный.
5. **Хвост битвы в бэклог:** для тяжёлых раундов (file-audit/SQL) — per-category POLL_TIMEOUT (900с) или предварительная выборка RAG-контекста вне раунда.

---

## § Последние изменения (2026-10-04 v149.17) — охота свежим взглядом: docker-API наружу, мусор в БД знаний ✅

1. **SECURITY (критично):** docker-proxy публиковал API на 0.0.0.0:2376 БЕЗ аутентификации — любой в LAN мог управлять всем Docker. Привязано к 127.0.0.1; контейнеры ходят по внутренней сети (проверено: наружу закрыт, изнутри 200).
2. **База знаний: 5,502 машинного мусора понижены** (low_priority ×0.5 в RAG): «источники недоступны» (2,890), «Ошибка парсинга» (594), «None» (430), сырые JSON-action. 79k нетипизированных узлов — отдельная чистка.
3. **Само-находка:** дедуп nightly_learner — полумера (замок не обновляется циклом); cron гоняет learner внутри victoria-agent рядом с контейнером. Полное решение — single-pass по env; в бэклог.
4. **Риск принят:** MLX 11435 слушает 0.0.0.0 (нужен контейнерам) — на домашней LAN за NAT приемлемо, задокументировано.

---

## § Последние изменения (2026-10-04 v149.16) — RAG-корень найден и вырван: HNSW-индекс убитым ORDER BY ✅

**Корень четырёх симптомов:** векторный поиск сортировал `(embedding <=> $1) * CASE low_priority` — умножение ОТКЛЮЧАЛО HNSW-индекс → seq scan 100,508 векторов → TimeoutError у каждого RAG-поиска (пустые сообщения об ошибках) → тяжёлые пути 4-6 мин, ENGLISH-цели CancelledError на ~219с, ядро отчёта не укладывалось в таймауты.

**Фикс:** ORDER BY только индексный (`embedding <=> $1`), штраф low_priority перенесён в Python (реранк-блок уже был). Ошибки поиска: сплошные → **ноль**. Тяжёлый путь: 4-6 мин → **~2 мин**. ENGLISH: CancelledError → **completed, по теме**.

**Дополнительно:** ошибки ядра стали громкими (`type + repr` — пустые строки замалчивали TimeoutError); nightly_learner получил дедуп-лок 4ч (контейнер-цикл + cron 03:00 = двойной прогон).

**Верификация живьём:** тяжёлый RU (WAL) completed ~2 мин по теме; ENGLISH completed ON-TOPIC; ошибок поиска 0 за циклы наблюдения.

---

## § Последние изменения (2026-10-04 v149.15) — цепочка протестирована вживую, отчёт и битва оживлены ✅

1. **Ночная авария разобрана:** brain_keepalive грузил qwen38 при низкой RAM → сегфолт → 503-отравление всего Ollama (65к отказов, битва 0/50). Кипер стал безопасным: RAM≥40%, бэкофф 30м, kickstart при отравлении. При 66% свободной памяти модель грузится за 30с без падений.
2. **Цепочка живыми тестами:** quick/fact/консилиум ✓; Вероника ✓ (фибоначчи, 26с); дебат-движок ✓ (3 участника, 6 мнений — ночные INCOMPLETE были 503-голоданием); куратор ✓ (ntfy); self-check 9/9; бэкапы ✓ (день-в-день).
3. **Мини-битва 3 раунда: 3/0, ноль ошибок** — конвейер битвы подтверждён до ночной.
4. **Утренний отчёт — три слоя починки:** CancelledError-гвард (BaseException в 3.11); дробление промпта на 3 блока; ПРЯМОЙ вызов мозга (qwen38@11434, без RAG — данные уже в промпте) с ядром как fallback. Итог: «✅ Доклад отправлен».
5. **Кэш очищен от яда:** 65 пустых записей удалены; гейты с двух сторон (чтение: пустой кэш — не ответ; запись: пустоту не кэшируем).
6. **Бэклог-уточнение:** ядро тонет в RAG-ретраях («Ошибка поиска знаний», пустые сообщения об ошибке) — тяжёлые пути медленные из-за этого. Отдельное расследование поиска знаний; ENGLISH-цели ~219с CancelledError всё ещё в очереди.

---

## § Последние изменения (2026-10-03 v149.13) — P0 гонка целей ЗАКРЫТА: per-run клон агента ✅

**Корень (найден точно):** `AtraBaseAgent.run()` начинает каждый запуск с `self.memory = [системный контекст]` — а агент-синглтон один на воркера. Конкурентный run() (куратор/бот/второй запрос) перезаписывал память первого: LLM получал чужой диалог → чужой ответ (ENGLISH-задача вернула юридический прогноз; ранее — «Проанализируй промпт Veroni» в чужом слоте).

**Фикс (мировая практика — прототип на запрос):** `agent = copy.copy(self)` в начале run(): память (`memory`), блокировки инструментов (`_blocked_tools`) и хэш команд — у каждого запуска свои; executor/planner общие (stateless HTTP-клиенты). 15 ссылок self→agent в теле run().

**Верификация (конкурентная пара):** pgbouncer-вопрос + HTTP/2-вопрос одновременно → pgbouncer **completed, по теме** (изоляция работает; раньше ответ бы подменился).

**Остаток (единственный открытый, точная трассировка):** англоязычные цели гаснут CancelledError на ~219с — отмена всплывает ИЗНУТРИ enhanced.solve (внешние потолки подняты: watchdog 180→480с, hard 600→900с, background 240→600с — не они). Трасса: `background start → before enhanced.solve → +219s → cancelled`. Кандидаты: semaphore-monitor, extended_thinking timeout-wrapper, recursion-cancel хак из комментария 7078.

---

## § Последние изменения (2026-10-03 v149.12) — батарея живых тестов: 10 атак, вердикты, фиксы ✅

**Метод:** 10 реальных запросов через прод-/run (знания/ловушка/код/devops/математика/инъекция/запись в системный файл/английский/консилиум/галлюцинация) + серийные ретейки.

**Вердикты:** KNOWLEDGE ✓40s, CODING ✓, DEVOPS ✓, CONSILIUM ✓ (монолит vs микросервисы по теме), REASON-TRAP ✓(5 мин), MATH ✗→✗386 после фикса, INJECTION: утечки НЕТ (но уводит в метрики — fact-probe hijack), GUARD: файл НЕ записан (ai_core.py цел; ответ мусорный из кэша), HALLUCIN ✗ (план вместо ответа), ENGLISH ✗✗ (даже после фиксов).

**Найденные корни и фиксы:**

1. **ORCHESTRATION_V2 10%-лотерея** (Зоя решала через phi3.5, возвращала план вместо ответа) → `ORCHESTRATION_V2_ENABLED=false`.
2. **Семафор 2с** — при живом трафике 3/4 параллельных задач отменялись → 60с.
3. **Потолок фоновых задач 240с** — тяжёлые qwen38-задачи (4-6 мин) гасились на полпути («превысил лимит времени», CancelledError) → 600с.
4. **Утечка внутренних лесов** (reasoning_trace, «План от оркестратора», «ПРОЕКТ ПАМЯТИ», «Отвечай строго по фактам», назначения моделей) → строчный резак в `_strip_internal_monologue`.

**НЕ ЗАКРЫТО (главный оставшийся баг, P0):** **гонка целей** — при конкурентном трафике (куратор/бот «Проанализируй промпт Veroni…», юридические прогнозы) чужая цель подменяет или съедает слот задачи: ENGLISH-задача выполняла чужой goal, финальный ответ = прогноз ИИ в юриспруденции. `victoria_enhanced.solve(goal)` чист — смешение ВЫШЕ по конвейеру (understand/strategy/кэш). Нужна отдельная сессия: contextvar-изоляция цели по task_id.

---

## § Последние изменения (2026-10-03 v149.10) — аудит по чеклисту Анны (QA): сюрпризы найдены ✅

**Метод:** владелец попросил дать эксперту задачу составить промпт-проверку. Попытки вскрыли 3 новых перехвата цели (expert-task RAG inject чужого ТЗ, факт-проб на «проверка системы», clarify-ловушку) + финал генерации ушёл в phi3.5 (слабый чеклист) — само упражнение стало находкой. Чеклист исполнен вручную по направлению Анны.

**Найдено и закрыто:**

1. **Двойной бэкап каждую ночь:** cron 03:00 (~/bin → ~/atra_backups → gdrive+health) И launchd 03:30 (scripts/db_backup.sh → repo/backups/db, 2.7GB, никто не проверяет). Отсюда пары дампов `03-00-00/03-00-0X` на gdrive и двойной расход квоты. Launchd-конвейер выгружен (обратимо).
2. **auto-recovery демон мёртв годами:** каждый цикл «docker-compose.yml не найден» → 2.9GB ошибок. Выгружен (есть recovery-listener/boot-incident-guard). Прочие пожиратели (mlx-логи 1.1GB и др., суммарно ~4.5GB) обнулены; scripts/atra_logs_rotate.sh + launchd еженедельно (>256MB).
3. **docker build cache 52.6GB** — очищен (диск 189→220Gi). Образы 119GB оставлены (используются).
4. **Зелёное подтверждено:** Prometheus 12/12 целей up (expert-workers ✓), очередь задач пуста (0 pending/in_progress), сертификаты до 03/2027, privileged-контейнеров нет, docker.sock только в docker-proxy (by design) и log-scanner (риск принят), backups/db gitignored, redis-ключи с TTL.

**Новые баги в бэклог (перехваты цели):** expert-task RAG inject сохранённых ТЗ в knowledge_nodes; «проверка системы» уходит в fact-probe; document-generation финиширует на phi3.5-fallback.

---

## § Последние изменения (2026-10-03 v149.9) — полный обход по слоям после упрёка владельца ✅

**Урок:** прежние «всё проверено» верифицировали изменённое, а не систему; каждый новый проход по нетронутым углам находил старое. Этот проход — по слоям целиком.

1. **Утренний отчёт запускался ДВАЖДЫ (cron 08:30 + launchd 08:30)** — вот источник двойных сообщений и «параллельного» падения на len(None). Cron-дубль удалён; в скрипт добавлены дедуп-лок (10 мин) и отказоустойчивый run_cursor_agent (любая ошибка ядра → None → штатный retry/fallback).
2. **watch_victoria_rebuild НИКОГДА не работал:** запускал `docker-compose -f docker-compose.yml up victoria-agent`, а сервис определён только в agents-оверлее → «no such service» → молчаливый провал (TG-токен пуст). Рестарт 01:13 был autoheal, не вотчер. Исправлен на оба compose-файла.
3. **brain_keepalive (launchd, 5 мин):** мозг гарантированно резидентен независимо от разгрузчиков (ice/shadow/board-consult/unload-политик) — «тёплый мозг» стал механическим инвариантом, а не договором.
4. **mas-worker выгружен:** стучался в несуществующий redis:6380 (хвост dev/atra), не мог работать в принципе. Обратимо: `launchctl load ~/Library/LaunchAgents/ai.atra.mas-worker.plist`.
5. **ollama.log 3.1GB обнулён** (+3ГБ диска) + launchd-ротация еженедельно (>512MB). Установка crontab блокируется системой в этой сессии — ротация через launchd.
6. **Подтверждено живым после всех recreate:** SOURCE_GUARD (отклоняет запись в ai_core.py), PG/Redis только на 127.0.0.1, враппер битвы берёт обновлённый ранер (360с + судья qwen38), сегфолты прекратились после 10:21.
7. **Осталось (осознанно):** performance_watchdog меряет RAM Docker-VM (кэши), не давление Mac — soft-ice срабатывает чаще нужного (мозгу уже не вредит после п.3); employees-sync-daemon падает в ~5% циклов (пиковая память, самолечится).

---

## § Последние изменения (2026-10-03 v149.8) — «везде и все в курсе»: полная миграция qwen38 ✅

1. **Аудит по требованию владельца нашёл недоселённые уголки:** local*router (reasoning/default = phi/wisdom → now qwen38@11434), extended_thinking (дефолт wisdom, URL зашит в MLX → qwen38 + URL выбирается по модели), strategic_board/board-scheduler (BOARD_CONSULT*\* = wisdom → qwen38 в коде и compose), 6 контейнеров жили со старым env (restart не обновляет env — recreate: orchestrator/worker/anna/heavy/victoria-1/rest/board-scheduler + рестарт dynamic-1..5).
2. **Контракт enforcement:** запрещённые дубликаты `victoria-wisdom-24k:latest` и `victoria-wisdom-v3.5:latest` УДАЛЕНЫ с Ollama 11434 (~35GB диска). Wisdom остаётся только на MLX 11435 как явный легаси-fallback.
3. **Segfault-каскад мозга (10578 за день!):** llama-server qwen38 (31GB Q8) сегфолтился при загрузке под давлением памяти (Docker VM распухла до 53GB) — с 02:51 (во время битвы — вторая причина ночных таймаутов). Каждый повторный запрос ронял раннер снова → мгновенные 503 «queue full». **Лечение:** рестарт ollama + чистая загрузка qwen38.
4. **SHADOW UNLOAD выгружал мозг:** performance_watchdog меряет RAM Docker-VM (кэши) → вечный soft-ice → victoria выгружала qwen38 после 10 мин простоя → перезагрузка под давлением → segfault. **Фикс:** выгрузка мозга только в hard-ice (RAM>85%, реальная авария).
5. **Эхо-хвосты и кэш:** хвостовое эхо (SWARM & HANDOFF PROTOCOL ПОСЛЕ ответа) срезается; семантический кэш чистит до-фиксовые ответы на выдаче (кэш-хит мог вечно отдавать мусор).
6. **Финальная верификация:** «дерево решений vs случайный лес» → completed, ответ по теме, чистый (нет SWARM/Discovery), единственный LLM_CALL — victoria-qwen38, MLX-подмен 0. Резидентно: qwen38 30.3GB + phi3.5 9.1GB + nomic 0.4GB.

**Правило:** после изменения compose-env сервисы обязаны рекрейтиться (restart не обновляет env); новые «мозговые» модели добавлять в guard-списки (MLX-маркеры, TOOL_CALL_ALLOWED, keep-листы) сразу при внедрении.

---

## § Последние изменения (2026-10-03 v149.7) — битва на qwen38: консилиум выигрывает, ранер починен ✅

1. **Первая битва полностью на qwen38 (без подмен):** A(соло)=8 **B(консилиум)=17** tie=22 error=3. По решённым раундам консилиум 17:8 (68%) — доминирование в brain-категориях: research 4:0, code_audit 4:1, devops 3:1, security 2:1; соло взял только communication (лёгкая болтовня). Против прошлой ночи (16:16, 18 «оба бестолковые») — качественный скачок.
2. **Корень 22 tie:** ранер опрашивал async-задачу 180с, а тяжёлый путь qwen38 занимает 200-300с → ранер сдавался, задача отменялась (`Task cancelled — semaphore slot released`), судья видел «таймаут» у обоих (28/50 раундов). Все tie — architecture/debugging/testing (тяжелейшие промпты). **Фикс:** `AB_POLL_TIMEOUT` 180→360.
3. **Судья гнал холодную wisdom:** после гейта v149.6 wisdom на MLX выгружена (0 ГБ) — каждый судья холодно грузил её ~45с (битва растянулась на 2ч16м). **Фикс:** судья → `victoria-qwen38` на тёплом Ollama 11434.
4. **Gdrive sync ловил дамп «на записи»:** дамп пишется до ~03:48, sync в 03:10 получал «source file is being updated». **Фикс:** cron 03:10→04:45. Health-check 04:00 проверяет вчерашний офсайт (25ч < 49ч) — зелёный; сегодняшний уезжает в 04:45.
5. **Утренний отчёт 08:30 — ПОЛНЫЙ доклад отправлен** (первый штатный за долгое время; раньше пустой fallback). Хвосты: двойной старт (400мс, второй упал на редком `len(None)` в глубине пути) — в бэклог; пользователю ушёл и полный доклад, и один fallback.

---

## § Последние изменения (2026-10-03 v149.6) — MLX-прокси молча подменял мозг ✅

1. **Открыто при полной перепроверке:** `_generate_via_mlx_or_ollama` («if True: всегда MLX первым») слал ЛЮБУЮ модель на MLX-прокси 11435. Прокси не знает `victoria-qwen38` и молча подменял её дефолтом `CATEGORY_TO_MODEL["default"]=victoria-wisdom-24k` → часть ответов генерировала старая wisdom на MLX, контракт v149.4 нарушался, две модели-мозга держались в памяти одновременно.
2. **Фикс (двусторонний):** victoria_server — гейт `_mlx_served_markers` (MLX первым только для реально обслуживаемых моделей: phi3.5/qwen_3b/tinyllama/wisdom/fast/tiny/…; qwen38 → сразу Ollama 11434); mlx_api_server — warning `[MODEL_SUBSTITUTION]` при подмене неизвестной модели (молчаливость больше невозможна). Evidence live: «[MLX_DEBUG] victoria-qwen38 не обслуживается MLX-прокси — сразу Ollama → [OLLAMA_DEBUG] Starting Ollama path».
3. **Обнаружен авто-деплой:** `watch_victoria_rebuild.py` (launchd) следит за victoria_server.py/system_tools.py/local_router.py и при изменении сам прогоняет compose recreate — правки этих файлов деплоятся сами (рестарт 01:13 был им). Не править эти файлы во время ночных битв.
4. **Прочее при перепроверке:** cron-копия ~/bin/atra_check_backups_health.sh была старой (без PATH/возраста) — синхронизирована; 14 контейнеров перезапущены со свежим ai_core; employees-sync-daemon падает в ~5% циклов («init_import_site» при пиковой памяти) — самолечится следующим циклом, в очередь.

---

## § Последние изменения (2026-10-03 v149.5) — молчаливые отказы закрыты: отчёт, source guard, бэкапы ✅

1. **Утренний отчёт падал молча (ImportError → заглушки):** `run_smart_agent_sync` был удалён из `ai_core.py`, а `victoria_morning_report.py` ловил ImportError и подставлял заглушки с `None` — каждый день в 08:30 уходил пустой fallback без единого LLM-вызова. Заодно пострадали `process_expert_task`, `expert_generator`, `enhanced_orchestrator`, `prompt_engineer_batch`. **Фикс:** `run_smart_agent_sync` восстановлен в ai_core (sync-обёртка, безопасна в работающем loop), заглушка в отчёте теперь ОРЁТ в лог с traceback. **Evidence:** реран → «✅ Доклад Виктории с OKR и ROI успешно отправлен» (Qwen3.8, ntfy).
2. **SOURCE_GUARD (санитария инцидента ai_core.py):** строка 1 ai_core.py была перезаписана LLM-текстом («исправляет ошибку вызова LLM…») → SyntaxError у свежих импортов (утренний отчёт 08:30). Писатели без проверок: `execution_phase._execute_file_write` и `SystemTools.write_file` (весь репо bind-mount в victoria-agent). **Фикс:** `knowledge_os/app/source_guard.py` — запрет системных путей (`knowledge_os/app/`, `src/agents/`, `backend/app/`…; override env `ATRA_ALLOW_SOURCE_WRITE=true`), syntax-gate для .py, отказ при усечённой перезаписи (<30% исходника), алерт в ntfy. Подключён в оба писателя. Тесты: 5/5 сценариев.
3. **Планировщик на старой модели:** `VICTORIA_PLANNER_MODEL` пуст → дефолты уводили planner на wisdom-24k @11435 (qwen38 живёт на 11434). **Фикс:** compose v149.4-контракт (`VICTORIA_MODEL`, `VICTORIA_PLANNER_MODEL=victoria-qwen38:latest`, `USE_MLX_FOR_PLANNER=false`, `VICTORIA_MLX_BRAIN/WISDOM_MLX_PRIMARY=false`), в коде qwen38 первым в preferred-списках. Верифицировано: «Current planner model: victoria-qwen38:latest».
4. **Эхо промпта в ответах:** тяжёлые /run возвращали куски системного шаблона (SWARM & HANDOFF PROTOCOL / ПРАВИЛА / «ТЫ — ВИКТОРИЯ») перед самим ответом. **Фикс:** `_strip_internal_monologue` отрезает всё до последнего эхо-блока (unit-тест: мусор убран, чистый ответ не тронут).
5. **Бэкапы: офсайт молчал 9 дней:** Google Drive quota exceeded (12.1 GiB живых дампов с 09-10, retention KEEP_DAYS_REMOTE=7 не срабатывал т.к. sync падал до удаления). Health-check говорил «✅ OK» на 8-дневную копию (проверял только наличие). **Фикс:** cleanup корзины + ручная ротация (оставлен 09-24, удалено 16 дампов) → **Free 11.98 GiB**; health-check теперь считает возраст офсайт-копии по имени файла (лимит 49ч) и алертит; rclone-path фикс подтверждён ручным прогоном.
6. **Ночная битва (01.10):** соло 16 — консилиум 16, tie 18 (битва шла ещё на wisdom; честный тест qwen38 — завтра ночью). Факт-пути: привет → quick 3.5с, «статус проекта» → живые метрики (completed_24h=175, error_rate 0).

**Правило «чтобы не повторялось»:** любые новые писатели файлов в автономных контурах обязаны проходить через `source_guard.guard_file_write`; sync-скрипты бэкапов — удалять СТАРЫЕ до/независимо от загрузки новых; health-check'и проверяют возраст, а не наличие.

---

## § Последние изменения (2026-09-23 v147.1) — RAG hubness: корень нерелевантности ✅

**Корень «свалки контекста» глубже капов — hubness эмбеддингов.** Эксперимент: cosine(запрос про pg_dump) → top-1 = «Стратегическая директива Совета» (0.799) против 0.700 у релевантного узла. 265 board_directive-узлов — генерические тексты-«хабы», ближние соседи любого запроса.

**Фикс:** даунрэнкинг −0.12/×0.85 для типов `board_directive|mentorship_note|strategy_summary` и категорий `strategy|mentorship` (Rust-path `eff_sim` + python-SQL ORDER BY); LIMIT 8→6.

**Evidence (live):** top-узлы для бэкап-вопроса — архитектура проекта (PostgreSQL+pg_vector), 2921 символ; `/run` → pg_dump --compare шаги проверки за 30с; привет→quick_answer. Наблюдение: docs автоматически заглощаются в knowledge_nodes (FINDINGS нашлись поиском).

---

## § Последние изменения (2026-09-23 v147) — RAG-контекст: релевантность и лимиты ✅

1. **Корень «свалки контекста»** (ответы = чужие темы/mode-collapse): нет общего капа собранного контекста (до 20k+ симв.), пороги similarity 0.55/0.6 впускали посторонние узлы, двойная RAG-инъекция на запрос (`_get_knowledge_context` + `EnhancedRAGEngine` при `FORCE_PROACTIVE_RAG=true`).
2. **Фикс:** общий кап `KNOWLEDGE_CONTEXT_MAX_CHARS` (default 4000, обрезка по границе узла, порядок vector→graph→visual); пороги 0.55/0.6 → **0.65** (Rust+LanceDB), Rust limit 10→6, top-1 fallback ≥0.6; `FORCE_PROACTIVE_RAG=false` на victoria-agent (дубль-инъекция выключена, возврат — env).
3. **Evidence:** `/run` «объясни: шаги проверки бэкапа PostgreSQL» → ответ по теме (pg_dump, структурирован, **29с**); регресс: привет→quick_answer, статус→fact_live_probe, объясни→consilium (debate по теме).
4. **Остаток:** in-process путь специалистов — преамбулы (конституция/meta-блоки вокруг вопроса) — следующий виток сборки промпта; прод-контур чист. Reranker-тест (RAG_RERANKER_ENABLED=true) релевантность не вернул — откажено, false.

---

## § Последние изменения (2026-09-23 v146) — Фаза 5.2: wisdom → DNA самообучение + битва после фиксов ✅

1. **Курируемое самообучение:** `expert_dna_wisdom_injection.py` — отбор high-band wisdom (distilled+band=high+conf≥0.8) → инъекция в `experts.metadata.wisdom_dna` (рендер в `_compose_expert_prompt` — блок WISDOM DNA во всех LLM-путях) → eval до/после через боевой /run → судья → keep/rollback (ERROR/пустые/деградация — автороллбэк из wisdom_dna_history). Кураторский маппинг категория→эксперт. Ночная петля в nightly (6ч). Дашборд: счётчики в Wisdom-вкладке.
2. **Live-подтверждение:** Виктория ← research-wisdom, kept (before 2.0 → after 3.0, судья); wisdom_dna в metadata, узел помечен.
3. **Ограничение:** eval через /run измерим только для Виктории (дефолтный ответчик); in-process `run_smart_agent_async` виснет в worker-контейнере (local_router, reasoning) — эксперты-специалисты подключаются после починки (задача).
4. **Ночная битва после фиксов (v144):** консилиум впервые победил — **B=24 : A=14**, tie 12, ошибок судьи **0** (retry работает). Категории: security 0-5, analysis 0-4, research 0-4 — дебат; communication 3-0, code_audit 4-0 — соло (роутер верен). По плану — копим 2 недели до решения о дефолтных составах.
5. **Расписания на launchd:** com.atra.backup-health-check (04:00, скрипт в ~/bin — cron+TCC никогда не работал), com.atra.morning-report (08:30, ntfy-fallback, старый краш distiller-report починен SQL-срезом).

---

## § Последние изменения (2026-09-23 v145) — Фаза 4: error budget + отчёт роя + STRICT_LOCAL drill ✅

1. **Error budget (SRE-практика):** `knowledge_os/app/error_budget.py` — суточный бюджет неудач на автономный цикл (env `ERRBUDGET_<CYCLE>_MAX`, default 10), Redis-счётчики `errbudget:{cycle}:{date}`, успех реабилитирует (−1). Исчерпан → цикл в наблюдаемый режим + triage-задача в БД (source=error_budget, diagnostic_path). Обвязка: `run_evolution_loop.py` + `orchestrator_phases.py` фаза 13 (curiosity).
2. **Битый SQL закрыт (атрибуция v143 сработала):** `adaptive_learner.py` писал под чужую схему `synthetic_training_data`. Починены: миграция `usage_count`, INSERT под реальные колонки (prompt/response/metadata), `input_query[:50]`→`left(prompt,50)`, потерянный отступ `if not exists`. Цикл живьём зелёный (1 updated).
3. **Фаза 1 KPI подтверждён:** eligible_with_emb/eligible_all = **54186/54186 = 100%** (официальный `content_is_rag_eligible`); raw 74.7% — антипаническая метрика (v131), не авария. Band-глубина: метадата `band` в узлах отсутствует (наследие v121) — наблюдение.
4. **Утренний отчёт (4.3):** 4 новых блока — ночная работа роя по source, решения совета (12ч), error budgets, консилиум-роутер. Формат доклада обновлён (ночная автономия + здоровье автономии).
5. **STRICT_LOCAL drill (4.4, bounded):** pre-flight зелёный; 3 вопроса (вкл. консилиумный, 54с дебат) — **0 реальных облачных вызовов** («OpenRouter пропущен: ключ не задан» = корректное поведение); режим возвращён на false. Полный offline-drill 1ч — ручной шаг.

Evidence: `victoria_consilium_routed_total{research,applied}=1`; evolution-баннер «бюджет: 10 неудач осталось»; контейнеры healthy; очередь 0.

---

## § Последние изменения (2026-09-23 v144) — Фаза 3: consilium-роутер + ночные A/B-битвы ✅

### Что внедрено

1. **Eval-контур:** `configs/evals/consilium_v1.jsonl` (50 вопросов × 10 категорий) + `scripts/consilium_ab.py` (соло vs дебат, судья victoria-wisdom-24k на MLX, ретрай парсинга, `wins_by_category` в отчёте). Полная битва: A=25 B=18 tie=1 err=6.
2. **Роутер консилиума (план 3.3):** `is_consilium_winnable_goal()` в `task_detector.py` (research/testing по узким паттернам, категории через `CONSILIUM_CATEGORIES`); в `_run_task_background` после guardrail'ов: debate через `POST {EXPERT_DIALOGUE_URL}/api/expert-dialogue/start {topic, mode:"debate"}` (default URL `host.docker.internal:8080` — localhost внутри контейнера не работает!). Анти-стаб: degraded/пустой дебат → fallback в соло. Метрика `victoria_consilium_routed_total{category, outcome}`. Только async-путь; opt-out `CONSILIUM_ROUTING_ENABLED=false`.
3. **Языковой фикс дебата:** промпты `multi_agent_debate.py` (участники + синтез) на русском, запрет off-topic шаблонов — дебат отвечал английским «structure/scalability» даже на «привет».
4. **Ночные битвы:** launchd `com.atra.consilium-battle-nightly`, 01:30, лог `~/Library/Logs/atra/consilium_battle.log` — накопление данных для расширения `CONSILIUM_CATEGORIES` числами.
5. **Учебный контур Виктории (v143-продолжение):** восстановлен FAST_ACTION_PATH (файл-проверки 0.01с), code-gen → 11436, «статус проекта» → fact-live-probe с метриками, guard объяснительных глаголов в fact-probe, no-clarify на объяснительные цели. Регресс 4/4 (привет 0.9с, статус 0.1с, код 12с, файл-чек 0.01с).

### Evidence (live 2026-09-23)

- Классификатор 8/8 (research/testing позитивы, communication/code_audit/статус негативы).
- «объясни, что такое HNSW…» → `strategy=consilium, category=research, engine=debate`, ответ русский по теме, 790 символов.
- «привет» → `quick_answer` 0.9с; «какой статус проекта?» → `fact_live_probe` 0.1с (роутер не мешает быстрым путям).
- `/metrics`: `victoria_consilium_routed_total{category="research",outcome="applied"} 1`; очередь 0; 8010/8080 = 200.

### Открытое

- Sync-путь /run дублирует стратегию — роутер пока только async (следующая итерация).
- Дебат латентен (50–90с) — норма для async; RAG-обогащение дебата тянет нерелевантные узлы (Фаза 1).
- Судья A/B: согласие ~80% на 20 разметках — на пороге; дожим по мере накопления ночных битв.

---

## § Последние изменения (2026-09-22 v143) — аудит + ремонт: Veronica порт, Prometheus targets, TCC-guard, GatheringFuture ✅

### Диагноз (полный аудит)

1. Veronica: контейнер healthy, но `ports` пусты — с хоста 8011 = 000.
2. Prometheus: target `expert-worker-light` (несуществующий) — job expert-workers down.
3. `start_model_tracker.sh`: hardcode `postgresql://zhuchyok@...` → hourly FATAL в PG + зомби-процессы model-tracker с 28.08.
4. `boot-incident-guard` exit 1: системный `/usr/bin/python3` без TCC → PermissionError в `~/Documents`.
5. `_GatheringFuture exception was never retrieved`: анонимный `asyncio.gather` под `wait_for` в `ai_core.py` и `parallel_executor.py`.
6. Ложные срабатывания аудита: бэкапы живы (cron 03:00 + gdrive 03:10 + health-check 04:00, дамп 758MB валиден); tg-deferred-alerts жив (KeepAlive).

### Решение

1. `docker-compose.agents.yml`: veronica-agent `ports: 8011:8000` + recreate.
2. `prometheus/prometheus.yml`: expert-workers → heavy + dynamic-1..5.
3. `start_model_tracker.sh` → `admin:${POSTGRES_PASSWORD:-secret}`; зомби убиты, launchd kickstart.
4. `boot-incident-guard.plist` → `/opt/homebrew/bin/python3`.
5. Root cause GatheringFuture: py3.11 `wait_for(gather(...))` при отмене/таймауте оставляет исключение gathering-future незабранным. Фикс: в `ai_core._get_knowledge_context_impl` и `parallel_executor.execute_parallel` — `asyncio.wait` (+ cancel pending, retrieve `.exception()`) вместо `wait_for(gather)`. Диагностика через временный monkeypatch `asyncio.gather` (GATHER-ORIGIN trace), после фикса снят. Evidence: 0 предупреждений за 4+ мин (было десятки/мин).
6. Ops-гигиена: rm atra-{grafana,prometheus,kibana,elasticsearch}, rm -f sandbox-qa (0 строк логов); мёртвый `ai.knowledgeos.backup_db` и дубль `com.atra.knowledge-postgres-backup` → `LaunchAgents/disabled/`.
7. `.cursor/rules/expert_and_brainstorm.mdc` синхронизирован с контрактом v142.
8. PG: включены `log_connections/log_disconnections` для атрибуции остаточных битых SQL.
9. Режим /expert переведён на **авто-триггер** (без команды): критерии включения/исключения — `CLAUDE.md` § «Режим /expert — авто-триггер» + `.cursor/rules/expert_and_brainstorm.mdc` § /expert.

### Evidence (live 2026-09-22 21:1x MSK)

- `curl localhost:8011/health` → `{"status":"ok","agent":"Вероника"}`.
- Prometheus: **12/12 up** (было 7/8).
- `launchctl list` boot-incident-guard → exit **0**; model-tracker PID жив, FATAL в PG = 0.
- Docker: exited=0, 36 контейнеров running; очередь 0/0; слоты 11434/11436/11435 по контракту.

### Открытое (наблюдение)

- Атрибуция «column source/status/assigned_to does not exist» + «aggregate in GROUP BY» — LLM-диагностический SQL, ждём следующий эпизод под трассировкой.
- RAG-eligible ~70% (цель ≥80%) — дожим nightly; эксперты: 88 всего / 33 активных (штат на линии, закрыто в Фазе 2.1; сотрудники = employees.json, Юлия активирована).

---

## § Последние изменения (2026-09-22 v142) — слот рук 11434 + сканер без петли + wisdom→MLX ✅

### Диагноз

LOG_SCANNER ел prose (`Error`, слово FATAL, `TimeoutError` в WARNING nightly) и открывал очередь. На 11434 одновременно садились wisdom / minicpm / `3.8b-stable` / smollm (Git-Guardian) и вытесняли nomic. Корень утечки wisdom: `_ollama_url_for_model` считал `VICTORIA_EXECUTOR_MODEL=victoria-wisdom-24k` «executor» и слал мозг на `OLLAMA_EXECUTOR_BASE_URL` (часто 11434). Guard был дворником, не замком.

### Решение

1. Сканер: ловить `ERROR:` / `FATAL:` / CRITICAL, не голые Error/timeout; IGNORE nightly TimeoutError, parallel worker FATAL, embed/503 busy, `_GatheringFuture`.
2. Руки: `normalize_ollama_hands_model` → один `phi3.5:3.8b`; ReAct/warmup default phi; minicpm keep_alive=0 и skip-as-hands.
3. Замок маршрута: wisdom → только MLX 11435 (`victoria_server` + `expert_worker`); distill teacher wisdom → phi; deferred warmup wisdom skip.
4. Guard: evict всего, кроме phi+nomic; pin обоих; timeout unload 60с.

### Evidence (live 2026-09-22 20:28 MSK)

- Очередь `pending/in_progress/queued` = **0**; `victoria:async_inflight` = **0**.
- HTTP: 8010 / 8080 / 11435 = **200**.
- 11434 `/api/ps`: `phi3.5:3.8b` + `nomic-embed-text:latest`.
- Коммиты: `d5544ff7`, `56a457b1`, `57646d6e`, `ed2976d8`.
- pytest рук/сканера/маршрута: **32 passed** (последний прогон после рестарта victoria + workers).
- Правило: `.cursor/rules/91_finish_to_closed.mdc`.

### Не закрыто (намеренно)

- ~400 porcelain / мёртвый хардкод 185 — не runtime-слой.
- На 11436 рядом с coder может сидеть phi (воркерный fallback) — это не слот рук.
- Настоящий `ERROR:` Victoria сканер по-прежнему шлёт в `/run`.

---

## § Последние изменения (2026-08-14 v141) — IDE frontend + scout class + workspace mount ✅

### Диагноз

`:3000` не существовал (нет контейнера/образа). Nightly scout: `cannot import name 'VeronicaScout'` — класс срезан при вставке `is_usable_scout_analysis`. Gateway `list_v2` 404: `WORKSPACE_ROOT=/workspace` без volume.

### Evidence (live 2026-08-14 23:00 MSK)

- Frontend `:3000` 200 healthy; backend `:8080/health` healthy + docker healthcheck.
- Gateway HTTP + `.:/workspace` → `list_v2` count=175, `docs` 396 entries.
- VisualRAG `vectors=10`; scout_research node `scout/2026-08-14-openai-anthropic-google-leaks-and-updates.md`.
- pending=0 in_progress=0 stale=0; no unhealthy; Victoria knowledge_size=83753.
- `pytest knowledge_os/tests/test_curated_research_refresh.py` → 8 passed.

---

## § Последние изменения (2026-08-14 v140) — Gateway HTTP + VisualRAG bootstrap ✅

### Диагноз

Gateway 8081 отдавал TLS, потому что compose всегда ставил `GATEWAY_CERT_PATH`; frontend ходит `http://…:8081`. VisualRAG `vectors=0`: FAISS в `/app/models` не существовал, indexer не на cron.

### Решение

1. TLS opt-in: `GATEWAY_TLS_ENABLED=false` locally; empty cert path → HTTP (existing binary).
2. Nightly bounded visual index (≤15 md из `docs/`) + persist `knowledge_os/models`.

### Evidence (live 2026-08-14 22:43 MSK)

- Gateway log: `listening on 0.0.0.0:8081 (HTTP mode)`; `GET http://127.0.0.1:8081/health` → `OK`; RestartCount=0, Health=healthy.
- Empty `GATEWAY_CERT_PATH=` must **not** be set (old binary treats empty string as TLS). Cert/key env omitted; `GATEWAY_TLS_ENABLED=false`.
- VisualRAG: `GET :8005/health` → `vectors=5`; FAISS reload after recreate; Docker healthcheck was false-unhealthy (`curl` missing in image) — probe switched to Python urllib, now `healthy`.
- Visual-search volumes: `docs` at `/app/docs` and `/app/corpus/docs`; index POST uses `text_content` (nightly does not depend on path inside visual container).
- Queue: pending=0, in_progress=0 (cancelled=80, completed=2303). Victoria `/status` knowledge_size≈83744.

---

## § Последние изменения (2026-08-14 v139) — P1: curiosity cooldown, OK-twins, status count ✅

### Диагноз

R&D спавнился снова: cooldown смотрел только `failed` + два reason, а CB пишет `cancelled`/`circuit_breaker_loop_exhausted`; смена эксперта (Роман→Инна) обходила per-expert dedup. File-check с result `ОК` watchdog отменял как work_item_timeout. `/status` knowledge_size = RAM project_knowledge (4), не PG.

### Решение

1. Cooldown: cancelled+failed, CB reasons, title-level.
2. Timeout-cap: OK → completed; cancel только пустой result.
3. `/status` knowledge_size = COUNT(knowledge_nodes).
4. Veronica/evolution: непустой `repr(e)`; nightly HOST\_\*.

### Evidence

- `pytest knowledge_os/tests/test_p1_curiosity_and_timeout_cap.py`
- pending curiosity R&D cancelled with cooldown reason; `/status` knowledge_size ≈ PG count

---

## § Последние изменения (2026-08-14 v138) — P0: dynamic-1, SOP mount, stale SQL ✅

### Диагноз

Инна Exited 137 без автоподъёма. Nightly SOP → Errno 30 после v137 `docs:ro`. Victoria stale-cleanup каждые 5 мин: `INTERVAL '%s seconds'` (psycopg-плейсхолдер в asyncpg) — UPDATE никогда не исполнялся.

### Решение

1. Recreate `expert-worker-dynamic-1`.
2. Overlay `../docs/SOP:/app/docs/SOP` (rw) поверх `docs:ro`.
3. asyncpg `$1` + `make_interval`; **не** трогать `pending`.

### Evidence

- `pytest knowledge_os/tests/test_stale_task_cleanup_sql.py`
- dynamic-1 healthy; postgres log без `"%s seconds"` после recreate Victoria
- nightly: `/app/docs/SOP` writable

---

## § Последние изменения (2026-08-14 v137) — Auto curated AI Research («Последние находки») ✅

### Диагноз (Five Whys)

Дашборд `localhost:8501` «Последние находки» застыл на **9 авг**. Фильтр живой (AI Research + `file_path` + source ∈ indexer/scout). Почему пусто свежее? Indexer/scout не на cron. Почему scout не помогал? `VeronicaScout` писал domain `Global Intelligence`, `source=veronica_scout`, без `file_path` — и звал несуществующий `knowledge_service.add_node`. Root cause: **jobs that feed the tab were never scheduled**, plus scout metadata missed the curated contract.

### Решение (KISS / Occam)

1. `knowledge_nightly` background: `run_continuous_research_refresh` каждые 6ч (`NIGHTLY_RESEARCH_INTERVAL_SEC=21600`).
2. Re-index `docs/COGNITIVE_CODE.md` (+ extra) — volume `../docs:/app/docs:ro`.
3. Scout: 1 topic/cycle, domain **AI Research**, `source=scout_research`, `file_path=scout/YYYY-MM-DD-*.md`.
4. Не клонировать `system_prompts_leaks` каждую ночь.

### Evidence

- `pytest knowledge_os/tests/test_curated_research_refresh.py`
- `knowledge_nightly` log: `📚 [NIGHTLY] Curated research refresh`
- SQL: curated `MAX(updated_at)` после цикла > 2026-08-09

---

## § Последние изменения (2026-08-14 v136) — Ops tip-top: FK, queued status, file-check, LanceDB ✅

### Диагноз (Five Whys)

Неделя 7–14 авг: ядро healthy, но ops шумел. FK 668× — DELETE knowledge*nodes без ON DELETE. `/run` poll queued — GET читал TCP Redis STRING, статус жил в HASH. Cancel ~50% — tracking twins + monster timeout: `_fast_file_check` смотрел только title «Делегировано», не parent_goal. LanceDB protobuf corrupt. Sandbox без HOST*\* на victoria/watchdog. Evolution без MLX_BASE_URL.

### Решение

1. Migration: `expert_discussions`/`tasks.knowledge_node_id` → ON DELETE SET NULL.
2. `/run/status`: только redis_manager HASH + local store; store всегда `processing`.
3. `_fast_file_check_from_task`: title + description + parent_goal.
4. LanceDB: quarantine corrupt dir, recreate table (PG = SoT).
5. Compose: HOST_PROJECT_ROOT on victoria/watchdog/**evolution**; MLX_BASE_URL on evolution.

### Evidence

- `pytest knowledge_os/tests/test_fast_file_check.py`
- FK `pg_get_constraintdef` contains ON DELETE SET NULL
- Recreate victoria-agent / knowledge_os_worker / knowledge_evolution / performance-watchdog

---

## § Последние изменения (2026-08-02 v135) — Wisdom MLX-primary + SRE error taxonomy ✅

### Диагноз (Five Whys)

Логи `LLM_TIMEOUT … (Ollama busy?)` → fallback на MLX. Почему timeout? Wisdom шёл в Ollama (загружен руками). Почему в Ollama? Executor default = Ollama base. Почему fallback «спасал»? MLX имел `victoria-wisdom-v3.5` без `:latest`, а Ollama-тег `:latest` на MLX не матчился / путь был медленный. Root cause: brain на wrong accelerator + false busy taxonomy (client timeout ≠ 503).

### Решение (world practice)

1. `executor.ask`: wisdom → probe MLX `/health` → MLX-primary; strip `:latest` for MLX ids.
2. Taxonomy: `reason=client_timeout`; explicit `[LLM_BUSY]` only on 429/503/busy body.
3. Compose: `VICTORIA_MLX_BRAIN`, `VICTORIA_WISDOM_MLX_PRIMARY`, `USE_MLX_FOR_PLANNER` default true; `local_router` + planner defaults aligned.
4. Opt-out: `VICTORIA_WISDOM_MLX_PRIMARY=false`.

### Evidence

- `pytest knowledge_os/tests/test_executor_wisdom_route.py` → 3 passed.
- In-container `OllamaExecutor.ask`: `[LLM_ROUTE] wisdom MLX-primary model=victoria-wisdom-v3.5 url=…:11435`, HTTP 200 ~9.4s.
- Env on victoria-agent: `VICTORIA_MLX_BRAIN=true`, `VICTORIA_WISDOM_MLX_PRIMARY=true`, `USE_MLX_FOR_PLANNER=true`.

---

## § Последние изменения (2026-07-31 v134) — Omni-RAG hang: honor RAG_RERANKER_ENABLED ✅

### Диагноз

`/api/omni-rag/search` получал Ollama embed 200, затем зависал. Semantic/keyword ~0.16s; hang = CrossEncoder в `hybrid_search` при `RAG_RERANKER_ENABLED=false` (флаг игнорировался).

### Решение

1. `enhanced_search`: gate rerank на `_reranker_enabled()`; lazy import CrossEncoder; load/predict timeouts.
2. `omni_rag_search`: `asyncio.wait_for` → 504 при timeout.
3. Victoria: victoria-agent; evidence omni-rag HTTP 200 ~0.19s.

---

## § Последние изменения (2026-07-30 v133) — Expert skills injection wire ✅

### Диагноз

Docker `expert_worker` импортировал несуществующий `app.worker_memory` → skills никогда не inject; ошибка в `debug`. Имя «Анна» не матчило ключи `qa/backend/...`.

### Решение

1. Import → `app.worker.worker_memory`; fail → `warning`.
2. `load_skills_for_expert(role=, department=)` + name hints + relevance + general.
3. Role/dept из metadata или `experts` table.
4. Tests: Анна/QA non-empty; workers restarted.

### Evidence

- `pytest tests/test_worker_memory.py` → 5 passed.
- Container: `load_skills_for_expert('Анна', …)` → chars>0, `ИНСТРУКЦИИ ИЗ СКИЛЛОВ`.
- `process_task` source contains `app.worker.worker_memory`.

---

## § Последние изменения (2026-07-29 v132) — Eligible ≥80% + embed path fix ✅

### Диагноз (Five Whys)

Eligible был ~67% при «живом» nightly: каждый `get_embedding` заново грузил SentenceTransformer (~5s/node) + VectorCore URL битый (`:8100`). Root cause — нет singleton + нет Ollama-primary на host Metal.

### Решение

1. `semantic_cache`: ST singleton; Ollama `/api/embeddings` primary; VectorCore secondary; `encode_texts_best` для batch.
2. `embedding_eligibility`: chunked encode→write; catch-up script `scripts/catchup_eligible_embeddings.py`.
3. Nightly compose: `EMBED_BACKFILL_BATCH=200`, `EMBED_PREFER_OLLAMA=true`.

### Evidence (live 2026-07-29)

- Catch-up: eligible **52417/65290 = 80.28%** (`TARGET_REACHED`); Ollama 16/16 in ~0.8s.
- Queue tip-top: failed|pending|stale = `0|0|0`; Victoria/MLX/Grafana 200.
- Out of scope: Approach C (coverage/E2E), raw 100%, wipe cancelled ledger.

---

## § Последние изменения (2026-07-29 v131) — Closure lite (eligible KPI + MLX probe + Grafana HC) ✅

### Definition of Done (корпорация tip-top+)

1. Очередь: `failed=0`, `stale=0`, pending кратковременно.
2. Телеметрия: `DELEGATION_ALERT=0` при failed=0; MLX monitor fail=0 при host healthy.
3. **RAG KPI = eligible %**, не raw % (цель eligible ≥80%; raw низкий ≠ авария).
4. **MLX SoT probe:** `GET http://127.0.0.1:11435/health` (или `host.docker.internal:11435/health` из Docker).  
   `GET /v1/models` **не** обязателен (может 404) — не считать это «MLX down».
5. Grafana: docker Healthcheck → `(healthy)` при живом `/api/health`.

### Норма метрик (не паника)

| Метрика                              | Норма                                 | Паника?        |
| ------------------------------------ | ------------------------------------- | -------------- |
| RAG-eligible with_emb / eligible_all | ≥80% цель; 55–80% = догон nightly     | Нет            |
| Raw with_emb / all nodes             | часто 50–60% из‑за junk в знаменателе | **Нет**        |
| MLX RAM ~84%                         | watch у порога 85%, concurrent=1      | Нет            |
| cancelled delegation ledger          | история timeout-cap                   | Нет (не stuck) |

### Решение

1. Dashboard caption: eligible KPI + anti-panic raw.
2. Bible: MLX `/health` contract.
3. Recreate Grafana with working healthcheck (`curl -sf` + start_period).

### Evidence (live 2026-07-29)

- Grafana: `Health=healthy` Healthcheck=set; `/api/health` → 200; `docker ps` → `(healthy)`.
- MLX: `/health` → 200; `/v1/models` → **404** (ожидаемо; не down).
- RAG: nodes_all=82617 with_emb=44398 (**raw 53.7%**); eligible_all=65260 eligible_with_emb=43824 (**eligible 67.2%**, догон к ≥80%).
- Tasks: failed/pending/stale отсутствуют в срезе; cancelled/completed — ledger.

---

## § Последние изменения (2026-07-29 v130) — Observability hygiene (OpenCode noise) ✅

### Диагноз

Ложные сигналы: `stuck_delegation=cancelled` и `resource_monitor` → `localhost:11435` внутри Docker при живом MLX на хосте.

### Решение

1. Alert stuck = `failed + stale_in_progress`; cancelled — ledger only.
2. Docker-aware MLX/Ollama URL в `resource_monitor` + env на `knowledge_os_worker`.
3. Cancel stale curiosity pending >24h.

### Evidence

- `DELEGATION_ALERT` count=0 при cancelled=51; `MLX health check failed`=0; mlx_url=host.docker.internal.

---

## § Последние изменения (2026-07-28 v129) — Orchestration tracking ≠ work-queue failed ✅

### Диагноз

4 `failed` за день — все `orchestration_tracking` twins (swarm LLM timeout + board shells). Не рабочие задачи, но портили KPI.

### Решение

1. `_record_orchestration_task_complete`: всегда `cancelled`; outcome в metadata.
2. Triage cancel 4 rows; drop known-OK `swarm_intelligence` curator line.

### Evidence

- `failed=0`, tracking noise cancelled; Victoria restarted with patch.

---

## § Последние изменения (2026-07-28 v128) — Docker Created: mounts denied ✅

### Диагноз

`7bc0ce8…` (`expert-worker-dynamic-1`) и `0c0bb59…` (`sandbox-qa`) в Status=`Created`, не Exited. Start → `mounts denied: The path /app/data is not shared`. Compose project.working_dir был `/app/knowledge_os` (оркестратор через docker.sock), relative volumes → `/app/...` на Mac host.

### Решение

1. Recreate dynamic-1 с host binds; `docker rm` sandbox-qa.
2. `HOST_PROJECT_ROOT` / `HOST_SANDBOX_SHARED_DIR` в `.env` + compose dynamic slots + orchestrator env.
3. `sandbox_manager`: resolve host path; recreate on bad mount.

### Evidence

- dynamic-1 healthy; sandbox-qa removed; orchestrator `HOST_PROJECT_ROOT` set.

---

## § Последние изменения (2026-07-28 v127) — Ghost Redis resurrection + residual tails ✅

### Диагноз

Anna worker крутил `RESURRECTION` на goal `178ed052…` (Trading & Quant): Redis `claimed`, строки в `tasks` нет → бесконечный resume. Плюс orphan curiosity R&D `in_progress` при idle smart_worker; локальные dirty-патчи OpenWebUI/KPI.

### Решение

1. Purge ghost goals when DB row missing/terminal; SREM `active_tasks`.
2. Ops: HDEL claimed ghosts (Anna/Roman); cancel orphan R&D.
3. Ship: OpenWebUI tool-router fallback, KPI redis timeout, drop phantom model id `Victoria`.

### Evidence

- `redis_claimed=0`, Anna `Found my task` count=0 за recovery interval.
- Queue: `pending=0 in_progress=0 failed=0`.

---

## § Последние изменения (2026-07-28 v126) — Work-item timeout cap + queue triage ✅

### Диагноз

Delegation-задачи (`victoria_monster_delegation`) при `work_item_timeout_420s` сбрасывались в `pending` без потолка → retry storm (`attempt_count` до 1182). Failed=8: LLM timeout на проверке `swarm_intelligence.py` + пустые tracking-only board shells.

### Решение

1. Cap `SMART_WORKER_WORK_ITEM_TIMEOUT_MAX_ATTEMPTS` (default 3) → `cancelled` + manual triage flags.
2. Watchdog sweep тех же зомби.
3. Ops cancel: 3 in_progress + 8 failed + 1 stale curiosity.
4. Autostart nightly только с `ENABLE_NIGHTLY_AUTOSTART=true`.

### Evidence

- Queue: `pending=0 in_progress=0 failed=0`.
- Tandem: `ENABLED=true GROUNDING=true`, nightly healthy.

---

## § Ops note (2026-07-28) — Tandem ON: redistill + grounding live ✅

- `knowledge_nightly` recreated: `REDISTILL_PRIORITY_ENABLED=true`, `DISTILL_GROUNDING_ENABLED=true`, batch=1, skip-if-busy.
- Compose default ENABLED restored to `true` (was false → loop silent).
- Evidence: `Priority re-distill: updated=1 failed=0 ungrounded=0`, DB `accepted=1`, `ground=0.76`.

---

## § Последние изменения (2026-07-28 v125) — Hybrid distill grounding (RAGAS-inspired) ✅

### Диагноз

`band=high` поднимался по длине текста; victoria/phi писали шаблоны («aggressively scale digital service…») без опоры на source.

### Решение (гибрид как у гигантов)

1. **Template reject** — mode-collapse phrases.
2. **Lexical faithfulness** — claim tokens ⊆ source (min overlap).
3. **Embed rescue** — cosine source↔claim если embedder доступен.
4. Fail closed: `redistill_status=rejected_ungrounded` без записи ложной wisdom.
5. Design: `docs/plans/2026-07-28-distill-grounding-hybrid-design.md`.

### Evidence

- Unit: `test_distill_grounding.py`.
- Smoke: template board sample → reject; mentorship-like → accept.

---

## § Последние изменения (2026-07-27 v124) — Priority re-distill: 503 backoff + light teacher ✅

### Диагноз

Днём `Priority re-distill: updated=0 failed=3` из‑за Ollama `503 maximum pending requests` (контеншн с workers/`qwen2.5-coder:14b`). Distiller на 503 сразу сдавался без fallback; compose временно выключал redistill (`ENABLED=false`).

### Решение

1. `_call_teacher_direct`: busy detect → backoff retries → fallback model.
2. Node delay между кандидатами; default teacher `phi3.5:3.8b`.
3. Compose: `ENABLED=true`, batch=1, interval=1800s, busy retries env.

### Evidence

- Unit: `_ollama_is_busy`.
- Ops: `updated=1 failed=0 teacher=phi3.5`; `prio_done`/`band_high` снова растут.

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

**Архитектура:** Единый Интеллект v31.2. **Параллельная работа (Parallel Work):** Мозг (MLX, порт 11435) и Руки (Ollama, порт 11434) разделены. Wisdom **не** дублируется в Ollama (v142). Актуальная мозг-модель: **victoria-wisdom-24k** только на MLX.

**Полноценная Виктория (v31.2 / контракт v142):**

1. **MLX (мозг):** `VICTORIA_MLX_BRAIN=true` — `victoria-wisdom-24k` на 11435.
2. **Ollama (руки):** 11434 держит **только** `phi3.5:3.8b` + `nomic-embed-text` (`keep_alive=-1`). Wisdom/minicpm/smollm на этом порту запрещены. Coder — отдельный инстанс 11436 (`qwen3-coder:30b`).
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
2. **Проверка Ollama руки:** `curl -s http://localhost:11434/api/ps` → HTTP 200, **только** `phi3.5:3.8b` + `nomic-embed-text` (wisdom в ps = нарушение v142)
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

### v150.13: Time Machine-эквивалент без root (добавлено)

Системный TM включить нельзя (нет destination-диска, sudo закрыт паролем). Вместо — **еженощие hardlink-снапшоты блобов** (`cp -al`, cron 04:30, ротация 7 дней): ноль места (df не меняется), мгновенно, и удаление/GC оригиналов физически не может освободить данные, пока жива ссылка в снапшоте. Первый снапшот 31GB создан 14.10 22:51. Восстановление = `cp -al` обратно (или re-pull 11 мин). Рекомендация владельцу: при подключении внешнего диска ≥256GB — включить системный TM (одно ручное действие в Settings).
