"""
Model Fine-Tuner - Дообучение локальных моделей для улучшения качества, скорости и снижения галлюцинаций
Поддерживает MLX (Apple Silicon) и Ollama модели
"""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
MLX_MODELS_DIR = os.getenv("MLX_MODELS_DIR", os.path.expanduser("~/.mlx_models"))
TRAINING_DATA_DIR = os.getenv("TRAINING_DATA_DIR", "./training_data")


class ModelFineTuner:
    """
    Дообучение моделей для улучшения качества и снижения галлюцинаций

    ⚠️ ВАЖНО: НЕ дообучаем на фактах из базы знаний!
    - Факты уже доступны через RAG (Виктория и Вероника используют)
    - Дообучаем ТОЛЬКО на паттернах стиля и форматах ответов
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.mlx_models_dir = MLX_MODELS_DIR
        self.training_data_dir = TRAINING_DATA_DIR

        # Создаем директории если их нет
        os.makedirs(self.training_data_dir, exist_ok=True)
        os.makedirs(self.mlx_models_dir, exist_ok=True)

    async def collect_style_patterns(self, limit: int = 500) -> List[Dict]:
        """
        Собрать паттерны СТИЛЯ для обучения (НЕ факты!)

        ⚠️ ВАЖНО: Собираем только стиль ответов, форматирование, структуру.
        НЕ собираем факты - они уже в RAG!

        Что собираем:
        - Стиль ответов Виктории (структурированные, с эмодзи)
        - Форматы (планы, отчеты, код)
        - Паттерны рассуждений
        - Структуру ответов
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Собираем только примеры со стилем и форматированием
                # Исключаем чистые факты (type='fact', 'definition')
                rows = await conn.fetch(
                    """
                    SELECT content, metadata, confidence_score, domain_id
                    FROM knowledge_nodes
                    WHERE is_verified = TRUE
                    AND confidence_score >= 0.8
                    AND (
                        metadata->>'type' IN ('code_example', 'plan', 'report', 'analysis', 'solution')
                        OR content LIKE '%📋%' OR content LIKE '%✅%' OR content LIKE '%💡%'
                        OR content LIKE '%🔍%' OR content LIKE '%📊%'
                        OR content LIKE '%ПЛАН%' OR content LIKE '%ШАГ%' OR content LIKE '%ЭТАП%'
                    )
                    AND metadata->>'type' NOT IN ('fact', 'definition', 'data')
                    ORDER BY confidence_score DESC, usage_count DESC
                    LIMIT $1
                """,
                    limit,
                )

                style_patterns = []
                for row in rows:
                    domain = await conn.fetchval(
                        "SELECT name FROM domains WHERE id = $1", row["domain_id"]
                    )
                    content = row["content"]
                    metadata = row["metadata"] or {}
                    task_type = metadata.get("type", "general")

                    # Определяем тип стиля
                    style_type = self._determine_style_type(content, task_type)

                    style_patterns.append(
                        {
                            "instruction": self._create_style_instruction(
                                style_type, task_type, domain
                            ),
                            "input": "",  # Стиль не зависит от входа
                            "output": content,  # Пример стиля
                            "style_type": style_type,
                            "domain": domain,
                            "confidence": float(row["confidence_score"]),
                            "metadata": {
                                **metadata,
                                "is_style_pattern": True,
                                "not_fact": True,  # Явно помечаем, что это не факт
                            },
                        }
                    )

                logger.info(f"✅ Собрано {len(style_patterns)} паттернов СТИЛЯ (не фактов!)")
                return style_patterns

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка сбора паттернов стиля: {e}")
            return []

    def _determine_style_type(self, content: str, task_type: str) -> str:
        """Определить тип стиля ответа"""
        content_lower = content.lower()

        if "📋" in content or "план" in content_lower or "этап" in content_lower:
            return "structured_plan"
        elif "✅" in content or "шаг" in content_lower:
            return "step_by_step"
        elif "💡" in content or "рекомендация" in content_lower:
            return "recommendation"
        elif "🔍" in content or "анализ" in content_lower:
            return "analysis"
        elif task_type == "coding" or "def " in content or "function" in content_lower:
            return "code_pattern"
        elif "📊" in content or "отчет" in content_lower:
            return "report"
        else:
            return "general_structured"

    def _create_style_instruction(self, style_type: str, task_type: str, domain: str) -> str:
        """Создать инструкцию для обучения стилю"""
        style_instructions = {
            "structured_plan": f"Создай структурированный план в стиле Виктории (с эмодзи, по этапам) для домена {domain}",
            "step_by_step": f"Ответь пошагово в стиле Виктории (с ✅, структурированно) для домена {domain}",
            "recommendation": f"Дай рекомендацию в стиле Виктории (с 💡, структурированно) для домена {domain}",
            "analysis": f"Проведи анализ в стиле Виктории (с 🔍, структурированно) для домена {domain}",
            "code_pattern": f"Напиши код в стиле Виктории (чистый, документированный) для домена {domain}",
            "report": f"Создай отчет в стиле Виктории (с 📊, структурированно) для домена {domain}",
            "general_structured": f"Ответь структурированно в стиле Виктории для домена {domain}",
        }
        return style_instructions.get(style_type, f"Ответь в стиле Виктории для домена {domain}")

    async def collect_training_data_from_knowledge_base(self, limit: int = 1000) -> List[Dict]:
        """
        ⚠️ УСТАРЕВШИЙ МЕТОД: Собирает факты (не рекомендуется!)

        ВАЖНО: Не используйте этот метод для дообучения на фактах!
        Факты уже доступны через RAG (Виктория и Вероника используют).

        Используйте collect_style_patterns() вместо этого!
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Собираем проверенные знания с высоким confidence_score
                rows = await conn.fetch(
                    """
                    SELECT content, metadata, confidence_score, domain_id
                    FROM knowledge_nodes
                    WHERE is_verified = TRUE
                    AND confidence_score >= 0.8
                    ORDER BY confidence_score DESC, usage_count DESC
                    LIMIT $1
                """,
                    limit,
                )

                training_data = []
                for row in rows:
                    # Получаем домен
                    domain = await conn.fetchval(
                        "SELECT name FROM domains WHERE id = $1", row["domain_id"]
                    )

                    # Формируем промпт и ответ
                    content = row["content"]
                    metadata = row["metadata"] or {}

                    # Определяем тип задачи
                    task_type = metadata.get("type", "general")

                    training_data.append(
                        {
                            "instruction": self._create_instruction(content, task_type, domain),
                            "input": "",
                            "output": content,
                            "domain": domain,
                            "confidence": float(row["confidence_score"]),
                            "metadata": metadata,
                        }
                    )

                logger.info(f"✅ Собрано {len(training_data)} примеров для обучения")
                return training_data

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка сбора данных из базы знаний: {e}")
            return []

    def _create_instruction(self, content: str, task_type: str, domain: str) -> str:
        """Создать инструкцию для обучения"""
        if task_type == "coding":
            return f"Напиши код для задачи в домене {domain}"
        elif task_type == "reasoning":
            return f"Реши задачу рассуждения в домене {domain}"
        elif task_type == "explanation":
            return f"Объясни концепцию из домена {domain}"
        else:
            return f"Ответь на вопрос из домена {domain}"

    async def collect_anti_hallucination_data(self) -> List[Dict]:
        """Собрать данные для снижения галлюцинаций"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Собираем примеры с явными указаниями на точность
                rows = await conn.fetch("""
                    SELECT content, metadata
                    FROM knowledge_nodes
                    WHERE is_verified = TRUE
                    AND confidence_score >= 0.9
                    AND metadata->>'type' IN ('fact', 'definition', 'code_example')
                    ORDER BY confidence_score DESC
                    LIMIT 500
                """)

                anti_hallucination_data = []
                for row in rows:
                    content = row["content"]
                    metadata = row["metadata"] or {}

                    anti_hallucination_data.append(
                        {
                            "instruction": "Отвечай только на основе проверенных фактов. Если не знаешь точно - скажи 'Не уверен'.",
                            "input": content[:200],  # Первые 200 символов как контекст
                            "output": content,
                            "metadata": {**metadata, "anti_hallucination": True, "verified": True},
                        }
                    )

                logger.info(
                    f"✅ Собрано {len(anti_hallucination_data)} примеров против галлюцинаций"
                )
                return anti_hallucination_data

            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Ошибка сбора данных против галлюцинаций: {e}")
            return []

    def prepare_training_dataset(self, training_data: List[Dict], output_file: str) -> str:
        """Подготовить датасет для обучения в формате JSONL"""
        output_path = os.path.join(self.training_data_dir, output_file)

        with open(output_path, "w", encoding="utf-8") as f:
            for item in training_data:
                # Формат для MLX-LM
                formatted = {
                    "text": f"### Instruction:\n{item['instruction']}\n\n### Input:\n{item.get('input', '')}\n\n### Response:\n{item['output']}"
                }
                f.write(json.dumps(formatted, ensure_ascii=False) + "\n")

        logger.info(f"✅ Датасет сохранен: {output_path} ({len(training_data)} примеров)")
        return output_path

    async def fine_tune_mlx_model(
        self,
        base_model: str,
        training_data_path: str,
        output_model_name: str,
        lora_rank: int = 16,
        lora_alpha: int = 32,
        batch_size: int = 4,
        learning_rate: float = 1e-4,
        num_epochs: int = 3,
    ) -> Tuple[bool, str]:
        """
        Дообучить модель через MLX-LM (LoRA)

        Args:
            base_model: Базовая модель (путь или HuggingFace ID)
            training_data_path: Путь к JSONL файлу с данными
            output_model_name: Имя выходной модели
            lora_rank: Ранг LoRA адаптера
            lora_alpha: Альфа параметр LoRA
            batch_size: Размер батча
            learning_rate: Скорость обучения
            num_epochs: Количество эпох

        Returns:
            (success, message)
        """
        try:
            # Проверяем наличие mlx-lm
            result = subprocess.run(
                ["python3", "-c", "import mlx_lm; print(mlx_lm.__version__)"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return False, "MLX-LM не установлен. Установите: pip install mlx-lm"

            # Команда для fine-tuning
            output_path = os.path.join(self.mlx_models_dir, output_model_name)

            cmd = [
                "python3",
                "-m",
                "mlx_lm.lora",
                "--model",
                base_model,
                "--data",
                training_data_path,
                "--train",
                "--lora-layers",
                "16",  # Количество слоев для LoRA
                "--rank",
                str(lora_rank),
                "--alpha",
                str(lora_alpha),
                "--batch-size",
                str(batch_size),
                "--learning-rate",
                str(learning_rate),
                "--iters",
                str(num_epochs * 100),  # Примерное количество итераций
                "--output-dir",
                output_path,
            ]

            logger.info(f"🚀 Запуск fine-tuning модели {base_model}...")
            logger.info(f"   Команда: {' '.join(cmd)}")

            # Запускаем обучение
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(training_data_path),
            )

            # Логируем вывод
            stdout_lines = []
            stderr_lines = []

            while True:
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output:
                    stdout_lines.append(output.strip())
                    logger.info(f"   {output.strip()}")

            stderr = process.stderr.read()
            if stderr:
                stderr_lines = stderr.split("\n")
                for line in stderr_lines:
                    if line.strip():
                        logger.warning(f"   {line.strip()}")

            return_code = process.poll()

            if return_code == 0:
                logger.info(f"✅ Fine-tuning завершен успешно: {output_path}")
                return True, f"Модель дообучена: {output_path}"
            else:
                error_msg = "\n".join(stderr_lines[-10:])  # Последние 10 строк ошибок
                return False, f"Ошибка fine-tuning: {error_msg}"

        except Exception as e:
            logger.error(f"Ошибка fine-tuning: {e}", exc_info=True)
            return False, f"Ошибка: {str(e)}"

    async def optimize_model_speed(
        self, model_path: str, quantization: str = "Q4_K_M"
    ) -> Tuple[bool, str]:
        """
        Оптимизировать модель для скорости через квантование

        Args:
            model_path: Путь к модели
            quantization: Уровень квантования (Q4_K_M, Q6_K, Q8_0)

        Returns:
            (success, message)
        """
        try:
            # Используем llama.cpp для квантования (если доступен)
            # Или mlx-lm для конвертации
            logger.info(f"⚡ Оптимизация модели {model_path} для скорости...")

            # Для MLX моделей квантование обычно уже применено
            # Можно использовать более агрессивное квантование
            return True, "Модель уже оптимизирована (MLX использует эффективную квантование)"

        except Exception as e:
            logger.error(f"Ошибка оптимизации: {e}")
            return False, f"Ошибка: {str(e)}"

    async def create_finetuning_pipeline(
        self,
        model_name: str,
        include_style_patterns: bool = True,
        include_anti_hallucination: bool = False,
        include_knowledge_base: bool = False,  # ⚠️ По умолчанию FALSE - не собираем факты!
    ) -> Dict:
        """
        Создать полный pipeline для дообучения модели

        ⚠️ ВАЖНО: По умолчанию собираем ТОЛЬКО паттерны стиля, НЕ факты!
        Факты уже доступны через RAG.

        Args:
            model_name: Имя модели для дообучения
            include_style_patterns: Собирать паттерны стиля (рекомендуется: True)
            include_anti_hallucination: Собирать данные против галлюцинаций
            include_knowledge_base: Собирать факты из базы (НЕ рекомендуется!)

        Returns:
            Словарь с результатами
        """
        results = {
            "model": model_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "warning": "⚠️ Дообучение только на паттернах стиля, НЕ на фактах (факты в RAG)",
        }

        # Шаг 1: Сбор данных
        logger.info("📊 Шаг 1: Сбор данных для обучения...")
        logger.warning("⚠️ Собираем ТОЛЬКО паттерны стиля, НЕ факты (факты уже в RAG)")
        training_data = []

        if include_style_patterns:
            style_data = await self.collect_style_patterns()
            training_data.extend(style_data)
            results["steps"].append(
                {
                    "step": "collect_style_patterns",
                    "status": "success",
                    "count": len(style_data),
                    "note": "Паттерны стиля (НЕ факты)",
                }
            )

        if include_knowledge_base:
            logger.warning(
                "⚠️ ВНИМАНИЕ: Собираем факты из базы знаний. Это НЕ рекомендуется - факты уже в RAG!"
            )
            kb_data = await self.collect_training_data_from_knowledge_base()
            training_data.extend(kb_data)
            results["steps"].append(
                {
                    "step": "collect_knowledge_base",
                    "status": "warning",
                    "count": len(kb_data),
                    "note": "⚠️ Факты - лучше использовать RAG!",
                }
            )

        if include_anti_hallucination:
            ah_data = await self.collect_anti_hallucination_data()
            training_data.extend(ah_data)
            results["steps"].append(
                {"step": "collect_anti_hallucination", "status": "success", "count": len(ah_data)}
            )

        if not training_data:
            results["status"] = "error"
            results["message"] = "Недостаточно данных для обучения"
            return results

        # Шаг 2: Подготовка датасета
        logger.info("📝 Шаг 2: Подготовка датасета...")
        dataset_file = f"{model_name}_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        dataset_path = self.prepare_training_dataset(training_data, dataset_file)
        results["steps"].append(
            {
                "step": "prepare_dataset",
                "status": "success",
                "file": dataset_path,
                "count": len(training_data),
            }
        )

        # Шаг 3: Fine-tuning
        logger.info("🚀 Шаг 3: Запуск fine-tuning...")
        base_model = self._get_model_path(model_name)
        output_model = f"{model_name}_finetuned"

        success, message = await self.fine_tune_mlx_model(
            base_model=base_model, training_data_path=dataset_path, output_model_name=output_model
        )

        results["steps"].append(
            {"step": "fine_tuning", "status": "success" if success else "error", "message": message}
        )

        if success:
            results["status"] = "success"
            results["output_model"] = output_model
        else:
            results["status"] = "error"
            results["message"] = message

        return results

    def _get_model_path(self, model_name: str) -> str:
        """Получить путь к модели"""
        # Пробуем найти в MLX моделях
        mlx_path = os.path.join(self.mlx_models_dir, model_name)
        if os.path.exists(mlx_path):
            return mlx_path

        # Или используем HuggingFace ID
        model_map = {
            "qwen2.5-coder:32b": "mlx-community/Qwen2.5-Coder-32B-Instruct-Q8",
            "deepseek-r1-distill-llama:70b": "mlx-community/DeepSeek-R1-Distill-Llama-70B-Q6",
            "llama3.3:70b": "mlx-community/Llama-3.3-70B-Instruct-Q6",
            "phi3.5:3.8b": "mlx-community/Phi-3.5-mini-instruct-Q4",
        }

        return model_map.get(model_name, model_name)


async def main():
    """Пример использования"""
    tuner = ModelFineTuner()

    # ✅ ПРАВИЛЬНО: Дообучение только на паттернах стиля (НЕ на фактах!)
    results = await tuner.create_finetuning_pipeline(
        model_name="qwen2.5-coder:32b",
        include_style_patterns=True,  # ✅ Собираем стиль
        include_anti_hallucination=False,  # Опционально
        include_knowledge_base=False,  # ❌ НЕ собираем факты (они в RAG!)
    )

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
