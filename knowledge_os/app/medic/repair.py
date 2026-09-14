"""
Victoria Medic — тулкит ремонта: снапшоты, откат, рестарт, canary-верификация.

Все действия детерминированные, без LLM. Снапшот ПЕРЕД любым изменением.
last_good/ обновляется только после успешного canary.
"""

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
PROTECTED_FILES = ["ai_core.py", "ai_pipeline.py", "victoria_enhanced.py"]
SNAPSHOT_ROOT = APP_DIR.parent / "backups" / "victoria_snapshots"
LAST_GOOD_DIR = SNAPSHOT_ROOT / "last_good"
MAX_SNAPSHOTS = 10

VICTORIA_URL = "http://victoria-agent:8000"
CANARY_TIMEOUT = 60
RESTART_WAIT = 30
RESTART_CHECKS = 10


class RepairToolkit:
    def __init__(self, victoria_url: str = VICTORIA_URL):
        self.victoria_url = victoria_url
        self.rollback_manager = None
        self.feedback_loop = None
        SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
        LAST_GOOD_DIR.mkdir(parents=True, exist_ok=True)

        # Try to import and initialize rollback manager
        try:
            from app.medic.rollback_manager import RollbackManager
            self.rollback_manager = RollbackManager()
        except Exception as e:
            logger.debug("RollbackManager not available: %s", e)

        # Try to import and initialize feedback loop
        try:
            from app.medic.feedback_loop import FeedbackLoop
            self.feedback_loop = FeedbackLoop()
        except Exception as e:
            logger.debug("FeedbackLoop not available: %s", e)

    def snapshot(self, tag: str) -> Path:
        # Create rollback point before snapshot
        if self.rollback_manager:
            try:
                self.rollback_manager.before_change(
                    file_path=str(APP_DIR),
                    change_type="snapshot",
                    description=f"Creating snapshot: {tag}"
                )
            except Exception as e:
                logger.debug("Rollback before_change failed: %s", e)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = SNAPSHOT_ROOT / f"{ts}_{tag}"
        dest.mkdir(parents=True, exist_ok=True)
        for name in PROTECTED_FILES:
            src = APP_DIR / name
            if src.exists():
                shutil.copy2(src, dest / name)
        self._prune_snapshots()
        logger.info("snapshot -> %s", dest)

        # Record rollback point after snapshot
        if self.rollback_manager:
            try:
                self.rollback_manager.after_change(
                    file_path=str(APP_DIR),
                    change_type="snapshot",
                    snapshot_path=str(dest)
                )
            except Exception as e:
                logger.debug("Rollback after_change failed: %s", e)

        return dest

    def _prune_snapshots(self):
        snaps = sorted(
            (p for p in SNAPSHOT_ROOT.iterdir() if p.is_dir() and p.name != "last_good"),
            key=lambda p: p.name,
        )
        for old in snaps[:-MAX_SNAPSHOTS]:
            shutil.rmtree(old, ignore_errors=True)

    def has_last_good(self) -> bool:
        return any(LAST_GOOD_DIR.glob("*.py"))

    def mark_last_good(self):
        LAST_GOOD_DIR.mkdir(parents=True, exist_ok=True)
        for name in PROTECTED_FILES:
            src = APP_DIR / name
            if src.exists():
                shutil.copy2(src, LAST_GOOD_DIR / name)
        logger.info("last_good updated")

    def rollback_last_good(self) -> bool:
        if not self.has_last_good():
            logger.warning("no last_good snapshot, rollback skipped")
            return False

        # Create rollback point before restoring
        if self.rollback_manager:
            try:
                self.rollback_manager.before_change(
                    file_path=str(APP_DIR),
                    change_type="rollback",
                    description="Rolling back to last_good state"
                )
            except Exception as e:
                logger.debug("Rollback before_change failed: %s", e)

        for name in PROTECTED_FILES:
            src = LAST_GOOD_DIR / name
            if src.exists():
                shutil.copy2(src, APP_DIR / name)
        logger.info("rolled back from last_good")

        # Log the rollback in feedback loop
        if self.feedback_loop:
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop is not None:
                    loop.create_task(
                        self.feedback_loop.log_fix(
                            error_id="rollback_last_good",
                            action_taken="restored_last_good_state",
                            action_result="success",
                        )
                    )
            except Exception as e:
                logger.debug("Feedback log_fix failed: %s", e)

        return True

    async def restart_victoria(self) -> bool:
        try:
            import docker

            client = docker.from_env()
            container = client.containers.get("victoria-agent")
            logger.info("restarting victoria-agent...")
            container.restart(timeout=60)
            await asyncio.sleep(RESTART_WAIT)
            return True
        except Exception as e:
            logger.error("restart failed: %s", e)
            return False

    async def canary(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{self.victoria_url}/health")
                if r.status_code != 200:
                    return False
        except Exception:
            return False
        # Do not call /run in canary checks: it creates delegated workload.
        # Health probe is enough for deterministic liveness here.
        return True

    async def wait_healthy(self) -> bool:
        for _ in range(RESTART_CHECKS):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.get(f"{self.victoria_url}/health")
                    if r.status_code == 200:
                        return True
            except Exception:
                pass
            await asyncio.sleep(10)
        return False
