# Анализ интеграции Clawdbot-подхода: Telegram + Terminal + автономный агент

## Текущая архитектура

### 1. Потоки выполнения

| Канал | Куда идёт | Инструменты | write_file |
|-------|-----------|-------------|------------|
| **Telegram** | Victoria `/run` → Victoria Enhanced или Base | Base: read, run_terminal_cmd, ssh, list. Enhanced: + create_file, write_file | ✅ в ReActAgent, ❌ без бэкапа и approval |
| **Web IDE Chat** | Victoria (agent) или RAG (ask) | То же | ✅ в ReActAgent |
| **Terminal** | PTY WebSocket — пользователь вводит команды напрямую | Нет агента | — |

### 2. Где реализован write_file

- **knowledge_os/app/react_agent.py** (стр. 782–813): `create_file` / `write_file` — прямая запись в файл, без бэкапа и подтверждения.
- **victoria_server** (atra-web-ide): использует только Base Agent с `read_file`, `run_terminal_cmd`, `ssh_run`, `list_directory` — **write_file отсутствует**.
- **SystemTools** (atra-web-ide): есть `apply_patch`, нет `write_file`.

### 3. Victoria Enhanced vs Base

- **Enhanced** (USE_VICTORIA_ENHANCED=true): ReActAgent с create_file/write_file, поиск в БЗ.
- **Base**: OllamaExecutor, без записи файлов.
- Telegram и Chat используют один и тот же `/run`; выбор Enhanced/Base — по `detect_task_type`.

---

## Что уже есть (из плана Clawdbot)

| Компонент | Статус |
|-----------|--------|
| Бэкапы перед записью | ✅ SafeFileWriter (Фаза 1) |
| Human-in-the-loop (approval) | ❌ |
| Рефлексия / перепланирование | ⚠️ частично (ReAct loop) |
| Валидация команд | ✅ `SystemTools._validate_command_safety` |
| Песочница | ❌ (команды выполняются напрямую) |

---

## Рекомендуемая стратегия

### Фаза 1: Безопасная запись (приоритет)

**Цель:** Бэкап и ограничение пути перед записью.

**Где менять:** `knowledge_os/app/react_agent.py` — в обработке `create_file`/`write_file`.

**План:**

1. Добавить `FileWriter` в `knowledge_os/app/` или `src/tools/`:
   - `workspace_root` из `WORKSPACE_ROOT` или `project_context`
   - бэкап в `.agent_backups/` перед перезаписью
   - проверка пути внутри workspace (защита от `../../../etc/passwd`)

2. Подменить прямой `open(file_path, 'w')` на вызов `FileWriter.write_file()`.

**Результат:** запись остаётся в ReActAgent, но с бэкапом и проверкой путей. Не ломает Telegram и Chat.

---

### Фаза 2: Human-in-the-loop

**Цель:** Подтверждение критичных действий (запись в важные файлы, sudo, rm и т.д.).

**Сложность:** Victoria работает в long-running цикле; нужно уметь «остановиться», спросить пользователя и продолжить.

**Варианты:**

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| **A. Синхронный approval через callback** | Простая модель | Victoria блокируется на ожидании |
| **B. Асинхронный: PENDING_APPROVAL + resume** | Не блокирует Victoria | Сложнее: состояние, таймауты, хранилище |
| **C. Только логирование** | Реализуется быстро | Нет реального контроля до выполнения |

**Рекомендация:** начать с **A** для Web IDE (есть SSE, можно держать соединение). Для Telegram — **C** или позднее **B**.

**Реализация A (Web IDE):**

1. В ReActAgent при `create_file`/`write_file` для критичных файлов:
   - не писать сразу;
   - вернуть специальный шаг `PENDING_APPROVAL` с `approval_id`, `action`, `params`.
2. Chat/SSE: при `PENDING_APPROVAL` отправить событие в UI, показать кнопки «Подтвердить» / «Отклонить».
3. Новый endpoint `POST /api/chat/approve`:
   - `approval_id`, `approved: true/false`;
   - возобновление ReAct с учётом ответа (продолжить или отменить шаг).

**Реализация для Telegram (позже):**

- Вместо блокировки — сохранить `approval_id` и отправить в Telegram:  
  «Victoria хочет записать в `X`. Ответьте /approve_123 или /reject_123».
