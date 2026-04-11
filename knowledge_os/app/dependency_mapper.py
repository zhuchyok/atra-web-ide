import os
import ast
import logging
from typing import Dict, Set, List

logger = logging.getLogger(__name__)

class DependencyMapper:
    """
    Dependency Mapper (Singularity 24.0).
    Строит граф импортов проекта для реализации Dependency-Aware Regression Guard.
    """
    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.getcwd()
        self.import_graph: Dict[str, Set[str]] = {} # file -> files that import it
        self.reverse_graph: Dict[str, Set[str]] = {} # file -> files it imports

    def build_graph(self, target_dir: str = None):
        """Сканирует директорию и строит граф зависимостей."""
        target_dir = target_dir or self.project_root
        self.import_graph = {}
        self.reverse_graph = {}

        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.project_root)
                    self._process_file(file_path, rel_path)
        
        logger.info(f"📊 [DEPENDENCY MAPPER] Graph built: {len(self.reverse_graph)} modules indexed.")

    def _process_file(self, file_path: str, rel_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=file_path)
            
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)
            
            self.reverse_graph[rel_path] = imports
            for imp in imports:
                # Пытаемся сопоставить имя импорта с путем к файлу
                imp_path = self._resolve_import(imp, rel_path)
                if imp_path:
                    if imp_path not in self.import_graph:
                        self.import_graph[imp_path] = set()
                    self.import_graph[imp_path].add(rel_path)

        except Exception as e:
            logger.debug(f"Failed to process {rel_path}: {e}")

    def _resolve_import(self, import_name: str, current_file: str) -> Optional[str]:
        """Преобразует имя импорта в относительный путь к файлу."""
        # Упрощенная логика резолвинга
        parts = import_name.split('.')
        
        # Проверяем как абсолютный путь от корня проекта
        potential_path = os.path.join(*parts) + ".py"
        if os.path.exists(os.path.join(self.project_root, potential_path)):
            return potential_path
        
        # Проверяем как пакет (__init__.py)
        potential_pkg = os.path.join(*parts, "__init__.py")
        if os.path.exists(os.path.join(self.project_root, potential_pkg)):
            return potential_pkg

        return None

    def get_affected_files(self, file_path: str) -> Set[str]:
        """Возвращает список файлов, которые импортируют данный файл."""
        rel_path = os.path.relpath(file_path, self.project_root)
        affected = self.import_graph.get(rel_path, set())
        
        # Также проверяем если это пакет
        if rel_path.endswith("__init__.py"):
            pkg_path = os.path.dirname(rel_path).replace(os.sep, '.')
            affected.update(self.import_graph.get(pkg_path, set()))
        
        return affected

_mapper = None

def get_dependency_mapper(project_root: str = None) -> DependencyMapper:
    global _mapper
    if _mapper is None:
        _mapper = DependencyMapper(project_root)
        _mapper.build_graph()
    return _mapper
