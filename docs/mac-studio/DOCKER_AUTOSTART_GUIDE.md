# 🐳 Автозапуск Docker и корпорации ATRA

**Дата:** 2026-01-25  
**Вопрос:** Нужно ли всегда запускать Docker вручную?

---

## ✅ ОТВЕТ: МОЖНО НАСТРОИТЬ АВТОЗАПУСК!

### Текущая ситуация:

**Да, сейчас нужно запускать Docker Desktop вручную**, но можно настроить автозапуск!

---

## 🚀 НАСТРОЙКА АВТОЗАПУСКА

### 1. **Автозапуск Docker Desktop**

#### Способ 1: Через настройки Docker Desktop (рекомендуется)

1. Откройте **Docker Desktop**
2. Перейдите в **Settings** (⚙️) → **General**
3. Включите **"Start Docker Desktop when you log in"**
4. Готово! Docker будет запускаться автоматически при входе в систему

#### Способ 2: Через командную строку

```bash
defaults write com.docker.docker 'StartAtLogin' -bool true
```

Проверка:

```bash
defaults read com.docker.docker 'StartAtLogin'
# Должно вернуть: 1 (true)
```

---

### 2. **Автозапуск контейнеров**

**Хорошая новость:** Контейнеры уже настроены с `restart: always`!

В `knowledge_os/docker-compose.yml`:

```yaml
services:
  db:
    restart: always # ← Автоматический перезапуск

  victoria-agent:
    restart: always # ← Автоматический перезапуск

  veronica-agent:
    restart: always # ← Автоматический перезапуск
```

**Что это значит:**

- Когда Docker Desktop запускается, контейнеры автоматически запускаются
- Если контейнер упал, Docker автоматически перезапустит его
- После перезагрузки Mac контейнеры запустятся автоматически

---

## 📋 ЧТО ТРЕБУЕТ DOCKER

### Сервисы в Docker:

1. **PostgreSQL (Knowledge OS DB)** - база данных
2. **Victoria Agent** - Team Lead (порт 8010)
3. **Veronica Agent** - Web Researcher (порт 8011)
4. **Knowledge OS API** - REST API (порт 8000)
5. **Knowledge OS Worker** - обработка задач
6. **Redis** - блокировки и кэш

### Что НЕ требует Docker:

- **MLX/Ollama** - работает отдельно (порт 11434)
- **Orchestrator** - запускается через скрипты (фоновые процессы)
- **Nightly Learner** - запускается через скрипты (фоновые процессы)

---

## 🔄 ПОЛНЫЙ АВТОЗАПУСК (после настройки)

### После настройки автозапуска Docker Desktop:

1. **При входе в Mac:**
   - ✅ Docker Desktop запускается автоматически
   - ✅ Контейнеры запускаются автоматически (restart: always)
   - ✅ Все сервисы доступны

2. **Что нужно запустить вручную (опционально):**
   - Orchestrator (каждые 5 минут) - можно настроить через launchd
   - Nightly Learner (ежедневно) - можно настроить через launchd

---

## 🛠️ БЫСТРАЯ НАСТРОЙКА

### Один раз выполните:

```bash
cd /Users/zhuchyok/Documents/atra-web-ide

# 1. Настройка автозапуска Docker Desktop
bash scripts/setup_docker_autostart.sh

# 2. Настройка автозапуска Orchestrator и Nightly Learner
bash scripts/start_autonomous_systems.sh
```

### Или вручную:

1. **Docker Desktop:**
   - Откройте Docker Desktop
   - Settings → General → "Start Docker Desktop when you log in" ✅

2. **Контейнеры:**
   - Уже настроены с `restart: always` ✅
   - Запустятся автоматически при старте Docker

---

## 📊 ТЕКУЩИЙ СТАТУС

### Что уже настроено:

- ✅ Контейнеры с `restart: always` - автоматический перезапуск
- ✅ Скрипты для автозапуска Orchestrator и Nightly Learner

### Что нужно настроить:

- ⚠️ Автозапуск Docker Desktop (через настройки или defaults)

---

## 💡 РЕКОМЕНДАЦИИ

### Вариант 1: Полный автозапуск (рекомендуется)

1. Настройте автозапуск Docker Desktop
2. После перезагрузки Mac всё запустится автоматически

### Вариант 2: Ручной запуск

Если не хотите автозапуск Docker Desktop:

```bash
# Запуск Docker Desktop
open -a Docker

# Подождите 10-15 секунд, затем:
bash scripts/start_full_corporation.sh
```

### Вариант 3: Проверка и запуск

Скрипт автоматически проверит и запустит всё:

```bash
bash scripts/start_full_corporation.sh
# Скрипт проверит Docker и запустит всё необходимое
```

---

## ✅ ИТОГ

**Ответ:** Нет, не нужно всегда запускать Docker вручную!

**После настройки:**

1. ✅ Docker Desktop запускается автоматически при входе в Mac
2. ✅ Контейнеры запускаются автоматически (restart: always)
3. ✅ Всё работает без ручного запуска

**Настройка занимает 2 минуты:**

- Включить "Start Docker Desktop when you log in" в настройках
- Готово!

---

_Руководство создано 2026-01-25_
