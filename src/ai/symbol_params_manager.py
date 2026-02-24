"""
🎯 МЕНЕДЖЕР ПАРАМЕТРОВ МОНЕТ
Автоматически добавляет новые монеты с базовыми параметрами,
запускает оптимизацию и блокирует генерацию сигналов до завершения
"""

import asyncio
import glob
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.shared.utils.datetime_utils import get_utc_now  # type: ignore

logger = logging.getLogger(__name__)

# Путь к файлу параметров
PARAMS_FILE_PATTERN = "backtests/optimize_intelligent_params_*.json"
PARAMS_DIR = Path("backtests")
LOCK_FILE_PATTERN = "backtests/optimization_lock_{symbol}.lock"
OPTIMIZATION_STATUS_FILE = "backtests/optimization_status.json"

# Базовые параметры для новых монет
DEFAULT_PARAMS = {
    "volume_ratio": 0.4,
    "rsi_oversold": 40,
    "rsi_overbought": 60,
    "trend_strength": 0.15,
    "quality_score": 0.65,
    "momentum_threshold": -5.0,
}

# Статусы оптимизации
STATUS_PENDING = "pending"  # Ожидает оптимизации
STATUS_OPTIMIZING = "optimizing"  # В процессе оптимизации
STATUS_OPTIMIZED = "optimized"  # Оптимизирована
STATUS_FAILED = "failed"  # Ошибка оптимизации


