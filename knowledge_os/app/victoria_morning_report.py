import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests

# Third-party imports with fallback
try:
    import asyncpg

    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_async, run_smart_agent_sync
except ImportError:  # pragma: no cover

    logging.getLogger(__name__).error(
        "❌ ai_core import failed — AI-генерация доклада будет пустой "
        "(заглушки вместо агентов). Причина:",
        exc_info=True,
    )

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

        async def generate_local_upgrade_report(self):
            return "MOCK_OFFLINE"


try:
    from training_pipeline import LocalTrainingPipeline
except ImportError:

    class LocalTrainingPipeline:
        """Fallback for LocalTrainingPipeline."""

        def trigger_auto_upgrade(self):
            return "MOCK_OFFLINE"


# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки Telegram (из переменных окружения)
TG_TOKEN = (
    os.getenv("PROD_TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_TOKEN", "")
)
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID", "")
_DISTILLER_SINGLETON = None


def _get_distiller_singleton():
    global _DISTILLER_SINGLETON
    if _DISTILLER_SINGLETON is None:
        _DISTILLER_SINGLETON = KnowledgeDistiller()
    return _DISTILLER_SINGLETON


async def get_pool():
    """Lazy initialization of the PostgreSQL connection pool."""
    if not ASYNCPG_AVAILABLE:
        return None
    import getpass

    user_name = getpass.getuser()
    if user_name == "zhuchyok":
        default_url = f"postgresql://{user_name}@localhost:6432/knowledge_os"
    else:
        default_url = "postgresql://admin:secret@localhost:6432/knowledge_os"

    return await asyncpg.create_pool(os.getenv("DATABASE_URL", default_url), min_size=1, max_size=3)


async def run_cursor_agent(prompt: str):
    """Запуск Cursor Agent для генерации контента через умное ядро.
    [v149.2] Очищаем <think> блоки и ReAct-артефакты до возврата.
    [v149.9] Любая ошибка ядра → None (штатный retry/fallback отчёта сработает;
    раньше редкий len(None) в глубине ai_core ронял весь прогон)."""
    import re as _re

    result = None
    try:
        if run_smart_agent_async:
            result = await run_smart_agent_async(prompt, expert_name="Виктория", category="report")
        else:
            result = run_smart_agent_sync(prompt, expert_name="Виктория", category="report")
    except asyncio.CancelledError:
        # [v149.14] В 3.11 CancelledError — BaseException: wait_for-таймауты ядра
        # прилетали сюда и роняли весь прогон. Гасим → штатный retry/fallback.
        logger.warning("run_cursor_agent: отменено (wait_for-таймаут ядра) — None в retry")
        result = None
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("run_cursor_agent: агент упал (%s) — отдаём None в retry/fallback", exc)
        result = None
    # Очистить thinking-блоки (модели начинают с <think>...</think>)
    if result:
        result = _re.sub(r"<think>.*?</think>", "", str(result), flags=_re.DOTALL).strip()
        result = _re.sub(r"</?think>", "", result).strip()
    return result


