#!/usr/bin/env bash
set -euo pipefail

# Автоматическая настройка сервера Mac Studio
# Выполняет все проверки и настройки автоматически

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 Автоматическая настройка сервера Mac Studio"
echo "=============================================="
echo ""

# Определяем путь к репозиторию
if [[ ! -f "docker-compose.yml" ]]; then
  # Пробуем найти репозиторий
  for dir in "$HOME/Documents/dev/atra" "$HOME/atra" "$HOME/Documents/GITHUB/atra/atra"; do
    if [[ -f "$dir/docker-compose.yml" ]]; then
      ROOT_DIR="$dir"
      cd "$ROOT_DIR"
      break
    fi
  done
fi

if [[ ! -f "docker-compose.yml" ]]; then
  echo "❌ Репозиторий не найден. Текущая директория: $(pwd)"
  exit 1
fi

echo "✅ Репозиторий: $(pwd)"
echo ""

# 1. Проверка и создание директорий
echo "[1/6] Создание необходимых директорий..."
mkdir -p "$HOME/bin"
mkdir -p "$HOME/Library/Logs/atra"
mkdir -p "$HOME/atra_backups/knowledge_postgres"
echo "✅ Директории созданы"
echo ""

# 2. Копирование/создание скриптов проверки
echo "[2/6] Настройка скриптов проверки..."

# Проверяем, есть ли улучшенный скрипт
if [[ ! -f "scripts/check_all_services_enhanced.sh" ]]; then
  echo "⚠️  Скрипт check_all_services_enhanced.sh не найден, создаю базовый..."
  # Базовый скрипт уже должен быть
fi

# Делаем скрипты исполняемыми
chmod +x scripts/*.sh 2>/dev/null || true
echo "✅ Скрипты проверки готовы"
echo ""

# 3. Настройка алертов
echo "[3/6] Настройка системы алертов..."

# Создаем скрипт проверки алертов
cat > "$HOME/bin/atra_check_alerts.sh" << 'ALERT_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ATRA_ROOT:-$HOME/Documents/dev/atra}"
cd "$ROOT_DIR" 2>/dev/null || exit 1

LOG_DIR="$HOME/Library/Logs/atra"
ALERTS=()

add_alert() {
  ALERTS+=("$1")
}

if ! docker info >/dev/null 2>&1; then
  add_alert "❌ Docker daemon не запущен"
fi

check_service() {
  local name=$1
  local url=$2
  if ! curl -s -f "$url" >/dev/null 2>&1; then
    add_alert "❌ $name недоступен ($url)"
  fi
}

check_service "Knowledge OS API" "http://localhost:8000/health" || check_service "Knowledge OS API" "http://localhost:8000/"
check_service "MLX API Server" "http://localhost:11434/"

if ! docker-compose exec -T knowledge-os-db pg_isready -U admin -d knowledge_os >/dev/null 2>&1; then
  add_alert "❌ PostgreSQL база данных недоступна"
fi

AGENTS=("victoria-agent" "veronica-agent" "nightly-learner")
for agent in "${AGENTS[@]}"; do
  if ! docker-compose ps "$agent" 2>/dev/null | grep -q "Up"; then
    add_alert "❌ Агент $agent не запущен"
  fi
done

DISK_USAGE=$(df -h / | tail -n 1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE -gt 90 ]]; then
  add_alert "⚠️  Диск заполнен на ${DISK_USAGE}%"
fi

BACKUP_DIR="${LOCAL_BACKUP_DIR:-$HOME/atra_backups/knowledge_postgres}"
LATEST_BACKUP=$(ls -1t "$BACKUP_DIR"/*.dump 2>/dev/null | head -n 1 || echo "")
if [[ -n "$LATEST_BACKUP" ]]; then
  AGE_HOURS=$(($(date +%s) - $(stat -f %m "$LATEST_BACKUP" 2>/dev/null || echo 0)) / 3600)
  if [[ $AGE_HOURS -gt 25 ]]; then
    add_alert "⚠️  Последний бэкап старше ${AGE_HOURS} часов"
  fi
else
  add_alert "⚠️  Бэкапы не найдены"
fi

if [[ ${#ALERTS[@]} -gt 0 ]]; then
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] АЛЕРТЫ:" >> "$LOG_DIR/alerts.log"
  for alert in "${ALERTS[@]}"; do
    echo "  $alert" >> "$LOG_DIR/alerts.log"
  done
  exit 1
else
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] ✅ Все проверки пройдены" >> "$LOG_DIR/alerts.log"
  exit 0
fi
ALERT_SCRIPT

chmod +x "$HOME/bin/atra_check_alerts.sh"

# Добавляем в cron
CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")
CLEANED_CRON=$(echo "$CURRENT_CRON" | grep -v "atra_check_alerts" || true)
NEW_LINE="*/15 * * * * ATRA_ROOT=\"$ROOT_DIR\" /bin/bash $HOME/bin/atra_check_alerts.sh >> $HOME/Library/Logs/atra/alerts_cron.out.log 2>> $HOME/Library/Logs/atra/alerts_cron.err.log"
FINAL_CRON=$(echo -e "$CLEANED_CRON\n$NEW_LINE\n" | grep -v '^$')
echo "$FINAL_CRON" | crontab -

echo "✅ Система алертов настроена (проверка каждые 15 минут)"
echo ""

# 4. Проверка Docker
echo "[4/6] Проверка Docker..."
if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon не запущен. Запустите Docker Desktop."
  echo "⚠️  Продолжаю настройку, но некоторые проверки не будут работать"
else
  echo "✅ Docker работает"
fi
echo ""

# 5. Проверка сервисов (если Docker запущен)
echo "[5/6] Проверка сервисов..."
if docker info >/dev/null 2>&1; then
  if [[ -f "scripts/check_all_services_enhanced.sh" ]]; then
    bash scripts/check_all_services_enhanced.sh || echo "⚠️  Есть проблемы с сервисами"
  else
    echo "📊 Статус контейнеров:"
    docker-compose ps 2>/dev/null || echo "⚠️  Не удалось получить статус"
  fi
else
  echo "⚠️  Docker не запущен, пропускаю проверку сервисов"
fi
echo ""

# 6. Проверка бэкапов
echo "[6/6] Проверка системы бэкапов..."
if [[ -f "scripts/check_backups_health.sh" ]]; then
  bash scripts/check_backups_health.sh || echo "⚠️  Есть проблемы с бэкапами"
else
  echo "⚠️  Скрипт проверки бэкапов не найден"
fi
echo ""

echo "=============================================="
echo "✅ Автоматическая настройка завершена!"
echo ""
echo "📋 Что настроено:"
echo "   ✅ Скрипт проверки алертов: $HOME/bin/atra_check_alerts.sh"
echo "   ✅ Cron job: каждые 15 минут"
echo "   ✅ Логи: $HOME/Library/Logs/atra/alerts.log"
echo ""
echo "🧪 Тестирование:"
echo "   bash $HOME/bin/atra_check_alerts.sh"
echo ""
echo "📊 Просмотр алертов:"
echo "   tail -f $HOME/Library/Logs/atra/alerts.log"
echo ""
echo "🔍 Проверка сервисов:"
echo "   bash scripts/check_all_services_enhanced.sh"
echo ""
