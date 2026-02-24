# Установка Node.js

**Дата:** 26.01.2026  
**Проблема:** Node.js не установлен на системе

---

## 🔍 Диагностика показала

Node.js **не установлен** на вашей системе:

- ❌ Не найден в `/opt/homebrew/bin/node`
- ❌ Не найден в `/usr/local/bin/node`
- ❌ nvm не установлен
- ❌ Не доступен через `/usr/bin/env`

---

## ✅ Решение: Установить Node.js

### Вариант 1: Через Homebrew (рекомендуется для macOS)

```bash
# Установить Homebrew (если еще не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установить Node.js
brew install node

# Проверить установку
node --version
npm --version
```

### Вариант 2: Скачать установщик с официального сайта

1. Перейдите на https://nodejs.org/
2. Скачайте LTS версию для macOS
3. Запустите установщик
4. Следуйте инструкциям

### Вариант 3: Через nvm (Node Version Manager)

```bash
# Установить nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# Перезагрузить shell или выполнить:
source ~/.zshrc

# Установить Node.js LTS
nvm install --lts
nvm use --lts

# Проверить
node --version
npm --version
```

---

## 🚀 После установки

После установки Node.js:

1. **Перезапустите терминал** (или выполните `source ~/.zshrc`)

2. **Проверьте установку:**

   ```bash
   node --version
   npm --version
   ```

3. **Запустите Frontend:**

   ```bash
   cd /Users/bikos/Documents/atra-web-ide/frontend
   npm run dev
   ```

4. **Откройте в браузере:** http://localhost:3002

---

## 📝 Примечание

После установки Node.js через Homebrew или официальный установщик, он автоматически добавится в PATH. Если используете nvm, убедитесь, что nvm инициализирован в `.zshrc`.

---

_Инструкция создана: 26.01.2026_
