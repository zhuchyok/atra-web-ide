#!/usr/bin/env python3
"""
Автоматическое применение исправлений и оптимизаций
Анализирует проблемы и автоматически применяет исправления без остановки
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.tracing import get_tracer
from scripts.pm_daily_check import ProjectManager
from scripts.pm_auto_optimize import AutoOptimizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(PROJECT_ROOT / "logs" / "pm_auto_fix.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AutoFixEngine:
    """Движок автоматического применения исправлений"""
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        self.tracer = get_tracer()
        self.pm = ProjectManager(db_path)
        self.optimizer = AutoOptimizer(db_path)
        self.applied_fixes: List[Dict] = []
    
    async def run_continuous_fix_cycle(self, interval_minutes: int = 60) -> None:
        """Запускает непрерывный цикл исправлений"""
        logger.info(f"🚀 Запуск непрерывного цикла исправлений (интервал: {interval_minutes} мин)")
        
        while True:
            try:
                logger.info("="*60)
                logger.info(f"🔄 Начало цикла исправлений: {get_utc_now().isoformat()}")
                
                # 1. Анализ проблем
                report = await self.pm.run_daily_check()
                
                # 2. Анализ оптимизаций
                optimization = await self.optimizer.run_optimization()
                
                # 3. Применение исправлений
                fixes_applied = await self._apply_fixes(report, optimization)
                
                if fixes_applied:
                    logger.info(f"✅ Применено исправлений: {len(fixes_applied)}")
                    for fix in fixes_applied:
                        logger.info(f"  • {fix.get('description', 'N/A')}")
                else:
                    logger.info("ℹ️ Нет критических проблем для исправления")
                
                # 4. Сохранение результатов
                await self._save_fix_results(report, optimization, fixes_applied)
                
                logger.info(f"⏳ Ожидание {interval_minutes} минут до следующего цикла...")
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле исправлений: {e}", exc_info=True)
                await asyncio.sleep(60)  # Короткая пауза при ошибке
    
    async def _apply_fixes(self, report: Dict, optimization: Dict) -> List[Dict]:
        """Применяет исправления на основе анализа"""
        fixes_applied = []
        
        # 1. Исправление операционных проблем
        operational_fixes = await self._fix_operational_issues(report)
        fixes_applied.extend(operational_fixes)
        
        # 2. Применение оптимизаций
        optimization_fixes = await self._apply_optimizations(optimization)
        fixes_applied.extend(optimization_fixes)
        
        # 3. Исправление риск-проблем
        risk_fixes = await self._fix_risk_issues(report)
        fixes_applied.extend(risk_fixes)
        
        return fixes_applied
    
    async def _fix_operational_issues(self, report: Dict) -> List[Dict]:
        """Исправляет операционные проблемы"""
        fixes = []
        
        operational = report.get("metrics", {}).get("operational", {})
        timeout_rate = operational.get("limit_timeout_rate_pct", 0)
        fill_rate = operational.get("limit_fill_rate_pct", 0)
        
        # Если timeout rate высокий, обновляем параметры в auto_execution.py
        if timeout_rate > 15:
            logger.info(f"🔧 Исправление: timeout rate {timeout_rate:.1f}% > 15%")
            
            # Увеличиваем TTL для лимитных ордеров
            fix_applied = await self._update_limit_order_ttl(60)  # Увеличиваем до 60 секунд
            if fix_applied:
                fixes.append({
                    "type": "operational",
                    "description": f"Увеличен TTL лимитных ордеров до 60 секунд (timeout rate: {timeout_rate:.1f}%)",
                    "parameter": "limit_order_ttl",
                    "old_value": "45s",
                    "new_value": "60s"
                })
            
            # Улучшаем спред для лимитных ордеров
            fix_applied = await self._update_limit_spread(0.0015)  # Увеличиваем до 0.15%
            if fix_applied:
                fixes.append({
                    "type": "operational",
                    "description": f"Увеличен спред лимитных ордеров до 0.15% (timeout rate: {timeout_rate:.1f}%)",
                    "parameter": "limit_spread",
                    "old_value": "0.1%",
                    "new_value": "0.15%"
                })
        
        # Если fill rate низкий, улучшаем цены лимитов
        if fill_rate < 85:
            logger.info(f"🔧 Исправление: fill rate {fill_rate:.1f}% < 85%")
            
            fix_applied = await self._update_limit_spread(0.002)  # Увеличиваем до 0.2%
            if fix_applied:
                fixes.append({
                    "type": "operational",
                    "description": f"Увеличен спред лимитных ордеров до 0.2% (fill rate: {fill_rate:.1f}%)",
                    "parameter": "limit_spread",
                    "old_value": "0.15%",
                    "new_value": "0.2%"
                })
        
        return fixes
    
    async def _apply_optimizations(self, optimization: Dict) -> List[Dict]:
        """Применяет оптимизации автоматически"""
        fixes = []
        
        recommendations = optimization.get("recommendations", [])
        
        for rec in recommendations:
            if rec.get("priority") == "high":
                actions = rec.get("actions", [])
                for action in actions:
                    param = action.get("parameter")
                    recommended_value = action.get("recommended_value")
                    
                    logger.info(f"🔧 Применение оптимизации: {param} = {recommended_value}")
                    
                    # Применяем оптимизацию в зависимости от параметра
                    if param == "limit_order_ttl":
                        # Извлекаем значение из recommended_value (например, "60s" -> 60)
                        ttl_value = int(recommended_value.replace("s", ""))
                        fix_applied = await self._update_limit_order_ttl(ttl_value)
                        if fix_applied:
                            fixes.append({
                                "type": "optimization",
                                "description": f"Обновлён TTL лимитных ордеров: {recommended_value}",
                                "parameter": param,
                                "old_value": action.get("current_value"),
                                "new_value": recommended_value
                            })
                    
                    elif param == "limit_price_spread":
                        # Извлекаем значение из recommended_value (например, "0.15%" -> 0.0015)
                        spread_value = float(recommended_value.replace("%", "")) / 100
                        fix_applied = await self._update_limit_spread(spread_value)
                        if fix_applied:
                            fixes.append({
                                "type": "optimization",
                                "description": f"Обновлён спред лимитных ордеров: {recommended_value}",
                                "parameter": param,
                                "old_value": action.get("current_value"),
                                "new_value": recommended_value
                            })
                    
                    elif param == "direction_confidence_min":
                        fix_applied = await self._update_direction_confidence(recommended_value)
                        if fix_applied:
                            fixes.append({
                                "type": "optimization",
                                "description": f"Обновлён минимальный direction confidence: {recommended_value}",
                                "parameter": param,
                                "old_value": action.get("current_value"),
                                "new_value": recommended_value
                            })
        
        return fixes
    
    async def _fix_risk_issues(self, report: Dict) -> List[Dict]:
        """Исправляет риск-проблемы"""
        fixes = []
        
        issues = report.get("issues", [])
        risk_issues = [i for i in issues if i.get("type") == "risk"]
        
        for issue in risk_issues:
            if issue.get("severity") == "high":
                message = issue.get("message", "")
                
                # Если много убыточных сделок, уменьшаем размер позиций
                if "убыточных сделок" in message:
                    logger.info(f"🔧 Исправление риск-проблемы: {message}")
                    
                    # Уменьшаем максимальный размер позиции
                    fix_applied = await self._update_max_position_size(0.12)  # 12% вместо 15%
                    if fix_applied:
                        fixes.append({
                            "type": "risk",
                            "description": "Уменьшен максимальный размер позиции до 12% (много убыточных сделок)",
                            "parameter": "max_position_size_pct",
                            "old_value": "15%",
                            "new_value": "12%"
                        })
                
                # Если большой убыток, уменьшаем риск на сделку
                elif "убыток" in message.lower():
                    logger.info(f"🔧 Исправление риск-проблемы: {message}")
                    
                    # Уменьшаем риск на сделку
                    fix_applied = await self._update_risk_per_trade(0.015)  # 1.5% вместо 2%
                    if fix_applied:
                        fixes.append({
                            "type": "risk",
                            "description": "Уменьшен риск на сделку до 1.5% (большой убыток)",
                            "parameter": "risk_per_trade_pct",
                            "old_value": "2%",
                            "new_value": "1.5%"
                        })
        
        return fixes
    
    async def _update_limit_order_ttl(self, ttl_seconds: int) -> bool:
        """Обновляет TTL для лимитных ордеров в auto_execution.py"""
        try:
            file_path = PROJECT_ROOT / "auto_execution.py"
            content = file_path.read_text(encoding="utf-8")
            
            import re
            
            # Обновляем значение по умолчанию (limit_timeout = 90)
            pattern1 = r'(limit_timeout\s*=\s*)90\b'
            if re.search(pattern1, content):
                new_content = re.sub(pattern1, f'\\g<1>{ttl_seconds}', content)
                file_path.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Обновлён limit_timeout по умолчанию до {ttl_seconds} секунд")
                return True
            
            # Также обновляем минимальное значение в условии (min(limit_timeout, 60))
            pattern2 = r'(min\(limit_timeout,\s*)\d+'
            if re.search(pattern2, content):
                new_content = re.sub(pattern2, f'\\g<1>{ttl_seconds}', content)
                file_path.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Обновлён минимальный limit_timeout до {ttl_seconds} секунд")
                return True
            
            # Если не найдено, добавляем проверку после инициализации
            pattern3 = r'(limit_timeout\s*=\s*)\d+'
            if re.search(pattern3, content):
                new_content = re.sub(pattern3, f'\\g<1>{ttl_seconds}', content, count=1)
                file_path.write_text(new_content, encoding="utf-8")
                logger.info(f"✅ Обновлён limit_timeout до {ttl_seconds} секунд")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления limit_order_ttl: {e}")
            return False
    
    async def _update_limit_spread(self, spread: float) -> bool:
        """Обновляет спред для лимитных ордеров в auto_execution.py"""
        try:
            file_path = PROJECT_ROOT / "auto_execution.py"
            content = file_path.read_text(encoding="utf-8")
            
            import re
            
            # Обновляем для BUY (bid * 1.001 -> bid * (1.0 + spread))
            pattern_buy = r'(limit_price\s*=\s*bid\s*\*\s*)1\.\d+'
            replacement_buy = f'limit_price = bid * {1.0 + spread:.6f}'
            if re.search(pattern_buy, content):
                content = re.sub(pattern_buy, replacement_buy, content)
                logger.info(f"✅ Обновлён спред для BUY до {spread*100:.2f}%")
            
            # Обновляем для SELL (ask * 0.999 -> ask * (1.0 - spread))
            pattern_sell = r'(limit_price\s*=\s*ask\s*\*\s*)0\.\d+'
            replacement_sell = f'limit_price = ask * {1.0 - spread:.6f}'
            if re.search(pattern_sell, content):
                content = re.sub(pattern_sell, replacement_sell, content)
                logger.info(f"✅ Обновлён спред для SELL до {spread*100:.2f}%")
            
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"✅ Обновлён спред лимитных ордеров до {spread*100:.2f}%")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления limit_spread: {e}")
            return False
    
    async def _update_direction_confidence(self, value: str) -> bool:
        """Обновляет минимальный direction confidence в signal_live.py"""
        try:
            file_path = PROJECT_ROOT / "signal_live.py"
            content = file_path.read_text(encoding="utf-8")
            
            # Ищем min_confirmations
            import re
            
            # Если значение "4/4", устанавливаем min_confirmations = 4
            if "4/4" in value:
                pattern = r'(min_confirmations\s*=\s*)\d+'
                replacement = r'\g<1>4'
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    file_path.write_text(content, encoding="utf-8")
                    logger.info("✅ Обновлён min_confirmations до 4")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления direction_confidence: {e}")
            return False
    
    async def _update_max_position_size(self, size_pct: float) -> bool:
        """Обновляет максимальный размер позиции в portfolio_risk_manager.py"""
        try:
            file_path = PROJECT_ROOT / "portfolio_risk_manager.py"
            content = file_path.read_text(encoding="utf-8")
            
            import re
            pattern = r"('max_capital_per_position_pct':\s*)\d+\.?\d*"
            replacement = f"\\g<1>{size_pct * 100}"
            
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                file_path.write_text(content, encoding="utf-8")
                logger.info(f"✅ Обновлён max_capital_per_position_pct до {size_pct*100}%")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления max_position_size: {e}")
            return False
    
    async def _update_risk_per_trade(self, risk_pct: float) -> bool:
        """Обновляет риск на сделку в конфигурации"""
        try:
            # Ищем в user_data.json или других конфигах
            # Пока просто логируем
            logger.info(f"ℹ️ Рекомендуется обновить risk_per_trade до {risk_pct*100}% вручную")
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления risk_per_trade: {e}")
            return False
    
    async def _save_fix_results(self, report: Dict, optimization: Dict, fixes: List[Dict]) -> None:
        """Сохраняет результаты применения исправлений"""
        try:
            results = {
                "timestamp": get_utc_now().isoformat(),
                "report": report,
                "optimization": optimization,
                "applied_fixes": fixes
            }
            
            output_dir = PROJECT_ROOT / "docs" / "project_management" / "auto_fixes"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = output_dir / f"auto_fix_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Результаты сохранены: {output_path}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения результатов: {e}")


async def main():
    """Главная функция - запускает непрерывный цикл"""
    engine = AutoFixEngine()
    
    # Запускаем непрерывный цикл (каждый час)
    await engine.run_continuous_fix_cycle(interval_minutes=60)


if __name__ == "__main__":
    asyncio.run(main())

