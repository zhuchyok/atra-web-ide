# Boot Incident Guard

Automatic post-boot diagnostics for Mac Studio hard restarts.

## What it captures

- Boot timestamp and uptime (`kern.boottime`)
- Panic/hard-restart evidence from unified logs (`log show`, `DumpPanic`)
- Critical container health
- Runtime task KPIs:
  - `pending`
  - `in_progress`
  - `stale_in_progress_45m`
  - `completed_10m`
  - `failed_10m`
  - `error_rate_10m`

## Files

- Script: `scripts/boot_incident_guard.py`
- LaunchAgent installer: `scripts/install_boot_incident_guard_launchagent.sh`
- Reports: `docs/audits/boot_incidents/latest.json`
- State: `.cache/boot_guard_state.json`

## Install

```bash
bash scripts/install_boot_incident_guard_launchagent.sh
```

## Manual run

```bash
python3 scripts/boot_incident_guard.py --force
```

## Verify agent

```bash
launchctl print "gui/$(id -u)/com.atra.boot-incident-guard"
```
