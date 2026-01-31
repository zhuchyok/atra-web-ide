#!/usr/bin/env python3
"""
Дашборд latency RAG (Фаза 4.1).
Использование: python3 scripts/create_latency_dashboard.py
"""
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_PATH = REPO_ROOT / "latency_benchmark.json"
OUTPUT_PATH = REPO_ROOT / "latency_dashboard.html"


def main():
    if not BENCHMARK_PATH.exists():
        print("❌ Нет latency_benchmark.json. Запустите: python scripts/benchmark_latency.py")
        return 1

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    p50 = data.get("p50_ms", 0)
    p95 = data.get("p95_ms", 0)
    p99 = data.get("p99_ms", 0)
    avg = data.get("avg_ms", 0)
    n = data.get("n_requests", 0)
    svc = data.get("services", {})
    span_totals = data.get("span_totals", {})
    p95_ok = p95 < 300

    # Этапы для bar chart
    span_items = sorted(span_totals.items(), key=lambda x: -x[1])[:6]
    span_names = [s[0] for s in span_items]
    span_values = [s[1] / max(n, 1) for s in span_items]

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Latency Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #58a6ff; margin-bottom: 20px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .metric {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }}
        .metric-value {{ font-size: 2rem; font-weight: bold; }}
        .metric-value.ok {{ color: #3fb950; }}
        .metric-value.fail {{ color: #f85149; }}
        .metric-label {{ font-size: 0.85rem; color: #8b949e; margin-top: 4px; }}
        .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; height: 220px; }}
        .status {{ padding: 8px 16px; border-radius: 6px; display: inline-block; font-weight: 600; margin-bottom: 20px; }}
        .status.pass {{ background: #238636; color: #fff; }}
        .status.fail {{ background: #da3633; color: #fff; }}
        .services {{ display: flex; gap: 12px; margin-bottom: 20px; font-size: 0.9rem; }}
        .service {{ padding: 6px 12px; border-radius: 6px; }}
        .service.on {{ background: #238636; color: #fff; }}
        .service.off {{ background: #30363d; color: #8b949e; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Latency Dashboard</h1>
        <div class="status {'pass' if p95_ok else 'fail'}">P95 {'✅ < 300ms' if p95_ok else '❌ ≥ 300ms'} (цель)</div>
        <div class="services">
            <span class="service {'on' if svc.get('ollama') else 'off'}">Ollama {'✅' if svc.get('ollama') else '❌'}</span>
            <span class="service {'on' if svc.get('mlx') else 'off'}">MLX {'✅' if svc.get('mlx') else '❌'}</span>
        </div>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value {'ok' if p50 < 100 else ''}">{p50:.0f} ms</div>
                <div class="metric-label">P50</div>
            </div>
            <div class="metric">
                <div class="metric-value {'ok' if p95_ok else 'fail'}">{p95:.0f} ms</div>
                <div class="metric-label">P95 (цель &lt; 300)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{p99:.0f} ms</div>
                <div class="metric-label">P99</div>
            </div>
            <div class="metric">
                <div class="metric-value">{avg:.0f} ms</div>
                <div class="metric-label">Avg</div>
            </div>
            <div class="metric">
                <div class="metric-value">{n}</div>
                <div class="metric-label">Запросов</div>
            </div>
        </div>
        <div class="chart-container">
            <canvas id="spanChart"></canvas>
        </div>
    </div>
    <script>
        new Chart(document.getElementById('spanChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(span_names)},
                datasets: [{{
                    label: 'ms avg',
                    data: {json.dumps(span_values)},
                    backgroundColor: '#58a6ff'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    y: {{ beginAtZero: true, title: {{ display: true, text: 'ms' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ Дашборд: {OUTPUT_PATH}")
    print(f"   Откройте: file://{OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    exit(main())
