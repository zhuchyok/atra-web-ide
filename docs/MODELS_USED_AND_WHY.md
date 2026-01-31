# Какие модели используются в проекте и почему

Единый справочник по всем LLM/vision-моделям в ATRA Web IDE и Knowledge OS: где используются, зачем и по какому принципу выбираются.

---

## 1. Источники моделей (два бэкенда)

| Источник | Порт | Назначение |
|----------|------|------------|
| **Ollama** | 11434 | Быстрые задачи, vision, fallback когда MLX недоступен |
| **MLX API Server** | 11435 | Тяжёлые задачи (reasoning, coding), Mac Studio M4 Max |

**Почему два источника:** MLX даёт максимальное качество и скорость на Apple Silicon; Ollama — универсальный fallback, плюс единственный источник vision-моделей (llava, moondream).

---

## 2. Модели по назначению

### 2.1 Reasoning (логика, планирование, анализ)

| Модель | Где | Почему |
|--------|-----|--------|
| **deepseek-r1-distill-llama:70b** | MLX (приоритет) | Основная reasoning-модель: chain-of-thought, длинный контекст, сильный анализ. Используется в orchestrator, Victoria Enhanced, scout, extended thinking, researcher, ReAct, Tree of Thoughts, ReCAP, swarm, consensus. |
| **glm-4.7-flash:q8_0** | Ollama (fallback) | Когда MLX недоступен: неплохой reasoning при Q8, ~30B параметров. В `local_router` и `model_performance_tracker` как Ollama-аналог для reasoning. |
| **command-r-plus:104b** | MLX | Enterprise/сложные сценарии; в backend chat и model_optimizer для «корпоративных» и «стратегических» запросов. |

**Почему именно так:** Для сложных задач приоритет — 70B reasoning (deepseek-r1); при недоступности MLX — glm-4.7-flash на Ollama; command-r-plus — для максимальной сложности на MLX.

---

### 2.2 Coding (код, рефакторинг, алгоритмы)

| Модель | Где | Почему |
|--------|-----|--------|
| **qwen2.5-coder:32b** | MLX (приоритет) | Основная coding-модель: качество кода, мультиязычность. В `local_router`, `streaming_processor`, `intelligent_model_router`, backend chat, Victoria Enhanced, scout fallback. |
| **glm-4.7-flash:q8_0** | Ollama | Fallback для кодинга когда MLX недоступен; в `OLLAMA_MODELS["coding"]` и иерархии. |
| **phi3.5:3.8b** | Ollama/MLX | Быстрый ответ по коду для простых задач; в `model_performance_tracker`, smart_worker по умолчанию. |

**Почему именно так:** Qwen2.5-coder даёт лучший баланс качества кода и скорости на 32B; glm — сильный Ollama-вариант; phi3.5 — для лёгких задач и экономии ресурсов.

---

### 2.3 Fast / default (быстрые и общие ответы)

| Модель | Где | Почему |
|--------|-----|--------|
| **phi3.5:3.8b** | Ollama и MLX | Основная «быстрая» модель: малый размер (~2 GB), низкая задержка. В `MODEL_MAP["fast"]`, `OLLAMA_MODELS`, smart_worker, nightly_learner, backend chat для коротких/общих сообщений. |
| **phi3:mini-4k** | MLX | Ещё легче; в backend chat для очень коротких сообщений и в extended_thinking / Victoria Enhanced как быстрый вариант. |
| **qwen2.5:3b** | MLX | Альтернатива быстрому слою; в backend chat по умолчанию и в model_enhancer ensemble. |

**Почему именно так:** Минимизация задержки при приемлемом качестве; phi3.5 — основной быстрый слой, phi3:mini и qwen2.5:3b — ещё более лёгкие варианты.

---

### 2.4 Vision (изображения, PDF)

| Модель | Где | Почему |
|--------|-----|--------|
| **moondream** | Ollama | Лёгкая vision (~1.6 GB), быстрый ответ. В `local_router`, `vision_processor` для обычных картинок. |
| **llava:7b** | Ollama | Тяжелее, лучше для PDF и сложных документов. В `local_router` как `vision_pdf`, в vision_processor и nightly_learner. |

**Почему именно так:** Vision есть только в Ollama; moondream — скорость, llava — качество по документам/PDF.

---

### 2.5 Enterprise / максимальная сложность

| Модель | Где | Почему |
|--------|-----|--------|
| **command-r-plus:104b** | MLX | Самая большая модель: корпоративные сценарии, стратегия, RAG. В backend chat (`_select_model_for_chat`), model_optimizer, extended_thinking, Victoria Enhanced. |
| **llama3.3:70b** | MLX | Высокое качество ответов; в backend chat для запросов «качество/оптимально/детально», в model_enhancer ensemble и Victoria Enhanced. |

