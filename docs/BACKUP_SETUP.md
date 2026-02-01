# Настройка бэкапов Knowledge OS

Полный бэкап: **локально (Mac Studio)** + **Google Drive**.  
(Telegram убран — лимит 50 MB, БД уже >50 MB и растёт.)

---

## Быстрый старт

```bash
# Ручной запуск
./scripts/backup_knowledge_os_full.sh
```

---

## Переменные окружения (.env)

| Переменная | Описание | Обязательно |
|------------|----------|-------------|
| `RCLONE_GDRIVE_REMOTE` | Имя rclone remote (по умолчанию `gdrive`) | Для GDrive |
| `BACKUP_GDRIVE_ENABLED` | `true`/`false` (по умолчанию true) | Нет |

---

## Настройка Google Drive (rclone)

### 1. Установка rclone

```bash
# macOS (Homebrew)
brew install rclone

# или
curl https://rclone.org/install.sh | sudo bash
```

### 2. Создание remote для Google Drive

```bash
rclone config
```

- `n` — новый remote  
- Имя: `gdrive` (или другое — укажите в `RCLONE_GDRIVE_REMOTE`)  
- Storage: `drive` (Google Drive)  
- Следуйте шагам OAuth (откроется браузер для авторизации)  
- При необходимости создайте папку `knowledge_os_backups` в Google Drive — rclone создаст её при первой загрузке  

Конфиг: `~/.config/rclone/rclone.conf`

### 3. Проверка

```bash
rclone listremotes
# Должно показать: gdrive:

rclone ls gdrive:knowledge_os_backups/
# После первого бэкапа — список файлов
```

---

## Автозапуск (cron / LaunchAgent)

### Cron (Mac Studio, Linux)

```bash
crontab -e
```

Добавить (замените путь на ваш):

```
0 2 * * * cd /Users/bikos/Documents/atra-web-ide && ./scripts/backup_knowledge_os_full.sh >> /tmp/backup_knowledge_os.log 2>&1
```

Запуск ежедневно в 02:00.

### LaunchAgent (macOS — автозапуск при загрузке)

См. `scripts/setup_backup_launchd.sh` — создаёт `com.atra.backup-knowledge-os.plist`.

---

## Структура

| Цель | Путь | Хранение |
|------|------|----------|
| Локально | `~/Documents/dev/atra/backups/` или `./backups/` | 7 дней |
| Google Drive | `gdrive:knowledge_os_backups/` | Без автоочистки (ручная ротация) |

---

## Проверка работы

```bash
# 1. Локальный бэкап
ls -la ~/Documents/dev/atra/backups/

# 2. Google Drive
rclone ls gdrive:knowledge_os_backups/
```

---

## Восстановление из бэкапа

```bash
# Из локального
gunzip -c ~/Documents/dev/atra/backups/knowledge_os_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i knowledge_postgres psql -U admin -d knowledge_os

# Из Google Drive
rclone copy gdrive:knowledge_os_backups/knowledge_os_YYYYMMDD_HHMMSS.sql.gz /tmp/
gunzip -c /tmp/knowledge_os_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i knowledge_postgres psql -U admin -d knowledge_os
```

---

---

*Документ создан 2026-02-01*
