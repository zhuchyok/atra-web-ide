"""
Early Warning System
Система раннего предупреждения о потенциальных проблемах
AGENT IMPROVEMENTS: Система раннего предупреждения
"""

import asyncio
import logging
import os
import json
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

# Уведомления: Telegram и Email (опционально)
EARLY_WARNING_TELEGRAM_TOKEN = os.getenv('EARLY_WARNING_TELEGRAM_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
EARLY_WARNING_TELEGRAM_CHAT_ID = os.getenv('EARLY_WARNING_TELEGRAM_CHAT_ID')
EARLY_WARNING_EMAIL_TO = os.getenv('EARLY_WARNING_EMAIL_TO')
SMTP_HOST = os.getenv('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.getenv('SMTP_PORT', '25'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

class WarningSeverity(Enum):
    """Уровень серьезности предупреждения"""
    CRITICAL = "critical"  # Требует немедленного внимания
    HIGH = "high"          # Высокий приоритет
    MEDIUM = "medium"      # Средний приоритет
    LOW = "low"            # Низкий приоритет

@dataclass
class EarlyWarning:
    """Раннее предупреждение"""
    warning_id: str
    warning_type: str  # 'win_rate_drop', 'overfitting', 'liquidity_risk', etc.
    severity: WarningSeverity
    description: str
    predicted_impact: str  # Описание потенциального воздействия
    confidence: float  # Уверенность в предсказании (0.0-1.0)
    suggested_actions: List[str]  # Рекомендуемые действия
    detected_at: datetime
    metadata: Dict[str, Any]

class EarlyWarningSystem:
    """
    Система раннего предупреждения.
    
    Функционал:
    - ML-модели для предсказания проблем (падение Win Rate, переобучение)
    - Ранние алерты о потенциальных рисках
    - Проактивные действия для предотвращения
    - Система эскалации (критичные проблемы → человек)
    - Метрики успешности предсказаний
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._warning_cache: Dict[str, EarlyWarning] = {}
        self._prediction_models: Dict[str, Any] = {}  # Кэш для ML моделей
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка подключения к БД: {e}")
            return None
    
    async def predict_win_rate_drop(self, lookback_days: int = 7) -> Optional[EarlyWarning]:
        """
        Предсказывает падение Win Rate на основе трендов.
        
        Args:
            lookback_days: Количество дней для анализа
        
        Returns:
            EarlyWarning или None
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем историю Win Rate за последние дни
                rows = await conn.fetch("""
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) FILTER (WHERE result = 'WIN') * 100.0 / COUNT(*) as win_rate
                    FROM signals_log
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """ % lookback_days)
                
                if len(rows) < 3:
                    return None
                
                # Анализируем тренд
                win_rates = [float(row['win_rate']) for row in rows[:7]]  # Последние 7 дней
                recent_avg = sum(win_rates[:3]) / 3  # Среднее за последние 3 дня
                older_avg = sum(win_rates[3:]) / len(win_rates[3:]) if len(win_rates) > 3 else recent_avg
                
                # Если падение > 10%
                drop_pct = (older_avg - recent_avg) / older_avg if older_avg > 0 else 0
                
                if drop_pct > 0.10:  # Падение > 10%
                    severity = WarningSeverity.CRITICAL if drop_pct > 0.20 else WarningSeverity.HIGH
                    confidence = min(drop_pct * 2, 1.0)  # Чем больше падение, тем выше уверенность
                    
                    warning = EarlyWarning(
                        warning_id=f"win_rate_drop_{int(datetime.now(timezone.utc).timestamp())}",
                        warning_type="win_rate_drop",
                        severity=severity,
                        description=f"Обнаружено падение Win Rate на {drop_pct*100:.1f}% за последние {lookback_days} дней",
                        predicted_impact="Снижение прибыльности стратегии, возможные убытки",
                        confidence=confidence,
                        suggested_actions=[
                            "Проверить качество сигналов",
                            "Пересмотреть параметры фильтров",
                            "Проверить переобучение ML модели",
                            "Анализ рыночных условий"
                        ],
                        detected_at=datetime.now(timezone.utc),
                        metadata={
                            'recent_avg': recent_avg,
                            'older_avg': older_avg,
                            'drop_pct': drop_pct
                        }
                    )
                    
                    logger.warning(f"⚠️ [EARLY WARNING] {warning.description}")
                    return warning
                
                return None
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка предсказания Win Rate: {e}")
            return None
    
    async def predict_overfitting(self) -> Optional[EarlyWarning]:
        """
        Предсказывает переобучение ML модели.
        
        Returns:
            EarlyWarning или None
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Проверяем метрики модели (если есть таблица model_metrics)
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'model_metrics'
                    )
                """)
                
                if not table_exists:
                    return None
                
                # Получаем последние метрики
                metrics = await conn.fetchrow("""
                    SELECT 
                        train_accuracy,
                        test_accuracy,
                        train_auc,
                        test_auc,
                        created_at
                    FROM model_metrics
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                if not metrics:
                    return None
                
                train_acc = float(metrics['train_accuracy'] or 0)
                test_acc = float(metrics['test_accuracy'] or 0)
                train_auc = float(metrics['train_auc'] or 0)
                test_auc = float(metrics['test_auc'] or 0)
                
                # Проверяем признаки переобучения
                # 1. Большая разница между train и test accuracy
                acc_gap = train_acc - test_acc
                # 2. Большая разница между train и test AUC
                auc_gap = train_auc - test_auc
                
                if acc_gap > 0.15 or auc_gap > 0.15:  # Разница > 15%
                    severity = WarningSeverity.HIGH if acc_gap > 0.25 else WarningSeverity.MEDIUM
                    confidence = min((acc_gap + auc_gap) / 2, 1.0)
                    
                    warning = EarlyWarning(
                        warning_id=f"overfitting_{int(datetime.now(timezone.utc).timestamp())}",
                        warning_type="overfitting",
                        severity=severity,
                        description=f"Обнаружены признаки переобучения: разница train/test accuracy = {acc_gap:.2%}",
                        predicted_impact="Снижение качества предсказаний на новых данных",
                        confidence=confidence,
                        suggested_actions=[
                            "Увеличить регуляризацию",
                            "Уменьшить сложность модели",
                            "Увеличить размер обучающей выборки",
                            "Использовать кросс-валидацию"
                        ],
                        detected_at=datetime.now(timezone.utc),
                        metadata={
                            'train_accuracy': train_acc,
                            'test_accuracy': test_acc,
                            'accuracy_gap': acc_gap,
                            'train_auc': train_auc,
                            'test_auc': test_auc,
                            'auc_gap': auc_gap
                        }
                    )
                    
                    logger.warning(f"⚠️ [EARLY WARNING] {warning.description}")
                    return warning
                
                return None
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка предсказания переобучения: {e}")
            return None
    
    async def predict_liquidity_risk(self) -> Optional[EarlyWarning]:
        """
        Предсказывает риски ликвидности.
        
        Returns:
            EarlyWarning или None
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем статистику по ликвидности (если есть таблица liquidity_metrics)
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'liquidity_metrics'
                    )
                """)
                
                if not table_exists:
                    return None
                
                # Анализируем тренд ликвидности
                rows = await conn.fetch("""
                    SELECT 
                        DATE(created_at) as date,
                        AVG(spread_pct) as avg_spread,
                        AVG(volume_24h) as avg_volume
                    FROM liquidity_metrics
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
                
                if len(rows) < 3:
                    return None
                
                recent_spread = float(rows[0]['avg_spread'] or 0)
                older_spread = float(rows[-1]['avg_spread'] or 0) if len(rows) > 1 else recent_spread
                
                # Если спред увеличился > 50%
                spread_increase = (recent_spread - older_spread) / older_spread if older_spread > 0 else 0
                
                if spread_increase > 0.5:  # Увеличение > 50%
                    severity = WarningSeverity.HIGH if spread_increase > 1.0 else WarningSeverity.MEDIUM
                    confidence = min(spread_increase, 1.0)
                    
                    warning = EarlyWarning(
                        warning_id=f"liquidity_risk_{int(datetime.now(timezone.utc).timestamp())}",
                        warning_type="liquidity_risk",
                        severity=severity,
                        description=f"Обнаружен рост спреда на {spread_increase*100:.1f}% - риск ликвидности",
                        predicted_impact="Увеличение проскальзывания, сложность исполнения ордеров",
                        confidence=confidence,
                        suggested_actions=[
                            "Проверить ликвидность монет",
                            "Увеличить минимальный объем для торговли",
                            "Исключить монеты с низкой ликвидностью"
                        ],
                        detected_at=datetime.now(timezone.utc),
                        metadata={
                            'recent_spread': recent_spread,
                            'older_spread': older_spread,
                            'spread_increase': spread_increase
                        }
                    )
                    
                    logger.warning(f"⚠️ [EARLY WARNING] {warning.description}")
                    return warning
                
                return None
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка предсказания ликвидности: {e}")
            return None
    
    async def check_all_warnings(self) -> List[EarlyWarning]:
        """
        Проверяет все типы предупреждений.
        
        Returns:
            Список предупреждений
        """
        warnings = []
        
        # Проверяем Win Rate
        win_rate_warning = await self.predict_win_rate_drop()
        if win_rate_warning:
            warnings.append(win_rate_warning)
        
        # Проверяем переобучение
        overfitting_warning = await self.predict_overfitting()
        if overfitting_warning:
            warnings.append(overfitting_warning)
        
        # Проверяем ликвидность
        liquidity_warning = await self.predict_liquidity_risk()
        if liquidity_warning:
            warnings.append(liquidity_warning)
        
        return warnings
    
    async def save_warning(self, warning: EarlyWarning) -> bool:
        """
        Сохраняет предупреждение в БД.
        
        Args:
            warning: EarlyWarning
        
        Returns:
            True если сохранение успешно
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'early_warnings'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO early_warnings (warning_id, warning_type, severity, description, predicted_impact, confidence, suggested_actions, detected_at, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (warning_id) DO UPDATE
                        SET severity = EXCLUDED.severity, confidence = EXCLUDED.confidence
                    """, warning.warning_id, warning.warning_type, warning.severity.value, warning.description, warning.predicted_impact, warning.confidence, json.dumps(warning.suggested_actions), warning.detected_at, json.dumps(warning.metadata))
                
                # Обновляем кэш
                self._warning_cache[warning.warning_id] = warning
                
                logger.info(f"✅ [EARLY WARNING] Сохранено предупреждение {warning.warning_id}")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка сохранения предупреждения: {e}")
            return False

    async def _send_telegram_alert(self, text: str) -> bool:
        """Отправка в Telegram при заданных EARLY_WARNING_TELEGRAM_BOT_TOKEN и EARLY_WARNING_TELEGRAM_CHAT_ID."""
        if not EARLY_WARNING_TELEGRAM_TOKEN or not EARLY_WARNING_TELEGRAM_CHAT_ID:
            return False
        try:
            import httpx
            url = f"https://api.telegram.org/bot{EARLY_WARNING_TELEGRAM_TOKEN}/sendMessage"
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, json={"chat_id": EARLY_WARNING_TELEGRAM_CHAT_ID, "text": text[:4000]})
            if r.is_success:
                logger.info("✅ [EARLY WARNING] Уведомление отправлено в Telegram")
                return True
            logger.warning("⚠️ [EARLY WARNING] Telegram: %s %s", r.status_code, r.text[:200])
            return False
        except Exception as e:
            logger.debug("EARLY WARNING Telegram: %s", e)
            return False

    async def _send_email_alert(self, subject: str, body: str) -> bool:
        """Отправка по Email при заданном EARLY_WARNING_EMAIL_TO (SMTP_HOST/PORT/USER/PASSWORD опционально)."""
        if not EARLY_WARNING_EMAIL_TO:
            return False
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = SMTP_USER or "early-warning@localhost"
            msg["To"] = EARLY_WARNING_EMAIL_TO
            msg.attach(MIMEText(body, "plain", "utf-8"))
            def _send():
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                    if SMTP_USER and SMTP_PASSWORD:
                        s.starttls()
                        s.login(SMTP_USER, SMTP_PASSWORD)
                    s.sendmail(msg["From"], [EARLY_WARNING_EMAIL_TO], msg.as_string())
            await asyncio.get_event_loop().run_in_executor(None, _send)
            logger.info("✅ [EARLY WARNING] Уведомление отправлено по Email")
            return True
        except Exception as e:
            logger.debug("EARLY WARNING Email: %s", e)
            return False

    async def escalate_critical_warnings(self) -> List[EarlyWarning]:
        """
        Эскалирует критичные предупреждения (отправка человеку).
        
        Returns:
            Список критичных предупреждений
        """
        try:
            # Получаем все критичные предупреждения из кэша или последние из БД
            critical_warnings = [
                w for w in self._warning_cache.values()
                if w.severity == WarningSeverity.CRITICAL
            ]
            
            # Если в кэше пусто, попробуем отправить просто уведомление о работе системы
            if not critical_warnings:
                logger.info("ℹ️ [EARLY WARNING] Нет критичных предупреждений для эскалации")
                return []
                logger.critical(f"🚨 [CRITICAL] {warning.description}")

            # Отправка уведомлений в Telegram и/или Email при настройке env
            if critical_warnings:
                text = "🚨 Early Warning: " + "; ".join(w.description[:200] for w in critical_warnings[:5])
                await self._send_telegram_alert(text)
                await self._send_email_alert("Early Warning: критичные предупреждения", text)

            return critical_warnings
            
        except Exception as e:
            logger.error(f"❌ [EARLY WARNING] Ошибка эскалации: {e}")
            return []

# Singleton instance
_early_warning_instance: Optional[EarlyWarningSystem] = None

def get_early_warning_system(db_url: str = DB_URL) -> EarlyWarningSystem:
    """Получить singleton экземпляр EarlyWarningSystem"""
    global _early_warning_instance
    if _early_warning_instance is None:
        _early_warning_instance = EarlyWarningSystem(db_url=db_url)
    return _early_warning_instance

