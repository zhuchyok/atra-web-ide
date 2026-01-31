#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple, Optional, List
import ta

class VolumeBlocksAnalyzer:
    """
    Анализатор блоков покупателей и продавцов на основе объемного профиля
    """

    def __init__(self, lookback_periods: int = 100, volume_threshold: float = 1.5):
        """
        Инициализация анализатора блоков

        Args:
            lookback_periods: Количество периодов для анализа (по умолчанию 100)
            volume_threshold: Порог для определения аномального объема (по умолчанию 1.5x)
        """
        self.lookback_periods = lookback_periods
        self.volume_threshold = volume_threshold
        self.logger = logging.getLogger(__name__)

    def identify_volume_blocks(self, df: pd.DataFrame, current_index: int) -> Dict:
        """
        Идентификация блоков покупателей и продавцов

        Args:
            df: DataFrame с данными OHLCV
            current_index: Текущий индекс для анализа

        Returns:
            Dict с информацией о блоках
        """
        try:
            if current_index < self.lookback_periods:
                return self._get_default_blocks()

            # Получаем данные для анализа
            start_idx = max(0, current_index - self.lookback_periods)
            analysis_data = df.iloc[start_idx:current_index + 1].copy()

            if len(analysis_data) < 20:
                return self._get_default_blocks()

            # Проверяем наличие колонки volume_ratio
            if 'volume_ratio' not in analysis_data.columns:
                # Если нет volume_ratio, используем ATR как прокси для объема
                if 'atr' in analysis_data.columns:
                    analysis_data['volume_ratio'] = analysis_data['atr'] / analysis_data['atr'].mean()
                else:
                    # Если нет ATR, используем волатильность как прокси
                    if 'volatility' in analysis_data.columns:
                        analysis_data['volume_ratio'] = analysis_data['volatility'] / analysis_data['volatility'].mean()
                    else:
                        # Если ничего нет, используем константу
                        analysis_data['volume_ratio'] = 1.0

            # Рассчитываем средний объем
            avg_volume = analysis_data['volume_ratio'].mean()

            # Находим свечи с аномально высоким объемом
            high_volume_candles = analysis_data[analysis_data['volume_ratio'] > avg_volume * self.volume_threshold]

            if len(high_volume_candles) == 0:
                return self._get_default_blocks()

            # Анализируем каждую свечу с высоким объемом
            buyer_blocks = []
            seller_blocks = []

            for idx, candle in high_volume_candles.iterrows():
                block_info = self._analyze_candle_block(candle, avg_volume)
                if block_info:
                    if block_info['type'] == 'buyer':
                        buyer_blocks.append(block_info)
                    else:
                        seller_blocks.append(block_info)

            # Группируем близкие блоки
            buyer_blocks = self._group_nearby_blocks(buyer_blocks)
            seller_blocks = self._group_nearby_blocks(seller_blocks)

            # Рассчитываем силу блоков
            current_price = df['close'].iloc[current_index]

            buyer_strength = self._calculate_block_strength(buyer_blocks, current_price, 'buyer')
            seller_strength = self._calculate_block_strength(seller_blocks, current_price, 'seller')

            return {
                'buyer_blocks': buyer_blocks,
                'seller_blocks': seller_blocks,
                'buyer_strength': buyer_strength,
                'seller_strength': seller_strength,
                'current_price': current_price,
                'avg_volume': avg_volume,
                'total_blocks': len(buyer_blocks) + len(seller_blocks)
            }

        except Exception as e:
            self.logger.error(f"Ошибка анализа блоков: {e}")
            return self._get_default_blocks()

    def _analyze_candle_block(self, candle: pd.Series, avg_volume: float) -> Optional[Dict]:
        """
        Анализ отдельной свечи для определения типа блока

        Args:
            candle: Данные свечи
            avg_volume: Средний объем

        Returns:
            Dict с информацией о блоке или None
        """
        try:
            open_price = candle['open']
            close_price = candle['close']
            high_price = candle['high']
            low_price = candle['low']
            volume = candle['volume_ratio']

            # Определяем тип свечи
            body_size = abs(close_price - open_price)
            total_range = high_price - low_price

            # Если тело свечи больше 60% от общего диапазона
            if body_size > total_range * 0.6:
                if close_price > open_price:
                    # Бычья свеча с высоким объемом = блок покупателей
                    return {
                        'type': 'buyer',
                        'price_level': (open_price + close_price) / 2,
                        'strength': volume / avg_volume,
                        'volume': volume,
                        'timestamp': candle.name if hasattr(candle, 'name') else None
                    }
                else:
                    # Медвежья свеча с высоким объемом = блок продавцов
                    return {
                        'type': 'seller',
                        'price_level': (open_price + close_price) / 2,
                        'strength': volume / avg_volume,
                        'volume': volume,
                        'timestamp': candle.name if hasattr(candle, 'name') else None
                    }

            # Анализ по объему и цене
            volume_ratio = volume / avg_volume

            if volume_ratio > 2.0:  # Очень высокий объем
                # Определяем по направлению цены
                if close_price > open_price:
                    return {
                        'type': 'buyer',
                        'price_level': close_price,
                        'strength': volume_ratio,
                        'volume': volume,
                        'timestamp': candle.name if hasattr(candle, 'name') else None
                    }
                else:
                    return {
                        'type': 'seller',
                        'price_level': close_price,
                        'strength': volume_ratio,
                        'volume': volume,
                        'timestamp': candle.name if hasattr(candle, 'name') else None
                    }

            return None

        except Exception as e:
            self.logger.error(f"Ошибка анализа свечи: {e}")
            return None

    def _group_nearby_blocks(self, blocks: List[Dict], price_tolerance: float = 0.02) -> List[Dict]:
        """
        Группировка близких блоков по цене

        Args:
            blocks: Список блоков
            price_tolerance: Допуск по цене (2% по умолчанию)

        Returns:
            Сгруппированные блоки
        """
        if not blocks:
            return []

        # Сортируем блоки по цене
        sorted_blocks = sorted(blocks, key=lambda x: x['price_level'])
        grouped_blocks = []

        current_group = [sorted_blocks[0]]

        for block in sorted_blocks[1:]:
            # Проверяем, близок ли блок к текущей группе
            group_avg_price = np.mean([b['price_level'] for b in current_group])
            price_diff = abs(block['price_level'] - group_avg_price) / group_avg_price

            if price_diff <= price_tolerance:
                current_group.append(block)
            else:
                # Создаем новый групповой блок
                grouped_blocks.append(self._create_group_block(current_group))
                current_group = [block]

        # Добавляем последнюю группу
        if current_group:
            grouped_blocks.append(self._create_group_block(current_group))

        return grouped_blocks

    def _create_group_block(self, blocks: List[Dict]) -> Dict:
        """
        Создание группового блока из нескольких блоков

        Args:
            blocks: Список блоков для группировки

        Returns:
            Групповой блок
        """
        avg_price = np.mean([b['price_level'] for b in blocks])
        total_volume = sum([b['volume'] for b in blocks])
        avg_strength = np.mean([b['strength'] for b in blocks])

        return {
            'type': blocks[0]['type'],  # Все блоки в группе одного типа
            'price_level': avg_price,
            'strength': avg_strength,
            'volume': total_volume,
            'block_count': len(blocks),
            'timestamp': blocks[-1]['timestamp']  # Время последнего блока
        }

    def _calculate_block_strength(self, blocks: List[Dict], current_price: float, block_type: str) -> float:
        """
        Расчет силы блоков относительно текущей цены

        Args:
            blocks: Список блоков
            current_price: Текущая цена
            block_type: Тип блока ('buyer' или 'seller')

        Returns:
            Сила блоков (0-1)
        """
        if not blocks:
            return 0.0

        total_strength = 0.0
        total_weight = 0.0

        for block in blocks:
            # Расстояние от текущей цены до блока
            price_distance = abs(current_price - block['price_level']) / current_price

            # Вес блока (ближе к цене = больше вес)
            if price_distance <= 0.05:  # В пределах 5%
                weight = 1.0
            elif price_distance <= 0.10:  # В пределах 10%
                weight = 0.7
            elif price_distance <= 0.20:  # В пределах 20%
                weight = 0.4
            else:
                weight = 0.1

            # Сила блока с учетом веса
            block_strength = min(block['strength'] / 3.0, 1.0)  # Нормализуем к 0-1
            weighted_strength = block_strength * weight

            total_strength += weighted_strength
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return total_strength / total_weight

    def _get_default_blocks(self) -> Dict:
        """
        Возвращает блоки по умолчанию при недостатке данных

        Returns:
            Dict с пустыми блоками
        """
        return {
            'buyer_blocks': [],
            'seller_blocks': [],
            'buyer_strength': 0.0,
            'seller_strength': 0.0,
            'current_price': 0.0,
            'avg_volume': 0.0,
            'total_blocks': 0
        }

    def get_signal_enhancement(self, df: pd.DataFrame, current_index: int, signal_type: str) -> Dict:
        """
        Получение усиления/ослабления сигнала на основе блоков

        Args:
            df: DataFrame с данными
            current_index: Текущий индекс
            signal_type: Тип сигнала ('LONG' или 'SHORT')

        Returns:
            Dict с информацией об усилении сигнала
        """
        blocks_info = self.identify_volume_blocks(df, current_index)

        buyer_strength = blocks_info['buyer_strength']
        seller_strength = blocks_info['seller_strength']

        if signal_type == 'LONG':
            if buyer_strength > seller_strength:
                enhancement_factor = 1.0 + (buyer_strength - seller_strength) * 0.3
                enhancement_type = 'strengthened'
                emoji = '🔥'
            elif seller_strength > buyer_strength:
                enhancement_factor = 1.0 - (seller_strength - buyer_strength) * 0.2
                enhancement_type = 'weakened'
                emoji = '⚠️'
            else:
                enhancement_factor = 1.0
                enhancement_type = 'neutral'
                emoji = ''
        elif signal_type == 'SHORT':
            if seller_strength > buyer_strength:
                enhancement_factor = 1.0 + (seller_strength - buyer_strength) * 0.3
                enhancement_type = 'strengthened'
                emoji = '🔥'
            elif buyer_strength > seller_strength:
                enhancement_factor = 1.0 - (buyer_strength - seller_strength) * 0.2
                enhancement_type = 'weakened'
                emoji = '⚠️'
            else:
                enhancement_factor = 1.0
                enhancement_type = 'neutral'
                emoji = ''
        else:
            enhancement_factor = 1.0
            enhancement_type = 'neutral'
            emoji = ''

        return {
            'enhancement_factor': enhancement_factor,
            'enhancement_type': enhancement_type,
            'emoji': emoji,
            'buyer_strength': buyer_strength,
            'seller_strength': seller_strength,
            'blocks_info': blocks_info
        }

