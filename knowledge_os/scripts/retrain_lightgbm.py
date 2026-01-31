#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 ПЕРЕОБУЧЕНИЕ LIGHTGBM С ПРАВИЛЬНЫМИ FEATURES
"""

import json
import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))

from src.shared.utils.datetime_utils import get_utc_now

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        roc_auc_score, accuracy_score, precision_score, recall_score, f1_score,
        mean_absolute_error, mean_squared_error, r2_score
    )
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    logger.error("❌ LightGBM не установлен: pip install lightgbm scikit-learn")
    sys.exit(1)

print("=" * 80)
print("🤖 ПЕРЕОБУЧЕНИЕ LIGHTGBM С ПРАВИЛЬНЫМИ FEATURES")
print("=" * 80)

PATTERNS_FILE = Path(__file__).parent.parent / "ai_learning_data" / "trading_patterns.json"
MODEL_DIR = Path(__file__).parent.parent / "ai_learning_data" / "lightgbm_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ⚡ LEARNING SESSION #4 (Дмитрий): Расширенные lag features
# Features которые мы будем использовать
# Original 15 + расширенные lag features = 28 total
FEATURE_NAMES = [
    # Base features (15)
    'rsi', 'macd', 'volume_ratio', 'volatility',
    'ema_distance', 'bb_position', 'atr_pct',
    'signal_is_long', 'risk_pct', 'leverage',
    'tp1_distance_pct', 'tp2_distance_pct',
    'hour_of_day', 'day_of_week', 'is_weekend',
    # Расширенные lag features (13) - для улучшения предсказаний
    'rsi_lag_1', 'rsi_lag_2', 'rsi_lag_3', 'rsi_change',
    'macd_lag_1', 'macd_lag_2', 'macd_lag_3', 'macd_change',
    'volume_ratio_lag_1', 'volume_trend', 'volume_change_1',
    'volatility_lag_1', 'volatility_change',
    'price_change_1', 'price_change_3'
]

def load_patterns():
    """Загружает паттерны из файла"""
    logger.info(f"📂 Загрузка паттернов из {PATTERNS_FILE}")
    
    if not PATTERNS_FILE.exists():
        logger.error(f"❌ Файл не найден: {PATTERNS_FILE}")
        sys.exit(1)
    
    with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"✅ Загружено {len(data)} паттернов")
    
    # Статистика
    wins = sum(1 for p in data if p.get('result') == 'WIN')
    losses = len(data) - wins
    logger.info(f"   WIN: {wins} ({wins/len(data)*100:.1f}%)")
    logger.info(f"   LOSS: {losses} ({losses/len(data)*100:.1f}%)")
    
    return data

def extract_features_from_pattern(pattern):
    """
    Извлекает features из паттерна
    
    Если indicators пустые - генерируем разумные дефолтные значения
    """
    try:
        # Базовые данные
        entry_price = float(pattern.get('entry_price', 0))
        tp1 = float(pattern.get('tp1', 0))
        tp2 = float(pattern.get('tp2', 0))
        
        if entry_price == 0:
            return None
        
        # Индикаторы (с дефолтными значениями)
        indicators = pattern.get('indicators', {})
        
        # RSI: если нет - генерируем разумное значение в зависимости от результата
        # Для WIN обычно RSI ближе к экстремумам (перекуплено/перепродано)
        if 'rsi' in indicators:
            rsi = float(indicators['rsi'])
        else:
            # Дефолтное значение
            if pattern.get('signal_type') == 'LONG':
                rsi = 35.0  # oversold для LONG
            else:
                rsi = 65.0  # overbought для SHORT
        
        # MACD
        macd = float(indicators.get('macd', 0.001))
        
        # Volume ratio
        volume_ratio = float(indicators.get('volume_ratio', 1.5))
        
        # Volatility (ATR %)
        volatility = float(indicators.get('volatility', 0.02))
        
        # EMA distance
        ema_fast = float(indicators.get('ema_fast', entry_price * 1.01))
        ema_slow = float(indicators.get('ema_slow', entry_price * 0.99))
        ema_distance = abs(ema_fast - ema_slow) / entry_price
        
        # BB position
        bb_upper = float(indicators.get('bb_upper', entry_price * 1.02))
        bb_lower = float(indicators.get('bb_lower', entry_price * 0.98))
        if bb_upper > bb_lower:
            bb_position = (entry_price - bb_lower) / (bb_upper - bb_lower)
        else:
            bb_position = 0.5
        
        # ATR %
        atr = float(indicators.get('atr', entry_price * 0.015))
        atr_pct = atr / entry_price
        
        # Signal type
        signal_is_long = 1.0 if pattern.get('signal_type') == 'LONG' else 0.0
        
        # Risk params
        risk_pct = float(pattern.get('risk_pct', 2.0))
        leverage = float(pattern.get('leverage', 1.0))
        
        # TP distances
        tp1_distance_pct = abs(tp1 - entry_price) / entry_price * 100
        tp2_distance_pct = abs(tp2 - entry_price) / entry_price * 100
        
        # Time features
        try:
            timestamp = datetime.fromisoformat(pattern['timestamp'].replace('Z', '+00:00'))
            hour_of_day = timestamp.hour
            day_of_week = timestamp.weekday()
            is_weekend = 1.0 if day_of_week >= 5 else 0.0
        except:
            hour_of_day = 12
            day_of_week = 2
            is_weekend = 0.0
        
        # Собираем features
        features = {
            'rsi': rsi,
            'macd': macd,
            'volume_ratio': volume_ratio,
            'volatility': volatility,
            'ema_distance': ema_distance,
            'bb_position': bb_position,
            'atr_pct': atr_pct,
            'signal_is_long': signal_is_long,
            'risk_pct': risk_pct,
            'leverage': leverage,
            'tp1_distance_pct': tp1_distance_pct,
            'tp2_distance_pct': tp2_distance_pct,
            'hour_of_day': hour_of_day,
            'day_of_week': day_of_week,
            'is_weekend': is_weekend
        }
        
        # ⚡ LEARNING SESSION #4 (Дмитрий): Расширенные lag features
        # Lag features (будут вычислены из последовательности при подготовке датасета)
        # Пока используем текущие значения как fallback
        features['rsi_lag_1'] = rsi  # Будет перезаписано если есть история
        features['rsi_change'] = 0.0
        features['macd_lag_1'] = macd
        features['macd_change'] = 0.0
        features['volume_ratio_lag_1'] = volume_ratio
        features['volume_trend'] = 0.0
        features['volatility_lag_1'] = volatility
        features['volatility_change'] = 0.0
        
        # Дополнительные lag features для улучшения предсказаний
        # (будут вычислены из последовательности)
        features['rsi_lag_2'] = rsi
        features['rsi_lag_3'] = rsi
        features['macd_lag_2'] = macd
        features['macd_lag_3'] = macd
        features['price_change_1'] = 0.0  # Изменение цены за 1 период
        features['price_change_3'] = 0.0  # Изменение цены за 3 периода
        features['volume_change_1'] = 0.0  # Изменение объёма
        
        return features
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка извлечения features: {e}")
        return None

def prepare_dataset(patterns):
    """Подготавливает датасет для обучения"""
    logger.info("\n📊 Подготовка датасета...")
    
    # Сортируем паттерны по времени для вычисления lag features
    try:
        def get_ts(p):
            ts = p.get('timestamp', '')
            if isinstance(ts, datetime):
                return ts.isoformat()
            return str(ts)
        patterns_sorted = sorted(patterns, key=get_ts)
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отсортировать паттерны: {e}")
        patterns_sorted = patterns
    
    X_list = []
    y_class = []  # 1 = WIN, 0 = LOSS
    y_reg = []    # profit_pct
    
    # ⚡ LEARNING SESSION #4 (Дмитрий): Расширенные lag features
    # Храним историю для вычисления lag features (lag_1, lag_2, lag_3)
    history_rsi = []
    history_macd = []
    history_volume = []
    history_volatility = []
    history_price = []
    
    for i, pattern in enumerate(patterns_sorted):
        features = extract_features_from_pattern(pattern)
        if features is None:
            continue
        
        # Получаем цену входа для вычисления price_change
        entry_price = float(pattern.get('entry_price', pattern.get('entry', 0)))
        
        # Вычисляем lag features из истории
        # Lag 1
        if len(history_rsi) >= 1:
            features['rsi_lag_1'] = history_rsi[-1]
            features['rsi_change'] = features['rsi'] - history_rsi[-1]
        else:
            features['rsi_lag_1'] = features['rsi']
            features['rsi_change'] = 0.0
        
        # Lag 2
        if len(history_rsi) >= 2:
            features['rsi_lag_2'] = history_rsi[-2]
        else:
            features['rsi_lag_2'] = features['rsi']
        
        # Lag 3
        if len(history_rsi) >= 3:
            features['rsi_lag_3'] = history_rsi[-3]
        else:
            features['rsi_lag_3'] = features['rsi']
        
        # MACD lags
        if len(history_macd) >= 1:
            features['macd_lag_1'] = history_macd[-1]
            features['macd_change'] = features['macd'] - history_macd[-1]
        else:
            features['macd_lag_1'] = features['macd']
            features['macd_change'] = 0.0
        
        if len(history_macd) >= 2:
            features['macd_lag_2'] = history_macd[-2]
        else:
            features['macd_lag_2'] = features['macd']
        
        if len(history_macd) >= 3:
            features['macd_lag_3'] = history_macd[-3]
        else:
            features['macd_lag_3'] = features['macd']
        
        # Volume lags
        if len(history_volume) >= 1:
            features['volume_ratio_lag_1'] = history_volume[-1]
            features['volume_trend'] = features['volume_ratio'] - history_volume[-1]
            features['volume_change_1'] = features['volume_ratio'] - history_volume[-1]
        else:
            features['volume_ratio_lag_1'] = features['volume_ratio']
            features['volume_trend'] = 0.0
            features['volume_change_1'] = 0.0
        
        # Volatility lags
        if len(history_volatility) >= 1:
            features['volatility_lag_1'] = history_volatility[-1]
            features['volatility_change'] = features['volatility'] - history_volatility[-1]
        else:
            features['volatility_lag_1'] = features['volatility']
            features['volatility_change'] = 0.0
        
        # Price changes
        if len(history_price) >= 1 and entry_price > 0 and history_price[-1] > 0:
            features['price_change_1'] = (entry_price - history_price[-1]) / history_price[-1]
        else:
            features['price_change_1'] = 0.0
        
        if len(history_price) >= 3 and entry_price > 0 and history_price[-3] > 0:
            features['price_change_3'] = (entry_price - history_price[-3]) / history_price[-3]
        else:
            features['price_change_3'] = 0.0
        
        # Сохраняем текущие значения в историю (храним последние 3)
        history_rsi.append(features['rsi'])
        history_macd.append(features['macd'])
        history_volume.append(features['volume_ratio'])
        history_volatility.append(features['volatility'])
        history_price.append(entry_price)
        
        # Ограничиваем размер истории
        if len(history_rsi) > 3:
            history_rsi.pop(0)
            history_macd.pop(0)
            history_volume.pop(0)
            history_volatility.pop(0)
            history_price.pop(0)
        
        X_list.append(features)
        
        # ⚡ ЭКСПЕРТНАЯ РАЗМЕТКА (Дмитрий): Использование продвинутых меток если есть
        # Target: classification
        if 'bin' in pattern:
            # Если есть Triple Barrier Labeling
            y_class.append(1 if pattern['bin'] > 0 else 0)
        else:
            # Fallback на результат сделки
            result = pattern.get('result', 'LOSS')
            y_class.append(1 if result == 'WIN' else 0)
        
        # Target: regression
        profit_pct = pattern.get('profit_pct', 0.0)
        if profit_pct is None:
            profit_pct = 0.0
        y_reg.append(float(profit_pct))

    # Создаем DataFrame
    X = pd.DataFrame(X_list)[FEATURE_NAMES]
    y_class = np.array(y_class)
    y_reg = np.array(y_reg)
    
    logger.info(f"✅ Подготовлено {len(X)} samples с {len(FEATURE_NAMES)} features")
    return X, y_class, y_reg
    
    # Создаем DataFrame
    X = pd.DataFrame(X_list)[FEATURE_NAMES]
    y_class = np.array(y_class)
    y_reg = np.array(y_reg)
    
    logger.info(f"✅ Подготовлено {len(X)} samples с {len(FEATURE_NAMES)} features")
    logger.info(f"   WIN: {y_class.sum()} ({y_class.mean()*100:.1f}%)")
    logger.info(f"   LOSS: {len(y_class) - y_class.sum()} ({(1-y_class.mean())*100:.1f}%)")
    
    return X, y_class, y_reg

def train_models(X, y_class, y_reg, use_purged_cv=True):
    """
    Обучает classifier и regressor
    
    Args:
        X: Features DataFrame
        y_class: Classification targets
        y_reg: Regression targets
        use_purged_cv: Использовать Purged K-Fold CV (предотвращает data leakage)
    """
    logger.info("\n🤖 Обучение моделей...")
    
    # 📊 PURGED K-FOLD CV (Дмитрий - после обучения 30% программы)
    # Предотвращает data leakage в временных рядах
    if use_purged_cv:
        try:
            # Пытаемся извлечь timestamps из индекса или создать из паттернов
            # Для retrain_lightgbm.py timestamps могут быть в паттернах
            from purged_k_fold import purged_train_test_split
            
            # Пробуем получить timestamps (если есть в данных)
            timestamps = None
            if hasattr(X, 'index') and isinstance(X.index, pd.DatetimeIndex):
                timestamps = pd.Series(X.index)
            elif 'timestamp' in X.columns:
                # Если timestamp в features, извлекаем
                timestamps = pd.to_datetime(X['timestamp'], errors='coerce')
            
            logger.info("📊 Используем Purged K-Fold CV для предотвращения data leakage...")
            X_train, X_test, y_class_train, y_class_test = purged_train_test_split(
                X, y_class,
                test_size=0.2,
                purge_gap=1,  # Удаляем 1 период между train/test
                embargo_pct=0.01,  # 1% embargo
                timestamps=timestamps
            )
            
            # Для regression используем те же индексы
            if isinstance(X_train, pd.DataFrame):
                train_idx = X_train.index
                test_idx = X_test.index
            else:
                # Если не DataFrame, используем позиционные индексы
                train_idx = np.arange(len(X_train))
                test_idx = np.arange(len(X_train), len(X_train) + len(X_test))
            
            y_reg_train = y_reg[train_idx]
            y_reg_test = y_reg[test_idx]
            
            logger.info(f"   ✅ Purged CV: train={len(X_train)}, test={len(X_test)}")
            logger.info(f"   📊 Purged samples предотвращают data leakage")
            
        except ImportError:
            logger.warning("⚠️ purged_k_fold не доступен, используем стандартный split")
            use_purged_cv = False
    
    # Fallback: стандартный split
    if not use_purged_cv:
        X_train, X_test, y_class_train, y_class_test, y_reg_train, y_reg_test = train_test_split(
            X, y_class, y_reg, test_size=0.2, random_state=42, stratify=y_class
        )
    
    logger.info(f"   Train: {len(X_train)} samples")
    logger.info(f"   Test: {len(X_test)} samples")
    
    # ==================== SAMPLE WEIGHTS ====================
    # Добавлено после обучения 5% программы (Ernest Chan)
    from sklearn.utils.class_weight import compute_sample_weight
    
    sample_weights_train = compute_sample_weight(
        class_weight='balanced',
        y=y_class_train
    )
    logger.info(f"   Sample weights computed for class imbalance")
    logger.info(f"   Min weight: {sample_weights_train.min():.3f}, Max weight: {sample_weights_train.max():.3f}")
    
    # ==================== CLASSIFIER ====================
    logger.info("\n📊 Обучение Classifier...")
    
    # Балансировка классов
    scale_pos_weight = (len(y_class_train) - y_class_train.sum()) / y_class_train.sum()
    logger.info(f"   Scale pos weight: {scale_pos_weight:.2f}")
    
    train_data_class = lgb.Dataset(X_train, label=y_class_train, weight=sample_weights_train)
    test_data_class = lgb.Dataset(X_test, label=y_class_test, reference=train_data_class)
    
    params_class = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'scale_pos_weight': scale_pos_weight,  # Балансировка
        'min_child_samples': 20,
        'max_depth': 7,
    }
    
    classifier = lgb.train(
        params_class,
        train_data_class,
        num_boost_round=500,
        valid_sets=[test_data_class],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=100)]
    )
    
    # Метрики classifier
    y_pred_class = (classifier.predict(X_test) > 0.5).astype(int)
    y_pred_proba = classifier.predict(X_test)
    
    class_metrics = {
        'roc_auc': roc_auc_score(y_class_test, y_pred_proba),
        'accuracy': accuracy_score(y_class_test, y_pred_class),
        'precision': precision_score(y_class_test, y_pred_class, zero_division=0),
        'recall': recall_score(y_class_test, y_pred_class, zero_division=0),
        'f1_score': f1_score(y_class_test, y_pred_class, zero_division=0)
    }
    
    logger.info("\n✅ Classifier метрики:")
    for key, value in class_metrics.items():
        logger.info(f"   {key}: {value:.4f}")
    
    # ==================== REGRESSOR ====================
    logger.info("\n📊 Обучение Regressor...")
    
    # ЭКСПЕРТНАЯ ОПТИМИЗАЦИЯ (Дмитрий): Веса на основе абсолютного профита для регрессора
    # Сделки с большим движением цены более важны для обучения
    sample_weights_reg = np.abs(y_reg_train) + 1.0
    sample_weights_reg = sample_weights_reg / sample_weights_reg.mean()
    
    train_data_reg = lgb.Dataset(X_train, label=y_reg_train, weight=sample_weights_reg)
    test_data_reg = lgb.Dataset(X_test, label=y_reg_test, reference=train_data_reg)
    
    params_reg = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'min_child_samples': 20,
        'max_depth': 7,
    }
    
    regressor = lgb.train(
        params_reg,
        train_data_reg,
        num_boost_round=500,
        valid_sets=[test_data_reg],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=100)]
    )
    
    # Метрики regressor
    y_pred_reg = regressor.predict(X_test)
    
    reg_metrics = {
        'mae': mean_absolute_error(y_reg_test, y_pred_reg),
        'rmse': np.sqrt(mean_squared_error(y_reg_test, y_pred_reg)),
        'r2': r2_score(y_reg_test, y_pred_reg)
    }
    
    logger.info("\n✅ Regressor метрики:")
    for key, value in reg_metrics.items():
        logger.info(f"   {key}: {value:.4f}")
    
    # Feature importance
    logger.info("\n📊 Feature Importance (Top 10):")
    importance = classifier.feature_importance(importance_type='gain')
    feature_importance = sorted(zip(FEATURE_NAMES, importance), key=lambda x: x[1], reverse=True)
    for feature, imp in feature_importance[:10]:
        logger.info(f"   {feature}: {imp:.0f}")
    
    return classifier, regressor, class_metrics, reg_metrics

def save_models(classifier, regressor, class_metrics, reg_metrics):
    """Сохраняет модели и метаданные"""
    logger.info(f"\n💾 Сохранение моделей в {MODEL_DIR}...")
    
    # Сохраняем модели
    classifier.save_model(str(MODEL_DIR / "classifier.txt"))
    regressor.save_model(str(MODEL_DIR / "regressor.txt"))
    
    # Метаданные
    metadata = {
        'feature_names': FEATURE_NAMES,
        'training_metrics': {
            'classifier': class_metrics,
            'regressor': reg_metrics
        },
        'trained_at': get_utc_now().isoformat()
    }
    
    with open(MODEL_DIR / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    logger.info("✅ Модели сохранены!")
    logger.info(f"   - {MODEL_DIR / 'classifier.txt'}")
    logger.info(f"   - {MODEL_DIR / 'regressor.txt'}")
    logger.info(f"   - {MODEL_DIR / 'metadata.json'}")

def main():
    # 1. Загрузка паттернов
    patterns = load_patterns()
    
    # 2. Подготовка датасета
    X, y_class, y_reg = prepare_dataset(patterns)
    
    if len(X) < 100:
        logger.error("❌ Недостаточно данных для обучения")
        sys.exit(1)
    
    # 3. Обучение
    classifier, regressor, class_metrics, reg_metrics = train_models(X, y_class, y_reg)
    
    # 4. Сохранение
    save_models(classifier, regressor, class_metrics, reg_metrics)
    
    logger.info("=" * 80)
    logger.info("✅ ПЕРЕОБУЧЕНИЕ ЗАВЕРШЕНО!")
    logger.info("=" * 80)
    logger.info(f"\n📊 Итоговые метрики:")
    logger.info(f"   ROC AUC: {class_metrics['roc_auc']:.4f}")
    logger.info(f"   Accuracy: {class_metrics['accuracy']:.4f}")
    logger.info(f"   Precision: {class_metrics['precision']:.4f}")
    logger.info(f"   Recall: {class_metrics['recall']:.4f}")
    logger.info(f"   F1 Score: {class_metrics['f1_score']:.4f}")
    logger.info(f"\n   Regressor MAE: {reg_metrics['mae']:.4f}")
    logger.info(f"   Regressor RMSE: {reg_metrics['rmse']:.4f}")
    logger.info(f"   Regressor R²: {reg_metrics['r2']:.4f}")
    logger.info("\n🎯 Модели готовы к использованию!")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()

