# BITGET Stop-Loss Stabilization — Final Report (12 Nov 2025)

## 1. Overview
- **Scope:** restoration of Bitget stop-loss / take-profit reliability after DASHUSDT incident.
- **Period:** 11–12 Nov 2025 (UTC).
- **Responsible:** Core trading/devops team (lead: zhuchyok).

## 2. Objectives & Outcomes
| Objective | Status | Evidence |
| --- | --- | --- |
| Remove immediate auto-close risk (SL fallback bug) | ✅ | `exchange_adapter.py` uses plan SL (`stopLossPrice`) only. |
| Guarantee TP plan placement on open | ✅ | `place_take_profit_order` → `planType=pos_profit` + audit logging. |
| Continuous monitoring + auto fix | ✅ | `run_risk_monitor.py --check-bitget-stoploss` restores SL/TP, logs to Prometheus. |
| Production deployment & validation | ✅ | `atra.service` restarted 12.11; Bitget responses `code=00000`. |
| Documentation & runbook updates | ✅ | `docs/BITGET_STOPLOSS_ROADMAP.md`, `docs/runbook_bitget_stoploss.md`, incident log. |

## 3. Key Changes
1. **Exchange adapter**
   - Removed reduce-only fallback for stops.
   - Unified `_generate_client_oid` usage for SL/TP (prevents `clientOid` rejection).
   - Added plan-order audit logging (`plan_sl`, `plan_tp1`, `plan_tp2`, `_exec`).
2. **Auto execution**
   - TP1/TP2 placed with `pos_profit` plans (partial closes supported).
3. **Monitoring (`run_risk_monitor.py`)**
   - Collects Bitget positions, detects missing plan orders.
   - Auto-fixes SL/TP using live expected targets (accepted signals/positions).
   - Prometheus metrics: `bitget_stoploss_missing_total`, `bitget_auto_fix_total`, `limit_vs_market_ratio`.
   - Telegram alert integration (requires production chat IDs).
4. **Operations**
   - Nightly cron (`scripts/run_nightly_bitget_checks.sh`) runs unit/integration tests and monitoring checks.

## 4. Verification
| Check | Result |
| --- | --- |
| `scripts/test_bitget_stop_orders.py` | ✅ (staging keys). |
| `run_risk_monitor.py --check-bitget-stoploss` (12.11 17:07 UTC) | Auto-fix: `sl_created=4`, `tp_created=4`, `tp_failed=0`. |
| Prometheus metrics | `bitget_stoploss_missing_total 0`, `bitget_auto_fix_total{tp_failed}=0`. |
| `order_audit_log` | `auto_plan_sl`/`auto_plan_tp` entries with `status='created'`. |
| Bitget API | `plan/currentPlan` returns 0 missing orders after fix. |

## 5. Residual Risks / Follow-ups
1. **Telegram alerts:** set real `TRADING_ALERT_CHAT_ID` / `TELEGRAM_CHAT_IDS` (currently stub IDs cause 400).
2. **Plan history API:** `mix/v1/plan/historyPlan` still returns `40034` for некоторых символов (Bitget issue, awaiting support).
3. **Fallback ratio spikes:** `limit_vs_market_ratio` highlights ADA/MMT → adjust execution params.
4. **Signals gap:** `signals_stalled` flag is active (no live trades ≥48h); monitor strategy pipeline.

## 6. Handover Checklist
- [x] `docs/BITGET_STOPLOSS_ROADMAP.md` Stage 4 marked complete.
- [x] Incident doc updated with auto-fix confirmation.
- [x] Infra health report references new metrics.
- [ ] Configure production chat IDs for alert delivery.
- [ ] Monitor nightly cron results (`logs/test_results.log`) first 48h post-deploy.

## 7. Contacts
- **Engineering:** zhuchyok (backend), devops@atra
- **Ops / Trading:** strategy@atra
- **Support escalation:** bitget-support@atra

---
*Prepared 12 Nov 2025, 17:20 UTC+3.*

