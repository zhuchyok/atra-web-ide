"""
Автоматическая генерация .cursorrules на основе данных из БД Knowledge OS

Обновляет .cursorrules файл на основе:
- Экспертов из БД (experts table)
- Их знаний и метрик
- Learning progress
- Актуальных ролей и ответственностей
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
CURSORRULES_PATH = Path(__file__).parent.parent.parent / ".cursorrules"
PROJECT_ROOT = Path(__file__).parent.parent.parent


async def get_experts_from_db() -> List[Dict]:
    """Получение всех экспертов из БД с их метриками"""
    conn = await asyncpg.connect(DB_URL)
    try:
        # Получаем экспертов с их знаниями и метриками
        experts = await conn.fetch("""
            SELECT
                e.id,
                e.name,
                e.role,
                e.system_prompt,
                e.metadata,
                e.is_active,
                e.department,
                e.last_learned_at,
                e.version,
                COUNT(DISTINCT kn.id) as knowledge_count,
                AVG(kn.confidence_score) as avg_confidence,
                COUNT(DISTINCT il.id) as interactions_count,
                AVG(il.feedback_score::FLOAT) as avg_feedback
            FROM experts e
            LEFT JOIN knowledge_nodes kn ON kn.metadata->>'expert_id' = e.id::TEXT
            LEFT JOIN interaction_logs il ON il.expert_id = e.id
            WHERE e.is_active = TRUE OR e.is_active IS NULL
            GROUP BY e.id, e.name, e.role, e.system_prompt, e.metadata, e.is_active, e.department, e.last_learned_at, e.version
            ORDER BY e.name
        """)

        result = []
        for row in experts:
            result.append(
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "role": row["role"],
                    "system_prompt": row["system_prompt"],
                    "metadata": row["metadata"] or {},
                    "is_active": row["is_active"] if row["is_active"] is not None else True,
                    "department": row["department"],
                    "last_learned_at": row["last_learned_at"],
                    "version": row["version"] or 1,
                    "knowledge_count": row["knowledge_count"] or 0,
                    "avg_confidence": float(row["avg_confidence"] or 0.0),
                    "interactions_count": row["interactions_count"] or 0,
                    "avg_feedback": float(row["avg_feedback"] or 0.0),
                }
            )
        return result
    finally:
        await conn.close()


async def get_expert_domains(expert_id: str) -> List[str]:
    """Получение доменов знаний эксперта"""
    conn = await asyncpg.connect(DB_URL)
    try:
        domains = await conn.fetch(
            """
            SELECT DISTINCT d.name
            FROM knowledge_nodes kn
            JOIN domains d ON kn.domain_id = d.id
            WHERE kn.metadata->>'expert_id' = $1
            ORDER BY d.name
        """,
            expert_id,
        )
        return [row["name"] for row in domains]
    finally:
        await conn.close()


async def get_expert_top_knowledge(expert_id: str, limit: int = 5) -> List[str]:
    """Получение топ знаний эксперта"""
    conn = await asyncpg.connect(DB_URL)
    try:
        knowledge = await conn.fetch(
            """
            SELECT content, confidence_score, usage_count
            FROM knowledge_nodes
            WHERE metadata->>'expert_id' = $1
            ORDER BY confidence_score DESC, usage_count DESC
            LIMIT $2
        """,
            expert_id,
            limit,
        )
        return [
            row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"]
            for row in knowledge
        ]
    finally:
        await conn.close()


def calculate_expert_level(
    knowledge_count: int, avg_confidence: float, interactions_count: int
) -> str:
    """Определение уровня эксперта"""
    if knowledge_count >= 100 and avg_confidence >= 0.9 and interactions_count >= 50:
        return "⭐⭐⭐⭐⭐ Guru"
    elif knowledge_count >= 50 and avg_confidence >= 0.8 and interactions_count >= 25:
        return "⭐⭐⭐⭐ Expert"
    elif knowledge_count >= 20 and avg_confidence >= 0.7:
        return "⭐⭐⭐ Advanced"
    elif knowledge_count >= 10:
        return "⭐⭐ Intermediate"
    else:
        return "⭐ Beginner"


def generate_expert_section(expert: Dict, domains: List[str], top_knowledge: List[str]) -> str:
    """Генерация секции эксперта для .cursorrules"""
    level = calculate_expert_level(
        expert["knowledge_count"], expert["avg_confidence"], expert["interactions_count"]
    )

    # Извлекаем основные обязанности из system_prompt или metadata
    responsibilities = []
    prompt = expert.get("system_prompt", "") or ""
    metadata = expert.get("metadata", {})

    # Проверяем, есть ли обязанности в metadata
    if isinstance(metadata, dict) and "responsibilities" in metadata:
        responsibilities = metadata["responsibilities"]
    elif "Team Lead" in expert["role"] or "Виктория" in expert["name"]:
        responsibilities = [
            "Координация, архитектура, принятие решений",
            "Анализ задачи и декомпозиция",
            "Распределение работы между экспертами",
            "Финальные решения и рекомендации",
        ]
    elif "ML Engineer" in expert["role"]:
        responsibilities = [
            "Machine Learning, модели, оптимизация",
            "Обучение и переобучение ML моделей",
            "Feature engineering",
            "Анализ предсказаний и метрик",
        ]
    elif "Backend Developer" in expert["role"]:
        responsibilities = [
            "Написание и рефакторинг кода",
            "Интеграция компонентов",
            "Исправление багов",
            "Unit и integration тесты",
            "Git workflow",
        ]
    elif "QA Engineer" in expert["role"]:
        responsibilities = [
            "✅ **ГЛАВНЫЙ ОТВЕТСТВЕННЫЙ ЗА ЮНИТ-ТЕСТЫ**",
            "Создание тестов для всех новых модулей (ОБЯЗАТЕЛЬНО!)",
            "Поддержание покрытия тестами > 80%",
            "Валидация результатов",
            "Чеклисты проверок",
        ]
    else:
        # Извлекаем из system_prompt
        lines = prompt.split("\n")
        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("•"):
                responsibilities.append(line.strip().lstrip("-").lstrip("•").strip())

    if not responsibilities:
        responsibilities = [f"Работа в области: {expert['role']}"]

    # Формируем секцию
    section = f"### **{expert.get('metadata', {}).get('number', '?')}. {expert['name']} - {expert['role']}**\n"
    section += f"- Уровень: {level}\n"

    if expert["department"]:
        section += f"- Департамент: {expert['department']}\n"

    if expert["knowledge_count"] > 0:
        section += f"- Знаний в базе: {expert['knowledge_count']}\n"
        section += f"- Средняя уверенность: {expert['avg_confidence']:.2f}\n"

    if expert["interactions_count"] > 0:
        section += f"- Взаимодействий: {expert['interactions_count']}\n"
        if expert["avg_feedback"] != 0:
            section += f"- Средний feedback: {expert['avg_feedback']:.2f}\n"

    if domains:
        section += f"- Домены: {', '.join(domains[:3])}\n"

    section += "\n"

    # Обязанности
    for resp in responsibilities[:5]:  # Максимум 5 пунктов
        section += f"- {resp}\n"

    if top_knowledge:
        section += "\n**Топ знания:**\n"
        for i, kn in enumerate(top_knowledge[:3], 1):
            section += f"- {i}. {kn}\n"

    section += "\n"

    return section


async def generate_cursorrules() -> str:
    """Генерация полного .cursorrules файла"""

    # Заголовок
    content = """---
