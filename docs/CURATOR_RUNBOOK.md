# Runbook куратора

Краткая последовательность шагов для прогона куратора и обновления эталонов.

---

## 0. Роль куратора-наставника (Cursor)

**Куратор-наставник** — это Cursor-агент (или человек с тем же процессом). Он **не учит Victoria при каждой задаче** в реальном времени, а задаёт стандарт и обновляет среду, из которой Victoria читает контекст:

- **Эталоны** в `docs/curator_reports/standards/` — как «правильно» отвечать на привет, статус, список файлов и т.д.
- **Прогоны** — отправка типовых задач Victoria, сравнение ответов с эталоном (`curator_compare_to_standard.py`).
- **Обучение Victoria** — при расхождениях: обновление эталонов, добавление в RAG (`curator_add_standard_to_knowledge.py`), правки библии и чеклистов. Victoria подхватывает это через RAG и системные промпты при следующих запросах.

**Правило: как давать задание Виктории (все должны знать).** Когда куратор (Cursor-агент или человек) даёт задание Виктории и должен проконтролировать результат — **всегда использовать скрипт** `scripts/curator_send_tasks_to_victoria.py` с `--file <файл с goal>` и `--async --max-wait 600`. Скрипт сам опрашивает статус и при завершении пишет отчёт в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и `.md`. «Виктория сделала» = появление этого файла; куратор открывает отчёт и при необходимости применяет правки. Не использовать голый `POST /run?async_mode=true` без скрипта — отчёт не сохранится. **Формулировка `goal`, параметры запроса и выбор endpoint** — [VICTORIA_TASK_FORMULATION.md](VICTORIA_TASK_FORMULATION.md). См. также VICTORIA_USAGE_GUIDE § «Куратор».

Важно (2026-06 hardening): для сложных задач скрипт куратора автоматически поднимает ожидание до 20 минут (`1200s`), а для очень сложных (полный ре-аудит «каждый пункт/все вкладки/production-ready») — до 60 минут (`3600s`), даже если задан меньший `--max-wait`; многострочные критические ТЗ с no-clarify маркерами склеиваются в одну цель (чтобы не рвать контекст на отдельные строки); формальный `success` с ответом-уточнением на задаче «без уточнений» засчитывается как `quality_gate_failed`.

**P0 (2026-06-04) — маршрут и таймауты (обязательно после pull):**

1. `victoria-agent`: `USE_VICTORIA_ENHANCED=true`, `VICTORIA_STALE_TASK_TIMEOUT_SEC=4200` (70 мин, после grace куратора), `VICTORIA_SWARM_GATHER_TIMEOUT_SEC=1200`.
2. Operational goals (`аудит` + `дашборд` / `без уточнений`) → **Enhanced**, in-process Swarm (3× ai_core) **отключён** (`task_detector.is_operational_execution_goal`).
3. Куратор: после основного `max_wait` — grace poll `CURATOR_POLL_GRACE_SEC=120`; ошибки cleanup → `victoria_stale:...` в отчёте.
4. Пересоздать контейнер после изменения compose:  
   `docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate`
5. Canary (одна вкладка):  
   `python scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks_dashboard_reaudit_one_tab.txt --async --max-wait 1200`  
   В логах Victoria: `USE_VICTORIA_ENHANCED: True`, `enhanced_solve` — **не** `Launching COMPLEX`.

Важно (2026-06 worker provisioning): контур исполнения использует **3 постоянных воркера** (`Виктория`, `Анна`, `Роман`) и **2 динамических слота** (`expert-worker-dynamic-1/2`). Оркестратор назначает задачи только live-экспертам по heartbeat; если нужный эксперт не live — пытается автоподнять динамический воркер, ждёт warmup, при неудаче делает fallback на следующего live-эксперта и пишет метрики (`spawn_attempts`, `spawn_success`, `fallback_count`, `stuck_agent_run_count`). Idle-динамика автоматически выключается по TTL.

