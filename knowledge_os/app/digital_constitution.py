"""
[SINGULARITY 20.0] Digital Constitution (Anthropic-style).
Core principles and ethical filters for Victoria and the expert team.
"""

CONSTITUTION_PRINCIPLES = [
    {
        "id": "C1",
        "name": "Data-Driven Decisions",
        "rule": "Всегда отдавай приоритет данным из Knowledge OS над предположениями. Если данных нет - запрашивай исследование (Scout).",
    },
    {
        "id": "C2",
        "name": "Security First",
        "rule": "Любое архитектурное решение должно проходить проверку на уязвимости. Никогда не предлагай открытые порты без туннелей.",
    },
    {
        "id": "C3",
        "name": "Predictive Correction",
        "rule": "Перед выполнением задачи проверь 'Голос Опыта' на наличие прошлых ошибок в похожих сценариях.",
    },
    {
        "id": "C4",
        "name": "Scalability by Design",
        "rule": "Проектируй системы как микросервисы (Google-style). Избегай монолитных решений, которые сложно масштабировать.",
    },
    {
        "id": "C5",
        "name": "Constitutional Honesty",
        "rule": "Если уровень уверенности (confidence_score) ниже 0.7, агент обязан сообщить об этом и предложить дебаты (Brainstorm).",
    },
]


def get_constitution_context() -> str:
    """Returns the formatted constitution for prompt injection."""
    context = "\n### 📜 ЦИФРОВАЯ КОНСТИТУЦИЯ КОРПОРАЦИИ (CONSTITUTIONAL AI):\n"
    for p in CONSTITUTION_PRINCIPLES:
        context += f"- [{p['id']}] {p['name']}: {p['rule']}\n"
    return context


# AGENT_OPERATIONAL_GUIDE - Hard-earned operational knowledge for agents
AGENT_OPERATIONAL_GUIDE = """
### 🔧 ОПЕРАЦИОННОЕ РУКОВОДСТВО АГЕНТА

## Quick Start
- Start services: `docker compose up -d`
- Run Victoria API: `cd knowledge_os && uvicorn app.main:app --host 0.0.0.0 --port 8010`

## Key Directories
- knowledge_os/app/ — Core AI agents (Victoria, orchestrators, workers)
- knowledge_os/db/ — PostgreSQL schema and migrations
- backend/ — Rust core, frontend/ — React/UI

## Critical Commands
- Query tasks: `docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT status, count(*) FROM tasks GROUP BY status;"`
- Check services: `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`

## Common Fixes
- "Solved:" in responses → Check ai_core.py `_clean_response()`
- Hallucinations → Ensure anti-hallucination prompt in ai_core.py for Victoria
- DB not accessible → Use `docker exec knowledge_postgres psql -U admin -d knowledge_os`
- Worker stuck → Check redis queue in redis_manager.py, task states: pending/in_progress/completed/cancelled

## Env Config
- knowledge_os/.env: VICTORIA_MODEL, VICTORIA_MLX_BRAIN=true
- Timeouts: MLX_GENERATION_TIMEOUT=600, SMART_WORKER_MAX_PENDING=1000

## Advanced Components (Singularity 28.X)
- Symbol Tuning: symbol_tuner.py (8 behavior symbols)
- Constitutional Rewards: constitutional_rewards.py (штрафы/бонусы)
- Toil Detection: toil_detector.py (автообнаружение рутины)
- Wisdom Pipeline: agent_ab_testing.py (автогенерация правил)
"""
