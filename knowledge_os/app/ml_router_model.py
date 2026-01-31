"""
ML Router Model
ML-модель для предсказания оптимального маршрута (local/cloud)
"""

import logging
import pickle
import os
from typing import Optional, Dict, Any, List
import numpy as np

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    try:
        import xgboost as xgb
        XGBOOST_AVAILABLE = True
    except ImportError:
        XGBOOST_AVAILABLE = False
        logger.warning("Neither LightGBM nor XGBoost available. Install one: pip install lightgbm or pip install xgboost")

class MLRouterModel:
    """
    ML-модель для предсказания оптимального маршрута.
    Использует LightGBM или XGBoost для классификации.
    """
    
    def __init__(self, model_type: str = "lightgbm"):
        """
        Args:
            model_type: Тип модели ("lightgbm" или "xgboost")
        """
        self.model_type = model_type
        self.model = None
        self.feature_names = [
            'task_type_coding',
            'task_type_reasoning',
            'task_type_general',
            'prompt_length',
            'category_coding',
            'category_reasoning',
            'category_fast',
            'category_other',
            'node_mac_performance',
            'node_server_performance',
            'node_mac_success_rate',
            'node_server_success_rate'
        ]
        self.label_encoder = {
            'local_mac': 0,
            'local_server': 1,
            'cloud': 2
        }
        self.reverse_label_encoder = {v: k for k, v in self.label_encoder.items()}
    
    def _encode_features(self, task_type: str, prompt_length: int, category: Optional[str], 
                        node_metrics: Optional[Dict[str, Any]] = None) -> np.ndarray:
        """Кодирует features для модели"""
        features = np.zeros(len(self.feature_names))
        
        # Task type (one-hot encoding)
        if task_type == "coding":
            features[0] = 1
        elif task_type == "reasoning":
            features[1] = 1
        else:
            features[2] = 1
        
        # Prompt length (normalized)
        features[3] = min(prompt_length / 5000.0, 1.0)  # Normalize to 0-1
        
        # Category (one-hot encoding)
        if category == "coding":
            features[4] = 1
        elif category == "reasoning":
            features[5] = 1
        elif category == "fast":
            features[6] = 1
        else:
            features[7] = 1
        
        # Node metrics
        if node_metrics:
            features[8] = node_metrics.get('local_mac', {}).get('avg_performance', 0.8)
            features[9] = node_metrics.get('local_server', {}).get('avg_performance', 0.8)
            features[10] = node_metrics.get('local_mac', {}).get('success_rate', 0.9)
            features[11] = node_metrics.get('local_server', {}).get('success_rate', 0.9)
        else:
            # Default values
            features[8] = 0.8
            features[9] = 0.8
            features[10] = 0.9
            features[11] = 0.9
        
        return features
    
    def train(self, X: np.ndarray, y: np.ndarray, validation_split: float = 0.2):
        """
        Обучает модель на данных.
        
        Args:
            X: Features (n_samples, n_features)
            y: Labels (n_samples,) - encoded route labels
            validation_split: Доля данных для валидации
        """
        if not LIGHTGBM_AVAILABLE and not XGBOOST_AVAILABLE:
            raise ImportError("No ML library available. Install lightgbm or xgboost")
        
        # Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        if self.model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            # LightGBM
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
            
            params = {
                'objective': 'multiclass',
                'num_class': 3,
                'metric': 'multi_logloss',
                'boosting_type': 'gbdt',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.9,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'verbose': -1
            }
            
            self.model = lgb.train(
                params,
                train_data,
                valid_sets=[val_data],
                num_boost_round=100,
                callbacks=[lgb.early_stopping(stopping_rounds=10), lgb.log_evaluation(period=0)]
            )
        elif self.model_type == "xgboost" and XGBOOST_AVAILABLE:
            # XGBoost
            self.model = xgb.XGBClassifier(
                objective='multi:softprob',
                num_class=3,
                max_depth=6,
                learning_rate=0.05,
                n_estimators=100,
                eval_metric='mlogloss'
            )
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=10,
                verbose=False
            )
        else:
            raise ValueError(f"Model type {self.model_type} not available")
        
        logger.info(f"✅ [ML MODEL] Trained {self.model_type} model on {len(X_train)} samples")
    
    def predict(self, task_type: str, prompt_length: int, category: Optional[str] = None,
                node_metrics: Optional[Dict[str, Any]] = None) -> tuple:
        """
        Предсказывает оптимальный маршрут.
        
        Args:
            task_type: Тип задачи (coding, reasoning, general)
            prompt_length: Длина промпта
            category: Категория задачи
            node_metrics: Метрики узлов (performance, success_rate)
        
        Returns:
            (predicted_route, confidence)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        # Encode features
        features = self._encode_features(task_type, prompt_length, category, node_metrics)
        features = features.reshape(1, -1)
        
        # Predict
        if self.model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            probs = self.model.predict(features, num_iteration=self.model.best_iteration)
            if len(probs.shape) > 1:
                probs = probs[0]
            predicted_class = np.argmax(probs)
            confidence = float(probs[predicted_class])
        elif self.model_type == "xgboost" and XGBOOST_AVAILABLE:
            probs = self.model.predict_proba(features)[0]
            predicted_class = np.argmax(probs)
            confidence = float(probs[predicted_class])
        else:
            raise ValueError(f"Model type {self.model_type} not available")
        
        predicted_route = self.reverse_label_encoder[predicted_class]
        
        return predicted_route, confidence
    
    def save(self, filepath: str):
        """Сохраняет модель в файл"""
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        model_data = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'label_encoder': self.label_encoder,
            'reverse_label_encoder': self.reverse_label_encoder
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"✅ [ML MODEL] Saved model to {filepath}")
    
    def load(self, filepath: str):
        """Загружает модель из файла"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file not found: {filepath}")
        
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.model_type = model_data['model_type']
        self.feature_names = model_data['feature_names']
        self.label_encoder = model_data['label_encoder']
        self.reverse_label_encoder = model_data['reverse_label_encoder']
        
        logger.info(f"✅ [ML MODEL] Loaded model from {filepath}")

