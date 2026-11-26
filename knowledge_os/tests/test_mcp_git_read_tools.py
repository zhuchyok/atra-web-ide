"""Wave2 polish: MCP exposes git read tools, not mutate."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP = ROOT / "src" / "agents" / "bridge" / "victoria_mcp_server.py"


def test_mcp_has_git_read_tools():
    text = MCP.read_text(encoding="utf-8")
    for name in (
        "victoria_git_status",
        "victoria_git_diff",
        "victoria_git_log",
        "victoria_git_pr_list",
    ):
        assert f"async def {name}" in text, name


def test_mcp_has_no_git_mutate_tools():
    text = MCP.read_text(encoding="utf-8")
    for name in (
        "victoria_git_add",
        "victoria_git_commit",
        "victoria_git_push",
        "victoria_git_branch_create",
    ):
        assert f"async def {name}" not in text, name
