---
name: multi-agent-coordinator
description: Координация нескольких AI агентов для параллельной работы. Используй для запуска агентов в нескольких потоках и объединения результатов.
---

# Multi-Agent Coordinator Skill

## Когда использовать
- Параллельная обработка задач
- Распределение работы между агентами
- Сбор результатов от нескольких источников
- Масштабирование вычислений

## Архитектура

### Master Agent Pattern
```
User Request
      ↓
Master Agent (Coordinator)
      ├→ Agent 1 → Result 1
      ├→ Agent 2 → Result 2
      ├→ Agent 3 → Result 3
      └→ ...
      ↓
Aggregate Results
```

### Примеры использования

#### 1. Parallel Research
```python
async def research_topic(topic):
    agents = [
        Agent("web", search_web),
        Agent("academic", search_arxiv),
        Agent("docs", search_docs),
        Agent("social", search_social),
    ]
    
    results = await asyncio.gather(*[
        agent.search(topic) for agent in agents
    ])
    
    return aggregate(results)
```

#### 2. Code Review Pipeline
```python
async def review_pr(pr_diff):
    reviewers = [
        Reviewer("security", scan_security),
        Reviewer("style", check_style),
        Reviewer("tests", check_tests),
        Reviewer("docs", check_docs),
    ]
    
    findings = await asyncio.gather(*[
        reviewer.review(pr_diff) for reviewer in reviewers
    ])
    
    return prioritize(findings)
```

## Agent Types

### Available Agent Types
- **Research Agent** - поиск информации
- **Code Review Agent** - review кода
- **Test Agent** - генерация тестов
- **Docs Agent** - документация
- **Security Agent** - security scan
- **Performance Agent** - профилирование
- **Refactor Agent** - рефакторинг

## Coordination Patterns

### Fan-out, Fan-in
```python
async def fan_out_fan_in(tasks):
    # Fan-out: запустить все параллельно
    futures = [agent.process(task) for task in tasks]
    
    # Fan-in: собрать результаты
    results = await asyncio.gather(*futures)
    
    # Aggregate
    return aggregate(results)
```

### Pipeline
```python
async def pipeline(stages):
    data = initial_input
    for stage in stages:
        data = await stage.process(data)
    return data
```

### Round Robin
```python
async def round_robin(tasks, agents):
    results = []
    for i, task in enumerate(tasks):
        agent = agents[i % len(agents)]
        result = await agent.process(task)
        results.append(result)
    return results
```

## Output
```json
{
  "total_agents": 4,
  "parallel_results": [...],
  "aggregate": {...},
  "duration_seconds": 2.3,
  "cost_credits": 0.05
}
```

## Rate Limiting
```python
# Ограничение параллельных агентов
MAX_CONCURRENT = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
```

## Commands
```
/agents run <task>       # Запустить всех
/agents status          # Статус агентов
/agents cancel          # Отмена
/agents results         # Результаты
```