#!/usr/bin/env python3
"""
Генерация HTML дашборда Auto-Optimizer.
Запуск: PYTHONPATH=backend:. python scripts/create_auto_optimizer_dashboard.py
"""
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "backend" / "auto_optimizer_report.json"
OUTPUT_PATH = REPO_ROOT / "auto_optimizer_dashboard.html"


def main():
    data = {}
    if REPORT_PATH.exists():
        try:
            with open(REPORT_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    metrics = data.get("metrics", {})
    p95 = metrics.get("p95_latency", 0)
    hit_rate = metrics.get("cache_hit_rate", 0)
    last = data.get("last_cycle", "")
    opt_count = data.get("optimizations_count", 0)

    p95_class = "good" if p95 < 150 else ("warning" if p95 < 200 else "critical")
    hit_class = "good" if hit_rate > 60 else ("warning" if hit_rate > 40 else "critical")

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Auto-Optimizer Dashboard</title>
    <style>
        body {{ font-family: system-ui; background: #0d1117; color: #c9d1d9; padding: 20px; }}
        h1 {{ color: #58a6ff; }}
        .metrics {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
        .metric {{ background: #161b22; padding: 20px; border-radius: 8px; min-width: 150px; }}
        .metric-value {{ font-size: 2rem; font-weight: bold; }}
        .good {{ color: #3fb950; }}
        .warning {{ color: #d29922; }}
        .critical {{ color: #f85149; }}
        .meta {{ color: #8b949e; font-size: 0.9rem; margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>🚀 Auto-Optimizer Dashboard</h1>
    <div class="metrics">
        <div class="metric">
            <div class="metric-value {p95_class}">{p95:.0f} ms</div>
            <div>P95 Latency</div>
        </div>
        <div class="metric">
            <div class="metric-value {hit_class}">{hit_rate:.1f}%</div>
            <div>Cache Hit Rate</div>
        </div>
        <div class="metric">
            <div class="metric-value">{opt_count}</div>
            <div>Оптимизаций применено</div>
        </div>
    </div>
    <div class="meta">Последний цикл: {last}</div>
    <div class="meta">API: GET /api/auto-optimizer/dashboard</div>
</body>
</html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ Дашборд: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    exit(main())
