# Почему не видно обучение, гипотезы, дебаты и новые задачи

## Откуда берутся данные

| Что видно в дашборде                    | Источник данных                                                         | Кто заполняет                                               | Когда запускается                                        |
| --------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------------- |
| **Обучение** (вкладка «🎓 Академия ИИ») | Таблица `expert_learning_logs`                                          | `nightly_learner.py`                                        | **1 раз в сутки** по cron: **6:00 МСК** (3:00 UTC)       |
| **Дебаты** (там же)                     | Таблица `expert_discussions`                                            | `nightly_learner.py` (initiate_debate)                      | **1 раз в сутки** в том же цикле (6:00 МСК)              |
| **Гипотезы** (кросс-доменные)           | Таблица `knowledge_nodes` (content как «🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА: …») | `enhanced_orchestrator.py`                                  | **Каждые 5 минут** по cron                               |
| **Метрики гипотез Singularity 9.0**     | A/B тестер (модуль singularity_9_ab_tester)                             | Дашборд запрашивает метрики                                 | При открытии вкладки                                     |
| **Новые задачи**                        | Таблица `tasks`                                                         | `enhanced_orchestrator.py`, worker, дашборд, разведка и др. | Оркестратор — **каждые 5 мин**; остальное — по действиям |

---

## Почему может быть пусто

### 0. Контейнеры оркестратора или Nightly Learner остановились и не перезапустились (Docker)

**Причина (устранена 2026-02-08):** Задачи и обучение создают контейнеры **knowledge_os_orchestrator** и **knowledge_nightly**. Если контейнер упал (OOM, исключение, перезагрузка без полного `up -d`):

- **Раньше:** скрипт самовосстановления при обнаружении «не запущенных» контейнеров делал `docker-compose restart`. Команда **restart** перезапускает только **уже работающие** контейнеры и **не поднимает** остановленные — поэтому упавший knowledge_nightly или knowledge_os_orchestrator так и оставались выключенными.
- Контроль (проверка здоровья) был только у Victoria и Veronica; оркестратор и Nightly Learner в цикле восстановления явно не проверялись и не поднимались по имени.
- Самовосстановление запускается при загрузке системы (launchd) и вручную; при падении контейнера в середине дня до следующего запуска скрипта никто перезапуск не выполнял.

**Что сделано:**

1. **scripts/system_auto_recovery.sh:** при наличии остановленных контейнеров Knowledge OS выполняется **`up -d`** (а не `restart`), чтобы поднять все сервисы, включая упавшие. Добавлена явная проверка: если **knowledge_nightly** или **knowledge_os_orchestrator** не в `docker ps`, выполняется `up -d knowledge_nightly` и `up -d knowledge_os_orchestrator`.
2. **scripts/check_and_start_containers.sh:** после общего `up -d` добавлена явная проверка и подъём **knowledge_nightly** и **knowledge_os_orchestrator**, если они не запущены.
3. **scripts/verify_mac_studio_self_recovery.sh:** уже содержал проверку этих контейнеров и подсказку `up -d`; теперь восстановление дублируется в основном цикле system_auto_recovery.

**Рекомендация:** Один раз настроить периодический запуск самовосстановления (например, раз в час через launchd), чтобы упавшие контейнеры поднимались без ожидания перезагрузки. Либо запускать вручную после сбоя: `bash scripts/system_auto_recovery.sh` или `bash scripts/check_and_start_containers.sh`.

**Проверка, что оркестратор и Nightly Learner работают:**

```bash
docker ps --format '{{.Names}}' | grep -E 'knowledge_nightly|knowledge_os_orchestrator'
# Ожидаются две строки: knowledge_nightly, knowledge_os_orchestrator
```

### 1. Cron не настроен

Оркестратор и Nightly Learner запускаются **только по cron**. Если его не настраивали, они не запускаются.

**Что сделать один раз:**

```bash
cd /Users/bikos/Documents/atra-web-ide
bash scripts/ensure_autonomous_systems.sh
```

После этого в crontab появится:

- **Enhanced Orchestrator** — каждые **5 минут** (`*/5 * * * *`), команда в контейнере `victoria-agent`.
- **Nightly Learner** — **раз в сутки в 6:00 МСК** (`0 3 * * *` UTC), тоже через `victoria-agent`.

Проверка:

```bash
crontab -l | grep -E "enhanced_orchestrator|nightly_learner"
```

**Важно:** в cron должен использоваться **полный путь к docker** (`/usr/local/bin/docker`), иначе при запуске по расписанию будет ошибка `docker: command not found`. Скрипт `ensure_autonomous_systems.sh` это учитывает. Если cron настраивали вручную, исправьте:

