import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, funding_threshold=0.05, pnl_threshold=-3.0):
        self.funding_threshold = Decimal(str(funding_threshold))
        self.pnl_threshold = Decimal(str(pnl_threshold))

    async def analyze_stuck_position(self, pos_data, market_regime, model_prediction):
        """
        Принимает решение по 'зависшей' позиции.
        """
        symbol = pos_data.get('symbol')
        pnl = Decimal(str(pos_data.get('pnl_percent', 0)))
        funding_cost = Decimal(str(pos_data.get('total_funding', 0)))
        
        logger.info(f"🔬 [DECISION] Анализ {symbol}: PnL={pnl}%, Funding={funding_cost}")

        # Сценарий 1: Критический убыток + Медвежий прогноз
        if pnl < self.pnl_threshold and model_prediction < 0.4:
            return {
                'action': 'EMERGENCY_CLOSE',
                'reason': 'PnL ниже порога и прогноз ИИ негативный',
                'confidence': 0.95
            }

        # Сценарий 2: Позиция в плюсе, но фандинг 'съедает' прибыль
        if pnl > 0 and funding_cost > (pnl * Decimal('0.5')):
            return {
                'action': 'TAKE_PROFIT_NOW',
                'reason': 'Фандинг съедает более 50% прибыли',
                'confidence': 0.85
            }

        # Сценарий 3: Тренд развернулся (Market Regime changed)
        if market_regime == 'TREND_REVERSAL':
            return {
                'action': 'ADAPT_TARGETS',
                'reason': 'Обнаружен разворот тренда, двигаем TP ближе',
                'target_adj': -0.01 # Снижаем TP на 1%
            }

        return {'action': 'HOLD', 'reason': 'Параметры в норме', 'confidence': 1.0}

def get_decision_engine():
    return DecisionEngine()
