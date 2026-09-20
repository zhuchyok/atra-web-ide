def analyze_data(data):
    # Предполагается, что data - это JSON с данными
    # Анализ данных для выявления паттернов, которые повлияют на будущее компании ATRA до 2026 года
    patterns = {}
    for record in data:
        record_id = record['id']
        for key, value in record.items():
            if key == 'market_trends':
                if 'market_trends' not in patterns:
                    patterns['market_trends'] = []
                patterns['market_trends'].append(value)
            elif key == 'profit_margins':
                if 'profit_margins' not in patterns:
                    patterns['profit_margins'] = []
                patterns['profit_margins'].append(value)
            # Дополнительные паттерны могут быть добавлены здесь
    return patterns

# Применение функции анализа
patterns = analyze_data(data)

# Вывод паттернов
print(patterns)