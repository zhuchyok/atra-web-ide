from app.skill_mapper import SkillMapper


def test_cursor_method_classifies_pair_goal():
    mapper = SkillMapper()
    info = mapper.classify_task("Сделай близнец задачи и работай по методу cursor_method")
    assert info is not None
    assert info["skill"] == "cursor_method"
    text = mapper.get_skill_instructions("cursor_method")
    assert "готово" in text.lower() or "Факты" in text
