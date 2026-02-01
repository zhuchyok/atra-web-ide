# Восстановление узлов знаний

## Сводка источников

| Источник | Узлов | Доступ |
|----------|-------|--------|
| **Mac Studio** | тысячи | Экспорт локально на Mac Studio, затем импорт |
| **Архив** | 131 | `restore_knowledge_from_archive.sql` |

> ⚠️ Server 46 — данных нет, не использовать.

**Единая база:** atra-web-ide и atra используют общий `knowledge_postgres`.

---

## Если «базу сменили» — старые узлы на Mac Studio

Тысячи узлов остались на Mac Studio. Postgres там недоступен по сети (порт 5432 закрыт).

### Перенос с Mac Studio

**1. На Mac Studio** (где запущен postgres с тысячами узлов):
```bash
cd /path/to/atra-web-ide  # или atra
bash scripts/export_knowledge_from_mac_studio.sh
# Создаётся knowledge_nodes_dump.sql (или .dump)
```

**2. Копирование на локальную машину:**
```bash
scp user@mac-studio-ip:/path/to/knowledge_nodes_export.json ./
```

**3. На локальной машине** (где единая база):
```bash
# Вариант A: JSON (рекомендуется — совместим при разной схеме)
# На Mac Studio: python3 scripts/export_knowledge_portable.py
# Копируем knowledge_nodes_export.json, затем:
python3 scripts/import_knowledge_from_json.py
# или в Docker:
docker cp knowledge_nodes_export.json atra-web-ide-backend:/tmp/
docker exec -i atra-web-ide-backend python3 -c "
import asyncio, json, asyncpg, os
async def run():
    with open('/tmp/knowledge_nodes_export.json') as f:
        data = json.load(f)
    conn = await asyncpg.connect('postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
    for r in data:
        try:
            await conn.execute('INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count) VALUES (\$1, \$2::jsonb, \$3, \$4, \$5)',
                r.get('content',''), json.dumps(r.get('metadata',{})), r.get('confidence_score',0.5), r.get('is_verified',False), r.get('usage_count',0))
        except: pass
    print('Done')
asyncio.run(run())
"

# Вариант B: SQL дамп (если схема совпадает)
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < knowledge_nodes_dump.sql
```

### Миграция по сети (если Postgres доступен)

```bash
SOURCE_DATABASE_URL=postgresql://admin:secret@СТАРЫЙ_ХОСТ:ПОРТ/knowledge_os \
DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os \
python3 scripts/migrate_knowledge_from_source_db.py
```

**Если старая БД в другом томе Docker:**
1. Запустить временный Postgres со старым томом:  
   `docker run -d -v ИМЯ_СТАРОГО_ТОМА:/var/lib/postgresql/data -p 5433:5432 -e POSTGRES_* pgvector/pgvector:pg16`
2. `SOURCE_DATABASE_URL=postgresql://admin:secret@localhost:5433/knowledge_os`
3. Выполнить скрипт миграции

## Архив (knowledge_cleaner)

- **knowledge_cleaner** переносит старые неиспользуемые узлы в `knowledge_nodes_archive`
- Восстановлено 131 узел из архива → сейчас **146** узлов в `knowledge_nodes`

## Поиск на MacBook (источник миграции)

Миграция делалась с MacBook. Там могут остаться дампы или volumes.

**Запустить на MacBook** (где Cursor и миграция):
```bash
cd ~/Documents/atra-web-ide
bash scripts/search_knowledge_on_macbook.sh
```

Скрипт ищет: `~/migration/server2/*.sql`, Docker volumes, бэкапы.

**Если MacBook в сети** — с Mac Studio можно попробовать:
```bash
MACBOOK_IP=192.168.1.XX  # IP MacBook
scp scripts/search_knowledge_on_macbook.sh bikos@$MACBOOK_IP:~/Documents/atra-web-ide/scripts/
ssh bikos@$MACBOOK_IP "cd ~/Documents/atra-web-ide && bash scripts/search_knowledge_on_macbook.sh"
```

## atra backups (~37k узлов)

В `~/Documents/dev/atra/backups/` лежат дампы knowledge_os (21 MB).

```bash
bash scripts/import_from_atra_backup.sh
```

Скрипт вставляет только в существующие колонки целевой таблицы, схему не меняет.

## Другие источники

- **Дамп** — если есть сохранённый `knowledge_os_dump.sql`: `bash scripts/migrate_from_dump.sh`

## Восстановление из архива

```bash
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < scripts/restore_knowledge_from_archive.sql
```

Или локально: `psql postgresql://admin:secret@localhost:5432/knowledge_os -f scripts/restore_knowledge_from_archive.sql`

## Отключение архивации

Чтобы knowledge_cleaner не переносил узлы, не запускайте его (он вызывается вручную или по крону). Либо измените пороги в `knowledge_os/app/knowledge_cleaner.py`.
