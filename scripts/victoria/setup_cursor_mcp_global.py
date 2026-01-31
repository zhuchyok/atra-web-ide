#!/usr/bin/env python3
"""
Автоматическая настройка MCP Victoria в Cursor settings.json для ВСЕХ проектов.
Запускать один раз: python3 scripts/setup_cursor_mcp_global.py
"""
import json
import os
from pathlib import Path

CURSOR_SETTINGS = Path.home() / "Library/Application Support/Cursor/User/settings.json"
CURSOR_SETTINGS_DIR = CURSOR_SETTINGS.parent

def setup_mcp_in_cursor():
    """Добавляет VictoriaATRA MCP сервер в Cursor settings.json"""
    
    # Создаём директорию, если её нет
    CURSOR_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Читаем существующие настройки
    if CURSOR_SETTINGS.exists():
        try:
            with open(CURSOR_SETTINGS, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️  Ошибка чтения {CURSOR_SETTINGS}: {e}")
            settings = {}
    else:
        settings = {}
    
    # Добавляем/обновляем MCP сервер
    if "mcp.servers" not in settings:
        settings["mcp.servers"] = {}
    
    victoria_config = {
        "type": "sse",
        "url": "http://localhost:8012/sse"
    }
    
    # Проверяем, нужно ли обновить
    if settings["mcp.servers"].get("VictoriaATRA") != victoria_config:
        settings["mcp.servers"]["VictoriaATRA"] = victoria_config
        
        # Сохраняем
        with open(CURSOR_SETTINGS, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        
        print(f"✅ VictoriaATRA добавлен в Cursor settings: {CURSOR_SETTINGS}")
        print(f"   Перезапусти Cursor, чтобы применить изменения.")
        return True
    else:
        print(f"✅ VictoriaATRA уже настроен в Cursor settings")
        return False

if __name__ == "__main__":
    setup_mcp_in_cursor()
