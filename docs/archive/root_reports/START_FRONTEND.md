# 🚀 Запуск Frontend

**Дата:** 26.01.2026

---

## ⚠️ Проблема

Node.js не найден в текущем shell окружении. Frontend нужно запустить вручную.

---

## ✅ Решение

### Вариант 1: Через терминал Cursor (рекомендуется)

1. Откройте встроенный терминал в Cursor (`` Ctrl+` `` или `View > Terminal`)
2. Выполните:
   ```bash
   cd /Users/bikos/Documents/atra-web-ide/frontend
   npm run dev
   ```

### Вариант 2: Через системный терминал

1. Откройте Terminal.app
2. Выполните:
   ```bash
   cd /Users/bikos/Documents/atra-web-ide/frontend
   npm run dev
   ```

### Вариант 3: Если npm не найден

Установите Node.js:

```bash
# Через Homebrew
brew install node

# Или скачайте с официального сайта
# https://nodejs.org/
```

---

## ✅ Текущий статус

- ✅ **Backend:** Работает на http://localhost:8080
- ✅ **Ollama:** Работает на http://localhost:11434
- ⚠️ **Frontend:** Требуется запуск вручную

---

## 🎯 После запуска Frontend

Откройте в браузере: **http://localhost:3002**

Приложение будет готово к работе!

---

_Инструкция создана: 26.01.2026_
