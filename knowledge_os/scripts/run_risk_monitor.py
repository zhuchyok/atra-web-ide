#!/usr/bin/env python3
"""Risk monitor CLI: aggregates metrics, checks Bitget protection and updates flags."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from observability.agent_identity import authorize_agent_action
from observability.guidance import get_guidance
from observability.lm_judge import get_lm_judge
from observability.tracing import get_tracer
from observability.prompt_manager import get_prompt_manager
from observability.context_engine import get_context_engine
from order_audit_log import get_audit_log
from risk_flags_manager import RiskFlagsManager

from src.shared.utils.datetime_utils import get_utc_now

from risk_monitor.bitget import (  # noqa: E402  pylint: disable=wrong-import-position
    BitgetProtectionStatus,
    ExpectedProtection,
    auto_fix_bitget_protection,
    collect_bitget_protection_status,
    compute_limit_market_stats,
    load_bitget_keys,
    load_expected_protection_targets,
    log_bitget_plan_executions,
)
from risk_monitor.calculations import (  # noqa: E402  pylint: disable=wrong-import-position
    get_daily_loss_pct,
    get_max_drawdown_pct,
    read_performance_report,
    weak_setup_burst,
)
from risk_monitor.flags import update_flags  # noqa: E402  pylint: disable=wrong-import-position
from risk_monitor.metrics import (  # noqa: E402  pylint: disable=wrong-import-position
    write_auto_fix_metrics,
    write_limit_market_metrics,
    write_plan_metrics,
    write_stoploss_metrics,
)
from risk_monitor.telegram import (  # noqa: E402  pylint: disable=wrong-import-position
    send_large_loss_alert,
    send_stoploss_alert,
)

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def check_large_losses(db_path: str, threshold_usd: float = -10.0, hours: int = 24) -> List[Dict]:
    """Проверяет сделки с крупными убытками (PnL < threshold) за последние hours часов."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        since = get_utc_now() - timedelta(hours=hours)
        
        # Проверяем наличие таблицы trades
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trades'
        """)
        if not cursor.fetchone():
            LOGGER.debug("⚠️ Таблица trades не найдена, пропускаем проверку крупных убытков")
            conn.close()
            return []
        
        # Проверяем наличие колонки user_id
        cursor = conn.execute("PRAGMA table_info(trades)")
        columns = [row[1] for row in cursor.fetchall()]
        has_user_id = "user_id" in columns
        
        if has_user_id:
            cursor = conn.execute("""
                SELECT 
                    symbol,
                    direction,
                    entry_price,
                    exit_price,
                    net_pnl_usd,
                    pnl_percent,
                    entry_time,
                    exit_time,
                    exit_reason,
                    user_id
                FROM trades
                WHERE datetime(entry_time) >= datetime(?)
                  AND net_pnl_usd < ?
                ORDER BY net_pnl_usd ASC
            """, (since.isoformat(), threshold_usd))
        else:
            cursor = conn.execute("""
                SELECT 
                    symbol,
                    direction,
                    entry_price,
                    exit_price,
                    net_pnl_usd,
                    pnl_percent,
                    entry_time,
                    exit_time,
                    exit_reason
                FROM trades
                WHERE datetime(entry_time) >= datetime(?)
                  AND net_pnl_usd < ?
                ORDER BY net_pnl_usd ASC
            """, (since.isoformat(), threshold_usd))
        
        losses = []
        for row in cursor.fetchall():
            loss_dict = {
                "symbol": row["symbol"],
                "direction": row["direction"],
                "entry_price": row["entry_price"],
                "exit_price": row["exit_price"],
                "net_pnl_usd": float(row["net_pnl_usd"]),
                "pnl_percent": float(row["pnl_percent"]),
                "entry_time": row["entry_time"],
                "exit_time": row["exit_time"],
                "exit_reason": row["exit_reason"],
            }
            if has_user_id:
                loss_dict["user_id"] = row.get("user_id", "unknown")
            else:
                loss_dict["user_id"] = "unknown"
            losses.append(loss_dict)
        
        conn.close()
        return losses
        
    except Exception as e:
        LOGGER.error("❌ Ошибка проверки крупных убытков: %s", e)
        return []


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the risk monitor."""
    parser = argparse.ArgumentParser(description="Монитор рисков и circuit breakers")
    parser.add_argument("--db", default="trading.db", help="Путь к БД SQLite")
    parser.add_argument(
        "--performance-report",
        default="data/reports/performance_live_vs_backfill.json",
        help="JSON с метриками (по умолчанию data/reports/performance_live_vs_backfill.json)",
    )
    parser.add_argument("--warn-maxdd", type=float, default=15.0, help="Порог предупреждения по MaxDD (%)")
    parser.add_argument("--stop-maxdd", type=float, default=18.0, help="Порог остановки по MaxDD (%)")
    parser.add_argument("--stop-daily-loss", type=float, default=5.0, help="Порог дневного убытка (%)")
    parser.add_argument("--weak-setup-limit", type=int, default=10, help="Количество WEAK_SETUP для стопа")
    parser.add_argument("--hours", type=int, default=24, help="Период для расчёта дневного PnL (часы)")
    parser.add_argument(
        "--signals-hours",
        type=int,
        default=48,
        help="Период контроля отсутствия live сигналов (часы)",
    )
    parser.add_argument(
        "--signals-min-count",
        type=int,
        default=1,
        help="Минимальное количество live сигналов за период",
    )
    parser.add_argument(
        "--check-bitget-stoploss",
        action="store_true",
        help="Проверять наличие stop-loss планов на Bitget для активных позиций",
    )
    return parser.parse_args()


