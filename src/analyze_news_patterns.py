import pandas as pd

def analyze_news_patterns(data_frame):
    # Расчет средней эффективности автоматизации
    avg_automation_efficiency = data_frame['automation_efficiency'].mean()
    
    # Суммарный риск безопасности
    total_incident_rate = data_frame['incident_rate'].sum()
    
    # Прогноз на 2026 год
    if avg_automation_efficiency < 0.85:
        return "Нужно улучшить архитектуру для автоматизации."
    elif total_incident_rate > 10:
        return "Присутствует критические проблемы безопасности."
    else:
        return "Модель готова к масштабированию и категоризации новостей."