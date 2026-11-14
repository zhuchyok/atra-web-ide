from pathlib import Path


def test_orchestrate_unknown_category_has_non_recursive_fallback():
    text = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agents"
        / "bridge"
        / "victoria_server.py"
    ).read_text(encoding="utf-8")
    fn = text.split("async def orchestrate_task(self, goal: str) -> str:", 1)[1].split(
        "async def _run_extended_swarm", 1
    )[0]
    assert "return await self.orchestrate_task(goal)" not in fn
    assert "return await self._run_direct_execution(goal, max_steps=600)" in fn