Итого: куратор держит эталоны и базу знаний в актуальном состоянии; Victoria учится из этого контекста, а не из «урока» в каждый запрос.

---

## 1. Запустить прогон

**Быстрый (2 задачи):**

```bash
./scripts/run_curator.sh
```

**Полный (файл задач):**

```bash
./scripts/run_curator.sh --file scripts/curator_tasks.txt --async --max-wait 600
```

**Регулярный прогон (для cron/launchd):**

```bash
./scripts/run_curator_scheduled.sh
```

Использует `scripts/curator_tasks.txt` и `--max-wait 600`; переопределение: `CURATOR_TASKS_FILE`, `CURATOR_MAX_WAIT`, `VICTORIA_URL`.

- **launchd (macOS), полная автоматизация:** один раз выполнить `bash scripts/setup_curator_launchd.sh` — создаётся задание `com.atra.curator-scheduled`. Ежедневно в 9:00 запускается **полный автономный цикл**: `run_curator_autonomous.sh --full --sync-rag` (прогон → сравнение с эталонами → при расхождении задачи в БД → синхронизация эталонов в RAG). VICTORIA_URL и DATABASE_URL подхватываются из `$ROOT/.env`. Логи: `~/Library/Logs/atra-curator.log`.
- **Cron (Linux):** ежедневно в 9:00 — автономный цикл:  
  `0 9 * * * cd /path/to/atra-web-ide && ./scripts/run_curator_autonomous.sh --full --sync-rag >> docs/curator_reports/curator-cron.log 2>&1`  
  (в crontab при необходимости задать DATABASE_URL и VICTORIA_URL или положить их в .env в каталоге проекта.)
- **Только прогон без сравнения (старый вариант):** `./scripts/run_curator_scheduled.sh` — по-прежнему доступен при необходимости.

Требуется: Victoria доступна (`http://localhost:8010/health` → 200). При обрыве соединения (Connection reset by peer): до двух повторов всей задачи (всего до 3 попыток) и до 3 повторов каждого GET /run/status по одному task_id.

Отчёт: `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и `.md`.

**Почему прогон долгий:** Victoria выполняет каждую задачу в фоне (LLM: понимание цели, план, ответ). На Mac Studio одна задача обычно **1–5 мин**; 5 задач → до **~25 мин**. Куратор при `--async` опрашивает `/run/status` каждые 2.5 с и выводит прогресс раз в 15 с (`... ждём Victoria (status=..., осталось ~Xs)`). Если кажется, что «висит» — смотрите этот вывод; при отсутствии вывода проверьте, что Victoria на :8010 жива (`curl -s http://localhost:8010/health`).

**Память:** При высокой загрузке RAM (Ollama 25–35 ГБ + Docker + Python) возможны падения Python или connection reset. Перед полным прогоном по возможности выгрузите неиспользуемые модели Ollama (`ollama list`; при необходимости перезапуск Ollama освобождает память). Подробнее: [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md) §6.

**Быстрая проверка (2 задачи, до 6 мин):**

```bash
python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --quick
```

**Почему прогон мог прерваться по таймауту (причина):** Куратор при `--quick` даёт **на каждую задачу** до **180 с** (max_wait); 2 задачи выполняются **последовательно** → в худшем случае 180+180 = **6 мин** только на ожидание. Плюс холодный старт LLM (1–5 мин на первую задачу). Если скрипт запускается из среды с **ограничением времени выполнения** (CI, Cursor/IDE runner, cron с коротким таймаутом), процесс **убивается по истечении этого лимита** — не из-за «poll timeout» внутри куратора, а из-за внешнего kill. **Что делать:** запускать куратора без внешнего таймаута или с лимитом **не менее 8–10 мин** для `--quick` (лучше 10 мин с запасом на холодный старт); для полного прогона (5 задач) — не менее 25–30 мин. В Cursor/скриптах не задавать timeout меньше 600000 ms (10 мин) для быстрого прогона.

