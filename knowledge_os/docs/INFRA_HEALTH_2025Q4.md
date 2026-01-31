# INFRA_HEALTH_2025Q4 — аудит инфраструктуры (ноябрь 2025)

## 1. Краткое резюме
- **Дата проверки:** 10 ноября 2025.
- **Охват:** рабочий сервер `root@185.177.216.15`, локальная среда разработки (`macOS 14.6`, Python 3.9.6), вспомогательные скрипты (`server_menu.sh`, `run_risk_status_report.sh`), cron-задачи и резервное копирование.
- **Состояние:** ядро торговли (`main.py`) и сопутствующие сервисы запущены, резервное копирование `trading.db` выполняется, латентность внешних API в норме. Требуется формализация миграции TLS-библиотек (LibreSSL → OpenSSL) и автоматизация health-check отчётности.

## 2. Среды и компоненты
| Компонент | Статус | Комментарий |
| --- | --- | --- |
| `main.py` (сервер) | ✅ | Запущен через `nohup`, PID 644476; лог `bot.log` обновляется. |
| Telegram-уведомления | ✅ | `python-telegram-bot 22.5`, latency ~0.1–0.2 с, доставка 100 %. |
| SourcesHub | ✅ | `get_price/market_cap/volume` выдают данные, кэш работает. |
| Stress-tests | ✅ | `run_flash_crash_stress_test.py`, `run_liquidity_crisis_test.py` используют `simulators/order_book_simulator.py`. |
| Risk-мониторинг | ✅ | `risk_flags` таблица создана; флаги `emergency_stop`, `maxdd_warning`, `weak_setup_stop`=0. Интегрирован Bitget-мониторинг: `bitget_stoploss_missing`, авто-фиксер (`auto_plan_sl/auto_plan_tp`), метрики `bitget_stoploss_missing_total`, `bitget_auto_fix_total`. 12.11: автофиксер успешно восстановил SL/TP (Bitget ответы `code=00000`). |
| Бэкапы БД | ✅ | `backups/trading.db_YYYYMMDD_HHMMSS`, ежедневный срез. |
| Cron | ✅ (manual check) | `run_daily_quality_report.sh` (генерация + авто‑отправка отчёта админу), `run_risk_status_report.sh`, `send_risk_status_report.py --include-infra`. Планируется отдельный health-report канал. |
| Логи | ⚠️ (исторически) | После фикса `risk_flags` и обновления `telegram_commands.py` статус-команда возвращает `Логи: ✅`. Мониторим заполнение `signals_log`; флаг `signals_stalled` прикрывает простои. |

## 3. Результаты health-check
- **База данных:** `sqlite3 trading.db` — целостность подтверждена, резервные копии создаются через `db.backup_file` (SQLite `.backup()` → точные копии, размер совпадает с исходным файлом).
- **Пользователи:** `users_data` — депозиты `556251171=1299.9167893`, `958930260=5000`, `filter_mode=soft/strict`, `auto_mode=auto` (server/local); `user_settings.trade_mode=auto` для 556251171.
- **Риск-флаги:** все сброшены (`value=0`).
- **Логи:** `bot.log` (32508 байт, 10 ноя 20:24), `logs/system.log` фиксирует здоровье; статус-команда обновлена для корректной сигнализации.
- **Внешние API:** CoinGecko 351–328 ms, CryptoCompare 393–371 ms.
- **CI скрипты:** `scripts/setup_venv.sh`, `scripts/start_atra.sh` обновлены под новые зависимости и `urllib3<2`.
- **Проблемы:** Live-сигналы пока отсутствуют из-за фильтров (direction confidence, BTC alignment); требуется наблюдение.
- **Smoke tests TLS (10.11 19:41 UTC):** `docker run atra-openssl-test ./scripts/run_openssl_smoke_tests.sh` (OpenSSL 3.5.1, `urllib3 2.5.0`, `pytest` 29 passed, стресс-тесты, `send_risk_status_report.py --dry-run` OK). Отчёты сохранены в `data/reports/stress_flash_crash.json` и `..._liquidity_crisis.json`.
- **Restore test:** `python3 scripts/test_restore_backup.py` на сервере — ✅ (`trading.db_20251110_224921`, все обязательные таблицы на месте).
- **Bitget стопы:** 11.11 устранён баг мгновенного закрытия позиций — `exchange_adapter.py` переводит SL на плановый ордер (`stopLossPrice`), добавлен регрессионный тест `scripts/test_bitget_stop_orders.py` (`make test-bitget-stop`), nightly-скрипт `scripts/run_nightly_bitget_checks.sh` + cron-шаблон `infrastructure/cron/nightly_bitget_checks.cron`. 12.11 `place_take_profit_order` переписан на плановые ордера (`planType=pos_profit`), `auto_execution` теперь выставляет TP1/TP2 одновременно (частичное закрытие). 13.11 внедрён авто-фиксер в `run_risk_monitor.py`: при обнаружении «дыр» выставляет `pos_loss/pos_profit` заново и логирует результат (`order_audit_log` + Prometheus `bitget_auto_fix_total`).