def collect_inputs(
    args: argparse.Namespace,
) -> Tuple[
    RiskFlagsManager,
    Optional[float],
    Optional[float],
    bool,
    Optional[bool],
    List[Tuple[int, Dict[str, str]]],
    Dict[Tuple[Optional[int], str, str], ExpectedProtection],
    Dict[str, Dict[str, float]],
]:
    """Fetch base metrics and Bitget credentials from the database."""
    manager = RiskFlagsManager(db_path=args.db)
    report = read_performance_report(Path(args.performance_report))
    max_dd = get_max_drawdown_pct(report)

    expected_targets: Dict[Tuple[Optional[int], str, str], ExpectedProtection] = {}
    with sqlite3.connect(args.db) as conn:
        daily_loss = get_daily_loss_pct(conn, hours=args.hours)
        weak_setup = weak_setup_burst(conn, limit=args.weak_setup_limit)
        signals_stalled: Optional[bool]
        try:
            cursor = conn.execute(
                """
                SELECT COUNT(*) FROM signals_log
                WHERE datetime(entry_time) >= datetime('now', ?)
                  AND (trade_mode = 'live' OR trade_mode IS NULL)
                """,
                (f"-{int(args.signals_hours)} hours",),
            )
            live_count = int(cursor.fetchone()[0])
            signals_stalled = live_count < int(args.signals_min_count)
        except sqlite3.Error:
            signals_stalled = None

        bitget_keys: List[Tuple[int, Dict[str, str]]] = []
        if args.check_bitget_stoploss:
            bitget_keys = load_bitget_keys(conn)
            expected_targets = load_expected_protection_targets(conn) if bitget_keys else {}

        limit_market_stats = compute_limit_market_stats(conn, hours=args.hours)

    return (
        manager,
        max_dd,
        daily_loss,
        weak_setup,
        signals_stalled,
        bitget_keys,
        expected_targets,
        limit_market_stats,
    )


def evaluate_bitget_protection(
    args: argparse.Namespace,
    bitget_keys: Sequence[Tuple[int, Dict[str, str]]],
    expected_targets: Dict[Tuple[Optional[int], str, str], ExpectedProtection],
) -> Tuple[List[BitgetProtectionStatus], List[str], Dict[str, int], Dict[str, int]]:
    """Collect Bitget status and attempt auto-fix if required."""
    if not (args.check_bitget_stoploss and bitget_keys):
        return [], [], {"sl_created": 0, "sl_failed": 0, "tp_created": 0, "tp_failed": 0, "skipped": 0}, {}

    statuses = asyncio.run(collect_bitget_protection_status(bitget_keys))
    missing_labels = [status.stoploss_label() for status in statuses if status.missing_stoploss()]
    gaps_for_fix = [status for status in statuses if status.missing_stoploss() or status.missing_take_profit()]

    auto_fix_summary = {"sl_created": 0, "sl_failed": 0, "tp_created": 0, "tp_failed": 0, "skipped": 0}
    plan_metrics: Dict[str, int] = {}
    audit = None

    if gaps_for_fix:
        audit = get_audit_log()
        auto_fix_summary = asyncio.run(
            auto_fix_bitget_protection(
                statuses=gaps_for_fix,
                keys_map=bitget_keys,
                expected_map=expected_targets,
                db_path=args.db,
                audit=audit,
            )
        )
        statuses = asyncio.run(collect_bitget_protection_status(bitget_keys))
        missing_labels = [status.stoploss_label() for status in statuses if status.missing_stoploss()]

    if bitget_keys:
        audit = audit or get_audit_log()
        plan_metrics = log_bitget_plan_executions(bitget_keys, audit, {status.market_id for status in statuses})

    return statuses, missing_labels, auto_fix_summary, plan_metrics