**После поднятия стека (Victoria + сервисы) и изменений в коде:** рекомендуется один раз прогнать быстрый прогон или сравнение с эталоном, чтобы проверить эталоны после правок (см. §3 «После изменений в коде Victoria»).

### 1.5. Куратор при деплое

После **деплоя** (например `docker-compose up -d` или выкат на сервер) один раз прогнать быстрый прогон куратора и сравнение с эталонами — проверка, что Victoria и эталоны в порядке после выката.

**Команда (рекомендуемая):**

```bash
./scripts/run_curator_post_deploy.sh
```

Скрипт запускает быстрый прогон (2 задачи) и сравнение по всем эталонам; код выхода 0/1 как у куратора.

**Альтернатива (то же вручную):**

```bash
./scripts/run_curator_and_compare.sh
```

**Требования:** Victoria доступна (например `http://localhost:8010/health` или ваш VICTORIA_URL); таймаут среды для скрипта **не менее 10 мин** (холодный старт LLM + 2 задачи). В CI или post-deploy hook задавать timeout ≥ 600 с (10 мин).

**Опционально:** в pipeline деплоя добавить шаг «после успешного поднятия сервисов — запустить run_curator_post_deploy.sh»; при падении — не откатывать деплой, а зафиксировать в FINDINGS и разобрать по чеклисту (§2).

### 1.6. Причина «Read timed out» и автозапуск Victoria

**Почему в отчёте куратора было «error» с текстом `Read timed out` (read timeout=30):** Victoria не успела ответить на первый запрос **POST /run** в течение 30 секунд. Возможные причины: (1) **Victoria не была запущена** — тогда скрипт раньше выходил по «Victoria недоступна» после проверки /health; (2) **Victoria была запущена, но при первом запросе долго «прогревалась»** (холодный старт LLM, загрузка модели) и не отдала 202 за 30 с; (3) Victoria перегружена или зависла.

**Что сделано, чтобы такого не было:**

- **Перед прогоном** (`run_curator_and_compare.sh`): шаг «0. Проверка Victoria». Если `GET ${VICTORIA_URL}/health` не отвечает — автоматически выполняется `docker-compose -f knowledge_os/docker-compose.yml up -d`, затем ожидание /health до **90 с**. Если за 90 с Victoria не поднялась — скрипт выходит с подсказкой запустить вручную или `bash scripts/system_auto_recovery.sh`.
- **Таймаут первого POST /run** в кураторе по умолчанию **300 с** (переменная `CURATOR_POST_RUN_TIMEOUT`): до ответа 202 Victoria выполняет стратегию и understand_goal (вызовы LLM), при холодном старте модели это может занять 3–5 мин. При необходимости увеличить до 400–600.
- **Повтор при таймауте:** при ошибке «timed out» куратор делает до двух повторов (как при обрыве соединения), с паузой 3 с.
- **Самовосстановление стека:** скрипт `scripts/system_auto_recovery.sh` проверяет Victoria (и Veronica, Ollama, MLX и др.); при недоступности Victoria перезапускает контейнер `victoria-agent` и ждёт /health. Можно запускать по расписанию (launchd) или вручную после сбоев.
- **OLLAMA_KEEP_ALIVE:** в `knowledge_os/docker-compose.yml` для victoria-agent по умолчанию 86400 (24 ч), чтобы модель оставалась в памяти после первого запроса и куратор не упирался в холодный старт. При необходимости задать в `.env`.
- **Прогрев при старте:** при `VICTORIA_WARMUP_ENABLED=true` (по умолчанию) Victoria прогревает в Ollama модели **VICTORIA_PLANNER_MODEL** и **VICTORIA_MODEL** (и опционально **VICTORIA_WARMUP_EXTRA_MODELS** через запятую); первый sync-запрос идёт быстрее. При **VICTORIA_WARMUP_BLOCK_STARTUP=true** сервер не принимает запросы до завершения прогрева — для стабильного первого sync.

