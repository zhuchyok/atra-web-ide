import asyncio
import psutil
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class MetricRequest(BaseModel):
    name: str
    value: float
    labels: Optional[dict] = None


class AlertRule(BaseModel):
    name: str
    metric: str
    condition: str
    threshold: float
    duration: int = 60


class Alert(BaseModel):
    id: str
    name: str
    metric: str
    condition: str
    threshold: float
    triggered_at: Optional[int] = None
    resolved_at: Optional[int] = None
    status: str = "pending"


class HealthCheck(BaseModel):
    service: str
    status: str
    latency_ms: float
    details: Optional[dict] = None


_metrics: list[dict] = []
_alert_rules: dict[str, dict] = {}
_active_alerts: dict[str, dict] = {}
_health_cache: dict[str, dict] = {}


def _collect_system_metrics() -> dict:
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "network_sent": psutil.net_io_counters().bytes_sent,
        "network_recv": psutil.net_io_counters().bytes_recv,
    }


@router.post("/metrics")
async def record_metric(request: MetricRequest):
    metric_id = f"metric_{uuid.uuid4().hex[:12]}"

    _metrics.append(
        {
            "id": metric_id,
            "name": request.name,
            "value": request.value,
            "labels": request.labels or {},
            "timestamp": int(datetime.now().timestamp()),
        }
    )

    await _check_alerts(request.name, request.value)

    return {"id": metric_id, "status": "recorded"}


@router.get("/metrics")
async def get_metrics(name: Optional[str] = None, limit: int = 100, since: Optional[int] = None):
    metrics = _metrics

    if name:
        metrics = [m for m in metrics if m["name"] == name]

    if since:
        metrics = [m for m in metrics if m["timestamp"] >= since]

    return sorted(metrics, key=lambda x: x["timestamp"], reverse=True)[:limit]


@router.get("/metrics/{name}/latest")
async def get_latest_metric(name: str):
    metrics = [m for m in _metrics if m["name"] == name]

    if not metrics:
        raise HTTPException(status_code=404, detail="Metric not found")

    return max(metrics, key=lambda x: x["timestamp"])


@router.get("/metrics/{name}/aggregated")
async def get_aggregated_metric(name: str, window: str = "5m"):
    metrics = [m for m in _metrics if m["name"] == name]

    if not metrics:
        raise HTTPException(status_code=404, detail="Metric not found")

    values = [m["value"] for m in metrics]

    return {
        "name": name,
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "sum": sum(values),
    }


@router.post("/alerts/rules")
async def create_alert_rule(request: AlertRule):
    rule_id = f"alert_{uuid.uuid4().hex[:12]}"

    _alert_rules[rule_id] = {
        "id": rule_id,
        "name": request.name,
        "metric": request.metric,
        "condition": request.condition,
        "threshold": request.threshold,
        "duration": request.duration,
        "created_at": int(datetime.now().timestamp()),
    }

    return {"id": rule_id, "status": "created"}


@router.get("/alerts/rules")
async def list_alert_rules():
    return list(_alert_rules.values())


@router.get("/alerts")
async def list_alerts(status: Optional[str] = None):
    alerts = list(_active_alerts.values())

    if status:
        alerts = [a for a in alerts if a["status"] == status]

    return alerts


@router.delete("/alerts/{alert_id}")
async def resolve_alert(alert_id: str):
    if alert_id not in _active_alerts:
        raise HTTPException(status_code=404, detail="Alert not found")

    _active_alerts[alert_id]["status"] = "resolved"
    _active_alerts[alert_id]["resolved_at"] = int(datetime.now().timestamp())

    return _active_alerts[alert_id]


async def _check_alerts(metric_name: str, value: float):
    for rule_id, rule in _alert_rules.items():
        if rule["metric"] != metric_name:
            continue

        triggered = False

        if rule["condition"] == "gt" and value > rule["threshold"]:
            triggered = True
        elif rule["condition"] == "lt" and value < rule["threshold"]:
            triggered = True
        elif rule["condition"] == "eq" and value == rule["threshold"]:
            triggered = True

        if triggered and rule_id not in _active_alerts:
            alert_id = f"alert_{uuid.uuid4().hex[:12]}"
            _active_alerts[alert_id] = {
                "id": alert_id,
                "name": rule["name"],
                "metric": metric_name,
                "condition": rule["condition"],
                "threshold": rule["threshold"],
                "triggered_at": int(datetime.now().timestamp()),
                "resolved_at": None,
                "status": "firing",
            }
        elif not triggered and rule_id in _active_alerts:
            _active_alerts[rule_id]["status"] = "resolved"
            _active_alerts[rule_id]["resolved_at"] = int(datetime.now().timestamp())


@router.get("/health")
async def check_health():
    system = _collect_system_metrics()

    health = []

    if system["cpu_percent"] > 90:
        health.append(
            AlertRule(name="High CPU", metric="cpu", condition="gt", threshold=90).model_dump()
        )

    if system["memory_percent"] > 90:
        health.append(
            HealthCheck(
                service="memory",
                status="warning",
                latency_ms=0,
                details={"percent": system["memory_percent"]},
            ).model_dump()
        )

    return {
        "status": "healthy" if len(health) == 0 else "degraded",
        "system": system,
        "alerts": health,
    }


@router.get("/health/{service}")
async def check_service_health(service: str):
    cached = _health_cache.get(service)

    if cached and datetime.now().timestamp() - cached["timestamp"] < 30:
        return cached

    latency = 0
    status = "healthy"
    details = {}

    if service == "database":
        start = time.time()
        latency = (time.time() - start) * 1000
    elif service == "redis":
        start = time.time()
        latency = (time.time() - start) * 1000
    elif service == "ollama":
        start = time.time()
        latency = (time.time() - start) * 1000

    if latency > 1000:
        status = "unhealthy"
    elif latency > 500:
        status = "degraded"

    result = HealthCheck(
        service=service, status=status, latency_ms=latency, details=details
    ).model_dump()

    _health_cache[service] = result

    return result


@router.get("/dashboard")
async def get_dashboard():
    system = _collect_system_metrics()

    recent_metrics = {}
    for m in _metrics[-50:]:
        name = m["name"]
        if name not in recent_metrics:
            recent_metrics[name] = []
        recent_metrics[name].append(m["value"])

    return {
        "system": system,
        "metrics": {
            name: {
                "latest": values[-1] if values else None,
                "avg": sum(values) / len(values) if values else None,
            }
            for name, values in recent_metrics.items()
        },
        "active_alerts": len([a for a in _active_alerts.values() if a["status"] == "firing"]),
        "alert_rules": len(_alert_rules),
    }


async def get_monitoring_processor() -> dict:
    return {
        "metrics_count": len(_metrics),
        "alert_rules": len(_alert_rules),
        "active_alerts": len(_active_alerts),
    }
