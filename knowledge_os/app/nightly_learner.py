import os

file_path = '/app/knowledge_os/app/nightly_learner.py'

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверка на subprocess pip
    has_subprocess_pip = 'subprocess' in content and ('pip install' in content or 'pip install ' in content)
    
    # Проверка на os.system pip
    has_os_system_pip = 'os.system' in content and ('pip install' in content or 'pip install ' in content)

    if has_subprocess_pip:
        print("ПРОБЛЕМА: Обнаружен subprocess pip install")
        # Вывод строки с кодом
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'subprocess' in line and 'pip install' in line:
                print(f"  Строка {i+1}: {line.strip()}")
    elif has_os_system_pip:
        print("ПРОБЛЕМА: Обнаружен os.system pip install")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'os.system' in line and 'pip install' in line:
                print(f"  Строка {i+1}: {line.strip()}")
    else:
        print("ОК: Уязвимости pip install в рантайме не обнаружены")

except FileNotFoundError:
    print("Файл не найден")
    except Exception as e:
    print(f"Ошибка: {e}")
