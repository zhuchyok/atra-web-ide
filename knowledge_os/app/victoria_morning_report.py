import asyncio
import os
import json
import logging
import requests
from datetime import datetime
from typing import Optional

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_sync, run_smart_agent_async
except ImportError:
    def run_smart_agent_sync(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_sync."""
        return None

    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

try:
    from distillation_engine import KnowledgeDistiller
except ImportError:
    class KnowledgeDistiller:
        """Fallback for KnowledgeDistiller."""
        async def generate_local_upgrade_report(self): return "MOCK_OFFLINE"

try:
    from training_pipeline import LocalTrainingPipeline
except ImportError:
    class LocalTrainingPipeline:
        """Fallback for LocalTrainingPipeline."""
        def trigger_auto_upgrade(self): return "MOCK_OFFLINE"

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки Telegram (из переменных окружения)
TG_TOKEN = os.getenv("PROD_TELEGRAM_TOKEN", "8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", '556251171')

async def get_pool():
    """Lazy initialization of the PostgreSQL connection pool."""
    if not ASYNCPG_AVAILABLE:
        return None
    import getpass
    user_name = getpass.getuser()
    if user_name == 'zhuchyok':
        default_url = f'postgresql://{user_name}@localhost:5432/knowledge_os'
    else:
        default_url = 'postgresql://admin:secret@localhost:5432/knowledge_os'
    
    return await asyncpg.create_pool(
        os.getenv('DATABASE_URL', default_url),
        min_size=1,
        max_size=3
    )

async def run_cursor_agent(prompt: str):
    """Запуск Cursor Agent для генерации контента через умное ядро"""
    if run_smart_agent_async:
        return await run_smart_agent_async(prompt, expert_name="Виктория", category="report")
    return run_smart_agent_sync(prompt, expert_name="Виктория", category="report")

def send_telegram_msg(msg: str):
    """Отправка сообщения в Telegram"""
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    data = {'chat_id': TG_CHAT_ID, 'text': msg, 'parse_mode': 'Markdown'}
    try:
        res = requests.post(url, data=data, timeout=10)
        if not res.ok:
            data['parse_mode'] = ''
            requests.post(url, data=data, timeout=10)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("Error sending TG message: %s", exc)

async def generate_morning_plan():
    """Генерация утреннего доклада с OKR и ROI"""
    logger.info("[%s] Виктория: Генерация утреннего доклада с OKR и ROI...", datetime.now())
    
    pool = await get_pool()
    if not pool:
        logger.error("❌ Database pool is not available.")
        return
    
    async with pool.acquire() as conn:
        # 1. Получаем промпт Виктории
        expert = await conn.fetchrow("SELECT system_prompt, role FROM experts WHERE name = 'Виктория'")
        victoria_prompt = expert['system_prompt'] if expert else "Вы Виктория, Team Lead и Системный Архитектор корпорации ATRA."

        # 2. Собираем финансовые данные
        finance_stats = await conn.fetchrow("""
            SELECT COALESCE(SUM(token_usage), 0) as total_tokens, COALESCE(SUM(cost_usd), 0) as total_cost 
            FROM interaction_logs 
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        
        # 3. Собираем OKR данные
        okrs = await conn.fetch("""
            SELECT o.objective, kr.description, kr.current_value, kr.target_value, kr.unit
            FROM okrs o
            JOIN key_results kr ON o.id = kr.okr_id
            WHERE o.period = '2025-Q4'
        """)
        
        okr_str = ""
        current_obj = ""
        for row in okrs:
            if row['objective'] != current_obj:
                okr_str += f"\n🎯 *{row['objective']}*:\n"
                current_obj = row['objective']
            progress = (row['current_value'] / row['target_value'] * 100) if row['target_value'] != 0 else 0
            okr_str += f"  - {row['description']}: {row['current_value']}/{row['target_value']} {row['unit']} ({progress:.1f}%)\n"

        # 4. Собираем данные о ликвидности знаний (ROI)
        top_roi = await conn.fetch("""
            SELECT k.content, d.name as domain, k.usage_count
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.usage_count > 0
            ORDER BY (k.usage_count * k.confidence_score) DESC
            LIMIT 3
        """)
        roi_str = "\n".join([f"💎 [{r['domain']}] {r['content'][:100]}... (использовано {r['usage_count']} раз)" for r in top_roi])

        # 5. Собираем свежие знания за ночь
        new_knowledge = await conn.fetch("""
            SELECT content, d.name as domain 
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.created_at > NOW() - INTERVAL '12 hours'
            ORDER BY k.created_at DESC
            LIMIT 10
        """)
        
        knowledge_str = "\n".join([f"- [{k['domain']}] {k['content'][:150]}..." for k in new_knowledge])
        
        # 5.1 Собираем статус дистилляции и готовность модели
        distiller = KnowledgeDistiller()
        distillation_report = await distiller.generate_local_upgrade_report()
        pipeline = LocalTrainingPipeline()
        upgrade_status = pipeline.trigger_auto_upgrade()
        
        # 6. Промпт для генерации отчета
        prompt = f"""
        {victoria_prompt}
        
        ЗАДАЧА: Подготовьте утренний стратегический доклад для Владельца Холдинга.
        
        💰 ФИНАНСОВЫЙ ИНТЕЛЛЕКТ (за 24ч):
        - Расход токенов: {finance_stats['total_tokens']:,}
        - Виртуальная стоимость: ${finance_stats['total_cost']:.4f}
        
        📈 СТАТУС ЛОКАЛЬНОГО ОБУЧЕНИЯ (Дистилляция):
        {distillation_report}
        
        🚀 ГОТОВНОСТЬ К АПГРЕЙДУ МОДЕЛИ:
        {upgrade_status}
        
        ТЕКУЩИЕ OKR И ПРОГРЕСС:
        {okr_str}
        
        ЛИКВИДНОСТЬ ЗНАНИЙ (Самые полезные активы):
        {roi_str if roi_str else "Данные о ликвидности накапливаются."}
        
        ОСНОВА ДЛЯ ДОКЛАДА (Новые знания корпорации за ночь):
        {knowledge_str if knowledge_str else "За ночь новых критических узлов знаний не добавлено."}
        
        ФОРМАТ ДОКЛАДА:
        1. 💰 Финансовая аналитика: Кратко о затратах и эффективности.
        2. 📊 Статус OKR: Короткий комментарий по прогрессу ключевых целей.
        3. 📉 Ликвидность и ROI: Как наши знания работают на бизнес.
        4. 🧠 Интеллектуальный аудит: Краткий обзор самых важных находок ночного обучения.
        5. 🧬 Эволюция L1: Комментарий по прогрессу дистилляции знаний для локальной модели.
        6. 🚀 Операционный план: Приоритеты для департаментов на сегодня.
        """

        # Пытаемся сгенерировать отчет с таймаутом 60 секунд
        try:
            plan = await asyncio.wait_for(run_cursor_agent(prompt), timeout=60)
            if plan and str(plan).strip() and len(str(plan)) > 50:
                full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{plan}"
                send_telegram_msg(full_msg)
                logger.info("✅ Доклад Виктории с OKR и ROI успешно отправлен.")
            else:
                raise ValueError("Пустой или слишком короткий ответ от агента")
        except asyncio.TimeoutError:
            logger.warning("⏱️ Таймаут генерации отчета (60s), отправляю упрощенный отчет")
            # Fallback: упрощенный отчет без AI генерации
            simple_report = f"""💰 *Финансовая аналитика (за 24ч):*
- Расход токенов: {finance_stats['total_tokens']:,}
- Виртуальная стоимость: ${finance_stats['total_cost']:.4f}

📊 *Статус OKR:*
{okr_str if okr_str else "OKR данные не найдены"}

📉 *Ликвидность знаний (Топ-3):*
{roi_str if roi_str else "Данные о ликвидности накапливаются"}

🧠 *Новые знания за ночь:*
{knowledge_str if knowledge_str else "За ночь новых критических узлов знаний не добавлено"}

📈 *Статус локального обучения:*
{distillation_report if distillation_report else "Статус недоступен"}

🚀 *Готовность к апгрейду:*
{upgrade_status if upgrade_status else "Статус недоступен"}

_Примечание: Полный AI-доклад недоступен из-за таймаута. Показаны базовые метрики._
"""
            full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{simple_report}"
            send_telegram_msg(full_msg)
            logger.info("✅ Упрощенный доклад Виктории отправлен (fallback)")
        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета: {e}", exc_info=True)
            # Отправляем минимальный отчет даже при ошибке
            error_report = f"""💰 *Финансовая аналитика (за 24ч):*
- Расход токенов: {finance_stats['total_tokens']:,}
- Виртуальная стоимость: ${finance_stats['total_cost']:.4f}

📊 *Статус OKR:*
{okr_str if okr_str else "OKR данные не найдены"}

⚠️ *Примечание:* Полный AI-доклад недоступен. Показаны базовые метрики.
Ошибка: {str(e)[:100]}
"""
            full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{error_report}"
            send_telegram_msg(full_msg)
            logger.info("✅ Минимальный доклад Виктории отправлен (error fallback)")

    await pool.close()

if __name__ == '__main__':
    asyncio.run(generate_morning_plan())
