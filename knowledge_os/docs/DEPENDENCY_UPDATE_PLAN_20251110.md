# План обновления зависимостей (10 ноября 2025)

## Цели
- Перейти на версии `httpx>=0.28.1`, `python-telegram-bot>=22.5`, `aiohttp>=3.13.2`, `requests>=2.31.0`.
- Синхронизировать требования `requirements.txt`, установочные скрипты и `pip`-валидацию.
- Проверить совместимость обновлённых библиотек с текущими модулями (`telegram_bot_core`, `SourcesHub`, стресс-тесты, отчётность).

## Шаги обновления
1. Обновить `requirements.txt`, `scripts/setup_venv.sh`, `scripts/start_atra.sh`, `archive/experimental/simple_upgrade.py` (выполнено).
2. Выполнить `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
3. Запустить smoke-тесты:
   - `pytest tests/unit` (основные модули).
   - `python scripts/run_flash_crash_stress_test.py --output /tmp/flash.json`.
   - `python scripts/run_liquidity_crisis_test.py --output /tmp/liquidity.json`.
   - `python scripts/send_risk_status_report.py --dry-run`.
4. Проверить Telegram-уведомление: `python scripts/send_risk_status_report.py --user-id <id> --dry-run` (или тестовый канал).
5. Проверить SourcesHub: `python - <<'PY' ... SourcesHub().get_price_data('BTCUSDT')`.
6. Зафиксировать результаты в `docs/CRYPTO_INTRADAY_STRATEGY_AUDIT_20251108.md`.

## Метрики контроля
- Успешные smoke-тесты без ошибок.
- Телеграм-уведомление < 2 с latency.
- `pip list --outdated` без критических пакетов.
- `docs/DEPENDENCY_UPDATE_PLAN_20251110.md` и аудит обновлены.

## Риски и действия
- **Breaking changes httpx 0.28** — проверить кастомные HTTP-клиенты (`telegram_bot_core`, `SourcesHub`). При проблемах зафиксировать issue и вернуть 0.25.2.
- **python-telegram-bot 22.5** — проверка async/await API (метод `Application`). При несовместимости использовать `pip install python-telegram-bot==20.7` и обновить план.
- **Aiohttp / Requests** — при нарушении работы `SourcesHub` откатить версии и поднять задачу на адаптацию.

## Откат
- `git checkout -- requirements.txt scripts/setup_venv.sh scripts/start_atra.sh archive/experimental/simple_upgrade.py`.
- `pip install -r requirements.txt` (до обновления).

## Ответственные действия
- @devops — пересоздание `.venv`, smoke-тесты, проверка cron.
- @quant — обновление метрик после деплоя.
- @risk_manager — мониторинг риск-флагов в первые сутки после обновления.

