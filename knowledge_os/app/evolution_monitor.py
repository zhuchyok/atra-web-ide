import asyncio
import os
import asyncpg
import logging
from datetime import datetime
from training_pipeline import LocalTrainingPipeline
from distillation_engine import KnowledgeDistiller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SingularityEvolutionMonitor:
    """
    Core component of Singularity v4.0.
    Monitors knowledge growth and triggers autonomous self-improvement.
    """
    
    def __init__(self):
        self.pipeline = LocalTrainingPipeline()
        self.distiller = KnowledgeDistiller()

    async def run_daily_check(self):
        """Run daily knowledge distillation and check upgrade readiness."""
        logger.info("🌀 Starting daily Evolution check...")
        
        # 1. Collect new high-quality samples from logs and tasks
        new_samples = await self.distiller.collect_high_quality_samples(days=1)
        logger.info(f"✅ Distilled {new_samples} new high-quality samples.")
        
        # 2. Check if we reached the threshold for Fine-tuning
        ready, count = self.pipeline.check_readiness(threshold=500) # Lowered for earlier v4.0 visibility
        
        report = f"🧬 **Evolution Report ({datetime.now().strftime('%Y-%m-%d')})**\n"
        report += f"- New knowledge nodes: {new_samples}\n"
        report += f"- Total distillation dataset: {count}/500\n"
        
        if ready:
            report += "🚀 **THRESHOLD REACHED!** Preparing autonomous upgrade..."
            # Trigger training (background process on MacBook)
            status = self.pipeline.trigger_auto_upgrade()
            report += f"\n- Action: {status}"
        else:
            report += f"- Status: Accumulating wisdom. Needs {500 - count} more samples for the next evolution leap."
            
        logger.info(f"Report generated: {report}")
        return report

if __name__ == "__main__":
    monitor = SingularityEvolutionMonitor()
    asyncio.run(monitor.run_daily_check())

