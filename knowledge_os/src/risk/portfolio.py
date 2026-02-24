#!/usr/bin/env python3

"""
Portfolio Risk Manager - управление рисками портфеля
Контролирует общую просадку, распределение капитала, лимиты убытков
"""

import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.shared.utils.datetime_utils import get_utc_now

try:
    from db import Database

    DATABASE_AVAILABLE = True
except ImportError:  # pragma: no cover - на случай ранних стадий инициализации
    Database = None  # type: ignore
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    """Метрики портфеля"""

    total_equity: float = 0.0
    used_capital: float = 0.0
    free_capital: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    open_positions_count: int = 0
    daily_loss: float = 0.0
    last_updated: float = 0.0


class PortfolioRiskManager:
    """
    Менеджер рисков портфеля

    Контролирует:
    1. Максимальную просадку портфеля (10%)
    2. Дневной лимит убытков (5%)
    3. Максимальное количество открытых позиций
    4. Распределение капитала между позициями
    """

    def __init__(self):
        # Лимиты рисков
        self.risk_limits = {
            "max_portfolio_drawdown_pct": 10.0,  # Максимальная просадка портфеля
            "max_daily_loss_pct": 5.0,  # Максимальный дневной убыток
            "max_open_positions": 10,  # Максимум открытых позиций
            "max_capital_per_position_pct": 15.0,  # Максимум капитала на одну позицию
            "max_sector_exposure_pct": 30.0,  # Максимальная экспозиция по сектору
        }

        # Метрики портфеля
        self.portfolio_metrics = PortfolioMetrics()
        self.peak_equity = 0.0
        self.daily_start_equity = 0.0
        self.daily_reset_time = 0

        # История для аналитики
        self.equity_history: List[float] = []
        self.drawdown_history: List[float] = []

        # Статистика
        self.stats = {
            "total_checks": 0,
            "blocked_by_drawdown": 0,
            "blocked_by_daily_loss": 0,
            "blocked_by_position_limit": 0,
            "blocked_by_capital_limit": 0,
        }

        self.db: Optional[Database] = Database() if DATABASE_AVAILABLE else None
        try:
            from risk_flags_manager import get_default_manager

            self._risk_flags = get_default_manager()
        except Exception:  # pragma: no cover
            self._risk_flags = None
        self._current_user_id: Optional[str] = None
        self._real_trade_modes = ("live", "futures")
        self._balance_cache: Dict[str, Dict[str, Any]] = {}
        self._acceptance_db: Optional[Any] = None
        self._exchange_adapter_cls: Optional[Any] = None

        # Лениво подгружаем сервисы для авто-режима
        try:
            from acceptance_database import AcceptanceDatabase

            self._acceptance_db: Optional[AcceptanceDatabase] = AcceptanceDatabase()
        except Exception:  # pragma: no cover
            logger.debug("⚠️ [PORTFOLIO RISK] AcceptanceDatabase недоступна", exc_info=True)
            self._acceptance_db = None

        try:
            from exchange_adapter import ExchangeAdapter

            self._exchange_adapter_cls = ExchangeAdapter
        except Exception:  # pragma: no cover
            logger.debug("⚠️ [PORTFOLIO RISK] ExchangeAdapter недоступен", exc_info=True)
            self._exchange_adapter_cls = None

    async def check_portfolio_risk(
        self, user_id: str, new_position_size_usdt: float, user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Проверяет риски для всего портфеля перед открытием новой позиции

        Args:
            user_id: ID пользователя
            new_position_size_usdt: Размер новой позиции в USDT
            user_data: Данные пользователя

        Returns:
            {
                'allowed': bool,
                'reason': str,
                'details': dict,
                'risk_score': float (0-1)
            }
        """
        try:
            self.stats["total_checks"] += 1

            # 0. Гварды против ложных срабатываний
            # 0.1 Нулевая заявка не должна триггерить риски портфеля
            if new_position_size_usdt is None or new_position_size_usdt <= 0:
                return {
                    "allowed": True,
                    "reason": "ZERO_SIZE_NO_CHECK",
                    "details": {"new_position_size_usdt": float(new_position_size_usdt or 0.0)},
                    "risk_score": 0.0,
                }

            # Обновляем депозит для auto-режима (подтягиваем с биржи при необходимости)
            await self._sync_deposit_from_exchange_if_needed(user_id, user_data)

            # Обновляем метрики портфеля
            await self._update_portfolio_metrics(user_id, user_data)

            # 0.2 Инициализация базовых величин (baseline/peak) от текущего equity/депозита
            if self.portfolio_metrics.total_equity <= 0:
                # Пытаемся взять депозит как baseline
                deposit = float(user_data.get("deposit", 0) or 0)
                if deposit > 0:
                    self.portfolio_metrics.total_equity = deposit
            if self.peak_equity <= 0 and self.portfolio_metrics.total_equity > 0:
                self.peak_equity = self.portfolio_metrics.total_equity

            # 0.3 Проверка risk flags (emergency_stop/weak_setup_stop)
            if self._risk_flags:
                if self._risk_flags.is_active("emergency_stop"):
                    logger.warning(
                        "🚨 [PORTFOLIO RISK] emergency_stop активен — блокируем открытие."
                    )
                    return {
                        "allowed": False,
                        "reason": "EMERGENCY_STOP_ACTIVE",
                        "details": {},
                        "risk_score": 1.0,
                    }
                if self._risk_flags.is_active("weak_setup_stop"):
                    logger.warning(
                        "🚨 [PORTFOLIO RISK] weak_setup_stop активен — блокируем открытие."
                    )
                    return {
                        "allowed": False,
                        "reason": "WEAK_SETUP_STOP_ACTIVE",
                        "details": {},
                        "risk_score": 1.0,
                    }

            # 1. Проверка просадки портфеля
            # Если baseline/peak не инициализированы или equity<=0 — не применяем блок по просадке
            if (
                self.portfolio_metrics.total_equity > 0
                and self.peak_equity > 0
                and self.portfolio_metrics.current_drawdown_pct
                >= self.risk_limits["max_portfolio_drawdown_pct"]
            ):
                self.stats["blocked_by_drawdown"] += 1
                logger.warning(
                    "🚨 [PORTFOLIO RISK] Достигнут лимит просадки портфеля: %.2f%% >= %.2f%%",
                    self.portfolio_metrics.current_drawdown_pct,
                    self.risk_limits["max_portfolio_drawdown_pct"],
                )
                return {
                    "allowed": False,
                    "reason": "MAX_DRAWDOWN_EXCEEDED",
                    "details": {
                        "current_drawdown": self.portfolio_metrics.current_drawdown_pct,
                        "max_drawdown": self.risk_limits["max_portfolio_drawdown_pct"],
                    },
                    "risk_score": 1.0,
                }

            # 2. Проверка дневного лимита убытков
            if self.daily_start_equity > 0 and self.portfolio_metrics.daily_loss < 0:
                daily_loss_pct = (
                    abs(self.portfolio_metrics.daily_loss) / self.daily_start_equity * 100
                )
            else:
                daily_loss_pct = 0.0
            if daily_loss_pct >= self.risk_limits["max_daily_loss_pct"]:
                self.stats["blocked_by_daily_loss"] += 1
                logger.warning(
                    "🚨 [PORTFOLIO RISK] Достигнут дневной лимит убытков: %.2f%% >= %.2f%%",
                    daily_loss_pct,
                    self.risk_limits["max_daily_loss_pct"],
                )
                return {
                    "allowed": False,
                    "reason": "DAILY_LOSS_LIMIT_EXCEEDED",
                    "details": {
                        "daily_loss_pct": daily_loss_pct,
                        "max_daily_loss": self.risk_limits["max_daily_loss_pct"],
                    },
                    "risk_score": 1.0,
                }

            # 3. Проверка количества открытых позиций
            if (
                self.portfolio_metrics.open_positions_count
                >= self.risk_limits["max_open_positions"]
            ):
                self.stats["blocked_by_position_limit"] += 1
                logger.warning(
                    "🚨 [PORTFOLIO RISK] Достигнут лимит открытых позиций: %d >= %d",
                    self.portfolio_metrics.open_positions_count,
                    self.risk_limits["max_open_positions"],
                )
                return {
                    "allowed": False,
                    "reason": "MAX_POSITIONS_EXCEEDED",
                    "details": {
                        "open_positions": self.portfolio_metrics.open_positions_count,
                        "max_positions": self.risk_limits["max_open_positions"],
                    },
                    "risk_score": 0.9,
                }

            # 4. Проверка лимита капитала на позицию
            position_pct = (
                (new_position_size_usdt / self.portfolio_metrics.total_equity * 100)
                if self.portfolio_metrics.total_equity > 0
                else 0
            )
            if position_pct > self.risk_limits["max_capital_per_position_pct"]:
                self.stats["blocked_by_capital_limit"] += 1
                logger.warning(
                    "🚨 [PORTFOLIO RISK] Размер позиции превышает лимит: %.2f%% > %.2f%%",
                    position_pct,
                    self.risk_limits["max_capital_per_position_pct"],
                )
                return {
                    "allowed": False,
                    "reason": "POSITION_SIZE_TOO_LARGE",
                    "details": {
                        "position_size_pct": position_pct,
                        "max_per_position": self.risk_limits["max_capital_per_position_pct"],
                        "suggested_max_size": self.portfolio_metrics.total_equity
                        * self.risk_limits["max_capital_per_position_pct"]
                        / 100,
                    },
                    "risk_score": 0.8,
                }

            # 5. Рассчитываем risk score (0-1, где 0 = безопасно, 1 = критично)
            risk_score = self._calculate_risk_score()

            # Позиция разрешена
            logger.debug(
                "✅ [PORTFOLIO RISK] Позиция разрешена (risk score: %.2f, drawdown: %.2f%%, позиций: %d)",
                risk_score,
                self.portfolio_metrics.current_drawdown_pct,
                self.portfolio_metrics.open_positions_count,
            )

            return {
                "allowed": True,
                "reason": "RISK_WITHIN_LIMITS",
                "details": {
                    "drawdown": self.portfolio_metrics.current_drawdown_pct,
                    "daily_loss_pct": daily_loss_pct,
                    "open_positions": self.portfolio_metrics.open_positions_count,
                    "position_size_pct": position_pct,
                },
                "risk_score": risk_score,
            }

        except Exception as e:
            logger.error("❌ Ошибка check_portfolio_risk: %s", e)
            # Fallback: разрешаем позицию (чтобы не блокировать систему)
            return {
                "allowed": True,
                "reason": "ERROR_FALLBACK",
                "details": {"error": str(e)},
                "risk_score": 0.5,
            }

    async def _sync_deposit_from_exchange_if_needed(
        self, user_id: str, user_data: Dict[str, Any]
    ) -> None:
        """
        Для auto-пользователей подтягивает фактический баланс с биржи и обновляет депозит.
        """
        try:
            if not await self._is_auto_mode(user_id, user_data):
                return

            balance = await self._fetch_exchange_balance(user_id, user_data)
            if not balance:
                return

            total = float(balance.get("total", 0.0))
            free = float(balance.get("free", total))
            used = float(balance.get("used", 0.0))
            if total <= 0:
                logger.warning(
                    "⚠️ [PORTFOLIO RISK] auto режим, но биржа вернула нулевой баланс (user=%s)",
                    user_id,
                )
                return

            deposit_changed = abs(float(user_data.get("deposit", 0.0)) - total) > 1e-6
            if (
                deposit_changed
                or user_data.get("balance") != total
                or user_data.get("free_deposit") != free
            ):
                user_data["deposit"] = total
                user_data["balance"] = total
                user_data["free_deposit"] = free
                user_data["used_margin"] = used

                if self.db:
                    self.db.save_user_data(user_id, user_data)

                logger.info(
                    "💰 [PORTFOLIO RISK] Депозит auto-пользователя %s обновлён с биржи: total=%.2f free=%.2f used=%.2f",
                    user_id,
                    total,
                    free,
                    used,
                )
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "⚠️ [PORTFOLIO RISK] Не удалось синхронизировать депозит с биржи (user=%s): %s",
                user_id,
                exc,
                exc_info=True,
            )

    async def _is_auto_mode(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Определяет, находится ли пользователь в авто-режиме."""
        try:
            mode_hint = str(user_data.get("auto_mode") or "").lower()
            if mode_hint == "auto":
                return True

            # Проверяем таблицу user_settings (источник правды для режима)
            if self.db:
                try:
                    self.db.cursor.execute(
                        "SELECT trade_mode FROM user_settings WHERE user_id = ?",
                        (int(user_id),),
                    )
                    row = self.db.cursor.fetchone()
                    if row and str(row[0]).lower() == "auto":
                        return True
                except Exception as exc:
                    logger.debug(
                        "⚠️ [PORTFOLIO RISK] Не удалось получить trade_mode из user_settings для %s: %s",
                        user_id,
                        exc,
                        exc_info=True,
                    )

            return False
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "⚠️ [PORTFOLIO RISK] Сбой определения auto_mode для %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            return False

    async def _fetch_exchange_balance(
        self, user_id: str, user_data: Dict[str, Any]
    ) -> Optional[Dict[str, float]]:
        """Запрашивает баланс пользователя на бирже с кешированием."""
        now = time.time()
        cache_entry = self._balance_cache.get(str(user_id))
        if cache_entry:
            cached_ts = float(cache_entry.get("timestamp") or 0.0)
            if now - cached_ts < 60:
                return cache_entry.get("payload")

        if not self._acceptance_db or not self._exchange_adapter_cls:
            return None

        exchange_name = str(user_data.get("exchange", "bitget") or "bitget").lower()
        trade_mode = str(user_data.get("trade_mode", "futures") or "futures")

        try:
            keys = await self._acceptance_db.get_active_exchange_keys(int(user_id), exchange_name)
            if not keys:
                logger.warning(
                    "⚠️ [PORTFOLIO RISK] auto режим без активных ключей (%s на %s)",
                    user_id,
                    exchange_name,
                )
                return None

            adapter = self._exchange_adapter_cls(
                exchange=exchange_name,
                keys=keys,
                sandbox=False,
                trade_mode=trade_mode,
            )

            balance = await adapter.fetch_balance()
            if not balance:
                return None

            payload = {
                "total": float(balance.get("total") or 0.0),
                "free": float(balance.get("free") or 0.0),
                "used": float(balance.get("used") or 0.0),
            }

            self._balance_cache[str(user_id)] = {
                "timestamp": now,
                "payload": payload,
            }
            return payload
        except Exception as exc:  # pragma: no cover
            logger.debug(
                "⚠️ [PORTFOLIO RISK] Ошибка получения баланса с биржи для %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            return None

    async def _update_portfolio_metrics(self, user_id: str, user_data: Dict[str, Any]):
        """Обновляет метрики портфеля"""
        try:
            if self._current_user_id != user_id:
                self._reset_portfolio_state()
                self._current_user_id = user_id

            current_time = time.time()

            # Получаем данные пользователя
            deposit = float(user_data.get("deposit", 0) or 0)
            open_positions = user_data.get("open_positions", []) or []

            # Рассчитываем unrealized PnL по переданным позициям
            unrealized_pnl = 0.0
            used_capital_fallback = 0.0
            for pos in open_positions:
                entry_price = float(pos.get("entry_price") or 0.0)
                qty = float(pos.get("qty") or pos.get("quantity") or 0.0)
                if qty <= 0:
                    continue
                used_capital_fallback += float(pos.get("risk_amount") or entry_price * qty)
                symbol = pos.get("symbol") or ""

                current_price = entry_price
                if symbol:
                    try:
                        try:
                            from src.execution.exchange_api import get_current_price_robust
                        except ImportError:
                            from improved_price_api import get_current_price_robust
                        from price_validation import get_validated_price

                        price_result = await get_validated_price(
                            symbol, entry_price, get_current_price_robust, max_deviation_pct=50.0
                        )
                        if price_result and price_result > 0:
                            current_price = float(price_result)
                    except Exception:
                        pass

                side = (pos.get("side") or "long").lower()
                if side == "long":
                    unrealized_pnl += (current_price - entry_price) * qty
                else:
                    unrealized_pnl += (entry_price - current_price) * qty

            realized_pnl_total = 0.0
            realized_pnl_today = 0.0
            used_capital_db = None
            open_count_db = None

            if self.db:
                try:
                    user_id_str = str(user_id)
                    with self.db.get_lock():
                        # Совокупный реализованный результат по всем закрытым сделкам
                        self.db.cursor.execute(
                            """
                            SELECT COALESCE(SUM(net_pnl_usd), 0)
                            FROM trades
                            WHERE user_id = ?
                              AND (trade_mode IS NULL OR trade_mode = '' OR trade_mode IN ({modes}))
                            """.format(modes=",".join("?" for _ in self._real_trade_modes)),
                            (user_id_str, *self._real_trade_modes),
                        )
                        row = self.db.cursor.fetchone()
                        realized_pnl_total = float(row[0] or 0.0)

                        # Реализованный результат за текущие сутки (UTC)
                        self.db.cursor.execute(
                            """
                            SELECT COALESCE(SUM(net_pnl_usd), 0)
                            FROM trades
                            WHERE user_id = ?
                              AND DATE(exit_time) = DATE('now')
                              AND (trade_mode IS NULL OR trade_mode = '' OR trade_mode IN ({modes}))
                            """.format(modes=",".join("?" for _ in self._real_trade_modes)),
                            (user_id_str, *self._real_trade_modes),
                        )
                        row = self.db.cursor.fetchone()
                        realized_pnl_today = float(row[0] or 0.0)

                        # Использованный капитал и количество позиций по открытому signals_log
                        self.db.cursor.execute(
                            """
                            SELECT
                                COALESCE(SUM(entry_amount_usd), 0),
                                COUNT(*)
                            FROM signals_log
                            WHERE user_id = ?
                              AND UPPER(IFNULL(result, 'OPEN')) LIKE 'OPEN%'
                              AND (trade_mode IS NULL OR trade_mode = '' OR trade_mode IN ({modes}))
                            """.format(modes=",".join("?" for _ in self._real_trade_modes)),
                            (user_id_str, *self._real_trade_modes),
                        )
                        row = self.db.cursor.fetchone()
                        if row:
                            used_capital_db = float(row[0] or 0.0)
                            open_count_db = int(row[1] or 0)
                except (sqlite3.Error, ValueError, TypeError) as db_err:
                    logger.debug(
                        "⚠️ [PORTFOLIO RISK] Ошибка получения данных из trades/signals_log: %s",
                        db_err,
                    )

            # Total equity = депозит + реализованный PnL + нереализованный PnL
            total_equity = deposit + realized_pnl_total + unrealized_pnl

            # Обновляем peak equity
            if total_equity > self.peak_equity:
                self.peak_equity = total_equity

            # Рассчитываем текущую просадку
            current_drawdown_pct = 0.0
            if self.peak_equity > 0:
                current_drawdown_pct = (self.peak_equity - total_equity) / self.peak_equity * 100

            # Обновляем максимальную просадку
            if current_drawdown_pct > self.portfolio_metrics.max_drawdown_pct:
                self.portfolio_metrics.max_drawdown_pct = current_drawdown_pct

            # Синхронизируем baseline дневного equity
            self._sync_daily_baseline(user_id, total_equity)

            # Рассчитываем дневной убыток относительно baseline
            daily_loss = total_equity - self.daily_start_equity
            if daily_loss > 0:
                daily_loss = 0.0

            # Обновляем метрики
            self.portfolio_metrics.total_equity = total_equity
            self.portfolio_metrics.used_capital = float(
                used_capital_db if used_capital_db is not None else used_capital_fallback
            )
            self.portfolio_metrics.free_capital = max(
                0.0, total_equity - self.portfolio_metrics.used_capital
            )
            self.portfolio_metrics.unrealized_pnl = unrealized_pnl
            self.portfolio_metrics.realized_pnl = realized_pnl_total
            self.portfolio_metrics.total_pnl = realized_pnl_total + unrealized_pnl
            self.portfolio_metrics.current_drawdown_pct = current_drawdown_pct
            self.portfolio_metrics.open_positions_count = int(
                open_count_db if open_count_db is not None else len(open_positions)
            )
            self.portfolio_metrics.daily_loss = daily_loss
            self.portfolio_metrics.last_updated = current_time

            logger.debug(
                "[PORTFOLIO STATE] user=%s equity=%.4f used=%.4f free=%.4f deposit=%.4f realized=%.4f unrealized=%.4f open=%s",
                user_id,
                self.portfolio_metrics.total_equity,
                self.portfolio_metrics.used_capital,
                self.portfolio_metrics.free_capital,
                float(user_data.get("deposit", 0) or 0),
                realized_pnl_total,
                unrealized_pnl,
                self.portfolio_metrics.open_positions_count,
            )

            # Добавляем в историю
            self.equity_history.append(total_equity)
            self.drawdown_history.append(current_drawdown_pct)

            # Ограничиваем историю (последние 1000 точек)
            if len(self.equity_history) > 1000:
                self.equity_history = self.equity_history[-1000:]
            if len(self.drawdown_history) > 1000:
                self.drawdown_history = self.drawdown_history[-1000:]

            # Сохраняем дневной реализованный результат (для аналитики)
            self._set_system_setting(
                f"portfolio_realized_daily:{user_id}", f"{realized_pnl_today:.10f}"
            )

        except Exception as e:
            logger.error("❌ Ошибка _update_portfolio_metrics: %s", e)

    def _reset_portfolio_state(self) -> None:
        """Сбрасывает накопленные метрики при переключении между пользователями."""
        self.portfolio_metrics = PortfolioMetrics()
        self.peak_equity = 0.0
        self.daily_start_equity = 0.0
        self.daily_reset_time = 0
        self.equity_history = []
        self.drawdown_history = []

    def _calculate_risk_score(self) -> float:
        """
        Рассчитывает общий risk score портфеля (0-1)

        0.0 = минимальный риск
        1.0 = критический риск
        """
        try:
            score = 0.0

            # 1. Просадка (40% веса)
            drawdown_ratio = (
                self.portfolio_metrics.current_drawdown_pct
                / self.risk_limits["max_portfolio_drawdown_pct"]
            )
            score += drawdown_ratio * 0.40

            # 2. Дневной убыток (30% веса)
            if self.daily_start_equity > 0 and self.portfolio_metrics.daily_loss < 0:
                daily_loss_pct = (
                    abs(self.portfolio_metrics.daily_loss) / self.daily_start_equity * 100
                )
                daily_loss_ratio = daily_loss_pct / self.risk_limits["max_daily_loss_pct"]
                score += daily_loss_ratio * 0.30

            # 3. Количество позиций (20% веса)
            positions_ratio = (
                self.portfolio_metrics.open_positions_count / self.risk_limits["max_open_positions"]
            )
            score += positions_ratio * 0.20

            # 4. Использование капитала (10% веса)
            capital_usage = (
                self.portfolio_metrics.used_capital / self.portfolio_metrics.total_equity
                if self.portfolio_metrics.total_equity > 0
                else 0
            )
            score += capital_usage * 0.10

            return min(1.0, max(0.0, score))

        except Exception as e:
            logger.debug("Ошибка _calculate_risk_score: %s", e)
            return 0.5

    def get_position_size_adjustment(self, base_size_usdt: float) -> float:
        """
        Корректирует размер позиции на основе текущего риска портфеля

        Args:
            base_size_usdt: Базовый размер позиции

        Returns:
            Скорректированный размер позиции
        """
        try:
            risk_score = self._calculate_risk_score()

            # Чем выше риск, тем меньше размер позиции
            if risk_score > 0.8:
                multiplier = 0.5  # -50% при высоком риске
            elif risk_score > 0.6:
                multiplier = 0.7  # -30% при среднем риске
            elif risk_score > 0.4:
                multiplier = 0.85  # -15% при умеренном риске
            else:
                multiplier = 1.0  # Без коррекции

            adjusted_size = base_size_usdt * multiplier

            if multiplier < 1.0:
                logger.info(
                    "📉 [PORTFOLIO RISK] Размер позиции скорректирован: %.2f → %.2f USDT (risk score: %.2f)",
                    base_size_usdt,
                    adjusted_size,
                    risk_score,
                )

            return adjusted_size

        except Exception as e:
            logger.debug("Ошибка get_position_size_adjustment: %s", e)
            return base_size_usdt

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику менеджера рисков"""
        return {
            "total_checks": self.stats["total_checks"],
            "blocked_by_drawdown": self.stats["blocked_by_drawdown"],
            "blocked_by_daily_loss": self.stats["blocked_by_daily_loss"],
            "blocked_by_position_limit": self.stats["blocked_by_position_limit"],
            "blocked_by_capital_limit": self.stats["blocked_by_capital_limit"],
            "current_metrics": {
                "total_equity": self.portfolio_metrics.total_equity,
                "current_drawdown_pct": self.portfolio_metrics.current_drawdown_pct,
                "max_drawdown_pct": self.portfolio_metrics.max_drawdown_pct,
                "open_positions": self.portfolio_metrics.open_positions_count,
                "risk_score": self._calculate_risk_score(),
            },
        }

    def _sync_daily_baseline(self, user_id: str, total_equity: float) -> None:
        """Обновляет baseline equity для расчёта дневного PnL."""
        today = get_utc_now().date().isoformat()

        if not self.db:
            now = time.time()
            if self.daily_start_equity == 0 or now - self.daily_reset_time > 86400:
                self.daily_start_equity = total_equity
                self.daily_reset_time = now
            return

        key_equity = f"portfolio_daily_start_equity:{user_id}"
        key_date = f"portfolio_daily_start_date:{user_id}"

        stored_date = self._get_system_setting(key_date)
        if stored_date != today or self.daily_start_equity == 0:
            self.daily_start_equity = total_equity
            self._set_system_setting(key_equity, f"{total_equity:.10f}")
            self._set_system_setting(key_date, today)
            self.daily_reset_time = time.time()
        else:
            if self.daily_start_equity == 0:
                baseline_val = self._get_system_setting(key_equity)
                try:
                    self.daily_start_equity = (
                        float(baseline_val) if baseline_val is not None else total_equity
                    )
                except (TypeError, ValueError):
                    self.daily_start_equity = total_equity

    def _get_system_setting(self, key: str) -> Optional[str]:
        if not self.db:
            return None
        try:
            with self.db.get_lock():
                self.db.cursor.execute(
                    "SELECT value FROM system_settings WHERE key = ?",
                    (key,),
                )
                row = self.db.cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as err:
            logger.debug(
                "⚠️ [PORTFOLIO RISK] Не удалось прочитать system_settings[%s]: %s", key, err
            )
            return None

    def _set_system_setting(self, key: str, value: str) -> None:
        if not self.db:
            return
        try:
            with self.db.get_lock():
                self.db.cursor.execute(
                    """
                    INSERT INTO system_settings(key, value)
                    VALUES(?, ?)
                    ON CONFLICT(key)
                    DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, value),
                )
                self.db.conn.commit()
        except sqlite3.Error as err:
            logger.debug(
                "⚠️ [PORTFOLIO RISK] Не удалось сохранить system_settings[%s]: %s", key, err
            )

    def reset_daily_stats(self):
        """Сбрасывает дневную статистику"""
        self.daily_start_equity = self.portfolio_metrics.total_equity
        self.portfolio_metrics.daily_loss = 0.0
        self.daily_reset_time = time.time()
        logger.info("🔄 [PORTFOLIO RISK] Дневная статистика сброшена")


