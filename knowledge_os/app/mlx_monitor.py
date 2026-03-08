import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class MLXMonitor:
    """
    Мониторинг производительности MLX: TBT (Time Between Tokens), TPS (Tokens Per Second).
    """
    def __init__(self):
        self.stats = {}
        self.history_limit = 100

    def record_chunk(self, request_id: str):
        """Записать время получения чанка."""
        now = time.time()
        if request_id not in self.stats:
            self.stats[request_id] = {
                "start_time": now,
                "last_chunk_time": now,
                "chunks": 0,
                "tbt_history": []
            }
        
        stat = self.stats[request_id]
        tbt = now - stat["last_chunk_time"]
        if stat["chunks"] > 0:  # Пропускаем первый чанк (время генерации первого токена)
            stat["tbt_history"].append(tbt)
            if len(stat["tbt_history"]) > self.history_limit:
                stat["tbt_history"].pop(0)
        
        stat["last_chunk_time"] = now
        stat["chunks"] += 1

    def get_metrics(self, request_id: str) -> Dict:
        """Получить метрики для конкретного запроса."""
        if request_id not in self.stats:
            return {}
        
        stat = self.stats[request_id]
        total_time = stat["last_chunk_time"] - stat["start_time"]
        avg_tbt = sum(stat["tbt_history"]) / len(stat["tbt_history"]) if stat["tbt_history"] else 0
        tps = stat["chunks"] / total_time if total_time > 0 else 0
        
        return {
            "total_time": total_time,
            "chunks": stat["chunks"],
            "avg_tbt_ms": avg_tbt * 1000,
            "tps": tps
        }

    def finalize_request(self, request_id: str):
        """Завершить мониторинг запроса и вывести итоги."""
        metrics = self.get_metrics(request_id)
        if metrics:
            logger.info(
                "📊 [MLX MONITOR] Request %s: %.2f TPS, avg TBT: %.2fms, total chunks: %d",
                request_id, metrics["tps"], metrics["avg_tbt_ms"], metrics["chunks"]
            )
        self.stats.pop(request_id, None)

_monitor = MLXMonitor()

def get_mlx_monitor():
    return _monitor
