"""
Валидация данных для ATRA
Проверка корректности и целостности данных из внешних источников
"""

import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
import re

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Ошибка валидации данных"""
    pass


class DataValidator(ABC):
    """Абстрактный базовый класс для валидаторов данных"""

    def __init__(self, name: str):
        self.name = name
        self.validation_errors = []
        self.warning_count = 0

    def add_error(self, field: str, message: str, value: Any = None):
        """Добавление ошибки валидации"""
        error = {
            'field': field,
            'message': message,
            'value': value,
            'timestamp': get_utc_now().isoformat()
        }
        self.validation_errors.append(error)
        logger.warning(f"Validation error in {self.name}: {field} - {message}")

    def add_warning(self, field: str, message: str, value: Any = None):
        """Добавление предупреждения валидации"""
        self.warning_count += 1
        logger.debug(f"Validation warning in {self.name}: {field} - {message}")

    def has_errors(self) -> bool:
        """Проверка наличия ошибок"""
        return len(self.validation_errors) > 0

    def get_errors(self) -> List[Dict]:
        """Получение списка ошибок"""
        return self.validation_errors.copy()

    def clear_errors(self):
        """Очистка ошибок"""
        self.validation_errors.clear()
        self.warning_count = 0

    def get_stats(self) -> Dict:
        """Получение статистики валидации"""
        return {
            'validator_name': self.name,
            'error_count': len(self.validation_errors),
            'warning_count': self.warning_count,
            'has_errors': self.has_errors()
        }

    @abstractmethod
    def validate(self, data: Any) -> bool:
        """Абстрактный метод валидации"""
        pass


class PriceValidator(DataValidator):
    """Валидатор ценовых данных"""

    def __init__(self):
        super().__init__('price_validator')

    def validate_price(self, price: Union[float, int, str]) -> Tuple[bool, Optional[float]]:
        """Валидация цены"""
        try:
            if price is None or price == "":
                self.add_error('price', 'Price is empty or None', price)
                return False, None

            # Конвертация в float
            if isinstance(price, str):
                price = price.replace(',', '').replace(' ', '')
                if price.lower() in ['nan', 'null', 'none', '']:
                    self.add_error('price', 'Invalid price string', price)
                    return False, None
                price_float = float(price)
            else:
                price_float = float(price)

            # Проверка на положительность
            if price_float <= 0:
                self.add_error('price', 'Price must be positive', price_float)
                return False, None

            # Проверка на разумные границы (0.000001 - 1,000,000)
            if price_float < 0.000001:
                self.add_error('price', 'Price too low (possible error)', price_float)
                return False, None
            elif price_float > 1000000:
                self.add_error('price', 'Price too high (possible error)', price_float)
                return False, None

            # Проверка на слишком много десятичных знаков
            if isinstance(price, str) and '.' in price:
                decimals = len(price.split('.')[-1])
                if decimals > 18:  # Биткоин имеет 8, но для безопасности
                    self.add_warning('price', f'Too many decimal places: {decimals}', price_float)

            return True, price_float

        except (ValueError, TypeError) as e:
            self.add_error('price', f'Invalid price format: {e}', price)
            return False, None

    def validate_volume(self, volume: Union[float, int, str]) -> Tuple[bool, Optional[float]]:
        """Валидация объема"""
        try:
            if volume is None or volume == "":
                self.add_error('volume', 'Volume is empty or None', volume)
                return False, None

            # Конвертация в float
            if isinstance(volume, str):
                volume = volume.replace(',', '').replace(' ', '')
                volume_float = float(volume)
            else:
                volume_float = float(volume)

            # Проверка на неотрицательность
            if volume_float < 0:
                self.add_error('volume', 'Volume cannot be negative', volume_float)
                return False, None

            return True, volume_float

        except (ValueError, TypeError) as e:
            self.add_error('volume', f'Invalid volume format: {e}', volume)
            return False, None

    def validate_symbol(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """Валидация символа монеты"""
        if not symbol or not isinstance(symbol, str):
            self.add_error('symbol', 'Symbol is empty or not a string', symbol)
            return False, None

        # Очистка и валидация
        clean_symbol = symbol.strip().upper()

        if not clean_symbol:
            self.add_error('symbol', 'Symbol is empty after cleaning', symbol)
            return False, None

        # Проверка на допустимые символы (буквы, цифры, дефис, подчеркивание)
        if not re.match(r'^[A-Z0-9_-]+$', clean_symbol):
            self.add_error('symbol', 'Symbol contains invalid characters', symbol)
            return False, None

        # Проверка на разумную длину
        if len(clean_symbol) > 20:
            self.add_error('symbol', 'Symbol too long', symbol)
            return False, None
        elif len(clean_symbol) < 2:
            self.add_error('symbol', 'Symbol too short', symbol)
            return False, None

        return True, clean_symbol

    def validate_timestamp(self, timestamp: Union[str, int, float, datetime]) -> Tuple[bool, Optional[datetime]]:
        """Валидация временной метки"""
        try:
            if isinstance(timestamp, datetime):
                dt = timestamp
            elif isinstance(timestamp, (int, float)):
                dt = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                # Поддержка различных форматов ISO
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                    try:
                        dt = datetime.strptime(timestamp, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Попытка парсинга как ISO
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                self.add_error('timestamp', 'Unsupported timestamp type', type(timestamp))
                return False, None

            # Проверка на разумные границы (не раньше 2010 и не позже чем через день от сейчас)
            now = get_utc_now()
            min_date = datetime(2010, 1, 1)

            if dt < min_date:
                self.add_error('timestamp', 'Timestamp too old', timestamp)
                return False, None
            elif dt > now + timedelta(days=1):
                self.add_error('timestamp', 'Timestamp in future', timestamp)
                return False, None

            return True, dt

        except (ValueError, TypeError, AttributeError) as e:
            self.add_error('timestamp', f'Invalid timestamp format: {e}', timestamp)
            return False, None

    def validate(self, data: Any) -> bool:
        """Основной метод валидации ценовых данных"""
        self.clear_errors()

        if not isinstance(data, dict):
            self.add_error('data', 'Data must be a dictionary', type(data))
            return False

        # Валидация обязательных полей
        required_fields = ['symbol', 'price']
        for field in required_fields:
            if field not in data:
                self.add_error(field, f'Required field missing: {field}')

        if self.has_errors():
            return False

        # Валидация символа
        symbol_valid, clean_symbol = self.validate_symbol(data.get('symbol'))
        if not symbol_valid:
            return False

        # Валидация цены
        price_valid, clean_price = self.validate_price(data.get('price'))
        if not price_valid:
            return False

        # Валидация объема (если есть)
        if 'volume' in data:
            volume_valid, clean_volume = self.validate_volume(data.get('volume'))
            if not volume_valid:
                return False

        # Валидация timestamp (если есть)
        if 'timestamp' in data:
            timestamp_valid, clean_timestamp = self.validate_timestamp(data.get('timestamp'))
            if not timestamp_valid:
                return False

        return True


class VolumeValidator(DataValidator):
    """Валидатор объемных данных"""

    def __init__(self):
        super().__init__('volume_validator')

    def validate_volume_change(self, current: float, previous: float) -> bool:
        """Валидация изменения объема"""
        if previous <= 0:
            self.add_error('volume_change', 'Previous volume must be positive', previous)
            return False

        change_pct = abs(current - previous) / previous * 100

        # Предупреждение при очень больших изменениях
        if change_pct > 1000:  # 10x изменение
            self.add_warning('volume_change', f'Very large volume change: {change_pct:.1f}%', change_pct)

        return True

    def validate_market_cap(self, market_cap: Union[float, int, str]) -> Tuple[bool, Optional[float]]:
        """Валидация рыночной капитализации"""
        try:
            if market_cap is None or market_cap == "":
                self.add_error('market_cap', 'Market cap is empty or None', market_cap)
                return False, None

            if isinstance(market_cap, str):
                market_cap = market_cap.replace(',', '').replace(' ', '').replace('$', '')
                if market_cap.lower() in ['nan', 'null', 'none', '']:
                    self.add_error('market_cap', 'Invalid market cap string', market_cap)
                    return False, None
                market_cap_float = float(market_cap)
            else:
                market_cap_float = float(market_cap)

            if market_cap_float < 0:
                self.add_error('market_cap', 'Market cap cannot be negative', market_cap_float)
                return False, None

            # Проверка на разумные границы
            if market_cap_float > 1e15:  # > 1 квадриллион
                self.add_warning('market_cap', f'Very large market cap: ${market_cap_float:,.0f}', market_cap_float)

            return True, market_cap_float

        except (ValueError, TypeError) as e:
            self.add_error('market_cap', f'Invalid market cap format: {e}', market_cap)
            return False, None

    def validate(self, data: Any) -> bool:
        """Основной метод валидации объемных данных"""
        self.clear_errors()

        if not isinstance(data, dict):
            self.add_error('data', 'Data must be a dictionary', type(data))
            return False

        # Валидация объема
        if 'volume' in data:
            volume_valid, clean_volume = PriceValidator().validate_volume(data.get('volume'))
            if not volume_valid:
                return False

        # Валидация изменения объема
        if 'volume' in data and 'previous_volume' in data:
            if not self.validate_volume_change(data['volume'], data['previous_volume']):
                return False

        # Валидация рыночной капитализации
        if 'market_cap' in data:
            market_cap_valid, clean_market_cap = self.validate_market_cap(data.get('market_cap'))
            if not market_cap_valid:
                return False

        return True


class NewsValidator(DataValidator):
    """Валидатор новостных данных"""

    def __init__(self):
        super().__init__('news_validator')

    def validate_news_item(self, news_item: Dict) -> bool:
        """Валидация отдельного новостного элемента"""
        if not isinstance(news_item, dict):
            self.add_error('news_item', 'News item must be a dictionary', type(news_item))
            return False

        # Проверка обязательных полей
        required_fields = ['title', 'url']
        for field in required_fields:
            if field not in news_item or not news_item[field]:
                self.add_error(f'news_{field}', f'Missing or empty {field}', news_item.get(field))

        if self.has_errors():
            return False

        # Валидация URL
        url = news_item.get('url', '')
        if not url.startswith(('http://', 'https://')):
            self.add_error('news_url', 'Invalid URL format', url)
            return False

        # Валидация заголовка
        title = news_item.get('title', '')
        if len(title.strip()) < 10:
            self.add_warning('news_title', 'Title too short', title)
        elif len(title) > 200:
            self.add_warning('news_title', 'Title too long', title)

        return True

    def validate(self, data: Any) -> bool:
        """Основной метод валидации новостных данных"""
        self.clear_errors()

        if isinstance(data, list):
            for i, item in enumerate(data):
                if not self.validate_news_item(item):
                    self.add_error('news_list', f'Invalid news item at index {i}')
                    return False
        elif isinstance(data, dict):
            return self.validate_news_item(data)
        else:
            self.add_error('news_data', 'News data must be dict or list', type(data))
            return False

        return True


# Глобальные экземпляры валидаторов
price_validator = PriceValidator()
volume_validator = VolumeValidator()
news_validator = NewsValidator()

# Экспорт для обратной совместимости
def validate_price_data(data: Dict) -> bool:
    """Обратная совместимость"""
    return price_validator.validate(data)

def validate_volume_data(data: Dict) -> bool:
    """Обратная совместимость"""
    return volume_validator.validate(data)
