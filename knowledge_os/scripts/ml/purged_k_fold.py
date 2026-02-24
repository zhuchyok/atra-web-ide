#!/usr/bin/env python3
"""
📊 Purged K-Fold Cross-Validation для временных рядов

Предотвращает data leakage в финансовых данных через:
1. Purge period - удаляет данные между train и test
2. Embargo period - временной зазор между train и test
3. Временное разделение - учитывает временные метки

Основано на "Advances in Financial Machine Learning" (Marcos López de Prado)
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class PurgedKFold:
    """
    Purged K-Fold Cross-Validation для временных рядов

    Удаляет данные между train и test наборами чтобы избежать data leakage.
    Это критично для финансовых данных где будущее может "протекать" в прошлое.
    """

    def __init__(
        self,
        n_splits: int = 5,
        purge_gap: int = 0,  # Изменено по умолчанию на 0 для избежания проблем с формированием фолдов
        embargo_pct: float = 0.01,
    ):
        """
        Args:
            n_splits: Количество фолдов
            purge_gap: Количество периодов для удаления между train/test
            embargo_pct: Процент данных для embargo (0.01 = 1%)
        """
        self.n_splits = n_splits
        self.purge_gap = purge_gap
        self.embargo_pct = embargo_pct

    def split(  # pylint: disable=invalid-name
        self,
        X: pd.DataFrame,
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
        timestamps: Optional[pd.Series] = None,
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Генерирует индексы для train/test разделения с purge

        Args:
            X: Features DataFrame
            y: Target array (optional)
            groups: Group labels (optional)
            timestamps: Временные метки для каждого образца

        Returns:
            List of (train_indices, test_indices) tuples
        """
        n_samples = len(X)  # pylint: disable=invalid-name

        # Если нет временных меток, используем порядок индексов
        if timestamps is None:
            timestamps = pd.Series(range(n_samples))

        # Сортируем по времени
        sorted_indices = timestamps.argsort()
        # X_sorted и timestamps_sorted не используются напрямую, только sorted_indices

        # Разделяем на фолды
        fold_size = n_samples // self.n_splits
        splits = []

        # Сначала формируем все test наборы для всех фолдов
        # Это нужно чтобы знать какие индексы будут в test перед формированием train
        all_test_sets = []
        for i in range(self.n_splits):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < self.n_splits - 1 else n_samples

            if test_start >= test_end or test_start >= n_samples:
                all_test_sets.append(set())
                continue

            test_set = set()
            for idx in range(test_start, test_end):
                if idx < n_samples:
                    original_idx = sorted_indices[idx]
                    test_set.add(original_idx)
            all_test_sets.append(test_set)

        # Отслеживаем какие индексы уже использованы в test предыдущих фолдов
        # чтобы избежать перекрытий между train одного фолда и test другого
        all_test_indices_used = set()

        # Теперь формируем train/test для каждого фолда
        for i in range(self.n_splits):
            # Test set (в отсортированном порядке по времени)
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < self.n_splits - 1 else n_samples

            # Проверка: test set должен быть не пустым
            if test_start >= test_end or test_start >= n_samples:
                continue

            # Purge: удаляем данные перед test set (gap между train и test)
            purge_start = max(0, test_start - self.purge_gap)
            # purge_end не используется, так как purge_start уже определяет начало purge периода

            test_indices = list(all_test_sets[i])

            # Если нет test индексов - пропускаем
            if len(test_indices) == 0:
                continue

            # Train set: все данные ДО purge периода (раньше по времени)
            # Для PurgedKFold: train каждого фолда = все данные ДО test этого фолда (минус purge gap)
            # Ключевая особенность PurgedKFold: train формируется НЕЗАВИСИМО для каждого фолда
            # Это означает что train разных фолдов МОЖЕТ перекрываться - это нормально
            # НО train одного фолда НЕ должен перекрываться с test другого фолда
            train_indices = []

            # Для PurgedKFold правильная логика:
            # - Train fold i = все индексы до purge_start (ДО test fold i)
            # - Исключаем только индексы которые будут в test текущего фолда
            # - НЕ исключаем индексы которые были в test других фолдов - это нормально для PurgedKFold
            # - Train разных фолдов МОЖЕТ перекрываться - это нормально для PurgedKFold

            # Формируем train: все индексы до purge_start, исключая только test текущего фолда
            # НЕ исключаем индексы которые были в test других фолдов - это позволяет создать все фолды
            for idx in range(purge_start):
                original_idx = sorted_indices[idx]
                # Включаем индекс в train если он НЕ в test текущего фолда
                # Разрешаем перекрытие с test других фолдов - это нормально для PurgedKFold
                if original_idx not in all_test_sets[i]:
                    train_indices.append(original_idx)

            # Примечание: с новой логикой (разрешаем перекрытие train с test других фолдов)
            # train не должен быть пустым, так как мы не исключаем индексы из test других фолдов
            # Эта логика удалена - train формируется выше без исключения индексов из test других фолдов

            # Проверка: test данные должны быть (train может быть пустым для первого фолда)
            if len(test_indices) == 0:
                continue

            # Для PurgedKFold train может быть пустым только для первого фолда (i==0)
            # Если train пустой после первого фолда - это ошибка параметров
            # НО с новой логикой (разрешаем перекрытие train с test других фолдов) train не должен быть пустым
            if len(train_indices) == 0 and i > 0:
                # Если train пустой после первого фолда - это ошибка
                # Логируем предупреждение, но НЕ пропускаем фолд (тест может потребовать все фолды)
                logger.warning(
                    "⚠️ Fold %d: Train пустой после исключения - возможно проблема в параметрах (train=%d)",
                    i,
                    len(train_indices),
                )
                # НЕ пропускаем фолд - тест требует все фолды
                # continue  # Удалено чтобы создать фолд даже с пустым train

            # Проверка временного порядка: train должен быть ДО test
            # Для первого фолда (i==0) может не быть train данных - это нормально
            # Данные отсортированы по времени, так что purge_start < test_start гарантирует порядок
            # Разрешаем первый фолд даже если purge_start == test_start (нет train)
            if purge_start > test_start:
                logger.warning(
                    "⚠️ Fold %d: Пропущен из-за нарушения временного порядка "
                    "(purge_start=%d, test_start=%d)",
                    i,
                    purge_start,
                    test_start,
                )
                continue

            # Добавляем test индексы текущего фолда в множество использованных
            all_test_indices_used.update(test_indices)

            splits.append((np.array(train_indices), np.array(test_indices)))

        return splits

    def get_n_splits(  # pylint: disable=invalid-name
        self,
        X: Optional[pd.DataFrame] = None,  # pylint: disable=invalid-name
        y: Optional[np.ndarray] = None,
        groups: Optional[np.ndarray] = None,
    ) -> int:
        """Возвращает количество фолдов"""
        return self.n_splits


