#!/usr/bin/env python3
import logging
from monitoring.infra_metrics import InfraMetricsStore, compute_metrics, should_alert, InfraTargets

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("infra_monitor")


def main() -> None:
    store = InfraMetricsStore(db_path="trading.db")
    snapshot = compute_metrics(db_path="trading.db", hours=1)
    ok = store.insert_snapshot(snapshot)
    if ok:
        logger.info("✅ INFRA snapshot saved: %s", snapshot)
    else:
        logger.error("❌ Failed to save INFRA snapshot")

    issues = should_alert(snapshot, InfraTargets())
    if issues:
        msg = " | ".join(f"{k}: {v}" for k, v in issues.items())
        logger.warning("🚨 INFRA issues detected: %s", msg)
        # Optional: Telegram/alert integration
        try:
            from alert_notifications import get_alert_service
            svc = get_alert_service()
            svc.alert_system(f"INFRA ALERT: {msg}")
        except Exception:
            pass
    else:
        logger.info("🟢 INFRA OK")


if __name__ == "__main__":
    main()


