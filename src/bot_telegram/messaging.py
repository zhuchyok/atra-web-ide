"""Сообщения для Telegram-бота ATRA.

Модуль содержит функции-конструкторы HTML-сообщений: новый сигнал, подтверждение
принятия, DCA, достижения TP1/TP2, частичное и полное закрытие позиции, а также
сообщение о переносе SL в безубыток. Форматирование цен выполняется переданным
форматтером, чтобы сохранять точность котировок конкретного символа.
"""

from typing import Optional, Dict, Any, List
import re
from src.shared.utils.datetime_utils import get_utc_now


def build_tp1_message(
    symbol: str,
    side: str,
    entry_price: float,
    tp1: float,
    current_price: float,
    qty_closed: float,
    qty_remaining: float,
    leverage_multiplier: int,
    price_format,  # Может быть строкой формата или функцией
) -> str:
    """Строит HTML-сообщение о достижении TP1 (закрыто 50%).

    Значения цен форматируются через шаблон ``price_format``. Возвращает
    готовую HTML-строку для отправки в Telegram.
    """
    base_pct = (
        (tp1 - entry_price) / entry_price * 100.0
        if side.lower() == "long"
        else ((entry_price - tp1) / entry_price * 100.0)
    )
    levered_pct = base_pct * max(1, leverage_multiplier)

    # Поддерживаем как строку формата, так и функцию форматирования
    if callable(price_format):
        entry_str = price_format(entry_price, symbol)
        tp1_str = price_format(tp1, symbol)
        current_str = price_format(current_price, symbol)
    else:
        entry_str = price_format.format(entry_price)
        tp1_str = price_format.format(tp1)
        current_str = price_format.format(current_price)
    msg = (
        "🎯 <b>TP1 ДОСТИГНУТ — ЗАКРЫТО 50%!</b>\n\n"
        f"Символ: <code>{symbol}</code>\n"
        f"Сторона: <code>{side.upper()}</code>\n"
        f"Цена входа: <code>{entry_str}</code>\n"
        f"TP1: <code>{tp1_str}</code> "
        f"(<code>{base_pct:+.2f}%</code> / <code>{levered_pct:+.2f}%</code> с плечом)\n"
        f"Текущая цена: <code>{current_str}</code>\n"
        f"Закрыто: <code>{qty_closed:.4f}</code>\n"
        f"Остаток: <code>{qty_remaining:.4f}</code>\n\n"
        f"⚠️ <b>Внимание:</b> перенесите SL в <b>безубыток</b> на <code>{entry_str}</code>\n\n"
        f"➡️ Держим остаток до TP2"
    )
    return msg


def build_tp2_message(
    symbol: str,
    side: str,
    entry_price: float,
    tp2: float,
    current_price: float,
    qty_closed: float,
    leverage_multiplier: int,
    price_format,  # Может быть строкой формата или функцией
) -> str:
    """Строит HTML-сообщение о достижении TP2 (позиция закрыта).

    Значения цен форматируются через шаблон ``price_format``. Возвращает
    готовую HTML-строку для отправки в Telegram.
    """
    base_pct = (
        (tp2 - entry_price) / entry_price * 100.0
        if side.lower() == "long"
        else ((entry_price - tp2) / entry_price * 100.0)
    )
    levered_pct = base_pct * max(1, leverage_multiplier)

    # Поддерживаем как строку формата, так и функцию форматирования
    if callable(price_format):
        entry_str = price_format(entry_price, symbol)
        tp2_str = price_format(tp2, symbol)
        current_str = price_format(current_price, symbol)
    else:
        entry_str = price_format.format(entry_price)
        tp2_str = price_format.format(tp2)
        current_str = price_format.format(current_price)
    msg = (
        "🎉 <b>TP2 ДОСТИГНУТ — ПОЗИЦИЯ ЗАКРЫТА!</b>\n\n"
        f"Символ: <code>{symbol}</code>\n"
        f"Сторона: <code>{side.upper()}</code>\n"
        f"Цена входа: <code>{entry_str}</code>\n"
        f"TP2: <code>{tp2_str}</code> "
        f"(<code>{base_pct:+.2f}%</code> / <code>{levered_pct:+.2f}%</code> с плечом)\n"
        f"Текущая цена: <code>{current_str}</code>\n"
        f"Объём: <code>{qty_closed:.4f}</code>\n"
    )
    return msg


