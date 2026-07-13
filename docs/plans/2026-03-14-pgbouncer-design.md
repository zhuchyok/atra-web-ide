# PgBouncer — дизайн внедрения

**Дата:** 2026-03-14  
**Автор:** Команда Atra Core (Виктория, Роман, Игорь, Анна, Сергей)  
**Статус:** Одобрен, готов к реализации

---

## Проблема

39 Python-модулей создают отдельные `asyncpg.create_pool()`. При старте 37 контейнеров после Docker restart
все пулы открываются одновременно → суммарно 300-500 соединений → `max_connections` PostgreSQL исчерпан →
`too many clients already` → Victoria не может загрузить Expert DNA → задачи зависают.

**Текущие меры (временные):**

- `max_connections=500` в PostgreSQL (повышено сегодня)
- `idle_in_transaction_session_timeout=300s`
- `auto_fix_db_connections.py` (чистит при >70%)

**Почему этого недостаточно:** при рестарте Docker все пулы открываются быстрее чем auto_fix успевает сработать.

---

## Решение: PgBouncer (transaction pooling)

```
Victoria / Veronica / expert-workers / orchestrator / ... (11 сервисов)
  │ каждый: max_size=5, итого ~55 клиентских соединений к PgBouncer
  ▼ порт 6432
┌─────────────────────────────────────┐
│  PgBouncer (transaction pooling)    │
│  max_client_conn=1000               │
│  default_pool_size=20               │
│  reserve_pool_size=5                │
└─────────────────────────────────────┘
  │ 20 реальных соединений
  ▼ порт 5432
┌─────────────────────────────────────┐
│  PostgreSQL                         │
│  max_connections=100 (было 500!)    │
└─────────────────────────────────────┘

Исключение: employees_sync_daemon → postgres:5432 напрямую (LISTEN/NOTIFY)
```

---

## Исключение: LISTEN/NOTIFY

`knowledge_os/app/employees_sync_daemon.py` использует PostgreSQL `LISTEN 'experts_changed'`.
Transaction pooling несовместим с LISTEN — соединение возвращается в пул после транзакции и теряет подписку.

**Решение:** добавить env `POSTGRES_DIRECT_URL` в victoria-agent, daemon использует его напрямую.

---

## Затронутые файлы

| Файл                                        | Действие                                                                                  |
| ------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `knowledge_os/docker-compose.yml`           | Новый сервис `pgbouncer`, 11 строк DATABASE_URL → `pgbouncer:6432`, `max_connections=100` |
| `knowledge_os/pgbouncer/pgbouncer.ini`      | Новый файл конфига                                                                        |
| `knowledge_os/pgbouncer/userlist.txt`       | Новый файл с credentials                                                                  |
| `knowledge_os/app/employees_sync_daemon.py` | Использовать `POSTGRES_DIRECT_URL` для LISTEN                                             |
| `knowledge_os/app/db_pool.py`               | `max_size` остаётся 5 (PgBouncer мультиплексирует)                                        |

---

## Параметры PgBouncer

```ini
pool_mode = transaction          # соединение возвращается в пул после каждой транзакции
max_client_conn = 1000           # клиентских соединений принимаем
default_pool_size = 20           # реальных соединений к Postgres
min_pool_size = 5                # минимум держим открытыми
reserve_pool_size = 5            # экстренный резерв
reserve_pool_timeout = 3         # секунды ожидания резервного пула
server_idle_timeout = 300        # закрывать idle server-соединения через 5 мин
```

---

## Критерии успеха

- [ ] `docker exec pgbouncer psql -p 6432 ...` — подключение работает
- [ ] Victoria health: `database: true`
- [ ] `pg_stat_activity` на Postgres: не более 30 соединений при всех запущенных контейнерах
- [ ] `employees_sync_daemon` корректно получает NOTIFY при `sync_employees.py`
- [ ] `too many clients` не появляется после рестарта Docker
