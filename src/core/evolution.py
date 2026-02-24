#!/usr/bin/env python3
"""
🚀 МОДУЛЬ ПРОАКТИВНОГО РАЗВИТИЯ
Выполняет микро-улучшения системы каждый час.
Автор: Виктория (Lead) + Дмитрий (ML)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

from src.ai.adaptive_filter_regulator import AdaptiveFilterRegulator, get_adaptive_regulator
from src.ai.lightgbm_predictor import get_lightgbm_predictor
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class AutonomousEvolver:
    """
    Класс для управления процессом ежечасной эволюции системы.
    """

    def __init__(self):
        try:
            self.regulator: Optional[AdaptiveFilterRegulator] = get_adaptive_regulator()
            self.predictor = get_lightgbm_predictor()
        except Exception:
            self.regulator = None
            self.predictor = None

    async def run_hourly_evolution(self):
        """Запускает бесконечный цикл эволюции системы (раз в час)"""
        logger.info("🕒 Запуск цикла эволюции системы...")
        while True:
            try:
                now = get_utc_now()
                logger.info("🕒 %s — Анализ возможностей для оптимизации...", now.strftime("%H:%M"))

                # 1. Оптимизация фильтров
                if self.regulator:
                    await self._optimize_filters()

                # 2. Логирование шага
                self._log_evolution_step()

            except Exception as e:
                logger.error("❌ Ошибка в цикле эволюции: %s", e)

            await asyncio.sleep(3600)

    async def _optimize_filters(self):
        """Выполняет микро-подстройку порогов фильтрации на основе AI"""
        logger.info("⚙️ Микро-подстройка порогов фильтрации...")
        try:
            if self.regulator:
                # Обновляем на основе AI-оптимизации
                await self.regulator.update_from_ai_optimization()
                logger.info("✅ Адаптивные пороги обновлены из AI Optimizer")
        except Exception as e:
            logger.error("❌ Ошибка подстройки фильтров: %s", e)

    def _log_evolution_step(self):
        """Логирует текущее состояние параметров эволюции в файл"""
        os.makedirs("logs", exist_ok=True)
        # Получаем текущие пороги из регулятора
        state = {}
        if self.regulator:
            state = {
                "rsi_long": self.regulator.current_rsi_long,
                "rsi_short": self.regulator.current_rsi_short,
                "volume_ratio": self.regulator.current_volume_ratio,
                "quality_score": self.regulator.current_quality_score,
            }

        entry = {
            "timestamp": get_utc_now().isoformat(),
            "action": "Filter Optimization",
            "state": state,
        }

        with open("logs/evolution_steps.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


async def start_evolution_task():
    """Точка входа для запуска задачи эволюции в main.py"""
    evolver = AutonomousEvolver()
    await evolver.run_hourly_evolution()