def build_accept_message(
    symbol: str,
    side: str,
    entry_price: float,
    tp1_price: float,
    tp2_price: float,
    qty: float,
    leverage: float,
    risk_amount: float,
    notional_usd: float,
    price_formatter,
) -> str:
    """Строит сообщение подтверждения принятия обычного сигнала.

    price_formatter: функция вида lambda v: str, которая форматирует цены по точности символа.
    """
    try:
        tp1_clean = (
            (tp1_price - entry_price) / entry_price * 100.0
            if side.lower() == "long"
            else ((entry_price - tp1_price) / entry_price * 100.0)
        )
        tp2_clean = (
            (tp2_price - entry_price) / entry_price * 100.0
            if side.lower() == "long"
            else ((entry_price - tp2_price) / entry_price * 100.0)
        )
    except (TypeError, ValueError):
        tp1_clean = 0.0
        tp2_clean = 0.0

    try:
        lev_used = float(leverage) if leverage else 1.0
    except (TypeError, ValueError):
        lev_used = 1.0

    tp1_lev = tp1_clean * lev_used
    tp2_lev = tp2_clean * lev_used

    entry_str = price_formatter(entry_price)
    tp1_str = price_formatter(tp1_price)
    tp2_str = price_formatter(tp2_price)

    parts = [
        "✅ <b>Сигнал принят!</b>\n\n",
        f"🔸 Символ: <code>{symbol}</code>\n",
        f"🔸 Сторона: <code>{side.upper()}</code>\n",
        f"🔸 Цена входа: <code>{entry_str}</code>\n",
    ]
    # Убираем вывод "Объём входа" — ниже уже показывается "Количество"
    parts.extend([
        (
            f"🔸 TP1: <code>{tp1_str}</code> "
            f"(<code>{tp1_clean:+.2f}%</code> / <code>{tp1_lev:+.2f}%</code> с плечом)\n"
        ),
        (
            f"🔸 TP2: <code>{tp2_str}</code> "
            f"(<code>{tp2_clean:+.2f}%</code> / <code>{tp2_lev:+.2f}%</code> с плечом)\n"
        ),
        f"🔸 Количество: <code>{qty:.6f}</code>\n",
        f"🔸 Плечо: <code>{int(round(float(lev_used)))}x</code>\n",
        f"🔸 Риск: <code>{float(risk_amount or 0.0):.2f}</code>\n",
        f"🔸 Сумма входа: <code>{int(round(float(notional_usd or 0.0)))}</code>\n\n",
        (
            "⚠️ <b>Внимание:</b> на <b>TP1</b> фиксируем "
            "<b>50%</b> позиции, остаток держим до <b>TP2</b>\n\n"
        ),
        f"⏰ Время принятия: <code>{get_utc_now().strftime('%H:%M:%S')}</code>",
    ])
    return "".join(parts)