class SymbolParamsManager:
    """Управляет параметрами монет и автоматической оптимизацией"""

    # 🔥 ОГРАНИЧЕНИЕ: Максимум 3 параллельные оптимизации, чтобы не вешать сервер
    _semaphore = asyncio.Semaphore(3)

    def __init__(self):
        self.params_cache: Dict[str, Dict[str, Any]] = {}
        self.optimization_status: Dict[str, Dict[str, Any]] = {}
        self._load_status()

    def _load_status(self):
        """Загружает статус оптимизации"""
        if os.path.exists(OPTIMIZATION_STATUS_FILE):
            try:
                with open(OPTIMIZATION_STATUS_FILE, encoding="utf-8") as f:
                    self.optimization_status = json.load(f)
            except Exception as e:
                logger.warning("⚠️ Ошибка загрузки статуса оптимизации: %s", e)
                self.optimization_status = {}

    def _save_status(self):
        """Сохраняет статус оптимизации"""
        try:
            with open(OPTIMIZATION_STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.optimization_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("❌ Ошибка сохранения статуса оптимизации: %s", e)

    def _get_latest_params_file(self) -> Optional[Path]:
        """Находит последний файл параметров"""
        json_files = sorted(glob.glob(PARAMS_FILE_PATTERN), reverse=True)
        if json_files:
            return Path(json_files[0])
        return None

    def _load_params_from_file(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Загружает параметры для монеты из файла"""
        params_file = self._get_latest_params_file()
        if not params_file:
            return None

        try:
            with open(params_file, encoding="utf-8") as f:
                data = json.load(f)
                if symbol in data:
                    symbol_data = data[symbol]
                    return symbol_data.get("best_params", {})
        except Exception as e:
            logger.debug("⚠️ Ошибка загрузки параметров для %s: %s", symbol, e)

        return None

    def _add_symbol_with_defaults(self, symbol: str) -> Dict[str, Any]:
        """Добавляет монету с базовыми параметрами в файл"""
        params_file = self._get_latest_params_file()

        # Если файла нет, создаем новый
        if not params_file:
            params_file = (
                PARAMS_DIR
                / f"optimize_intelligent_params_{get_utc_now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            data = {}
        else:
            try:
                with open(params_file, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        # Добавляем монету с базовыми параметрами
        data[symbol] = {
            "symbol": symbol,
            "best_params": DEFAULT_PARAMS.copy(),
            "status": STATUS_PENDING,
            "added_at": get_utc_now().isoformat(),
            "optimized_at": None,
            "best_result": None,
        }

        # Сохраняем
        try:
            with open(params_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ [%s] Добавлена с базовыми параметрами", symbol)
        except Exception as e:
            logger.error("❌ [%s] Ошибка сохранения параметров: %s", symbol, e)

        # Обновляем статус
        self.optimization_status[symbol] = {
            "status": STATUS_PENDING,
            "added_at": get_utc_now().isoformat(),
            "optimized_at": None,
        }
        self._save_status()

        return data[symbol]["best_params"]

    def _check_lock_file(self, symbol: str) -> bool:
        """Проверяет наличие lock-файла (оптимизация в процессе)"""
        lock_file = Path(LOCK_FILE_PATTERN.format(symbol=symbol))
        return lock_file.exists()

    def _create_lock_file(self, symbol: str):
        """Создает lock-файл"""
        lock_file = Path(LOCK_FILE_PATTERN.format(symbol=symbol))
        try:
            lock_file.touch()
        except Exception as e:
            logger.error("❌ [%s] Ошибка создания lock-файла: %s", symbol, e)

    def _remove_lock_file(self, symbol: str):
        """Удаляет lock-файл"""
        lock_file = Path(LOCK_FILE_PATTERN.format(symbol=symbol))
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            logger.error("❌ [%s] Ошибка удаления lock-файла: %s", symbol, e)

    async def _run_optimization(self, symbol: str) -> bool:
        """Запускает оптимизацию параметров для монеты"""
        async with self._semaphore:
            logger.info("🚀 [%s] Запуск оптимизации параметров...", symbol)

        # Обновляем статус
        self.optimization_status[symbol] = {
            "status": STATUS_OPTIMIZING,
            "added_at": self.optimization_status.get(symbol, {}).get(
                "added_at", get_utc_now().isoformat()
            ),
            "optimized_at": None,
            "started_at": get_utc_now().isoformat(),
        }
        self._save_status()

        # Создаем lock-файл
        self._create_lock_file(symbol)

        try:
            # Запускаем скрипт оптимизации
            script_path = Path("scripts/optimize_intelligent_params.py")
            if not script_path.exists():
                logger.error("❌ [%s] Скрипт оптимизации не найден: %s", symbol, script_path)
                return False

            # Запускаем в фоне
            process = await asyncio.create_subprocess_exec(
                "python3",
                str(script_path),
                "--symbol",
                symbol,
                "--period",
                "30",  # 30 дней для быстрой оптимизации
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Ждем завершения (с таймаутом 2 часа)
            try:
                _, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=7200,  # 2 часа
                )
                return_code = process.returncode

                if return_code == 0:
                    logger.info("✅ [%s] Оптимизация завершена успешно", symbol)
                    self.optimization_status[symbol] = {
                        "status": STATUS_OPTIMIZED,
                        "added_at": self.optimization_status.get(symbol, {}).get(
                            "added_at", get_utc_now().isoformat()
                        ),
                        "optimized_at": get_utc_now().isoformat(),
                    }
                    self._save_status()
                    return True
                else:
                    logger.error(
                        "❌ [%s] Ошибка оптимизации (код %d): %s",
                        symbol,
                        return_code,
                        stderr.decode(),
                    )
                    self.optimization_status[symbol] = {
                        "status": STATUS_FAILED,
                        "added_at": self.optimization_status.get(symbol, {}).get(
                            "added_at", get_utc_now().isoformat()
                        ),
                        "optimized_at": None,
                        "error": stderr.decode()[:200],  # Первые 200 символов ошибки
                    }
                    self._save_status()
                    return False

            except asyncio.TimeoutError:
                logger.error("❌ [%s] Таймаут оптимизации (2 часа)", symbol)
                process.kill()
                self.optimization_status[symbol] = {
                    "status": STATUS_FAILED,
                    "added_at": self.optimization_status.get(symbol, {}).get(
                        "added_at", get_utc_now().isoformat()
                    ),
                    "optimized_at": None,
                    "error": "Timeout (2 hours)",
                }
                self._save_status()
                return False

        except Exception as e:
            logger.error("❌ [%s] Ошибка запуска оптимизации: %s", symbol, e)
            self.optimization_status[symbol] = {
                "status": STATUS_FAILED,
                "added_at": self.optimization_status.get(symbol, {}).get(
                    "added_at", get_utc_now().isoformat()
                ),
                "optimized_at": None,
                "error": str(e)[:200],
            }
            self._save_status()
            return False
        finally:
            # Удаляем lock-файл
            self._remove_lock_file(symbol)

    def get_symbol_params(self, symbol: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Получает параметры для монеты

        Returns:
            Tuple[params, is_optimized]:
            - params: Параметры монеты или None
            - is_optimized: True если монета оптимизирована, False если в процессе или не оптимизирована
        """
        # Проверяем кэш
        if symbol in self.params_cache:
            status = self.optimization_status.get(symbol, {}).get("status", STATUS_PENDING)
            is_optimized = status == STATUS_OPTIMIZED
            return self.params_cache[symbol], is_optimized

        # Загружаем из файла
        params = self._load_params_from_file(symbol)

        if params:
            # Параметры найдены
            self.params_cache[symbol] = params
            # 🔧 ИСПРАВЛЕНО: Если статус не установлен, считаем монету не оптимизированной (STATUS_PENDING)
            status = self.optimization_status.get(symbol, {}).get("status", STATUS_PENDING)
            is_optimized = status == STATUS_OPTIMIZED
            return params, is_optimized

        # Параметры не найдены - монета новая
        return None, False

    async def ensure_symbol_optimized(self, symbol: str) -> Tuple[Dict[str, Any], bool]:
        """
        Обеспечивает наличие оптимизированных параметров для монеты

        Если монеты нет - добавляет с базовыми параметрами и запускает оптимизацию

        Returns:
            Tuple[params, is_ready]:
            - params: Параметры монеты (базовые или оптимизированные)
            - is_ready: True если монета готова для генерации сигналов (оптимизирована)
        """
        # Проверяем наличие параметров
        params, is_optimized = self.get_symbol_params(symbol)

        if params and is_optimized:
            # Монета оптимизирована - готова
            return params, True

        if params and not is_optimized:
            # Параметры есть, но не оптимизированы
            status_info = self.optimization_status.get(symbol, {})
            status = status_info.get("status", STATUS_PENDING)

            if status == STATUS_OPTIMIZING:
                # Оптимизация в процессе - РАЗРЕШАЕМ использование базовых параметров
                # чтобы не ждать часами завершения бэктестов.
                return params, True

            if status == STATUS_FAILED:
                # Оптимизация провалилась - используем базовые параметры
                logger.warning(
                    "⚠️ [%s] Оптимизация провалилась, используем базовые параметры", symbol
                )
                return params, True  # Разрешаем использовать базовые параметры

        # Монеты нет - добавляем с базовыми параметрами
        logger.info("🆕 [%s] Новая монета, добавляем с базовыми параметрами", symbol)
        params = self._add_symbol_with_defaults(symbol)

        # Запускаем оптимизацию в фоне (не блокируем)
        if not self._check_lock_file(symbol):
            # Создаем задачу для оптимизации
            asyncio.create_task(self._run_optimization(symbol))
        else:
            logger.debug("⏳ [%s] Оптимизация уже запущена", symbol)

        # Возвращаем базовые параметры, разрешаем использование до оптимизации
        # 🚀 ИЗМЕНЕНО: Разрешаем использование монеты сразу с базовыми параметрами,
        # чтобы не блокировать сигналы на время долгих расчетов.
        return params, True

    def is_symbol_ready(self, symbol: str) -> bool:
        """
        Проверяет, готова ли монета для генерации сигналов

        Returns:
            True если монета оптимизирована и готова
        """
        _, is_optimized = self.get_symbol_params(symbol)
        return is_optimized

    def get_optimization_status(self, symbol: str) -> Dict[str, Any]:
        """Возвращает статус оптимизации монеты"""
        status_info = self.optimization_status.get(
            symbol, {"status": STATUS_PENDING, "added_at": None, "optimized_at": None}
        )
        return status_info

    def get_symbol_status(self, symbol: str) -> Dict[str, Any]:
        """Возвращает статус монеты"""
        params, is_optimized = self.get_symbol_params(symbol)
        status_info = self.optimization_status.get(
            symbol, {"status": STATUS_PENDING, "added_at": None, "optimized_at": None}
        )

        return {
            "symbol": symbol,
            "has_params": params is not None,
            "is_optimized": is_optimized,
            "status": status_info.get("status", STATUS_PENDING),
            "added_at": status_info.get("added_at"),
            "optimized_at": status_info.get("optimized_at"),
            "params": params if params else DEFAULT_PARAMS,
        }


# Глобальный экземпляр
_symbol_params_manager: Optional[SymbolParamsManager] = None


def get_symbol_params_manager() -> SymbolParamsManager:
    """Получает глобальный экземпляр менеджера параметров"""
    global _symbol_params_manager
    if _symbol_params_manager is None:
        _symbol_params_manager = SymbolParamsManager()
    return _symbol_params_manager
