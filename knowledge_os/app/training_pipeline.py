import os
import json
import subprocess
import logging

logger = logging.getLogger(__name__)

DISTILLATION_DATASET_PATH = "/Users/zhuchyok/Documents/GITHUB/atra/atra/ai_learning_data/distillation_dataset.jsonl"
MODEL_PATH = "/Users/zhuchyok/Documents/GITHUB/atra/atra/ai_learning_data/local_model_v1"
BASE_MODEL = "mlx-community/Llama-3-8B-Instruct-4bit"

class LocalTrainingPipeline:
    """
    Pipeline to trigger local model fine-tuning on Apple Silicon (MLX).
    This is the "Singularity Actuator" for L1.
    """
    
    def check_readiness(self, threshold: int = 1000):
        """Check if we have enough data to trigger fine-tuning."""
        if not os.path.exists(DISTILLATION_DATASET_PATH):
            return False, 0
            
        count = 0
        with open(DISTILLATION_DATASET_PATH, 'r', encoding='utf-8') as f:
            for _ in f: count += 1
            
        return count >= threshold, count

    def get_tuning_command(self):
        """Returns the command to run on MacBook for MLX fine-tuning."""
        # Using mlx-lm library for Apple Silicon
        cmd = f"python -m mlx_lm.lora --model {BASE_MODEL} --train --data {os.path.dirname(DISTILLATION_DATASET_PATH)} --iters 1000"
        return cmd

    def trigger_auto_upgrade(self):
        """
        Attempts to trigger fine-tuning if running on MacBook.
        """
        ready, count = self.check_readiness()
        if not ready:
            return f"⌛ Недостаточно данных для апгрейда ({count}/1000)."
            
        cmd = self.get_tuning_command()
        
        import platform
        if platform.system() == "Darwin":
            # AUTONOMOUS ACTION: Trigger training in a separate background process
            try:
                # We use nohup to keep it running even if this script ends
                logfile = f"/Users/zhuchyok/Documents/GITHUB/atra/atra/logs/training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                os.makedirs(os.path.dirname(logfile), exist_ok=True)
                
                # Check if already training
                check_cmd = "pgrep -f mlx_lm.lora"
                result = subprocess.run(check_cmd, shell=True, capture_output=True)
                if result.returncode == 0:
                    return "⏳ Процесс обучения уже запущен в фоне."

                full_cmd = f"nohup {cmd} > {logfile} 2>&1 &"
                subprocess.Popen(full_cmd, shell=True)
                
                return f"🔥 **АВТОНОМНЫЙ АПГРЕЙД ЗАПУЩЕН!**\nСобрано {count} эталонов. Обучение идет в фоне. Лог: `{logfile}`"
            except Exception as e:
                return f"❌ Ошибка авто-запуска обучения: {e}. Требуется ручной запуск: `{cmd}`"
        else:
            return f"📡 **ДАННЫЕ ГОТОВЫ ({count} шт).**\nПеренеси датасет на MacBook и запусти обучение:\n`{cmd}`"

from datetime import datetime

if __name__ == "__main__":
    pipeline = LocalTrainingPipeline()
    print(pipeline.trigger_auto_upgrade())