**Если Victoria всё равно недоступна:** выполнить `docker-compose -f knowledge_os/docker-compose.yml up -d` (или `bash scripts/system_auto_recovery.sh` для полного восстановления), убедиться, что порт 8010 слушается и `curl -s http://localhost:8010/health` возвращает 200, затем снова запустить `./scripts/run_curator_and_compare.sh`.

**Если Victoria отвечает на /health, но куратор всё время получает «Read timed out»:** с внедрением «202 до стратегии» Victoria при async_mode=true возвращает 202 сразу; стратегия и understand_goal выполняются в фоне, поэтому долгое ожидание до 202 больше не должно возникать. При необходимости задать `CURATOR_POST_RUN_TIMEOUT=300` и таймаут среды ≥10 мин; прогрев при старте (VICTORIA_WARMUP_ENABLED) и OLLAMA_KEEP_ALIVE=86400 снижают холодный старт.

### 1.7. Victoria: рекомендации для production (стабильность, 2026-02-11)

- **Длительная обработка:** везде, где возможна долгая задача, использовать **асинхронный режим** (POST /run с `async_mode=true` → 202 + task_id, опрос GET /run/status/{task_id} до status=completed). Так клиент не упирается в таймаут соединения.
- **Быстрые ответы (health, простые запросы):** можно оставить синхронный режим; для стабильности задать **лёгкие модели**: `VICTORIA_PLANNER_MODEL=phi3.5:3.8b`, `VICTORIA_MODEL=phi3.5:3.8b`.
- **Первый запрос не холодный:** включить блокирующий прогрев: `VICTORIA_WARMUP_BLOCK_STARTUP=true` (по умолчанию в docker-compose).
- **Модель не выгружается между запросами:** `OLLAMA_KEEP_ALIVE=86400` (24 ч) — уже по умолчанию в docker-compose.
- **MLX отключён:** при `MLX_API_URL=disabled` невалидные URL отфильтрованы; используется только Ollama (react_agent, local_router). Ошибок «Request URL missing protocol» больше не возникает.

См. CHANGES_FROM_OTHER_CHATS §0.4et.

---

## 2. Разобрать отчёт по чеклисту

Открыть **docs/curator_reports/CURATOR_CHECKLIST.md** и проверить:

