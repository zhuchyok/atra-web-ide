# Запуск всего (обучение + оркестрация)

**Дата:** 2026-01-29

## Быстрый старт

1. **Проверить готовность** (venv, импорты, БД):
   ```bash
   bash scripts/check_ready.sh
   ```

2. **Запустить всё один раз** (venv при необходимости + один цикл Nightly Learner + один цикл Enhanced Orchestrator):
   ```bash
   bash scripts/run_everything.sh
   ```

3. **Только обучение и оркестрация** (один цикл; при отсутствии venv скрипт сам запустит setup):
   ```bash
   bash scripts/run_learning_and_orchestration.sh
   ```

## Настройка вручную

- **Создать venv и установить зависимости:**
  ```bash
  bash scripts/setup_knowledge_os_venv.sh
  ```

- **БД:** используется `DATABASE_URL` из `.env` или `postgresql://admin:secret@localhost:5432/knowledge_os`. Убедитесь, что PostgreSQL запущен и доступен.

- **Ollama:** для Nightly Learner нужен Ollama (или MLX) для генерации инсайтов. Для Enhanced Orchestrator — для эмбеддингов и LLM.

## Что будет работать

- Записи в **«Академия ИИ»** (логи обучения, дебаты) — после успешного Nightly Learner.
- **Гипотезы** и пополнение **базы знаний** — после Enhanced Orchestrator.
- **Задачи** на дашборде — создаются оркестратором и обрабатываются worker’ом.

После запуска дашборд обновит вкладки «Академия ИИ», «Задачи», «База знаний» (данные из одной локальной БД).
