"""Обёртка для работы с биржами через ccxt (Bitget по умолчанию)."""

import inspect
import logging
import re
import time
from typing import Any, Callable, Dict, Optional, cast

try:
    import ccxt.async_support as ccxt  # type: ignore

    CCXT_LIB = ccxt
except ModuleNotFoundError:  # pragma: no cover
    CCXT_LIB = None  # type: ignore

from src.core.exceptions import (
    AuthenticationError,
    ExchangeAPIError,
    NetworkError,
    OrderCancellationError,
    OrderExecutionError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class ExchangeAdapter:
    """Адаптер биржи (Bitget по умолчанию) через ccxt. Грейсфул, если ccxt недоступен."""

    @staticmethod
    def _generate_client_oid(prefix: str, symbol: str, pos_side: Optional[str] = None) -> str:
        """Формирует допустимый clientOid (≤32 символа, только [A-Za-z0-9])."""
        timestamp = str(int(time.time() * 1000))
        prefix_clean = re.sub(r"[^A-Za-z0-9]", "", prefix) or "oid"
        symbol_base = symbol.split(":")[0] if symbol else ""
        symbol_clean = re.sub(r"[^A-Za-z0-9]", "", symbol_base)
        pos_clean = re.sub(r"[^A-Za-z0-9]", "", pos_side or "")

        parts = [
            prefix_clean[:6],
            pos_clean[:4],
            symbol_clean[-8:],
            timestamp[-12:],
        ]
        candidate = "".join(parts)
        if not candidate:
            candidate = timestamp[-12:]
        if len(candidate) > 32:
            candidate = candidate[-32:]
        return candidate

    def __init__(
        self,
        exchange: str = "bitget",
        keys: Optional[Dict[str, Any]] = None,
        sandbox: bool = False,
        trade_mode: str = "futures",
    ):
        """Создаёт адаптер и инициализирует клиента ccxt при наличии."""
        self.exchange_name = (exchange or "bitget").lower()
        self.keys = keys or {}
        self.sandbox = sandbox
        self.trade_mode = trade_mode
        self.client = None

        logger.info(
            "🔧 [EXCHANGE] Инициализация адаптера %s (ключи: %s, режим: %s)",
            self.exchange_name,
            "есть" if keys else "нет",
            trade_mode,
        )

        try:
            if CCXT_LIB is None:
                raise ImportError("ccxt недоступен")

            if self.exchange_name == "bitget":
                logger.info("🔧 [BITGET] Создаю клиент с ключами")

                # Выбираем тип клиента в зависимости от режима торговли
                if self.trade_mode == "spot":
                    # Spot клиент
                    client_options = {
                        "defaultType": "spot",
                    }
                    logger.info("📊 [BITGET] Режим: SPOT")
                else:
                    # Futures клиент
                    client_options = {
                        "defaultType": "swap",
                        "defaultMarginMode": "isolated",
                        "defaultProductType": "USDT-FUTURES",
                    }
                    logger.info("📊 [BITGET] Режим: FUTURES")

                self.client = CCXT_LIB.bitget(
                    {
                        "apiKey": self.keys.get("api_key") or self.keys.get("apiKey"),
                        "secret": self.keys.get("secret") or self.keys.get("secret_key"),
                        "password": self.keys.get("passphrase") or self.keys.get("password"),
                        "options": client_options,
                        "enableRateLimit": True,
                    }
                )
                logger.info("✅ [BITGET] Клиент создан успешно")
            elif self.exchange_name == "binance":
                self.client = CCXT_LIB.binance(
                    {
                        "apiKey": self.keys.get("api_key"),
                        "secret": self.keys.get("secret"),
                        "enableRateLimit": True,
                    }
                )
            else:
                raise ValueError(f"Unsupported exchange: {self.exchange_name}")

            if self.sandbox and hasattr(self.client, "set_sandbox_mode"):
                # Для асинхронного клиента ccxt в __init__ нельзя использовать await
                # В данном проекте используется async ccxt, поэтому sandbox режим
                # должен устанавливаться в методах или через инициализатор.
                # Пока отключаем прямую установку здесь, чтобы избежать SyntaxError.
                pass
                # self.client.set_sandbox_mode(True)
                logger.info("🧪 [EXCHANGE] Sandbox режим затребован (но не активирован в __init__)")
        except (ImportError, AttributeError, KeyError) as exc:
            logger.error(
                "❌ [EXCHANGE] ccxt недоступен или ошибка инициализации: %s",
                exc,
                exc_info=True,
            )
            self.client = None
        except Exception as exc:
            logger.error(
                "❌ [EXCHANGE] Неожиданная ошибка инициализации: %s",
                exc,
                exc_info=True,
            )
            self.client = None

    def _ensure(self) -> bool:
        """Проверяет доступность клиента ccxt."""
        return self.client is not None

    async def _call_client(self, method_name: str, *args, **kwargs) -> Any:
        """
        Универсальный вызов метода ccxt клиента с трекингом Latency (🚀 DevOps Optimization).
        """
        if not self._ensure():
            return None

        method = getattr(self.client, method_name, None)
        if method is None:
            logger.warning("⚠️ [EXCHANGE] Метод %s не найден у клиента ccxt", method_name)
            return None

        start_time = time.perf_counter()
        try:
            result = method(*args, **kwargs)
            if inspect.isawaitable(result):
                response = await result
            else:
                response = result

            latency = (time.perf_counter() - start_time) * 1000  # в миллисекундах
            logger.info("⏱️ [LATENCY] %s call took %.2f ms", method_name, latency)

            # Сохраняем латентность в БД для анализа (если доступен DatabaseSingleton)
            try:
                from src.database.db import DatabaseSingleton

                db = DatabaseSingleton()
                db.log_api_latency(self.exchange_name, method_name, latency)
            except (ImportError, AttributeError):
                pass  # БД недоступна - не критично

            return response
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            error_msg = str(e).lower()

            # Определяем тип ошибки по сообщению (ccxt использует разные исключения)
            if (
                CCXT_LIB
                and hasattr(CCXT_LIB, "NetworkError")
                and isinstance(e, CCXT_LIB.NetworkError)
            ):
                logger.error(
                    "❌ [EXCHANGE] Ошибка сети при вызове %s (%.2f ms): %s", method_name, latency, e
                )
                raise NetworkError(
                    f"Network error in {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            elif (
                CCXT_LIB
                and hasattr(CCXT_LIB, "RateLimitExceeded")
                and isinstance(e, CCXT_LIB.RateLimitExceeded)
            ):
                logger.error(
                    "❌ [EXCHANGE] Превышен лимит запросов для %s (%.2f ms): %s",
                    method_name,
                    latency,
                    e,
                )
                raise RateLimitError(
                    f"Rate limit exceeded for {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            elif (
                CCXT_LIB
                and hasattr(CCXT_LIB, "AuthenticationError")
                and isinstance(e, CCXT_LIB.AuthenticationError)
            ):
                logger.error(
                    "❌ [EXCHANGE] Ошибка аутентификации для %s (%.2f ms): %s",
                    method_name,
                    latency,
                    e,
                )
                raise AuthenticationError(
                    f"Authentication error for {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            elif "network" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                logger.error(
                    "❌ [EXCHANGE] Ошибка сети при вызове %s (%.2f ms): %s", method_name, latency, e
                )
                raise NetworkError(
                    f"Network error in {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            elif "rate limit" in error_msg or "too many requests" in error_msg:
                logger.error(
                    "❌ [EXCHANGE] Превышен лимит запросов для %s (%.2f ms): %s",
                    method_name,
                    latency,
                    e,
                )
                raise RateLimitError(
                    f"Rate limit exceeded for {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            elif (
                "authentication" in error_msg
                or "unauthorized" in error_msg
                or "api key" in error_msg
            ):
                logger.error(
                    "❌ [EXCHANGE] Ошибка аутентификации для %s (%.2f ms): %s",
                    method_name,
                    latency,
                    e,
                )
                raise AuthenticationError(
                    f"Authentication error for {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e
            else:
                logger.error(
                    "❌ [EXCHANGE] Ошибка биржи при вызове %s (%.2f ms): %s",
                    method_name,
                    latency,
                    e,
                    exc_info=True,
                )
                raise ExchangeAPIError(
                    f"Exchange API error in {method_name}: {e}",
                    context={"method": method_name, "latency_ms": latency},
                ) from e

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Устанавливает плечо для символа на Bitget.

        Args:
            symbol: Символ.
            leverage: Плечо (1-125).

        Returns:
            True если успешно.
        """
        try:
            if not self._ensure():
                return True

            if self.exchange_name != "bitget":
                return True

            leverage = max(1, min(125, int(leverage)))  # Ограничиваем 1-125

            logger.info("🔧 [BITGET] Устанавливаю плечо для %s: %dx", symbol, leverage)

            if hasattr(self.client, "set_leverage"):
                # Для Bitget CCXT требует params={'marginMode': 'isolated'|'cross'}
                # По умолчанию используем isolated если не задано
                params = {"marginMode": "isolated"}
                result = await self.client.set_leverage(leverage, symbol, params=params)
                logger.info("✅ [BITGET] Плечо установлено: %s", result)
                return True
            logger.warning("⚠️ [BITGET] set_leverage недоступен")
            return False
        except Exception as exc:
            logger.warning("⚠️ [BITGET] Не удалось установить плечо для %s: %s", symbol, exc)
            # Если позиция уже открыта с другим плечом, Bitget может выдать ошибку.
            # В таком случае просто продолжаем.
            return False

    async def set_position_mode(self, symbol: str, hedge_mode: bool = True) -> bool:
        """
        Устанавливает режим позиции для символа на Bitget.

        Args:
            symbol: Символ (например BTCUSDT).
            hedge_mode: True = hedge mode (два направления), False = one-way mode.

        Returns:
            True если успешно установлено.
        """
        try:
            if not self._ensure():
                return True  # Нет клиента - пропускаем

            if self.exchange_name != "bitget":
                return True  # Только для Bitget

            logger.info(
                "🔧 [BITGET] Устанавливаю режим позиции для %s: %s",
                symbol,
                "hedge" if hedge_mode else "one-way",
            )

            # Используем метод ccxt если доступен
            if hasattr(self.client, "set_position_mode"):
                result = await self.client.set_position_mode(hedged=hedge_mode, symbol=symbol)
                logger.info("✅ [BITGET] Режим позиции установлен: %s", result)
                return True
            # Прямой API запрос если метода нет
            logger.warning("⚠️ [BITGET] set_position_mode недоступен, пробуем через params")
            return True
        except Exception as exc:
            # Не критично если не удалось установить - продолжаем
            logger.warning("⚠️ [BITGET] Не удалось установить режим позиции: %s", exc)
            return False

    async def create_limit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        reduce_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Создаёт лимитный ордер, учитывая режим торговли и hedge-настройки."""
        try:
            if not self._ensure():
                logger.warning("⚠️ ccxt клиент недоступен, возвращаем dry-run ордер")
                return {"id": f"dry-{int(time.time())}", "status": "filled"}

            # Для Bitget futures: сначала пытаемся установить hedge режим (не критично если не получится)
            if self.exchange_name == "bitget" and self.trade_mode == "futures":
                try:
                    await self.set_position_mode(symbol, hedge_mode=True)
                except Exception:
                    pass  # Продолжаем даже если не удалось

            logger.info(
                "📝 [BITGET] Создаю лимитный ордер: %s %s amount=%.6f price=%.8f",
                symbol,
                side,
                amount,
                price,
            )

            # Для Bitget нужно указать параметры ордера явно
            if self.trade_mode == "futures":
                params = {
                    "timeInForce": "GTC",  # Good Till Cancel
                    "hedged": True,  # Hedge mode
                    "reduceOnly": reduce_only,  # Только закрытие позиций (для TP/SL ордеров)
                }
                # В hedge режиме указываем holdSide для открытия позиций
                if not reduce_only:
                    # holdSide определяет направление позиции в hedge режиме
                    # 'long' для покупки (BUY), 'short' для продажи (SHORT)
                    params["holdSide"] = "long" if side.lower() == "buy" else "short"
                    logger.info("📋 [BITGET] Параметры с holdSide: %s", params)
            else:
                # Spot режим - не нужны futures параметры
                params = {}

            order = await self.client.create_order(
                symbol=symbol,
                type="limit",
                side=side.lower(),
                amount=amount,
                price=price,
                params=params,
            )
            logger.info("✅ [BITGET] Лимитный ордер создан: %s", order.get("id"))
            return order
        except (ExchangeAPIError, NetworkError, RateLimitError, AuthenticationError):
            # Уже обработано в _call_client, просто пробрасываем дальше
            raise
        except Exception as exc:
            logger.error(
                "❌ [BITGET] Неожиданная ошибка create_limit_order: %s", exc, exc_info=True
            )
            raise OrderExecutionError(
                f"Failed to create limit order: {exc}",
                context={"symbol": symbol, "side": side, "amount": amount, "price": price},
            ) from exc

    async def create_market_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        reduce_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Создаёт маркет-ордер с учётом торгового режима."""
        try:
            if not self._ensure():
                logger.warning("⚠️ ccxt клиент недоступен, возвращаем dry-run ордер")
                return {"id": f"drym-{int(time.time())}", "status": "filled"}

            # Для Bitget futures: сначала пытаемся установить hedge режим (не критично если не получится)
            if self.exchange_name == "bitget" and self.trade_mode == "futures":
                try:
                    await self.set_position_mode(symbol, hedge_mode=True)
                except Exception:
                    pass  # Продолжаем даже если не удалось

            logger.info("📝 [BITGET] Создаю маркет ордер: %s %s amount=%.6f", symbol, side, amount)

            if self.trade_mode == "futures":
                params = {
                    "timeInForce": "IOC",  # Immediate Or Cancel
                    "hedged": True,
                    "reduceOnly": reduce_only,
                    "clientOid": f"atra-{int(time.time() * 1000)}",
                }
                # В hedge режиме указываем holdSide для открытия позиций
                if not reduce_only:
                    # holdSide определяет направление позиции в hedge режиме
                    # 'long' для покупки (BUY), 'short' для продажи (SHORT)
                    params["holdSide"] = "long" if side.lower() == "buy" else "short"
            else:
                # Spot режим - не нужны futures параметры
                params = {}

            order = await self.client.create_order(
                symbol=symbol,
                type="market",
                side=side.lower(),
                amount=amount,
                params=params,
            )
            logger.info("✅ [BITGET] Маркет ордер создан: %s", order.get("id"))
            return order
        except (ExchangeAPIError, NetworkError, RateLimitError, AuthenticationError):
            # Уже обработано в _call_client, просто пробрасываем дальше
            raise
        except Exception as exc:
            logger.error(
                "❌ [BITGET] Неожиданная ошибка create_market_order: %s", exc, exc_info=True
            )
            raise OrderExecutionError(
                f"Failed to create market order: {exc}",
                context={"symbol": symbol, "side": side, "amount": amount},
            ) from exc

    async def wait_for_fill(self, order_id: str, symbol: str, timeout_sec: int = 90) -> bool:
        """Ожидает исполнения ордера в течение заданного таймаута."""
        try:
            if not self._ensure():
                return True
            deadline = time.time() + max(5, timeout_sec)
            while time.time() < deadline:
                info = await self.client.fetch_order(order_id, symbol)
                status = (info or {}).get("status", "").lower()
                if status in ("closed", "filled"):  # ccxt унификация
                    return True
                await asyncio.sleep(2)
            return False
        except Exception as exc:
            logger.error("wait_for_fill error: %s", exc)
            return False

    async def fetch_positions(self) -> Optional[Any]:
        """Возвращает список открытых позиций биржи."""
        try:
            if not self._ensure():
                return []
            if hasattr(self.client, "fetch_positions"):
                return await self.client.fetch_positions()
            return []
        except Exception as exc:
            logger.error("fetch_positions error: %s", exc)
            return []

    async def fetch_balance(self) -> Optional[Dict[str, Any]]:
        """Получает баланс USDT с биржи."""
        try:
            if not self._ensure():
                logger.warning("⚠️ ccxt клиент недоступен для получения баланса")
                return None

            logger.debug("💰 [EXCHANGE] Запрашиваю баланс...")
            balance = await self.client.fetch_balance()

            if balance:
                # USDT баланс для futures
                usdt_balance = balance.get("USDT", {})
                free = float(usdt_balance.get("free", 0) or 0)
                used = float(usdt_balance.get("used", 0) or 0)
                total = float(usdt_balance.get("total", 0) or 0)

                logger.info(
                    "💰 [EXCHANGE] Баланс получен: total=%.2f, free=%.2f, used=%.2f",
                    total,
                    free,
                    used,
                )

                return {
                    "total": total,
                    "free": free,
                    "used": used,
                    "currency": "USDT",
                }

            return None

        except Exception as exc:
            logger.error("❌ [EXCHANGE] fetch_balance error: %s", exc, exc_info=True)
            return None

    async def close(self):
        """Закрывает соединение с биржей и освобождает ресурсы."""
        try:
            if hasattr(self, "client") and self.client:
                # В асинхронном режиме ccxt требует вызова close()
                await self.client.close()
                logger.info("✅ [EXCHANGE] Соединение с биржей закрыто")
                self.client = None
        except Exception as exc:
            logger.error("❌ [EXCHANGE] Ошибка при закрытии соединения: %s", exc)

    async def __aenter__(self):
        """Для использования в async with"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Гарантирует закрытие сессии при выходе из блока"""
        await self.close()

    async def is_symbol_available(self, symbol: str) -> bool:
        """
        Проверяет, доступен ли символ на бирже для текущего режима торговли.

        Args:
            symbol: Символ (например BTCUSDT).

        Returns:
            True если символ доступен.
        """
        try:
            if not self._ensure():
                return True  # Fallback

            # Загружаем рынки если еще не загружены
            if not self.client.markets:
                await self.client.load_markets()

            # Формируем ID символа для поиска в ccxt
            # Для Bitget futures в ccxt символ обычно BTC/USDT:USDT или BTCUSDT
            # Мы ищем совпадение
            symbol_upper = symbol.upper()

            # 1. Прямое совпадение
            if symbol_upper in self.client.markets:
                return True

            # 2. Совпадение с разделителем (например BTC/USDT)
            if "/" not in symbol_upper and "USDT" in symbol_upper:
                alt_symbol = symbol_upper.replace("USDT", "/USDT")
                if alt_symbol in self.client.markets:
                    return True

            # 3. Совпадение с двоеточием (для свопов, например BTC/USDT:USDT)
            if self.trade_mode == "futures":
                alt_symbol_futures = f"{symbol_upper.replace('USDT', '/USDT')}:USDT"
                if alt_symbol_futures in self.client.markets:
                    return True

            # 4. Проверка по market id
            for market in self.client.markets.values():
                if market.get("id") == symbol_upper:
                    return True
                if market.get("symbol") == symbol_upper:
                    return True

            return False
        except Exception as exc:
            logger.warning("⚠️ [EXCHANGE] Ошибка проверки доступности символа %s: %s", symbol, exc)
            return True  # Fallback в случае ошибки

    async def place_stop_loss_order(
        self,
        symbol: str,
        direction: str,
        position_amount: float,
        stop_price: float,
        reduce_only: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Выставляет стоп-лосс для позиции.

        На Bitget (futures) создаём план-ордер loss_plan (market trigger), что
        унифицирует поведение с profit_plan (TP) и поддерживает частичные закрытия.
        При ошибке или на других биржах используем лимитный reduce-only fallback.

        Args:
            symbol: Символ
            direction: Направление позиции ('BUY'/'SELL' или 'LONG'/'SHORT')
            position_amount: Размер позиции в контрактах
            stop_price: Цена Stop Loss
            reduce_only: Ограничить ордер закрытием позиции

        Returns:
            Ордер или None
        """
        try:
            if not self._ensure():
                return None

            direction_norm = (direction or "").upper()
            is_short_position = direction_norm in ("SELL", "SHORT")
            sl_side = "buy" if is_short_position else "sell"
            pos_side = "short" if is_short_position else "long"

            logger.info(
                "🛡️ [SL Order] %s → direction=%s, trigger=%.8f, amount=%.4f",
                symbol,
                direction_norm or "?",
                stop_price,
                position_amount,
            )

            if self.exchange_name == "bitget" and self.trade_mode == "futures":
                # Используем единый механизм план-ордеров (pos_loss), аналогично TP (pos_profit)
                plan_client_oid = self._generate_client_oid("sl", symbol, pos_side)
                plan_order = await self.create_plan_order(
                    symbol=symbol,
                    side=sl_side,
                    size=position_amount,
                    trigger_price=stop_price,
                    plan_type="pos_loss",
                    trigger_type="mark_price",
                    pos_side=pos_side,
                    reduce_only=reduce_only,
                    client_oid=plan_client_oid,
                )
                if plan_order:
                    logger.info("✅ [SL Order] Bitget pos_loss план размещён: %s", plan_order)
                else:
                    logger.warning("⚠️ [SL Order] Bitget не принял pos_loss для %s", symbol)
                return plan_order

            # Fallback для остальных бирж/режимов: обычный лимитный reduceOnly ордер
            order = await self.create_limit_order(
                symbol=symbol,
                side=sl_side,
                amount=position_amount,
                price=stop_price,
                reduce_only=reduce_only,
            )

            if order:
                logger.info(
                    "✅ [SL Order] Reduce-only стоп выставлен: %s, id=%s", symbol, order.get("id")
                )
            else:
                logger.warning("⚠️ [SL Order] Не удалось выставить защитный ордер для %s", symbol)

            return order

        except Exception as exc:
            logger.error(
                "❌ [SL Order] Ошибка выставления защитного ордера: %s", exc, exc_info=True
            )
            return None

    # NOTE: Удалена дублирующаяся и некорректная реализация place_take_profit_order
    # (использовала неинициализированную переменную pos_side). Оставлена корректная
    # реализация ниже в файле (с передачей pos_side).

    async def create_plan_order(
        self,
        symbol: str,
        side: str,
        size: float,
        trigger_price: float,
        execute_price: float = 0.0,
        plan_type: str = "profit_loss",
        trigger_type: str = "mark_price",
        pos_side: Optional[str] = None,
        reduce_only: bool = True,
        client_oid: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Создает план-ордер (условный) на Bitget."""
        try:
            if not self._ensure():
                return None

            if self.exchange_name != "bitget":
                logger.warning(
                    "⚠️ [Plan Order] План-ордера поддерживаются только для Bitget, пропускаем"
                )
                return None

            market = None
            try:
                market = self.client.market(symbol)
            except Exception:
                market = None

            margin_coin = "USDT"
            product_type = None
            symbol_param = None
            if market:
                margin_coin = (market.get("settle") or market.get("quote") or "USDT") or "USDT"
                market_info = market.get("info") or {}
                symbol_param = market_info.get("symbol") or market.get("id") or symbol
                product_type = market_info.get("productType") or market_info.get("productTypeCode")
                if not product_type:
                    settle = (market.get("settle") or "").upper()
                    if settle == "USDT":
                        product_type = "umcbl"
                    elif settle == "USDC":
                        product_type = "cmcbl"
                    elif settle == "BTC":
                        product_type = "dmcbl"
                    elif settle == "ETH":
                        product_type = "emcbl"
                margin_coin = str(margin_coin).upper()

                # В Bitget V2 (mix) используется формат 'BTCUSDT' (без суффикса)
                # или формат ccxt 'BTC/USDT:USDT'. Для raw API обычно просто BTCUSDT.
                symbol_param = market_info.get("symbol") or market.get("id") or symbol
                # Убираем разделители для Bitget V2 raw API
                symbol_param = str(symbol_param).replace("/", "").replace(":", "").replace("-", "")

            if not symbol_param:
                symbol_param = symbol.replace("/", "").replace(":", "").replace("-", "")

            if not product_type:
                product_type = "umcbl"
            product_type = str(product_type).lower()

            try:
                size_precise = self.client.amount_to_precision(symbol, size)
            except Exception:
                size_precise = str(size)

            try:
                trigger_price_precise = self.client.price_to_precision(symbol, trigger_price)
            except Exception:
                trigger_price_precise = str(trigger_price)

            client_oid_final = client_oid or self._generate_client_oid("plan", symbol, pos_side)

            payload = {
                "symbol": symbol_param,
                "productType": product_type,
                "marginCoin": margin_coin,
                "size": str(size_precise),
                "side": side.lower(),
                "planType": plan_type,
                "triggerPrice": str(trigger_price_precise),
                "triggerType": trigger_type,
                "reduceOnly": bool(reduce_only),
                "marginMode": "isolated",
                "orderType": "market" if trigger_type == "mark_price" else "limit",
                "clientOid": client_oid_final,
            }

            if pos_side:
                payload["posSide"] = pos_side
                payload["holdSide"] = pos_side

            if trigger_type == "limit_price" and execute_price:
                try:
                    payload["executePrice"] = str(
                        self.client.price_to_precision(symbol, execute_price)
                    )
                except Exception:
                    payload["executePrice"] = str(execute_price)

            response = None

            # 🔧 ИСПРАВЛЕНО: V1 API Bitget больше не поддерживается. Переходим сразу к V2.
            if response is None:
                # Bitget V2 имеет специализированный эндпоинт для TPSL (pos_loss/pos_profit)
                if plan_type in ("pos_loss", "pos_profit"):
                    # Для TPSL эндпоинта Bitget V2 использует 'holdSide' вместо 'posSide'
                    if pos_side:
                        payload["holdSide"] = pos_side
                        if "posSide" in payload:
                            del payload["posSide"]

                    method_name = "privateMixPostV2MixOrderPlaceTpslOrder"
                    logger.info("📋 [TPSL Order] Bitget V2 request (%s): %s", method_name, payload)
                else:
                    method_name = "privateMixPostV2MixOrderPlacePlanOrder"
                    logger.info("📋 [Plan Order] Bitget V2 request (%s): %s", method_name, payload)

                plan_method_raw = getattr(self.client, method_name, None)
                if not callable(plan_method_raw):
                    raise RuntimeError(f"Bitget {method_name} API недоступен в текущей версии ccxt")

                plan_method = cast(Callable[[Dict[str, Any]], Any], plan_method_raw)
                response = plan_method(payload)
                if inspect.isawaitable(response):
                    response = await response
            logger.info("📋 [Plan Order] Bitget response: %s", response)

            if not isinstance(response, dict):
                raise RuntimeError(f"Неожиданный ответ Bitget: {response}")

            code = response.get("code")
            if code not in (None, "00000", 0):
                raise RuntimeError(f"Bitget отклонил план-ордер: {response}")

            data = response.get("data") or {}
            order_id = data.get("orderId") or data.get("planOrderId")
            if not order_id:
                logger.warning("⚠️ [Plan Order] Ответ Bitget без orderId: %s", response)
            return {
                "id": order_id,
                "raw": response,
                "side": side.lower(),
                "plan_type": plan_type,
                "trigger_price": trigger_price,
            }

        except Exception as exc:
            logger.error("❌ [Plan Order] Ошибка создания план-ордера: %s", exc, exc_info=True)
            return None

    async def place_take_profit_order(
        self,
        symbol: str,
        direction: str,
        position_amount: float,
        take_profit_price: float,
        reduce_only: bool = True,
        client_tag: str = "tp1",
    ) -> Optional[Dict[str, Any]]:
        """
        Выставляет take-profit для позиции.

        🆕 ИСПРАВЛЕНО: Для TP1 используем обычный limit order вместо profit_plan,
        так как Bitget profit_plan может игнорировать параметр size и закрывать всю позицию.
        Для TP2 используем profit_plan (он должен закрывать оставшиеся 50%).
        """
        try:
            if not self._ensure():
                return None

            direction_norm = (direction or "").upper()
            is_short_position = direction_norm in ("SELL", "SHORT")
            tp_side = "buy" if is_short_position else "sell"

            logger.info(
                "🎯 [TP Order] %s → direction=%s, trigger=%.8f, amount=%.4f, tag=%s",
                symbol,
                direction_norm or "?",
                take_profit_price,
                position_amount,
                client_tag,
            )

            # 🆕 ДЛЯ TP1: Используем обычный limit order (Bitget profit_plan игнорирует size для TP1)
            if client_tag == "tp1":
                logger.info(
                    "🔧 [TP1] %s: Используем обычный limit order вместо profit_plan "
                    "(Bitget игнорирует size для profit_plan)",
                    symbol,
                )
                order = await self.create_limit_order(
                    symbol=symbol,
                    side=tp_side,
                    amount=position_amount,
                    price=take_profit_price,
                    reduce_only=reduce_only,
                )

                if order:
                    logger.info(
                        "✅ [TP1 Order] Limit order TP1 выставлен: %s, id=%s, size=%.4f",
                        symbol,
                        order.get("id"),
                        position_amount,
                    )
                else:
                    logger.warning("⚠️ [TP1 Order] Не удалось выставить TP1 для %s", symbol)

                return order

            # ДЛЯ TP2: Используем pos_profit (специализированный TPSL эндпоинт)
            if self.exchange_name == "bitget" and self.trade_mode == "futures":
                plan_client_oid = self._generate_client_oid(
                    client_tag,
                    symbol,
                    "short" if is_short_position else "long",
                )
                plan_order = await self.create_plan_order(
                    symbol=symbol,
                    side=tp_side,
                    size=position_amount,
                    trigger_price=take_profit_price,
                    plan_type="pos_profit",
                    trigger_type="mark_price",
                    pos_side="short" if is_short_position else "long",
                    reduce_only=reduce_only,
                    client_oid=plan_client_oid,
                )
                if plan_order:
                    logger.info(
                        "✅ [TP2 Order] Bitget pos_profit план размещён: %s, size=%.4f",
                        plan_order,
                        position_amount,
                    )
                    return plan_order

                # Fallback для TP2: обычный limit order
                logger.warning(
                    "⚠️ [TP2 Order] Bitget не принял pos_profit для %s, пробуем обычный limit order",
                    symbol,
                )

            # Общий fallback: обычный лимитный reduceOnly ордер
            order = await self.create_limit_order(
                symbol=symbol,
                side=tp_side,
                amount=position_amount,
                price=take_profit_price,
                reduce_only=reduce_only,
            )

            if order:
                logger.info(
                    "✅ [TP Order] Reduce-only TP выставлен: %s, id=%s", symbol, order.get("id")
                )
            else:
                logger.warning("⚠️ [TP Order] Не удалось выставить TP для %s", symbol)

            return order

        except Exception as exc:
            logger.error("❌ [TP Order] Ошибка выставления take-profit: %s", exc, exc_info=True)
            return None

    async def fetch_plan_orders(self, symbol: Optional[str] = None) -> list:
        """
        Возвращает список активных план-ордеров Bitget (если поддерживается текущей версией ccxt).
        Используется только для мониторинга/верификации (не критично для исполнения).
        """
        try:
            if not self._ensure():
                return []
            if self.exchange_name != "bitget" or self.trade_mode != "futures":
                return []
            # Попытка вызвать один из доступных raw-эндпоинтов ccxt Bitget:
            # V2 pending plan orders
            candidates = [
                "privateMixGetV2MixOrderOrdersPlanPending",
                "privateMixGetMixOrderOrdersPlanPending",
                "privateMixGetPlanCurrentPlan",
            ]
            for name in candidates:
                method = getattr(self.client, name, None)
                if callable(method):
                    try:
                        # Некоторые эндпоинты принимают фильтры; вызываем без фильтра для упрощения
                        method_callable = cast(Callable[[Dict[str, Any]], Any], method)
                        resp = method_callable({})  # pylint: disable=not-callable
                        if isinstance(resp, dict):
                            data = resp.get("data") or []
                        else:
                            data = resp or []
                        # Нормализуем в список словарей
                        if isinstance(data, dict):
                            data = [data]
                        return data or []
                    except Exception as e:
                        logger.debug("[PlanOrders] %s failed: %s", name, e)
                        continue
            logger.debug("[PlanOrders] Raw API not available in this ccxt version")
            return []
        except Exception as exc:
            logger.error("❌ [PlanOrders] Ошибка получения план-ордеров: %s", exc, exc_info=True)
            return []

    async def cancel_order(self, order_id: str, symbol: str, is_plan_order: bool = False) -> bool:
        """
        Отменяет ордер по ID

        Args:
            order_id: ID ордера
            symbol: Символ
            is_plan_order: Если True, использует специальный метод для план-ордеров Bitget
        """
        try:
            if not self._ensure():
                return False

            # Для план-ордеров Bitget используем специальный метод
            if is_plan_order and self.exchange_name == "bitget" and self.trade_mode == "futures":
                return await self._cancel_plan_order_bitget(order_id, symbol)

            logger.info("🗑️ [Cancel] Отменяю ордер %s для %s", order_id, symbol)
            result = await self.client.cancel_order(order_id, symbol)
            logger.info("✅ [Cancel] Ордер отменён: %s", result)
            return True

        except Exception as exc:
            logger.error("❌ [Cancel] Ошибка отмены ордера: %s", exc, exc_info=True)
            return False

    async def _cancel_plan_order_bitget(self, order_id: str, symbol: str) -> bool:
        """Отменяет план-ордер на Bitget через raw API"""
        try:
            # Пробуем разные методы отмены план-ордеров Bitget
            cancel_methods = [
                "privateMixPostV2MixOrderCancelPlanOrder",
                "privateMixPostMixOrderCancelPlanOrder",
                "privateMixPostPlanCancelPlan",
            ]

            # Получаем market info для правильного формата symbol
            market = None
            try:
                market = self.client.market(symbol)
            except Exception:
                pass

            symbol_param = symbol
            if market:
                market_info = market.get("info") or {}
                symbol_param = market_info.get("symbol") or market.get("id") or symbol
                if symbol_param and "_" not in symbol_param:
                    settle = (market.get("settle") or "USDT").upper()
                    suffix_map = {"USDT": "UMCBL", "USDC": "CMCBL", "BTC": "DMCBL", "ETH": "EMCBL"}
                    suffix = suffix_map.get(settle, "UMCBL")
                    base = re.sub(r"[^A-Za-z0-9]", "", symbol_param)
                    symbol_param = f"{base}_{suffix}"

            for method_name in cancel_methods:
                method = getattr(self.client, method_name, None)
                if callable(method):
                    try:
                        payload = {
                            "orderId": str(order_id),
                            "symbol": symbol_param,
                        }
                        method_callable = cast(Callable[[Dict[str, Any]], Any], method)
                        response = await method_callable(payload)  # pylint: disable=not-callable  # type: ignore[call-arg]

                        if isinstance(response, dict):
                            code = response.get("code")
                            if code in (None, "00000", 0):
                                logger.info(
                                    "✅ [Cancel Plan] План-ордер %s отменён на Bitget", order_id
                                )
                                return True
                            else:
                                logger.warning(
                                    "⚠️ [Cancel Plan] Bitget отклонил отмену: %s", response
                                )
                        else:
                            logger.info(
                                "✅ [Cancel Plan] План-ордер %s отменён (ответ: %s)",
                                order_id,
                                response,
                            )
                            return True
                    except Exception as e:
                        logger.debug("⚠️ [Cancel Plan] Метод %s не сработал: %s", method_name, e)
                        continue

            logger.warning(
                "⚠️ [Cancel Plan] Не удалось отменить план-ордер %s через Bitget API", order_id
            )
            return False

        except Exception as exc:
            logger.error("❌ [Cancel Plan] Ошибка отмены план-ордера: %s", exc, exc_info=True)
            return False

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> list:
        """Получает список открытых ордеров"""
        try:
            if not self._ensure():
                return []

            if symbol:
                orders = await self.client.fetch_open_orders(symbol)
            else:
                orders = await self.client.fetch_open_orders()

            logger.debug("📋 [Orders] Открытых ордеров: %d", len(orders or []))
            return orders or []

        except Exception as exc:
            logger.error("❌ [Orders] Ошибка получения открытых ордеров: %s", exc, exc_info=True)
            return []