- Цепочка и маршрутизация
- Качество ответов (полнота, точность, формат)
- Соответствие эталонам из **docs/curator_reports/standards/**

Выводы записать в `FINDINGS_YYYY-MM-DD.md` или в отчёт `*_findings.md`.

**Сравнение с эталоном (скоринг «как я»):**

```bash
python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json --standard what_can_you_do
```

Опционально: `--standard greeting`, `--standard status_project`, `--standard list_files`, `--standard one_line_code` или `--standard-file путь/к/эталону.md`.

**При падении скоринга — пометка в FINDINGS (план «умнее быстрее» §4.1):** добавить `--write-findings`. Тогда при доле совпадений ниже порога (по умолчанию 0.5) в `docs/curator_reports/FINDINGS_YYYY-MM-DD.md` дописывается строка «Требуется дообучение RAG / правка эталона» по релевантным задачам. Порог: `--threshold 0.6` (0..1).

**Прогон + сравнение по всем эталонам (регулярная проверка, план «как я» п.3.1):**

```bash
./scripts/run_curator_and_compare.sh        # быстрый прогон (--quick), затем сравнение с status_project, greeting, what_can_you_do, list_files, one_line_code
./scripts/run_curator_and_compare.sh --full # полный прогон, затем то же сравнение
./scripts/run_curator_and_compare.sh --write-findings   # при падении скоринга дописывать в FINDINGS_YYYY-MM-DD.md (план «умнее быстрее» §4.1)
./scripts/run_curator_and_compare.sh --full --write-findings
```

Таймаут среды: для быстрого прогона не менее 10 мин, для полного — не менее 30 мин (см. §1 «Почему прогон мог прерваться по таймауту»).

---

## 3. Добавить эталоны в RAG (при необходимости)

```bash
DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os python3 scripts/curator_add_standard_to_knowledge.py
```

Скрипт добавляет в knowledge_nodes эталоны: что ты умеешь, привет, статус проекта, список файлов, одна строка кода. Идемпотентно (повторный запуск не дублирует). После правки **standards/status_project.md** обновить узел в RAG: `... curator_add_standard_to_knowledge.py --update-status`.

**Кандидаты в эталон (план «умнее быстрее» §4.1):** при лайке в чате (POST /api/feedback, score=1) инсайт сохраняется в knowledge_nodes с **metadata.suggested_standard=true**. Наставник/куратор может отбирать такие узлы (по домену или по запросу в БД) и при необходимости переносить в standards/ и запускать curator_add_standard_to_knowledge.

**При расхождении с эталоном:** доучить в RAG (скрипт выше), обновить файлы в `docs/curator_reports/standards/`. Для «какой статус проекта?» (0/3): сравнение `--standard status_project`; при обрезке/галлюцинации — проверить контекст enhanced, повторить прогон после дообучения. Новые типы запросов — добавлять эталоны в `standards/`, при необходимости расширить `curator_add_standard_to_knowledge.py`.

**Стабильность:** следить за Grafana (порт 3002), алерт deferred_to_human; при падениях MLX/Ollama — `./scripts/system_auto_recovery.sh`. См. WHATS_NOT_DONE.md «Действия сейчас».

**После изменений в коде Victoria (bridge или Enhanced):** контейнер использует образ — недостаточно только `restart`. Пересобрать образ и поднять контейнер заново:

```bash
docker compose -f knowledge_os/docker-compose.yml build victoria-agent
docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent
```

Трассировка маршрута «какой статус проекта?»: `python3 scripts/trace_status_project_route.py` (из корня репо). Перед/после правок в Victoria или Enhanced рекомендуется: `./scripts/run_all_system_tests.sh`; при необходимости — быстрый прогон куратора или сравнение с эталоном (см. [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §2 и пункт 38).

---

## 4. Veronica: таймауты и сбои «список файлов»

- **Таймаут делегирования:** Victoria ждёт ответ Veronica до **DELEGATE_VERONICA_TIMEOUT** (по умолчанию 90 с). При частых таймаутах на задаче «покажи список файлов» задать в окружении Victoria (например в `knowledge_os/docker-compose.yml` или `.env`): `DELEGATE_VERONICA_TIMEOUT=120` (или больше).
- **При сбоях «список файлов» (connection reset, error):** см. [curator_reports/CURATOR_LIST_FILES_FAILURES.md](curator_reports/CURATOR_LIST_FILES_FAILURES.md) — диагностика (логи Victoria, доступность Veronica), проверка Ollama/памяти, при стабильных сбоях — рассмотреть маршрут «список файлов» через Enhanced вместо Veronica (гипотеза в CURATOR_MENTOR_CAUSES §5).
- **При следующих сбоях:** (1) Увеличить DELEGATE_VERONICA_TIMEOUT до 120 с. (2) Проверить логи Victoria (поиск по «Veronica», «list_directory», «connection reset»). (3) Проверить доступность Veronica: `curl -s -X POST http://localhost:8011/run -H "Content-Type: application/json" -d '{"goal":"покажи файлы в корне"}'` — ответ должен прийти в разумное время (до таймаута).
- **Проверка Veronica:** `curl -s -X POST http://localhost:8011/run -H "Content-Type: application/json" -d '{"goal":"покажи файлы в корне"}'` (или ваш VERONICA_URL); ответ должен прийти в разумное время (до 90 с).

---

## 5. Операционные «секретики» (чтобы ничего не забыть)

| Что                                    | Где смотреть                      | Действие                                                                                                                         |
| -------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Один воркер на окружение**           | VERIFICATION §5, §3               | Перед и после деплоя проверять `docker ps`: только один контейнер воркера на окружение.                                          |
| **Перед правками в коде/конфиге**      | VERIFICATION §5                   | Определить затронутые компоненты; открыть §5 и выполнить пункты по ним (чат, воркер, Ollama/MLX, Victoria, Совет, БД, RAG).      |
| **Границы кода**                       | SRC_AND_KNOWLEDGE_OS_BOUNDARIES   | При правках в `src/` или `knowledge_os/app/` сверять границы; при общей логике — единый модуль.                                  |
| **Redis (atra-web-ide)**               | VERIFICATION §3, §5               | Контейнер **knowledge_os_redis**, порт хоста **6381**. Не использовать knowledge_redis и 6380 (atra).                            |
| **Изменения в маршрутизации Victoria** | VERIFICATION §5                   | Прогнать `pytest backend/app/tests/test_task_detector_chain.py -v`; при необходимости обновить VICTORIA_TASK_CHAIN_FULL §9.      |
| **Контракт Victoria**                  | VERIFICATION §5, п.21             | POST /run — body.goal (не prompt), project_context; при новых полях сверять с TaskRequest в victoria_server.                     |
| **Recovery по расписанию**             | VERIFICATION §5, ORCHESTRATOR_137 | Один раз: `bash scripts/setup_system_auto_recovery.sh`; при остановленных контейнерах использовать **up -d**, не только restart. |

---

## 6. Путь к автономности (без Cursor и внешних сайтов)

**Цель:** куратор должен работать полностью у вас — свои скрипты, своя Victoria, своя БД; без доступа к Cursor и без обращения к иностранным/внешним сайтам.

**Что уже не зависит от Cursor:**

- Все скрипты куратора обращаются только к **VICTORIA_URL** (localhost или ваш внутренний хост) и к локальной БД (DATABASE_URL). Никаких вызовов в Cursor или во внешние API.
- **Запуск по расписанию:** cron или launchd (`run_curator_scheduled.sh`, `setup_curator_launchd.sh`) — прогон и отчёт выполняются на вашей стороне.
- Victoria при ответах может работать только на **локальных моделях** (Ollama/MLX) и **локальной БД** — тогда и интернет для ответов не нужен (эмбеддинги и LLM — локально).

**Чего не хватает для полной автономности:**

- Сейчас **решение при расхождении с эталоном** (добавить в RAG, поправить эталон) принимает человек или Cursor-агент. В автономном режиме это нужно автоматизировать.

**Варианты «автономный куратор»:**

| Вариант                                  | Описание                                                                                                                                                                                            | Плюсы / минусы                                                                                  |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| **A. Обёртка-скрипт**                    | После `run_curator` → `curator_compare_to_standard`; при падении скоринга ниже порога автоматически вызывать `curator_add_standard_to_knowledge.py` (или только писать в FINDINGS). Запуск по cron. | Минимум изменений; риск «накачать» RAG шумом при ложных расхождениях.                           |
| **B. Задача в БД вместо правки вручную** | При расхождении создавать задачу в `tasks` (assignee_hint: Technical Writer или Victoria), чтобы «кто-то» в системе потом поправил эталон или RAG. Куратор только детектирует и ставит задачу.      | Не требует доверия к полной авто-правке RAG; логика «обнаружил → поставил задачу» универсальна. |
| **C. Сервис в Knowledge OS**             | Небольшой воркер/демон: по расписанию прогон → сравнение → при расхождении либо запись в RAG с логом, либо создание задачи в БД (как B).                                                            | Единая среда, мониторинг, логи; больше кода и поддержки.                                        |

**Рекомендация:** сначала **B** (при расхождении — создавать задачу в БД), при необходимости добавить осторожную авто-правку RAG (A) только для заранее выбранных эталонов и с порогом/лимитами.

**Реализовано «под ключ» (вариант B + запись в FINDINGS):**

- **Скрипт** `./scripts/run_curator_autonomous.sh` — один запуск: проверка Victoria → прогон куратора → сравнение по всем эталонам → при расхождении запись в FINDINGS и **создание задачи в таблице tasks** (metadata.assignee_hint: Technical Writer). Без Cursor: только VICTORIA_URL и при необходимости DATABASE_URL.
- **Флаги:** `--full` — полный прогон; `--sync-rag` — в конце выполнить `curator_add_standard_to_knowledge.py` (синхронизация эталонов в RAG, идемпотентно).
- **Сравнение с эталоном:** в `curator_compare_to_standard.py` добавлен флаг `--create-task-on-divergence`: при падении скоринга создаётся запись в tasks (нужен DATABASE_URL). Запуск по cron/launchd: `./scripts/run_curator_autonomous.sh` (таймаут среды ≥ 10 мин для быстрого, ≥ 30 мин для `--full`).

**Изолированная среда (без внешних сайтов):**

- `VICTORIA_URL` — внутренний хост (например `http://victoria-agent:8000` в Docker или `http://10.0.0.5:8010`).
- Модели и эмбеддинги — только Ollama/MLX на своих серверах; в конфиге Victoria/Knowledge OS не указывать внешние API для LLM/embeddings.
- Эталоны и скрипты — в своём репозитории; обновления репо — внутренний зеркал или копия без выхода в интернет.

**Полная автоматизация:** один раз настроить расписание — дальше всё идёт без участия человека (без Cursor):

- **macOS:** `bash scripts/setup_curator_launchd.sh` — ежедневно в 9:00 полный автономный цикл с созданием задач в БД и синхронизацией эталонов в RAG.
- **Linux:** добавить в crontab строку для `run_curator_autonomous.sh --full --sync-rag` (см. §1 выше).
  В обоих случаях в `.env` в каталоге проекта должны быть заданы VICTORIA_URL и DATABASE_URL (скрипт подхватывает их при запуске). Задачи по расхождениям попадают в БД; исполнитель (Victoria или человек) может править эталоны и RAG по задаче.

**После перезагрузки (чтобы всё работало без ручного запуска):**

- **Launchd (macOS):** задание загружается при входе пользователя в систему (LaunchAgents). После перезагрузки достаточно войти в учётную запись — к 9:00 куратор запустится сам. При необходимости проверить: `launchctl list | grep curator`.
- **Victoria и БД:** скрипт `run_curator_autonomous.sh` при отсутствии Victoria сам поднимает контейнеры (`docker-compose -f knowledge_os/docker-compose.yml up -d`) и ждёт /health до 90 с. Чтобы после перезагрузки Victoria и PostgreSQL были доступны до запуска куратора, включите автозапуск Docker (Docker Desktop → Settings → General → «Start Docker Desktop when you sign in») или настройте запуск стека при загрузке системы (cron @reboot или отдельный launchd для `docker-compose up -d`).
- **Итог:** после перезагрузки при входе в систему launchd уже загружен; в 9:00 куратор запустится; если Victoria не отвечает — скрипт попытается поднять контейнеры. Для полностью «руки прочь» после перезагрузки включите автозапуск Docker.

---

## 7. Ссылки

- План и роль: [VICTORIA_CURATOR_PLAN.md](VICTORIA_CURATOR_PLAN.md)
- Чеклист: [curator_reports/CURATOR_CHECKLIST.md](curator_reports/CURATOR_CHECKLIST.md)
- Индекс отчётов и эталонов: [curator_reports/INDEX.md](curator_reports/INDEX.md)
- **Куратор и наставник: причины с экспертами и мировыми практиками:** [curator_reports/CURATOR_MENTOR_CAUSES.md](curator_reports/CURATOR_MENTOR_CAUSES.md)
- Сбои «список файлов»: [curator_reports/CURATOR_LIST_FILES_FAILURES.md](curator_reports/CURATOR_LIST_FILES_FAILURES.md)
- Эталоны: [curator_reports/standards/](curator_reports/standards/)
- Следующие шаги: [NEXT_STEPS_CORPORATION.md](NEXT_STEPS_CORPORATION.md)
- Чеклист верификации: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §5 «При следующих изменениях».
- Автономность: §6 этого runbook (без Cursor и внешних сайтов).
