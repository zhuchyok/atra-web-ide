# Release Note: Harness Hardening

Date: 2026-10-28  
Commit: `92ad38c5`  
Scope: alert-spam suppression, disk/state hygiene automation, stronger operational gating.

## What changed

### 1) Launchd watchdog hardening (`scripts/launchd_watchdog.py`)

- Added Cursor state DB monitor with safe cleanup:
  - monitors `state.vscdb` size/growth;
  - prunes old Cursor logs/snapshots.
- Added disk top-growers monitor/report:
  - tracks 24h deltas for key paths (`Cursor`, `Docker.raw`, `ollama`, `backups`);
  - writes report to `logs/disk_growth_report.log`.
- Added dedup keys for new alert families:
  - `[CURSOR-DB]`, `[CURSOR-GROWTH]`, `[DISK-GROWTH]`.
- Added stale internal tail auto-close policy:
  - closes aged internal/synthetic tasks by source and age.
- Added monthly metadata hygiene:
  - removes transient dispatch/retry keys from terminal tasks metadata.

### 2) Security responder anti-spam (`scripts/security_incident_responder.py`)

- DB connect retries/backoff for pgbouncer flaps.
- Consolidated security flow no longer creates duplicate hourly tasks:
  - updates existing open consolidated security task (`updated_open`) when applicable.

### 3) Task watchdog fail-soft (`scripts/docker_task_watchdog.sh`)

- PATH hardening and docker availability checks.
- Safe skip when docker/container not available (prevents log storm).

### 4) Operational context gating (`knowledge_os/app/ai_pipeline.py`)

- Operational-query detection is now env-driven:
  - configurable categories and markers;
  - reduces memory-crystal noise for incident/monitoring prompts.

### 5) Tracking/reporting

- Added harness checklist/map:
  - `docs/reports/2026-10-28-harness-checklist.md`

## Runtime behavior impact

- Fewer duplicate watchdog/security tasks and alerts.
- Earlier visibility into disk growth drivers before hard low-space incidents.
- Lower context noise for operational prompts.
- Reduced long-term metadata bloat in `tasks` terminal rows.

## New/important environment variables

### Watchdog / disk / cursor

- `LAUNCHD_WD_DISK_MIN_FREE_PCT` (default: `12.0`)
- `CURSOR_STATE_DB_WARN_GB` (default: `80`)
- `CURSOR_STATE_DB_GROWTH_WARN_GB` (default: `5`)
- `CURSOR_STATE_DB_GROWTH_WINDOW_HOURS` (default: `24`)
- `CURSOR_LOGS_KEEP_DAYS` (default: `14`)
- `CURSOR_SNAPSHOTS_KEEP_DAYS` (default: `7`)
- `DISK_GROWTH_REPORT_EVERY_HOURS` (default: `24`)
- `DISK_GROWTH_WARN_GB_24H` (default: `8`)
- `WATCHDOG_STALE_INTERNAL_HOURS` (default: `8`)
- `WATCHDOG_STALE_INTERNAL_SOURCES` (default: `nightly_hypothesis_debate,launchd_watchdog,predictive_monitor`)
- `TASK_METADATA_HYGIENE_EVERY_DAYS` (default: `30`)
- `TASK_METADATA_HYGIENE_RETAIN_DAYS` (default: `30`)

### AI pipeline operational gating

- `AI_PIPELINE_OPERATIONAL_CATEGORIES`
- `AI_PIPELINE_OPERATIONAL_MARKERS`
- `AI_PIPELINE_CRYSTALS_SKIP_OPERATIONAL`
- `AI_PIPELINE_CRYSTALS_OPERATIONAL_MAX_CHARS`

## Quick verification

1. Run watchdog once:
   - `/Users/bikos/Documents/atra-web-ide/.venv/bin/python scripts/launchd_watchdog.py`
2. Confirm disk growth report exists:
   - `logs/disk_growth_report.log`
3. Check queue tail:
   - `pending=0`, `queued=0` (only expected `in_progress` operational work remains)
4. Confirm runtime endpoints:
   - `11435/health=200`
   - `11434/11437 generate=200`
   - `8001/encode=200`
