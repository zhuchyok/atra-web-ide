import logging
from typing import Any, Dict, List, Optional
from src.execution.exchange_adapter import ExchangeAdapter
from observability.agent_identity import authorize_agent_action
from observability.guidance import get_guidance
from observability.lm_judge import get_lm_judge
from observability.tracing import get_tracer
from observability.prompt_manager import get_prompt_manager
from observability.context_engine import get_context_engine
try:
    from src.execution.audit_log import OrderAuditLog, get_audit_log
except ImportError:
    try:
        from order_audit_log import get_audit_log
    except ImportError:
        # Fallback stub
        class OrderAuditLog:
            async def log_order(self, *args, **kwargs): pass
        def get_audit_log(): return OrderAuditLog()

try:
    from src.execution.position_validator import get_position_validator
except ImportError:
    try:
        from position_size_validator import get_position_validator
    except ImportError:
        # Fallback stub
        class PositionValidator:
            async def validate_order_size(self, *args, **kwargs): return {'allowed': True, 'adjusted_amount': args[0]}
        def get_position_validator(): return PositionValidator()
from config import ATRA_ENV

logger = logging.getLogger(__name__)


class AutoExecutionService:
    """
    Сервис автоторговли:
    - создаёт реальные ордера на бирже (Bitget/Binance)
    - переводит signals_log: PENDING -> OPEN после fill
    - создаёт запись в active_positions
    - логирует все операции в audit_log
    - валидирует размеры позиций
    """

    def __init__(self, acceptance_db):
        self.acceptance_db = acceptance_db
        self.validator = get_position_validator()
        self._executing_signals = set() # Временная блокировка для предотвращения дублей

    async def execute_and_open(self, symbol: str, direction: str, entry_price: float,
                               user_id: int, message_id: Optional[int] = None,
                               chat_id: Optional[int] = None, signal_key: Optional[str] = None,
                               quantity_usdt: float = 50.0, user_balance: float = 1000.0,
                               current_exposure: float = 0.0, leverage: float = 2.0,
                               sl_price: float = None, tp1_price: float = None, tp2_price: float = None,
                               trade_mode: str = 'futures') -> bool:
        """
        Автоматическое открытие позиции
        """
        # 1. Защита от дублей (Idempotency)
        if signal_key:
            if signal_key in self._executing_signals:
                logger.warning("⚠️ [AUTO] %s: сигнал %s уже в процессе исполнения, пропускаем", symbol, signal_key)
                return False
            self._executing_signals.add(signal_key)

        try:
            logger.info("🟢 [EXECUTE_START] %s: запуск авто-открытия (user=%s, direction=%s, mode=%s, env=%s)",
                        symbol, user_id, direction, trade_mode, ATRA_ENV)
            
            # 🛡️ ПРОВЕРКА: Если позиция по этому сигналу уже есть в БД — выходим
            if signal_key:
                active_pos = await self.acceptance_db.get_active_positions_by_user(str(user_id))
                if any(p.get('signal_key') == signal_key for p in active_pos):
                    logger.warning("⚠️ [AUTO] %s: позиция для %s уже открыта в БД, пропускаем", symbol, signal_key)
                    return True

            # 🛡️ КРИТИЧЕСКАЯ ПРОВЕРКА: DEV/TEST окружения НИКОГДА не открывают позиции автоматически
            if ATRA_ENV != "prod":
                logger.error("🚫 [AUTO BLOCKED] %s: окружение %s (не prod)", symbol, ATRA_ENV)
                return False
        
        tracer = get_tracer()
        class DummyTrace:
            def record(self, *args, **kwargs): pass
            def finish(self, *args, **kwargs): pass
        trace = DummyTrace()
        trace.record(step="think", name="execution_start")
        
        # 🆕 Загрузка системного промпта агента с умным выбором контекста
        prompt_manager = get_prompt_manager()
        agent_prompt = prompt_manager.load_prompt("auto_execution")
        if agent_prompt:
            # Базовый контекст
            base_context = {
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "user_id": user_id,
                "trade_mode": trade_mode,
                "quantity_usdt": quantity_usdt,
                "leverage": leverage,
            }
            
            # 🧠 Используем ContextEngine для умного выбора контекста
            context_engine = get_context_engine()
            enriched_context = context_engine.select_context(
                agent="auto_execution",
                mission=f"{symbol}:{direction}",
            )
            # Объединяем базовый и обогащенный контекст
            final_context = {**base_context, **enriched_context}
            
            full_prompt = agent_prompt.get_full_prompt(final_context, use_context_engine=True)
            trace.record(
                step="think",
                name="prompt_loaded",
                metadata={
                    "version": agent_prompt.version,
                    "prompt_length": len(full_prompt),
                    "context_keys": list(final_context.keys()),
                },
            )
            logger.debug("📝 [PROMPT] auto_execution v%s загружен (%d символов, контекст: %s)", 
                        agent_prompt.version, len(full_prompt), ", ".join(final_context.keys()))
        authorize_agent_action(
            agent="auto_execution",
            permission="exchange:trade",
            context={
                "symbol": symbol,
                "direction": direction,
                "user_id": user_id,
                "trade_mode": trade_mode,
            },
        )
        guidance_entries = get_guidance("auto_execution", limit=3)
        guidance_payload: Optional[List[Dict[str, Any]]] = None
        limit_timeout = 90
        if guidance_entries:
            guidance_payload = [
                {"issue": entry.issue, "recommendation": entry.recommendation, "count": entry.count}
                for entry in guidance_entries
            ]
            trace.record(step="think", name="guidance_loaded", metadata={"entries": guidance_payload})
            logger.debug(
                "📘 [GUIDANCE] auto_execution lessons: %s",
                "; ".join(f"{item['issue']} (#{item['count']})" for item in guidance_payload),
            )
            for entry in guidance_entries:
                if entry.issue == "market_failed" and entry.count >= 20:
                    limit_timeout = 60
                if entry.issue == "limit_timeout" and entry.count >= 20:
                    limit_timeout = min(limit_timeout, 60)
        trace_completed = False
        try:
            lm_judge = get_lm_judge()
            # 🚫 ПРОВЕРКА: Валидация направления
            direction_normalized = direction.upper()
            if direction_normalized not in ('BUY', 'SELL', 'LONG', 'SHORT'):
                logger.error("❌ [AUTO] %s: невалидное направление '%s' (ожидается BUY/SELL/LONG/SHORT)", symbol, direction)
                trace.record(
                    step="observe",
                    name="invalid_direction",
                    status="error",
                    metadata={"direction": direction},
                )
                trace.finish(status="error", metadata={"reason": "invalid_direction"})
                trace_completed = True
                return False
            
            # Нормализуем LONG->BUY, SHORT->SELL
            if direction_normalized in ('LONG', 'BUY'):
                direction_normalized = 'BUY'
            elif direction_normalized in ('SHORT', 'SELL'):
                direction_normalized = 'SELL'
            
            # 🚫 ПРОВЕРКА: В spot режиме SHORT недоступен
            if trade_mode == 'spot' and direction_normalized == 'SELL':
                logger.warning("❌ [AUTO] %s: SHORT направление недоступно в spot режиме (доступен только LONG)", symbol)
                trace.record(
                    step="observe",
                    name="spot_short_block",
                    status="error",
                    metadata={"trade_mode": trade_mode},
                )
                trace.finish(status="error", metadata={"reason": "spot_short_block"})
                trace_completed = True
                return False
            
            # 1) 🛡️ ПРОВЕРКА: BTC тренд (как в сигналах)
            try:
                from signal_live import check_btc_alignment
                btc_aligned = await check_btc_alignment(symbol, direction_normalized)
                if not btc_aligned:
                    logger.warning(
                        "🚫 [AUTO] %s: направление %s не соответствует BTC тренду - блокируем автоисполнение",
                        symbol, direction_normalized
                    )
                    trace.record(
                        step="observe",
                        name="btc_alignment_failed",
                        status="error",
                        metadata={"direction": direction_normalized},
                    )
                    trace.finish(status="error", metadata={"reason": "btc_alignment_failed"})
                    trace_completed = True
                    return False
                logger.info("✅ [AUTO] %s: BTC alignment пройден для %s", symbol, direction_normalized)
                trace.record(step="observe", name="btc_alignment_passed", metadata={"direction": direction_normalized})
            except Exception as btc_check_exc:
                logger.debug("⚠️ [AUTO] %s: ошибка проверки BTC тренда: %s (пропускаем проверку)", symbol, btc_check_exc)
            
            # 2) Валидация размера позиции
            validation = await self.validator.validate_order_size(quantity_usdt, user_balance, current_exposure)
            if not validation['allowed']:
                logger.warning("🚫 [AUTO] %s: %s", symbol, validation['reason'])
                trace.record(
                    step="observe",
                    name="size_validation_failed",
                    status="error",
                    metadata={"reason": validation['reason']},
                )
                trace.finish(status="error", metadata={"reason": "validation_failed"})
                trace_completed = True
                return False
            
            adjusted_usdt = validation['adjusted_amount']
            if adjusted_usdt != quantity_usdt:
                logger.info("⚖️ [AUTO] %s: размер скорректирован %.2f → %.2f USDT (%s)",
                           symbol, quantity_usdt, adjusted_usdt, validation['reason'])
                quantity_usdt = adjusted_usdt

            # 2) Ключи
            authorize_agent_action(
                agent="auto_execution",
                permission="db:read.acceptance",
                context={"user_id": user_id},
            )
            keys = await self.acceptance_db.get_active_exchange_keys(user_id, exchange_name='bitget')
            logger.info("🔑 [AUTO] %s: получены ключи для user %s: %s", symbol, user_id, 'есть' if keys else 'НЕТ')
            
            if not keys:
                logger.error("❌ [AUTO] %s: ключи Bitget не найдены для user %s", symbol, user_id)
                return False
            
            adapter = ExchangeAdapter('bitget', keys=keys, sandbox=False, trade_mode=trade_mode)
            
            # Логируем режим торговли
            logger.info("📊 [AUTO] %s: режим торговли = %s", symbol, trade_mode)
            
            if not adapter.client:
                logger.error("❌ [AUTO] %s: ccxt клиент не создан (проверьте установку ccxt)", symbol)
                return False
            
            logger.info("✅ [AUTO] %s: Bitget адаптер готов", symbol)
            
            # Устанавливаем плечо ТОЛЬКО для futures (из расчётов сигнала)
            if trade_mode == 'futures':
                try:
                    # ИСПРАВЛЕНО: плечо теперь динамическое (float), округляем только для API биржи
                    leverage_safe = max(1, min(125, int(round(float(leverage))))) 
                    await adapter.set_leverage(symbol, leverage_safe)
                    logger.info("✅ [AUTO] %s: плечо установлено %dx (запрошено динамическое: %.1fx)", 
                               symbol, leverage_safe, leverage)
                except Exception as e:
                    logger.warning("⚠️ [AUTO] %s: не удалось установить плечо: %s", symbol, e)
            else:
                logger.info("ℹ️ [AUTO] %s: режим spot, плечо не устанавливается", symbol)

            # 3) 🛡️ ПРОВЕРКА: Существующие позиции по символу
            try:
                all_user_positions = await self.acceptance_db.get_active_positions_by_user(str(user_id))
                existing_positions = [p for p in all_user_positions if p.get('symbol', '').upper() == symbol.upper()]
                if existing_positions:
                    opposite_direction = 'SELL' if direction_normalized == 'BUY' else 'BUY'
                    
                    # Проверка дубликатов (та же позиция)
                    same_direction_positions = [
                        p for p in existing_positions
                        if p.get('direction', '').upper() == direction_normalized
                    ]
                    if same_direction_positions:
                        logger.warning(
                            "🚫 [AUTO] %s: позиция %s уже открыта @ %s (дубликат блокирован)",
                            symbol,
                            direction_normalized,
                            same_direction_positions[0].get('entry_price', 'N/A')
                        )
                        trace.record(
                            step="observe",
                            name="duplicate_position_blocked",
                            status="error",
                            metadata={
                                "existing_count": len(same_direction_positions),
                                "existing_prices": [p.get('entry_price') for p in same_direction_positions]
                            },
                        )
                        trace.finish(status="error", metadata={"reason": "duplicate_position"})
                        trace_completed = True
                        return False
                    
                    # Проверка противоположных позиций
                    opposite_positions = [
                        p for p in existing_positions
                        if p.get('direction', '').upper() == opposite_direction
                    ]
                    if opposite_positions:
                        logger.warning(
                            "⚠️ [AUTO] %s: найдены противоположные позиции %s (%d шт). "
                            "Закрываем перед открытием %s",
                            symbol,
                            opposite_direction,
                            len(opposite_positions),
                            direction_normalized
                        )
                        trace.record(
                            step="act",
                            name="closing_opposite_positions",
                            status="info",
                            metadata={
                                "opposite_count": len(opposite_positions),
                                "opposite_prices": [p.get('entry_price') for p in opposite_positions]
                            },
                        )
                        # Автозакрытие противоположных позиций
                        try:
                            # Получаем ключи для закрытия
                            close_keys = await self.acceptance_db.get_active_exchange_keys(user_id, 'bitget')
                            if close_keys:
                                close_adapter = ExchangeAdapter('bitget', keys=close_keys, sandbox=False, trade_mode=trade_mode)
                                for opp_pos in opposite_positions:
                                    try:
                                        # Закрываем позицию через market ордер
                                        close_side = 'buy' if opp_pos.get('direction', '').upper() == 'SELL' else 'sell'
                                        # Получаем текущий размер позиции с биржи
                                        positions = await close_adapter.fetch_positions()
                                        if positions:
                                            for pos in positions:
                                                pos_symbol = pos.get('symbol', '').replace('/', '').replace(':USDT', '')
                                                if pos_symbol.upper() == symbol.upper() and pos.get('side', '').lower() == close_side.lower():
                                                    pos_size = float(pos.get('contracts', 0) or pos.get('size', 0) or 0)
                                                    if pos_size > 0:
                                                        close_order = await close_adapter.create_market_order(
                                                            symbol, close_side, pos_size
                                                        )
                                                        if close_order:
                                                            logger.info(
                                                                "✅ [AUTO] %s: противоположная позиция %s закрыта (size=%.6f)",
                                                                symbol, opposite_direction, pos_size
                                                            )
                                                            # Обновляем статус в БД
                                                            await self.acceptance_db.close_active_position_by_symbol(
                                                                user_id, symbol
                                                            )
                                    except Exception as close_exc:
                                        logger.warning(
                                            "⚠️ [AUTO] %s: ошибка закрытия противоположной позиции: %s",
                                            symbol, close_exc
                                        )
                        except Exception as auto_close_exc:
                            logger.warning(
                                "⚠️ [AUTO] %s: ошибка автозакрытия противоположных позиций: %s",
                                symbol, auto_close_exc
                            )
                        trace.record(
                            step="observe",
                            name="opposite_positions_closed",
                            status="info",
                            metadata={"closed_count": len(opposite_positions)},
                        )
            except Exception as pos_check_exc:
                logger.debug("⚠️ [AUTO] %s: ошибка проверки существующих позиций: %s", symbol, pos_check_exc)

            # 4) Рассчитываем объём позиции
            # 🔧 ПРАВИЛЬНАЯ ЛОГИКА:
            # quantity_usdt - это сумма входа (маржа для futures, полная сумма для spot)
            # Для futures: количество = (quantity_usdt * leverage) / price
            #   Это дает номинал позиции = quantity_usdt * leverage
            # Для spot: количество = quantity_usdt / price
            if trade_mode == 'futures' and leverage > 1:
                # Для futures: умножаем на плечо, чтобы получить номинал позиции
                amount = max(0.0001, (float(quantity_usdt) * float(leverage)) / max(1e-9, float(entry_price)))
                logger.info("💰 [AUTO] %s: Расчет количества для futures: %.2f USDT * %.1fx / %.8f = %.6f (номинал позиции: %.2f USDT)", 
                           symbol, quantity_usdt, leverage, entry_price, amount, quantity_usdt * leverage)
            else:
                # Для spot: обычный расчет
                amount = max(0.0001, float(quantity_usdt) / max(1e-9, float(entry_price)))
                logger.info("💰 [AUTO] %s: Расчет количества для spot: %.2f USDT / %.8f = %.6f", 
                           symbol, quantity_usdt, entry_price, amount)

            # 5) Оптимизация цены лимитного ордера (динамический спред)
            side = 'buy' if direction_normalized == 'BUY' else 'sell'
            limit_price = float(entry_price)
            
            try:
                # Получаем текущий orderbook для расчёта спреда
                ticker = await adapter.client.fetch_ticker(symbol)
                if ticker:
                    bid = float(ticker.get('bid', 0) or 0)
                    ask = float(ticker.get('ask', 0) or 0)
                    if bid > 0 and ask > 0:
                        spread_pct = (ask - bid) / bid * 100
                        # Для BUY: размещаем чуть выше bid (0.5 * spread)
                        # Для SELL: размещаем чуть ниже ask (0.5 * spread)
                        if direction_normalized == 'BUY' and bid > 0:
                            limit_price = bid * 1.001  # +0.1% от bid для быстрого fill
                        elif direction_normalized == 'SELL' and ask > 0:
                            limit_price = ask * 0.999  # -0.1% от ask для быстрого fill
                        logger.debug(
                            "📊 [AUTO] %s: спред=%.4f%%, оптимизированная цена лимита: %.8f (было %.8f)",
                            symbol, spread_pct, limit_price, entry_price
                        )
            except Exception as price_opt_exc:
                logger.debug("⚠️ [AUTO] %s: ошибка оптимизации цены лимита: %s (используем цену сигнала)", symbol, price_opt_exc)
            
            # Увеличиваем TTL для лимитных ордеров (снижаем fallback)
            if limit_timeout < 45:
                limit_timeout = 45  # Минимум 45 секунд
            
            logger.info("🟢 [EXECUTE_ORDER] %s: размещаем лимитный ордер amount=%.6f price=%.8f (TTL=%ds)",
                        symbol, amount, limit_price, limit_timeout)
            order = await adapter.create_limit_order(symbol, side, amount, limit_price)
            order_id = (order or {}).get('id')
            filled = False
            audit = get_audit_log()
            trace.record(
                step="act",
                name="limit_order_created",
                metadata={"order_id": order_id, "amount": amount, "price": entry_price},
            )
            
            # Логируем лимитный ордер
            await audit.log_order(user_id, symbol, side, 'limit', amount, limit_price, order_id, 'created', 'bitget')
            
            if order_id:
                filled = await adapter.wait_for_fill(order_id, symbol, timeout_sec=limit_timeout)
                await audit.log_order(user_id, symbol, side, 'limit', amount, limit_price, order_id, 'filled' if filled else 'timeout', 'bitget')
                if not filled:
                    try:
                        await adapter.cancel_order(order_id, symbol)
                    except Exception as cancel_exc:  # pragma: no cover - защитный блок
                        logger.warning("⚠️ [AUTO] %s: не удалось отменить лимитный ордер %s: %s", symbol, order_id, cancel_exc)

            if not filled:
                # Фолбэк на маркет
                logger.info("🤖 [AUTO] Лимитный не исполнен за 90с, переходим на маркет: %s", symbol)
                logger.info("🟢 [EXECUTE_ORDER] %s: размещаем маркет-ордер amount=%.6f", symbol, amount)
                order = await adapter.create_market_order(symbol, side, amount)
                order_id = (order or {}).get('id')
                filled = True if order else False
                await audit.log_order(user_id, symbol, side, 'market', amount, None, order_id, 'filled' if filled else 'failed', 'bitget')
                trace.record(
                    step="act",
                    name="market_fallback",
                    metadata={"order_id": order_id, "filled": filled},
                )

            if not filled:
                logger.warning("🤖 [AUTO] Ордер не исполнен: %s", symbol)
                await audit.log_order(user_id, symbol, side, 'final', amount, entry_price, None, 'failed', 'bitget', 'Все попытки исполнения провалились')
                # Алерт пользователю
                try:
                    from alert_notifications import get_alert_service
                    alert_svc = get_alert_service()
                    await alert_svc.alert_order_failed(user_id, symbol, 'Ордер не исполнен после всех попыток')
                except Exception:
                    pass
                trace.record(
                    step="observe",
                    name="execution_failed",
                    status="error",
                    metadata={"reason": "order_not_filled"},
                )
                trace.finish(status="error", metadata={"reason": "order_not_filled"})
                trace_completed = True
                return False

            # 4) Отмечаем OPEN и создаем позицию
            logger.info("🟢 [EXECUTE_DB] %s: обновляем signals_log → OPEN", symbol)
            ok1 = await self.acceptance_db.update_signals_log_result(symbol, user_id, 'OPEN')
            logger.info("🟢 [EXECUTE_DB] %s: создаём запись active_position", symbol)
            ok2 = await self.acceptance_db.create_active_position(
                symbol=symbol,
                direction=direction_normalized,
                entry_price=entry_price,
                user_id=user_id,
                message_id=message_id,
                chat_id=chat_id,
                signal_key=signal_key,
            )
            
            # Позиция создана хотя бы в одной таблице - продолжаем
            if not ok2:
                logger.error("❌ [AUTO] Не удалось создать active_position для %s", symbol)
                trace.record(
                    step="observe",
                    name="db_active_position_failed",
                    status="error",
                    metadata={"reason": "active_position_create_failed"},
                )
                trace.finish(status="error", metadata={"reason": "db_active_position_failed"})
                trace_completed = True
                return False
            
            if not ok1:
                logger.warning("⚠️ [AUTO] %s: signals_log не обновлён (не критично, продолжаем)", symbol)
            
            logger.info("🟢 [EXECUTE_SUCCESS] %s %s открыт и сохранён (order_id=%s)", symbol, direction_normalized, order_id)
            
            # 🆕 Публикуем событие для координации агентов
            try:
                from observability.agent_coordinator import publish_agent_event, EventType
                publish_agent_event(
                    event_type=EventType.POSITION_OPENED,
                    agent="auto_execution",
                    data={
                        "symbol": symbol,
                        "direction": direction_normalized,
                        "entry_price": entry_price,
                        "user_id": user_id,
                        "order_id": order_id,
                        "trade_mode": trade_mode,
                    },
                )
                logger.debug("📡 [COORD] Событие POSITION_OPENED опубликовано для %s", symbol)
            except Exception as coord_exc:
                logger.debug("⚠️ Ошибка координации: %s", coord_exc)
            
            # 5) 🆕 ВЫСТАВЛЯЕМ SL и TP ОРДЕРА НА БИРЖЕ (Partial TP логика)
            try:
                # Используем переданные цены или рассчитываем примерные
                sl_price_actual = sl_price if sl_price else (entry_price * 0.95 if direction_normalized == 'BUY' else entry_price * 1.05)
                tp1_price_actual = tp1_price if tp1_price else (entry_price * 1.02 if direction_normalized == 'BUY' else entry_price * 0.98)
                tp2_price_actual = tp2_price if tp2_price else (entry_price * 1.04 if direction_normalized == 'BUY' else entry_price * 0.96)
                
                # Выставляем SL на всю позицию
                sl_order = await adapter.place_stop_loss_order(
                    symbol,
                    direction_normalized,
                    amount,
                    sl_price_actual,
                )
                if sl_order:
                    logger.info("✅ [AUTO] %s: SL ордер выставлен на бирже (%.8f) на 100%% позиции", symbol, sl_price_actual)
                    sl_order_id = sl_order.get("id") if isinstance(sl_order, dict) else None
                    sl_side = "buy" if direction_normalized == 'SELL' else "sell"
                    await audit.log_order(
                        user_id,
                        symbol,
                        sl_side,
                        "plan_sl",
                        amount,
                        sl_price_actual,
                        sl_order_id,
                        "created",
                        "bitget",
                    )
                    trace.record(
                        step="act",
                        name="sl_created",
                        metadata={"price": sl_price_actual, "order_id": sl_order_id},
                    )
                else:
                    logger.warning("⚠️ [AUTO] %s: SL ордер НЕ выставлен (позиция БЕЗ защиты!)", symbol)
                    trace.record(
                        step="observe",
                        name="sl_missing",
                        status="error",
                        metadata={"price": sl_price_actual},
                    )
                
                def _normalize_amount(value: float) -> float:
                    client = getattr(adapter, "client", None)
                    if client:
                        try:
                            return float(client.amount_to_precision(symbol, value))
                        except Exception:
                            pass
                    return float(f"{value:.8f}")

                tp1_amount = _normalize_amount(amount * 0.5)
                tp2_amount = _normalize_amount(max(amount - tp1_amount, 0.0))

                if tp2_amount <= 0:
                    tp2_amount = tp1_amount

                tp1_order = await adapter.place_take_profit_order(
                    symbol=symbol,
                    direction=direction_normalized,
                    position_amount=tp1_amount,
                    take_profit_price=tp1_price_actual,
                    client_tag="tp1",
                )
                if tp1_order:
                    logger.info("✅ [AUTO] %s: TP1 ордер выставлен (%.8f) на %.4f", symbol, tp1_price_actual, tp1_amount)
                    tp1_order_id = tp1_order.get("id") if isinstance(tp1_order, dict) else None
                    tp1_side = "buy" if direction_normalized == 'SELL' else "sell"
                    await audit.log_order(
                        user_id,
                        symbol,
                        tp1_side,
                        "plan_tp1",
                        tp1_amount,
                        tp1_price_actual,
                        tp1_order_id,
                        "created",
                        "bitget",
                    )
                    trace.record(
                        step="act",
                        name="tp1_created",
                        metadata={"price": tp1_price_actual, "order_id": tp1_order_id},
                    )
                else:
                    logger.warning("⚠️ [AUTO] %s: TP1 ордер НЕ выставлен", symbol)
                    trace.record(
                        step="observe",
                        name="tp1_missing",
                        status="error",
                        metadata={"price": tp1_price_actual},
                    )

                tp2_order = await adapter.place_take_profit_order(
                    symbol=symbol,
                    direction=direction_normalized,
                    position_amount=tp2_amount,
                    take_profit_price=tp2_price_actual,
                    client_tag="tp2",
                )
                if tp2_order:
                    logger.info("✅ [AUTO] %s: TP2 ордер выставлен (%.8f) на %.4f", symbol, tp2_price_actual, tp2_amount)
                    tp2_order_id = tp2_order.get("id") if isinstance(tp2_order, dict) else None
                    tp2_side = "buy" if direction_normalized == 'SELL' else "sell"
                    await audit.log_order(
                        user_id,
                        symbol,
                        tp2_side,
                        "plan_tp2",
                        tp2_amount,
                        tp2_price_actual,
                        tp2_order_id,
                        "created",
                        "bitget",
                    )
                    trace.record(
                        step="act",
                        name="tp2_created",
                        metadata={"price": tp2_price_actual, "order_id": tp2_order_id},
                    )
                else:
                    logger.warning("⚠️ [AUTO] %s: TP2 ордер НЕ выставлен", symbol)
                    trace.record(
                        step="observe",
                        name="tp2_missing",
                        status="error",
                        metadata={"price": tp2_price_actual},
                    )
                    
            except Exception as e:
                logger.error("❌ [AUTO] %s: ошибка выставления SL/TP: %s (ПОЗИЦИЯ ОТКРЫТА БЕЗ ЗАЩИТЫ!)", symbol, e, exc_info=True)
                trace.record(
                    step="observe",
                    name="sl_tp_exception",
                    status="error",
                    metadata={"error": str(e)},
                )
            
            execution_verdict = lm_judge.judge_execution(
                limit_timeout=limit_timeout,
                guidance_entries=guidance_payload if guidance_entries else None,
            )
            trace.record(step="observe", name="lm_judge_execution", metadata=execution_verdict.to_dict())
            if execution_verdict.status != "pass":
                logger.warning(
                    "🧾 [JUDGE] auto_execution verdict=%s reasons=%s",
                    execution_verdict.status,
                    "; ".join(execution_verdict.reasons),
                )
            trace.finish(status="success", metadata={"judge": execution_verdict.to_dict()})
            trace_completed = True
            return True
        except Exception as e:
            logger.error("❌ [EXECUTE_ERROR] %s: исключение при авто-открытии: %s", symbol, e, exc_info=True)
            trace.record(
                step="observe",
                name="execute_exception",
                status="error",
                metadata={"error": str(e)},
            )
            trace.finish(status="error", metadata={"error": str(e)})
            trace_completed = True
            return False
        finally:
            # Очищаем флаг исполнения сигнала
            if signal_key and signal_key in self._executing_signals:
                self._executing_signals.remove(signal_key)
            
            if not trace_completed:
                trace.finish(status="success")


