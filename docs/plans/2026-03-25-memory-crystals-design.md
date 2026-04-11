# Design: Memory Crystals & U-Shape Context (Singularity 23.0)

## 1. Проблема
1. **Lost in the Middle:** Модели LLM (даже 35B/70B) теряют концентрацию на фактах, расположенных в середине длинного контекстного окна.
2. **Context Bloat:** Длинные диалоги перегружают RAM и увеличивают задержку (TTFT).
3. **Linear Forgetting:** При достижении лимита контекста старые, но критически важные решения (архитектура, порты) просто обрезаются.

## 2. Решение: Memory Crystals (Кристаллы Памяти)
Вместо линейной истории мы переходим к **иерархическому ядру**.

### 2.1. Таблица `memory_crystals`
```sql
CREATE TABLE memory_crystals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_context TEXT NOT NULL,
    crystal_type TEXT NOT NULL, -- 'decision', 'parameter', 'milestone'
    content TEXT NOT NULL,
    confidence_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_crystals_project ON memory_crystals(project_context);
```

### 2.2. U-Shape Context Architecture
Формирование промпта перед отправкой в LLM:
1. **TOP (Attention Anchor 1):** Блок `<memory_crystals>`. Самые важные факты и решения по проекту. Модель видит их первыми.
2. **MIDDLE (Compressed Noise):** Агрессивно сжатая история последних 5-10 сообщений через `phi3.5`. Удаляется вежливость, повторы, оставляется только суть.
3. **BOTTOM (Attention Anchor 2):** Текущий запрос пользователя + **Instruction Re-injection** (повтор главной системной роли и правил Золотого Стандарта).

## 3. Компоненты системы

### 3.1. Crystallizer (Экстрактор)
Фоновый процесс или хук в `ai_core.py`, который:
- Анализирует ответ ассистента.
- Если обнаружено принятое решение (через паттерны или LLM-анализ), создает запись в `memory_crystals`.
- Пример: "Решили использовать порт 6432" -> Кристалл `{type: 'parameter', content: 'DB Port: 6432'}`.

### 3.2. U-Shape Assembler
Модификация `run_smart_agent_async_impl`:
- Извлекает кристаллы по `project_context`.
- Вызывает `ContextCompressor.compress_smart` для середины.
- Собирает финальный промпт.

## 4. Метрики успеха
- **Recall Accuracy:** Точность вспоминания фактов из начала диалога (цель: >95%).
- **Token Efficiency:** Снижение объема контекста на 40-60% при сохранении смысла.
- **Latency:** Уменьшение TTFT за счет более коротких промптов.

## 5. Pre-mortem (Риски)
1. **Crystal Hallucination:** Ошибочное извлечение факта. *Защита: ручная верификация или высокий порог уверенности.*
2. **Over-compression:** Потеря нюансов в середине. *Защита: сохранение последних 3 сообщений в сыром виде.*
