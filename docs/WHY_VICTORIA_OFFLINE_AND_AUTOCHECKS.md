# Почему Victoria не в сети и где автопроверки

## Почему Victoria может быть недоступна

1. **Victoria живёт в отдельном стеке**  
   Контейнер `victoria-agent` описан в **knowledge_os/docker-compose.yml**, а не в корневом **docker-compose.yml**.  
   При запуске только `docker-compose up -d` из корня поднимаются только frontend и backend — Victoria и Veronica не стартуют.

2. **Автопроверки не настроены**  
   Скрипт самовосстановления (`system_auto_recovery.sh`) запускается по расписанию только если один раз выполнен:
   ```bash
   bash scripts/setup_system_auto_recovery.sh
   ```
   Без этого launchd не загружен, скрипт не крутится, Victoria никто не поднимает.

3. **Контейнер упал после старта**  
   Даже если Knowledge OS когда-то поднимали, контейнер Victoria мог завершиться (OOM, ошибка). До правок автовосстановление не делало явный перезапуск именно Victoria.

---

## Где наши автопроверки

| Что | Где | Когда срабатывает |
|-----|-----|-------------------|
| **Самовосстановление** | `scripts/system_auto_recovery.sh` | При загрузке и каждые **5 минут** (если настроен launchd) |
| **Настройка launchd** | `scripts/setup_system_auto_recovery.sh` | Один раз вручную — после этого скрипт самовосстановления запускается автоматически |
| **Проверка и старт контейнеров** | `scripts/check_and_start_containers.sh` | Вручную; при запуске проверяет Victoria и при необходимости поднимает её |
| **Cron (orchestrator/nightly)** | `scripts/ensure_autonomous_systems.sh` | Настраивает crontab; задачи выполняются **внутри** victoria-agent — если контейнер не запущен, cron не поможет |

---

## Что сделать, чтобы Victoria была в сети и автопроверки работали

### 1. Один раз включить автопроверки (launchd)

```bash
cd /Users/bikos/Documents/atra-web-ide
bash scripts/setup_system_auto_recovery.sh
```

После этого:
- при загрузке системы и каждые 5 минут будет запускаться `system_auto_recovery.sh`;
- если Victoria не отвечает на health — скрипт явно поднимает `victoria-agent`;
- перезапускаются упавшие контейнеры Knowledge OS.

Проверка, что launchd загружен:

```bash
launchctl list | grep auto-recovery
tail -f ~/Library/Logs/atra-auto-recovery.log
```

### 2. Сразу поднять Victoria (без настройки launchd)

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
# проверка
curl -s http://localhost:8010/health
```

### 3. Полный стек Knowledge OS (Victoria + Veronica + остальное)

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d
```

### 4. Универсальная проверка и старт контейнеров

```bash
bash scripts/check_and_start_containers.sh
```

Скрипт проверяет, что Victoria запущена; если контейнера нет — поднимает его, затем при необходимости поднимает остальные сервисы Knowledge OS.

---

## Итог

- **Почему Victoria не в сети:** она в другом docker-compose и/или автопроверки не были настроены (launchd не загружен).
- **Где автопроверки:** `system_auto_recovery.sh` (каждые 5 мин при настроенном launchd) и `check_and_start_containers.sh` (ручной запуск).
- **Что сделать:** один раз выполнить `bash scripts/setup_system_auto_recovery.sh`, при необходимости вручную поднять Victoria или весь стек (см. выше).