def write_outputs(
    stoploss_missing: List[str],
    limit_market_stats: Dict[str, Dict[str, float]],
    auto_fix_summary: Dict[str, int],
    plan_metrics: Dict[str, int],
) -> None:
    """Persist metrics and alerts."""
    write_stoploss_metrics(stoploss_missing)
    send_stoploss_alert(stoploss_missing, authorize_agent_action)
    write_limit_market_metrics(limit_market_stats)
    write_auto_fix_metrics(auto_fix_summary)
    write_plan_metrics(plan_metrics)
    
    # 🆕 Экспорт метрик агентов в Prometheus формат
    try:
        agent_metrics = get_agent_metrics()
        agent_metrics.export_to_file()
        LOGGER.debug("✅ Метрики агентов экспортированы")
    except Exception as e:
        LOGGER.debug("⚠️ Ошибка экспорта метрик агентов: %s", e)


def main() -> None:
    """Entry point for the risk monitor CLI."""
    tracer = get_tracer()
    args = parse_args()
    trace = tracer.start(
        agent="risk_monitor",
        mission="risk_scan",
        metadata={
            "db": args.db,
            "check_bitget_stoploss": args.check_bitget_stoploss,
            "hours": args.hours,
        },
    )
    
    # 🆕 Загрузка системного промпта агента с умным выбором контекста
    prompt_manager = get_prompt_manager()
    agent_prompt = prompt_manager.load_prompt("risk_monitor")
    if agent_prompt:
        # Базовый контекст
        base_context = {
            "db": args.db,
            "check_bitget_stoploss": args.check_bitget_stoploss,
            "hours": args.hours,
        }
        
        # 🧠 Используем ContextEngine для умного выбора контекста
        context_engine = get_context_engine()
        enriched_context = context_engine.select_context(
            agent="risk_monitor",
            mission="risk_scan",
        )
        # Объединяем базовый и обогащенный контекст
        final_context = {**base_context, **enriched_context}
        
        full_prompt = agent_prompt.get_full_prompt(final_context, use_context_engine=True)
        trace.record(
            step="think",
            name="prompt_loaded",
            metadata={
                "version": agent_prompt.version,
                "prompt_length": len(full_prompt),
                "context_keys": list(final_context.keys()),
            },
        )
        LOGGER.debug("📝 [PROMPT] risk_monitor v%s загружен (%d символов, контекст: %s)", 
                    agent_prompt.version, len(full_prompt), ", ".join(final_context.keys()))
    authorize_agent_action(
        agent="risk_monitor",
        permission="db:write.metrics",
        context={"check_bitget_stoploss": args.check_bitget_stoploss},
    )
    if args.check_bitget_stoploss:
        authorize_agent_action(
            agent="risk_monitor",
            permission="exchange:read",
            context={"scope": "bitget_plan_orders"},
        )

    try:
        lm_judge = get_lm_judge()
        guidance_entries = get_guidance("risk_monitor", limit=3)
        if guidance_entries:
            trace.record(
                step="think",
                name="guidance_loaded",
                metadata={
                    "entries": [
                        {"issue": entry.issue, "recommendation": entry.recommendation, "count": entry.count}
                        for entry in guidance_entries
                    ]
                },
            )

        (
            manager,
            max_dd,
            daily_loss,
            weak_setup,
            signals_stalled,
            bitget_keys,
            expected_targets,
            limit_market_stats,
        ) = collect_inputs(args)

        trace.record(
            step="observe",
            name="risk_inputs_collected",
            metadata={
                "max_dd": max_dd,
                "daily_loss": daily_loss,
                "weak_setup": weak_setup,
            },
        )

        statuses, stoploss_missing, auto_fix_summary, plan_metrics = evaluate_bitget_protection(
            args,
            bitget_keys,
            expected_targets,
        )

        if statuses:
            trace.record(
                step="observe",
                name="bitget_positions",
                metadata={"positions": len(statuses), "missing_stoploss": len(stoploss_missing)},
            )

        if limit_market_stats:
            trace.record(
                step="observe",
                name="limit_market_stats",
                metadata={"symbols": len(limit_market_stats)},
            )
            for symbol, data in sorted(
                limit_market_stats.items(),
                key=lambda item: item[1].get("fallback_ratio", 0.0),
                reverse=True,
            ):
                LOGGER.info(
                    "📊 [FALLBACK] %s: limit_created=%d limit_timeout=%d market=%d fallback=%.1f%% market_share=%.1f%%",
                    symbol,
                    int(data.get("limit_created", 0)),
                    int(data.get("limit_timeout", 0)),
                    int(data.get("market_filled", 0)),
                    data.get("fallback_ratio", 0.0) * 100,
                    data.get("market_share", 0.0) * 100,
                )

        update_flags(
            manager=manager,
            max_drawdown_pct=max_dd,
            daily_loss_pct=daily_loss,
            weak_setup=weak_setup,
            warn_threshold=args.warn_maxdd,
            stop_threshold=args.stop_maxdd,
            daily_loss_threshold=args.stop_daily_loss,
            signals_stalled=signals_stalled,
            signals_hours=args.signals_hours if signals_stalled is not None else None,
            stoploss_missing=stoploss_missing,
        )
        trace.record(
            step="act",
            name="flags_updated",
            metadata={"stoploss_missing": len(stoploss_missing) if stoploss_missing else 0},
        )

        # Проверка крупных убытков (PnL < -10 USD)
        large_losses = check_large_losses(args.db, threshold_usd=-10.0)
        if large_losses:
            LOGGER.warning(
                "🚨 Обнаружено %d сделок с крупным убытком (PnL < -10 USD)",
                len(large_losses)
            )
            trace.record(
                step="observe",
                name="large_losses_detected",
                status="warning",
                metadata={"count": len(large_losses), "threshold": -10.0},
            )
            authorize_agent_action(
                agent="risk_monitor",
                permission="telegram:send",
                context={"large_losses": len(large_losses)},
            )
            send_large_loss_alert(
                large_losses,
                threshold_usd=-10.0,
                authorize=authorize_agent_action,
            )
            
            # 🆕 Публикуем событие для координации агентов
            try:
                from observability.agent_coordinator import publish_agent_event, EventType
                publish_agent_event(
                    event_type=EventType.RISK_ALERT,
                    agent="risk_monitor",
                    data={
                        "alert_type": "large_loss",
                        "count": len(large_losses),
                        "threshold_usd": -10.0,
                    },
                )
                LOGGER.debug("📡 [COORD] Событие RISK_ALERT опубликовано (large_loss)")
            except Exception as coord_exc:
                LOGGER.debug("⚠️ Ошибка координации: %s", coord_exc)

        write_outputs(stoploss_missing, limit_market_stats, auto_fix_summary, plan_metrics)

        protection_verdict = lm_judge.judge_protection(
            missing_stoploss=len(stoploss_missing),
            auto_fix_failures=auto_fix_summary.get("sl_failed", 0) + auto_fix_summary.get("tp_failed", 0),
        )
        trace.record(step="observe", name="lm_judge_protection", metadata=protection_verdict.to_dict())
        if protection_verdict.status != "pass":
            LOGGER.warning(
                "🧾 [JUDGE] risk_monitor verdict=%s reasons=%s",
                protection_verdict.status,
                "; ".join(protection_verdict.reasons),
            )

        trace.record(step="observe", name="metrics_written")
        trace.finish(status="success")
    except Exception as exc:  # pragma: no cover - top-level guard
        trace.record(
            step="observe",
            name="risk_monitor_exception",
            status="error",
            metadata={"error": str(exc)},
        )
        trace.finish(status="error", metadata={"error": str(exc)})
        raise


if __name__ == "__main__":
    main()