## 4. Выявленные риски
1. **LibreSSL / urllib3** — отсутствие OpenSSL приводит к необходимости удерживать `urllib3<2` (иначе `NotOpenSSLWarning`). Требуется план обновления TLS-стека.
2. **Отсутствие автоматических health-отчётов** — статусы по cron, бэкапам и логам собираются вручную.
3. **Зависимость от единственного `main.py`** — отсутствие supervisor/PM2; перезапуск выполняется вручную.
4. **Signals log = 0 записей** — live-выдача ещё не возобновлена; важно отслеживать, чтобы автоматическая проверка логов не считала это ошибкой.

## 5. План действий (Q4 2025)
| № | Задача | Ответственный | Дедлайн | Метрика успеха |
| --- | --- | --- | --- | --- |
| 1 | Автоматизировать ежедневный health-report (`docs/INFRA_HEALTH_2025Q4.md` → JSON → Telegram). | @devops | 20.11 | Скрипт `scripts/report_infra_status.py`, cron запись, отчёт в Telegram 09:00 UTC. *(реализовано: отчет встроен в `send_risk_status_report.py --include-infra`; осталось оформить отдельный Telegram канал/cron.)* |
| 2 | Добавить мониторинг заполнения `signals_log` (минимум 1 запись за 48 ч). | @risk_manager | 25.11 | Alert при `COUNT(signals_log)=0` > 48 ч; логика в `run_risk_monitor.py`. *(реализовано: флаг `signals_stalled`)* |
| 3 | Внедрить supervisor (systemd unit или `start_continuous.sh`) для `main.py`. | @devops | 30.11 | Автозапуск при рестарте сервера, проверка watchdog. *(выполнено: `atra.service` установлен, `systemctl enable --now atra.service`)* |
| 4 | Провести тест восстановления из бэкапа `trading.db`. | @devops | 05.12 | ✅ 10.11 `scripts/test_restore_backup.py` → все таблицы восстановлены из `trading.db_20251110_224921`. |
| 5 | Реализовать план миграции TLS (см. раздел 6). | @devops + @security | 20.12 | urllib3≥2.1, отсутствие `NotOpenSSLWarning`. |
| 6 | Автоматизировать регрессионный тест Bitget stop-loss (`make test-bitget-stop`). | @devops | 15.11 | Скрипт прогоняется перед релизом и после инцидентов; лог `logs/system.log` без ошибок `SL Order`; nightly результат в `logs/test_results.log`. |

*Статус 10.11 (22:50 UTC+3):* `scripts/report_infra_status.py` интегрирован в `run_risk_status_report.sh` (с `--include-infra`), флаг `signals_stalled` в `run_risk_monitor.py`, `atra.service` активен (`systemctl enable --now atra.service`). Обновлён `db.backup_file` — теперь использует `sqlite3.Connection.backup()`, что устранило усечённые бэкапы (подтверждено размером и восстановлением). `scripts/test_restore_backup.py` прошёл с копией `trading.db_20251110_224921`. Smoke-тест TLS-контейнера выполнен непосредственно на сервере, отчёты стресс-тестов сохранены.

## 6. План миграции OpenSSL / urllib3
### 6.1 Результаты аудита TLS (10.11.2025)
- **Локальная среда (macOS 14.6 / Python 3.9.6):**
  - `ssl.OPENSSL_VERSION` → `LibreSSL 2.8.3` (ограниченные cipher suites, несовместимо с `urllib3>=2`).
  - Системный `/usr/bin/openssl` → `OpenSSL 3.6.0 (1 Oct 2025)` — доступен, но Python собран с LibreSSL.
  - `python3 -m pip show urllib3` → `2.5.0` (установлено глобально; требуется выравнивание с проектным требованием `<2` до миграции на OpenSSL).
