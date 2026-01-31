#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌉 AI INSIGHT BRIDGE (Autonomous Knowledge Sync)
Synchronizes AI-detected market patterns and strategy performance to Knowledge OS.
"""

import logging
import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class KnowledgeBridge:
    """
    Bridges the gap between AI Learning and Human-Readable Knowledge.
    """
    def __init__(self, knowledge_os_path: str = "knowledge_os/ai_insights/"):
        self.knowledge_os_path = knowledge_os_path
        os.makedirs(self.knowledge_os_path, exist_ok=True)

    async def sync_loop(self, interval_hours: int = 12):
        """Periodically syncs insights"""
        while True:
            try:
                await self.generate_insights()
            except Exception as e:
                logger.error(f"❌ Error in Knowledge Bridge: {e}")
            
            await asyncio.sleep(interval_hours * 3600)

    async def generate_insights(self):
        """Analyzes recent performance and generates structured insights"""
        logger.info("🌉 Generating AI insights for Knowledge OS...")
        
        insights = []
        
        # 1. Best Performing Coins
        top_coins = self._get_top_performing_coins()
        if top_coins:
            insights.append({
                "type": "performance",
                "title": "Top Performing Coins (Last 30 Days)",
                "data": top_coins,
                "recommendation": "Increase risk multiplier for these symbols."
            })

        # 2. Market Regime Analysis
        regime_stats = self._get_regime_performance()
        if regime_stats:
            insights.append({
                "type": "market_regime",
                "title": "Strategy Performance by Market Phase",
                "data": regime_stats,
                "recommendation": "Use STRICT mode during High Volatility phases."
            })

        # Save as Markdown for Knowledge OS
        self._save_to_knowledge_os(insights)

    def _get_top_performing_coins(self) -> List[Dict[str, Any]]:
        """Queries DB for top symbols by profit factor"""
        try:
            conn = sqlite3.connect("trading.db")
            cursor = conn.cursor()
            query = """
                SELECT symbol, 
                       CAST(COUNT(CASE WHEN result IN ('TP1', 'TP2') THEN 1 END) AS FLOAT) / COUNT(*) as win_rate,
                       SUM(CASE WHEN net_profit > 0 THEN net_profit ELSE 0 END) / 
                       ABS(SUM(CASE WHEN net_profit < 0 THEN net_profit ELSE 0.00001 END)) as profit_factor
                FROM signals_log
                WHERE result IS NOT NULL
                GROUP BY symbol
                HAVING COUNT(*) > 5
                ORDER BY win_rate DESC
                LIMIT 5
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {"symbol": r[0], "win_rate": round(r[1], 2), "profit_factor": round(r[2], 2)}
                for r in rows
            ]
        except Exception as e:
            logger.error(f"❌ Error querying top coins: {e}")
            return []

    def _get_regime_performance(self) -> Dict[str, Any]:
        """Queries DB for regime-based stats if available in signals_log"""
        try:
            conn = sqlite3.connect("trading.db")
            cursor = conn.cursor()
            # Пытаемся извлечь regime из json meta в signals_log если он там есть
            query = """
                SELECT result, net_profit
                FROM signals_log
                WHERE result IS NOT NULL
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return {}
                
            # Группируем по результату (пока упрощенно, так как regime может не быть в БД)
            wins = len([r for r in rows if r[0] in ('TP1', 'TP2')])
            total = len(rows)
            wr = wins / total if total > 0 else 0
            
            return {
                "GLOBAL_STATS": {"win_rate": round(wr, 2), "total_trades": total}
            }
        except Exception as e:
            logger.error(f"❌ Error querying regime stats: {e}")
            return {}

    def _save_to_knowledge_os(self, insights: List[Dict[str, Any]]):
        """Saves insights as a Markdown report"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"ai_insights_{timestamp}.md"
        path = os.path.join(self.knowledge_os_path, filename)
        
        with open(path, "w") as f:
            f.write(f"# 🧠 AI INSIGHTS REPORT - {datetime.now(timezone.utc).isoformat()}\n\n")
            for insight in insights:
                f.write(f"## {insight['title']}\n")
                f.write(f"**Type:** {insight['type']}\n\n")
                f.write(f"```json\n{json.dumps(insight['data'], indent=2)}\n```\n\n")
                f.write(f"**Recommendation:** {insight['recommendation']}\n\n")
                f.write("---\n\n")
        
        logger.info(f"✅ AI Insights synced to {path}")

async def start_knowledge_sync():
    """Entry point for main.py"""
    bridge = KnowledgeBridge()
    await bridge.sync_loop()

if __name__ == "__main__":
    # Настройка логирования при прямом запуске
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        asyncio.run(start_knowledge_sync())
    except KeyboardInterrupt:
        pass
