# Диагностика проблемы с Node.js

**Дата:** 26.01.2026  
**Проблема:** Node.js не найден в текущем shell

---

## 🔍 Причины

### Возможные причины:

1. **Node.js не установлен**
   - Node.js не установлен на системе
   - Решение: установить Node.js

2. **Node.js установлен, но не в PATH**
   - Node.js установлен, но путь не добавлен в переменную PATH
   - Решение: добавить путь в PATH или использовать полный путь

3. **Используется nvm, но не инициализирован**
   - Node.js установлен через nvm, но nvm не загружен в текущий shell
   - Решение: инициализировать nvm или использовать полный путь

4. **Shell не загружает конфигурацию**
   - .zshrc или .bashrc не загружается в текущем shell
   - Решение: загрузить конфигурацию вручную

5. **Используется неинтерактивный shell**
   - Текущий shell не загружает пользовательские настройки
   - Решение: использовать интерактивный shell или явно загрузить настройки

---

## ✅ Решения

### Вариант 1: Установить Node.js

```bash
# Через Homebrew
brew install node

# Или скачать с официального сайта
# https://nodejs.org/
```

### Вариант 2: Использовать полный путь

Если Node.js установлен, но не в PATH:

```bash
# Для Homebrew
/opt/homebrew/bin/node --version

# Для nvm
~/.nvm/versions/node/v20.0.0/bin/node --version
```

### Вариант 3: Загрузить nvm

Если используется nvm:

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use default
```

### Вариант 4: Добавить в PATH

Добавить в ~/.zshrc или ~/.bashrc:

```bash
# Для Homebrew
export PATH="/opt/homebrew/bin:$PATH"

# Для nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

---

## 🔧 Быстрое решение

Для запуска frontend прямо сейчас:

1. Откройте терминал в Cursor (`` Ctrl+` ``)
2. Выполните:
   ```bash
   cd /Users/bikos/Documents/atra-web-ide/frontend
   npm run dev
   ```

Терминал в Cursor обычно имеет правильный PATH.

---

_Диагностика выполнена: 26.01.2026_