def build_dca_accept_message(
    symbol: str,
    side: str,
    entry_price: float,
    qty: float,
    leverage: float,
    risk_amount: float,
    tp1_price: float,
    tp2_price: float,
    avg_price_new: float,
    dca_index: int,
    price_formatter,
) -> str:
    """Строит сообщение подтверждения DCA (усреднение).

    price_formatter: функция вида lambda v: str, которая форматирует цены по точности символа.
    """
    try:
        tp1_clean = (
            (tp1_price - entry_price) / entry_price * 100.0
            if side.lower() == "long"
            else ((entry_price - tp1_price) / entry_price * 100.0)
        )
        tp2_clean = (
            (tp2_price - entry_price) / entry_price * 100.0
            if side.lower() == "long"
            else ((entry_price - tp2_price) / entry_price * 100.0)
        )
    except (TypeError, ValueError):
        tp1_clean = 0.0
        tp2_clean = 0.0

    try:
        lev_used = float(leverage) if leverage else 1.0
    except (TypeError, ValueError):
        lev_used = 1.0

    tp1_lev = tp1_clean * lev_used
    tp2_lev = tp2_clean * lev_used

    entry_str = price_formatter(entry_price)
    tp1_str = price_formatter(tp1_price)
    tp2_str = price_formatter(tp2_price)
    avg_str = price_formatter(avg_price_new)
    entry_sum_usd = int(
        round(float(qty or 0.0) * float(entry_price or 0.0))
    )

    parts = [
        "📈 <b>DCA позиция добавлена!</b>\n\n",
        f"🔸 Символ: <code>{symbol}</code>\n",
        f"🔸 DCA #<code>{int(dca_index)}</code>\n",
        f"🔸 Цена входа: <code>{entry_str}</code>\n",
    ]
    # Убираем вывод "Объём входа" — ниже уже показывается "Количество"
    parts.extend([
        f"🔸 Количество: <code>{qty:.6f}</code>\n",
        f"🔸 Плечо: <code>{int(round(float(lev_used)))}x</code>\n",
        f"🔸 Риск: <code>{float(risk_amount or 0.0):.2f}</code>\n",
        f"🔸 Сумма входа: <code>{entry_sum_usd}</code>\n",
        f"🔸 Средняя цена: <code>{avg_str}</code>\n",
        (
            f"🔸 TP1: <code>{tp1_str}</code> "
            f"(<code>{tp1_clean:+.2f}%</code> / "
            f"<code>{tp1_lev:+.2f}%</code> с плечом)\n"
        ),
        (
            f"🔸 TP2: <code>{tp2_str}</code> "
            f"(<code>{tp2_clean:+.2f}%</code> / "
            f"<code>{tp2_lev:+.2f}%</code> с плечом)\n\n"
        ),
        "⚠️ <b>Внимание:</b> на <b>TP1</b> фиксируем <b>50%</b> позиции, "
        "остаток держим до <b>TP2</b>\n\n",
        f"⏰ Время: <code>{get_utc_now().strftime('%H:%M:%S')}</code>",
    ])
    return "".join(parts)


def build_dca_proposal_block(
    symbol: str,
    trade_mode: str,
    leverage_info: str,
    last_close: float,
    new_qty: float,
    avg_price_new: float,
    tp1: float,
    tp2: float,
    percent_tp1_clean: float,
    percent_tp1_lev: float,
    percent_tp2_clean: float,
    percent_tp2_lev: float,
    dca_count: int,
    total_qty: float,
    entry_prices_str: str,
    qtys_str: str,
    risk_pct: float,
    current_risk: float,
    price_formatter,
) -> str:
    """Возвращает блок с деталями DCA для добавления в сообщение."""
    return (
        "\n📊 ДАННЫЕ УСРЕДНЕНИЯ:\n"
        f"• Режим: {trade_mode.upper()}{leverage_info}\n"
        f"• Цена: {price_formatter(last_close)}\n"
        f"• Объём усреднения: {new_qty:.4f}\n"
        f"• Новая средняя цена: {price_formatter(avg_price_new)}\n"
        f"• TP1: {price_formatter(tp1)} "
        f"({percent_tp1_clean:+.2f}% / {percent_tp1_lev:+.2f}% с плечом)\n"
        f"• TP2: {price_formatter(tp2)} "
        f"({percent_tp2_clean:+.2f}% / {percent_tp2_lev:+.2f}% с плечом)\n"
        f"• Усреднений: {dca_count+1} (лимит: ?)\n"
        f"• Общий объём: {total_qty:.4f}\n"
        f"• Все входы: {entry_prices_str}\n"
        f"• Все объёмы: {qtys_str}\n"
        f"• Риск на сделку: {risk_pct:.2f}%\n"
        f"• Текущий риск: {current_risk:.2f} USDT\n\n"
        f"⚠️ ВАЖНО: Обновите TP на всех открытых позициях по {symbol}!\n\n"
    )


def build_sl_be_message(
    symbol: str,
    side: str,
    entry_price: float,
    sl_price: float,
    realized_pnl: float,
    remaining_qty: float,
    price_formatter,
) -> str:
    """Сообщение о закрытии позиции по SL безубытка."""
    entry_str = price_formatter(entry_price)
    sl_str = price_formatter(sl_price)
    return (
        "🛡️ <b>SL БЕЗУБЫТОК — ПОЗИЦИЯ ЗАКРЫТА!</b>\n\n"
        f"Символ: <code>{symbol}</code>\n"
        f"Сторона: <code>{side.upper()}</code>\n"
        f"Цена входа: <code>{entry_str}</code>\n"
        f"SL (BE): <code>{sl_str}</code>\n"
        f"Итоговый P&L: <code>{float(realized_pnl):.2f} USDT</code>\n"
        f"Остаток закрыт: <code>{float(remaining_qty):.4f}</code>\n"
    )


