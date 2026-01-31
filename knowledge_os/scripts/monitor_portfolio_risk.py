#!/usr/bin/env python3
"""
Мониторинг корреляционных рисков портфеля
Периодическая проверка и алерты по критическим порогам
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk.correlation_risk import CorrelationRiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Пороги для алертов
ALERT_THRESHOLDS = {
    "max_sol_positions": 8,           # Предупреждение при 8+ позициях
    "max_concurrent_loss": 5,         # Алерт при 5+ убыточных позициях
    "max_drawdown": 12.0,             # Алерт при просадке >12%
    "sol_correlation": 0.85,          # Алерт при корреляции >0.85
    "critical_correlation": 0.9       # Критический алерт при корреляции >0.9
}

# Критические точки остановки
HARD_LIMITS = {
    "max_capital_at_risk": 20.0,      # 10 позиций × 2%
    "max_concurrent_loss": 6,          # Не более 6 убыточных позиций
    "max_drawdown": 15.0,             # Абсолютный стоп-лосс
    "max_sol_correlation": 0.9        # Максимальная корреляция к SOL
}


async def check_portfolio_risks() -> Dict[str, Any]:
    """
    Проверяет риски портфеля и возвращает отчет
    """
    try:
        manager = CorrelationRiskManager()
        await manager._load_signal_history()
        
        # Получаем активные сигналы
        import time
        current_time = int(time.time())
        cooldown = 3600  # 1 час
        
        active_signals = [
            s for s in manager.signal_history_cache
            if (current_time - s.get('timestamp', 0)) < cooldown
        ]
        
        # Проверяем корреляционный риск
        portfolio_risk = await manager.check_portfolio_correlation_risk(active_signals)
        
        # Получаем алерты
        alerts = await manager.get_risk_alerts(active_signals)
        
        # Формируем отчет
        report = {
            'timestamp': datetime.now().isoformat(),
            'portfolio_risk': portfolio_risk,
            'alerts': alerts,
            'active_signals_count': len(active_signals),
            'sol_positions': portfolio_risk['sol_positions_count'],
            'correlation_to_sol': portfolio_risk['correlation_to_sol'],
            'risk_level': portfolio_risk['risk_level'],
            'thresholds': ALERT_THRESHOLDS,
            'hard_limits': HARD_LIMITS
        }
        
        return report
        
    except Exception as e:
        logger.error("❌ Ошибка проверки рисков портфеля: %s", e)
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'portfolio_risk': None,
            'alerts': []
        }


def format_risk_report(report: Dict[str, Any]) -> str:
    """
    Форматирует отчет о рисках для вывода
    """
    lines = [
        "=" * 80,
        "📊 ОТЧЕТ МОНИТОРИНГА РИСКОВ ПОРТФЕЛЯ",
        "=" * 80,
        f"Время: {report.get('timestamp', 'N/A')}",
        ""
    ]
    
    if 'error' in report:
        lines.append(f"❌ Ошибка: {report['error']}")
        return "\n".join(lines)
    
    portfolio_risk = report.get('portfolio_risk', {})
    
    # Основные метрики
    lines.extend([
        "📈 ОСНОВНЫЕ МЕТРИКИ:",
        f"  Активных сигналов: {report.get('active_signals_count', 0)}",
        f"  Позиций в SOL_HIGH: {report.get('sol_positions', 0)}",
        f"  Корреляция к SOL: {report.get('correlation_to_sol', 0.0):.3f}",
        f"  Уровень риска: {report.get('risk_level', 'UNKNOWN')}",
        ""
    ])
    
    # Алерты
    alerts = report.get('alerts', [])
    if alerts:
        lines.append("🚨 АЛЕРТЫ:")
        for alert in alerts:
            level_emoji = {
                'CRITICAL': '🚨',
                'WARNING': '⚠️',
                'INFO': 'ℹ️',
                'ERROR': '❌'
            }.get(alert.get('level', 'INFO'), 'ℹ️')
            
            lines.append(
                f"  {level_emoji} [{alert.get('level', 'INFO')}] {alert.get('message', 'N/A')}"
            )
            if alert.get('action'):
                lines.append(f"     → {alert.get('action')}")
        lines.append("")
    else:
        lines.append("✅ Алертов нет - все в норме")
        lines.append("")
    
    # Проверка критических порогов
    lines.append("🎯 ПРОВЕРКА КРИТИЧЕСКИХ ПОРОГОВ:")
    
    sol_positions = report.get('sol_positions', 0)
    correlation = report.get('correlation_to_sol', 0.0)
    
    # Проверка позиций
    if sol_positions >= ALERT_THRESHOLDS['max_sol_positions']:
        lines.append(f"  ⚠️ Позиций SOL_HIGH: {sol_positions} >= {ALERT_THRESHOLDS['max_sol_positions']} (порог)")
    else:
        lines.append(f"  ✅ Позиций SOL_HIGH: {sol_positions} < {ALERT_THRESHOLDS['max_sol_positions']} (в норме)")
    
    # Проверка корреляции
    if correlation >= HARD_LIMITS['max_sol_correlation']:
        lines.append(f"  🚨 КРИТИЧЕСКАЯ корреляция: {correlation:.3f} >= {HARD_LIMITS['max_sol_correlation']}")
    elif correlation >= ALERT_THRESHOLDS['sol_correlation']:
        lines.append(f"  ⚠️ Высокая корреляция: {correlation:.3f} >= {ALERT_THRESHOLDS['sol_correlation']} (порог)")
    else:
        lines.append(f"  ✅ Корреляция: {correlation:.3f} < {ALERT_THRESHOLDS['sol_correlation']} (в норме)")
    
    lines.append("")
    lines.append("=" * 80)
    
    return "\n".join(lines)


async def main():
    """
    Главная функция мониторинга
    """
    logger.info("🔍 Запуск мониторинга рисков портфеля...")
    
    report = await check_portfolio_risks()
    
    # Выводим отчет
    formatted_report = format_risk_report(report)
    print(formatted_report)
    
    # Сохраняем в файл
    report_file = PROJECT_ROOT / "data" / "reports" / f"risk_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info("✅ Отчет сохранен: %s", report_file)
    
    # Проверяем критические алерты
    critical_alerts = [
        a for a in report.get('alerts', [])
        if a.get('level') == 'CRITICAL'
    ]
    
    if critical_alerts:
        logger.warning("🚨 ОБНАРУЖЕНЫ КРИТИЧЕСКИЕ АЛЕРТЫ!")
        for alert in critical_alerts:
            logger.warning("  %s", alert.get('message'))
        return 1
    
    return 0


if __name__ == "__main__":
    import time
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

