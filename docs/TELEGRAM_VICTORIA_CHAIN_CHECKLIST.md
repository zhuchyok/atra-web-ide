# Цепочка Victoria → эксперты: нестабильности и чеклист проверки

**Дата:** 2026-02-01  
**Контекст:** Задачи на код из Telegram/Cursor дают: «Эксперт Veronica не найден в БД», таймаут, смешанный/битый текст. Нужно проверять конфиг и доступность агентов на стороне VictoriaATRA / Mac Studio.

---

## Откуда берутся ошибки

| Симптом | Источник в коде | Причина |
|--------|------------------|--------|
| **«Эксперт Veronica не найден в БД»** | `knowledge_os/app/task_distribution_system_complete.py` (стр. ~250–252): `assignment.result = f"Эксперт '{assignment.employee_name}' не найден в БД"` | В план/assignments попадает имя «Veronica» (латиница), а в БД эксперт — «Вероника» (кириллица). Исправление: `_get_expert_by_name` использует `resolve_expert_name_for_db` и fallback по роли «Local Developer». **Нужно:** на сервере VictoriaATRA/Mac Studio должен быть задеплоен актуальный код (с этим фиксом) и перезапущен victoria-agent. |
| **«Таймаут: задача заняла слишком много времени»** | `src/agents/bridge/victoria_mcp_server.py`: при `httpx.TimeoutException` возвращается сообщение с указанием лимита. Таймаут клиента MCP задаётся **VICTORIA_MCP_RUN_TIMEOUT_SEC** (по умолчанию **600 с = 10 мин**; раньше было 300 с). | Задачи на код (оркестратор → эксперты → Victoria Enhanced) часто дольше 5 минут. Увеличьте `VICTORIA_MCP_RUN_TIMEOUT_SEC` при необходимости. |
| **Таймаут в Telegram** | `src/agents/bridge/victoria_telegram_bot.py`: при `result is None` (в т.ч. таймаут) пользователь видит: «❌ Не удалось выполнить задачу. Таймаут выполнения (до N мин)». Таймаут опроса: **VICTORIA_POLL_TIMEOUT_SEC** (по умолчанию 900 с = 15 мин). | Victoria не успевает ответить за 15 мин (тяжёлые модели, цепочка экспертов). |
| **Смешанный/битый текст** | Модель возвращает «мусор» или внутренние рассуждения (finish без output, смешение языков). В коде есть фильтры (`_strip_internal_monologue` в victoria_server, проверки в victoria_enhanced), но не все пути ими покрыты. | LLM иногда выдаёт нестабильный вывод; часть ответов не очищается перед отправкой пользователю. |

---

## Чеклист: конфиг и доступность (VictoriaATRA / Mac Studio)

### 1. Агенты и БД

- [ ] **victoria-agent** запущен и здоров: `curl -s http://localhost:8010/health` → 200.
- [ ] **veronica-agent** запущен: `curl -s http://localhost:8011/health` → 200 (если запросы идут в Veronica).
- [ ] **PostgreSQL (knowledge_postgres)** доступна для Victoria: в контейнере victoria-agent переменная `DATABASE_URL` указывает на работающую БД.
- [ ] В таблице `experts` есть эксперт с именем **«Вероника»** (кириллица) и ролью, содержащей «Local Developer». Проверка:  
  `SELECT name, role FROM experts WHERE name = 'Вероника' OR role ILIKE '%Local Developer%';`

### 2. Актуальность кода

- [ ] На сервере подтянут репозиторий с фиксом «Veronica → Вероника» (resolve_expert_name_for_db, fallback по роли в `task_distribution_system_complete._get_expert_by_name`).
- [ ] После обновления кода **перезапущен victoria-agent** (и при необходимости veronica-agent), чтобы подхватить изменения.

### 3. Таймауты

- [ ] **MCP (VictoriaATRA):** таймаут задаётся переменной **VICTORIA_MCP_RUN_TIMEOUT_SEC** (по умолчанию 600 с = 10 мин). Для очень длинных задач увеличьте в окружении (например 900 или 1200).
- [ ] **Telegram-бот:** `VICTORIA_POLL_TIMEOUT_SEC` (по умолчанию 900). При необходимости увеличить в окружении запуска бота.
- [ ] **Backend → Victoria:** в `backend` используется `victoria_timeout` (например 600 с); при длинных задачах можно увеличить в конфиге.

### 4. Переменные окружения (Victoria / бот / MCP)

- [ ] **Victoria:** `PREFER_EXPERTS_FIRST=true` (по умолчанию), чтобы задачи на код шли в enhanced (оркестратор + эксперты), а не сразу в Veronica.
- [ ] **Victoria:** `USE_VICTORIA_ENHANCED=true`, `ORCHESTRATION_V2_ENABLED=true` (если используется оркестратор V2).
- [ ] **Telegram-бот:** `VICTORIA_URL` указывает на рабочий адрес Victoria (например `http://localhost:8010` или адрес Mac Studio).
- [ ] **MCP:** `VICTORIA_URL` в окружении victoria_mcp_server указывает на тот же рабочий адрес Victoria.

### 5. Сеть и доступность

- [ ] Если Telegram-бот или Cursor работают не на Mac Studio: туннели/порты 8010 (и при необходимости 8011, 8012) проброшены и доступны с машины, где запущен бот/Cursor.
- [ ] Нет блокировок файрволом для портов 8010, 8011, 8012 между клиентом и сервером Victoria.

---

## Рекомендации по стабилизации

1. **Убедиться в деплое фикса Veronica:** на всех инстансах, где крутится Victoria (Mac Studio, сервер VictoriaATRA), должен быть код с `resolve_expert_name_for_db` и fallback по роли в `_get_expert_by_name`, и перезапущен victoria-agent.
2. **Таймаут MCP:** уже вынесен в **VICTORIA_MCP_RUN_TIMEOUT_SEC** (по умолчанию 600 с). При необходимости увеличить в окружении запуска MCP-сервера.
3. **Проверять логи Victoria при «Эксперт не найден»:** по логам victoria-agent убедиться, что вызывается именно `_get_expert_by_name` с резолвом имени и fallback по роли; при необходимости добавить логирование `assignment.employee_name` и результата резолва.
4. **Очистка вывода:** убедиться, что все пути ответа (в т.ч. через оркестратор и Victoria Enhanced) проходят через нормализацию/очистку от внутренних рассуждений и битого текста перед отправкой в Telegram/Cursor.

---

## Где что править в коде (справка)

| Что | Файл |
|-----|------|
| Резолв «Veronica» → «Вероника», fallback по роли | `knowledge_os/app/task_distribution_system_complete.py` (`_get_expert_by_name`), `knowledge_os/app/expert_aliases.py` |
| Таймаут MCP victoria_run | `src/agents/bridge/victoria_mcp_server.py`: переменная **VICTORIA_MCP_RUN_TIMEOUT_SEC** (по умолчанию 600) |
| Таймаут Telegram-опроса Victoria | `src/agents/bridge/victoria_telegram_bot.py` (`VICTORIA_POLL_TIMEOUT_SEC`) |
| Сообщение пользователю при таймауте в Telegram | `src/agents/bridge/victoria_telegram_bot.py` (блок «Не удалось выполнить задачу», стр. ~702–710) |