def build_partial_close_message(
    symbol: str,
    side: str,
    total_closed_qty: float,
    closed_pct_view: float,
    pnl_after_fee: float,
    pnl_pct_total: float,
    total_fee: float,
    remain_total_qty: float,
    new_balance: float,
) -> str:
    """Частичное закрытие позиции."""
    return (
        "🔒 <b>Частичное закрытие</b>\n\n"
        f"🔸 Символ: <code>{symbol}</code>\n"
        f"🔸 Сторона: <code>{side.upper()}</code>\n"
        f"🔸 Закрыто: <code>{float(total_closed_qty):.6f}</code> "
        f"(<code>{float(closed_pct_view):.0f}%</code>)\n"
        f"🔸 PnL: <code>{float(pnl_after_fee):.2f}</code> "
        f"(<code>{float(pnl_pct_total):+.2f}%</code>)\n"
        f"🔸 Комиссия: <code>{float(total_fee):.2f}</code>\n"
        f"🔸 Остаток: <code>{float(remain_total_qty):.6f}</code>\n"
        f"🔸 Новый баланс: <code>{float(new_balance):.2f}</code>\n\n"
        f"⏰ Время: <code>{get_utc_now().strftime('%H:%M:%S')}</code>"
    )


def build_full_close_message(
    symbol: str,
    side: str,
    total_closed_qty: float,
    pnl_after_fee: float,
    pnl_pct_total: float,
    total_fee: float,
) -> str:
    """Полное закрытие позиции."""
    return (
        "🔒 <b>Позиция закрыта</b>\n\n"
        f"🔸 Символ: <code>{symbol}</code>\n"
        f"🔸 Сторона: <code>{side.upper()}</code>\n"
        f"🔸 Закрыто: <code>{float(total_closed_qty):.6f}</code> (<code>100%</code>)\n"
        f"🔸 PnL: <code>{float(pnl_after_fee):.2f}</code> "
        f"(<code>{float(pnl_pct_total):+.2f}%</code>)\n"
        f"🔸 Комиссия: <code>{float(total_fee):.2f}</code>\n"
    )


def generate_signal_recommendation(
    symbol: str,
    side: str,
    score: int,
    technical_data: Optional[Dict[str, Any]],
    btc_trend: bool
) -> str:
    """Генерирует рекомендацию для торгового сигнала"""
    try:
        # Анализируем технические данные
        rsi = technical_data.get('rsi', 50) if technical_data else 50
        macd_status = technical_data.get('macd_status', 'Нейтральный') if technical_data else 'Нейтральный'
        volume_status = technical_data.get('volume_status', 'Средний') if technical_data else 'Средний'

        # Определяем плюсы
        pluses = []
        if rsi < 30 and side == "long":
            pluses.append("🟢 RSI перепродан - хорошая точка входа")
        elif rsi > 70 and side == "short":
            pluses.append("🔴 RSI перекуплен - подходит для SHORT")

        if macd_status == "Бычий" and side == "long":
            pluses.append("🟢 MACD подтверждает бычий тренд")
        elif macd_status == "Медвежий" and side == "short":
            pluses.append("🔴 MACD подтверждает медвежий тренд")

        if "Выше" in volume_status:
            pluses.append("🟢 Высокий объем - сильное движение")

        if btc_trend and side == "long":
            pluses.append("🟢 BTC тренд поддерживает LONG")
        elif not btc_trend and side == "short":
            pluses.append("🔴 BTC тренд поддерживает SHORT")

        # Определяем минусы и риски
        minuses = []
        risks = []

        if rsi > 70 and side == "long":
            minuses.append("🔴 RSI перекуплен - риск коррекции")
        elif rsi < 30 and side == "short":
            minuses.append("🟢 RSI перепродан - риск отскока")

        if macd_status == "Медвежий" and side == "long":
            minuses.append("🔴 MACD против LONG позиции")
        elif macd_status == "Бычий" and side == "short":
            minuses.append("🟢 MACD против SHORT позиции")

        if "Низкий" in volume_status:
            risks.append("⚠️ Низкий объем - слабое движение")

        if not btc_trend and side == "long":
            risks.append("⚠️ BTC тренд против LONG")
        elif btc_trend and side == "short":
            risks.append("⚠️ BTC тренд против SHORT")

        # Общие риски
        risks.append("⚠️ Криптовалюты волатильны - используйте стоп-лосс")
        risks.append("⚠️ Не инвестируйте больше, чем можете потерять")

        # Формируем рекомендацию
        recommendation_parts = []

        if score >= 80:
            recommendation_parts.append("✅ СИЛЬНАЯ РЕКОМЕНДАЦИЯ")
        elif score >= 60:
            recommendation_parts.append("👍 УМЕРЕННАЯ РЕКОМЕНДАЦИЯ")
        else:
            recommendation_parts.append("⚠️ ОСТОРОЖНО")

        if pluses:
            recommendation_parts.append("➕ ПЛЮСЫ:")
            recommendation_parts.extend([f"  {plus}" for plus in pluses[:3]])

        if minuses:
            recommendation_parts.append("➖ МИНУСЫ:")
            recommendation_parts.extend([f"  {minus}" for minus in minuses[:2]])

        if risks:
            recommendation_parts.append("⚠️ РИСКИ:")
            recommendation_parts.extend([f"  {risk}" for risk in risks[:2]])

        return "\n".join(recommendation_parts)

    except Exception as e:
        print(f"[DEBUG] Ошибка генерации рекомендации: {type(e).__name__}: {e}")
        return "⚠️ Анализ недоступен. Торгуйте осторожно!"


