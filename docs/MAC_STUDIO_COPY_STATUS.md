# Копия «тебя» на Mac Studio — статус и следующие шаги

**Назначение:** один документ — что уже есть на Mac Studio (Victoria + команда как «копия» Cursor-агента), что работает, чем продолжить.  
**Связь:** [ROADMAP_CORPORATION_LIKE_AI.md](ROADMAP_CORPORATION_LIKE_AI.md), [NEXT_STEPS_CORPORATION.md](NEXT_STEPS_CORPORATION.md), [VICTORIA_CURATOR_PLAN.md](VICTORIA_CURATOR_PLAN.md).

**Обновлено:** 2026-02-09

---

## 1. Что уже есть (база «как я»)

| Область | Состояние |
|--------|-----------|
| **Victoria + Veronica** | Один сервис Victoria (8010), три уровня (Agent, Enhanced, Initiative); Veronica (8011) — «руки». Запуск: `docker compose -f knowledge_os/docker-compose.yml up -d`. Модель по умолчанию: phi3.5:3.8b (тяжёлые 70B/104B убраны из приоритетов под Metal/MLX). |
| **Цепочка задачи** | Документирована (VICTORIA_TASK_CHAIN_FULL). Маршрутизация: простые шаги → Veronica, сложные → Victoria Enhanced (эксперты, swarm/consensus). PREFER_EXPERTS_FIRST, тесты покрывают логику. |
| **Эксперты** | Один источник (employees.json), sync в БД; 86 экспертов в runtime. Добавление: запись в employees.json → `python scripts/sync_employees.py`. |
| **Библия и методология** | MASTER_REFERENCE, CHANGES, VERIFICATION_CHECKLIST §5. В промпт Victoria подставляется «КАК МЫ МЫСЛИМ» (corporation_thinking.txt), возможности — victoria_capabilities.txt. |
| **Куратор и эталоны** | Прогоны: `./scripts/run_curator_scheduled.sh`; сравнение с эталоном: `curator_compare_to_standard.py`; эталоны в RAG (curator_standards). По расписанию: `bash scripts/setup_curator_launchd.sh` (ежедневно 9:00). |
| **Mac Studio** | Док [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md): RAM/Docker 8–12 GB, MAX_CONCURRENT_VICTORIA 10–20, модель phi3.5:3.8b; при вылетах — VICTORIA_RESTARTS_CAUSE. |
| **Тесты и верификация** | Backend + knowledge_os тесты; E2E Playwright (чат, health); план верификации пройден; стратегический e2e: `./scripts/test_strategic_chat_e2e.sh`. |

Итого: **база «как я» на Mac Studio уже есть** — один контекст (библия, эксперты, эталоны), предсказуемая цепочка, куратор и расписание, тесты и доки.

---

## 2. Продолжаем: что делать дальше (по приоритету)

### Сейчас (цикл «как я»)

1. **Гонять куратора регулярно**  
   Полный прогон: `./scripts/run_curator_scheduled.sh` (или уже по launchd в 9:00). Разбирать отчёт по [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) и [CURATOR_CHECKLIST.md](curator_reports/CURATOR_CHECKLIST.md). При расхождении с эталоном — доучивать эталоны в RAG (`curator_add_standard_to_knowledge.py`) и при необходимости обновлять standards/.

2. **Накапливать эталоны**  
   В `docs/curator_reports/standards/` добавлять эталонные ответы по новым типам запросов; при прогонах сравнивать через `curator_compare_to_standard.py`. Чем больше эталонов в RAG — тем стабильнее ответы Victoria «как я».

3. **Следить за стабильностью**  
   Grafana (3002): алерт deferred_to_human; при падениях MLX/Ollama — system_auto_recovery, логи Victoria. Модели на Mac Studio: без 70B/104B в приоритетах (см. MASTER_REFERENCE §4).

### Средний срок (если нужен рост)

4. **План оркестратора → исполнение**  
   Сейчас план только подсказка (контекст в промпт). При желании «чтобы план реально выполнялся» — доработка: вызов run_smart_agent по списку экспертов из assignments и сбор ответов в рамках запроса. Решение зафиксировано в NEXT_STEPS_CORPORATION §5; при доработке — обновить VICTORIA_TASK_CHAIN_FULL и библию.

5. **RAG-кэш в Redis**  
   Нужен только при втором инстансе Victoria или общем кэше между сервисами. Пока один инстанс на Mac Studio — memory достаточно.

### Долгий срок

6. **Секреты в проде, мониторинг**  
   В проде — секрет-менеджер; алерты deferred_to_human уже есть; при росте — мониторинг пула БД и здоровья Ollama/MLX.

---

## 3. Быстрые команды (Mac Studio)

```bash
# Поднять корпорацию (Knowledge OS + Web IDE)
docker compose -f knowledge_os/docker-compose.yml up -d
docker compose up -d

# MLX с автоперезапуском при падении (один раз: автозапуск при логине)
bash scripts/setup_mlx_autostart.sh
launchctl start com.atra.mlx-api-server   # запустить сейчас
launchctl list | grep mlx                  # статус; при краше — «Пропустить» в диалоге, Victoria продолжит через Ollama

# Куратор: полный прогон (Victoria должна быть на :8010)
./scripts/run_curator_scheduled.sh

# Сравнение с эталоном
python3 scripts/curator_compare_to_standard.py --report docs/curator_reports/curator_*.json --standard what_can_you_do

# Восстановление при сбоях
bash scripts/system_auto_recovery.sh
```

---

**Итог:** копия «тебя» на Mac Studio **уже работает** — Victoria + команда, куратор, эталоны, библия. **Продолжаем** — регулярные прогоны куратора и накопление эталонов; при необходимости потом — исполнение по плану оркестратора и RAG Redis при масштабе.
