"""
DateTime Utilities

Common date/time utility functions.

Принцип: Self-Validating Code - Временная консистентность
Цель: Обеспечить корректную работу с временем независимо от часового пояса
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def now() -> datetime:
    """
    Get current datetime in UTC
    
    ВАЖНО: Всегда возвращает UTC время с явным timezone
    """
    return datetime.now(timezone.utc)


def utc_now() -> datetime:
    """
    Get current UTC datetime (alias for now())
    
    ВАЖНО: Использует datetime.now(timezone.utc) вместо устаревшего datetime.utcnow()
    """
    return datetime.now(timezone.utc)


def get_utc_now() -> datetime:
    """
    Get current UTC datetime (explicit function name)
    
    Returns:
        Текущее время в UTC с явным timezone
    """
    return datetime.now(timezone.utc)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """Add minutes to datetime"""
    return dt + timedelta(minutes=minutes)


def add_hours(dt: datetime, hours: int) -> datetime:
    """Add hours to datetime"""
    return dt + timedelta(hours=hours)


def add_days(dt: datetime, days: int) -> datetime:
    """Add days to datetime"""
    return dt + timedelta(days=days)


def is_expired(dt: datetime, expiry_minutes: int, current_time: Optional[datetime] = None) -> bool:
    """Check if datetime is expired"""
    if current_time is None:
        current_time = now()
    
    age_minutes = (current_time - dt).total_seconds() / 60
    return age_minutes > expiry_minutes


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string"""
    return dt.strftime(format_str)