def build_new_signal_message(
    symbol: str,
    side: str,
    signal_price: float,
    trade_mode: str,
    filter_mode: str,
    created_at_str: str,
    news_indicator: str,
    technical_data: Optional[Dict[str, Any]],
    fgi_val: Optional[int],
    fgi_text: Optional[str],
    btc_trend_status: Optional[bool],
    eth_trend_status: Optional[bool],
    whale_line: Optional[str],
    anomalies_line: Optional[str],
    accumulation_line: Optional[str],
    news_info_block: Optional[str],
    price_formatter,
    entry_amount_line: Optional[str] = None,
    super_assessment_line: Optional[str] = None,
    eta_ttl_line: Optional[str] = None,
    sol_trend_status: Optional[bool] = None,
    recommendation: Optional[str] = None,
    risk_pct: Optional[float] = None,
    is_dca: bool = False,
    # Новые параметры для полного формата
    quantity: Optional[float] = None,
    leverage: Optional[float] = None,
    entry_amount_usdt: Optional[float] = None,
    tp1_price: Optional[float] = None,
    tp2_price: Optional[float] = None,
    sl_price: Optional[float] = None,
    tp1_pct: Optional[float] = None,
    tp2_pct: Optional[float] = None,
    sl_pct: Optional[float] = None,
    confidence: Optional[float] = None,
    guidance_entries: Optional[List[Dict[str, Any]]] = None,
    judge_verdict: Optional[Dict[str, Any]] = None,
    ai_factors: Optional[List[str]] = None,
) -> str:
    """Строит HTML‑сообщение о новом торговом сигнале для Telegram.

    Значения цен форматируются через переданный ``price_formatter`` с учётом
    точности символа. В сообщении опционально включаются блоки новостей,
    подтверждения, аномалий, накопления, а также тренды BTC/ETH и данные
    технического анализа.

    Возвращает готовую HTML‑строку.
    """
    # Определяем эмодзи для стороны сигнала
    if str(side).upper() in ["BUY", "LONG"]:
        side_emoji = "🟢"  # Зеленый для лонга
    elif str(side).upper() in ["SELL", "SHORT"]:
        side_emoji = "🔴"  # Красный для шорта
    else:
        side_emoji = "🔴"  # По умолчанию красный

    # Добавляем заголовок в зависимости от типа сигнала
    signal_type_header = "НОВЫЙ DCA СИГНАЛ" if is_dca else "НОВЫЙ ТОРГОВЫЙ СИГНАЛ"
    title = f"{side_emoji} {signal_type_header}\n\n"

    # Преобразуем BUY/SELL в LONG/SHORT
    if side.upper() in ["BUY", "LONG"]:
        side_display = "LONG"
    elif side.upper() in ["SELL", "SHORT"]:
        side_display = "SHORT"
    else:
        side_display = side.upper()

    # Новый формат заголовка с поддержкой DCA
    # Используем HTML формат с <code> - теги не видны, но значения копируются
    header = (
        f"{title}"
        f"📊 Символ: <code>{symbol}</code>\n"
        f"📈 Сторона: <code>{side_display}</code>\n"
        f"💰 Цена входа: <code>{price_formatter(signal_price)}</code>\n"
    )

    # Добавляем количество, если передано
    if quantity is not None:
        header += f"🎯 Количество: <code>{quantity:.6f}</code>\n"

    # Добавляем плечо, если передано
    if leverage is not None and leverage >= 1:
        header += f"🔢 Плечо: <code>{int(round(float(leverage)))}x</code>\n"

    # Добавляем риск, если передан
    if risk_pct is not None:
        header += f"💡 Риск: <code>{risk_pct:.2f}%</code>\n"

    # Добавляем сумму входа, если передана
    if entry_amount_usdt is not None:
        header += f"💵 Сумма входа: <code>{entry_amount_usdt:.0f} USDT</code>\n"

    header += f"📅 Время: <code>{created_at_str}</code>\n"

    # Добавляем TP и SL, если переданы (с процентами для TP: чистый и с плечом)
    tp_sl_block = "\n\n"
    if tp1_price is not None and tp1_pct is not None:
        tp1_pct_lev = tp1_pct * (leverage if leverage else 1)
        tp_sl_block += f"🎯 TP1: <code>{price_formatter(tp1_price)}</code> (+{tp1_pct:.2f}% / +{tp1_pct_lev:.2f}%)\n"

    if tp2_price is not None and tp2_pct is not None:
        tp2_pct_lev = tp2_pct * (leverage if leverage else 1)
        tp_sl_block += f"🎯 TP2: <code>{price_formatter(tp2_price)}</code> (+{tp2_pct:.2f}% / +{tp2_pct_lev:.2f}%)\n"

    if sl_price is not None and sl_pct is not None:
        # Рассчитываем сумму убытка в USDT
        sl_amount_usdt = None
        if entry_amount_usdt is not None:
            sl_amount_usdt = entry_amount_usdt * (abs(sl_pct) / 100)

        if sl_amount_usdt is not None:
            tp_sl_block += (
                f"🛡️ SL: <code>{price_formatter(sl_price)}</code> "
                f"(-{abs(sl_pct):.2f}% / -<code>{sl_amount_usdt:.2f}</code>$)\n"
            )
        else:
            tp_sl_block += f"🛡️ SL: <code>{price_formatter(sl_price)}</code> (-{abs(sl_pct):.2f}%)\n"

    if tp_sl_block.strip():
        header += tp_sl_block

    # Собираем сообщение
    parts = [header]

    # Технический анализ рассчитывается, но не показывается в сообщении
    # (используется для внутренней логики, но скрыт от пользователя)
    if technical_data:
        tech_parts = []
        rsi_val = technical_data.get("rsi", 0)
        if rsi_val:
            rsi_emoji = "🔴" if rsi_val > 70 else ("🟢" if rsi_val < 30 else "🟡")
            tech_parts.append(f"RSI:{rsi_val:.0f}{rsi_emoji}")

        macd_status = technical_data.get("macd_status", "")
        if macd_status:
            macd_emoji = "🟢" if macd_status == "Бычий" else ("🔴" if macd_status == "Медвежий" else "")
            if macd_emoji:
                tech_parts.append(f"MACD:{macd_emoji}")

        if btc_trend_status is not None:
            btc_emoji = "🟢" if btc_trend_status else "🔴"
            tech_parts.append(f"BTC:{btc_emoji}")

        # Анализ не добавляется в сообщение (скрыт от пользователя)
        # if tech_parts:
        #     parts.append(f"\n\n📊 Анализ: {' | '.join(tech_parts)}")

    # Уверенность ИИ
    if confidence is not None:
        parts.append(f"\n⏰ Уверенность: <code>{confidence:.0f}%</code>")
    elif recommendation and "Уверенность:" in recommendation:
        confidence_match = re.search(r'Уверенность:\s*(\d+)%', recommendation)
        if confidence_match:
            confidence_val = confidence_match.group(1)
            parts.append(f"\n⏰ Уверенность: <code>{confidence_val}%</code>")

    # 🔧 УБРАНО: Judge verdict больше не показывается в сообщениях
    # (по запросу пользователя - убрать пункт "🧾 Judge: ⚠️ WARN • confidence=65.0% ниже warn-пор...")
    # if judge_verdict:
    #     status = judge_verdict.get("status", "pass").upper()
    #     if status in ("WARN", "FAIL"):
    #         reasons = judge_verdict.get("reasons", [])
    #         judge_emoji = "⚠️" if status == "WARN" else "❌"
    #         if reasons:
    #             reasons_short = [r[:30] + "..." if len(r) > 30 else r for r in reasons[:2]]
    #             reasons_str = " | ".join(reasons_short)
    #             parts.append(f"\n🧾 Judge: {judge_emoji} <code>{status}</code> • {reasons_str}")
    #         else:
    #             parts.append(f"\n🧾 Judge: {judge_emoji} <code>{status}</code>")

    # Уроки системы (очень компактно, только если есть место)
    if guidance_entries:
        # Показываем только если сообщение короткое (проверка длины)
        current_length = len("".join(parts))
        if current_length < 3000:  # Оставляем запас
            lessons_compact = []
            for entry in guidance_entries[:2]:  # Только топ-2
                issue = entry.get("issue", "")[:20]  # Обрезаем длинные названия
                count = entry.get("count", 0)
                if issue:
                    lessons_compact.append(f"{issue}(#{count})")
            if lessons_compact:
                parts.append(f"\n🧠 Уроки: {' | '.join(lessons_compact)}")

    # AI Factors (SHAP)
    if ai_factors:
        # Улучшенное форматирование факторов для читаемости
        formatted_factors = []
        for factor in ai_factors:
            if '(' in factor:
                name, pct = factor.split('(', 1)
                formatted_factors.append(f"• {name.strip()} — <b>{pct.rstrip(')')}</b>")
            else:
                formatted_factors.append(f"• {factor}")

        factors_str = "\n".join(formatted_factors)
        parts.append(f"\n\n🔬 <b>ФАКТОРЫ ИИ:</b>\n{factors_str}")

    message = "".join(parts)

    # Проверка длины сообщения (Telegram лимит: 4096 символов)
    max_telegram_length = 4000  # Оставляем запас
    if len(message) > max_telegram_length:
        # Обрезаем до безопасной длины
        message = message[:max_telegram_length]
        # Обрезаем по последней строке, чтобы не обрывать посередине
        last_newline = message.rfind('\n')
        if last_newline > 0:
            message = message[:last_newline]
        message += "\n\n⚠️ Сообщение обрезано из-за ограничения длины"

    return message


