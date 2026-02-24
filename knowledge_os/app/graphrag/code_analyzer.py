import ast
import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeEntity:
    name: str
    type: str  # 'class', 'function', 'module'
    file_path: str
    line_start: int
    line_end: int
    content: str
    metadata: Dict[str, Any]


@dataclass
class CodeLink:
    source_name: str
    target_name: str
    link_type: str  # 'calls', 'inherits', 'depends_on'
    metadata: Dict[str, Any]


class CodeAnalyzer:
    """
    Анализирует Python код с помощью AST для извлечения сущностей и связей.
    Используется для построения GraphRAG кодовой базы.
    """

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.entities: List[CodeEntity] = []
        self.links: List[CodeLink] = []

    def analyze_file(self, file_path: str):
        """Парсит один файл и извлекает сущности и связи."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            relative_path = os.path.relpath(file_path, self.base_path)

            # 1. Извлечение сущностей (Классы и Функции)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entity = CodeEntity(
                        name=node.name,
                        type="class",
                        file_path=relative_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        content=ast.get_source_segment(content, node) or "",
                        metadata={"bases": [ast.unparse(b) for b in node.bases]},
                    )
                    self.entities.append(entity)

                    # Связи наследования
                    for base in node.bases:
                        self.links.append(
                            CodeLink(
                                source_name=node.name,
                                target_name=ast.unparse(base),
                                link_type="inherits",
                                metadata={"file": relative_path},
                            )
                        )

                elif isinstance(node, ast.FunctionDef):
                    # Проверяем, не является ли функция методом класса
                    parent = self._get_parent_class(node, tree)
                    full_name = f"{parent.name}.{node.name}" if parent else node.name

                    entity = CodeEntity(
                        name=full_name,
                        type="function",
                        file_path=relative_path,
                        line_start=node.lineno,
                        line_end=getattr(node, "end_lineno", node.lineno),
                        content=ast.get_source_segment(content, node) or "",
                        metadata={"is_method": parent is not None},
                    )
                    self.entities.append(entity)

                    # Извлечение вызовов функций внутри этой функции
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Call):
                            try:
                                call_name = ast.unparse(subnode.func)
                                self.links.append(
                                    CodeLink(
                                        source_name=full_name,
                                        target_name=call_name,
                                        link_type="calls",
                                        metadata={"file": relative_path, "line": subnode.lineno},
                                    )
                                )
                            except:
                                pass

            # 2. Извлечение импортов (depends_on)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.links.append(
                                CodeLink(
                                    source_name=relative_path,
                                    target_name=alias.name,
                                    link_type="depends_on",
                                    metadata={"type": "import"},
                                )
                            )
                    else:
                        module = node.module or ""
                        for alias in node.names:
                            self.links.append(
                                CodeLink(
                                    source_name=relative_path,
                                    target_name=f"{module}.{alias.name}",
                                    link_type="depends_on",
                                    metadata={"type": "import_from"},
                                )
                            )

        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}")

    def _get_parent_class(self, node, tree) -> Optional[ast.ClassDef]:
        """Находит родительский класс для функции, если он есть."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                if node in parent.body:
                    return parent
        return None


async def sync_code_to_graph(directory: str = "knowledge_os/app/"):
    """
    Сканирует директорию и синхронизирует структуру кода с GraphRAG (knowledge_nodes/links).
    """
    analyzer = CodeAnalyzer(base_path=os.getcwd())

    # Рекурсивный поиск всех .py файлов
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                analyzer.analyze_file(os.path.join(root, file))

    if not analyzer.entities:
        logger.warning("No code entities found to sync.")
        return

    # Подключение к БД
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    try:
        import asyncpg
        from app.semantic_cache import get_embedding

        conn = await asyncpg.connect(db_url)

        # 1. Upsert Entities
        entity_map = {}  # name -> uuid
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Codebase' LIMIT 1")
        if not domain_id:
            domain_id = await conn.fetchval(
                "INSERT INTO domains (name) VALUES ('Codebase') RETURNING id"
            )

        logger.info(f"Syncing {len(analyzer.entities)} entities to GraphRAG...")

        for entity in analyzer.entities:
            # Генерируем эмбеддинг для контента (кода)
            embedding = await get_embedding(entity.content[:8000])

            metadata = entity.metadata
            metadata.update(
                {
                    "type": "code_entity",
                    "code_type": entity.type,
                    "file_path": entity.file_path,
                    "line_range": [entity.line_start, entity.line_end],
                }
            )

            node_id = await conn.fetchval(
                """
                INSERT INTO knowledge_nodes (domain_id, content, embedding, metadata, confidence_score, is_verified, source_ref)
                VALUES ($1, $2, $3::vector, $4, 1.0, true, $5)
                ON CONFLICT (content) DO UPDATE
                SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata, updated_at = NOW()
                RETURNING id
            """,
                domain_id,
                entity.content,
                str(embedding) if embedding else None,
                json.dumps(metadata),
                f"code:{entity.file_path}",
            )

            if not node_id:
                # Если конфликт не сработал по сложной логике, ищем существующий
                node_id = await conn.fetchval(
                    "SELECT id FROM knowledge_nodes WHERE content = $1 AND domain_id = $2",
                    entity.content,
                    domain_id,
                )

            entity_map[entity.name] = node_id

        # 2. Upsert Links
        logger.info(f"Syncing {len(analyzer.links)} links to GraphRAG...")
        for link in analyzer.links:
            source_id = entity_map.get(link.source_name)
            target_id = entity_map.get(link.target_name)

            # Если цель - это внешняя библиотека или мы её еще не пропарсили,
            # создаем 'placeholder' узел или пропускаем.
            if not source_id:
                # Может быть это модуль (file_path)
                source_id = await conn.fetchval(
                    "SELECT id FROM knowledge_nodes WHERE metadata->>'file_path' = $1",
                    link.source_name,
                )

            if not target_id:
                # Ищем по имени в той же кодовой базе
                target_id = await conn.fetchval(
                    "SELECT id FROM knowledge_nodes WHERE content LIKE $1 AND domain_id = $2",
                    f"%{link.target_name}%",
                    domain_id,
                )

            if source_id and target_id:
                await conn.execute(
                    """
                    INSERT INTO knowledge_links (source_node_id, target_node_id, link_type, strength, metadata)
                    VALUES ($1, $2, $3, 1.0, $4)
                    ON CONFLICT (source_node_id, target_node_id, link_type) DO NOTHING
                """,
                    source_id,
                    target_id,
                    link.link_type,
                    json.dumps(link.metadata),
                )

        await conn.close()
        logger.info("✅ Code Call Graph successfully synced to GraphRAG.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    asyncio.run(sync_code_to_graph())
