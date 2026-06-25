import asyncio
import logging
import os

logger = logging.getLogger(__name__)
EVOLUTION_SCOUT_TIMEOUT_SEC = int(os.getenv("EVOLUTION_SCOUT_TIMEOUT_SEC", "120"))
EVOLUTION_DISTILL_TIMEOUT_SEC = int(os.getenv("EVOLUTION_DISTILL_TIMEOUT_SEC", "900"))
EVOLUTION_AUTODISTILL_TIMEOUT_SEC = int(os.getenv("EVOLUTION_AUTODISTILL_TIMEOUT_SEC", "180"))
EVOLUTION_EXPERT_TIMEOUT_SEC = int(os.getenv("EVOLUTION_EXPERT_TIMEOUT_SEC", "1200"))
EVOLUTION_ENABLE_EXPERT_MUTATIONS = os.getenv(
    "EVOLUTION_ENABLE_EXPERT_MUTATIONS", "true"
).lower() in ("true", "1", "yes")
_DISTILLER_SINGLETON = None


def _get_distiller_singleton():
    global _DISTILLER_SINGLETON
    if _DISTILLER_SINGLETON is None:
        from distillation_engine import KnowledgeDistiller

        _DISTILLER_SINGLETON = KnowledgeDistiller()
    return _DISTILLER_SINGLETON


class PerpetualEvolution:
    """
    [SINGULARITY 21.28] Perpetual Evolution Engine.
    Оркестрирует процессы самосовершенствования системы.
    """

    async def run_one_cycle(self) -> bool:
        """[SINGULARITY 28.1] Запускает один полный цикл эволюции (Level 8)."""
        logger.info("⚗️ [EVOLUTION:LEVEL-8] Начало рекурсивного цикла...")
        strict_budget_mode = os.getenv("EVOLUTION_STRICT_BUDGET_MODE", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        recursive_iterations = int(os.getenv("EVOLUTION_RECURSIVE_ITERATIONS", "1"))

        try:
            # 1. Рекурсивная эволюция ядра (Self-Improvement)
            try:
                from recursive_evolution import get_evolution_engine

                engine = get_evolution_engine()
                # Эволюционируем сам процесс эволюции (мета-обучение)
                evolve_coro = engine.evolve_task(
                    "Optimize evolution cycle efficiency",
                    "def optimize(): pass",
                    iterations=max(1, recursive_iterations),
                )
                if strict_budget_mode:
                    await asyncio.wait_for(evolve_coro, timeout=EVOLUTION_SCOUT_TIMEOUT_SEC)
                else:
                    await evolve_coro
            except Exception as e:
                logger.error(f"⚠️ [EVOLUTION] Ошибка рекурсивного цикла: {e}")

            # 2. Дистилляция знаний (Self-Distillation)
            try:
                distiller = _get_distiller_singleton()
                distill_coro = distiller.distill_knowledge_batch()
                if strict_budget_mode:
                    await asyncio.wait_for(distill_coro, timeout=EVOLUTION_DISTILL_TIMEOUT_SEC)
                else:
                    await distill_coro
            except Exception as e:
                logger.error(f"⚠️ [EVOLUTION] Ошибка дистилляции: {e}")

            # 3. Автономная дистилляция (Synthetic Data)
            try:
                from autonomous_distillation import get_autonomous_distiller

                auto_distiller = get_autonomous_distiller()
                auto_coro = auto_distiller.run_autonomous_distillation()
                if strict_budget_mode:
                    await asyncio.wait_for(auto_coro, timeout=EVOLUTION_AUTODISTILL_TIMEOUT_SEC)
                else:
                    await auto_coro
            except Exception as e:
                logger.error(f"⚠️ [EVOLUTION] Ошибка автономной дистилляции: {e}")

            # 4. Автономная эволюция/мутации экспертов
            if EVOLUTION_ENABLE_EXPERT_MUTATIONS:
                try:
                    from enhanced_expert_evolver import run_enhanced_evolution_cycle
                    from promotion_engine import run_promotion_cycle

                    evolve_coro = run_enhanced_evolution_cycle()
                    if strict_budget_mode:
                        await asyncio.wait_for(evolve_coro, timeout=EVOLUTION_EXPERT_TIMEOUT_SEC)
                    else:
                        await evolve_coro
                    await run_promotion_cycle()
                except Exception as e:
                    logger.error(f"⚠️ [EVOLUTION] Ошибка эволюции экспертов: {e}")

            return True
        except Exception as e:
            logger.error(f"❌ [EVOLUTION] Критическая ошибка в цикле: {e}")
            return False