def build_analysis_message(
    symbol: str,
    price: float,
    timeframe_text: str,
    technical_data: Optional[Dict[str, Any]],
    fgi_val: Optional[int],
    fgi_text: Optional[str],
    btc_trend_status: Optional[bool],
    eth_trend_status: Optional[bool],
    whale_line: Optional[str],
    anomalies_line: Optional[str],
    accumulation_line: Optional[str],
    news_info_block: Optional[str],
    price_formatter,
) -> str:
    """Строит HTML‑сообщение аналитического обзора по символу.

    Показывает теханализ, тренды BTC/ETH, CONF, аномалии и накопление.
    """
    header = (
        "📊 АНАЛИТИЧЕСКИЙ ОБЗОР\n\n"
        f"📊 Символ: 🪙 {symbol}\n"
        f"💰 Текущая цена: {price_formatter(price)}\n"
        f"⏱️ Таймфрейм: {timeframe_text}\n"
    )

    tech_block = ""
    if technical_data:
        rsi_val = technical_data.get("rsi", 0)
        rsi_emoji = "🔴" if rsi_val > 70 else ("🟢" if rsi_val < 30 else "🟡")
        macd_status = technical_data.get("macd_status", "Нейтральный")
        macd_emoji = "🟢" if macd_status == "Бычий" else "🔴"
        volume_status = technical_data.get("volume_status", "Средний")
        volume_emoji = "🟢" if "Выше" in volume_status else "🟡"
        ema_status = technical_data.get("ema_status", "Нейтральный")
        ema_emoji = "🟢" if ema_status == "Бычий" else "🔴"
        bb_position = technical_data.get("bb_position", "Средняя зона")

        tech_block = (
            f"\n📊 ТЕХНИЧЕСКИЙ АНАЛИЗ:\n"
            f"• RSI: {float(rsi_val):.1f} ({rsi_emoji} "
            f"{technical_data.get('rsi_status', 'Нейтральный')})\n"
            f"• MACD: {macd_emoji} {macd_status}\n"
            f"• Объем: {volume_emoji} {volume_status}\n"
            f"• EMA: {ema_emoji} {ema_status}\n"
            f"• BB: {bb_position}\n"
        )
        if fgi_text is not None:
            fgi_val_str = str(fgi_val) if fgi_val is not None and fgi_val >= 0 else "—"
            tech_block += f"• FGI: {fgi_text} ({fgi_val_str})\n"

    trends_block = ""
    if btc_trend_status is not None:
        btc_emoji = "🟢" if btc_trend_status else "🔴"
        btc_status = "БЫЧИЙ" if btc_trend_status else "МЕДВЕЖИЙ"
        trends_block += f"• BTC тренд: {btc_emoji} {btc_status}\n"
    if eth_trend_status is not None:
        eth_emoji = "🟢" if eth_trend_status else "🔴"
        eth_status = "БЫЧИЙ" if eth_trend_status else "МЕДВЕЖИЙ"
        trends_block += f"• ETH тренд: {eth_emoji} {eth_status}\n"
    # Добавляем SOL тренд, если он передан через technical_data
    sol_trend_status = None
    if isinstance(technical_data, dict):
        sol_trend_status = technical_data.get("sol_trend_status")
    if sol_trend_status is not None:
        sol_emoji = "🟢" if sol_trend_status else "🔴"
        sol_status = "БЫЧИЙ" if sol_trend_status else "МЕДВЕЖИЙ"
        trends_block += f"• SOL тренд: {sol_emoji} {sol_status}\n"

    parts = [header]
    if news_info_block:
        parts.append(news_info_block + "\n")
    if tech_block:
        parts.append(tech_block)
    if trends_block:
        parts.append(trends_block)
    if accumulation_line:
        parts.append(accumulation_line)
    # Сначала CONF, затем Аномалии
    if whale_line:
        normalized = whale_line.replace("Киты:", "CONF:")
        parts.append(normalized)
    if anomalies_line:
        parts.append(anomalies_line)
    # Блок мнения ИИ отключён

    return "".join(parts)

