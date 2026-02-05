"""
Тесты: поболтать vs что-то прошу без ключевых слов.
Проверяем _is_casual_chat и fallback-отдел Strategy/Data для просьб.
Запуск: из knowledge_os: python3 -m pytest tests/test_victoria_chat_and_request.py -v
        или: python3 tests/test_victoria_chat_and_request.py
"""

import asyncio
import os
import sys

# Для импорта app при запуске из корня knowledge_os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

os.environ.setdefault("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


class TestCasualChatDetection:
    """Проверка: короткие и разговорные фразы = casual chat."""

    def test_chat_phrases_recognized(self):
        from app.victoria_enhanced import VictoriaEnhanced
        v = VictoriaEnhanced()
        chat_phrases = [
            "Привет",
            "Как дела?",
            "Хочу просто поболтать",
            "Расскажи о себе",
            "Что умеешь?",
            "Hello",
            "Спасибо, пока!",
        ]
        for phrase in chat_phrases:
            assert v._is_casual_chat(phrase), f"Ожидалось casual chat: '{phrase}'"

    def test_short_messages_are_chat(self):
        from app.victoria_enhanced import VictoriaEnhanced
        v = VictoriaEnhanced()
        assert v._is_casual_chat("Привет!")
        assert v._is_casual_chat("Ок")

    def test_requests_not_chat(self):
        from app.victoria_enhanced import VictoriaEnhanced
        v = VictoriaEnhanced()
        not_chat = [
            "Помоги настроить docker для проекта",
            "Нужен анализ данных по продажам за квартал",
            "Сделай отчёт по бэкенду за месяц",
        ]
        for phrase in not_chat:
            assert not v._is_casual_chat(phrase), f"Не должно быть casual chat: '{phrase}'"


class TestDepartmentFallback:
    """Проверка: просьбы без ключевых слов получают отдел Strategy/Data."""

    def test_request_phrases_get_strategy_data(self):
        from app.department_heads_system import get_department_heads_system
        db_url = os.getenv("DATABASE_URL")
        system = get_department_heads_system(db_url)
        requests_without_keywords = [
            "Помоги с одной задачей",
            "Можешь что-нибудь подсказать?",
            "Прошу разобраться в вопросе",
            "Хочу чтобы ты объяснил",
        ]
        for goal in requests_without_keywords:
            dept = system.determine_department(goal)
            assert dept == "Strategy/Data", f"Ожидался Strategy/Data для '{goal}', получен {dept}"

    def test_keywords_still_work(self):
        from app.department_heads_system import get_department_heads_system
        db_url = os.getenv("DATABASE_URL")
        system = get_department_heads_system(db_url)
        assert system.determine_department("Нужен анализ данных") == "Strategy/Data"
        assert system.determine_department("настроить docker") == "DevOps/Infra"
        assert system.determine_department("api для пользователей") == "Backend"

    def test_file_creation_skips_department(self):
        from app.department_heads_system import get_department_heads_system
        db_url = os.getenv("DATABASE_URL")
        system = get_department_heads_system(db_url)
        # Фразы про создание файла/страницы: отдел может быть None или назначен (Backend, ML/AI и т.д.)
        dept1 = system.determine_department("напиши файл конфига")
        dept2 = system.determine_department("создай html страницу")
        assert dept1 is None or dept1 in ("Backend", "ML/AI", "Strategy/Data")
        assert dept2 is None or dept2 in ("Backend", "ML/AI", "Strategy/Data", "Creative")


async def _test_should_use_department_heads_skips_chat():
    """Для casual chat _should_use_department_heads возвращает False."""
    from app.victoria_enhanced import VictoriaEnhanced
    v = VictoriaEnhanced()
    should_use, dept_info = await v._should_use_department_heads("Привет, как дела?", category="general")
    assert should_use is False
    assert dept_info == {}


class TestPreferExpertsFirstDelegation:
    """PREFER_EXPERTS_FIRST: в Veronica только простые одношаговые; «сделай/напиши код» — Victoria/эксперты."""

    def test_simple_veronica_request_detected(self):
        from app.victoria_enhanced import VictoriaEnhanced
        v = VictoriaEnhanced()
        assert v._is_simple_veronica_request("покажи файлы в src")
        assert v._is_simple_veronica_request("выведи список файлов")
        assert v._is_simple_veronica_request("прочитай файл README.md")
        assert v._is_simple_veronica_request("покажи список") is True
        assert v._is_simple_veronica_request("сделай отчёт по продажам") is False
        assert v._is_simple_veronica_request("напиши код для API") is False

    @pytest.mark.asyncio
    async def test_should_delegate_only_simple_when_prefer_experts_first(self):
        from app.victoria_enhanced import VictoriaEnhanced
        prev = os.environ.get("PREFER_EXPERTS_FIRST")
        try:
            os.environ["PREFER_EXPERTS_FIRST"] = "true"
            v = VictoriaEnhanced()
            if not v.task_delegator:
                pytest.skip("TaskDelegator не инициализирован (опциональный компонент)")
            # «Сделай отчёт» — не одношаговый → не делегируем Veronica
            should, info = await v._should_delegate_task("Сделай отчёт по метрикам за месяц")
            assert should is False, "При PREFER_EXPERTS_FIRST execution-задачи остаются Victoria/экспертам"
            # «Покажи файлы» — простое → делегируем
            should2, info2 = await v._should_delegate_task("покажи файлы в backend")
            assert should2 is True
            assert info2.get("agent") == "Вероника"
        finally:
            if prev is not None:
                os.environ["PREFER_EXPERTS_FIRST"] = prev
            elif "PREFER_EXPERTS_FIRST" in os.environ:
                del os.environ["PREFER_EXPERTS_FIRST"]


async def _test_should_delegate_only_simple_when_prefer_experts_first():
    """Обёртка для запуска без pytest."""
    from app.victoria_enhanced import VictoriaEnhanced
    v = VictoriaEnhanced()
    if not v.task_delegator:
        return  # skip без pytest
    prev = os.environ.get("PREFER_EXPERTS_FIRST")
    try:
        os.environ["PREFER_EXPERTS_FIRST"] = "true"
        should, _ = await v._should_delegate_task("Сделай отчёт по метрикам за месяц")
        assert should is False
        should2, info2 = await v._should_delegate_task("покажи файлы в backend")
        assert should2 is True and info2.get("agent") == "Вероника"
    finally:
        if prev is not None:
            os.environ["PREFER_EXPERTS_FIRST"] = prev
        elif "PREFER_EXPERTS_FIRST" in os.environ:
            del os.environ["PREFER_EXPERTS_FIRST"]


if HAS_PYTEST:
    @pytest.mark.asyncio
    async def test_should_use_department_heads_skips_chat():
        await _test_should_use_department_heads_skips_chat()


def run_all_without_pytest():
    """Запуск всех тестов без pytest."""
    t1 = TestCasualChatDetection()
    t1.test_chat_phrases_recognized()
    t1.test_short_messages_are_chat()
    t1.test_requests_not_chat()
    print("✅ TestCasualChatDetection")

    t2 = TestDepartmentFallback()
    t2.test_request_phrases_get_strategy_data()
    t2.test_keywords_still_work()
    t2.test_file_creation_skips_department()
    print("✅ TestDepartmentFallback")

    asyncio.run(_test_should_use_department_heads_skips_chat())
    print("✅ test_should_use_department_heads_skips_chat")

    t3 = TestPreferExpertsFirstDelegation()
    t3.test_simple_veronica_request_detected()
    print("✅ TestPreferExpertsFirstDelegation.test_simple_veronica_request_detected")
    try:
        asyncio.run(_test_should_delegate_only_simple_when_prefer_experts_first())
        print("✅ TestPreferExpertsFirstDelegation.test_should_delegate_only_simple")
    except Exception as e:
        if "TaskDelegator" in str(e) or "skip" in str(e).lower():
            print("⏭️ TestPreferExpertsFirstDelegation (TaskDelegator не загружен — пропуск)")
        else:
            raise
    print("\n✅ Все тесты пройдены.")


if __name__ == "__main__":
    run_all_without_pytest()
