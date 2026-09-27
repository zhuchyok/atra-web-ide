import pandas as pd
import numpy as np

def analyze_knowledge_os(data_source):
    """
    Анализирует данные Knowledge OS для выявления паттернов роста и рисков.
    :param data_source: DataFrame с данными (TimeSeries, KPI, Market Sentiment).
    :return: dict с выводами по эффективности и устойчивости.
    """
    # Проверка на пропуски и бассейна очистки
    data = data_source.dropna()

    # Расчет скользящего среднего для трендов
    data['trend_growth'] = data['revenue'].rolling(window=3).mean()

    # Выявление паттернов риска (симуляция проверки 'голоса опыта')
    risk_alert = data[data['volatility'] > npsoft(data['volatility'] * 2)]

    insights = {
        'trend_growth': data['trend_growth'],
        'risk_alert': risk_alert
    }

    return insights

# Пример использования:
# предполагая, что 'knowledge_data' - это DataFrame с нужными метриками
# insights = analyze_knowledge_os(knowledge_data)
# далее можно использовать данные в выводах и визуализациях