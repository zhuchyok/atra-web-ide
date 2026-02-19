import pytest
import os
import ast
from knowledge_os.app.graphrag.code_analyzer import CodeAnalyzer, CodeEntity, CodeLink

def test_code_analyzer_basic():
    """Проверка базового анализа Python кода."""
    code = """
class Base:
    pass

class Derived(Base):
    def method(self):
        print("hello")
        self.other_method()

    def other_method(self):
        return 42

def standalone_func():
    d = Derived()
    d.method()
"""
    # Создаем временный файл для теста
    test_file = "test_analyzer_tmp.py"
    with open(test_file, "w") as f:
        f.write(code)
    
    try:
        analyzer = CodeAnalyzer(base_path=os.getcwd())
        analyzer.analyze_file(test_file)
        
        # Проверка сущностей
        entity_names = [e.name for e in analyzer.entities]
        assert "Base" in entity_names
        assert "Derived" in entity_names
        assert "Derived.method" in entity_names
        assert "Derived.other_method" in entity_names
        assert "standalone_func" in entity_names
        
        # Проверка типов
        classes = [e for e in analyzer.entities if e.type == 'class']
        functions = [e for e in analyzer.entities if e.type == 'function']
        assert len(classes) == 2
        assert len(functions) == 3
        
        # Проверка связей
        # 1. Наследование
        inheritance = [l for l in analyzer.links if l.link_type == 'inherits']
        assert len(inheritance) == 1
        assert inheritance[0].source_name == "Derived"
        assert inheritance[0].target_name == "Base"
        
        # 2. Вызовы
        calls = [l for l in analyzer.links if l.link_type == 'calls']
        # standalone_func вызывает Derived() и d.method()
        # Derived.method вызывает print() и self.other_method()
        
        call_targets = [l.target_name for l in calls]
        assert "print" in call_targets
        assert "self.other_method" in call_targets
        assert "Derived" in call_targets
        assert "d.method" in call_targets
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def test_code_analyzer_imports():
    """Проверка извлечения импортов."""
    code = """
import os
from datetime import datetime
import asyncpg as pg
"""
    test_file = "test_imports_tmp.py"
    with open(test_file, "w") as f:
        f.write(code)
    
    try:
        analyzer = CodeAnalyzer(base_path=os.getcwd())
        analyzer.analyze_file(test_file)
        
        depends = [l for l in analyzer.links if l.link_type == 'depends_on']
        targets = [l.target_name for l in depends]
        
        assert "os" in targets
        assert "datetime.datetime" in targets
        assert "asyncpg" in targets
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
