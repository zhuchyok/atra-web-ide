# 📥 КАК СКОПИРОВАТЬ ВСЕ ФАЙЛЫ С Mac Studio

**Дата:** 2026-01-26

---

## 🚀 БЫСТРЫЙ СПОСОБ

### Вариант 1: Интерактивный скрипт (рекомендуется)

```bash
# На Mac Studio, в терминале Cursor
bash ~/Documents/dev/atra/.cursor_chats_backup/copy_all_from_Mac Studio.sh
```

Скрипт:

- ✅ Запросит IP адрес Mac Studio
- ✅ Проверит доступность
- ✅ Оценит размер (~2 GB)
- ✅ Скопирует все файлы с прогрессом
- ✅ Покажет результат

**Пример использования:**

```bash
bash ~/Documents/dev/atra/.cursor_chats_backup/copy_all_from_Mac Studio.sh 192.168.1.100
```

---

### Вариант 2: Ручное копирование через rsync

```bash
# На Mac Studio
Mac Studio_IP="192.168.1.XXX"  # Укажите IP Mac Studio
Mac Studio_USER="bikos"

# Копировать все файлы
rsync -avz --progress \
    --exclude='node_modules' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='*.log' \
    --exclude='backups/migration' \
    $Mac Studio_USER@$Mac Studio_IP:~/Documents/atra-web-ide/ \
    ~/Documents/atra-web-ide/
```

---

### Вариант 3: Через USB/внешний диск

**На Mac Studio:**

```bash
cd ~/Documents/atra-web-ide

# Создать архив (исключая большие файлы)
tar czf atra-web-ide-full.tar.gz \
    --exclude='node_modules' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='backups' \
    --exclude='*.log' \
    .
```

**Скопировать архив на внешний диск, затем на Mac Studio:**

```bash
# На Mac Studio
cd ~/Documents
tar xzf /Volumes/EXTERNAL_DRIVE/atra-web-ide-full.tar.gz
```

---

## ⚙️ НАСТРОЙКА SSH (если нужно)

Если SSH без пароля не настроен:

```bash
# На Mac Studio - создать SSH ключ (если нет)
ssh-keygen -t ed25519 -C "mac-studio"

# Скопировать ключ на Mac Studio
ssh-copy-id bikos@[Mac Studio_IP]

# Проверить доступ
ssh bikos@[Mac Studio_IP]
```

---

## 📊 ОЦЕНКА ВРЕМЕНИ

- **Размер проекта:** ~2 GB
- **Через локальную сеть (100 Mbps):** ~3-5 минут
- **Через USB 3.0:** ~1-2 минуты
- **Через WiFi (50 Mbps):** ~5-10 минут

---

## ✅ ПОСЛЕ КОПИРОВАНИЯ

1. **Проверка файлов:**

   ```bash
   cd ~/Documents/atra-web-ide
   ls -la
   du -sh .
   ```

2. **Открыть в Cursor:**
   - File → Open Folder → `~/Documents/atra-web-ide`

3. **Запустить контейнеры:**
   ```bash
   docker-compose -f knowledge_os/docker-compose.yml up -d
   docker-compose up -d
   ```

---

_Инструкция создана: 2026-01-26_
