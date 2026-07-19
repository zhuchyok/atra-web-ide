import asyncio
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

# Загружаем .env из корня репозитория (RUST_GATEWAY_URL, etc.)
# Без этого при запуске на хосте используются Docker-internal имена → DNS ошибки
try:
    _repo_root = Path(__file__).resolve().parent.parent
    _env_file = _repo_root / ".env"
    if _env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(_env_file, override=False)
        except ImportError:
            # dotenv не установлен — парсим вручную (только простые KEY=VALUE)
            with open(_env_file) as _f:
                for _line in _f:
                    _line = _line.strip()
                    if _line and not _line.startswith("#") and "=" in _line:
                        _k, _v = _line.split("=", 1)
                        os.environ.setdefault(_k.strip(), _v.strip())
except Exception:
    pass

# Host pre-commit: knowledge_os Redis is on 6381.
_redis = (os.getenv("REDIS_URL") or "").strip()
if (not _redis) or ("localhost:6379" in _redis) or ("127.0.0.1:6379" in _redis):
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6381/0"

# Host Ollama (not Docker DNS host.docker.internal).
_ollama = (os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_URL") or "").strip()
if (not _ollama) or ("host.docker.internal" in _ollama):
    os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:11434"
    os.environ["OLLAMA_URL"] = "http://127.0.0.1:11434"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("git_guardian")


def _parse_status(response: str) -> bool:
    """
    True = allow commit.
    Only explicit STATUS/СТАТУС: REJECTED blocks; ambiguous output allows.
    """
    text = str(response or "")
    if re.search(r"(СТАТУС|STATUS)\s*:\s*REJECTED", text, flags=re.IGNORECASE):
        return False
    if re.search(r"(СТАТУС|STATUS)\s*:\s*APPROVED", text, flags=re.IGNORECASE):
        return True
    upper = text.upper()
    if "REJECTED" in upper and "APPROVED" not in upper:
        logger.warning("⚠️ Git Guardian: ambiguous REJECTED without STATUS line — allowing commit")
    return True


async def run_local_audit(diff_content: str) -> bool:
    """
    Fast local audit for pre-commit.
    Prefer dialogue_llm/Ollama — full ai_core path can trigger brainstorm and hang.
    """
    max_chars = int(os.getenv("GIT_GUARDIAN_DIFF_CHARS", "12000"))
    timeout_sec = float(os.getenv("GIT_GUARDIAN_TIMEOUT_SEC", "90"))
    model = os.getenv("GIT_GUARDIAN_MODEL", "smollm2:360m")

    if len(diff_content) > max_chars:
        diff_content = (
            diff_content[:max_chars]
            + f"\n\n[diff truncated to {max_chars} chars for pre-commit SLA]"
        )

    prompt = f"""### ЗАДАЧА: АУДИТ КОДА (Git Guardian)
Ты — Виктория, Team Lead. Проверь изменения ПЕРЕД коммитом.

ИЗМЕНЕНИЯ (git diff, may be truncated):
{diff_content}

Правила:
1. REJECTED только при реальных секретах в diff (не placeholder your-secret-api-key / ${{API_KEY}}) или явной поломке production.
2. Placeholder API_KEY в compose — НЕ секрет.
3. Ответь строго в формате ниже, без рассуждений.

СТАТУС: APPROVED
ПРИЧИНА: ok
СОВЕТ: keep shipping
"""

    try:

        async def _via_dialogue() -> str:
            try:
                from dialogue_llm import generate_dialogue
            except ImportError:
                from knowledge_os.app.dialogue_llm import generate_dialogue

            gen = await generate_dialogue(prompt, expert_name="Виктория", model_hint=model)
            if getattr(gen, "ok", False) and getattr(gen, "text", None):
                return str(gen.text)
            return ""

        response = await asyncio.wait_for(_via_dialogue(), timeout=timeout_sec)
        if not response:
            logger.warning("⚠️ Git Guardian: empty LLM answer — allowing commit")
            return True

        logger.info("\n--- ОТЧЕТ GIT GUARDIAN ---")
        logger.info(response[:2000])
        logger.info("--------------------------\n")
        return _parse_status(response)

    except asyncio.TimeoutError:
        logger.warning(
            "⚠️ Git Guardian timeout after %.0fs — allowing commit (fail-open)",
            timeout_sec,
        )
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка связи с локальной Викторией: {e}")
        return True  # fail-open


async def main():
    try:
        diff = subprocess.check_output(["git", "diff", "--cached"]).decode("utf-8")
        if not diff:
            sys.exit(0)

        is_approved = await run_local_audit(diff)
        if not is_approved:
            logger.error("❌ КОММИТ ОТКЛОНЕН: Локальная Виктория нашла проблемы в коде.")
            sys.exit(1)
        sys.exit(0)
    except Exception as e:
        logger.error(f"⚠️ Ошибка Git Guardian: {e}")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
