# OpenSSL/urllib3 migration sandbox

Экспериментальное окружение для проверки совместимости ATRA с `urllib3>=2` и системным OpenSSL.

## Цели
- Запустить контейнер с Python 3.11 и OpenSSL 3.x.
- Установить актуальные версии сетевых библиотек (`requests`, `aiohttp`, `httpx`, `python-telegram-bot`, `urllib3`).
- Прогнать smoke-тесты (`pytest`, стресс-сценарии, Telegram dry-run) без предупреждений `NotOpenSSLWarning`.

## Требования
- Docker >= 24.
- Локальный репозиторий `atra` (актуальная ветка `insight`).

## Сборка образа
```bash
cd infrastructure/docker/openssl_migration
docker build -t atra-openssl-test .
```

## Тестовый запуск
```bash
docker run --rm -it \
  -v "$(pwd)/../../..":/opt/atra \
  atra-openssl-test \
  ./scripts/run_openssl_smoke_tests.sh
```

Скрипт:
- пересоздаёт виртуальное окружение внутри контейнера;
- устанавливает зависимости с `urllib3>=2`;
- запускает `pytest tests/unit`;
- прогоняет `scripts/run_flash_crash_stress_test.py` и `scripts/run_liquidity_crisis_test.py` (в dry-run);
- выполняет `scripts/send_risk_status_report.py --dry-run` (Telegram API проверяется без отправки).

## Результаты фиксируем
- В `docs/INFRA_HEALTH_2025Q4.md` (раздел 6.2–6.6).
- При успехе — обновляем `requirements.txt` и снимаем пин `urllib3<2`.
- При ошибках — описываем несовместимости и создаём задачи в backlog.

