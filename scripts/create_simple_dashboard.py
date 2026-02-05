#!/usr/bin/env python3
"""
Дашборд качества RAG v2 (Фаза 4.1, День 5).
Рекомендации SRE (Елена): детализация по запросам, алерты, история метрик.
Использование: python3 scripts/create_simple_dashboard.py
"""
import html
import json
from pathlib import Path
from datetime import datetime
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

# Пороги по умолчанию (как в run_quality_pipeline.sh)
DEFAULT_THRESHOLDS = {"faithfulness": 0.8, "relevance": 0.85, "coherence": 0.7}


def load_quality_alerts():
    """Загружает алерты из backend/quality_alerts.json (QualityMonitor)."""
    path = REPO_ROOT / "backend" / "quality_alerts.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("alerts", [])
    except Exception:
        return []


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


def load_problematic_analysis():
    """Загружает scripts/problematic_queries_analysis.json если есть."""
    path = REPO_ROOT / "problematic_queries_analysis.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def generate_dashboard_html(history, latest, alerts):
    """Генерирует HTML (v2: пороги, цели, рекомендации, проблемные запросы)."""
    thresholds = DEFAULT_THRESHOLDS.copy()
    if latest and isinstance(latest.get("thresholds"), dict):
        thresholds.update(latest["thresholds"])
    th_faith = thresholds.get("faithfulness", 0.8) * 100
    th_rel = thresholds.get("relevance", 0.85) * 100
    th_coh = thresholds.get("coherence", 0.7) * 100

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
        passed = latest.get("passed")
        if passed is None:
            passed = (
                current_faith >= th_faith
                and current_rel >= th_rel
                and current_coh >= th_coh
            )
        results = latest.get("results", [])
    else:
        current_faith = current_rel = current_coh = 0
        total = 0
        passed = False
        results = []

    # Классы метрик (ok/fail по порогу)
    class_faith = "metric-ok" if current_faith >= th_faith else "metric-fail"
    class_rel = "metric-ok" if current_rel >= th_rel else "metric-fail"
    class_coh = "metric-ok" if current_coh >= th_coh else "metric-fail"

    # Рекомендации по улучшению (конкретные шаги)
    recs = []
    if current_rel < th_rel:
        recs.append(
            f"<strong>Relevance</strong> ({current_rel:.1f}% при цели ≥{th_rel:.0f}%) — "
            "добавьте в базу знаний ответы на частые запросы (тарифы, Victoria, RAG, порты, документация); "
            "проверьте ретривер и порог similarity; включите <code>RERANKING_ENABLED=true</code> в пайплайне."
        )
    if current_faith < th_faith:
        recs.append(
            f"<strong>Faithfulness</strong> ({current_faith:.1f}% при цели ≥{th_faith:.0f}%) — "
            "ответы должны опираться на контекст: проверьте ретривер, размер чанков и фильтрацию по домену."
        )
    if current_coh < th_coh:
        recs.append(
            f"<strong>Coherence</strong> ({current_coh:.1f}% при цели ≥{th_coh:.0f}%) — "
            "улучшите формулировки ответов и постобработку (шаблоны, инструкции для LLM)."
        )
    if not recs:
        recs.append("Все пороги пройдены. Для дальнейшего улучшения: расширьте validation set и следите за алертами.")
    if not passed and (current_rel < th_rel or current_faith < th_faith):
        recs.append(
            "Self-healing: очистите RAG-кэш и перезапустите пайплайн — "
            "<code>backend/.venv/bin/python3 scripts/quality_heal_rag_cache.py && ./scripts/run_quality_pipeline.sh</code>"
        )
    recommendations_html = "".join(f"<li style=\"margin-bottom: 8px;\">{r}</li>" for r in recs)

    # Проблемные запросы (низкий relevance или faithfulness) — топ-15
    problem_rows = []
    with_scores = [
        (r, r.get("metrics", {}).get("relevance", 0), r.get("metrics", {}).get("faithfulness", 0))
        for r in results
    ]
    with_scores.sort(key=lambda x: (x[1], x[2]))  # худшие сначала
    for r, rel, faith in with_scores[:15]:
        q = html.escape((r.get("query") or "")[:55])
        rel_p = rel * 100
        faith_p = faith * 100
        coh_p = r.get("metrics", {}).get("coherence", 0) * 100
        problem_rows.append(
            f"<tr class=\"row-problem\"><td>{q}</td><td>{rel_p:.0f}%</td><td>{faith_p:.0f}%</td><td>{coh_p:.0f}%</td></tr>"
        )
    problematic_table = "\n".join(problem_rows) if problem_rows else "<tr><td colspan='4'>Нет данных</td></tr>"

    # Таблица детализации по запросам (все, подсветка проблемных)
    detail_rows = []
    for r in results[:100]:
        q = html.escape((r.get("query") or "")[:60])
        met = r.get("metrics", {})
        rel = met.get("relevance", 0) * 100
        faith = met.get("faithfulness", 0) * 100
        coh = met.get("coherence", 0) * 100
        row_class = "row-problem" if rel < th_rel or faith < th_faith else ""
        detail_rows.append(
            f"<tr class=\"{row_class}\"><td>{q}</td><td>{rel:.0f}%</td><td>{faith:.0f}%</td><td>{coh:.0f}%</td></tr>"
        )
    detail_table = "\n".join(detail_rows) if detail_rows else "<tr><td colspan='4'>Нет данных</td></tr>"
    detail_caption = f"Показаны первые {min(len(results), 100)} из {len(results)} запросов." if len(results) > 100 else ""

    # Алерты
    alert_items = "".join(
        f"<li>{html.escape(a.get('message', str(a)))}</li>" for a in alerts[:20]
    ) if alerts else "<li>Нет активных алертов</li>"

    # Краткий вывод анализа проблемных запросов (если есть скрипт 5a)
    problematic_analysis = load_problematic_analysis()
    analysis_block = ""
    if problematic_analysis:
        total_q = problematic_analysis.get("total_queries", 0)
        problem_count = problematic_analysis.get("problematic_count", 0)
        analysis_block = f"""
        <div class="chart-container">
            <h2 style="color: #c9d1d9; margin-bottom: 12px;">📋 Анализ проблемных запросов (5a)</h2>
            <p style="color: #8b949e; margin-bottom: 10px;">Всего запросов: <strong>{total_q}</strong>, с relevance &lt; 85%: <strong>{problem_count}</strong></p>
            <p style="color: #8b949e; font-size: 0.9em;">Подробности в <code>problematic_queries_analysis.json</code>. Запустите пайплайн: <code>./scripts/run_quality_pipeline.sh</code></p>
        </div>"""

    html_content = f"""<!DOCTYPE html>
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
        .metric {{ background: #161b22; border: 2px solid #30363d; border-radius: 8px; padding: 20px; }}
        .metric.metric-ok {{ border-color: #238636; }}
        .metric.metric-fail {{ border-color: #da3633; }}
        .metric-value {{ font-size: 2.5rem; font-weight: bold; color: #58a6ff; }}
        .metric.metric-ok .metric-value {{ color: #3fb950; }}
        .metric.metric-fail .metric-value {{ color: #f85149; }}
        .metric-label {{ font-size: 0.9rem; color: #8b949e; margin-top: 5px; }}
        .metric-target {{ font-size: 0.8rem; color: #8b949e; margin-top: 4px; }}
        .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .status {{ padding: 10px 20px; border-radius: 6px; display: inline-block; font-weight: 600; margin-bottom: 20px; }}
        .status.pass {{ background: #238636; color: #fff; }}
        .status.fail {{ background: #da3633; color: #fff; }}
        .recommendations {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .recommendations h2 {{ color: #58a6ff; margin-bottom: 12px; }}
        .recommendations ul {{ color: #c9d1d9; margin-left: 20px; line-height: 1.5; }}
        table {{ width: 100%; border-collapse: collapse; color: #c9d1d9; }}
        th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #30363d; }}
        tr.row-problem {{ background: rgba(248, 81, 73, 0.08); }}
        .detail-caption {{ color: #8b949e; font-size: 0.85rem; margin-top: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 RAG Quality Dashboard</h1>

        <div class="status {'pass' if passed else 'fail'}">
            {'✅ Пороги пройдены' if passed else '⚠️ Требуется улучшение'}
        </div>

        <div class="metrics">
            <div class="metric {class_faith}">
                <div class="metric-value">{current_faith:.1f}%</div>
                <div class="metric-label">Faithfulness</div>
                <div class="metric-target">Цель: ≥{th_faith:.0f}%</div>
            </div>
            <div class="metric {class_rel}">
                <div class="metric-value">{current_rel:.1f}%</div>
                <div class="metric-label">Relevance</div>
                <div class="metric-target">Цель: ≥{th_rel:.0f}%</div>
            </div>
            <div class="metric {class_coh}">
                <div class="metric-value">{current_coh:.1f}%</div>
                <div class="metric-label">Coherence</div>
                <div class="metric-target">Цель: ≥{th_coh:.0f}%</div>
            </div>
            <div class="metric">
                <div class="metric-value">{total}</div>
                <div class="metric-label">Запросов</div>
                <div class="metric-target">в отчёте</div>
            </div>
        </div>

        <div class="recommendations">
            <h2>📋 Рекомендации по улучшению</h2>
            <ul>{recommendations_html}</ul>
        </div>

        <div class="chart-container">
            <canvas id="metricsChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 style="color: #c9d1d9; margin-bottom: 15px;">Запросы с низким Relevance / Faithfulness (топ-15)</h2>
            <table><thead><tr><th style="width:50%">Запрос</th><th>Relevance</th><th>Faithfulness</th><th>Coherence</th></tr></thead><tbody>{problematic_table}</tbody></table>
        </div>

        <div class="chart-container">
            <h2 style="color: #c9d1d9; margin-bottom: 15px;">Детализация по запросам</h2>
            <table><thead><tr><th style="width:50%">Запрос</th><th>Relevance</th><th>Faithfulness</th><th>Coherence</th></tr></thead><tbody>{detail_table}</tbody></table>
            <p class="detail-caption">{detail_caption}</p>
        </div>
        {analysis_block}

        <div class="chart-container">
            <h2 style="color: #c9d1d9; margin-bottom: 15px;">Алерты качества</h2>
            <ul style="color: #c9d1d9; margin-left: 20px;">{alert_items}</ul>
        </div>

        <p style="color: #8b949e; text-align: center; margin-top: 20px;">
            Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · Пороги: faithfulness≥{th_faith:.0f}%, relevance≥{th_rel:.0f}%, coherence≥{th_coh:.0f}%
        </p>
    </div>

    <script>
        const ctx = document.getElementById('metricsChart');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(dates)},
                datasets: [
                    {{ label: 'Faithfulness', data: {json.dumps(faithfulness)}, borderColor: '#f85149', tension: 0.3 }},
                    {{ label: 'Relevance', data: {json.dumps(relevance)}, borderColor: '#58a6ff', tension: 0.3 }},
                    {{ label: 'Coherence', data: {json.dumps(coherence)}, borderColor: '#3fb950', tension: 0.3 }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ labels: {{ color: '#c9d1d9' }} }}, title: {{ display: true, text: 'История метрик качества', color: '#c9d1d9' }} }},
                scales: {{ y: {{ beginAtZero: true, max: 100, grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e' }} }}, x: {{ grid: {{ color: '#30363d' }}, ticks: {{ color: '#8b949e' }} }} }}
            }}
        }});
    </script>
</body>
</html>
"""
    return html_content

def main():
    print("📊 Создание дашборда качества (v2)...")
    history = load_validation_results()
    latest = load_latest_report()
    alerts = load_quality_alerts()
    
    html = generate_dashboard_html(history, latest, alerts)
    output = REPO_ROOT / "quality_dashboard.html"
    
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"✅ Дашборд создан: {output}")
    print(f"🌐 Откройте в браузере: file://{output.resolve()}")
    print(f"   или: cd {REPO_ROOT} && python3 -m http.server 8000")
    return 0

if __name__ == "__main__":
    sys.exit(main())
