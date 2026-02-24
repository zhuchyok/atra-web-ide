import asyncio
import getpass
import json
import logging
import os
import re
import subprocess
from datetime import datetime

import asyncpg
from ai_core import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Credentials & Paths (env override для atra-web-ide / Mac Studio)
# Всё уже в локальной БД; удалённый сервер только если задан SERVER_IP
SERVER_IP = os.getenv("SERVER_IP", "localhost")
SERVER_USER = os.getenv("SERVER_USER", "root")
SERVER_PASS = os.getenv("SERVER_PASS", "u44Ww9NmtQj,XG")
SERVER_PATH = os.getenv("SERVER_PATH", "/root/atra")
LOCAL_USER = getpass.getuser()
DB_URL_LOCAL = os.getenv("DATABASE_URL") or os.getenv(
    "DATABASE_URL_LOCAL", "postgresql://admin:secret@localhost:5432/knowledge_os"
)


class ServerKnowledgeSync:
    """
    Synchronizes collective knowledge (MD reports, logs, agents) from the remote server
    to the local MacBook 'Knowledge OS'.
    """

    def __init__(self, db_url: str = DB_URL_LOCAL):
        self.db_url = db_url

    def _run_ssh(self, cmd: str):
        """Helper to run SSH commands or local commands if on server."""
        import socket

        if socket.gethostname() == "5330397-wo60847":
            # We are on the server, run locally
            return subprocess.check_output(cmd, shell=True).decode(errors="ignore")

        full_cmd = f"sshpass -p '{SERVER_PASS}' ssh -o StrictHostKeyChecking=no {SERVER_USER}@{SERVER_IP} \"{cmd}\""
        return subprocess.check_output(full_cmd, shell=True).decode(errors="ignore")

    async def _get_domain_id(self, conn, domain_name: str):
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
        if not domain_id:
            domain_id = await conn.fetchval(
                "INSERT INTO domains (name, description) VALUES ($1, $2) RETURNING id",
                domain_name,
                f"Knowledge synced from server for {domain_name}",
            )
        return domain_id

    async def sync_experts(self):
        """Pulls expert definitions, establishes hierarchy and handles 40+ employees from both SQL and MD files."""
        logger.info(f"👥 Deep syncing 40+ experts and hierarchy from {SERVER_IP}...")

        # 1. Sync from SQL Seed
        seed_path = f"{SERVER_PATH}/knowledge_os/db/seed_experts.sql"
        try:
            sql_content = self._run_ssh(f"cat '{seed_path}'")
            conn = await asyncpg.connect(self.db_url)
            await conn.execute(sql_content)
            await conn.close()
        except Exception as e:
            logger.error(f"Failed to sync experts from SQL: {e}")

        # 2. Sync from Learning Programs (MD files) - Auto-create named experts
        prog_path = f"{SERVER_PATH}/scripts/learning_programs"
        try:
            list_cmd = f"find {prog_path} -name '*_program.md'"
            programs = self._run_ssh(list_cmd).splitlines()

            conn = await asyncpg.connect(self.db_url)
            # Ensure domain exists
            domain_id = await self._get_domain_id(conn, "Expert Programs")

            for prog in programs:
                prog = prog.strip()
                if not prog:
                    continue

                content = self._run_ssh(f"cat '{prog}'")

                # Extract Name and Role from MD header: "# 🎓 ПРОГРАММА ОБУЧЕНИЯ: Артем (Code Reviewer)"
                header_match = re.search(r"ПРОГРАММА ОБУЧЕНИЯ:\s*([^\(]+)\(([^)]+)\)", content)
                if header_match:
                    name = header_match.group(1).strip()
                    role = header_match.group(2).strip()

                    # Create expert if not exists
                    exists = await conn.fetchval("SELECT id FROM experts WHERE name = $1", name)
                    if not exists:
                        logger.info(f"  🆕 Creating named expert: {name} ({role})")
                        await conn.execute(
                            """
                            INSERT INTO experts (name, role, system_prompt, department)
                            VALUES ($1, $2, $3, $4)
                        """,
                            name,
                            role,
                            f"You are {name}, {role}.\n{content[:1000]}",
                            "General",
                        )

                # Sync as knowledge node
                node_exists = await conn.fetchval(
                    "SELECT id FROM knowledge_nodes WHERE source_ref = $1", prog
                )
                if not node_exists:
                    embedding = await get_embedding(content[:2000])
                    await conn.execute(
                        """
                        INSERT INTO knowledge_nodes (domain_id, content, embedding, source_ref, is_verified)
                        VALUES ($1, $2, $3::vector, $4, true)
                    """,
                        domain_id,
                        content,
                        str(embedding) if embedding else None,
                        prog,
                    )

            await conn.close()
        except Exception as e:
            logger.error(f"Failed to sync expert programs: {e}")

        # 3. Define Hierarchy
        hierarchy_data = {
            "Виктория": {"level": 0, "parent": None, "dept": "Management"},
            "Виктория": {"level": 0, "parent": None, "dept": "Management"},
            "Дмитрий": {"level": 1, "parent": "Виктория", "dept": "ML/AI"},
            "Мария": {"level": 1, "parent": "Виктория", "dept": "Risk Management"},
            "Сергей": {"level": 1, "parent": "Виктория", "dept": "DevOps/Infra"},
            "Игорь": {"level": 1, "parent": "Виктория", "dept": "Backend"},
            "Анна": {"level": 1, "parent": "Виктория", "dept": "QA"},
            "Роман": {"level": 1, "parent": "Виктория", "dept": "Database"},
            "Ольга": {"level": 1, "parent": "Виктория", "dept": "Performance"},
            "Павел": {"level": 1, "parent": "Виктория", "dept": "Strategy"},
            "Максим": {"level": 1, "parent": "Виктория", "dept": "Analysis"},
            "Андрей": {"level": 1, "parent": "Виктория", "dept": "Architecture"},
            "Татьяна": {"level": 1, "parent": "Виктория", "dept": "Documentation"},
            "Артем": {"level": 2, "parent": "Виктория", "dept": "Review"},
            "Елена": {"level": 2, "parent": "Сергей", "dept": "Monitoring"},
            "Алексей": {"level": 2, "parent": "Мария", "dept": "Security"},
            "София": {"level": 2, "parent": "Игорь", "dept": "Web/Frontend"},
            "Никита": {"level": 2, "parent": "Игорь", "dept": "Web/Frontend"},
            "Дарья": {"level": 2, "parent": "Татьяна", "dept": "SEO"},
            "Марина": {"level": 2, "parent": "Татьяна", "dept": "SEO"},
            "Юлия": {"level": 2, "parent": "Виктория", "dept": "Legal"},
            "Екатерина": {"level": 2, "parent": "Максим", "dept": "Finance"},
            "Глаз": {"level": 2, "parent": "Дмитрий", "dept": "Vision/ML"},
        }

        # 4. Apply Hierarchy to DB
        conn = await asyncpg.connect(self.db_url)
        try:
            for name, data in hierarchy_data.items():
                await conn.execute(
                    """
                    UPDATE experts
                    SET metadata = metadata || $1::jsonb, department = COALESCE(department, $2)
                    WHERE name = $3
                """,
                    json.dumps({"hierarchy": {"level": data["level"], "parent": data["parent"]}}),
                    data["dept"],
                    name,
                )

            # Default for others
            await conn.execute("""
                UPDATE experts
                SET metadata = metadata || '{"hierarchy": {"level": 2, "parent": "Виктория"}}'::jsonb
                WHERE metadata->'hierarchy' IS NULL AND name != 'Виктория'
            """)

            count = await conn.fetchval("SELECT count(*) FROM experts")
            logger.info(f"✅ Deep sync complete. Total active employees: {count}")
            return count
        finally:
            await conn.close()

    async def sync_reports(self, limit: int = 100):
        """Pulls recent markdown reports from server and ingests them."""
        logger.info(f"🔄 Starting knowledge sync from {SERVER_IP}...")

        # 1. Get list of MD files on server (handling spaces correctly)
        # Use find with -printf to get full path and mtime, then sort and head
        list_cmd = f"find {SERVER_PATH} -name '*.md' -mtime -60 -printf '%T@ %p\\n' | sort -nr | head -n {limit} | cut -d' ' -f2-"
        try:
            result = self._run_ssh(list_cmd).splitlines()
        except Exception as e:
            logger.error(f"Failed to list remote files: {e}")
            return

        if not result:
            logger.info("No new reports found on server.")
            return

        conn = await asyncpg.connect(self.db_url)
        sync_count = 0

        for remote_file in result:
            remote_file = remote_file.strip()
            if not remote_file:
                continue

            file_name = remote_file.split("/")[-1]

            # Check if already synced
            exists = await conn.fetchval(
                "SELECT id FROM knowledge_nodes WHERE source_ref = $1", remote_file
            )
            if exists:
                continue

            logger.info(f"  📥 Syncing: {file_name}")

            # 2. Read remote file content (quoting path for spaces)
            try:
                cat_cmd = f"cat '{remote_file}'"
                content = self._run_ssh(cat_cmd)

                if len(content) < 50:
                    continue

                # 3. Generate embedding & Ingest
                embedding = await get_embedding(content[:2000])
                domain_id = await self._get_domain_id(conn, "Server Reports")

                await conn.execute(
                    """
                    INSERT INTO knowledge_nodes (domain_id, content, embedding, source_ref, is_verified, confidence_score)
                    VALUES ($1, $2, $3::vector, $4, true, 0.95)
                """,
                    domain_id,
                    content,
                    str(embedding) if embedding else None,
                    remote_file,
                )

                sync_count += 1
            except Exception as e:
                logger.error(f"Error syncing {file_name}: {e}")

        await conn.close()
        logger.info(f"✅ Sync complete. Ingested {sync_count} new knowledge nodes.")
        return sync_count


if __name__ == "__main__":
    sync = ServerKnowledgeSync()

    async def main():
        await sync.sync_experts()
        await sync.sync_reports(limit=50)

    asyncio.run(main())
