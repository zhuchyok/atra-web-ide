"""
Unit tests for File Watcher
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from app.file_watcher import FileWatcher, FileChangeHandler
from app.event_bus import get_event_bus, EventType


@pytest.mark.asyncio
async def test_file_watcher_initialization():
    """Test File Watcher initialization"""
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FileWatcher(
            watch_paths=[tmpdir],
            file_extensions=[".py", ".md"],
            recursive=True
        )
        
        assert watcher is not None
        assert not watcher.is_running()
        
        await watcher.stop()


@pytest.mark.asyncio
async def test_file_watcher_start_stop():
    """Test File Watcher start and stop"""
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FileWatcher(
            watch_paths=[tmpdir],
            file_extensions=[".py"],
            recursive=False
        )
        
        await watcher.start()
        assert watcher.is_running()
        
        await watcher.stop()
        assert not watcher.is_running()


@pytest.mark.asyncio
async def test_file_watcher_detects_creation():
    """Test File Watcher detects file creation"""
    event_bus = get_event_bus()
    await event_bus.start()
    
    events_received = []
    
    async def event_handler(event):
        events_received.append(event)
    
    event_bus.subscribe(EventType.FILE_CREATED, event_handler)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = FileWatcher(
            watch_paths=[tmpdir],
            file_extensions=[".py"],
            recursive=False
        )
        
        await watcher.start()
        
        # Создаем файл
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('test')")
        
        # Ждем немного для обработки события
        await asyncio.sleep(0.5)
        
        await watcher.stop()
        await event_bus.stop()
        
        # Проверяем, что событие было получено
        assert len(events_received) > 0
        assert events_received[0].event_type == EventType.FILE_CREATED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
