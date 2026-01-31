# 📚 Отправка контекста чата в Veronica

**Дата:** 2026-01-26

---

## ✅ СПОСОБ 1: Через скрипт (рекомендуется)

```bash
cd ~/Documents/atra-web-ide
python3 scripts/send_chat_context_to_veronica.py
```

---

## ✅ СПОСОБ 2: Через curl напрямую

```bash
curl -X POST http://192.168.1.64:8011/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Изучи весь контекст миграции Docker контейнеров с Mac Studio на Mac Studio. Ключевые моменты: Mac Studio IP 192.168.1.64, пользователь bikos, все контейнеры перенесены, Knowledge OS работает. Изучи все документы миграции в проекте (FINAL_MIGRATION_REPORT.md, MIGRATION_STATUS.md, COMPLETE_MIGRATION_REPORT.md и другие). Запомни структуру проекта, созданные скрипты, процессы миграции. Будь готова отвечать на вопросы о миграции, контейнерах, структуре проекта. Используй Extended Thinking для глубокого анализа.",
    "max_steps": 30
  }' \
  --max-time 300
```

---

## 📋 КОНТЕКСТ ДЛЯ ИЗУЧЕНИЯ

Veronica должна изучить:

1. **Документы миграции:**
   - FINAL_MIGRATION_REPORT.md
   - MIGRATION_STATUS.md
   - COMPLETE_MIGRATION_REPORT.md
   - FINAL_DOCKER_CHECK.md
   - MIGRATION_FINAL_STATUS.md
   - CHECK_CONTAINERS_ON_MAC_STUDIO.md
   - MIGRATION_INSTRUCTIONS.md

2. **Скрипты:**
   - scripts/full_migration_Mac Studio_to_macstudio.sh
   - scripts/migrate_docker_to_mac_studio.sh
   - scripts/import_docker_from_Mac Studio.sh
   - scripts/migrate_root_containers.sh
   - scripts/import_root_containers.sh
   - scripts/check_and_start_containers.sh
   - START_ON_MAC_STUDIO.sh

3. **Структура проекта:**
   - knowledge_os/docker-compose.yml - основные сервисы
   - docker-compose.yml - корневые контейнеры
   - scripts/ - скрипты управления
   - docs/mac-studio/ - документация

---

## 🎯 ЧТО ДОЛЖНА ЗАПОМНИТЬ VERONICA

- Mac Studio IP: 192.168.1.64
- Пользователь Mac Studio: bikos
- Все контейнеры перенесены
- Knowledge OS работает
- Процессы миграции
- Структуру проекта
- Созданные скрипты

---

*Документ создан: 2026-01-26*
