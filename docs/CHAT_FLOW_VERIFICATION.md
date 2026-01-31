# Проверка логики чата (как задумано)

## Цепочка: от кнопки «Отправить» до отображения

### 1. Frontend (Chat.svelte + chat.js)

- **Отправка:** `handleSubmit()` → `sendMessage(content)`. Режим берётся из `chatMode` (agent | plan | ask).
- **Перед запросом:** добавляется сообщение пользователя, затем пустое сообщение ассистента с `steps: []`.
- **Запрос:** `POST /api/chat/stream` с телом `{ content, expert_name, use_victoria: true, mode }`.
- **Чтение SSE:** `response.body.getReader()` → цикл по чанкам, `buffer` для неполных строк, разбор только строк вида `data: {...}`.
- **Обработка событий:**
  - `type === 'step'` → `appendStep({ stepType, title, content, duration })` — шаг добавляется к **последнему** сообщению ассистента.
  - `type === 'chunk'` и `data.content` → `updateLastMessage(data.content)` — контент дописывается к последнему сообщению.
  - `type === 'error'` → `error.set(...)`, при пустом контенте последнее сообщение заменяется на текст ошибки.
  - `type === 'end'` → при пустом контенте последнего сообщения подставляется «Не удалось получить ответ».
  - `type === 'start'` → только лог.
- **После цикла:** `isStreaming.set(false)`, `isLoading.set(false)` в `finally`.

### 2. Backend (chat.py)

- **Роут:** `POST /api/chat/stream` → `StreamingResponse(sse_generator(...))`.
- **Вход:** `ChatMessage` с полями `content`, `expert_name`, `model`, `use_victoria`, `mode`.
- **Порядок в sse_generator:**
  1. Всегда: `yield start` (type: start).
  2. Если `use_victoria`:
     - **mode === 'plan':** один step «Составляю план», вызов `victoria.plan()`, стрим строк плана как `chunk`, затем `end`.
     - **mode === 'agent':** step thought → (опционально step exploration) → step action «Запрос к Victoria» → `victoria.run()` → при успехе step «Генерация ответа» + стрим chunk'ов текста → `end`; при ошибке step «Запасной вариант» + MLX fallback + chunk'и → `end`.
     - **mode === 'ask':** step «Быстрый ответ» → MLX без Victoria → chunk'и → `end`.
  3. После каждого `yield` step — `await asyncio.sleep(0.05)` для сброса буфера.
- **Формат SSE:** строка `data: {JSON}\n\n`, в JSON — `type`, для step ещё `stepType`, `title`, `content`, `duration`, для chunk — `content`.

### 3. Отображение (Chat.svelte)

- **Режимы:** переключатель Agent / Plan / Ask привязан к `chatMode`; при отправке в body уходит текущий `chatMode`.
- **Панель шагов:** показывается при `$isStreaming` и у последнего сообщения `lastMessage.steps.length > 0`; шаги из `lastMessage.steps` с анимацией.
- **В каждом сообщении ассистента:** если есть `message.steps`, над контентом рисуется вертикальная линия и шаги (thought/exploration/action) с точками.
- **Контент:** для ассистента — `renderMarkdown(message.content)`; при пустом контенте — «Агент думает» + точки.
- **Мигающий курсор:** только у сообщения, которое сейчас стримится: `isStreamingLast && message.id === lastMessage.id`.
- **«Агент работает…»:** блок под сообщениями при `$isStreaming`.

### 4. Что проверить вручную

1. **Режим Agent:** отправить сообщение → должны по очереди появиться шаги (Анализ запроса, при наличии эксперта — Эксперт найден, Запрос к Victoria Agent, Генерация ответа), затем поток текста и мигающий курсор в конце; по завершении — курсор исчезает.
2. **Режим Plan:** отправить задачу → один шаг «Составляю план», затем текст плана по строкам.
3. **Режим Ask:** отправить вопрос → шаг «Быстрый ответ», затем текст от MLX (если MLX доступен).
4. **Ошибка:** при недоступной Victoria и недоступном MLX — шаг «Запасной вариант» и сообщение об ошибке или fallback-текст.
5. **Курсор:** мигает только в последнем (стримящемся) сообщении, не в старых.

### 5. Известные нюансы

- В Docker фронт и бэкенд — разные порты; для запросов к `/api/*` нужен прокси или один entrypoint (например, nginx), иначе в браузере запросы идут на порт фронта и 404.
- `chunk` с пустым `content` не вызывают `updateLastMessage` — так и задумано.
- Пустые строки в плане (режим plan) не стримятся, т.к. в бэкенде `if line.strip()` — при необходимости можно убрать и слать все строки.
- **Шаги не видны:** убедитесь, что бэкенд **перезапущен** после правок в `chat.py` (иначе на 8080 может работать старый процесс без step). Фронт всегда шлёт `use_victoria: true` и `mode`. Проверка после перезапуска:
  ```bash
  curl -s -N -X POST http://localhost:8080/api/chat/stream \
    -H "Content-Type: application/json" \
    -d '{"content":"тест","expert_name":"Виктория","use_victoria":true,"mode":"agent"}' | head -20
  ```
  В выводе до `"type": "chunk"` должны быть строки `"type": "step"` (Анализ запроса, Запрос к Victoria Agent и т.д.). После каждого step бэкенд шлёт SSE-комментарий `: \n\n` для сброса буфера.
