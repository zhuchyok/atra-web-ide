import os

# Путь к файлу для проверки
file_path = '/app/knowledge_os/app/cube_sandbox_manager.py'

# Проверка существования файла
if not os.path.exists(file_path):
    print(f'Файл {file_path} не найден.')
else:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Поиск pip install в рантайме
    issues = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        if 'pip install' in line:
            issues.append(f'Строка {i}: {line.strip()}')
    
    if issues:
        print('НАЙДЕНЫ ПРОБЛЕМЫ:')
        for issue in issues:
            print(f'  {issue}')
        print('\nВывод: ПРОБЛЕМА')
    else:
        print('Проблем не найдено.')
        print('Вывод: ОК')
