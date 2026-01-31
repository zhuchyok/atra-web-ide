# Миграция данных корпорации — 25.01.2026

## Скачанные данные

### Server 2 (46.149.66.170) — Knowledge OS
| Файл | Размер | Описание |
|------|--------|----------|
| `knowledge_os_dump.sql` | 106 MB | Полный дамп БД (26 таблиц) |
| `experts.csv` | 131 KB | 58 экспертов |
| `knowledge_os_app.tar.gz` | 342 KB | 72 Python файла |

**Данные в БД:**
- Эксперты: 58
- Узлы знаний: 50,926
- Домены: 35
- Таблицы: 26

### Server 1 (185.177.216.15) — Trading Bot
| Файл | Размер | Описание |
|------|--------|----------|
| `redis_dump.rdb` | 612 B | Redis backup (4 ключа) |
| `ai_data.tar.gz` | 1 KB | AI learning/reports data |

## Путь к файлам

```
~/migration/
├── server1/
│   ├── redis_dump.rdb
│   └── ai_data.tar.gz
└── server2/
    ├── knowledge_os_dump.sql
    ├── experts.csv
    └── knowledge_os_app.tar.gz
```

## Статус серверов

| Сервер | IP | Статус |
|--------|------|--------|
| Server 1 | 185.177.216.15 | ✅ Ollama работает, SSH OK |
| Server 2 | 46.149.66.170 | ✅ PostgreSQL работает, SSH OK |
| Mac Studio | 192.168.1.43 | ✅ Ollama (8 моделей), Victoria/Veronica не запущены |
| Локально | localhost | ✅ Ollama (6 моделей), Victoria работает |

## Как применить дамп БД

### Вариант 1: Локально (если есть PostgreSQL)
```bash
# Создать БД
createdb knowledge_os

# Импортировать
psql -d knowledge_os < ~/migration/server2/knowledge_os_dump.sql
```

### Вариант 2: Через Docker
```bash
cd /Users/zhuchyok/Documents/atra-web-ide

# Запустить БД
docker-compose -f knowledge_os/docker-compose.yml up -d db

# Подождать 30 секунд, затем импорт
docker exec -i knowledge_os_db psql -U admin -d knowledge_os < ~/migration/server2/knowledge_os_dump.sql
```

## Как применить app файлы

```bash
# Распаковать и сравнить
cd ~/migration/server2
tar -xzf knowledge_os_app.tar.gz

# Скопировать новые файлы (если нужно)
# rsync -av app/ /Users/zhuchyok/Documents/atra-web-ide/knowledge_os/app/
```

## Эксперты (58 человек)

Экспорт из БД включает:
- Натан — Director of Competitive Intelligence
- Оксана — Digital Strategist / Media Planner
- И ещё 56 экспертов...

Полный список: `~/migration/server2/experts.csv`

## Следующие шаги

1. [ ] Запустить PostgreSQL локально или через Docker
2. [ ] Импортировать `knowledge_os_dump.sql`
3. [ ] Запустить Victoria и Veronica на Mac Studio
4. [ ] Проверить работу Knowledge OS API

## Скрипты

- Проверка сервисов: `bash scripts/check_services.sh`
- Локальный запуск: `bash scripts/start_local.sh`
- Миграция (полная): `python3 scripts/migration/corporation_full_migration.py`
