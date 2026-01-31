#!/usr/bin/env python3
"""
Volume Spike Detection System
Детектирование манипуляций объемом
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VolumeSpikeDetector:
    """Детектор манипуляций объемом"""
    
    def __init__(self):
        self.enabled = True
        self.volume_spike_threshold = 3.0  # 3x от среднего объема
        self.suspicious_spike_threshold = 5.0  # 5x от среднего объема
        
    def detect_manipulation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Детектирует манипуляции объемом
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Dict с результатами детектирования
        """
        if not self.enabled or 'volume' not in df.columns:
            return {
                "is_manipulation": False,
                "confidence": 0.0,
                "volume_spike": 1.0,
                "reason": "Volume detection disabled or no volume data"
            }
        
        try:
            if len(df) < 20:
                return {
                    "is_manipulation": False,
                    "confidence": 0.0,
                    "volume_spike": 1.0,
                    "reason": "Not enough data"
                }
            
            # Рассчитываем средний объем
            avg_volume = df['volume'].rolling(window=20).mean().iloc[-1]
            current_volume = df['volume'].iloc[-1]
            
            # Соотношение текущего объема к среднему
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Проверяем на подозрительные скачки
            is_manipulation = False
            confidence = 0.0
            reason = "Normal volume"
            
            if volume_ratio >= self.suspicious_spike_threshold:
                is_manipulation = True
                confidence = 0.9
                reason = f"Suspicious volume spike: {volume_ratio:.2f}x"
            elif volume_ratio >= self.volume_spike_threshold:
                is_manipulation = True
                confidence = 0.7
                reason = f"High volume spike: {volume_ratio:.2f}x"
            
            return {
                "is_manipulation": is_manipulation,
                "confidence": confidence,
                "volume_spike": volume_ratio,
                "reason": reason
            }
            
        except Exception as e:
            logger.error("[VolumeSpike] Ошибка детектирования: %s", e)
            return {
                "is_manipulation": False,
                "confidence": 0.0,
                "volume_spike": 1.0,
                "reason": f"Error: {e}"
            }
    
    def get_volume_quality(self, df: pd.DataFrame) -> float:
        """
        Возвращает качество объема (0.0 - 1.0)
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Качество объема от 0.0 до 1.0
        """
        if not self.enabled or 'volume' not in df.columns or len(df) < 20:
            return 1.0
        
        try:
            detection = self.detect_manipulation(df)
            
            if detection["is_manipulation"]:
                # Качество обратно пропорционально confidence манипуляции
                quality = 1.0 - detection["confidence"]
            else:
                # Нормальный объем = высокое качество
                quality = 0.9
            
            return max(0.0, min(1.0, quality))
            
        except Exception as e:
            logger.debug("[VolumeSpike] Ошибка расчета качества: %s", e)
            return 1.0
