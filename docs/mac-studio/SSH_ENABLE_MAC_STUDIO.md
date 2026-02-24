# 🔐 ВКЛЮЧЕНИЕ SSH НА MAC STUDIO

**Дата:** 2026-01-25  
**Статус:** ✅ **ИНСТРУКЦИЯ**

---

## 🎯 ПРОБЛЕМА

Mac Studio недоступен по SSH. Нужно включить удалённый вход.

---

## ✅ РЕШЕНИЕ: ВКЛЮЧЕНИЕ SSH

### **Вариант 1: Через Системные настройки (GUI)** 🖥️

1. Откройте **Системные настройки** (System Settings)
2. Перейдите в **Общий доступ** (Sharing)
3. Включите **Удалённый вход** (Remote Login)
4. Выберите, кому разрешён доступ:
   - **Все пользователи** (All users)
   - **Только эти пользователи** (Only these users) — выберите нужных

**Готово!** SSH теперь доступен на порту 22.

---

### **Вариант 2: Через Терминал (CLI)** 💻

Выполните на Mac Studio:

```bash
# Включить SSH
sudo systemsetup -setremotelogin on

# Проверить статус
sudo systemsetup -getremotelogin

# Должно вывести: "Remote Login: On"
```

---

### **Вариант 3: Автоматический скрипт** 🚀

Используйте скрипт из проекта:

```bash
bash scripts/mac-studio/enable_ssh.sh
```

---

## 🔍 ПРОВЕРКА

### 1. Проверка статуса SSH

```bash
# На Mac Studio
sudo systemsetup -getremotelogin

# Или проверить, слушает ли SSH порт 22
sudo lsof -i :22
# Должно показать процесс sshd
```

### 2. Проверка подключения (с другого компьютера)

```bash
# Узнайте IP адрес Mac Studio
# На Mac Studio:
ifconfig | grep "inet " | grep -v 127.0.0.1

# С другого компьютера (например, Mac Studio):
ssh <username>@<mac-studio-ip>

# Например:
ssh bikos@192.168.1.64
```

---

## 🔥 ВОЗМОЖНЫЕ ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема 1: SSH включен, но подключение не работает

**Решение:**

1. Проверьте файрвол:

   ```bash
   # Проверить статус файрвола
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

   # Если файрвол включен, разрешите SSH
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/sbin/sshd
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /usr/sbin/sshd
   ```

2. Проверьте, что SSH слушает порт 22:
   ```bash
   sudo lsof -i :22
   ```

### Проблема 2: "Connection refused"

**Решение:**

1. Убедитесь, что SSH включен:

   ```bash
   sudo systemsetup -setremotelogin on
   ```

2. Перезапустите SSH сервис:
   ```bash
   sudo launchctl stop com.openssh.sshd
   sudo launchctl start com.openssh.sshd
   ```

### Проблема 3: "Permission denied"

**Решение:**

1. Убедитесь, что пользователь существует и имеет права на вход
2. Проверьте настройки в **Системные настройки → Общий доступ → Удалённый вход**

---

## 🔐 БЕЗОПАСНОСТЬ

### Рекомендации:

1. **Используйте SSH ключи вместо паролей:**

   ```bash
   # На клиенте (Mac Studio)
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ssh-copy-id <username>@<mac-studio-ip>
   ```

2. **Отключите вход по паролю** (после настройки ключей):

   ```bash
   # На Mac Studio
   sudo nano /etc/ssh/sshd_config
   # Измените: PasswordAuthentication no
   sudo launchctl stop com.openssh.sshd
   sudo launchctl start com.openssh.sshd
   ```

3. **Измените стандартный порт** (опционально):
   ```bash
   # На Mac Studio
   sudo nano /etc/ssh/sshd_config
   # Измените: Port 2222 (или другой порт)
   sudo launchctl stop com.openssh.sshd
   sudo launchctl start com.openssh.sshd
   ```

---

## 📝 БЫСТРАЯ КОМАНДА

```bash
# Включить SSH одной командой
sudo systemsetup -setremotelogin on && echo "✅ SSH включен" || echo "❌ Ошибка"
```

---

## 🔗 СВЯЗАННЫЕ ДОКУМЕНТЫ

- `REMOTE_ACCESS_SETUP.md` — настройка удалённого доступа (Tailscale, Cloudflare, SSH туннели)
- `MAC_STUDIO_AND_SERVERS_KNOWLEDGE.md` — общая информация по Mac Studio и серверам

---

_Документ создан 2026-01-25_
