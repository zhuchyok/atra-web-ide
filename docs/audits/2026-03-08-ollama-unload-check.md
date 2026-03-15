# Проверка: почему Ollama не выгружает модели (2026-03-08)

**Запрос:** проверить сама, почему Ollama не выгружает модели.

---

## Результаты проверки

### 1. Что сейчас в Ollama

- **Загружена одна модель:** `victoria-wisdom-v3.5:latest` (~28 GB).
- **expires_at:** задан (например `2026-03-08T01:24:31+03:00`) — модель **не бессмертна**, Ollama выгрузит её по таймеру после последнего запроса.

**Вывод:** Ollama выгрузку по таймеру поддерживает; модель не висит с `keep_alive=-1` навсегда.

---

### 2. MLX

- **curl http://localhost:11435/health** → **200**.
- Пока MLX жив, политика для `victoria-wisdom-v3.5` в Ollama даёт **keep_alive=60** (1 мин), а не -1.

---

### 3. Переменные окружения

| Место                        | Значение                | Комментарий                                             |
| ---------------------------- | ----------------------- | ------------------------------------------------------- |
| **.env (корень)**            | `OLLAMA_KEEP_ALIVE=5m`  | Ожидаем 5 мин для общих моделей                         |
| **Контейнер victoria-agent** | `OLLAMA_KEEP_ALIVE=600` | 600 с = 10 мин; значение из дефолта compose, не из .env |

**Вывод:** В контейнер попадает дефолт **600** из `knowledge_os/docker-compose.yml` (`${OLLAMA_KEEP_ALIVE:-600}`), а не `5m` из корневого `.env`. Либо compose запускался из другой директории/без этого .env, либо контейнер не пересоздавался после смены .env.

---

### 4. Код: кто передаёт keep_alive

- **knowledge_os:** `local_router`, `executor`, `ai_core`, `semantic_cache`, `semantic_router` используют `get_keep_alive()` из `ollama_keep_alive_policy` или явно `keep_alive=0` (эмбеддинги).
- **src/agents/core/executor.py** (корень): свой `get_smart_keep_alive()` — не использует политику fallback (v3.5 при MLX down). Используется ли этот executor в контейнере Victoria — отдельно; основной путь через knowledge_os — через политику.

---

### 5. Как запущен Ollama

- Процесс: `/Applications/Ollama.app/Contents/Resources/ollama serve`.
- Переменную окружения процесса Ollama (OLLAMA_KEEP_ALIVE) прочитать не удалось (права/защита процесса).

---

## Рекомендации

1. **Чтобы контейнер использовал значение из .env:**  
   Запускать compose из корня репо, где лежит `.env` с `OLLAMA_KEEP_ALIVE=5m`, и пересоздать контейнер:

   ```bash
   cd /path/to/atra-web-ide
   docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate
   ```

   После этого проверить: `docker exec victoria-agent env | grep OLLAMA_KEEP_ALIVE`.

2. **Чтобы модели выгружались быстрее:**  
   В `.env` поставить `OLLAMA_KEEP_ALIVE=60` (1 мин) или `0` (сразу после ответа), затем пересоздать victoria-agent (см. выше). В политике для v3.5 при живом MLX уже стоит 60 с; env влияет на остальные модели и на дефолт.

3. **Проверка после изменений:**
   - `curl -s http://localhost:11434/api/ps` — смотреть `expires_at` у загруженных моделей.
   - Подождать 1–2 мин без запросов и снова вызвать `/api/ps` — список должен стать пустым или модель смениться.

---

## Итог

Ollama выгрузку по таймеру выполняет (expires_at задан). В контейнере Victoria реально используется `OLLAMA_KEEP_ALIVE=600`, а не `5m` из .env. Чтобы «Ollama выгружал модели» так, как ожидается: задать нужное значение в .env, запускать compose из корня и при смене .env пересоздавать victoria-agent.