**Почему именно так:** Когда нужна максимальная «мощность» — 104B; когда важнее стабильное качество — 70B (llama3.3).

---

### 2.6 Специальные и исключённые

| Модель / правило | Где | Почему |
|------------------|-----|--------|
| **tinyllama:1.1b-chat** | Почти нигде в пользовательских сценариях | Зарезервирована для внутренней коммуникации агентов; в extended_thinking, Victoria Enhanced, mlx_api_server явно исключена из пользовательских цепочек. |
| **all-MiniLM-L6-v2** | vector_core | Эмбеддинги для RAG/поиска; не LLM, отдельный сервис. |

---

## 3. Где что задаётся в коде

| Файл | Что задаёт |
|------|------------|
| **knowledge_os/app/local_router.py** | `MODEL_MAP` (MLX приоритет), `OLLAMA_MODELS` (fallback), эвристики выбора модели по задаче и узлу. |
| **knowledge_os/app/model_performance_tracker.py** | `MODEL_HIERARCHY`: порядок моделей от лёгких к тяжёлым для fast/coding/reasoning/default. |
| **knowledge_os/app/intelligent_model_router.py** | Базовые способности моделей (phi3.5, glm-4.7-flash:q8_0, qwen2.5-coder:32b, deepseek-r1-distill-llama:70b) для выбора по задаче. |
| **knowledge_os/app/ai_core.py** | Список `models_to_try` при fallback на Ollama (deepseek, qwen2.5-coder, glm-4.7-flash:q8_0, phi3.5). |
| **knowledge_os/app/mlx_api_server.py** | `MODEL_PATHS`, `PRELOAD_MODEL_MAP`, маппинг категорий и имён Ollama → MLX. |
| **backend/app/routers/chat.py** | `_select_model_for_chat`: выбор модели по тексту сообщения (command-r-plus, deepseek-r1, llama3.3, qwen2.5-coder, phi3.5, phi3:mini-4k, qwen2.5:3b). |
| **docs/CURRENT_MODELS_LIST.md** | Актуальный список моделей Ollama и MLX; с ним синхронизированы конфиги. |

---

## 4. Логика выбора модели (кратко)

1. **Роутинг узла:** MLX (11435) предпочитается для reasoning/coding; при перегрузке или недоступности — Ollama (11434).
2. **Категория задачи:** reasoning → deepseek-r1 / glm; coding → qwen2.5-coder / glm; fast/default → phi3.5 и легче; vision → moondream/llava.
3. **Содержимое запроса:** В backend chat по ключевым словам («код», «логика», «корпорац» и т.д.) выбирается конкретная модель.
4. **Иерархия при неудаче:** `model_performance_tracker` предлагает следующую по списку модель (например, с phi3.5 на glm или deepseek).
5. **Vision:** Всегда Ollama; тип задачи (картинка vs PDF) определяет moondream vs llava.

---

## 5. Сводная таблица «модель → зачем»

| Модель | Размер / тип | Основное назначение | Почему эта модель |
|--------|--------------|----------------------|-------------------|
| deepseek-r1-distill-llama:70b | 70B, MLX | Reasoning, анализ, планирование | Сильный CoT и анализ при приемлемой скорости на Mac Studio. |
| qwen2.5-coder:32b | 32B, MLX/Ollama | Код, рефакторинг | Лучший баланс качества кода и скорости среди доступных. |
| command-r-plus:104b | 104B, MLX | Enterprise, сложные задачи | Максимальная «мощность» для корпоративных сценариев. |
| llama3.3:70b | 70B, MLX | Качество ответов, сложные общие задачи | Высокое качество и универсальность. |
| glm-4.7-flash:q8_0 | ~30B, Ollama | Reasoning/coding fallback | Лучший Ollama-вариант когда MLX недоступен. |
| phi3.5:3.8b | 3.8B, Ollama/MLX | Быстрые и общие ответы | Малая задержка, мало памяти. |
| phi3:mini-4k | Малая, MLX | Очень быстрые ответы | Ещё легче phi3.5 для коротких запросов. |
| qwen2.5:3b | 3B, MLX | Быстрый default | Лёгкий универсальный слой. |
| moondream | Vision, Ollama | Картинки | Быстрая и лёгкая vision. |
| llava:7b | Vision 7B, Ollama | PDF, документы | Лучше для текста в изображениях/PDF. |
| tinyllama:1.1b-chat | 1.1B | Только агентская коммуникация | Не для пользователя; минимум ресурсов внутри системы. |

---

**Дата:** 2026-01-28  
**Связанные документы:** `docs/CURRENT_MODELS_LIST.md`, `knowledge_os/app/local_router.py`, `backend/app/routers/chat.py`
