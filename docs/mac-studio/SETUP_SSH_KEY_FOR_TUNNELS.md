# 🔐 Настройка SSH ключа на Mac Studio для туннелей

**Дата:** 2026-01-25  
**Проблема:** На Mac Studio отсутствует SSH ключ `id_ed25519` для подключения к серверу

---

## 📋 ТЕКУЩАЯ СИТУАЦИЯ

**На Mac Studio:**

- ✅ Ключ `~/.ssh/id_ed25519` существует
- ✅ Публичный ключ добавлен на сервер `185.177.216.15`
- ✅ Подключение к серверу работает

**На Mac Studio:**

- ❌ Ключ `~/.ssh/id_ed25519` отсутствует
- ❌ Туннели 8010/8012 не работают
- ⚠️ Нет доступа к серверу по ключу

---

## 🔧 РЕШЕНИЕ: ВАРИАНТ А — Копирование ключа с Mac Studio

### Шаг 1: Копирование ключа на Mac Studio

**На Mac Studio выполните:**

```bash
# Копируем приватный и публичный ключи
scp ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub bikos@192.168.1.64:~/.ssh/
```

**На Mac Studio выполните:**

```bash
# Устанавливаем правильные права доступа
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

### Шаг 2: Проверка подключения

**На Mac Studio:**

```bash
# Проверяем подключение к серверу
ssh -i ~/.ssh/id_ed25519 root@185.177.216.15 "echo 'SSH key works'"
```

### Шаг 3: Запуск туннелей

**На Mac Studio:**

```bash
cd /path/to/atra-web-ide
bash scripts/start_mac_studio_tunnels.sh
```

---

## 🔧 РЕШЕНИЕ: ВАРИАНТ Б — Создание нового ключа на Mac Studio

### Шаг 1: Генерация нового ключа

**На Mac Studio выполните:**

```bash
# Создаем новый ключ
ssh-keygen -t ed25519 -C "mac-studio-tunnel" -f ~/.ssh/id_ed25519

# Устанавливаем права
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

### Шаг 2: Добавление публичного ключа на сервер

**На Mac Studio:**

```bash
# Копируем публичный ключ на сервер
cat ~/.ssh/id_ed25519.pub | ssh root@185.177.216.15 'cat >> ~/.ssh/authorized_keys'
```

**Или вручную:**

```bash
# Показываем публичный ключ
cat ~/.ssh/id_ed25519.pub

# Затем на сервере добавьте его в ~/.ssh/authorized_keys
```

### Шаг 3: Проверка и запуск туннелей

**На Mac Studio:**

```bash
# Проверяем подключение
ssh -i ~/.ssh/id_ed25519 root@185.177.216.15 "echo 'SSH key works'"

# Запускаем туннели
cd /path/to/atra-web-ide
bash scripts/start_mac_studio_tunnels.sh
```

---

## 📊 ПРОВЕРКА РАБОТЫ ТУННЕЛЕЙ

После настройки ключа и запуска туннелей проверьте:

```bash
# На сервере проверяем открытые порты
ssh root@185.177.216.15 "ss -tuln | grep -E ':(8010|8012)'"

# С Mac Studio проверяем доступность
curl -s http://185.177.216.15:8010/health
curl -s http://185.177.216.15:8012/health
```

**Ожидаемый результат:**

- Порт 8010 слушается на сервере
- Порт 8012 слушается на сервере
- Victoria доступна через `http://185.177.216.15:8010`
- MCP доступен через `http://185.177.216.15:8012`

---

## 🔄 АВТОЗАПУСК ТУННЕЛЕЙ

Для автоматического запуска туннелей при загрузке Mac Studio создайте launchd service:

**На Mac Studio:**

```bash
# Создаем plist файл
cat > ~/Library/LaunchAgents/com.atra.ssh-tunnels.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.ssh-tunnels</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/path/to/atra-web-ide/scripts/start_mac_studio_tunnels.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/atra-web-ide</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>~/Library/Logs/ssh-tunnels.log</string>
    <key>StandardErrorPath</key>
    <string>~/Library/Logs/ssh-tunnels.err.log</string>
</dict>
</plist>
EOF

# Загружаем service
launchctl load ~/Library/LaunchAgents/com.atra.ssh-tunnels.plist
```

---

## ✅ ЧЕКЛИСТ

- [ ] SSH ключ создан/скопирован на Mac Studio
- [ ] Права доступа установлены (600 для приватного, 644 для публичного)
- [ ] Публичный ключ добавлен на сервер `185.177.216.15`
- [ ] Подключение к серверу проверено
- [ ] Туннели запущены (`scripts/start_mac_studio_tunnels.sh`)
- [ ] Порты 8010 и 8012 слушаются на сервере
- [ ] Victoria и MCP доступны через сервер
- [ ] Автозапуск настроен (опционально)

---

**Создано:** 2026-01-25  
**Автор:** Команда экспертов (Виктория, Сергей, Алексей)
