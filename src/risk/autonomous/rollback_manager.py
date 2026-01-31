import logging
import asyncio
import json
import os
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Optional, Dict, List, Tuple
from src.database.db import Database
from src.telegram.enhanced_delivery import notify_user_enhanced

logger = logging.getLogger(__name__)

class AutonomousRollbackManager:
    """
    🛡️ Autonomous Rollback System
    Protects capital by reverting to stable parameters during abnormal losses.
    """
    
    def __init__(self, db_path: str = "/root/atra/trading.db"):
        self.db = Database(db_path=db_path) # Используем абсолютный путь для стабильности
        self.check_interval_hours = 1
        self.snapshot_interval_hours = 24
        self.pnl_threshold = -5.0 # -5% daily loss trigger
        self.consecutive_losses_threshold = 3
        self.min_win_rate_for_stable = 60.0 # 60% win rate to save a stable snapshot

    async def run_loop(self):
        """Main loop for performance monitoring and auto-rollback."""
        logger.info("🛡️ Autonomous Rollback System (ARS) loop started")
        
        last_snapshot_time = get_utc_now() - timedelta(hours=self.snapshot_interval_hours)
        
        while True:
            try:
                # 1. Performance Check
                is_abnormal, reason = await self._check_abnormal_losses()
                
                if is_abnormal:
                    logger.warning(f"🚨 ABNORMAL LOSS DETECTED: {reason}. Initiating rollback...")
                    await self._perform_rollback(reason)
                else:
                    # 2. Stable Snapshot (every 24h if performance is good)
                    if get_utc_now() - last_snapshot_time >= timedelta(hours=self.snapshot_interval_hours):
                        await self._maybe_save_stable_snapshot()
                        last_snapshot_time = get_utc_now()
                
            except Exception as e:
                logger.error(f"❌ Error in ARS loop: {e}", exc_info=True)
            
            await asyncio.sleep(3600) # Check every hour

    async def _check_abnormal_losses(self) -> Tuple[bool, Optional[str]]:
        """Analyzes recent trades for abnormal loss patterns."""
        try:
            # Get trades from the last 24 hours
            since = (get_utc_now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            
            with self.db._lock:
                cur = self.db.conn.execute(
                    "SELECT pnl_percent, exit_reason FROM trades WHERE exit_time >= ? ORDER BY exit_time DESC",
                    (since,)
                )
                recent_trades = cur.fetchall()
            
            if not recent_trades:
                return False, None

            # Check for cumulative PnL
            total_pnl = sum(float(t[0] or 0) for t in recent_trades)
            if total_pnl <= self.pnl_threshold:
                return True, f"Daily PnL is {total_pnl:.2f}% (threshold: {self.pnl_threshold}%)"

            # Check for consecutive losses
            consecutive_losses = 0
            for pnl, _ in recent_trades:
                if pnl and float(pnl) < 0:
                    consecutive_losses += 1
                else:
                    break # Reset on first win
            
            if consecutive_losses >= self.consecutive_losses_threshold:
                return True, f"{consecutive_losses} consecutive losses detected"

            return False, None

        except Exception as e:
            logger.error(f"Error checking abnormal losses: {e}")
            return False, None

    async def _maybe_save_stable_snapshot(self):
        """Saves current configuration as a stable snapshot if performance is good."""
        try:
            # Check performance over the last 7 days
            since = (get_utc_now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            
            with self.db._lock:
                cur = self.db.conn.execute(
                    "SELECT pnl_percent FROM trades WHERE exit_time >= ?",
                    (since,)
                )
                trades = cur.fetchall()
            
            if len(trades) < 5:
                logger.info("Not enough trades to verify stability for snapshot")
                return

            win_count = sum(1 for t in trades if float(t[0] or 0) > 0)
            win_rate = (win_count / len(trades)) * 100
            total_pnl = sum(float(t[0] or 0) for t in trades)

            if win_rate >= self.min_win_rate_for_stable:
                settings = self.db.get_all_system_settings()
                if settings:
                    logger.info(f"✅ Performance is stable (WR={win_rate:.1f}%, PnL={total_pnl:.2f}%). Saving snapshot...")
                    self.db.save_config_snapshot(settings, win_rate, total_pnl, is_stable=True)
            else:
                logger.info(f"Performance not stable enough for snapshot (WR={win_rate:.1f}%)")

        except Exception as e:
            logger.error(f"Error saving stable snapshot: {e}")

    async def _perform_rollback(self, reason: str):
        """Reverts system settings to the latest stable snapshot."""
        try:
            stable_config = self.db.get_latest_stable_snapshot()
            
            if not stable_config:
                logger.error("❌ NO STABLE SNAPSHOT FOUND! Cannot perform rollback.")
                await self._alert_user(f"⚠️ ABNORMAL LOSS: {reason}\n❌ Rollback FAILED: No stable snapshot found.")
                return

            # Apply stable config
            for key, value in stable_config.items():
                self.db.set_system_setting(key, value)
            
            logger.warning("🔄 System settings reverted to latest stable snapshot.")
            
            # Log evolution step
            os.makedirs("logs", exist_ok=True)
            with open("logs/evolution_steps.log", "a") as f:
                f.write(f"{get_utc_now().isoformat()} — EMERGENCY ROLLBACK: {reason}. Reverted to last stable config.\n")

            await self._alert_user(f"🛡️ <b>EMERGENCY ROLLBACK</b>\n\nReason: {reason}\n✅ System settings reverted to last stable configuration.")

        except Exception as e:
            logger.error(f"Error performing rollback: {e}")

    async def _alert_user(self, message: str):
        """Sends emergency alert to Telegram."""
        # Get users with 'auto' mode or admin user
        # For simplicity, we use notify_user_enhanced which should be configured with default chat_id
        # In a real scenario, we might want to alert all admins.
        try:
            # We need a user_id. Let's try to get it from users_data or env
            # For now, we'll try to find any user who has auto mode
            user_ids = []
            with self.db._lock:
                cur = self.db.conn.execute("SELECT user_id FROM users_data")
                rows = cur.fetchall()
                user_ids = [row[0] for row in rows]
            
            if user_ids:
                for uid in user_ids:
                    await notify_user_enhanced(uid, message)
            else:
                # Fallback to default if available
                await notify_user_enhanced(None, message)
        except Exception as e:
            logger.error(f"Error alerting user: {e}")

async def start_rollback_manager():
    manager = AutonomousRollbackManager()
    await manager.run_loop()

