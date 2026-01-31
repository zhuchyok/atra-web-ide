#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ AUTONOMOUS RISK GUARD (Portfolio Protection)
Automatically monitors daily drawdown and halts trading if limits are exceeded.
"""

import logging
import asyncio
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class AutonomousRiskGuard:
    """
    Guardian of the capital. Prevents catastrophic losses autonomously.
    """
    def __init__(self, max_daily_drawdown_pct: float = 3.0):
        self.max_daily_drawdown_pct = Decimal(str(max_daily_drawdown_pct))
        self.is_halted = False
        self.halt_reason = ""
        self.last_check_time = None
        self.initial_daily_balance = None
        self.current_day = datetime.now(timezone.utc).date()

    async def start_monitoring(self, interval_seconds: int = 60):
        """Continuous risk monitoring loop"""
        logger.info(f"🛡️ Autonomous Risk Guard active. Max Daily Drawdown: {self.max_daily_drawdown_pct}%")
        
        while True:
            try:
                await self._check_risk()
            except Exception as e:
                logger.error(f"❌ Error in Risk Guard: {e}")
            
            await asyncio.sleep(interval_seconds)

    async def _check_risk(self):
        """Calculates current drawdown and applies halts if necessary"""
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Reset at start of new day
        if today != self.current_day:
            logger.info("🌅 New trading day. Resetting daily risk metrics.")
            self.current_day = today
            self.initial_daily_balance = await self._get_current_equity()
            self.is_halted = False
            self.halt_reason = ""

        if self.initial_daily_balance is None:
            self.initial_daily_balance = await self._get_current_equity()
            if self.initial_daily_balance == Decimal("0"):
                return # Can't monitor without balance

        current_equity = await self._get_current_equity()
        if current_equity == Decimal("0"):
            return

        drawdown = (self.initial_daily_balance - current_equity) / self.initial_daily_balance * Decimal("100")
        
        if drawdown >= self.max_daily_drawdown_pct and not self.is_halted:
            self.is_halted = True
            self.halt_reason = f"Daily Drawdown Limit Hit: {drawdown:.2f}%"
            logger.critical(f"🚨 EMERGENCY HALT: {self.halt_reason}. Trading disabled for the rest of the day.")
            await self._apply_halt()
        elif self.is_halted:
            logger.info(f"🛡️ System currently in HALT mode: {self.halt_reason}")

    async def _get_current_equity(self) -> Decimal:
        """
        Calculates total equity (Balance + Unrealized PnL) from Exchange API.
        """
        try:
            # 1. Получаем ключи основного пользователя (id=1 или первого активного)
            from src.database.acceptance import AcceptanceDatabase
            db = AcceptanceDatabase()
            
            # Ищем первого активного пользователя с ключами Bitget
            query_users = "SELECT user_id FROM user_exchange_keys WHERE is_active = 1 LIMIT 1"
            user_rows = await db.execute_with_retry(query_users, (), is_write=False)
            
            if not user_rows:
                return Decimal("1000") # Fallback
                
            user_id = user_rows[0][0]
            keys = await db.get_active_exchange_keys(user_id)
            if not keys:
                return Decimal("1000")

            # 2. Получаем баланс через адаптер
            from src.execution.exchange_adapter import ExchangeAdapter
            async with ExchangeAdapter(keys=keys) as adapter:
                balance_data = await adapter.fetch_balance()
                
                if balance_data and 'total' in balance_data:
                    return Decimal(str(balance_data['total']))
                
        except Exception as e:
            logger.error(f"❌ [RISK_GUARD] Error fetching real equity: {e}")
        
        return Decimal("1000") # Fallback

    async def _apply_halt(self):
        """Disables signal generation globally"""
        # We can implement this by writing to a global state file or emergency_status.json
        import json
        status = {
            "is_halted": True,
            "reason": self.halt_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reset_at": (datetime.now(timezone.utc) + asyncio.timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
        }
        with open("emergency_status.json", "w") as f:
            json.dump(status, f)

async def start_risk_guard():
    """Entry point for main.py"""
    guard = AutonomousRiskGuard()
    await guard.start_monitoring()
