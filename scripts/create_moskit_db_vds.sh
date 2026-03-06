#!/usr/bin/env bash
# Создание БД moskit и пользователя moskit на существующем PostgreSQL (atra-postgres).
# Запуск на VDS из каталога приложения (где есть .env с DB_PASSWORD и MOSKIT_DB_PASSWORD):
#   cd /home/atra/app && bash scripts/create_moskit_db_vds.sh
# Или с хоста: ssh root@45.10.43.248 "cd /home/atra/app && MOSKIT_DB_PASSWORD=xxx bash scripts/create_moskit_db_vds.sh"

set -e

CONTAINER="${POSTGRES_CONTAINER:-atra-postgres}"
# На VDS atra-postgres часто создаётся с суперпользователем postgres, а не admin
PG_USER="${DB_USER:-postgres}"
PG_PASS="${DB_PASSWORD:-}"
MOSKIT_PASS="${MOSKIT_DB_PASSWORD:-moskit_secret}"
# Экранирование одиночной кавычки для SQL: ' -> ''
MOSKIT_PASS_SQL="${MOSKIT_PASS//\'/\'\'}"

echo "Creating moskit user and database on $CONTAINER (psql user: $PG_USER)..."

# Пользователь moskit (игнорируем ошибку если уже есть)
docker exec ${PG_PASS:+-e PGPASSWORD="$PG_PASS"} "$CONTAINER" psql -U "$PG_USER" -d postgres -c "CREATE USER moskit WITH PASSWORD '${MOSKIT_PASS_SQL}';" 2>/dev/null || true

# База moskit
exists=$(docker exec ${PG_PASS:+-e PGPASSWORD="$PG_PASS"} "$CONTAINER" psql -U "$PG_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='moskit'" 2>/dev/null || echo "")
if [ -z "$exists" ]; then
  docker exec ${PG_PASS:+-e PGPASSWORD="$PG_PASS"} "$CONTAINER" psql -U "$PG_USER" -d postgres -c "CREATE DATABASE moskit OWNER moskit;"
  echo "Database moskit created."
else
  echo "Database moskit already exists."
fi

echo "Done. moskit DB and user ready for moskit-api."