# ========================================================================
# 🛡️ АВТОМАТИЧЕСКОЕ УПРАВЛЕНИЕ ПОЗИЦИЯМИ И ЗАЩИТЫ (ГИБРИДНАЯ СИСТЕМА)
# ========================================================================

# Константы для автоматического закрытия позиций
#
# ГИБРИДНАЯ СИСТЕМА СТОП-ЛОСС:
# 1. Приоритет: AI-оптимизированный SL из БД (учитывает ATR, волатильность)
# 2. Резервная защита: -3% (если нет AI SL), -5% (критический стоп)
# 3. AI SL может быть от -1% до -8% в зависимости от волатильности актива
#
MAX_LOSS_PER_POSITION_PCT = 3.0  # Резервное авто-закрытие (если нет AI SL)
CRITICAL_LOSS_PER_POSITION_PCT = 5.0  # Критический стоп (всегда активен)
AUTO_CLOSE_ENABLED = True


async def check_position_auto_close(
    position: Dict[str, Any], current_price: float, exchange_adapter=None
) -> Dict[str, Any]:
    """
    Проверяет позицию на необходимость автоматического закрытия по убыткам

    Args:
        position: Данные позиции (symbol, entry_price, direction, contracts, etc.)
        current_price: Текущая цена актива
        exchange_adapter: Адаптер биржи для закрытия позиции

    Returns:
        {
            'should_close': bool,
            'reason': str,
            'close_pct': int (100 = полностью),
            'pnl_pct': float
        }
    """
    if not AUTO_CLOSE_ENABLED:
        return {"should_close": False, "reason": "auto_close_disabled"}

    try:
        symbol = position.get("symbol")
        entry_price = float(position.get("entryPrice") or position.get("entry_price", 0))
        direction = position.get("direction", "BUY")

        if not entry_price or entry_price <= 0:
            return {"should_close": False, "reason": "invalid_entry_price"}

        # Рассчитываем PnL
        if direction == "BUY":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Проверяем критический убыток (-5%)
        if pnl_pct <= -CRITICAL_LOSS_PER_POSITION_PCT:
            logger.warning(
                "🚨 [CRITICAL LOSS] %s: PnL=%.2f%% <= -%.1f%%, требуется немедленное закрытие!",
                symbol,
                pnl_pct,
                CRITICAL_LOSS_PER_POSITION_PCT,
            )
            return {
                "should_close": True,
                "reason": f"critical_loss_{pnl_pct:.2f}%",
                "close_pct": 100,
                "pnl_pct": pnl_pct,
            }

        # Проверяем авто-стоп (-3%)
        if pnl_pct <= -MAX_LOSS_PER_POSITION_PCT:
            logger.warning(
                "⚠️ [AUTO STOP] %s: PnL=%.2f%% <= -%.1f%%, закрываем позицию",
                symbol,
                pnl_pct,
                MAX_LOSS_PER_POSITION_PCT,
            )
            return {
                "should_close": True,
                "reason": f"auto_stop_{pnl_pct:.2f}%",
                "close_pct": 100,
                "pnl_pct": pnl_pct,
            }

        return {"should_close": False, "reason": "within_limits", "pnl_pct": pnl_pct}

    except Exception as e:
        logger.error("Ошибка check_position_auto_close: %s", e)
        return {"should_close": False, "reason": f"error: {e}"}


