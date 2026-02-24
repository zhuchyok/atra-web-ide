#!/usr/bin/env python3
"""
CI/CD Task Caching: Content-Addressed Hashing & Change Detection

Based on Turbo audit (8.5/10):
- Content-addressed task hashing
- Git-aware change detection
- Affected package/task identification
"""
import hashlib
import json
import glob
import subprocess
import sys
import os
from pathlib import Path
from typing import List, Dict, Set

# Task definitions (content-addressed inputs/outputs)
TASKS = {
    "rust_core:build": {
        "inputs": [
            "rust_core/**/*.rs",
            "rust_core/**/Cargo.toml",
            "Cargo.lock",
            "Cargo.toml"
        ],
        "outputs": ["rust_core/target/release/"],
        "cache": True
    },
    "rust_core:test": {
        "inputs": [
            "rust_core/**/*.rs",
            "rust_core/**/Cargo.toml",
            "Cargo.lock"
        ],
        "outputs": [],
        "cache": True,
        "depends_on": ["rust_core:build"]
    },
    "knowledge_os:lint": {
        "inputs": [
            "knowledge_os/**/*.py",
            "knowledge_os/pyproject.toml",
            "knowledge_os/.ruff.toml"
        ],
        "outputs": [],
        "cache": True
    },
    "knowledge_os:test": {
        "inputs": [
            "knowledge_os/**/*.py",
            "knowledge_os/requirements.txt",
            "knowledge_os/pyproject.toml"
        ],
        "outputs": [],
        "cache": True,
        "depends_on": ["knowledge_os:lint"]
    },
    "frontend:build": {
        "inputs": [
            "frontend/src/**",
            "frontend/package.json",
            "frontend/package-lock.json",
            "frontend/vite.config.js"
        ],
        "outputs": ["frontend/dist/"],
        "cache": True
    },
    "frontend:test": {
        "inputs": [
            "frontend/src/**",
            "frontend/tests/**",
            "frontend/package.json"
        ],
        "outputs": [],
        "cache": True
    }
}

def hash_files(patterns: List[str], base_dir: str = ".") -> str:
    """
    Content-addressed hash of files matching patterns.

    Based on Turbo's task hashing (xxHash64 for speed, but using SHA256 for simplicity).

    Args:
        patterns: List of glob patterns (e.g., ["**/*.rs", "Cargo.toml"])
        base_dir: Base directory for glob patterns

    Returns:
        16-character hex hash (truncated SHA256)
    """
    hasher = hashlib.sha256()
    files = []

    # Collect all files matching patterns
    original_dir = os.getcwd()
    try:
        os.chdir(base_dir)

        for pattern in patterns:
            matched = glob.glob(pattern, recursive=True)
            files.extend(matched)

        # Deduplicate and sort for determinism
        files = sorted(set(files))

        # Hash each file's content
        for file_path in files:
            if not os.path.isfile(file_path):
                continue

            try:
                with open(file_path, 'rb') as f:
                    hasher.update(file_path.encode('utf-8'))  # Include path in hash
                    hasher.update(f.read())
            except (IOError, OSError):
                # Skip unreadable files
                pass

    finally:
        os.chdir(original_dir)

    # Return first 16 chars (like Turbo's short hashes)
    return hasher.hexdigest()[:16]


def detect_changed_files(base_ref: str = "main") -> List[str]:
    """
    Get list of changed files using git diff.

    Args:
        base_ref: Base branch/ref to compare against (default: "main")

    Returns:
        List of changed file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", f"{base_ref}...HEAD", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )

        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter empty strings

    except subprocess.CalledProcessError:
        # Fallback: compare with HEAD if base_ref doesn't exist
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD", "--name-only"],
                capture_output=True,
                text=True,
                check=True
            )
            files = result.stdout.strip().split("\n")
            return [f for f in files if f]
        except:
            return []


def map_files_to_packages(files: List[str]) -> Set[str]:
    """
    Map changed files to affected packages.

    Args:
        files: List of file paths

    Returns:
        Set of package names (e.g., {"rust_core", "knowledge_os"})
    """
    packages = set()

    for file in files:
        if file.startswith("rust_core/"):
            packages.add("rust_core")
        elif file.startswith("knowledge_os/"):
            packages.add("knowledge_os")
        elif file.startswith("frontend/"):
            packages.add("frontend")
        elif file.startswith("backend/"):
            packages.add("backend")

        # Lockfiles affect all related packages
        if file in ["Cargo.lock", "Cargo.toml"]:
            packages.add("rust_core")
        elif file in ["frontend/package-lock.json", "frontend/package.json"]:
            packages.add("frontend")
        elif file in ["knowledge_os/requirements.txt", "knowledge_os/pyproject.toml"]:
            packages.add("knowledge_os")

    return packages


def get_affected_tasks(changed_packages: Set[str]) -> List[str]:
    """
    Get list of tasks affected by changed packages.

    Args:
        changed_packages: Set of package names

    Returns:
        List of task IDs that need to run
    """
    affected = []

    for task_id, task_config in TASKS.items():
        package = task_id.split(":")[0]

        if package in changed_packages:
            affected.append(task_id)

            # Also include dependent tasks
            # TODO: Implement full dependency graph traversal

    return affected


def hash_task(task_id: str) -> Dict[str, str]:
    """
    Compute content-addressed hash for a task.

    Args:
        task_id: Task identifier (e.g., "rust_core:build")

    Returns:
        Dict with task_id and hash
    """
    task = TASKS.get(task_id)

    if not task:
        return {"task_id": task_id, "hash": "unknown", "error": "Task not found"}

    try:
        hash_value = hash_files(task["inputs"])
        return {
            "task_id": task_id,
            "hash": hash_value,
            "inputs": task["inputs"],
            "cache": task.get("cache", False)
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "hash": "error",
            "error": str(e)
        }


def main():
    """Main CLI interface"""
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "hash":
            # Hash specific task
            if len(sys.argv) > 2:
                task_id = sys.argv[2]
                result = hash_task(task_id)
                print(json.dumps(result, indent=2))
            else:
                # Hash all tasks
                results = {}
                for task_id in TASKS.keys():
                    result = hash_task(task_id)
                    results[task_id] = result["hash"]
                print(json.dumps(results, indent=2))

        elif command == "changed":
            # Detect changed packages
            base_ref = sys.argv[2] if len(sys.argv) > 2 else "main"
            changed_files = detect_changed_files(base_ref)
            changed_packages = map_files_to_packages(changed_files)
            affected_tasks = get_affected_tasks(changed_packages)

            print(json.dumps({
                "changed_files": changed_files,
                "changed_packages": list(changed_packages),
                "affected_tasks": affected_tasks
            }, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)

    else:
        # Default: show changed packages and affected tasks
        changed_files = detect_changed_files()
        changed_packages = map_files_to_packages(changed_files)
        affected_tasks = get_affected_tasks(changed_packages)

        print(f"Changed packages: {', '.join(changed_packages) if changed_packages else 'none'}")
        print(f"Affected tasks: {', '.join(affected_tasks) if affected_tasks else 'none'}")


if __name__ == "__main__":
    main()