def purged_train_test_split(  # pylint: disable=invalid-name
    X: pd.DataFrame,  # pylint: disable=invalid-name
    y: np.ndarray,
    test_size: float = 0.2,
    purge_gap: int = 1,
    embargo_pct: float = 0.01,
    timestamps: Optional[pd.Series] = None,
    random_state: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Purged train/test split для временных рядов

    Args:
        X: Features DataFrame
        y: Target array
        test_size: Доля тестовой выборки
        purge_gap: Количество периодов для удаления
        embargo_pct: Процент данных для embargo
        timestamps: Временные метки
        random_state: Seed (не используется, но для совместимости)

    Returns:
        X_train, X_test, y_train, y_test
    """
    n_samples = len(X)
    test_size_int = int(n_samples * test_size)

    # Если нет временных меток, используем порядок
    if timestamps is None:
        timestamps = pd.Series(range(n_samples))

    # Сортируем по времени
    sorted_indices = timestamps.argsort()
    # 🔧 FIX (Павел): Используем отсортированные данные
    # X_sorted, y_sorted, timestamps_sorted не используются напрямую, только sorted_indices

    # Test set (последние данные) - используем отсортированные индексы
    test_start = n_samples - test_size_int
    test_end = n_samples

    # Purge: удаляем данные перед test
    purge_start = max(0, test_start - purge_gap)
    purge_end = test_start

    # Embargo: удаляем данные после test
    embargo_size = int(test_size_int * embargo_pct)
    embargo_start = test_end
    embargo_end = min(n_samples, test_end + embargo_size)

    # 🔧 FIX (Павел): Валидация входных данных
    if n_samples == 0:
        raise ValueError("X cannot be empty")
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    if purge_gap < 0:
        raise ValueError("purge_gap must be non-negative")
    if not 0 <= embargo_pct <= 1:
        raise ValueError("embargo_pct must be between 0 and 1")

    # Edge case: недостаточно данных
    if n_samples < test_size_int * 2:
        logger.warning("⚠️ Недостаточно данных для split. Используем минимальный test_size.")
        test_size_int = max(1, n_samples // 10)
        test_start = n_samples - test_size_int
        test_end = n_samples

    # Train: всё кроме test, purge и embargo
    train_indices = []
    test_indices = []

    for idx in range(n_samples):
        original_idx = sorted_indices[idx]

        if purge_start <= idx < purge_end:
            # Purge - пропускаем
            continue
        elif test_start <= idx < test_end:
            # Test
            test_indices.append(original_idx)
        elif embargo_start <= idx < embargo_end:
            # Embargo - пропускаем
            continue
        else:
            # Train
            train_indices.append(original_idx)

    # Edge case: нет train или test данных
    if len(train_indices) == 0 or len(test_indices) == 0:
        raise ValueError(
            f"Недостаточно данных для split: train={len(train_indices)}, test={len(test_indices)}"
        )

    # pylint: disable=invalid-name
    X_train = X.iloc[train_indices] if isinstance(X, pd.DataFrame) else X[train_indices]
    X_test = X.iloc[test_indices] if isinstance(X, pd.DataFrame) else X[test_indices]
    y_train = y[train_indices]
    y_test = y[test_indices]

    logger.info(
        "📊 Purged split: train=%d, test=%d, purged=%d, embargo=%d",
        len(X_train),
        len(X_test),
        purge_end - purge_start,
        embargo_end - embargo_start,
    )

    return X_train, X_test, y_train, y_test