# Настройки фильтрации для разных режимов
BLOCK_FILTER_SETTINGS = {
    "strict": {
        "reject_threshold": 1.5,      # Отклонение при противоречии >50%
        "weaken_threshold": 1.2,      # Ослабление при противоречии >20%
        "strengthen_threshold": 0.8,   # Усиление при подтверждении >20%
        "description": "Строгая фильтрация - отклоняет противоречивые сигналы"
    },
    "soft": {
        "reject_threshold": 1.8,      # Отклонение при противоречии >80%
        "weaken_threshold": 1.5,      # Ослабление при противоречии >50%
        "strengthen_threshold": 0.7,   # Усиление при подтверждении >30%
        "description": "Мягкая фильтрация - больше сигналов, меньше отклонений"
    }
}

# Глобальный экземпляр анализатора
volume_blocks_analyzer = VolumeBlocksAnalyzer()

def enhance_signal_with_blocks(df: pd.DataFrame, current_index: int, signal_type: str, signal_price: float, filter_mode: str = "strict") -> Tuple[str, float, Dict]:
    """
    Усиление сигнала на основе анализа блоков с настраиваемой фильтрацией

    Args:
        df: DataFrame с данными
        current_index: Текущий индекс
        signal_type: Тип сигнала ('LONG' или 'SHORT')
        signal_price: Цена сигнала
        filter_mode: Режим фильтрации ('strict', 'soft')

    Returns:
        Tuple: (усиленный тип сигнала, цена, информация об усилении)
    """
    try:
        # Получаем настройки фильтрации для режима
        filter_settings = BLOCK_FILTER_SETTINGS.get(filter_mode, BLOCK_FILTER_SETTINGS["strict"])

        # Получаем информацию о блоках
        blocks_info = volume_blocks_analyzer.identify_volume_blocks(df, current_index)
        buyer_strength = blocks_info['buyer_strength']
        seller_strength = blocks_info['seller_strength']

        # Определяем логику фильтрации в зависимости от типа сигнала
        if signal_type == 'LONG':
            if seller_strength > 0 and buyer_strength > 0:
                strength_ratio = seller_strength / buyer_strength
            else:
                strength_ratio = 1.0

            # Применяем фильтрацию
            if strength_ratio >= filter_settings["reject_threshold"]:
                # Сигнал отклонен
                return None, None, {
                    'enhancement_factor': 0.0,
                    'enhancement_type': 'rejected',
                    'emoji': '❌',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Отклонен: блоки продавцов в {strength_ratio:.2f}x сильнее'
                }
            elif strength_ratio >= filter_settings["weaken_threshold"]:
                # Сигнал ослаблен
                enhancement_factor = 1.0 - (strength_ratio - 1.0) * 0.2
                return f"{signal_type} ⚠️", signal_price, {
                    'enhancement_factor': enhancement_factor,
                    'enhancement_type': 'weakened',
                    'emoji': '⚠️',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Ослаблен: блоки продавцов в {strength_ratio:.2f}x сильнее'
                }
            elif buyer_strength > seller_strength and (buyer_strength / max(seller_strength, 0.1)) >= (1 / filter_settings["strengthen_threshold"]):
                # Сигнал усилен
                enhancement_factor = 1.0 + (buyer_strength - seller_strength) * 0.3
                return f"{signal_type} 🔥", signal_price, {
                    'enhancement_factor': enhancement_factor,
                    'enhancement_type': 'strengthened',
                    'emoji': '🔥',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Усилен: блоки покупателей в {(buyer_strength/max(seller_strength, 0.1)):.2f}x сильнее'
                }
            else:
                # Обычный сигнал
                return signal_type, signal_price, {
                    'enhancement_factor': 1.0,
                    'enhancement_type': 'neutral',
                    'emoji': '',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': 'Нейтральные блоки'
                }

        elif signal_type == 'SHORT':
            if buyer_strength > 0 and seller_strength > 0:
                strength_ratio = buyer_strength / seller_strength
            else:
                strength_ratio = 1.0

            # Применяем фильтрацию
            if strength_ratio >= filter_settings["reject_threshold"]:
                # Сигнал отклонен
                return None, None, {
                    'enhancement_factor': 0.0,
                    'enhancement_type': 'rejected',
                    'emoji': '❌',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Отклонен: блоки покупателей в {strength_ratio:.2f}x сильнее'
                }
            elif strength_ratio >= filter_settings["weaken_threshold"]:
                # Сигнал ослаблен
                enhancement_factor = 1.0 - (strength_ratio - 1.0) * 0.2
                return f"{signal_type} ⚠️", signal_price, {
                    'enhancement_factor': enhancement_factor,
                    'enhancement_type': 'weakened',
                    'emoji': '⚠️',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Ослаблен: блоки покупателей в {strength_ratio:.2f}x сильнее'
                }
            elif seller_strength > buyer_strength and (seller_strength / max(buyer_strength, 0.1)) >= (1 / filter_settings["strengthen_threshold"]):
                # Сигнал усилен
                enhancement_factor = 1.0 + (seller_strength - buyer_strength) * 0.3
                return f"{signal_type} 🔥", signal_price, {
                    'enhancement_factor': enhancement_factor,
                    'enhancement_type': 'strengthened',
                    'emoji': '🔥',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': f'Усилен: блоки продавцов в {(seller_strength/max(buyer_strength, 0.1)):.2f}x сильнее'
                }
            else:
                # Обычный сигнал
                return signal_type, signal_price, {
                    'enhancement_factor': 1.0,
                    'enhancement_type': 'neutral',
                    'emoji': '',
                    'buyer_strength': buyer_strength,
                    'seller_strength': seller_strength,
                    'blocks_info': blocks_info,
                    'filter_mode': filter_mode,
                    'strength_ratio': strength_ratio,
                    'reason': 'Нейтральные блоки'
                }
        else:
            # Неизвестный тип сигнала
            return signal_type, signal_price, {
                'enhancement_factor': 1.0,
                'enhancement_type': 'unknown',
                'emoji': '',
                'buyer_strength': buyer_strength,
                'seller_strength': seller_strength,
                'blocks_info': blocks_info,
                'filter_mode': filter_mode,
                'strength_ratio': 1.0,
                'reason': 'Неизвестный тип сигнала'
            }

    except Exception as e:
        logging.error(f"Ошибка усиления сигнала блоками: {e}")
        # Возвращаем оригинальный сигнал при ошибке
        return signal_type, signal_price, {
            'enhancement_factor': 1.0,
            'enhancement_type': 'error',
            'emoji': '',
            'buyer_strength': 0.0,
            'seller_strength': 0.0,
            'blocks_info': {},
            'filter_mode': filter_mode,
            'strength_ratio': 1.0,
            'reason': f'Ошибка: {str(e)}'
        }