async def detect_hedge_positions(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Обнаруживает hedge-позиции (одновременные LONG и SHORT на один символ)

    Args:
        positions: Список всех открытых позиций

    Returns:
        Список hedge-конфликтов: [{'symbol': 'BTC/USDT:USDT', 'long': {...}, 'short': {...}}]
    """
    try:
        # Группируем позиции по символу
        symbol_positions = {}

        for pos in positions:
            contracts = float(pos.get("contracts", 0))
            if abs(contracts) <= 0:
                continue

            symbol = pos.get("symbol")
            hold_side = pos.get("side") or pos.get("info", {}).get("holdSide", "")
            direction = "LONG" if hold_side.lower() == "long" else "SHORT"

            if symbol not in symbol_positions:
                symbol_positions[symbol] = {"LONG": None, "SHORT": None}

            symbol_positions[symbol][direction] = pos

        # Находим hedge-конфликты
        hedge_conflicts = []
        for symbol, directions in symbol_positions.items():
            if directions["LONG"] and directions["SHORT"]:
                long_size = abs(float(directions["LONG"].get("contracts", 0)))
                short_size = abs(float(directions["SHORT"].get("contracts", 0)))

                hedge_conflicts.append(
                    {
                        "symbol": symbol,
                        "long": directions["LONG"],
                        "short": directions["SHORT"],
                        "long_size": long_size,
                        "short_size": short_size,
                        "net_exposure": long_size - short_size,
                    }
                )

                logger.warning(
                    "⚠️ [HEDGE DETECTED] %s: LONG %.4f + SHORT %.4f = NET %.4f",
                    symbol,
                    long_size,
                    short_size,
                    long_size - short_size,
                )

        return hedge_conflicts

    except Exception as e:
        logger.error("Ошибка detect_hedge_positions: %s", e)
        return []


async def close_hedge_positions(
    hedge_conflicts: List[Dict[str, Any]], exchange_adapter=None
) -> List[Dict[str, Any]]:
    """
    Закрывает hedge-позиции (оставляет только нетто-позицию)

    Args:
        hedge_conflicts: Список hedge-конфликтов от detect_hedge_positions
        exchange_adapter: Адаптер биржи для закрытия

    Returns:
        Список результатов закрытия
    """
    if not exchange_adapter:
        logger.error("❌ [HEDGE CLOSE] Exchange adapter not provided")
        return []

    results = []

    for conflict in hedge_conflicts:
        symbol = conflict["symbol"]
        long_size = conflict["long_size"]
        short_size = conflict["short_size"]

        try:
            # Закрываем меньшую позицию полностью
            if long_size < short_size:
                # Закрываем весь LONG
                logger.info(
                    "🔒 [HEDGE CLOSE] %s: Закрываю LONG %.4f (SHORT %.4f остается)",
                    symbol,
                    long_size,
                    short_size,
                )
                order = await exchange_adapter.create_market_order(
                    symbol=symbol,
                    side="sell",  # Закрытие LONG
                    amount=long_size,
                )
                results.append({"symbol": symbol, "closed": "LONG", "order": order})
            else:
                # Закрываем весь SHORT
                logger.info(
                    "🔒 [HEDGE CLOSE] %s: Закрываю SHORT %.4f (LONG %.4f остается)",
                    symbol,
                    short_size,
                    long_size,
                )
                order = await exchange_adapter.create_market_order(
                    symbol=symbol,
                    side="buy",  # Закрытие SHORT
                    amount=short_size,
                )
                results.append({"symbol": symbol, "closed": "SHORT", "order": order})

        except Exception as e:
            logger.error("❌ [HEDGE CLOSE] %s: ошибка закрытия - %s", symbol, e)
            results.append({"symbol": symbol, "error": str(e)})

    return results


# Глобальный экземпляр
_portfolio_risk_manager = None


def get_portfolio_risk_manager() -> PortfolioRiskManager:
    """Получение глобального экземпляра менеджера рисков"""
    global _portfolio_risk_manager
    if _portfolio_risk_manager is None:
        _portfolio_risk_manager = PortfolioRiskManager()
        logger.info("✅ PortfolioRiskManager инициализирован")
    return _portfolio_risk_manager
