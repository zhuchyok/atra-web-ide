import asyncio
import logging
import os
import sys

# Настройка путей
ko_path = "/Users/bikos/Documents/atra-web-ide/knowledge_os"
app_path = os.path.join(ko_path, "app")
if ko_path not in sys.path:
    sys.path.insert(0, ko_path)
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from app.consensus_agent import AgentResponse, ConsensusAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_consensus_v2_logic():
    """Тест логики взвешенного голосования без реальных вызовов LLM."""
    consensus = ConsensusAgent(quorum_threshold=0.6)

    # Сценарий: 3 агента.
    # Агент A (KPI 1.5) говорит "Да"
    # Агент B (KPI 0.8) говорит "Нет"
    # Агент C (KPI 0.8) говорит "Нет"

    # В Consensus v1 (простое большинство) победило бы "Нет" (2 против 1).
    # В Consensus v2 (взвешенное):
    # Вес "Да" = 1.5 * 0.9 = 1.35
    # Вес "Нет" = (0.8 * 0.9) + (0.8 * 0.9) = 0.72 + 0.72 = 1.44
    # "Нет" все еще побеждает, но разрыв меньше.

    # Если Агент A имеет KPI 2.0:
    # Вес "Да" = 2.0 * 0.9 = 1.8
    # Вес "Нет" = 1.44
    # Победит "Да", несмотря на то что он в меньшинстве.

    responses = [
        AgentResponse(
            agent_name="Expert_High_KPI",
            response="Да, это правильный подход.",
            confidence=0.9,
            performance_score=2.0,
        ),
        AgentResponse(
            agent_name="Expert_Low_1",
            response="Нет, я не согласен.",
            confidence=0.9,
            performance_score=0.8,
        ),
        AgentResponse(
            agent_name="Expert_Low_2",
            response="Нет, это ошибка.",
            confidence=0.9,
            performance_score=0.8,
        ),
    ]

    print("\n--- Тест Consensus v2 (Взвешенное голосование) ---")
    for r in responses:
        print(
            f"Агент: {r.agent_name}, Ответ: {r.response[:10]}, KPI: {r.performance_score}, Weight: {r.performance_score * r.confidence:.2f}"
        )

    final_answer, score = consensus._synthesize_final_answer(responses)
    agreement = consensus._calculate_agreement_level(responses)

    print("\nРезультат:")
    print(f"Финальный ответ: {final_answer}")
    print(f"Consensus Score (доля веса): {score:.2f}")
    print(f"Agreement Level: {agreement:.2f}")

    if "Да" in final_answer:
        print(
            "\n✅ Успех: Взвешенное голосование выбрало мнение эксперта с высоким KPI, несмотря на меньшинство."
        )
    else:
        print("\n❌ Ошибка: Логика весов не сработала.")


async def test_db_kpi_loading():
    """Тест загрузки KPI из БД."""
    consensus = ConsensusAgent()
    # Берем известных экспертов
    agents = ["Виктория", "Игорь", "Артур"]

    print("\n--- Тест загрузки KPI из БД ---")
    # Мы не можем легко вызвать приватный метод, но можем проверить через мок или просто запустить часть кода
    import asyncpg

    DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        conn = await asyncpg.connect(DB_URL)
        rows = await conn.fetch(
            "SELECT name, performance_score FROM experts WHERE name = ANY($1)", agents
        )
        await conn.close()
        expert_kpis = {r["name"]: r["performance_score"] or 1.0 for r in rows}
        print(f"Загруженные KPI: {expert_kpis}")
        if expert_kpis:
            print("✅ KPI успешно загружены из БД.")
        else:
            print(
                "⚠️ KPI не найдены (возможно, в БД нет этих экспертов), используются значения по умолчанию."
            )
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")


if __name__ == "__main__":
    asyncio.run(test_consensus_v2_logic())
    asyncio.run(test_db_kpi_loading())
