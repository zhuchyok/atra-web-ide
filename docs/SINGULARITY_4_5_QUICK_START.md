# 🚀 SINGULARITY 4.5: БЫСТРЫЙ СТАРТ

**Дата:** 2025-12-14  
**Версия:** Singularity 4.5

---

## 📋 ЧТО НУЖНО СДЕЛАТЬ

После деплоя всех файлов на сервер осталось выполнить несколько шагов для полного запуска системы.

---

## ⚡ БЫСТРЫЙ СТАРТ (АВТОМАТИЧЕСКИ)

### **Использование скрипта:**

```bash
cd knowledge_os
bash scripts/quick_start_4_5.sh
```

**Скрипт автоматически:**
1. ✅ Применит все миграции БД
2. ✅ Запустит тесты
3. ✅ Сгенерирует документацию
4. ✅ Проверит статус системы

---

## 📝 РУЧНОЙ СТАРТ (ПОШАГОВО)

### **Шаг 1: Применить миграции БД** ⚠️ ОБЯЗАТЕЛЬНО

```bash
ssh root@185.177.216.15
cd /root/knowledge_os

# Найти путь к psql
which psql || find /usr -name psql 2>/dev/null

# Применить все миграции
psql -U admin -d knowledge_os -f db/migrations/add_knowledge_links_table.sql
psql -U admin -d knowledge_os -f db/migrations/add_contextual_memory.sql
psql -U admin -d knowledge_os -f db/migrations/add_webhooks_table.sql
psql -U admin -d knowledge_os -f db/migrations/add_security_tables.sql
psql -U admin -d knowledge_os -f db/migrations/add_performance_optimizations.sql
psql -U admin -d knowledge_os -f db/migrations/add_multilanguage_support.sql
```

**Или использовать скрипт:**

```bash
bash scripts/apply_all_migrations.sh
```

---

### **Шаг 2: Запустить тесты**

```bash
cd /root/knowledge_os
bash tests/run_tests.sh
```

**Ожидаемый результат:**
```
test_knowledge_graph.py::test_create_link PASSED
test_security.py::test_jwt_auth PASSED
...
```

---

### **Шаг 3: Сгенерировать документацию**

```bash
cd /root/knowledge_os
python3 app/doc_generator.py
```

**Результат:**
- `docs/auto_generated/code_documentation.md`
- `docs/auto_generated/api_documentation.md`
- `docs/auto_generated/usage_examples.md`
- `docs/auto_generated/tutorials.md`

---

### **Шаг 4: Обновить cron для автоматических задач**

```bash
crontab -e
```

**Добавить:**

```cron
# Мониторинг (каждые 5 минут)
*/5 * * * * cd /root/knowledge_os && python3 app/enhanced_monitor.py >> logs/cron_monitor.log 2>&1

# Orchestrator (каждые 30 минут)
*/30 * * * * cd /root/knowledge_os && python3 app/enhanced_orchestrator.py >> logs/orchestrator.log 2>&1

# Иммунитет (каждые 6 часов)
0 */6 * * * cd /root/knowledge_os && python3 app/enhanced_immunity.py >> logs/immunity.log 2>&1

# Global Scout (каждые 12 часов)
0 */12 * * * cd /root/knowledge_os && python3 app/global_scout.py >> logs/global_scout.log 2>&1

# Auto-Translation (каждые 24 часа в 2:00)
0 2 * * * cd /root/knowledge_os && python3 -c 'from app.translator import run_auto_translation_cycle; import asyncio; asyncio.run(run_auto_translation_cycle())' >> logs/auto_translation.log 2>&1

# Performance Optimization (каждые 6 часов)
0 */6 * * * cd /root/knowledge_os && python3 app/performance_optimizer.py >> logs/performance.log 2>&1

# Expert Evolution (каждые 24 часа в 1:00)
0 1 * * * cd /root/knowledge_os && python3 app/enhanced_expert_evolver.py >> logs/expert_evolution.log 2>&1

# Nightly Learner (каждые 24 часа в 3:00)
0 3 * * * cd /root/knowledge_os && python3 app/nightly_learner.py >> logs/nightly_learner.log 2>&1

# Бэкапы (ежедневно в 3:00)
0 3 * * * bash /root/knowledge_os/scripts/backup_db.sh >> /root/knowledge_os/logs/cron_backup.log 2>&1
```

---

### **Шаг 5: Настроить Webhooks (опционально)**

```bash
cd /root/knowledge_os
python3 -c "
from app.webhook_manager import WebhookManager
import asyncio

async def setup():
    manager = WebhookManager()
    
    # Slack
    await manager.register_webhook(
        'slack',
        'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
        events=['knowledge_created', 'expert_hired', 'task_completed']
    )
    
    # Telegram
    await manager.register_webhook(
        'telegram',
        'https://api.telegram.org/botYOUR_TOKEN/sendMessage',
        events=['knowledge_created', 'expert_hired']
    )
    
    print('✅ Webhooks настроены')

asyncio.run(setup())
"
```

---

### **Шаг 6: Запустить REST API (опционально)**

```bash
cd /root/knowledge_os
python3 app/rest_api.py
```

**Или через systemd для постоянной работы:**

```bash
# Создать файл /etc/systemd/system/knowledge-os-api.service
cat > /etc/systemd/system/knowledge-os-api.service << 'EOF'
[Unit]
Description=Knowledge OS REST API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/knowledge_os
ExecStart=/usr/bin/python3 app/rest_api.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Запустить
systemctl daemon-reload
systemctl enable knowledge-os-api
systemctl start knowledge-os-api
```

---

## ✅ ПРОВЕРКА РАБОТОСПОСОБНОСТИ

### **Проверка таблиц БД:**

```bash
psql -U admin -d knowledge_os -c "\dt"
```

**Должны быть созданы:**
- `tasks`
- `knowledge_links`
- `user_preferences`
- `interaction_patterns`
- `webhooks`
- `users`
- `roles`
- `permissions`
- `audit_logs`
- `knowledge_translations`
- `ui_translations`
- `user_language_preferences`

### **Проверка модулей:**

```bash
cd /root/knowledge_os
python3 -c "
import sys
sys.path.insert(0, 'app')

# Проверка импортов
from global_scout import GlobalScout
from knowledge_graph import KnowledgeGraph
from contextual_learner import ContextualMemory
from translator import KnowledgeTranslator
from security import SecurityManager

print('✅ Все модули импортируются успешно')
"
```

### **Проверка тестов:**

```bash
cd /root/knowledge_os
bash tests/run_tests.sh
```

---

## 🎯 ГОТОВО!

После выполнения всех шагов система **Singularity 4.5** полностью готова к работе!

**Автор:** Виктория (Team Lead)  
**Дата:** 2025-12-14

