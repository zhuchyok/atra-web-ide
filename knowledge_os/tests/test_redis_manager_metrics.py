import importlib

import pytest

import app.redis_manager as redis_manager


def test_worker_queue_depth_metric_is_idempotent_on_reload():
    if not redis_manager._PROMETHEUS_AVAILABLE:
        pytest.skip("prometheus_client is not available")

    first_metric = redis_manager._queue_depth
    reloaded = importlib.reload(redis_manager)
    second_metric = reloaded._queue_depth

    assert first_metric is not None
    assert second_metric is not None
    assert first_metric._name == "worker_queue_depth"
    assert second_metric._name == "worker_queue_depth"
