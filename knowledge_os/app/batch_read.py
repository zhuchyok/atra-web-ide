"""
Batch Read — параллельное чтение множества файлов для быстрого сканирования проекта.
Используется Victoria Enhanced для задач типа «найди все упоминания X в проекте».
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BatchReadError(Exception):
    """Ошибка при batch_read операции."""

    pass


async def batch_read_files(
    file_paths: List[str],
    workspace_path: str,
    max_concurrent: int = 10,
    max_file_size_mb: int = 1,
) -> List[Dict[str, Any]]:
    """
    Параллельное чтение множества файлов через Rust Gateway [SINGULARITY 21.23].
    """
    try:
        import httpx

        # Rust Gateway работает на порту 8081
        rust_url = "http://localhost:8081/api/files/batch_read"
        payload = {"file_paths": file_paths, "max_concurrent": max_concurrent}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(rust_url, json=payload)
            if response.status_code == 200:
                logger.info(f"🚀 [RUST BATCH_READ] Successfully read {len(file_paths)} files.")
                return response.json().get("results", [])
    except Exception as e:
        logger.warning(f"⚠️ Rust Batch Read failed, falling back to Python: {e}")

    # Fallback на Python реализацию (старый код)
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    # ... (остальной код остается как fallback)

    async def read_single_file(file_path: str) -> Dict[str, Any]:
        """Читает один файл с ограничением по размеру."""
        async with semaphore:
            try:
                # Нормализуем путь
                if not file_path.startswith("/"):
                    full_path = Path(workspace_path) / file_path
                else:
                    full_path = Path(file_path)

                # Проверка существования
                if not full_path.exists():
                    return {
                        "path": file_path,
                        "content": None,
                        "status": "error",
                        "error": "File not found",
                    }

                # Проверка размера
                file_size_mb = full_path.stat().st_size / (1024 * 1024)
                if file_size_mb > max_file_size_mb:
                    return {
                        "path": file_path,
                        "content": None,
                        "status": "error",
                        "error": f"File too large ({file_size_mb:.2f} MB > {max_file_size_mb} MB)",
                    }

                # Чтение
                content = full_path.read_text(encoding="utf-8", errors="ignore")

                return {
                    "path": file_path,
                    "content": content,
                    "status": "success",
                    "size_kb": round(len(content) / 1024, 2),
                    "lines": len(content.split("\n")),
                }

            except UnicodeDecodeError:
                return {
                    "path": file_path,
                    "content": None,
                    "status": "error",
                    "error": "Binary file or encoding error",
                }
            except Exception as e:
                logger.exception(f"Error reading {file_path}")
                return {"path": file_path, "content": None, "status": "error", "error": str(e)}

    # Запускаем чтение всех файлов параллельно
    tasks = [read_single_file(path) for path in file_paths]
    results = await asyncio.gather(*tasks)

    # Статистика
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count
    total_size_kb = sum(r.get("size_kb", 0) for r in results if r["status"] == "success")

    logger.info(
        f"[BATCH_READ] Прочитано {success_count}/{len(file_paths)} файлов "
        f"({total_size_kb:.2f} KB), ошибок: {error_count}"
    )

    return results


async def batch_grep_files(
    pattern: str,
    file_paths: List[str],
    workspace_path: str,
    case_sensitive: bool = False,
    max_concurrent: int = 10,
) -> List[Dict[str, Any]]:
    """
    Параллельный поиск паттерна через Rust Gateway [SINGULARITY 21.23].
    """
    try:
        import httpx

        rust_url = "http://localhost:8081/api/files/batch_grep"
        payload = {"pattern": pattern, "file_paths": file_paths, "case_sensitive": case_sensitive}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(rust_url, json=payload)
            if response.status_code == 200:
                logger.info(
                    f"🚀 [RUST BATCH_GREP] Successfully grepped {len(file_paths)} patterns."
                )
                return response.json().get("results", [])
    except Exception as e:
        logger.warning(f"⚠️ Rust Batch Grep failed, falling back to Python: {e}")

    import re

    results = []
    semaphore = asyncio.Semaphore(max_concurrent)

    # Компилируем regex один раз
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        raise BatchReadError(f"Invalid regex pattern: {e}")

    async def grep_single_file(file_path: str) -> Dict[str, Any]:
        """Ищет паттерн в одном файле."""
        async with semaphore:
            try:
                # Нормализуем путь
                if not file_path.startswith("/"):
                    full_path = Path(workspace_path) / file_path
                else:
                    full_path = Path(file_path)

                if not full_path.exists():
                    return {
                        "path": file_path,
                        "matches": [],
                        "match_count": 0,
                        "status": "error",
                        "error": "File not found",
                    }

                # Чтение и поиск
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")

                matches = []
                for line_num, line_content in enumerate(lines, 1):
                    if regex.search(line_content):
                        # Находим все совпадения в строке
                        for match in regex.finditer(line_content):
                            matches.append(
                                {
                                    "line": line_num,
                                    "content": line_content.strip(),
                                    "match": match.group(0),
                                    "start": match.start(),
                                    "end": match.end(),
                                }
                            )

                return {
                    "path": file_path,
                    "matches": matches[:50],  # Лимит 50 совпадений на файл
                    "match_count": len(matches),
                    "status": "success",
                }

            except Exception as e:
                logger.exception(f"Error grepping {file_path}")
                return {
                    "path": file_path,
                    "matches": [],
                    "match_count": 0,
                    "status": "error",
                    "error": str(e),
                }

    # Запускаем grep всех файлов параллельно
    tasks = [grep_single_file(path) for path in file_paths]
    results = await asyncio.gather(*tasks)

    # Статистика
    total_matches = sum(r["match_count"] for r in results)
    files_with_matches = sum(1 for r in results if r["match_count"] > 0)

    logger.info(
        f"[BATCH_GREP] Найдено {total_matches} совпадений в {files_with_matches}/{len(file_paths)} файлах"
    )

    return results
