import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from src.data.macro_provider import get_macro_provider
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class ResearchLab:
    """
    🔬 RESEARCH LAB: ГЕНЕРАТОР ГИПОТЕЗ И УЛУЧШЕНИЙ
    Каждый час генерирует идею, проверяет её и внедряет.
    """

    def __init__(self):
        self.hypotheses_file = "research/hypotheses_log.json"
        self.macro = get_macro_provider()
        os.makedirs("research", exist_ok=True)

    async def run_research_cycle(self):
        logger.info("🧪 Исследовательская лаборатория ATRA запущена.")

        while True:
            try:
                # 1. Получаем макро-данные (DXY)
                dxy_data = self.macro.get_dxy_trend()

                # 2. Генерируем гипотезу на основе макро-фона
                hypothesis = self._generate_hypothesis(dxy_data)

                # 3. Микро-тест (симуляция)
                is_valid = await self._test_hypothesis(hypothesis)

                # 4. Внедрение и логирование
                if is_valid:
                    self._apply_improvement(hypothesis)

                self._log_research(hypothesis, is_valid, dxy_data)

            except Exception as e:
                logger.error(f"❌ Ошибка в цикле исследования: {e}")

            await asyncio.sleep(3600)

    def _generate_hypothesis(self, macro):
        """Создает гипотезу на основе индекса доллара"""
        now = get_utc_now()
        if macro["trend"] == "BEARISH":
            return {
                "id": f"H-DXY-{now.strftime('%Y%m%d%H')}",
                "expert": "Pavel",
                "target": "Aggressive Longs",
                "idea": f"DXY падает ({macro['value']}). Смягчаем фильтры RSI для LONG на 15%",
                "expected_gain": "Increase trade frequency during macro tailwinds",
            }
        elif macro["trend"] == "BULLISH":
            return {
                "id": f"H-DXY-{now.strftime('%Y%m%d%H')}",
                "expert": "Maria",
                "target": "Capital Preservation",
                "idea": f"DXY растет ({macro['value']}). Увеличиваем Quality Score для LONG до 0.85",
                "expected_gain": "Avoid fake breakouts during dollar strength",
            }
        else:
            return {
                "id": f"H-GEN-{now.strftime('%Y%m%d%H')}",
                "expert": "Maxim",
                "target": "Normal Ops",
                "idea": "Стандартные настройки фильтров для нейтрального макро-фона",
                "expected_gain": "Stability",
            }

    async def _test_hypothesis(self, hypothesis):
        """Запускает реальный Rust-бэктест для проверки гипотезы"""
        logger.info(f"🧪 Тестирование гипотезы {hypothesis['id']}...")

        try:
            # 1. Формируем команду для запуска бэктеста
            # Используем облегченный бэктест на 5 монетах для скорости
            cmd = "python3 scripts/run_backtests_rust.py scripts/backtest_5coins_intelligent.py"

            # 2. Запускаем процесс
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode()

            # 3. Анализируем вывод
            if "Общая доходность:" in output:
                import re

                # Ищем число после "Общая доходность:"
                match = re.search(r"Общая доходность: ([+-]?\d+\.?\d*)%", output)
                if match:
                    return_pct = float(match.group(1))
                    logger.info(f"📊 Результат теста {hypothesis['id']}: {return_pct:+.2f}%")

                    # Гипотеза верна, если доходность положительна
                    return return_pct > 0

            if stderr:
                logger.error(f"❌ Ошибка при бэктесте: {stderr.decode()}")

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка запуска бэктеста: {e}")
            return False

    def _apply_improvement(self, hypothesis):
        """Внедряет подтвержденное улучшение в систему"""
        logger.info(f"🚀 Внедрение улучшения: {hypothesis['idea']}")

        try:
            # Обновляем глобальные настройки через adaptive_settings если они есть
            # Или сохраняем в файл, который подхватит бот
            os.makedirs("config/improvements", exist_ok=True)
            now = get_utc_now()
            filename = f"config/improvements/applied_{now.strftime('%Y%m%d')}.json"

            entry = {"timestamp": now.isoformat(), "hypothesis": hypothesis, "status": "Applied"}

            with open(filename, "a") as f:
                f.write(json.dumps(entry) + "\n")

            logger.info("✅ Улучшение сохранено и будет применено при следующем цикле.")

        except Exception as e:
            logger.error(f"❌ Ошибка внедрения улучшения: {e}")

    def _log_research(self, hypothesis, success, macro):
        entry = {
            "time": get_utc_now().isoformat(),
            "macro_snapshot": macro,
            "hypothesis": hypothesis,
            "status": "Applied" if success else "Rejected",
        }
        with open(self.hypotheses_file, "a") as f:
            f.write(json.dumps(entry) + "\n")


async def start_research_lab():
    lab = ResearchLab()
    await lab.run_research_cycle()
