#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 TRIPLE BARRIER LABELING & META-LABELING UTILS
Based on "Advances in Financial Machine Learning" by Marcos López de Prado
"""

import pandas as pd
import numpy as np
from typing import Optional, Union, List, Tuple
import logging

logger = logging.getLogger(__name__)

def get_volatility(close: pd.Series, span: int = 100) -> pd.Series:
    """
    Вычисляет динамическую волатильность для установки порогов барьеров
    """
    # Вычисляем лог-доходность и её экспоненциальное стандартное отклонение
    df0 = close.index.searchsorted(close.index - pd.Timedelta(days=1))
    df0 = df0[df0 > 0]
    df0 = pd.Series(close.index[df0 - 1], index=close.index[close.shape[0] - df0.shape[0]:])
    try:
        df0 = close.loc[df0.index] / close.loc[df0.values].values - 1  # daily returns
    except Exception:
        logger.warning("⚠️ Ошибка расчета волатильности через Timedelta, используем простой pct_change")
        df0 = close.pct_change()
        
    return df0.ewm(span=span).std()

def apply_triple_barrier(
    close: pd.Series,
    events: pd.DataFrame,
    pt_sl: List[float] = [1, 1],
    t1: Optional[pd.Series] = None,
    molecule: Optional[pd.Index] = None,
    commission_pct: float = 0.001  # Добавлена комиссия (0.1% по умолчанию)
) -> pd.DataFrame:
    """
    Triple Barrier Labeling с учетом комиссии
    """
    if molecule is None:
        molecule = events.index
        
    # Инициализация результатов
    out = events.loc[molecule].copy()
    if pt_sl[0] > 0:
        pt = pt_sl[0] * out['trgt']
    else:
        pt = pd.Series(index=events.index)  # No profit taking
        
    if pt_sl[1] > 0:
        sl = -pt_sl[1] * out['trgt']
    else:
        sl = pd.Series(index=events.index)  # No stop loss
        
    # Находим время первого пересечения барьера
    for loc, t_end in events.loc[molecule, 't1'].fillna(close.index[-1]).items():
        df0 = close.loc[loc:t_end]  # path prices
        # Вычитаем комиссию (вход + выход)
        df0 = (df0 / close.loc[loc] - 1) * events.at[loc, 'side'] - (2 * commission_pct)
        
        out.at[loc, 'sl'] = df0[df0 < sl[loc]].index.min()  # earliest stop loss
        out.at[loc, 'pt'] = df0[df0 > pt[loc]].index.min()  # earliest profit take
        
    return out

def get_bins(events: pd.DataFrame, close: pd.Series, commission_pct: float = 0.001) -> pd.DataFrame:
    """
    Генерирует финальные метки (bin) на основе пересечения барьеров с учетом комиссии
    """
    # 1. Ищем пересечение барьера
    out = events.copy()
    first_touch = out[['sl', 'pt']].min(axis=1)
    
    for loc, t_touch in first_touch.items():
        if pd.isna(t_touch):
            # Ни один из горизонтальных барьеров не пробит до вертикального
            out.at[loc, 'bin'] = 0
            # Чистая доходность с учетом комиссии
            ret = (close.loc[out.at[loc, 't1']] / close.loc[loc] - 1) * events.at[loc, 'side'] - (2 * commission_pct)
            out.at[loc, 'ret'] = ret
        else:
            # Пробит один из горизонтальных барьеров
            if t_touch == out.at[loc, 'sl']:
                out.at[loc, 'bin'] = -1
            else:
                out.at[loc, 'bin'] = 1
            # Чистая доходность
            ret = (close.loc[t_touch] / close.loc[loc] - 1) * events.at[loc, 'side'] - (2 * commission_pct)
            out.at[loc, 'ret'] = ret
            
    return out

def get_meta_labels(real_labels: pd.Series, predicted_labels: pd.Series) -> pd.Series:
    """
    Генерирует метки для Meta-Model (вторичная модель)
    
    Meta-label = 1 если (Primary Prediction == Real Outcome)
    Meta_label = 0 если (Primary Prediction != Real Outcome)
    """
    # В классическом Meta-labeling мы обучаем модель предсказывать ПОЗИТИВНЫЙ исход
    # если наша первичная модель УГАДАЛА сторону.
    return (real_labels == predicted_labels).astype(int)

