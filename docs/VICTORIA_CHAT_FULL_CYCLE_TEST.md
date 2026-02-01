# Полный цикл теста чата Victoria

## Назначение

Скрипт и конфиг для проверки **полного цикла** чата с Victoria: от принятия сообщения до ответа пользователю, в разных режимах (async и sync), с логированием каждого этапа и повторными прогонами при сбоях.

## Компоненты

- **Промпты:** `scripts/victoria_chat_cycle_test_prompts.json` — простой / средний / сложный запросы.
- **Тест-харнес:** `scripts/test_victoria_chat_full_cycle.py` — запуск сценариев, запись логов, анализ сбоев, повтор до успеха или лимита итераций.
- **Логи [VICTORIA_CYCLE]:** добавлены в:
  - `src/agents/bridge/victoria_server.py` — приём POST /run, 202, фоновая задача (start/completed/failed), GET /run/status, sync 200.
  - `backend/app/services/victoria.py` — клиент: отправка POST /run и ответ.
  - `knowledge_os/app/extended_thinking.py` — вход в _generate_response (выбор модели, LLM).

## Режимы

| Режим | Описание |
|-------|----------|
| **async** | POST /run?async_mode=true → 202 + task_id → опрос GET /run/status/{task_id} до completed/failed. |
| **sync** | POST /run без async_mode → ожидание 200 с телом (output). |

## Запуск

```bash
# Все сценарии (simple + medium + complex, async + sync), до 5 итераций при сбоях
python3 scripts/test_victoria_chat_full_cycle.py

# Только простой промпт, только async
python3 scripts/test_victoria_chat_full_cycle.py --prompt simple --mode async

# Увеличить лимит ожидания при async (сложный запрос может занимать 5–10 мин)
python3 scripts/test_victoria_chat_full_cycle.py --poll-max-wait 600 --max-iterations 10
```

Логи пишутся в `logs/victoria_chat_cycle_YYYYMMDD_HHMMSS.log`.

## Критерии успеха

- **Успех:** ответ не пустой, длина ≥ `expected_min_length` для данного промпта, статус success или есть output.
- **Сбой:** таймаут, пустой ответ, статус failed или ошибка клиента.

При сбое скрипт анализирует лог по известным паттернам (coroutine not awaited, 503, Timeout и т.д.) и выводит рекомендации; при следующей итерации тесты повторяются.

## Известные узкие места

- **Сложный промпт (complex):** анализ БЗ/оркестратор может выполняться 3–10 мин. Для него используйте `--poll-max-wait 600` (и при необходимости больше).
- **Таймаут sync:** клиент sync использует 300 с в `victoria_chat._do_request`; при долгих запросах может не хватить — тогда предпочтите async + poll.

## Где смотреть логи Victoria

На сервере Victoria все этапы цикла помечены `[VICTORIA_CYCLE]`:

```bash
docker logs victoria-agent 2>&1 | grep VICTORIA_CYCLE
```

Типичная последовательность при async: `accept POST /run` → `async 202 task_id=...` → `background start` → `background completed route=...` или `background failed`. При опросе: `GET /run/status/{task_id} status=completed`.
