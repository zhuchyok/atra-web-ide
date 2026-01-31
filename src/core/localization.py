"""
Система локализации для ATRA
Многоязычная поддержка: русский, английский
"""

import json
import os
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..core.config import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


@dataclass
class LocalizationConfig:
    """Конфигурация локализации"""
    default_language: str = DEFAULT_LANGUAGE
    supported_languages: list = None
    locales_path: str = None

    def __post_init__(self):
        if self.supported_languages is None:
            self.supported_languages = ['ru', 'en']
        if self.locales_path is None:
            # Используем абсолютный путь от корня проекта
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.locales_path = os.path.join(base_dir, 'locales')


class Localizer:
    """Основной класс для локализации"""

    def __init__(self, config: Optional[LocalizationConfig] = None):
        self.config = config or LocalizationConfig()
        self.translations = {}
        self._load_translations()

    def _load_translations(self):
        """Загрузка переводов из файлов"""
        for lang in self.config.supported_languages:
            lang_file = os.path.join(self.config.locales_path, f'{lang}.json')
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
                logger.info(f"Loaded translations for {lang}: {len(self.translations[lang])} keys")
            except FileNotFoundError:
                logger.warning(f"Translation file not found: {lang_file}")
                self.translations[lang] = {}
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing translation file {lang_file}: {e}")
                self.translations[lang] = {}

    def get_text(self, key: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Получение текста по ключу

        Args:
            key: Ключ перевода
            language: Язык ('ru', 'en', или None для языка по умолчанию)
            **kwargs: Параметры для форматирования

        Returns:
            str: Переведенный и отформатированный текст
        """
        if language is None:
            language = self.config.default_language

        # Получение перевода
        translation = self._get_translation(key, language)

        # Форматирование с параметрами
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except (KeyError, ValueError) as e:
                logger.warning(f"Error formatting text '{key}': {e}")

        return translation

    def _get_translation(self, key: str, language: str) -> str:
        """Получение перевода по ключу и языку"""
        # Проверяем, есть ли перевод для этого языка
        if language in self.translations and key in self.translations[language]:
            return self.translations[language][key]

        # Fallback на английский, если текущий язык не русский
        if language != 'en' and key in self.translations.get('en', {}):
            return self.translations['en'][key]

        # Fallback на ключ, если перевод не найден
        logger.warning(f"Translation not found for key '{key}' in language '{language}'")
        return key

    def set_language(self, user_id: int, language: str):
        """Установка языка для пользователя"""
        if language not in self.config.supported_languages:
            raise ValueError(f"Unsupported language: {language}")

        # Здесь можно сохранить выбор языка пользователя в базу данных
        logger.info(f"Set language {language} for user {user_id}")

    def get_supported_languages(self) -> list:
        """Получение списка поддерживаемых языков"""
        return self.config.supported_languages.copy()

    def get_language_name(self, language_code: str) -> str:
        """Получение названия языка по коду"""
        language_names = {
            'ru': 'Русский',
            'en': 'English'
        }
        return language_names.get(language_code, language_code)

    def validate_translations(self) -> Dict[str, Any]:
        """Валидация переводов"""
        validation_results = {
            'missing_keys': {},
            'extra_keys': {},
            'summary': {}
        }

        # Используем английский как базовый язык
        base_lang = 'en'
        if base_lang not in self.translations:
            validation_results['summary']['error'] = f"Base language {base_lang} not found"
            return validation_results

        base_keys = set(self.translations[base_lang].keys())

        for lang in self.config.supported_languages:
            if lang == base_lang:
                continue

            if lang not in self.translations:
                validation_results['missing_keys'][lang] = list(base_keys)
                continue

            lang_keys = set(self.translations[lang].keys())
            missing = base_keys - lang_keys
            extra = lang_keys - base_keys

            if missing:
                validation_results['missing_keys'][lang] = list(missing)
            if extra:
                validation_results['extra_keys'][lang] = list(extra)

        validation_results['summary'] = {
            'total_languages': len(self.config.supported_languages),
            'languages_with_missing': len(validation_results['missing_keys']),
            'languages_with_extra': len(validation_results['extra_keys']),
            'base_keys_count': len(base_keys)
        }

        return validation_results


# Глобальный экземпляр локализатора
localizer = Localizer()

# Функции для обратной совместимости
def gettext(key: str, language: Optional[str] = None, **kwargs) -> str:
    """Функция для получения текста (gettext совместимость)"""
    return localizer.get_text(key, language, **kwargs)

def set_language(user_id: int, language: str):
    """Установка языка для пользователя"""
    return localizer.set_language(user_id, language)

def get_supported_languages() -> list:
    """Получение поддерживаемых языков"""
    return localizer.get_supported_languages()

def get_language_name(language_code: str) -> str:
    """Получение названия языка"""
    return localizer.get_language_name(language_code)
