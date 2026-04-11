# Локальное формирование диалогов экспертов: Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Перенос генерации обсуждений экспертов из облака в локальный инференс MLX для экономии токенов и повышения точности.

**Architecture:** Внедрение `TeamDiscussionEngine` в `ai_core.py`, который формирует комплексный промпт для локальной модели `victoria-wisdom-v3.5` и получает структурированный Markdown-диалог за один проход.

**Tech Stack:** Python, MLX API, PostgreSQL (для RAG), asyncpg.

---

### Task 1: Подготовка инфраструктуры (ai_core.py)

**Files:**
- Modify: `knowledge_os/app/ai_core.py`

**Step 1: Определение структуры TeamDiscussionEngine**
Добавить класс `TeamDiscussionEngine` и метод `generate_discussion`.

**Step 2: Интеграция с LocalAIRouter**
Настроить вызов локальной модели через порт 11435 с флагом `single_pass_team=True`.

**Step 3: Commit**
```bash
git add knowledge_os/app/ai_core.py
git commit -m "feat: add TeamDiscussionEngine skeleton to ai_core"
```

### Task 2: Маппинг личностей и формирование промпта

**Files:**
- Modify: `knowledge_os/app/ai_core.py`
- Read: `docs/TEAM_PERSONALITIES.md`

**Step 1: Загрузка стилей экспертов**
Реализовать метод `_get_expert_styles`, который читает `TEAM_PERSONALITIES.md` и формирует краткие инструкции для каждой роли.

**Step 2: Формирование сценарного промпта**
Реализовать сборку финального промпта, включающего задачу, контекст кода и инструкции по ролям.

**Step 3: Commit**
```bash
git add knowledge_os/app/ai_core.py
git commit -m "feat: implement personality mapping for local team generation"
```

### Task 3: Тестирование и Fallback

**Files:**
- Create: `knowledge_os/tests/test_local_team.py`
- Modify: `knowledge_os/app/ai_core.py`

**Step 1: Написание теста**
Проверить, что `TeamDiscussionEngine` возвращает валидный Markdown с именами экспертов.

**Step 2: Реализация Fallback**
Добавить `try...except` блок: если MLX недоступен или выдает мусор, переключаться на стандартный облачный режим.

**Step 3: Commit**
```bash
git add knowledge_os/tests/test_local_team.py knowledge_os/app/ai_core.py
git commit -m "test: add local team generation tests and fallback logic"
```
