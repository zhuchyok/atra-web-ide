# 🚀 ОТКРЫТИЕ ПРОЕКТА ATRA-WEB-IDE В CURSOR

**Дата:** 2026-01-26

---

## ✅ ПРОЕКТ ГОТОВ

- ✅ Docker образы импортированы (4 образа)
- ✅ Конфигурация настроена (.env, .cursorrules)
- ✅ Структура проекта подготовлена
- ✅ Размер проекта: 764 MB

---

## 📂 ОТКРЫТИЕ В CURSOR

### Шаг 1: Открыть проект

1. **В Cursor:**
   - `File → Open Folder...`
   - Выбрать: `/Users/bikos/Documents/atra-web-ide`
   - Нажать: "Open"

2. **Или через терминал:**
   ```bash
   cd ~/Documents/atra-web-ide
   cursor .
   ```

### Шаг 2: Cursor автоматически обнаружит

- ✅ `.cursorrules` - правила проекта
- ✅ Структуру проекта (backend, frontend, knowledge_os)
- ✅ Конфигурацию Docker

---

## 🚀 ЗАПУСК СЕРВИСОВ

После открытия проекта в Cursor:

### 1. Остановить atra (если запущен)

```bash
cd ~/Documents/dev/atra
docker-compose down
```

### 2. Запустить atra-web-ide

```bash
cd ~/Documents/atra-web-ide

# Knowledge OS
docker-compose -f knowledge_os/docker-compose.yml up -d

# Web IDE
docker-compose up -d
```

### 3. Проверить сервисы

```bash
curl http://localhost:8010/health  # Victoria
curl http://localhost:8011/health  # Veronica
curl http://localhost:8080/health  # Backend
open http://localhost:3000         # Frontend
```

---

## 📊 ПОРТЫ

| Сервис   | Порт | URL                   |
| -------- | ---- | --------------------- |
| Frontend | 3000 | http://localhost:3000 |
| Backend  | 8080 | http://localhost:8080 |
| Victoria | 8010 | http://localhost:8010 |
| Veronica | 8011 | http://localhost:8011 |

---

## 💡 РАБОТА В CURSOR

После открытия проекта:

1. **Виктория (Team Lead)** будет доступна через `.cursorrules`
2. Все эксперты команды активированы
3. Проект готов к разработке

---

**Проект готов к работе!** 🎉

_Создано: 2026-01-26_
