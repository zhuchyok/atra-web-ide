"""
Unit tests for Service Monitor
"""

import pytest
import asyncio

from app.service_monitor import ServiceMonitor, Service, ServiceStatus


@pytest.mark.asyncio
async def test_service_monitor_initialization():
    """Test Service Monitor initialization"""
    monitor = ServiceMonitor(check_interval=10)
    
    assert monitor is not None
    assert not monitor.is_running()


@pytest.mark.asyncio
async def test_service_monitor_add_service():
    """Test adding service to monitor"""
    monitor = ServiceMonitor(check_interval=10)
    
    service = Service(
        name="test_service",
        service_type="http",
        endpoint="http://localhost:8080",
        port=8080,
        health_check_path="/health"
    )
    
    monitor.add_service(service)
    
    assert "test_service" in monitor.services
    assert monitor.services["test_service"].name == "test_service"


@pytest.mark.asyncio
async def test_service_monitor_start_stop():
    """Test Service Monitor start and stop"""
    monitor = ServiceMonitor(check_interval=10)
    
    await monitor.start()
    assert monitor.is_running()
    
    await monitor.stop()
    assert not monitor.is_running()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