- **Сервер (Ubuntu 22.04 / Python 3.10.12):**
  - `ssl.OPENSSL_VERSION` → `OpenSSL 3.0.2`.
  - `openssl version` → `OpenSSL 3.0.2`.
  - `python3 -m pip show urllib3` → `1.26.5` (из системного репозитория; соответствует текущему пину `<2`).
- **Вывод:** переход на `urllib3>=2` возможен только после пересборки/обновления Python в локальной среде (или использования проектного `.venv` с системным OpenSSL). На сервере достаточно обновить пакетный менеджер после подготовки тестовой среды.

### 6.2 План миграции OpenSSL / urllib3
| Фаза | Действия | Результат |
| --- | --- | --- |
| 6.2.1 Аудит | Сбор информации об установленной версии LibreSSL/OpenSSL, проверка совместимости зависимостей (`requests`, `aiohttp`, `httpx`). *(выполнено, см. выше)* | Отчёт с Matrix совместимости. |
| 6.2 Тестовый контейнер | Развернуть контейнер/VM с системным OpenSSL≥1.1.1, собрать `.venv`, установить `urllib3>=2`, `requests>=2.32`, `httpx>=0.28.1`. *(docker установлен; sandbox собран и прогнан локально)* | Успешные smoke-тесты (`pytest`, стресс-тесты, Telegram dry-run без предупреждений). |
- **Результат фазы 6.2 (10.11):**  
  ```
  python: OpenSSL 3.5.1 1 Jul 2025
  urllib3: 2.5.0
  tests/unit: 29 passed (pytest 9.0.0)
  flash_crash / liquidity_crisis: отчёты → data/reports/stress_flash_crash.json, stress_liquidity_crisis.json
  send_risk_status_report.py --dry-run: вывод сформирован без ошибок
  ```
  Dry-run поддерживается флагом `--dry-run`; образ собран и прогнан на прод-сервере (`docker build/ run`).
| 6.3 Рефакторинг кода | Проверить кастомные SSL-настройки (если есть) в `SourcesHub`, `telegram_bot_core`, отключить явные фиксации `ssl_context`. *(grep по проекту → нет `ssl_context`, `verify=False`; `aiohttp`/`httpx` используют дефолтный TLS)* | Репозиторий совместим с новой версией TLS. |
| 6.4 Деплой в staging | Обновить staging сервер, включить мониторинг (latency, TLS ошибки). | Отсутствие предупреждений, стабильная работа 72 часа. |
| 6.5 Продакшн | Перевести основной сервер на OpenSSL стэк (OS upgrade или установка `openssl@3` + rebuild Python), обновить `.venv`, убрать pin `urllib3<2`. | `pip check` чистый, предупреждения отсутствуют, лог мониторинга OK. |
| 6.6 Post-mortem | Задокументировать изменение в `docs/DEPENDENCY_UPDATE_PLAN_*`, обновить этот файл. | Завершённый отчёт и обновлённый план. |

## 7. Мониторинг и отчётность
- `scripts/report_combined_status.py` расширен разделом Infrastructure Health (`collect_infra_status`, `format_infra_status`).
- `run_risk_status_report.sh` выполняет `report_infra_status.py` и логирует результат (`logs/infra_status.log`); при cron-запуске отчёт добавится автоматически.
- Локальный контроль: `server_menu.sh -> 5. Health Check` обновить под новые проверки.
- Для миграции TLS подготовлен sandbox (`infrastructure/docker/openssl_migration` + `scripts/run_openssl_smoke_tests.sh`) — использовать для фазы 6.2.

## 8. Следующие шаги
1. Реализовать задачи из раздела 5 (health-report, supervisor).
2. Подготовить cron для отдельного health-report канала (при необходимости).
3. Подготовить отчёт о завершённых этапах в `docs/CRYPTO_INTRADAY_STRATEGY_AUDIT_20251108.md`.
4. Включить `make test-bitget-stop` в pre-release чек-лист и настроить уведомление при сбоях планового ордера.

--- 

**Ответственный за документ:** @devops (обновления по мере выполнения плана).  
**Текущая ревизия:** commit после включения auto-режима и фикса `risk_flags`.  
**Следующее обновление:** после завершения фазы 6.2 (тестовый контейнер OpenSSL).


