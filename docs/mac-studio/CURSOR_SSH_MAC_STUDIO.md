# Подключение Cursor к проекту на Mac Studio через SSH

Как открыть проект **atra-web-ide** на Mac Studio с другой машины (ноутбук, другой Mac) через SSH и работать в Cursor как будто локально.

---

## 1. На Mac Studio: включить SSH

1. **Системные настройки** → **Общий доступ** (Sharing) → включить **Удалённый вход** (Remote Login).
2. Или в терминале на Mac Studio:
   ```bash
   sudo systemsetup -setremotelogin on
   ```
3. Узнать IP Mac Studio (в одной сети):
   ```bash
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
   Или: **Системные настройки** → **Сеть** → ваш Wi‑Fi/Ethernet → IP-адрес.

Подробнее: [SSH_ENABLE_MAC_STUDIO.md](SSH_ENABLE_MAC_STUDIO.md).

---

## 2. На своей машине: SSH-ключ (один раз)

Чтобы не вводить пароль каждый раз:

```bash
# Если ключа ещё нет
ssh-keygen -t ed25519 -C "cursor-mac-studio" -f ~/.ssh/id_ed25519_macstudio

# Скопировать ключ на Mac Studio (подставьте USER и IP Mac Studio)
ssh-copy-id -i ~/.ssh/id_ed25519_macstudio.pub USER@MAC_STUDIO_IP
```

Пример: `ssh-copy-id -i ~/.ssh/id_ed25519_macstudio.pub bikos@192.168.1.64`

В `~/.ssh/config` на своей машине можно добавить:

```
Host macstudio
    HostName 192.168.1.64
    User bikos
    IdentityFile ~/.ssh/id_ed25519_macstudio
```

Тогда подключение: `ssh macstudio`.

---

## 3. В Cursor: подключиться по Remote-SSH

1. Открыть **Command Palette**: `Cmd+Shift+P` (macOS) или `Ctrl+Shift+P` (Windows/Linux).
2. Ввести: **Remote-SSH: Connect to Host...**.
3. Выбрать **+ Add New SSH Host...**.
4. Ввести:
   ```text
   ssh USER@MAC_STUDIO_IP
   ```
   Пример: `ssh bikos@192.168.1.64`.  
   Если настроен `~/.ssh/config`, можно выбрать хост **macstudio**.
5. Выбрать конфиг для сохранения (обычно `~/.ssh/config`).
6. Cursor переподключится к Mac Studio. В списке хостов снова выбрать этот хост.
7. После подключения: **File → Open Folder** (или «Open Folder» в welcome) и указать путь к проекту **на Mac Studio**, например:
   ```text
   /Users/bikos/Documents/atra-web-ide
   ```
8. Cursor откроет папку проекта на удалённой машине; терминал и расширения работают на Mac Studio.

---

## 4. Проверка

- В левом нижнем углу Cursor должен быть индикатор **SSH: macstudio** (или ваш хост).
- Терминал внутри Cursor выполняется на Mac Studio.
- Запуск Docker, агентов (Victoria, MLX и т.д.) — на Mac Studio; с вашей машины вы только редактируете код и отдаёте команды по SSH.

---

## 5. Если Mac Studio в другой сети (интернет)

- Нужен доступ по SSH извне: проброс порта на роутере (порт 22 → IP Mac Studio) или VPN/туннель (Tailscale, Cloudflare Tunnel и т.п.).
- В Cursor тогда подключаться по публичному IP или hostname и порту (если не 22), например: `ssh -p 2222 bikos@your-public-ip`.

---

## Связанные документы

| Документ | Назначение |
|----------|------------|
| [SSH_ENABLE_MAC_STUDIO.md](SSH_ENABLE_MAC_STUDIO.md) | Включение SSH и проверка на Mac Studio |
| [SSH_KEYS_ENV_SETUP.md](SSH_KEYS_ENV_SETUP.md) | Ключи и переменные для скриптов |
| [MASTER_REFERENCE.md](../MASTER_REFERENCE.md) | Порты и компоненты (Victoria 8010, MLX 11435 и др.) |
