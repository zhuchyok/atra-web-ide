---
name: claude-code-integration
description: Claude Code Integration - интеграция с Claude Code через Ollama (Anthropic-compatible API)
category: development
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": { "bins": ["claude"] },
        "emoji": "💻",
        "homepage": "https://docs.ollama.com/integrations/claude-code",
      },
  }
---

# Claude Code Integration Skill

Навык на основе **Claude Code Integration** через Ollama. Использование открытых моделей с Claude Code через Anthropic-compatible API.

## Когда использовать

Используй этот навык для:

- Интеграции с Claude Code IDE
- Использования локальных моделей в Claude Code
- Разработки с поддержкой AI в IDE
- Чтения, модификации и выполнения кода через Claude Code

## Рекомендованные модели

- **qwen3-coder** - Специализированная coding модель
- **glm-4.7** - Мощная reasoning модель
- **gpt-oss:20b** - Баланс качества и скорости
- **gpt-oss:120b** - Максимальное качество (Cloud)

## Методология

Claude Code Integration работает через:

1. **Anthropic-compatible API** - Использование Ollama как Anthropic API
2. **Environment Setup** - Настройка переменных окружения
3. **Model Selection** - Выбор модели для Claude Code
4. **Code Interaction** - Взаимодействие с кодом через Claude Code
5. **Execution** - Выполнение кода в рабочей директории

## Примеры использования

```
Быстрая настройка:
ollama launch claude

Или вручную:
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11434

Запуск Claude Code:
claude --model qwen3-coder
```

## Требования

- Claude Code установлен: `curl -fsSL https://claude.ai/install.sh | bash`
- Ollama запущен локально или Cloud API настроен
- Модель с большим контекстом (минимум 64k токенов)

## Интеграция

- OllamaClient: Метод `get_anthropic_compatible_config()`
- Переменные окружения для Claude Code
- Поддержка локальных и cloud моделей

## Источник

- Ollama Claude Code Integration
- Файл: `backend/app/services/ollama.py`
