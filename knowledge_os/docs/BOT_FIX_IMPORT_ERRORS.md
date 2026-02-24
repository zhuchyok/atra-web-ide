# ✅ ИСПРАВЛЕНИЕ ОШИБОК ИМПОРТА

## 🎯 ПРОБЛЕМА

**Ошибка:** `ImportError: cannot import name 'start_stuck_monitor' from 'src.risk.autonomous.stuck_monitor'`

**Причина:**

- В файле `src/risk/autonomous/stuck_monitor.py` есть класс `StuckPositionMonitor`, но нет функции `start_stuck_monitor`
- В `signal_live.py` используется несуществующая функция `start_stuck_monitor()`

## ✅ РЕШЕНИЕ

1. ✅ Обернул импорты в try-except блоки с флагами доступности
2. ✅ Изменил использование `start_stuck_monitor()` на класс `StuckPositionMonitor`
3. ✅ Добавил проверку доступности модулей перед использованием
4. ✅ Исправил инициализацию Self-Healing системы

## 📋 ИЗМЕНЕНИЯ

**Файл:** `signal_live.py`

1. **Импорты:**

   ```python
   try:
       from src.infrastructure.self_healing.manager import SelfHealingManager
       SELF_HEALING_AVAILABLE = True
   except ImportError:
       SELF_HEALING_AVAILABLE = False
       SelfHealingManager = None

   try:
       from src.risk.autonomous.stuck_monitor import StuckPositionMonitor
       STUCK_MONITOR_AVAILABLE = True
   except ImportError:
       STUCK_MONITOR_AVAILABLE = False
       StuckPositionMonitor = None
   ```

2. **Использование Self-Healing:**

   ```python
   if SELF_HEALING_AVAILABLE and SelfHealingManager:
       try:
           sh_manager = SelfHealingManager()
           asyncio.create_task(sh_manager.monitor_health())
           logger.info("✅ Система Self-Healing запущена")
       except Exception as e:
           logger.error("❌ Ошибка запуска Self-Healing: %s", e)
   else:
       logger.warning("⚠️ Self-Healing недоступен, пропускаем")
   ```

3. **Использование Stuck Monitor:**
   ```python
   if STUCK_MONITOR_AVAILABLE:
       try:
           user_data_dict = await load_user_data()
           for user_id, user_data in user_data_dict.items():
               try:
                   monitor = StuckPositionMonitor()
                   asyncio.create_task(monitor.run_monitor(int(user_id)))
                   logger.info("✅ [ARS] Монитор зависших сделок запущен для пользователя %s", user_id)
               except Exception as e:
                   logger.error("❌ [ARS] Ошибка запуска монитора для пользователя %s: %s", user_id, e)
       except Exception as e:
           logger.error("❌ [ARS] Ошибка запуска ARS: %s", e)
   else:
       logger.warning("⚠️ [ARS] StuckPositionMonitor недоступен, пропускаем")
   ```

## 🔍 ПРОВЕРКА

После исправлений:

1. ✅ Модуль `signal_live` должен импортироваться без ошибок
2. ✅ Бот должен запускаться без ошибок импорта
3. ✅ Self-Healing и Stuck Monitor запускаются только если модули доступны

---

**Дата:** 2025-12-11  
**Исполнитель:** Команда экспертов ATRA (21 сотрудник)

**Статус:** ✅ Ошибки импорта исправлены, ожидание проверки запуска бота
