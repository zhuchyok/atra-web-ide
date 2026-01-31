#!/usr/bin/env python3
"""
Создание простого HTML-дашборда для мониторинга качества.
Использование: python3 scripts/create_simple_dashboard.py
"""
import json
from pathlib import Path
from datetime import datetime
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

def load_validation_results():
    """Загружает все validation_results/*.json."""
    results_dir = REPO_ROOT / "backend" / "validation_results"
    if not results_dir.exists():
        return []
    files = sorted(results_dir.glob("validation_*.json"), reverse=True)
    data = []
    for f in files[:30]:  # последние 30
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data.append(json.load(fp))
        except Exception:
            continue
    return data

def load_latest_report():
    """Загружает backend/validation_report.json."""
    path = REPO_ROOT / "backend" / "validation_report.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_dashboard_html(history, latest):
    """Генерирует HTML."""
    # История метрик для графика
    dates = [h.get("timestamp", "")[:10] for h in history]
    faithfulness = [h.get("avg_metrics", {}).get("faithfulness", 0) * 100 for h in history]
    relevance = [h.get("avg_metrics", {}).get("relevance", 0) * 100 for h in history]
    coherence = [h.get("avg_metrics", {}).get("coherence", 0) * 100 for h in history]

    # Текущие метрики
    if latest:
        m = latest.get("avg_metrics", {})
        current_faith = m.get("faithfulness", 0) * 100
        current_rel = m.get("relevance", 0) * 100
        current_coh = m.get("coherence", 0) * 100
        total = latest.get("total_queries", 0)
        passed = latest.get("passed", False)
    else:
        current_faith = current_rel = current_coh = 0
        total = 0
        passed = False

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RAG Quality Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #58a6ff; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .metric {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
        .metric-value {{ font-size: 2.5rem; font-weight: bold; color: #58a6ff; }}
        .metric-label {{ font-size: 0.9rem; color: #8b949e; margin-top: 5px; }}
        .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .status {{ padding: 10px 20px; border-radius: 6px; display: inline-block; font-weight: 600; }}
        .status.pass {{ background: #238636; color: #fff; }}
        .status.fail {{ background: #da3633; color: #fff; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 RAG Quality Dashboard</h1>
        
        <div class="status {'pass' if passed else 'fail'}">
            {'✅ Пороги пройдены' if passed else '⚠️ Требуется улучшение'}
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{current_faith:.1f}%</div>
                <div class="metric-label">Faithfulness</div>
            </div>
            <div class="metric">
                <div class="metric-value">{current_rel:.1f}%</div>
                <div class="metric-label">Relevance</div>
            </div>
            <div class="metric">
                <div class="metric-value">{current_coh:.1f}%</div>
                <div class="metric-label">Coherence</div>
            </div>
            <div class="metric">
                <div class="metric-value">{total}</div>
                <div class="metric-label">Запросов</div>
            </div>
        </div>
        
        <div class="chart-container">
            <canvas id="metricsChart"></canvas>
        </div>
        
        <p style="color: #8b949e; text-align: center; margin-top: 20px;">
            Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
    
    <script>
        const ctx = document.getElementById('metricsChart');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [
                    {{
                        label: 'Faithfulness',
                        data: {json.dumps(faithfulness)},
                        borderColor: '#f85149',
                        tension: 0.3
                    }},
                    {{
                        label: 'Relevance',
                        data: {json.dumps(relevance)},
                        borderColor: '#58a6ff',
                        tension: 0.3
                    }},
                    {{
                        label: 'Coherence',
                        data: {json.dumps(coherence)},
                        borderColor: '#3fb950',
                        tension: 0.3
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#c9d1d9' }} }},
                    title: {{ display: true, text: 'История метрик качества', color: '#c9d1d9' }}
                }},
                scales: {{
                    y: {{ beginAtZero: true, max: 100, grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e' }} }},
                    x: {{ grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    return html

def main():
    print("📊 Создание дашборда качества...")
    history = load_validation_results()
    latest = load_latest_report()
    
    html = generate_dashboard_html(history, latest)
    output = REPO_ROOT / "quality_dashboard.html"
    
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Дашборд создан: {output}")
    print(f"🌐 Откройте в браузере: file://{output.resolve()}")
    print(f"   или: cd {REPO_ROOT} && python3 -m http.server 8000")
    return 0

if __name__ == "__main__":
    sys.exit(main())
