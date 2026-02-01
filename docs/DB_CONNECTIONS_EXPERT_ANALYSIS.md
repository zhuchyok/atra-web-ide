# Экспертная сводка: «Too many clients» — почему и что делать

## Диагноз

**PostgreSQL max_connections = 100, активных подключений ≈ 95.** Лимит почти достигнут.

## Почему так вышло (по мнению экспертов)

### 1. Много сервисов к одной БД
- **atra-web-ide backend** — pool max 10
- **Victoria Agent** — pool max 5 + прямые connect (corporation_data_tool, department_heads)
- **Veronica Agent** — pool max 5
- **knowledge_os_api** — pool max 5
- **knowledge_os_worker** — pool max 5
- **knowledge_os_orchestrator** — pool max 5
- **knowledge_nightly** — свои connect
- **corporation-dashboard** (Streamlit 8501) — psycopg2, каждое обновление страницы
- **knowledge_dashboard** — Streamlit, свой коннект
- **ai_core** — pool max 5
- **streaming_orchestrator** — pool max 5
- **Итого по пулам:** 10+5+5+5+5+5+5+5+5 ≈ 55 только по max_size
- **Плюс:** прямые `asyncpg.connect()` без пула — corporation_data_tool, task_distribution, department_heads и др.

### 2. Прямые connect вместо пула
- `corporation_data_tool` — каждый Text-to-SQL = новое подключение
- `task_distribution_system_complete` — connect на каждый вызов
- `department_heads_system` — connect на каждый вызов
- `debate_processor`, `collective_memory` и др. — аналогично

### 3. Streamlit
- При каждом rerun/refresh Streamlit открывает новые соединения
- `_quick_db_check()` закрывает соединение, но до этого успевает создаться ещё одно

### 4. «idle in transaction»
- Одно из подключений зависло в транзакции — соединение не освобождено

## Рекомендации

1. **Быстро:** увеличить `max_connections` в PostgreSQL до 200
2. **Среднесрочно:** уменьшить `max_size` в пулах (backend: 5, victoria: 3, worker: 3)
3. **Долгосрочно:** corporation_data_tool и др. — перейти на общий пул или переиспользование соединений
