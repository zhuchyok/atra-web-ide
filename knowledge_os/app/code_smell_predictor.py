"""
Code Smell Predictor: Предсказание будущих багов в коде

Функционал:
- Анализ кода на анти-паттерны (cyclomatic complexity, null pointers, race conditions)
- Предсказание вероятности бага в следующие 30 дней
- Интеграция с code_auditor.py для создания задач на исправление
"""

import asyncio
import os
import json
import re
import logging
import ast
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Import database connection from evaluator
from evaluator import get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Пороги для предсказания багов
MIN_BUG_PROBABILITY = 0.5  # Минимальная вероятность бага для создания задачи
HIGH_BUG_PROBABILITY = 0.7  # Высокая вероятность бага

# Типы багов
BUG_TYPES = ["null_pointer", "race_condition", "memory_leak", "type_error", "logic_error"]


@dataclass
class BugPrediction:
    """Предсказание бага в коде"""
    file_path: str
    code_snippet: str
    bug_probability: float  # 0.0-1.0
    likely_issues: List[str]  # [null_pointer, race_condition, ...]
    risk_files: List[str]  # Список файлов с высоким риском
    predicted_issues: Dict[str, any]  # {bug_probability, likely_issues, risk_files}


class CodeSmellPredictor:
    """Класс для предсказания багов в коде"""
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
    
    def analyze_code_complexity(self, code: str) -> Dict[str, float]:
        """
        Анализирует сложность кода (cyclomatic complexity).
        
        Args:
            code: Исходный код Python
        
        Returns:
            Словарь с метриками сложности
        """
        try:
            tree = ast.parse(code)
            complexity = 1  # Базовая сложность = 1
            
            # Подсчитываем условные конструкции
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
                elif isinstance(node, ast.Compare):
                    complexity += len(node.ops) - 1
            
            # Количество функций и классов
            functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            
            # Средняя длина функции (строк)
            avg_function_length = 0.0
            if functions:
                total_lines = sum(len(ast.unparse(func).split('\n')) for func in functions)
                avg_function_length = total_lines / len(functions)
            
            return {
                'cyclomatic_complexity': float(complexity),
                'function_count': float(len(functions)),
                'class_count': float(len(classes)),
                'avg_function_length': avg_function_length
            }
        except Exception as e:
            logger.error(f"Error analyzing code complexity: {e}")
            return {
                'cyclomatic_complexity': 0.0,
                'function_count': 0.0,
                'class_count': 0.0,
                'avg_function_length': 0.0
            }
    
    def detect_anti_patterns(self, code: str) -> List[str]:
        """
        Детектирует анти-паттерны в коде.
        
        Args:
            code: Исходный код Python
        
        Returns:
            Список найденных анти-паттернов
        """
        anti_patterns = []
        
        # Проверяем на null pointer patterns (None без проверки)
        if re.search(r'[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\s*=', code):
            # Потенциальная опасность: обращение к атрибуту без проверки
            if not re.search(r'if\s+[a-zA-Z_][a-zA-Z0-9_]*\s+is\s+not\s+None', code):
                anti_patterns.append('potential_null_pointer')
        
        # Проверяем на race conditions (глобальные переменные без блокировки)
        if re.search(r'global\s+[a-zA-Z_][a-zA-Z0-9_]+', code):
            anti_patterns.append('potential_race_condition')
        
        # Проверяем на memory leaks (открытые файлы без закрытия)
        if re.search(r'open\(', code) and not re.search(r'with\s+open\(', code):
            anti_patterns.append('potential_memory_leak')
        
        # Проверяем на type errors (отсутствие type hints в сложных функциях)
        if re.search(r'def\s+[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\):', code):
            # Если функция имеет >3 параметра без type hints
            func_defs = re.findall(r'def\s+[a-zA-Z_][a-zA-Z0-9_]*\(([^)]*)\):', code)
            for params in func_defs:
                if params.count(',') > 2 and ':' not in params:
                    anti_patterns.append('potential_type_error')
                    break
        
        # Проверяем на logic errors (магические числа)
        magic_numbers = re.findall(r'\b\d{3,}\b', code)  # Числа >= 1000
        if len(magic_numbers) > 5:
            anti_patterns.append('potential_logic_error')
        
        return anti_patterns
    
    def calculate_bug_probability(self, code: str, file_path: str, history: Optional[Dict] = None) -> float:
        """
        Вычисляет вероятность бага в следующие 30 дней.
        
        Args:
            code: Исходный код Python
            file_path: Путь к файлу
            history: История изменений файла (опционально)
        
        Returns:
            Вероятность бага (0.0-1.0)
        """
        # Анализируем сложность кода
        complexity_metrics = self.analyze_code_complexity(code)
        
        # Детектируем анти-паттерны
        anti_patterns = self.detect_anti_patterns(code)
        
        # Базовая вероятность = 0.0
        bug_probability = 0.0
        
        # Увеличиваем вероятность на основе сложности
        if complexity_metrics['cyclomatic_complexity'] > 20:
            bug_probability += 0.3
        elif complexity_metrics['cyclomatic_complexity'] > 10:
            bug_probability += 0.2
        elif complexity_metrics['cyclomatic_complexity'] > 5:
            bug_probability += 0.1
        
        # Увеличиваем вероятность на основе анти-паттернов
        bug_probability += len(anti_patterns) * 0.15
        
        # Увеличиваем вероятность на основе истории (если доступна)
        if history:
            if history.get('bug_count', 0) > 0:
                bug_probability += 0.2
            if history.get('recent_changes', 0) > 10:
                bug_probability += 0.1
        
        # Нормализуем вероятность (0.0-1.0)
        bug_probability = min(bug_probability, 1.0)
        
        return bug_probability
    
    def predict_bugs(self, file_path: str, code: str, history: Optional[Dict] = None) -> BugPrediction:
        """
        Предсказывает баги в коде.
        
        Args:
            file_path: Путь к файлу
            code: Исходный код Python
            history: История изменений файла (опционально)
        
        Returns:
            BugPrediction с предсказанием багов
        """
        # Вычисляем вероятность бага
        bug_probability = self.calculate_bug_probability(code, file_path, history)
        
        # Детектируем анти-паттерны
        anti_patterns = self.detect_anti_patterns(code)
        
        # Маппинг анти-паттернов в типы багов
        likely_issues = []
        for pattern in anti_patterns:
            if 'null_pointer' in pattern:
                likely_issues.append('null_pointer')
            elif 'race_condition' in pattern:
                likely_issues.append('race_condition')
            elif 'memory_leak' in pattern:
                likely_issues.append('memory_leak')
            elif 'type_error' in pattern:
                likely_issues.append('type_error')
            elif 'logic_error' in pattern:
                likely_issues.append('logic_error')
        
        # Если вероятных проблем нет, но вероятность бага высока
        if not likely_issues and bug_probability >= MIN_BUG_PROBABILITY:
            likely_issues.append('general_bug_risk')
        
        # Формируем предсказание
        predicted_issues = {
            'bug_probability': bug_probability,
            'likely_issues': likely_issues,
            'risk_files': [file_path] if bug_probability >= HIGH_BUG_PROBABILITY else []
        }
        
        return BugPrediction(
            file_path=file_path,
            code_snippet=code[:500],  # Первые 500 символов для примера
            bug_probability=bug_probability,
            likely_issues=likely_issues,
            risk_files=predicted_issues['risk_files'],
            predicted_issues=predicted_issues
        )
    
    async def save_prediction(self, prediction: BugPrediction) -> Optional[str]:
        """
        Сохраняет предсказание бага в БД.
        
        Args:
            prediction: Предсказание бага
        
        Returns:
            ID созданной записи или None
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            try:
                prediction_id = await conn.fetchval("""
                    INSERT INTO code_smell_predictions (
                        file_path,
                        code_snippet,
                        predicted_issues,
                        actual_bugs,
                        precision_score,
                        recall_score,
                        created_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    RETURNING id
                """,
                prediction.file_path,
                prediction.code_snippet,
                json.dumps(prediction.predicted_issues),
                0,  # actual_bugs будет обновлен позже (через 30 дней)
                None,  # precision_score будет вычислен после проверки
                None  # recall_score будет вычислен после проверки
                )
                
                logger.debug(f"✅ Saved bug prediction: {prediction.file_path} (probability: {prediction.bug_probability:.2f})")
                return str(prediction_id) if prediction_id else None
            except Exception as e:
                logger.error(f"❌ Error saving bug prediction: {e}")
                return None
    
    async def get_file_history(self, file_path: str) -> Optional[Dict]:
        """
        Получает историю изменений файла из БД (если доступна).
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            Словарь с историей или None
        """
        # В будущем здесь можно получить историю из git или БД
        # Пока возвращаем None
        return None


if __name__ == "__main__":
    # Тестирование
    test_code = """
def process_data(data):
    if data is None:
        return None
    result = data.process()
    return result.value

def complex_function(a, b, c, d, e):
    if a > b:
        if c > d:
            if e > 1000:
                return a + b + c + d + e
    return 0
"""
    
    predictor = CodeSmellPredictor()
    prediction = predictor.predict_bugs("test.py", test_code)
    
    print(f"File: {prediction.file_path}")
    print(f"Bug Probability: {prediction.bug_probability:.2f}")
    print(f"Likely Issues: {prediction.likely_issues}")
    print(f"Risk Files: {prediction.risk_files}")

