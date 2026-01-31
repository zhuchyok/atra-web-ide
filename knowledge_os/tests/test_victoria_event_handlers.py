"""
Unit tests for Victoria Event Handlers
"""

import pytest
import asyncio

from app.victoria_event_handlers import VictoriaEventHandlers, HandlerState, HandlerContext
from app.event_bus import Event, EventType


@pytest.mark.asyncio
async def test_event_handlers_initialization():
    """Test Victoria Event Handlers initialization"""
    handlers = VictoriaEventHandlers()
    
    assert handlers is not None
    assert handlers.victoria is None
    assert len(handlers.handler_contexts) == 0


@pytest.mark.asyncio
async def test_event_handlers_create_checkpoint():
    """Test checkpoint creation"""
    handlers = VictoriaEventHandlers()
    
    event = Event(
        event_id="test_event",
        event_type=EventType.FILE_CREATED,
        payload={"file_path": "/tmp/test.py"},
        source="test"
    )
    
    context = HandlerContext(event=event)
    handlers._create_checkpoint(context, HandlerState.PROCESSING, {"test": "data"})
    
    assert len(context.checkpoints) == 1
    assert context.state == HandlerState.PROCESSING


@pytest.mark.asyncio
async def test_event_handlers_handle_file_created():
    """Test file created handler"""
    handlers = VictoriaEventHandlers()
    
    event = Event(
        event_id="test_event",
        event_type=EventType.FILE_CREATED,
        payload={"file_path": "/tmp/test.py", "file_name": "test.py"},
        source="test"
    )
    
    result = await handlers.handle_file_created(event)
    
    assert result is not None
    assert "action" in result or "state_machine_result" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