def send_telegram_msg(msg: str):
    """Отправка сообщения в Telegram, fallback ntfy (Telegram блокируется DPI)."""
    sent = False
    if TG_TOKEN and TG_CHAT_ID:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = {"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        try:
            res = requests.post(url, data=data, timeout=10)
            sent = res.ok
            if not sent:
                data["parse_mode"] = ""
                sent = requests.post(url, data=data, timeout=10).ok
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error sending TG message: %s", exc)
    if not sent:
        try:
            ntfy_url = os.getenv("NTFY_URL", "https://ntfy.sh/atra_victoria_curator")
            requests.post(
                ntfy_url,
                data=msg.encode("utf-8")[:4000],
                headers={"Title": "Morning report: Victoria (ATRA)", "Tags": "sunrise,robot"},
                timeout=10,
            )
            logger.info("Отправлено через ntfy (Telegram недоступен)")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Error sending ntfy: %s", exc)


async def generate_morning_plan():
    """Генерация утреннего доклада с OKR и ROI"""
    logger.info("[%s] Виктория: Генерация утреннего доклада с OKR и ROI...", datetime.now())

    pool = await get_pool()
    if not pool:
        logger.error("❌ Database pool is not available.")
        return

    async with pool.acquire() as conn:
        # 1. Получаем промпт Виктории
        expert = await conn.fetchrow(
            "SELECT system_prompt, role FROM experts WHERE name = 'Виктория'"
        )
        victoria_prompt = (
            expert["system_prompt"]
            if expert
            else "Вы Виктория, Team Lead и Системный Архитектор корпорации ATRA."
        )

        # 2. Собираем финансовые данные
        finance_stats = await conn.fetchrow("""
            SELECT COALESCE(SUM(token_usage), 0) as total_tokens, COALESCE(SUM(cost_usd), 0) as total_cost
            FROM interaction_logs
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)

        # 3. Собираем OKR данные (active period only — не хардкод 2025-Q4)
        from okr_service import (
            ensure_active_okrs_seeded,
            get_active_okr_period,
            refresh_key_results_from_metrics,
        )

        try:
            await ensure_active_okrs_seeded(conn)
            await refresh_key_results_from_metrics(conn)
        except Exception as okr_seed_err:
            logger.warning("OKR seed/refresh skipped: %s", okr_seed_err)

        active_period = get_active_okr_period()
        okrs = await conn.fetch(
            """
            SELECT o.objective, kr.description, kr.current_value, kr.target_value, kr.unit
            FROM okrs o
            JOIN key_results kr ON o.id = kr.okr_id
            WHERE o.period = $1
            ORDER BY o.created_at, kr.description
            """,
            active_period,
        )

        okr_str = ""
        current_obj = ""
        for row in okrs:
            if row["objective"] != current_obj:
                okr_str += f"\n🎯 *{row['objective']}*:\n"
                current_obj = row["objective"]
            progress = (
                (row["current_value"] / row["target_value"] * 100)
                if row["target_value"] != 0
                else 0
            )
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
        roi_str = "\n".join(
            [
                f"💎 [{r['domain']}] {r['content'][:100]}... (использовано {r['usage_count']} раз)"
                for r in top_roi
            ]
        )

        # 5. Собираем свежие знания за ночь
        new_knowledge = await conn.fetch("""
            SELECT content, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.created_at > NOW() - INTERVAL '12 hours'
            ORDER BY k.created_at DESC
            LIMIT 10
        """)

        knowledge_str = "\n".join(
            [f"- [{k['domain']}] {k['content'][:150]}..." for k in new_knowledge]
        )

        # 5.1 Статус дистилляции (SQL-срез — метод report у дистиллятора отсутствует)
        try:
            dr = await conn.fetchrow("""
                SELECT
                    COUNT(*) AS total_24h,
                    COUNT(*) FILTER (WHERE metadata->>'distilled' = 'true') AS distilled_24h,
                    COUNT(*) FILTER (WHERE is_verified = true) AS verified_24h
                FROM knowledge_nodes WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            distillation_report = (
                f"узлов за 24ч: {dr['total_24h']}, дистиллировано: {dr['distilled_24h']}, "
                f"верифицировано: {dr['verified_24h']}"
            )
        except Exception as dr_err:  # pylint: disable=broad-exception-caught
            logger.warning("distill report skipped: %s", dr_err)
            distillation_report = "статус недоступен"
        try:
            upgrade_status = LocalTrainingPipeline().trigger_auto_upgrade()
        except Exception as up_err:  # pylint: disable=broad-exception-caught
            logger.warning("upgrade status skipped: %s", up_err)
            upgrade_status = "статус недоступен"

        # 5.2 [Фаза 4.3] Ночная работа роя / решения совета / error budgets / консилиум
        night_work_str = ""
        board_str = ""
        budget_str = ""
        try:
            night_rows = await conn.fetch("""
                SELECT COALESCE(metadata->>'source', 'other') AS src, COUNT(*) AS cnt
                FROM tasks
                WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '12 hours'
                GROUP BY 1 ORDER BY cnt DESC LIMIT 6
            """)
            night_total = sum(r["cnt"] for r in night_rows)
            night_work_str = (
                ", ".join(f"{r['src']}: {r['cnt']}" for r in night_rows)
                + f" — всего {night_total} за 12ч"
            )
        except Exception as night_err:  # pylint: disable=broad-exception-caught
            logger.warning("night work block skipped: %s", night_err)

        try:
            board_rows = await conn.fetch("""
                SELECT LEFT(COALESCE(directive_text, question, ''), 140) AS d
                FROM board_decisions WHERE created_at > NOW() - INTERVAL '12 hours'
                ORDER BY created_at DESC LIMIT 3
            """)
            board_str = (
                "\n".join(f"- {r['d']}" for r in board_rows)
                if board_rows
                else "Совет директоров за ночь не собирался."
            )
        except Exception as board_err:  # pylint: disable=broad-exception-caught
            logger.warning("board block skipped: %s", board_err)
            board_str = "Статус совета недоступен."

        try:
            from error_budget import check_budget

            budget_lines = []
            for _cycle in ("evolution", "curiosity", "self_check", "nightly"):
                _ok, _left = await check_budget(_cycle)
                budget_lines.append(
                    f"{'🟢' if _ok else '🔴'} {_cycle}: {'осталось ' + str(_left) + ' неудач' if _ok else 'ИСЧЕРПАН — наблюдаемый режим'}"
                )
            budget_str = "\n".join(budget_lines)
        except Exception as eb_err:  # pylint: disable=broad-exception-caught
            logger.warning("budget block skipped: %s", eb_err)
            budget_str = "Error budgets недоступны."

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                m = await client.get("http://localhost:8000/metrics")
            cons_lines = [
                ln
                for ln in m.text.splitlines()
                if ln.startswith("victoria_consilium_routed_total{")
            ]
            consilium_str = "\n".join(cons_lines[-6:]) if cons_lines else "консилиум не вызывался"
        except Exception as cons_err:  # pylint: disable=broad-exception-caught
            logger.warning("consilium block skipped: %s", cons_err)
            consilium_str = "недоступно"

        # 6. Промпт для генерации отчета
        prompt = f"""
        {victoria_prompt}

        ЗАДАЧА: Подготовьте утренний стратегический доклад для Владельца Холдинга.

        💰 ФИНАНСОВЫЙ ИНТЕЛЛЕКТ (за 24ч):
        - Расход токенов: {finance_stats["total_tokens"]:,}
        - Виртуальная стоимость: ${finance_stats["total_cost"]:.4f}

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

        🌙 ЧТО РОЙ СДЕЛАЛ НОЧЬЮ (выполнено за 12ч по источникам):
        {night_work_str or "данных нет"}

        🏛 РЕШЕНИЯ СОВЕТА ДИРЕКТОРОВ (12ч):
        {board_str}

        🚦 ERROR BUDGETS АВТОНОМНЫХ ЦИКЛОВ (неудач осталось до наблюдаемого режима):
        {budget_str}

        ⚔️ КОНСИЛИУМ-РОУТЕР (решений):
        {consilium_str}

        ФОРМАТ ДОКЛАДА:
        1. 💰 Финансовая аналитика: Кратко о затратах и эффективности.
        2. 📊 Статус OKR: Короткий комментарий по прогрессу ключевых целей.
        3. 🌙 Ночная автономия: Что рой сделал сам и какие решения принял совет.
        4. 🚦 Здоровье автономии: Error budgets — где горит, где наблюдаемый режим.
        5. 📉 Ликвидность и ROI: Как наши знания работают на бизнес.
        6. 🚀 Операционный план: Приоритеты для департаментов на сегодня.
        """

        # Пытаемся сгенерировать отчет с таймаутом 60 секунд
        try:
            plan = await asyncio.wait_for(run_cursor_agent(prompt), timeout=480)
            if not (plan and str(plan).strip() and len(str(plan)) > 50):
                # [v149.2] Retry: второй вызов (модель может вернуть пусто с первой попытки)
                plan = await asyncio.wait_for(run_cursor_agent(prompt), timeout=480)
            if plan and str(plan).strip() and len(str(plan)) > 50:
                full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{plan}"
                send_telegram_msg(full_msg)
                logger.info("✅ Доклад Виктории с OKR и ROI успешно отправлен.")
            else:
                raise ValueError("Пустой или слишком короткий ответ от агента (после retry)")
        except asyncio.TimeoutError:
            logger.warning("⏱️ Таймаут генерации отчета (60s), отправляю упрощенный отчет")
            # Fallback: упрощенный отчет без AI генерации
            simple_report = f"""💰 *Финансовая аналитика (за 24ч):*
- Расход токенов: {finance_stats["total_tokens"]:,}
- Виртуальная стоимость: ${finance_stats["total_cost"]:.4f}

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

🌙 *Ночная автономия:*
{night_work_str if night_work_str else "данных нет"}

🏛 *Совет директоров (12ч):*
{board_str if board_str else "не собирался"}

🚦 *Error budgets:*
{budget_str if budget_str else "недоступны"}

⚔️ *Консилиум-роутер:*
{consilium_str if consilium_str else "недоступно"}

_Примечание: Полный AI-доклад недоступен из-за таймаута. Показаны базовые метрики._
"""
            full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{simple_report}"
            send_telegram_msg(full_msg)
            logger.info("✅ Упрощенный доклад Виктории отправлен (fallback)")
        except Exception as e:
            # TODO: Convert f-string to %s formatting for performance
            logger.error(f"❌ Ошибка генерации отчета: {e}", exc_info=True)
            # Отправляем минимальный отчет даже при ошибке
            error_report = f"""💰 *Финансовая аналитика (за 24ч):*
- Расход токенов: {finance_stats["total_tokens"]:,}
- Виртуальная стоимость: ${finance_stats["total_cost"]:.4f}

📊 *Статус OKR:*
{okr_str if okr_str else "OKR данные не найдены"}

⚠️ *Примечание:* Полный AI-доклад недоступен. Показаны базовые метрики.
Ошибка: {str(e)[:100]}
"""
            full_msg = f"👩‍💼 *Утренний доклад Виктории (Team Lead)*\n\n{error_report}"
            send_telegram_msg(full_msg)
            logger.info("✅ Минимальный доклад Виктории отправлен (error fallback)")

    await pool.close()


if __name__ == "__main__":
    # [v149.9] Дедуп: запуск дважды за 10 минут (launchd double-fire) — второй молча выходит
    import time as _time

    _LOCK = "/tmp/victoria_morning_report.lock"
    try:
        if os.path.exists(_LOCK) and _time.time() - os.path.getmtime(_LOCK) < 600:
            logger.warning("Дубль запуска (<10мин с прошлого) — выходим")
            raise SystemExit(0)
        open(_LOCK, "w").close()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        pass
    asyncio.run(generate_morning_plan())
