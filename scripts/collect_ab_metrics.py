#!/usr/bin/env python3
"""
Сбор и сравнение метрик двух систем оркестрации (V2 vs existing) для A/B теста.
Читает tasks из knowledge_os с полем orchestrator_version.
Запуск: python scripts/collect_ab_metrics.py [--hours 24] [--output json]
"""
import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# Добавляем корень проекта в path
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    import asyncpg
except ImportError:
    asyncpg = None


def _get_db_url() -> str:
    return os.getenv("DATABASE_URL") or "postgresql://admin:secret@localhost:5432/knowledge_os"


async def collect_metrics(hours: int = 24) -> dict:
    """Собрать метрики за последние N часов из таблицы tasks."""
    if not asyncpg:
        return {"error": "asyncpg not installed", "v2": {}, "existing": {}, "comparison": {}}
    db_url = _get_db_url()
    v2_metrics = {
        "total_tasks": 0,
        "successful_tasks": 0,
        "durations": [],
        "by_complexity": defaultdict(list),
    }
    existing_metrics = {
        "total_tasks": 0,
        "successful_tasks": 0,
        "durations": [],
        "by_complexity": defaultdict(list),
    }
    try:
        conn = await asyncpg.connect(db_url)
        # Интервал: NOW() - N hours (parameterized)
        query = """
        SELECT id, description, status, result,
               complexity_score, task_type, orchestrator_version,
               created_at, completed_at
        FROM tasks
        WHERE created_at > NOW() - make_interval(hours => $1)
          AND orchestrator_version IN ('v2', 'existing')
        """
        rows = await conn.fetch(query, hours)
        await conn.close()
    except Exception as e:
        return {
            "error": str(e),
            "v2": dict(v2_metrics),
            "existing": dict(existing_metrics),
            "comparison": {},
        }

    for row in rows:
        duration = 0.0
        if row.get("completed_at") and row.get("created_at"):
            duration = (row["completed_at"] - row["created_at"]).total_seconds()
        version = (row.get("orchestrator_version") or "existing").strip().lower()
        if version == "v2":
            metrics_dict = v2_metrics
        else:
            metrics_dict = existing_metrics

        metrics_dict["total_tasks"] += 1
        if (row.get("status") or "").lower() == "completed":
            metrics_dict["successful_tasks"] += 1
        if duration > 0:
            metrics_dict["durations"].append(duration)

        complexity = float(row.get("complexity_score") or 0.5)
        if complexity < 0.3:
            group = "simple"
        elif complexity < 0.7:
            group = "medium"
        else:
            group = "complex"
        metrics_dict["by_complexity"][group].append({
            "duration": duration,
            "success": (row.get("status") or "").lower() == "completed",
        })

    def _calc_complexity_metrics(m: dict) -> dict:
        out = {}
        for group, items in m["by_complexity"].items():
            if not items:
                continue
            successes = sum(1 for x in items if x.get("success"))
            durations = [x["duration"] for x in items if x["duration"] > 0]
            out[group] = {
                "count": len(items),
                "success_rate": successes / len(items) if items else 0,
                "avg_duration": sum(durations) / len(durations) if durations else 0,
            }
        return out

    v2_success_rate = (
        v2_metrics["successful_tasks"] / v2_metrics["total_tasks"]
        if v2_metrics["total_tasks"] > 0 else 0
    )
    existing_success_rate = (
        existing_metrics["successful_tasks"] / existing_metrics["total_tasks"]
        if existing_metrics["total_tasks"] > 0 else 0
    )
    v2_avg_duration = (
        sum(v2_metrics["durations"]) / len(v2_metrics["durations"])
        if v2_metrics["durations"] else 0
    )
    existing_avg_duration = (
        sum(existing_metrics["durations"]) / len(existing_metrics["durations"])
        if existing_metrics["durations"] else 0
    )

    comparison = {
        "v2": {
            "total_tasks": v2_metrics["total_tasks"],
            "success_rate": v2_success_rate,
            "avg_duration": v2_avg_duration,
            "by_complexity": _calc_complexity_metrics(v2_metrics),
        },
        "existing": {
            "total_tasks": existing_metrics["total_tasks"],
            "success_rate": existing_success_rate,
            "avg_duration": existing_avg_duration,
            "by_complexity": _calc_complexity_metrics(existing_metrics),
        },
        "comparison": {
            "success_rate_difference": v2_success_rate - existing_success_rate,
            "duration_difference": existing_avg_duration - v2_avg_duration,
            "percentage_faster": (
                (existing_avg_duration - v2_avg_duration) / existing_avg_duration * 100
                if existing_avg_duration > 0 else 0
            ),
        },
    }
    return {"error": None, "hours": hours, "collected_at": datetime.utcnow().isoformat(), **comparison}


def main():
    parser = argparse.ArgumentParser(description="Collect A/B metrics for orchestration V2 vs existing")
    parser.add_argument("--hours", type=int, default=24, help="Last N hours to aggregate")
    parser.add_argument("--output", choices=("json", "text"), default="text", help="Output format")
    args = parser.parse_args()
    data = asyncio.run(collect_metrics(hours=args.hours))
    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    if data.get("error"):
        print("Error:", data["error"])
        return
    c = data.get("comparison", data)
    v2 = c.get("v2", {})
    ex = c.get("existing", {})
    comp = c.get("comparison", {})
    print(f"Last {data.get('hours', 24)} hours — A/B Orchestration Metrics")
    print("V2:      total_tasks=%s success_rate=%.2f%% avg_duration=%.1fs" % (
        v2.get("total_tasks", 0), (v2.get("success_rate") or 0) * 100, v2.get("avg_duration") or 0))
    print("Existing: total_tasks=%s success_rate=%.2f%% avg_duration=%.1fs" % (
        ex.get("total_tasks", 0), (ex.get("success_rate") or 0) * 100, ex.get("avg_duration") or 0))
    print("Comparison: success_rate_diff=%.2f%% duration_diff=%.1fs (positive = V2 faster)" % (
        (comp.get("success_rate_difference") or 0) * 100, comp.get("duration_difference") or 0))


if __name__ == "__main__":
    main()