def build_dca_queue_message(
    symbol: str,
    side: str,
    current_price: float,
    missed_count: int,
    avg_price_new: float,
    tp1: float,
    tp2: float,
    tp1_pct: float,
    tp2_pct: float,
    risk_pct: float,
    leverage: float,
    trade_mode: str,
    price_formatter,
    volume_blocks_info: Optional[str] = None,
) -> str:
    """Сообщение о накопленном DCA сигнале (очередь), HTML-формат.

    Проценты TP1/TP2 показываются с учётом плеча (если режим фьючерсы).
    """
    side_text = "LONG" if str(side).lower() == "long" else "SHORT"
    lev_mult = float(leverage) if str(trade_mode).lower() == "futures" else 1.0
    sign = "+" if str(side).lower() == "long" else "-"

    parts = [
        "⏰ <b>НАКОПЛЕННЫЙ DCA СИГНАЛ</b>\n\n",
        f"📊 Символ: <code>{symbol}</code>\n",
        f"📈 Сторона: <code>{side_text}</code>\n",
        f"💰 Текущая цена: <code>{price_formatter(current_price)}</code>\n",
        f"📊 Количество пропущенных сигналов: <code>{int(missed_count)}</code>\n\n",
        "🎯 <b>ПЕРЕСЧИТАННЫЕ ПАРАМЕТРЫ:</b>\n",
        f"• Новая средняя цена: <code>{price_formatter(avg_price_new)}</code>\n",
        (
            f"• 🎯 TP1: <code>{price_formatter(tp1)}</code> "
            f"(<code>{sign}{(float(tp1_pct) * lev_mult):.1f}%</code>)\n"
        ),
        (
            f"• 🚀 TP2: <code>{price_formatter(tp2)}</code> "
            f"(<code>{sign}{(float(tp2_pct) * lev_mult):.1f}%</code>)\n"
        ),
        f"• ⚠️ Риск: <code>{float(risk_pct):.2f}%</code>\n",
        f"• 📊 Плечо: <code>x{int(round(float(leverage)))}</code>\n",
    ]
    if volume_blocks_info:
        parts.append(f"• Блоки объёма: {volume_blocks_info}\n")
    return "".join(parts)
