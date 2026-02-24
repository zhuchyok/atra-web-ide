"""
Дашборд для визуализации метрик фильтров
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.metrics.filter_metrics import FilterType, filter_metrics_collector
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class FilterMetricsDashboard:
    """Дашборд метрик фильтров"""

    def __init__(self, output_dir: str = "metrics_dashboard"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Создание поддиректорий
        (self.output_dir / "html").mkdir(exist_ok=True)
        (self.output_dir / "json").mkdir(exist_ok=True)
        (self.output_dir / "csv").mkdir(exist_ok=True)

    def generate_html_dashboard(self) -> str:
        """Генерация HTML дашборда"""
        try:
            # Получение данных
            report = filter_metrics_collector.get_efficiency_report()
            performance = filter_metrics_collector.get_performance_summary()

            # Создание HTML
            html_content = self._create_html_content(report, performance)

            # Сохранение файла
            html_file = self.output_dir / "html" / "dashboard.html"
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html_content)

            logger.info(f"HTML дашборд создан: {html_file}")
            return str(html_file)

        except Exception as e:
            logger.error(f"Ошибка при создании HTML дашборда: {e}")
            return ""

    def _create_html_content(self, report: Dict[str, Any], performance: Dict[str, Any]) -> str:
        """Создание HTML контента"""
        html = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ATRA Trading Bot - Метрики фильтров</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .metric-title {{
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .metric-label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .recommendations {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .recommendation {{
            margin-bottom: 10px;
            padding: 10px;
            background: white;
            border-radius: 5px;
            border-left: 4px solid #f39c12;
        }}
        .filter-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        .filter-table th, .filter-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        .filter-table th {{
            background-color: #f8f9fa;
            font-weight: bold;
        }}
        .success-rate {{
            color: #28a745;
            font-weight: bold;
        }}
        .rejection-rate {{
            color: #dc3545;
            font-weight: bold;
        }}
        .performance-good {{
            color: #28a745;
        }}
        .performance-warning {{
            color: #ffc107;
        }}
        .performance-bad {{
            color: #dc3545;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 ATRA Trading Bot - Метрики фильтров</h1>
            <p>Обновлено: {get_utc_now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>

        {self._create_overall_metrics_html(report)}

        {self._create_filter_breakdown_html(report)}

        {self._create_performance_charts_html(performance)}

        {self._create_recommendations_html(report)}

        {self._create_filter_table_html(report)}
    </div>

    <script>
        {self._create_chart_scripts(report, performance)}
    </script>
</body>
</html>
        """
        return html

    def _create_overall_metrics_html(self, report: Dict[str, Any]) -> str:
        """Создание HTML для общих метрик"""
        overall = report.get("overall", {})

        return f"""
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">📊 Общие сигналы</div>
                <div class="metric-value">{overall.get("total_signals", 0)}</div>
                <div class="metric-label">Всего обработано</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">✅ Успешные</div>
                <div class="metric-value">{overall.get("total_passed", 0)}</div>
                <div class="metric-label">Прошли фильтры</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">❌ Отклоненные</div>
                <div class="metric-value">{overall.get("total_rejected", 0)}</div>
                <div class="metric-label">Отклонены фильтрами</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">📈 Успешность</div>
                <div class="metric-value">{(overall.get("overall_success_rate", 0) * 100):.1f}%</div>
                <div class="metric-label">Общий показатель</div>
            </div>
        </div>
        """

    def _create_filter_breakdown_html(self, report: Dict[str, Any]) -> str:
        """Создание HTML для разбивки по фильтрам"""
        filters = report.get("filters", {})

        html = '<div class="chart-container"><h3>📊 Разбивка по фильтрам</h3><div class="metrics-grid">'

        for filter_name, filter_data in filters.items():
            metrics = filter_data.get("metrics", {})
            success_rate = metrics.get("success_rate", 0) * 100
            rejection_rate = metrics.get("rejection_rate", 0) * 100

            # Определение цвета на основе успешности
            success_class = "success-rate" if success_rate > 50 else "rejection-rate"

            html += f"""
            <div class="metric-card">
                <div class="metric-title">🔍 {filter_name.replace("_", " ").title()}</div>
                <div class="metric-value">{metrics.get("total_signals", 0)}</div>
                <div class="metric-label">Всего сигналов</div>
                <div class="{success_class}">Успешность: {success_rate:.1f}%</div>
                <div class="metric-label">Отклонения: {rejection_rate:.1f}%</div>
            </div>
            """

        html += "</div></div>"
        return html

    def _create_performance_charts_html(self, performance: Dict[str, Any]) -> str:
        """Создание HTML для графиков производительности"""
        return """
        <div class="chart-container">
            <h3>⚡ Производительность фильтров</h3>
            <canvas id="performanceChart" width="400" height="200"></canvas>
        </div>

        <div class="chart-container">
            <h3>📊 Распределение времени обработки</h3>
            <canvas id="timeDistributionChart" width="400" height="200"></canvas>
        </div>
        """

    def _create_recommendations_html(self, report: Dict[str, Any]) -> str:
        """Создание HTML для рекомендаций"""
        recommendations = report.get("recommendations", [])

        if not recommendations:
            return ""

        html = '<div class="recommendations"><h3>💡 Рекомендации по оптимизации</h3>'

        for i, rec in enumerate(recommendations, 1):
            html += f'<div class="recommendation">{i}. {rec}</div>'

        html += "</div>"
        return html

    def _create_filter_table_html(self, report: Dict[str, Any]) -> str:
        """Создание HTML таблицы фильтров"""
        filters = report.get("filters", {})

        html = """
        <div class="chart-container">
            <h3>📋 Детальная таблица фильтров</h3>
            <table class="filter-table">
                <thead>
                    <tr>
                        <th>Фильтр</th>
                        <th>Всего</th>
                        <th>Успешные</th>
                        <th>Отклоненные</th>
                        <th>Успешность</th>
                        <th>Время обработки</th>
                        <th>Топ причины отклонения</th>
                    </tr>
                </thead>
                <tbody>
        """

        for filter_name, filter_data in filters.items():
            metrics = filter_data.get("metrics", {})
            perf = filter_data.get("performance", {})
            top_reasons = filter_data.get("top_rejection_reasons", [])

            success_rate = metrics.get("success_rate", 0) * 100
            avg_time = perf.get("avg_processing_time", 0)

            # Определение класса производительности
            if avg_time < 0.01:
                perf_class = "performance-good"
            elif avg_time < 0.1:
                perf_class = "performance-warning"
            else:
                perf_class = "performance-bad"

            # Форматирование причин отклонения
            reasons_text = ", ".join([f"{reason} ({count})" for reason, count in top_reasons[:3]])

            html += f"""
                    <tr>
                        <td>{filter_name.replace("_", " ").title()}</td>
                        <td>{metrics.get("total_signals", 0)}</td>
                        <td>{metrics.get("passed_signals", 0)}</td>
                        <td>{metrics.get("rejected_signals", 0)}</td>
                        <td class="success-rate">{success_rate:.1f}%</td>
                        <td class="{perf_class}">{avg_time:.4f}s</td>
                        <td>{reasons_text}</td>
                    </tr>
            """

        html += """
                </tbody>
            </table>
        </div>
        """
        return html

    def _create_chart_scripts(self, report: Dict[str, Any], performance: Dict[str, Any]) -> str:
        """Создание JavaScript для графиков"""
        # Подготовка данных для графиков
        filter_names = []
        success_rates = []
        processing_times = []

        for filter_name, filter_data in report.get("filters", {}).items():
            filter_names.append(filter_name.replace("_", " ").title())
            metrics = filter_data.get("metrics", {})
            perf = filter_data.get("performance", {})

            success_rates.append(metrics.get("success_rate", 0) * 100)
            processing_times.append(perf.get("avg_processing_time", 0))

        return f"""
        // График производительности
        const performanceCtx = document.getElementById('performanceChart').getContext('2d');
        new Chart(performanceCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(filter_names)},
                datasets: [{{
                    label: 'Время обработки (сек)',
                    data: {json.dumps(processing_times)},
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: 'Время обработки (сек)'
                        }}
                    }}
                }}
            }}
        }});

        // График распределения времени
        const timeDistCtx = document.getElementById('timeDistributionChart').getContext('2d');
        new Chart(timeDistCtx, {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(filter_names)},
                datasets: [{{
                    data: {json.dumps(success_rates)},
                    backgroundColor: [
                        '#28a745', '#17a2b8', '#ffc107', '#dc3545', '#6f42c1',
                        '#e83e8c', '#20c997', '#fd7e14'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Успешность фильтров (%)'
                    }}
                }}
            }}
        }});
        """

    def export_metrics_to_json(self) -> str:
        """Экспорт метрик в JSON"""
        try:
            report = filter_metrics_collector.get_efficiency_report()
            performance = filter_metrics_collector.get_performance_summary()

            data = {
                "report": report,
                "performance": performance,
                "exported_at": get_utc_now().isoformat(),
            }

            now = get_utc_now()
            json_file = self.output_dir / "json" / f"metrics_{now.strftime('%Y%m%d_%H%M%S')}.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Метрики экспортированы в JSON: {json_file}")
            return str(json_file)

        except Exception as e:
            logger.error(f"Ошибка при экспорте метрик в JSON: {e}")
            return ""

    def export_metrics_to_csv(self) -> str:
        """Экспорт метрик в CSV"""
        try:
            # Создание DataFrame с метриками
            data = []

            for filter_type in FilterType:
                metrics = filter_metrics_collector.get_filter_metrics(filter_type)
                performance = filter_metrics_collector.get_filter_performance(filter_type)

                data.append(
                    {
                        "filter_type": filter_type.value,
                        "total_signals": metrics.total_signals,
                        "passed_signals": metrics.passed_signals,
                        "rejected_signals": metrics.rejected_signals,
                        "success_rate": metrics.success_rate,
                        "rejection_rate": metrics.rejection_rate,
                        "avg_processing_time": metrics.avg_processing_time,
                        "min_processing_time": performance.min_processing_time,
                        "max_processing_time": performance.max_processing_time,
                        "std_processing_time": np.std(list(performance.processing_times))
                        if performance.processing_times
                        else 0.0,
                        "last_updated": metrics.last_updated.isoformat(),
                    }
                )

            df = pd.DataFrame(data)

            now = get_utc_now()
            csv_file = self.output_dir / "csv" / f"metrics_{now.strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(csv_file, index=False, encoding="utf-8")

            logger.info(f"Метрики экспортированы в CSV: {csv_file}")
            return str(csv_file)

        except Exception as e:
            logger.error(f"Ошибка при экспорте метрик в CSV: {e}")
            return ""

    def generate_full_report(self) -> Dict[str, str]:
        """Генерация полного отчета"""
        try:
            results = {}

            # HTML дашборд
            html_file = self.generate_html_dashboard()
            if html_file:
                results["html_dashboard"] = html_file

            # JSON экспорт
            json_file = self.export_metrics_to_json()
            if json_file:
                results["json_export"] = json_file

            # CSV экспорт
            csv_file = self.export_metrics_to_csv()
            if csv_file:
                results["csv_export"] = csv_file

            logger.info(f"Полный отчет сгенерирован: {results}")
            return results

        except Exception as e:
            logger.error(f"Ошибка при генерации полного отчета: {e}")
            return {}


# Глобальный экземпляр дашборда
dashboard = FilterMetricsDashboard()


def generate_dashboard() -> Dict[str, str]:
    """Удобная функция для генерации дашборда"""
    return dashboard.generate_full_report()