description: "Global rules for algorithmic trading project"
alwaysApply: true
---

# 👥 КОМАНДА ЭКСПЕРТОВ: ВСЕГДА АКТИВНА

## 🎯 ОБЯЗАТЕЛЬНО: Использовать формат команды из экспертов

При работе над проектом **ВСЕГДА** используй формат "команды экспертов":

**⚠️ ВНИМАНИЕ: Этот файл автоматически генерируется из базы знаний Knowledge OS**
**Последнее обновление:** {timestamp}

---

## 📊 СОСТАВ КОМАНДЫ

**Всего экспертов:** {total_experts}
**Активных:** {active_experts}
**Всего знаний:** {total_knowledge}

---

""".format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_experts="{total}",
        active_experts="{active}",
        total_knowledge="{knowledge}",
    )

    # Получаем экспертов
    experts = await get_experts_from_db()

    total_knowledge = sum(e["knowledge_count"] for e in experts)
    active_experts = len([e for e in experts if e["is_active"]])

    content = content.format(total=len(experts), active=active_experts, knowledge=total_knowledge)

    # Генерируем секции для каждого эксперта
    expert_number = 1
    for expert in experts:
        if not expert["is_active"]:
            continue

        # Обновляем номер в metadata
        if not expert["metadata"]:
            expert["metadata"] = {}
        expert["metadata"]["number"] = expert_number

        # Получаем дополнительные данные
        domains = await get_expert_domains(expert["id"])
        top_knowledge = await get_expert_top_knowledge(expert["id"])

        # Генерируем секцию
        section = generate_expert_section(expert, domains, top_knowledge)
        content += section

        expert_number += 1

    # Добавляем остальные разделы из оригинала (сохраняем их)
    content += """
