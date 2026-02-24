# ✅ ЕЖЕДНЕВНЫЕ ОТЧЕТЫ И БЭКАПЫ: НАСТРОЙКА ЗАВЕРШЕНА

**Дата:** 2025-12-14  
**Статус:** ✅ **НАСТРОЕНО**

---

## 📊 РАСПИСАНИЕ ОТЧЕТОВ

### **🌙 БЭКАПЫ БД** (ежедневно в 3:00)

- **Время:** Ежедневно в 3:00 UTC
- **Куда:** Telegram (CHAT_ID: 556251171)
- **Что:** SQL дамп базы данных Knowledge OS (сжатый .gz файл)
- **Команда:** `bash /root/knowledge_os/scripts/backup_db.sh`
- **Лог:** `/root/knowledge_os/logs/cron_backup.log`
- **Хранение:**
  - Последние 7 дней локально
  - Старые бэкапы автоматически удаляются
  - Опционально: синхронизация с S3 через rclone

**Содержимое бэкапа:**

- Полный дамп базы данных PostgreSQL
- Все таблицы, индексы, функции
- Все данные знаний, экспертов, задач

---

### **🌅 УТРЕННИЙ ОТЧЕТ ВИКТОРИИ** (ежедневно в 8:00)

- **Время:** Ежедневно в 8:00 UTC
- **Куда:** Telegram (CHAT_ID: 556251171)
- **Что:** Стратегический доклад для владельца холдинга
- **Команда:** `python3 /root/knowledge_os/app/victoria_morning_report.py`
- **Лог:** `/root/knowledge_os/logs/morning_report.log`

**Содержимое отчета:**

1. **💰 Финансовая аналитика:**
   - Расход токенов за последние 24 часа
   - Виртуальная стоимость операций
   - Эффективность использования ресурсов

2. **📊 Статус OKR:**
   - Текущие цели (Objectives)
   - Ключевые результаты (Key Results)
   - Прогресс выполнения (%)
   - Оставшееся время до дедлайна

3. **📉 Ликвидность знаний (ROI):**
   - Самые полезные знания (топ-3)
   - Количество использований
   - Домены знаний
   - Оценка эффективности

4. **🧠 Интеллектуальный аудит:**
   - Новые знания за ночь (последние 12 часов)
   - Домены новых знаний
   - Приоритетность новых знаний
   - Качество новых знаний

5. **🚀 Операционный план:**
   - Приоритеты для департаментов на сегодня
   - Задачи на день
   - Рекомендации по развитию

---

### **🌆 ВЕЧЕРНИЙ WEBHOOK ОТЧЕТ** (ежедневно в 20:00)

- **Время:** Ежедневно в 20:00 UTC
- **Куда:** Настроенные webhooks (Slack, Discord, Telegram)
- **Что:** Статистика за день
- **Команда:** `python3 -c "from app.webhook_manager import run_webhook_reports; import asyncio; asyncio.run(run_webhook_reports())"`
- **Лог:** `/root/knowledge_os/logs/webhook_reports.log`

**Содержимое отчета:**

- **Новые знания:** Количество созданных узлов знаний за день
- **Завершенные задачи:** Количество выполненных задач
- **Взаимодействия:** Количество взаимодействий с системой
- **Средний feedback:** Средняя оценка качества ответов
- **Эксперты:** Количество активных экспертов
- **Домены:** Количество активных доменов

**Настройка webhooks:**

Для получения вечерних отчетов через webhooks нужно настроить webhooks в системе:

```bash
ssh root@185.177.216.15
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
        events=['daily_report', 'weekly_report']
    )

    # Telegram
    await manager.register_webhook(
        'telegram',
        'https://api.telegram.org/botYOUR_TOKEN/sendMessage',
        events=['daily_report']
    )

    print('✅ Webhooks настроены')

asyncio.run(setup())
"
```

---

## ✅ ПРОВЕРКА НАСТРОЙКИ

### **Просмотреть задачи в crontab:**

```bash
ssh root@185.177.216.15
crontab -l | grep -E '(backup|victoria|webhook)'
```

**Ожидаемый результат:**

```
0 3 * * * bash /root/knowledge_os/scripts/backup_db.sh >> /root/knowledge_os/logs/cron_backup.log 2>&1
0 8 * * * cd /root/knowledge_os && python3 app/victoria_morning_report.py >> logs/morning_report.log 2>&1
0 20 * * * cd /root/knowledge_os && python3 -c "from app.webhook_manager import run_webhook_reports; import asyncio; asyncio.run(run_webhook_reports())" >> logs/webhook_reports.log 2>&1
```

---

## 🧪 ТЕСТОВЫЙ ЗАПУСК

### **Тестовый запуск бэкапа:**

```bash
ssh root@185.177.216.15
bash /root/knowledge_os/scripts/backup_db.sh
```

**Результат:** Бэкап будет отправлен в Telegram сразу же.

---

### **Тестовый запуск утреннего отчета:**

```bash
ssh root@185.177.216.15
cd /root/knowledge_os
python3 app/victoria_morning_report.py
```

**Результат:** Отчет будет отправлен в Telegram сразу же.

---

### **Тестовый запуск вечернего webhook отчета:**

```bash
ssh root@185.177.216.15
cd /root/knowledge_os
python3 -c "from app.webhook_manager import run_webhook_reports; import asyncio; asyncio.run(run_webhook_reports())"
```

**Результат:** Отчет будет отправлен через настроенные webhooks.

---

## 📝 ЛОГИ

Все отчеты и бэкапы логируются в следующие файлы:

- **Бэкапы:** `/root/knowledge_os/logs/cron_backup.log`
- **Утренние отчеты:** `/root/knowledge_os/logs/morning_report.log`
- **Webhook отчеты:** `/root/knowledge_os/logs/webhook_reports.log`

**Просмотр логов:**

```bash
ssh root@185.177.216.15
tail -f /root/knowledge_os/logs/cron_backup.log
tail -f /root/knowledge_os/logs/morning_report.log
tail -f /root/knowledge_os/logs/webhook_reports.log
```

---

## 🎯 ИТОГ

**Теперь вы будете получать:**

1. ✅ **📦 Ежедневные бэкапы БД** в Telegram (каждый день в 3:00)
2. ✅ **📊 Ежедневные утренние отчеты** от Виктории (каждый день в 8:00)
3. ✅ **📈 Ежедневные вечерние webhook отчеты** (каждый день в 20:00)

**Все отчеты будут приходить автоматически!**

---

**Автор:** Виктория (Team Lead)  
**Дата:** 2025-12-14
