# Чеклист ручных проверок (по желанию)

**Когда использовать:** после крупных изменений в чате, Victoria, делегировании или мониторинге; перед релизом; при восстановлении после сбоев.  
**Связь:** [VERIFICATION_AND_FULL_PICTURE_PLAN.md](.cursor/plans/VERIFICATION_AND_FULL_PICTURE_PLAN.md) §4 (чеклист верификации), [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md).

---

## 1. Полный сценарий чата (эхо / 503)

- [ ] Открыть чат (frontend http://localhost:3000), отправить сообщение. Убедиться, что ответ приходит и **не является копией запроса** (эхо). При необходимости проверить несколько фраз.
- [ ] При перегрузке: имитировать много одновременных запросов (или дождаться лимита слотов Victoria). Ожидать **503** с заголовком **Retry-After** вместо 500. Настройка: `MAX_CONCURRENT_VICTORIA` в backend.

---

## 2. Ручная проверка делегирования (простой шаг → Veronica)

- [ ] Отправить в чат запрос, который должен выполнить Veronica (простое одношаговое действие): например «покажи список файлов в корне проекта» или «выведи содержимое README». В логах Victoria/Veronica или в ответе убедиться, что запрос обработан через Veronica (локальный исполнитель), а не через тяжёлую цепочку Enhanced.
- [ ] См. логику: [VICTORIA_TASK_CHAIN_FULL.md](VICTORIA_TASK_CHAIN_FULL.md), PREFER_EXPERTS_FIRST, `_should_delegate_task` / `_is_simple_veronica_request`.

---

## 3. Prometheus «Data source is working» в UI Grafana

- [ ] Открыть Grafana Web IDE: http://localhost:3002 (логин admin/admin).
- [ ] **Configuration** → **Data sources** → выбрать Prometheus. Нажать **Save & Test**. Должно быть сообщение **«Data source is working»** (или аналог для вашей версии).
- [ ] Если ошибка — проверить, что контейнер Prometheus (atra-prometheus / порт 9091) запущен и что в provisioning задан верный URL (например `http://atra-prometheus:9090` для Web IDE или как в [grafana/README.md](grafana/README.md)).

---

## 4. Launchd (автозапуск system_auto_recovery)

- [ ] Проверить, что задание launchd установлено (если настроено):  
  `launchctl list | grep -i atra` (или имя из `setup_system_auto_recovery.sh`).
- [ ] При необходимости установить один раз: `bash scripts/setup_system_auto_recovery.sh` (создаёт plist, загружает задание). Тогда после перезагрузки хоста скрипт восстановления будет запускаться по расписанию (каждые 5 мин).
- [ ] Документация: [LIVING_ORGANISM_PREVENTION.md](LIVING_ORGANISM_PREVENTION.md), [system_auto_recovery.sh](../scripts/system_auto_recovery.sh).

---

*Результаты при необходимости фиксировать в плане верификации (раздел «Результаты верификации») или в CHANGES_FROM_OTHER_CHATS.*
