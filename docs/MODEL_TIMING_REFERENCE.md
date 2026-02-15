# Время по моделям: загрузка и ответ (Ollama/MLX)

**Назначение:** у каждой модели своё время холодной загрузки и первого ответа. Этот справочник помогает задавать таймауты и задержки под выбранный размер модели (Mac Studio M4, ориентиры).

**Связанные документы:** [MODEL_COLD_START_REFERENCE.md](MODEL_COLD_START_REFERENCE.md) (ориентиры из интернета + зафиксированные замеры по нашим 8 моделям Ollama в §4 и в **configs/ollama_model_timings.json** — использовать для таймаутов), [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) §4.4, [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md), [MAC_STUDIO_M4_MODELS_GUIDE.md](MAC_STUDIO_M4_MODELS_GUIDE.md).

---

## 1. Ориентиры по размеру модели (Mac Studio M4, холодный старт)

| Размер модели | Примеры (Ollama/MLX) | Холодная загрузка в RAM | Первый ответ (TTFT) | Один шаг LLM (типично) |
|---------------|----------------------|--------------------------|----------------------|-------------------------|
| **1–4B**      | tinyllama, phi3.5:3.8b, qwen2.5:3b | 5–15 с  | 2–5 с   | 10–30 с  |
| **7–11B**    | qwen2.5-coder:7b, llama3.2:11b     | 10–25 с | 5–15 с  | 20–60 с  |
| **32B**      | qwen2.5-coder:32b, deepseek-coder:33b | 30–60 с | 15–45 с | 60–180 с |
| **70B**      | llama3.3:70b, deepseek-r1-distill-llama:70b | 1–3 мин | 30 с–2 мин | 120–300 с |
| **104B**     | command-r-plus:104b                 | 2–5 мин | 1–3 мин | 180–600 с |

- **Холодная загрузка** — первый запрос к модели после старта Ollama/MLX (модель ещё не в памяти).
- **Первый ответ (TTFT)** — время до первого токена ответа.
- **Один шаг LLM** — один вызов `generate` в рамках задачи Victoria (зависит от длины промпта и ответа).

Значения ориентировочные; зависят от объёма RAM, диска и загрузки хоста.

---

## 2. Какие переменные подстраивать под модель

| Переменная | Где | Рекомендация по размеру модели |
|------------|-----|--------------------------------|
| **OLLAMA_EXECUTOR_TIMEOUT** | Victoria (victoria-agent) | Один вызов LLM. 1–4B: 60–120 с; 7–11B: 120–180 с; 32B: 180–300 с; 70B: 300–600 с; 104B: 600+ с. |
| **VICTORIA_TIMEOUT** | Backend | Вся задача (много шагов). Обычно 900 с; при 70B/104B можно 1200–1800. |
| **SERVICE_MONITOR_INITIAL_DELAY** | Victoria (Service Monitor) | Задержка перед первой проверкой. 1–4B: 40–50 с; 7–11B: 50–60 с; 32B: 60–75 с; 70B: 90–120 с; 104B: 120–180 с. |

Итог: при тяжёлых моделях (32B+) увеличивать **OLLAMA_EXECUTOR_TIMEOUT** и **SERVICE_MONITOR_INITIAL_DELAY**; при лёгких — можно уменьшать для быстрой отдачи.

---

## 3. Примеры настроек под модель

**Лёгкие модели (phi3.5:3.8b, qwen2.5:3b):**
```bash
OLLAMA_EXECUTOR_TIMEOUT=120
SERVICE_MONITOR_INITIAL_DELAY=45
```

**Средние (qwen2.5-coder:7b, llama3.2:11b):**
```bash
OLLAMA_EXECUTOR_TIMEOUT=180
SERVICE_MONITOR_INITIAL_DELAY=55
```

**Тяжёлые (qwen2.5-coder:32b):**
```bash
OLLAMA_EXECUTOR_TIMEOUT=300
SERVICE_MONITOR_INITIAL_DELAY=70
```

**Очень тяжёлые (70B, 104B):**
```bash
OLLAMA_EXECUTOR_TIMEOUT=600
SERVICE_MONITOR_INITIAL_DELAY=120
VICTORIA_TIMEOUT=1200
```

---

## 4. Замер времени ответа на своей машине

### 4.1 Одна модель

- **scripts/measure_ollama_response_time.sh** — один запрос к первой доступной модели Ollama (и при наличии MLX). Запуск: `OLLAMA_BASE_URL=http://localhost:11434 bash scripts/measure_ollama_response_time.sh`. По результату можно оценить, укладываются ли async-задачи в окно опроса.

### 4.2 Все модели Ollama (скрипт bash)

- **scripts/measure_all_ollama_models.sh** — по очереди один запрос **каждой** модели Ollama (кроме embedding-only). Выход: tmp/ollama_model_timings.txt, .json (model, time_sec, status). Запуск: `OLLAMA_BASE_URL=http://localhost:11434 bash scripts/measure_all_ollama_models.sh`.

### 4.3 Все модели Ollama + MLX с таймаутами по размеру и буфером на запуск

- **scripts/measure_all_models_ollama_mlx.py** — замер **каждой** модели Ollama и MLX; у каждой модели своё время и рекомендуемый таймаут.
  - **Таймаут на запрос по размеру:** маленькие (1–7B) — 1 мин, средние (11–32B) — 2 мин, большие (70B+) — 3 мин. Задаётся **MEASURE_TIMEOUT_SMALL/MEDIUM/LARGE** (по умолчанию 60/120/180 с).
  - **Буфер на запуск/развёртывание:** прибавляется к замеренному времени (холодный старт). По умолчанию: small +30 с, medium +60 с, large +90 с (**MEASURE_STARTUP_BUFFER_SMALL/MEDIUM/LARGE**).
  - **recommended_timeout_sec** = measured_sec + startup_buffer_sec — если ответа нет после этого времени, считаем «модель не отвечает», а не «ещё думает»; по нему выставлять настройки и тесты.
  - Запуск: `OLLAMA_BASE_URL=http://localhost:11434 MLX_BASE_URL=http://localhost:11435 python scripts/measure_all_models_ollama_mlx.py`
  - Выход: **tmp/model_timings_ollama_mlx.json**, **tmp/model_timings_ollama_mlx.txt** (model, source, size_category, measured_sec, request_timeout_sec, startup_buffer_sec, recommended_timeout_sec, status).
- Пример использования в тесте: загрузить JSON, взять `recommended_timeout_sec` для выбранной модели и ждать ответ не дольше этого времени; при превышении — «модель не отвечает».

## 5. Ссылки

- Переменные Victoria/Backend: MAC_STUDIO_LOAD_AND_VICTORIA §4.1–4.2, §4.4.
- Async-задачи долго в running: VICTORIA_RESTARTS_CAUSE §4.1.
- Список моделей и приоритеты: MAC_STUDIO_M4_MODELS_GUIDE, executor fallback — `src/agents/core/executor.py`.
