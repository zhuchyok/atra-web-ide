# Без заглушек и обходных путей — что сделано по мировым практикам

Все исправления сделаны **без заглушек и без ухода в обходные пути**. Требования выполняются явно: миграции, зависимости, очереди и fallback.

---

## 1. Watchdog (hot-reload skills)

- **Заглушек нет:** watchdog добавлен в **requirements.txt** (`watchdog>=3.0.0`). Hot-reload включается при установленной зависимости.
- **Поведение:** при отсутствии watchdog выводится **предупреждение** (не скрыто через debug): «Установите: pip install watchdog (есть в requirements.txt)». Fallback — работа без hot-reload, без скрытия проблемы.
- **Что сделать:** `pip install -r knowledge_os/requirements.txt` — предупреждение исчезнет после установки.

---

## 2. Колонки организационной структуры (experts)

- **Заглушек нет:** добавлена **миграция** `knowledge_os/db/migrations/add_experts_organizational_columns.sql`: колонки `organizational_unit_id`, `is_manager`, `manages_unit_id` добавляются в таблицу `experts`.
- **Код:** в `organizational_structure.py` используется **только полный запрос** с этими колонками. Нет минимального запроса и тихого fallback при отсутствии колонок.
- **При отсутствии колонок:** выбрасывается **RuntimeError** с текстом: применить миграцию или один раз запустить Enhanced Orchestrator. Fallback-структура возвращается только при других ошибках (например, недоступность БД).
- **Что сделать:** применить миграцию один раз (см. раздел «Выполнение миграции и установки» ниже).

---

## 3. IntelligentModelRouter (prioritize_quality, classify_task, get_fallback)

- **Заглушек нет:** в роутере реализованы:
  - параметры `prioritize_quality` / `prioritize_speed` в `select_optimal_model`;
  - возврат тройки `(model_name, TaskCategory, confidence)`;
  - методы `classify_task(prompt, category)` и `get_fallback_models(model_name, task_category, max_fallbacks)`.
- **Вызовы:** `extended_thinking.py` и `local_router.py` используют новую сигнатуру и методы без обходных путей.

---

## 4. Отслеживание загрузки MLX/Ollama и очередь (rate limit)

- **Реализовано без заглушек:**
  - **Очередь запросов:** `knowledge_os/app/mlx_request_queue.py` — `MLXRequestQueue` с приоритетами (HIGH — чат, MEDIUM — Task Distribution). Запросы к MLX API ставятся в очередь, ограничивается число одновременных запросов (`max_concurrent`).
  - **Проверка загрузки MLX:** в `local_router.py` — `_is_mlx_overloaded()` по статистике очереди (`active_requests`, `queue_size`). В `react_agent.py` при простой задаче и перегрузке MLX (активных запросов >= max_concurrent или очередь > 3) **в список URL добавляется Ollama** и простые задачи идут на Ollama.
  - **Rate limit (429):** в `extended_thinking.py` и `react_agent.py` при ответе 429 от MLX в список пробных URL **добавляется Ollama** и запрос повторяется. В `react_agent.py` после 429 от MLX включается кэш на 60 с: следующие запросы сначала пробуют Ollama (меньше повторных 429).
- **Настройка MLX rate limit:** в `mlx_api_server.py` лимит задаётся через env: `MLX_RATE_LIMIT_MAX` (по умолчанию 150 запросов), `MLX_RATE_LIMIT_WINDOW` (по умолчанию 90 с). Так реже срабатывает 429.
- **Local router:** при перегрузке MLX (`_is_mlx_overloaded()`) в `local_router.py` первыми в списке узлов ставятся Ollama-узлы, затем MLX — запросы идут в Ollama, пока MLX перегружен.
- **Итог:** загрузка MLX отслеживается через очередь; при перегрузке или rate limit запросы автоматически переключаются на Ollama (очередь и fallback по мировым практикам).

---

## 5. Установка и миграция (что сделано автоматически и что сделать при наличии БД)

### Сделано автоматически в проекте

- **Виртуальное окружение:** в `knowledge_os/` создан `.venv`, в нём установлены все зависимости из `knowledge_os/requirements.txt`, в т.ч. **watchdog** — предупреждения про hot-reload исчезнут при запуске из этого venv.
- **Скрипт одной миграции:** `knowledge_os/scripts/apply_organizational_columns_migration.py` — применяет только `add_experts_organizational_columns.sql` (идемпотентно). Запуск:  
  `cd knowledge_os && .venv/bin/python scripts/apply_organizational_columns_migration.py`  
  (требуется доступная PostgreSQL по `DATABASE_URL` или дефолтному URL.)

### Установка зависимостей (если venv ещё не ставили)

**Один скрипт (рекомендуется):**

```bash
bash knowledge_os/scripts/setup_knowledge_os.sh
```

Скрипт создаёт `knowledge_os/.venv`, ставит зависимости (в т.ч. watchdog) и выводит инструкцию по миграции.

Локально вручную:

```bash
cd knowledge_os
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Через Docker: образ агентов уже собирается с зависимостями из `requirements.txt` (в т.ч. watchdog).

### Применение миграции (когда PostgreSQL доступна)

**Вариант A — Enhanced Orchestrator (рекомендуется):**  
Один раз запустить Enhanced Orchestrator; в Phase 0.5 он применит все миграции из `db/migrations/` (используется таблица `schema_migrations`, не зависит от `knowledge_nodes`/`domains`), включая `add_experts_organizational_columns.sql`.

**Вариант B — скрипт одной миграции:**

```bash
cd knowledge_os
export DATABASE_URL="postgresql://admin:secret@localhost:5432/knowledge_os"  # или ваш URL
.venv/bin/python scripts/apply_organizational_columns_migration.py
```

**Вариант C — вручную через psql:**

```bash
export DATABASE_URL="postgresql://admin:secret@localhost:5432/knowledge_os"  # или ваш URL
psql "$DATABASE_URL" -f knowledge_os/db/migrations/add_experts_organizational_columns.sql
```

После применения миграции ошибка «column organizational_unit_id does not exist» исчезнет; при забытой миграции вы получите явную ошибку с инструкцией, а не тихий fallback.

---

## Итог

| Что | Заглушки/обходы | Решение по мировым практикам |
|-----|------------------|------------------------------|
| Watchdog | Нет скрытия через debug | В requirements; при отсутствии — явное предупреждение |
| Колонки experts | Нет минимального запроса | Миграция + один полный запрос; при отсутствии колонок — RuntimeError с инструкцией |
| Роутер (prioritize_quality, classify_task, get_fallback) | Нет | Реализованы в IntelligentModelRouter и вызываются из extended_thinking/local_router |
| Загрузка MLX / rate limit | Нет | Очередь MLXRequestQueue + при перегрузке/429 добавление Ollama в список URL |

Всё сделано без заглушек и без ухода в обходные пути; поведение соответствует описанным практикам.
