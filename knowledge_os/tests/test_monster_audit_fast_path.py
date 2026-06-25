from app.expert_worker import _run_monster_pip_runtime_audit, _run_monster_secret_header_audit


def test_monster_fast_audit_detects_runtime_pip(tmp_path, monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "target.py"
    target.write_text(
        "import subprocess\nsubprocess.run(['python3', '-m', 'pip', 'install', 'x'])\n",
        encoding="utf-8",
    )
    prompt = f"проверь файл {target} — есть ли там pip install в рантайме?"

    result = _run_monster_pip_runtime_audit(
        prompt,
        {"source": "victoria_monster_delegation", "source_path": str(target)},
    )

    assert result is not None
    assert "ПРОБЛЕМА" in result
    assert "L2:" in result


def test_monster_fast_audit_returns_ok_for_clean_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "clean.py"
    target.write_text("print('hello')\n", encoding="utf-8")
    prompt = f"проверь файл {target} — есть ли там pip install в рантайме?"

    result = _run_monster_pip_runtime_audit(
        prompt,
        {"source": "victoria_monster_delegation", "source_path": str(target)},
    )

    assert result is not None
    assert result.startswith("ОК")


def test_monster_fast_audit_returns_none_for_unrelated_prompt(monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    result = _run_monster_pip_runtime_audit("просто напиши ответ", {})
    assert result is None


def test_monster_fast_audit_toggle_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "false")
    target = tmp_path / "target.py"
    target.write_text("import os\nos.system('pip install x')\n", encoding="utf-8")
    prompt = f"проверь файл {target} — есть ли там pip install в рантайме?"

    result = _run_monster_pip_runtime_audit(
        prompt,
        {"source": "victoria_monster_delegation", "source_path": str(target)},
    )

    assert result is None


def test_monster_secret_header_audit_detects_hardcoded_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "secret_header.py"
    target.write_text(
        "API_KEY = 'prod-very-secret-key'\nprint('ok')\n",
        encoding="utf-8",
    )
    prompt = f"проверь файл {target} — есть ли там hardcoded секреты или пароли в первых 30 строках?"

    result = _run_monster_secret_header_audit(
        prompt,
        {"source": "victoria_monster_delegation", "source_path": str(target)},
    )

    assert result is not None
    assert "ПРОБЛЕМА" in result
    assert "L1:" in result


def test_monster_secret_header_audit_ok_for_env_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("MONSTER_AUDIT_FAST_PATH", "true")
    target = tmp_path / "safe_header.py"
    target.write_text(
        "import os\nAPI_KEY = os.getenv('API_KEY')\n",
        encoding="utf-8",
    )
    prompt = f"check file {target} for hardcoded secrets in first 30 lines"

    result = _run_monster_secret_header_audit(
        prompt,
        {"source": "victoria_monster_delegation", "source_path": str(target)},
    )

    assert result is not None
    assert result.startswith("ОК")
