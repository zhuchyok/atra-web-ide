"""
[SINGULARITY 26.7] Celery Configuration

Victoria Celery Workers Configuration
- Redis as broker и result backend
-监控 через Flower (port 5555)
- Error handling и retries настроены
"""

import os

# Broker settings
broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
result_backend = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Task settings
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

# Execution settings
task_track_started = True
task_time_limit = 300  # 5 minutes hard limit
task_soft_time_limit = 240  # 4 minutes soft limit
task_acks_late = True  # Ack after completion
task_reject_on_worker_lost = True

# Worker settings
worker_prefetch_multiplier = 1  # One task at a time
worker_concurrency = 2
worker_max_tasks_per_child = 100  # Restart after 100 tasks

# Retry settings
task_default_retry_delay = 60
task_max_retries = 3

# Result settings
result_expires = 3600  # 1 hour
result_persistent = True

# Monitoring (Flower)
flower_url = os.getenv("FLOWER_URL", "http://localhost:5555")
flower_basic_auth = os.getenv("FLOWER_AUTH", "admin:secret")

# Error handling
worker_send_task_events = True
task_send_sent_event = True

# Monitoring
worker_log_format = "[%(asctime)s: %(levelname)s/%(process_name)s] %(message)s"
worker_task_log_format = (
    "[%(asctime)s: %(levelname)s/%(process_name)s][%(task_name)s(%(task_id)s)] %(message)s"
)

# Redis broker settings
broker_pool_limit = 10
broker_connection_retry = True
broker_connection_max_retries = 3

# Result backend settings
result_backend_transport_options = {
    "master_name": "mymaster",
    "visibility_timeout": 3600,
}

# Task routes - приоритеты
task_routes = {
    "victoria.run_code_generation": {"queue": "code"},
    "victoria.run_analysis": {"queue": "analysis"},
    "victoria.run_research": {"queue": "research"},
    "victoria.health_check": {"queue": "default"},
}

# Queue definitions
task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "code": {
        "exchange": "code",
        "routing_key": "code",
    },
    "analysis": {
        "exchange": "analysis",
        "routing_key": "analysis",
    },
    "research": {
        "exchange": "research",
        "routing_key": "research",
    },
}

# Beat schedule (periodic tasks)
beat_schedule = {
    "health-check-every-5-minutes": {
        "task": "victoria.periodic.health",
        "schedule": 300.0,
    },
}
