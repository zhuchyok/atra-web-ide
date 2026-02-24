# 📋 ВСЕ ЗАДАЧИ ДЛЯ VICTORIA - ВЫПОЛНИТЬ ВСЕ

**Дата:** 2026-01-26  
**Цель:** Выполнить все задачи, созданные сегодня

---

## 🎯 ПОЛНЫЙ СПИСОК ЗАДАЧ

### 1. Проверка и запуск всех контейнеров Knowledge OS ⚠️

**Текущий статус:**

- ✅ Victoria (8010) - работает
- ✅ Veronica (8011) - работает
- ✅ Knowledge OS API (8003) - работает
- ✅ Knowledge OS Database (5432) - работает
- ✅ Knowledge OS Worker - работает
- ⚠️ Elasticsearch (9200) - НЕ ЗАПУЩЕН
- ⚠️ Kibana (5601) - НЕ ЗАПУЩЕН
- ⚠️ Prometheus (9090) - НЕ ЗАПУЩЕН
- ⚠️ Grafana (3001) - НЕ ЗАПУЩЕН

**Действие:**

```bash
cd ~/Documents/atra-web-ide
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
docker-compose -f knowledge_os/docker-compose.yml up -d
docker-compose -f knowledge_os/docker-compose.yml ps
```

---

### 2. Проверка доступности всех сервисов ⚠️

**Проверить каждый сервис:**

```bash
# Knowledge OS сервисы
curl http://localhost:8010/health  # Victoria
curl http://localhost:8011/health  # Veronica
curl http://localhost:8003/health  # Knowledge OS API
curl http://localhost:11434/api/tags  # Ollama/MLX

# Мониторинг
curl http://localhost:9200/_cluster/health  # Elasticsearch
curl http://localhost:5601/api/status  # Kibana
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3001/api/health  # Grafana
```

**Создать отчет о доступности каждого сервиса.**

---

### 3. Проверка доступности с Mac Studio ⚠️

**Проверить доступность с Mac Studio (192.168.1.38):**

```bash
# С Mac Studio
curl http://192.168.1.64:8010/health  # Victoria
curl http://192.168.1.64:8011/health  # Veronica
curl http://192.168.1.64:8003/health  # Knowledge OS API
curl http://192.168.1.64:11434/api/tags  # Ollama/MLX
```

**Зафиксировать результаты.**

---

### 4. Настройка автозапуска контейнеров ⚠️

**Создать launchd service для автозапуска:**

```bash
cd ~/Documents/atra-web-ide
bash scripts/create_mac_studio_autostart.sh
```

**Или создать вручную:**

- Файл: `~/Library/LaunchAgents/com.atra.mac-studio-startup.plist`
- Запуск: `scripts/start_all_on_mac_studio.sh`
- При загрузке системы и каждые 5 минут

**Проверить работу автозапуска.**

---

### 5. Обновление PLAN.md ⚠️

**Обновить PLAN.md:**

1. Зафиксировать завершение миграции
2. Обновить IP адреса:
   - Заменить `192.168.1.43` на `192.168.1.64`
   - Заменить `zhuchyok` на `bikos` (где нужно)
3. Обновить статус сервисов:
   - Knowledge OS контейнеры: ✅ Работают
   - Корневые контейнеры: ✅ Импортированы
   - Мониторинг: ⚠️ Требует запуска
4. Добавить информацию о миграции
5. Обновить дату последнего обновления

---

### 6. Обновление всех IP адресов в проекте ⚠️

**Найти и обновить все упоминания старого IP:**

```bash
# Найти все файлы с 192.168.1.43
grep -r "192.168.1.43" --include="*.md" --include="*.sh" --include="*.py" .

# Обновить на 192.168.1.64
# (кроме документации, где может быть историческая информация)
```

**Файлы для обновления:**

- Документация (где актуально)
- Скрипты
- Конфигурационные файлы

---

### 7. Создание финального отчета ⚠️

**Создать файл: `MIGRATION_COMPLETE_FINAL.md`**

Содержание:

- ✅ Что было сделано
- ✅ Текущий статус всех сервисов
- ✅ Доступность сервисов
- ✅ Настроенный автозапуск
- ✅ Обновленная документация
- 📋 Инструкции по использованию
- 🔧 Команды для управления

---

### 8. Проверка и исправление скриптов ⚠️

**Проверить все созданные скрипты:**

1. `scripts/start_all_on_mac_studio.sh` - работает ли?
2. `scripts/check_and_start_containers.sh` - работает ли?
3. `START_ON_MAC_STUDIO.sh` - работает ли?
4. `scripts/create_mac_studio_autostart.sh` - работает ли?

**Исправить ошибки, если есть.**

---

### 9. Проверка volumes и данных ⚠️

**Проверить импортированные volumes:**

```bash
docker volume ls
docker volume inspect knowledge_os_postgres_data
docker volume inspect atra-postgres-data
```

**Убедиться, что данные на месте.**

---

### 10. Тестирование полного цикла ⚠️

**Протестировать:**

1. Остановить все контейнеры
2. Запустить через `scripts/start_all_on_mac_studio.sh`
3. Проверить, что все запустилось
4. Проверить доступность всех сервисов

---

## 🎯 КОМАНДА ДЛЯ VICTORIA

```
Прочитай файл ALL_TASKS_FOR_VICTORIA.md в корне проекта. Выполни ВСЕ задачи из списка последовательно. Используй Extended Thinking для планирования, Swarm Intelligence для координации с экспертами, и Hierarchical Orchestration для управления выполнением. После каждой задачи проверяй результат. Создай финальный отчет MIGRATION_COMPLETE_FINAL.md со всеми результатами.

Mac Studio: 192.168.1.64, пользователь: bikos, путь: ~/Documents/atra-web-ide
Docker PATH: /usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH
```

---

## 📋 ЧЕКЛИСТ ВЫПОЛНЕНИЯ

- [ ] 1. Запустить все контейнеры Knowledge OS
- [ ] 2. Проверить доступность всех сервисов
- [ ] 3. Проверить доступность с Mac Studio
- [ ] 4. Настроить автозапуск
- [ ] 5. Обновить PLAN.md
- [ ] 6. Обновить IP адреса в проекте
- [ ] 7. Создать финальный отчет
- [ ] 8. Проверить и исправить скрипты
- [ ] 9. Проверить volumes и данные
- [ ] 10. Протестировать полный цикл

---

_Задачи созданы: 2026-01-26_
