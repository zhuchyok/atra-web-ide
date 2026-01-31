#!/usr/bin/env python3
"""
Фаза 4: генерация HTML-отчёта по качеству (для пайплайна качества).

Использование:
  python scripts/generate_quality_report.py --validation backend/validation_report.json --output quality_report.html
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate quality report HTML")
    parser.add_argument("--validation", default="backend/validation_report.json")
    parser.add_argument("--feedback", help="feedback_analysis.json (optional)")
    parser.add_argument("--output", "-o", default="quality_report.html")
    args = parser.parse_args()

    val_path = REPO_ROOT / args.validation
    if not val_path.exists():
        print(f"Validation report not found: {val_path}", file=sys.stderr)
        return 1

    with open(val_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    avg = data.get("avg_metrics", data.get("avg", {}))
    n = data.get("total_queries", 0)
    passed = data.get("passed", True)

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>RAG Quality Report</title></head>
<body>
<h1>RAG Quality Report</h1>
<p>Generated: {datetime.now().isoformat()}</p>
<h2>Summary</h2>
<ul>
<li>Total queries: {n}</li>
<li>Passed: {passed}</li>
<li>Faithfulness: {avg.get('faithfulness', 0):.3f}</li>
<li>Relevance: {avg.get('relevance', 0):.3f}</li>
<li>Coherence: {avg.get('coherence', 0):.3f}</li>
</ul>
</body>
</html>
"""

    out = Path(args.output)
    if not out.is_absolute():
        out = REPO_ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
