#!/bin/bash
# Скрипт для проверки антипаттернов в CI/CD

set -e

echo "🔍 Проверка антипаттернов в коде..."

python3 << 'EOF'
from src.core.anti_pattern_detector import get_anti_pattern_detector
import os
import sys

detector = get_anti_pattern_detector()
errors = 0
warnings = 0

for root, dirs, files in os.walk('src'):
    # Пропускаем __pycache__
    dirs[:] = [d for d in dirs if d != '__pycache__']
    
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                patterns = detector.detect_in_code(code, filepath)
                
                for p in patterns:
                    if p.severity == 'error':
                        print(f'❌ {filepath}:{p.line_number}: {p.message}')
                        errors += 1
                    elif p.severity == 'warning':
                        print(f'⚠️  {filepath}:{p.line_number}: {p.message}')
                        warnings += 1
            except Exception as e:
                print(f'⚠️  Ошибка при проверке {filepath}: {e}')

if errors > 0:
    print(f'\n❌ Обнаружено {errors} критичных антипаттернов')
    sys.exit(1)
elif warnings > 0:
    print(f'\n⚠️  Обнаружено {warnings} предупреждений')
    print('✅ Критичных ошибок не обнаружено')
    sys.exit(0)
else:
    print('\n✅ Антипаттерны не обнаружены')
    sys.exit(0)
EOF