```bash
crontab -l | sed 's| docker exec| /usr/local/bin/docker exec|g' | crontab -
```

Оркестратор в cron должен запускать **файл**, а не `python3 -c 'from enhanced_orchestrator import ...'`:

- Правильно: `victoria-agent python3 /app/knowledge_os/app/enhanced_orchestrator.py`
- Неправильно: `python3 -c '... from enhanced_orchestrator import ...'` (в контейнере модуль — `app.enhanced_orchestrator`).

### 2. Контейнер Victoria не запущен

Cron выполняет:

```bash
docker exec ... victoria-agent python3 /app/knowledge_os/app/enhanced_orchestrator.py
docker exec ... victoria-agent python3 /app/knowledge_os/app/nightly_learner.py
```

Если контейнер **victoria-agent** не запущен в момент срабатывания cron, команды падают — обучение, дебаты и гипотезы не появятся.

**Проверка и запуск:**

```bash
docker ps | grep victoria-agent
# если нет:
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
```

Рекомендуется один раз настроить автопроверки (тогда при падении Victoria её поднимут):

```bash
bash scripts/setup_system_auto_recovery.sh
```

### 3. Таблица `expert_learning_logs` отсутствовала

Если миграции для этой таблицы не применялись, `nightly_learner.py` при записи логов обучения падал с ошибкой, и в дашборде в «Академия ИИ» ничего не было.

**Что сделано:** добавлена миграция `knowledge_os/db/migrations/add_expert_learning_logs.sql`.

**Применить вручную (если БД уже поднята):**

```bash
psql "$DATABASE_URL" -f knowledge_os/db/migrations/add_expert_learning_logs.sql
# или, из корня проекта:
psql "postgresql://admin:secret@localhost:5432/knowledge_os" -f knowledge_os/db/migrations/add_expert_learning_logs.sql
```

### 4. Nightly Learner запускается только в 6:00 МСК

Обучение и дебаты обновляются **раз в сутки**. Если смотрели дашборд до первого запуска или в другой час — записей ещё не будет. После первого успешного прогона в 6:00 МСК появятся строки в «Академия ИИ».

### 5. Оркестратор создаёт гипотезы и задачи не при каждом запуске

Гипотезы и авто-задачи создаются по логике (приоритеты, домены, доступные знания). Поэтому «каждые 5 минут» — это **запуск скрипта**, а не гарантированно новая гипотеза/задача каждый раз. Если данных мало или условия не выполняются, записей может быть мало.

---

## Быстрая проверка (всё ли готово)

1. **Cron:**

   ```bash
   crontab -l
   ```

   Должны быть строки с `enhanced_orchestrator` и `nightly_learner`.

2. **Victoria:**

   ```bash
   curl -s http://localhost:8010/health
   ```

   Ожидается ответ с `"agent":"Виктория"` (или аналог).

3. **Таблица логов обучения:**

   ```bash
   psql "postgresql://admin:secret@localhost:5432/knowledge_os" -c "\dt expert_learning_logs"
   ```

   Таблица должна существовать.

4. **Логи оркестратора и обучения (если cron уже срабатывал):**

   ```bash
   tail -100 /tmp/orchestrator.log
   tail -100 /tmp/nightly_learner.log
   ```

5. **Ручной однократный запуск (для проверки без ожидания cron):**

   ```bash
   docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os victoria-agent python3 /app/knowledge_os/app/enhanced_orchestrator.py
   docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os victoria-agent python3 /app/knowledge_os/app/nightly_learner.py
   ```

   После успешного выполнения в дашборде должны появиться/обновиться обучение, дебаты и, при выполнении условий, гипотезы и задачи.

---

## Где в дашборде смотреть

- **Обучение и дебаты:** вкладка **«🎓 Академия ИИ и Дебаты»** (колонки «Обучение» и «Дебаты»).
- **Задачи:** вкладка **«🛠️ Автономные Задачи и Оркестрация»**.
- **Гипотезы Singularity 9.0:** блок метрик Singularity 9.0 (A/B тесты гипотез).
- **Кросс-доменные гипотезы:** хранятся в `knowledge_nodes` с текстом «🔬 КРОСС-ДОМЕННАЯ ГИПОТЕЗА»; при необходимости можно добавить отдельный вид в дашборде.

Если после выполнения шагов выше данные по-прежнему не появляются, стоит посмотреть полный вывод команд выше и логи `orchestrator.log` / `nightly_learner.log` на ошибки.
