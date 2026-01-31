# 🔐 Настройка SSH ключей в переменных окружения

**Дата:** 2026-01-25  
**Статус:** ✅ **Настроено на Mac Studio и Mac Studio**

---

## 📋 ДОБАВЛЕНО В .env

### На Mac Studio (`/Users/zhuchyok/Documents/atra-web-ide/.env`):

```bash
# SSH КЛЮЧИ ДЛЯ ПОДКЛЮЧЕНИЯ К СЕРВЕРАМ
SSH_KEY_PATH=/Users/zhuchyok/.ssh/id_ed25519
SSH_KEY_PUB_PATH=/Users/zhuchyok/.ssh/id_ed25519.pub

# SSH настройки для сервера
SSH_REMOTE_HOST=root@185.177.216.15
SSH_REMOTE_PASS=u44Ww9NmtQj,XG

# SSH настройки для Mac Studio
MAC_STUDIO_HOST=bikos@192.168.1.64
MAC_STUDIO_IP=192.168.1.64
```

### На Mac Studio (`/Users/bikos/.env`):

```bash
# SSH КЛЮЧИ ДЛЯ ПОДКЛЮЧЕНИЯ К СЕРВЕРАМ
SSH_KEY_PATH=/Users/bikos/.ssh/id_ed25519
SSH_KEY_PUB_PATH=/Users/bikos/.ssh/id_ed25519.pub

# SSH настройки для сервера
SSH_REMOTE_HOST=root@185.177.216.15
SSH_REMOTE_PASS=u44Ww9NmtQj,XG

# SSH настройки для Mac Studio
Mac Studio_HOST=zhuchyok@192.168.1.38
Mac Studio_IP=192.168.1.38
```

---

## 🔧 ИСПОЛЬЗОВАНИЕ

### В скриптах:

```bash
# Загрузка переменных из .env
source .env

# Использование SSH ключа
ssh -i "$SSH_KEY_PATH" "$SSH_REMOTE_HOST" "команда"

# Подключение к Mac Studio
ssh "$MAC_STUDIO_HOST" "команда"
```

### В Python:

```python
import os
from dotenv import load_dotenv

load_dotenv()

SSH_KEY_PATH = os.getenv("SSH_KEY_PATH")
SSH_REMOTE_HOST = os.getenv("SSH_REMOTE_HOST")
MAC_STUDIO_HOST = os.getenv("MAC_STUDIO_HOST")
```

---

## ✅ ПРОВЕРКА

**На Mac Studio:**
```bash
source .env
echo "SSH ключ: $SSH_KEY_PATH"
ls -la "$SSH_KEY_PATH"
```

**На Mac Studio:**
```bash
source ~/.env
echo "SSH ключ: $SSH_KEY_PATH"
ls -la "$SSH_KEY_PATH"
```

---

## 🔄 ОБНОВЛЕНИЕ СКРИПТОВ

Все скрипты, использующие SSH, теперь могут использовать переменные окружения:

- `scripts/start_mac_studio_tunnels.sh` - использует `$SSH_KEY_PATH` и `$SSH_REMOTE_HOST`
- `scripts/copy_ssh_key_to_mac_studio.sh` - использует `$MAC_STUDIO_HOST`
- `knowledge_os/app/tunnel_manager.py` - использует `$SSH_REMOTE_HOST` и `$SSH_REMOTE_PASS`

---

**Создано:** 2026-01-25