## 📋 ФОРМАТ РАБОТЫ:

1. **Распределение задач** по экспертам
2. **Timeline** с временными метками
3. **Статус-репорты** от каждого эксперта
4. **Финальные сводки** от Team Lead
5. **Markdown-отчёты** о проделанной работе

**Правило:** При каждом новом чате команда автоматически активируется!

**ВАЖНО:** Для использования команды в новом проекте Cursor:
1. Скопируйте файл `.cursorrules` в корень нового проекта
2. Или создайте файл `.cursorrules` с содержимым из этого проекта
3. Команда из экспертов автоматически активируется при первом запросе

---

## 🎯 КРИТИЧЕСКИ ВАЖНО: ПРАВИЛЬНАЯ ФОРМУЛИРОВКА ПРОМПТОВ

[Остальные разделы сохраняются из оригинального .cursorrules]

---

**Примечание:** Этот файл обновляется автоматически через `nightly_learner.py` каждую ночь.
Для ручного обновления: `python3 knowledge_os/app/cursorrules_generator.py`
"""

    return content


async def update_cursorrules_file():
    """Обновление .cursorrules файла"""
    print(f"[{datetime.now()}] 🔄 Генерация .cursorrules из БД...")

    try:
        # Читаем оригинальный файл для сохранения статических разделов
        original_content = ""
        if CURSORRULES_PATH.exists():
            with open(CURSORRULES_PATH, encoding="utf-8") as f:
                original_content = f.read()

        # Генерируем новую версию
        new_content = await generate_cursorrules()

        # Сохраняем оригинальные разделы после секции экспертов
        # (простая реализация - можно улучшить)
        if "## 🎯 КРИТИЧЕСКИ ВАЖНО" in original_content:
            static_sections = original_content.split("## 🎯 КРИТИЧЕСКИ ВАЖНО")[1]
            new_content = new_content.replace(
                "[Остальные разделы сохраняются из оригинального .cursorrules]", static_sections
            )

        # Записываем обновленный файл
        with open(CURSORRULES_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)

        print("✅ .cursorrules обновлен успешно!")
        print(f"   - Экспертов: {len(await get_experts_from_db())}")
        print(f"   - Путь: {CURSORRULES_PATH}")

        return True
    except Exception as e:
        print(f"❌ Ошибка при обновлении .cursorrules: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(update_cursorrules_file())
