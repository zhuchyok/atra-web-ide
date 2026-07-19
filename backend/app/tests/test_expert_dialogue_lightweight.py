from app.routers.expert_dialogue import DialogueRequest, _want_lightweight_first


def test_lightweight_is_default_when_not_overridden(monkeypatch):
    monkeypatch.setattr("app.routers.expert_dialogue.PREFER_LIGHTWEIGHT_DEFAULT", True)
    req = DialogueRequest(topic="P0 test")
    assert _want_lightweight_first(req) is True


def test_force_full_overrides_lightweight_flag(monkeypatch):
    monkeypatch.setattr("app.routers.expert_dialogue.PREFER_LIGHTWEIGHT_DEFAULT", True)
    req = DialogueRequest(topic="P0 test", prefer_lightweight=True, force_full=True)
    assert _want_lightweight_first(req) is False
