# Python Crash Detector (MLX coalition)

Detects new `Python-*.ips` incidents for MLX launchd services and sends a local notification.

## Scope

- Source: `~/Library/Logs/DiagnosticReports/Python-*.ips`
- Filter: `coalitionName` starts with `com.atra.mlx-`
- Output reports: `~/Library/Application Support/Atra/python-crash-detector/reports/`

## Install

```bash
bash scripts/install_python_crash_detector_launchagent.sh
```

## Verify

```bash
launchctl print "gui/$(id -u)/com.atra.python-crash-detector"
```

## Notes

- First run bootstraps state and does not notify historical crashes.
- Optional ntfy integration: set `ATRA_CRASH_NTFY_URL` in environment if needed.
