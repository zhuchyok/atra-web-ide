# Victoria / Veronica — как продолжить

## В чём была путаница

Мы зацикливались: скрипты с таймаутами, фоновый запуск, разные compose — сложно и ненадёжно. **На Mac Studio контейнеры уже могут быть запущены** (Docker Desktop → Containers: victoria_agen, veronica_age на 8010/8011).

## Решение: один сценарий

### 1. Проверить, работают ли агенты

```bash
cd /path/to/atra
bash scripts/migration/verify_agents.sh
```

Если **«Все проверки пройдены»** — ничего не трогаем. Victoria и Veronica в порядке.

**Всё сам (проверка + подъём + verify):**  
`bash scripts/migration/do_all_and_verify.sh` — лог: `~/migration/do_all_verify.log`. Запускать в **терминале на Mac Studio** (не из CI/автоматизации), иначе `docker` может зависать.

---

### 2. Если verify падает — поднять вручную

**Шаг А.** Убедиться, что Docker Desktop запущен.

**Шаг Б.** В корне репо (рядом с `knowledge_os/`):

```bash
# стек (db, api, worker)
docker-compose -f knowledge_os/docker-compose.yml up -d db api worker

# подождать 1–2 минуты, затем агенты
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent
```

**Шаг В.** Подождать ~30 с, снова проверить:

```bash
bash scripts/migration/verify_agents.sh
```

---

### 3. Если агенты уже запущены в другом compose (например «atra»)

На Mac Studio может быть отдельный проект **atra** со своими контейнерами (victoria_agen, veronica_age). Тогда:

- Проверка: `curl -s http://localhost:8010/health` и `http://localhost:8011/health`
- Логи: `docker logs victoria_agen` (или `victoria-agent` — смотри точное имя в Docker Desktop)

Если `/health` отдаёт 200 — агенты работают, ничего перезапускать не нужно.

---

### 4. Остановиться и не усложнять

- Не добавлять новые таймауты, фоновые циклы и обходные скрипты.
- Одна проверка: `verify_agents.sh`.
- Один способ поднять: три команды выше (compose up db/api/worker, потом up агентов, потом verify).

---

### 5. Логи при сбое

```bash
docker logs victoria-agent    # или victoria_agen
docker logs veronica-agent   # или veronica_age
```

MLX/Ollama должен быть на **localhost:11434**; агенты ходят в `host.docker.internal:11434`.