- Отдельный процесс/бот слушает ответы и вызывает `POST /api/chat/approve`.
- Таймаут (например, 5 мин): при истечении — считать отклонённым.

---

### Фаза 3: Terminal + Victoria

**Цель:** возможность «спросить Victoria» из терминала.

**Варианты:**

| Вариант | Описание |
|---------|----------|
| **T1. Команда `v`** | В PTY: `v "создай файл test.py"` → запрос в Victoria, ответ в терминал |
| **T2. Отдельная вкладка/панель** | В Web IDE: панель «Ask Victoria» рядом с терминалом |
| **T3. Inline подсказки** | Терминал показывает подсказки Victoria на основе введённой команды |

**Рекомендация:** начать с **T1** — одна команда `v` в терминале, которая дергает Victoria. Можно сделать через Backend API (тот же chat/victoria), без изменений PTY.

**Пример реализации T1:**

1. В backend: `POST /api/terminal/ask` с `{"command": "создай test.py"}`.
2. Handler вызывает Victoria так же, как chat.
3. В PTY: при вводе `v ...` клиент шлёт запрос на `/api/terminal/ask` и печатает ответ.

---

## План внедрения (приоритеты)

### Неделя 1: Безопасная запись ✅

- [x] Создать `SafeFileWriter` (`knowledge_os/app/file_writer.py`) с бэкапами и проверкой путей.
- [x] Интегрировать в ReActAgent вместо прямой записи.
- [x] Добавить `AGENT_BACKUP_ENABLED`, `WORKSPACE_ROOT` в конфиг (docker-compose).

### Неделя 2: Approval для Web IDE (частично)

- [x] ApprovalManager: проверка критичных файлов (package.json, .env, Dockerfile и т.п.).
- [x] При `AGENT_APPROVAL_REQUIRED=true` — отказ в записи в критичные файлы.
- [ ] Полный flow: PENDING_APPROVAL + UI + resume (запланировано).

### Неделя 3: Telegram approval (опционально)

- [x] Заглушки `/approve_X`, `/reject_X` (готовы к интеграции с Victoria).
- [ ] Сохранение pending approvals (интеграция с Victoria PENDING_APPROVAL).
- [ ] Таймаут и автоматический reject.

### Неделя 4: Terminal + Victoria ✅

- [x] `POST /api/terminal/ask` в backend.
- [x] Поддержка `v "задача"` в Web IDE терминале (перехват, вызов Victoria).
- [x] `bash scripts/chat_victoria.sh` — интерактивный чат в системном терминале (без браузера).

### Telegram Bot: меню и команды ✅

- [x] setMyCommands — меню при нажатии / в Telegram.
- [x] /project, /models, /clear — основные команды.
- [x] История чата per chat_id (до 100 сообщений).
- [x] Заглушки /approve_X, /reject_X.

---

## Чего не делать на первом этапе

1. **SandboxedExecutor** — `_validate_command_safety` уже есть; изолированная песочница (контейнер, ns) — отдельная большая задача.
2. **DynamicPlanner** — ReAct уже планирует шаги; расширенный планировщик — после стабилизации approval и записи.
3. **ReflectionEngine** — ReAct делает observe/reflect; отдельный «рефлексивный» движок — только при явных проблемах с циклами.

---

## Итоговая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                         Пользователь                             │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐
│   Telegram   │    │  Web IDE     │    │  Terminal (PTY)      │
│   Bot        │    │  Chat        │    │  v "задача" → Victoria│
└──────────────┘    └──────────────┘    └──────────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌──────────────────┐
                    │ Victoria /run    │
                    │ Enhanced or Base │
                    └──────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌───────────────┐  ┌─────────────────────┐
│ create_file/    │  │ Approval      │  │ FileWriter          │
│ write_file      │  │ (критичные)   │  │ (бэкап + путь)      │
└─────────────────┘  └───────────────┘  └─────────────────────┘
```

---

## Конфигурация (.env)

```bash
# Бэкапы
AGENT_BACKUP_ENABLED=true
AGENT_BACKUP_RETENTION_DAYS=7
AGENT_BACKUP_DIR=.agent_backups

# Approval (опционально)
AGENT_APPROVAL_REQUIRED=critical_files,first_write
AGENT_APPROVAL_TIMEOUT_SEC=300
```
