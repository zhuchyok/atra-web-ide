#!/usr/bin/env python3
"""
Тестовый скрипт для отслеживания полного процесса распределения задач
Отслеживает: выбор моделей, промпты, движение задачи через систему
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Добавляем путь к knowledge_os
knowledge_os_path = str(Path(__file__).parent.parent / "knowledge_os" / "app")
knowledge_os_root = str(Path(__file__).parent.parent / "knowledge_os")
sys.path.insert(0, knowledge_os_path)
sys.path.insert(0, knowledge_os_root)
# Устанавливаем PYTHONPATH для правильных импортов
os.environ['PYTHONPATH'] = f"{knowledge_os_root}:{knowledge_os_path}:{os.environ.get('PYTHONPATH', '')}"

# Настройка логирования для детального трейсинга
import logging

# Создаем детальный логгер
trace_logger = logging.getLogger("task_trace")
trace_logger.setLevel(logging.DEBUG)

# Создаем файл для трейса
trace_file = Path(__file__).parent.parent / "logs" / f"task_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
trace_file.parent.mkdir(exist_ok=True)

# Handler для файла
file_handler = logging.FileHandler(trace_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
trace_logger.addHandler(file_handler)

# Handler для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)
trace_logger.addHandler(console_handler)

# Настраиваем логирование для всех модулей
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[file_handler, console_handler]
)

# Перехватываем все логи
logger = logging.getLogger(__name__)


class TaskTracer:
    """Трейсер для отслеживания движения задачи"""

    def __init__(self):
        self.trace = {
            "start_time": datetime.now().isoformat(),
            "stages": [],
            "model_selections": [],
            "prompts": [],
            "decisions": [],
            "metrics": {}
        }

    def log_stage(self, stage_name: str, data: dict):
        """Логировать этап выполнения"""
        stage = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage_name,
            "data": data
        }
        self.trace["stages"].append(stage)
        trace_logger.info(f"📋 [STAGE] {stage_name}: {json.dumps(data, ensure_ascii=False, indent=2)}")

    def log_model_selection(self, who: str, task: str, selected_model: str, reason: str, available_models: list = None, context: dict = None):
        """Логировать выбор модели"""
        selection = {
            "timestamp": datetime.now().isoformat(),
            "who": who,
            "task": task,
            "selected_model": selected_model,
            "reason": reason,
            "available_models": available_models or [],
            "context": context or {}
        }
        self.trace["model_selections"].append(selection)
        trace_logger.info(f"🤖 [MODEL] {who} выбрал модель '{selected_model}' для задачи '{task[:50]}...' | Причина: {reason}")

    def log_prompt(self, who: str, stage: str, prompt: str, model: str = None):
        """Логировать промпт"""
        prompt_data = {
            "timestamp": datetime.now().isoformat(),
            "who": who,
            "stage": stage,
            "prompt": prompt,
            "model": model,
            "prompt_length": len(prompt)
        }
        self.trace["prompts"].append(prompt_data)
        trace_logger.debug(f"💬 [PROMPT] {who} ({stage}): {prompt[:200]}...")

    def log_decision(self, who: str, decision: str, reason: str, data: dict = None):
        """Логировать решение"""
        decision_data = {
            "timestamp": datetime.now().isoformat(),
            "who": who,
            "decision": decision,
            "reason": reason,
            "data": data or {}
        }
        self.trace["decisions"].append(decision_data)
        trace_logger.info(f"🎯 [DECISION] {who}: {decision} | Причина: {reason}")

    def save_trace(self, output_file: str):
        """Сохранить трейс в файл"""
        self.trace["end_time"] = datetime.now().isoformat()
        self.trace["duration_seconds"] = (
            datetime.fromisoformat(self.trace["end_time"]) -
            datetime.fromisoformat(self.trace["start_time"])
        ).total_seconds()

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.trace, f, ensure_ascii=False, indent=2)

        trace_logger.info(f"💾 Трейс сохранен в {output_file}")


# Глобальный трейсер
tracer = TaskTracer()

# Устанавливаем трейсер в hooks
def setup_tracer():
    try:
        from app.task_trace_hooks import set_tracer
        set_tracer(tracer)
        trace_logger.info("✅ Трейсер установлен в hooks")
    except ImportError:
        trace_logger.warning("⚠️ task_trace_hooks не найден, детальное логирование недоступно")


async def test_task_distribution():
    """Тестировать распределение задач с детальным трейсингом"""

    trace_logger.info("=" * 80)
    trace_logger.info("🚀 НАЧАЛО ТЕСТИРОВАНИЯ СИСТЕМЫ РАСПРЕДЕЛЕНИЯ ЗАДАЧ")
    trace_logger.info("=" * 80)

    # Тестовая задача - реальная задача пользователя
    test_goal = "напишут одностраничный сайт по пластиковым окнам современный и наполнят его сео"

    tracer.log_stage("INIT", {
        "goal": test_goal,
        "description": "Инициализация теста"
    })

    # Устанавливаем трейсер ПЕРЕД импортом Victoria
    setup_tracer()

    try:
        import os
        # Импортируем Victoria Enhanced ПОСЛЕ установки tracer
        from victoria_enhanced import VictoriaEnhanced

        # Получаем DATABASE_URL используя централизованную утилиту
        try:
            from scripts.utils.environment import get_database_url, is_docker
            db_url = get_database_url(
                default_docker="postgresql://admin:secret@knowledge_postgres:5432/knowledge_os",
                default_local="postgresql://admin:secret@localhost:5432/knowledge_os"
            )
            docker_status = is_docker()
        except ImportError:
            # Fallback для обратной совместимости
            docker_status = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
            if docker_status:
                db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
            else:
                db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

        trace_logger.info(f"🔗 DATABASE_URL: {db_url.replace('secret', '***')} (Docker: {docker_status})")

        tracer.log_stage("VICTORIA_INIT", {
            "db_url": db_url,
            "description": "Инициализация Victoria Enhanced"
        })

        # Создаем Victoria
        victoria = VictoriaEnhanced()

        tracer.log_stage("TASK_START", {
            "goal": test_goal,
            "description": "Начало выполнения задачи через Victoria"
        })

        # Выполняем задачу
        trace_logger.info(f"\n{'='*80}")
        trace_logger.info(f"📝 ИСХОДНАЯ ЗАДАЧА: {test_goal}")
        trace_logger.info(f"{'='*80}\n")

        result = await victoria.solve(goal=test_goal, context=None)

        tracer.log_stage("TASK_COMPLETE", {
            "result_length": len(result.get("result", "")) if result else 0,
            "method": result.get("method", "unknown") if result else "none",
            "metadata": result.get("metadata", {}) if result else {}
        })

        # Выводим результат
        trace_logger.info(f"\n{'='*80}")
        trace_logger.info("✅ РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ")
        trace_logger.info(f"{'='*80}\n")

        if result:
            trace_logger.info(f"Метод: {result.get('method', 'N/A')}")
            trace_logger.info(f"Отдел: {result.get('department', 'N/A')}")
            trace_logger.info(f"Назначений: {result.get('assignments_count', 0)}")
            trace_logger.info(f"Выполнено: {result.get('completed_count', 0)}")
            trace_logger.info(f"Утверждено: {result.get('approved_count', 0)}")

            if result.get('metrics'):
                trace_logger.info(f"\n📊 МЕТРИКИ:")
                metrics = result['metrics']
                trace_logger.info(f"  Всего задач: {metrics.get('total_tasks', 0)}")
                trace_logger.info(f"  Выполнено: {metrics.get('completed_tasks', 0)}")
                trace_logger.info(f"  Среднее время: {metrics.get('avg_execution_time', 0):.2f}с")
                trace_logger.info(f"  Успешность: {metrics.get('success_rate', 0):.2f}%")

            if result.get('metadata'):
                trace_logger.info(f"\n🔧 МЕТАДАННЫЕ:")
                metadata = result['metadata']
                trace_logger.info(f"  Retry: {'✅' if metadata.get('retry_enabled') else '❌'}")
                trace_logger.info(f"  Load Balancing: {'✅' if metadata.get('load_balancing_enabled') else '❌'}")
                trace_logger.info(f"  Validation: {'✅' if metadata.get('validation_enabled') else '❌'}")
                trace_logger.info(f"  Escalation: {'✅' if metadata.get('escalation_enabled') else '❌'}")

            full_result = result.get('result', 'N/A')
            trace_logger.info(f"\n📄 РЕЗУЛЬТАТ ({len(full_result) if isinstance(full_result, str) else 0} символов):\n{full_result[:1000]}...")

            # Сохраняем полный результат в отдельный файл
            if full_result and full_result != 'N/A':
                result_file = Path(__file__).parent.parent / "logs" / f"task_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(result_file, 'w', encoding='utf-8') as f:
                    f.write(full_result)
                trace_logger.info(f"💾 Полный результат сохранен в: {result_file}")

                # Если результат содержит HTML, сохраняем как HTML файл
                if '<html' in full_result.lower() or '<!doctype' in full_result.lower():
                    html_file = Path(__file__).parent.parent / "logs" / f"task_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(full_result)
                    trace_logger.info(f"🌐 HTML результат сохранен в: {html_file}")
        else:
            trace_logger.error("❌ Результат не получен")

        # Сохраняем трейс
        trace_output = Path(__file__).parent.parent / "logs" / f"task_trace_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        tracer.save_trace(str(trace_output))

        trace_logger.info(f"\n{'='*80}")
        trace_logger.info("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        trace_logger.info(f"📄 Детальный лог: {trace_file}")
        trace_logger.info(f"📄 JSON трейс: {trace_output}")
        trace_logger.info(f"{'='*80}\n")

        return result

    except Exception as e:
        trace_logger.error(f"❌ ОШИБКА: {e}", exc_info=True)
        tracer.log_stage("ERROR", {
            "error": str(e),
            "type": type(e).__name__
        })
        raise


if __name__ == "__main__":
    asyncio.run(test_task_distribution())
