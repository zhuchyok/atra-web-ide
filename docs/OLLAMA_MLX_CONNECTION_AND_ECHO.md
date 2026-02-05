# Подключение к Ollama и MLX: точки входа и причины зависаний/эхо

Документ для проверки параметров серверов Ollama/MLX и устранения зависаний и эхо-ответов. Рекомендации Backend (Игорь), SRE (Елена).

---

## 1. Где задаются URL Ollama и MLX

| Место | Переменные | Поведение |
|-------|------------|-----------|
| **docker-compose** (knowledge_os, backend) | `OLLAMA_BASE_URL`, `OLLAMA_API_URL`, `SERVER_LLM_URL`, `MLX_API_URL` | Передаются в контейнер; должны использоваться приложением. |
| **LocalAIRouter** (`knowledge_os/app/local_router.py`) | `OLLAMA_API_URL`, `OLLAMA_BASE_URL`, `MLX_API_URL` | Формирует `self.nodes` (узлы для запросов к LLM). **Раньше в Docker игнорировал env** — исправлено: сначала env, иначе `host.docker.internal` в Docker, `localhost` локально. |
| **_refresh_available_models** (тот же файл) | `MLX_API_URL`, `OLLAMA_API_URL` | Сканирование списка моделей через `get_available_models(mlx_url, ollama_url)`. |
| **available_models_scanner** | env в `_default_ollama_url()` / `_default_mlx_url()` | При вызове `scan_and_select_models()` без аргументов используются env + логика Docker. |

Итог: везде, где мы подключаемся к Ollama/MLX, URL берутся из env с fallback на `host.docker.internal` (Docker) или `localhost`. Неверный или не заданный URL → таймауты, пустые ответы, зависания.

---

## 2. Сканер доступных моделей

- **Файл:** `knowledge_os/app/available_models_scanner.py`
- **Функции:** `_fetch_ollama_models(ollama_url)`, `_fetch_mlx_models(mlx_url)`, `get_available_models(mlx_url, ollama_url)`, `scan_and_select_models(mlx_url=None, ollama_url=None)`.
- **Таймаут:** 5 сек на запрос к `/api/tags`.
- **Кэш:** TTL 120 сек; при истечении — повторное сканирование.

Если URL неверный (например `localhost` из контейнера), сканер вернёт пустые списки → используются fallback-модели из констант. Запрос к LLM тогда идёт на тот же (неверный) URL → соединение/таймаут. Проверка: в логах «Сканирование моделей: MLX=0, Ollama=0» при работающих серверах на хосте — значит URL не доходит до хоста (проверить env и `host.docker.internal`).

---

## 3. Почему зависают задачи (сводка)

1. **Блокировка event loop** — синхронное I/O (например чтение файлов) в async-коде → heartbeats не бегут → задача считается зависшей. Решение: `run_in_executor` для тяжёлого I/O.
2. **Нехватка соединений в пуле БД** — мало соединений при многих задачах и heartbeats → heartbeats не обновляют `updated_at`. Решение: пул `max(15, MAX_CONCURRENT + 8)`.
3. **Поздний сброс зависших** — раньше 1 ч → мало pending. Решение: `SMART_WORKER_STUCK_MINUTES=15`.
4. **Неверные URL Ollama/MLX** — в Docker env не использовался → запросы на неверный хост → таймауты/зависания. Решение: везде использовать env (LocalAIRouter, сканер).

Подробнее: [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md).

---

## 4. Почему Victoria возвращает ваш же текст (эхо)

**Симптом:** В телеграме (или в чате) в ответ приходит ваш запрос целиком или в начале ответа.

**Причины:** Модель или сервер иногда возвращает промпт как ответ (эхо). Либо неверный endpoint/формат запроса.

**Что сделано:** В `local_router.run_local_llm()` добавлена проверка `_is_echo_response(result, prompt)`: если ответ совпадает с промптом или является его началом (короткий ответ) — ответ не считается успешным, пробуем следующий узел (Ollama/MLX) или возвращаем `None` (fallback в облако/ошибка).

**Что проверить:** В docker-compose для victoria-agent заданы `OLLAMA_API_URL` и `MLX_API_URL` на нужный хост (например `http://host.docker.internal:11434`). После правок перезапустить контейнер Victoria.

---

## 5. Чеклист при проблемах с Ollama/MLX

| № | Проверка | Действие |
|---|----------|----------|
| 1 | URL в Docker | В контейнере: `echo $OLLAMA_API_URL $MLX_API_URL` — должны быть заданы и доступны с хоста (например `host.docker.internal:11434/11435`). |
| 2 | Доступность с контейнера | Из контейнера: `curl -s http://host.docker.internal:11434/api/tags` (и 11435 для MLX) — ответ 200 и список моделей. |
| 3 | Логи сканера | В логах Victoria/воркера: «Сканирование моделей: MLX=N, Ollama=M» — при N=0, M=0 при работающих серверах проверить URL и сеть. |
| 4 | Эхо | Если ответ = ваш текст — обновить код (пункт 18 чеклиста), перезапустить Victoria; убедиться, что запросы идут на правильный хост и модель. |

---

## 6. При следующих изменениях

- **Новый код, обращающийся к Ollama/MLX:** брать URL из env (`OLLAMA_API_URL`, `OLLAMA_BASE_URL`, `MLX_API_URL`); в Docker при отсутствии env использовать `host.docker.internal`, локально — `localhost`. Не хардкодить только `localhost` в коде, который может выполняться в контейнере.
- **Новая логика ответа LLM:** при возврате ответа пользователю проверять эхо (ответ = промпт) и не отдавать его как успешный результат; при необходимости пробовать следующий узел или возвращать ошибку.

---

*Документ согласован с рекомендациями Backend (Игорь) и SRE (Елена). См. также [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) (пункты 17–18), [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md).*
