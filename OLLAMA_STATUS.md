# Ollama Status - ATRA Web IDE

**Дата:** 2026-01-26

## ✅ Статус

**Ollama работает и доступна!**

### Проверка:
- ✅ Ollama запущена на порту 11434
- ✅ Backend видит Ollama как `healthy`
- ✅ Доступна модель: `tinyllama:1.1b-chat`
- ✅ Автозапуск настроен через `brew services`

### Команды:

```bash
# Проверка статуса
curl http://localhost:11434/api/tags

# Запуск (если остановлена)
brew services start ollama
# или
ollama serve

# Остановка
brew services stop ollama
```

### Модели:

Доступные модели в Ollama:
- `tinyllama:1.1b-chat` (~700MB) - быстрая модель для чата

### Настройка:

Backend использует:
- URL: `http://localhost:11434` (для локального запуска)
- URL: `http://host.docker.internal:11434` (для Docker контейнеров)

### Автозапуск:

Ollama настроена на автозапуск через Homebrew:
```bash
brew services start ollama
```

При перезагрузке Mac Studio Ollama запустится автоматически.

---

**Статус:** ✅ Работает
