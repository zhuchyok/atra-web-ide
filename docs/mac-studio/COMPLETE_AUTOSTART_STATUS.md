# ✅ Полный статус автозапуска корпорации ATRA на Mac Studio

**Дата:** 2026-01-25  
**Статус:** ✅ **ПОЧТИ ВСЕ НАСТРОЕНО, НУЖНО ПРОВЕРИТЬ НЕСКОЛЬКО КОМПОНЕНТОВ**

---

## 🎯 ЧТО ЗАПУСТИТСЯ АВТОМАТИЧЕСКИ ПРИ ПЕРЕЗАГРУЗКЕ

### ✅ **АВТОМАТИЧЕСКИ ЗАПУСТИТСЯ:**

#### 1. Docker Desktop

- **Статус:** ✅ Настроен (`StartAtLogin = true`)
- **Проверка:** `defaults read com.docker.docker StartAtLogin` → `1`
- **Действие:** Запускается автоматически при входе в систему

#### 2. Docker контейнеры (с `restart: always`):

- ✅ **db** (PostgreSQL) — `restart: always`
- ✅ **victoria-agent** — `restart: always`
- ✅ **veronica-agent** — `restart: always`

**Что это значит:**

- При запуске Docker Desktop эти контейнеры автоматически запускаются
- Если контейнер упал, Docker автоматически перезапустит его

#### 3. Docker контейнеры (с `restart: unless-stopped`):

- ✅ **prometheus** — `restart: unless-stopped`
- ✅ **grafana** — `restart: unless-stopped`
- ✅ **elasticsearch** — `restart: unless-stopped`
- ✅ **kibana** — `restart: unless-stopped`

**Что это значит:**

- Запускаются автоматически при старте Docker
- НЕ перезапускаются если были остановлены вручную (`docker stop`)
- Перезапускаются если упали сами

---

### ⚠️ **ТРЕБУЕТ ПРОВЕРКИ/НАСТРОЙКИ:**

#### 1. Ollama (LLM модели)

- **Статус:** ⚠️ Требует проверки
- **Вопрос:** Запускается ли Ollama автоматически?
- **Проверка:**
  ```bash
  brew services list | grep ollama
  # Или
  launchctl list | grep ollama
  ```
- **Настройка (если не настроено):**
  ```bash
  brew services start ollama
  # Или через launchd
  ```

#### 2. Victoria MCP Server (порт 8012)

- **Статус:** ⚠️ Требует настройки через launchd
- **Настройка:**
  ```bash
  bash scripts/victoria/quick_victoria_autostart.sh
  ```
- **Результат:** MCP сервер будет запускаться автоматически

#### 3. Автономные системы (Orchestrator, Nightly Learner)

- **Статус:** ⚠️ Требует настройки через launchd
- **Настройка:**
  ```bash
  bash scripts/start_autonomous_systems.sh
  ```
- **Результат:** Автономные системы будут запускаться автоматически

---

## 📋 ПОЛНЫЙ ЧЕКЛИСТ АВТОЗАПУСКА

### ✅ Уже настроено:

- [x] Docker Desktop автозапуск (`StartAtLogin = true`)
- [x] Контейнеры с `restart: always` (db, victoria, veronica)
- [x] Контейнеры с `restart: unless-stopped` (prometheus, grafana, elasticsearch, kibana)

### ⚠️ Требует проверки/настройки:

- [ ] Ollama автозапуск (проверить `brew services list`)
- [ ] Victoria MCP Server (настроить через `quick_victoria_autostart.sh`)
- [ ] Автономные системы (настроить через `start_autonomous_systems.sh`)

---

## 🚀 БЫСТРАЯ НАСТРОЙКА ПОЛНОГО АВТОЗАПУСКА

### Выполните один раз:

```bash
cd /Users/zhuchyok/Documents/atra-web-ide

# 1. Проверка Docker Desktop (уже настроен ✅)
defaults read com.docker.docker StartAtLogin
# Должно вернуть: 1

# 2. Настройка Ollama автозапуска
brew services start ollama
# Или проверьте: brew services list | grep ollama

# 3. Настройка Victoria MCP Server
bash scripts/victoria/quick_victoria_autostart.sh

# 4. Настройка автономных систем
bash scripts/start_autonomous_systems.sh
```

---

## 📊 ЧТО ЗАПУСТИТСЯ ПРИ ПЕРЕЗАГРУЗКЕ

### Автоматически (после настройки):

1. ✅ **Docker Desktop** — при входе в систему
2. ✅ **Docker контейнеры:**
   - db (PostgreSQL)
   - victoria-agent
   - veronica-agent
   - prometheus
   - grafana
   - elasticsearch
   - kibana
   - knowledge_os_api (если есть)
3. ✅ **Ollama** — если настроен через `brew services`
4. ✅ **Victoria MCP Server** — если настроен через launchd
5. ✅ **Автономные системы** — если настроены через launchd

---

## 🔍 ПРОВЕРКА ПОСЛЕ ПЕРЕЗАГРУЗКИ

### Через 2-3 минуты после перезагрузки:

```bash
# 1. Проверка Docker
docker ps

# 2. Проверка Ollama
curl http://localhost:11434/api/tags

# 3. Проверка Victoria
curl http://localhost:8010/health

# 4. Проверка Veronica
curl http://localhost:8011/health

# 5. Проверка MCP Server
curl http://localhost:8012/sse

# 6. Проверка мониторинга
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3001/api/health  # Grafana
curl http://localhost:9200/_cluster/health  # Elasticsearch
curl http://localhost:5601/api/status  # Kibana
```

---

## ✅ ИТОГ

### После полной настройки:

**ДА, все запустится автоматически при перезагрузке Mac Studio!**

1. ✅ Docker Desktop запустится автоматически
2. ✅ Все Docker контейнеры запустятся автоматически
3. ✅ Ollama запустится автоматически (если настроен)
4. ✅ Victoria MCP Server запустится автоматически (если настроен)
5. ✅ Автономные системы запустятся автоматически (если настроены)

**Осталось только:**

- Проверить/настроить Ollama автозапуск
- Настроить Victoria MCP Server (1 команда)
- Настроить автономные системы (1 команда)

**Время настройки: ~5 минут**

---

_Документация создана 2026-01-25_
