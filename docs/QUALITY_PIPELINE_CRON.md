# Пайплайн качества RAG: cron и запуск

## Ручной запуск

Из корня репозитория:

```bash
./scripts/run_quality_pipeline.sh
```

Для реальных метрик качества нужна заполненная БЗ (таблица `knowledge_nodes`, эмбеддинги). Иначе валидация отработает с низкими faithfulness/relevance и `--no-fail`.

## Ежедневный запуск по cron (установка одной командой)

Из корня репозитория:

```bash
./scripts/install_quality_cron.sh
```

Скрипт сам подставит путь к проекту, создаст каталог `logs/` и добавит задание в crontab. Расписание: **каждый день в 03:00**. Лог: `logs/quality_pipeline.log`.

Ручная установка (если нужно): откройте `infrastructure/cron/quality_pipeline.cron`, замените путь и вставьте строку в `crontab -e`.

## Проверка

- Отчёт валидации: `backend/validation_report.json`
- HTML-отчёт: `quality_report.html`
- API метрик: `GET /api/quality/metrics/history`, `GET /api/quality/metrics/summary`
