#!/usr/bin/env python3
"""
Автоматическая оптимизация оркестрации на основе A/B метрик.
Запуск: python scripts/auto_optimize_orchestration.py [--hours 6] [--dry-run]
Рекомендуется по cron каждые 6 часов.
"""
import argparse
import asyncio
import os
import sys

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


async def auto_optimize(hours: int = 6, dry_run: bool = True) -> None:
    # 1. Собрать метрики (импорт из той же папки scripts)
    _scripts = os.path.join(_REPO_ROOT, "scripts")
    if _scripts not in sys.path:
        sys.path.insert(0, _scripts)
    from collect_ab_metrics import collect_metrics
    data = await collect_metrics(hours=hours)
    if data.get("error"):
        print("Error collecting metrics:", data["error"])
        return
    v2 = data.get("v2", {})
    existing = data.get("existing", {})
    comp = data.get("comparison", {})
    success_diff = (comp.get("success_rate_difference") or 0) * 100

    # 2. Оптимизатор (knowledge_os)
    ko_app = os.path.join(_REPO_ROOT, "knowledge_os", "app")
    if ko_app not in sys.path:
        sys.path.insert(0, ko_app)
    try:
        from app.task_orchestration.optimizer import OrchestrationOptimizer
        optimizer = OrchestrationOptimizer()
        result = await optimizer.optimize_based_on_metrics(data)
        for s in result.get("suggestions", []):
            print("Suggestion:", s.get("type"), "-", s.get("reason"))
            if not dry_run and s.get("type") == "increase_v2_percentage":
                new_pct = s.get("suggested")
                if new_pct is not None:
                    os.environ["ORCHESTRATION_V2_PERCENTAGE"] = str(int(new_pct))
                    print("  -> ORCHESTRATION_V2_PERCENTAGE set to", new_pct, "(restart Victoria to apply)")
    except ImportError as e:
        print("Optimizer not available:", e)

    if success_diff > 20:
        print("V2 shows +%.1f%% better success rate; consider increasing V2 traffic." % success_diff)
    print("Auto-optimization check completed (dry_run=%s)." % dry_run)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true", default=True, help="Do not apply changes")
    parser.add_argument("--apply", action="store_true", help="Apply suggested changes (e.g. env)")
    args = parser.parse_args()
    asyncio.run(auto_optimize(hours=args.hours, dry_run=not args.apply))


if __name__ == "__main__":
    main()
