# -*- coding: utf-8 -*-
"""
Exchange utility functions
"""
# Utility functions for exchange operations


def get_symbol_precision(symbol):
    """
    Returns correct precision for symbol on Binance
    """
    if symbol.endswith('USDT'):
        precision_map = {
            # Main coins (1-2 digits)
            'BTCUSDT': 1,    # 45000.5 (исправлено с 2 на 1)
            'ETHUSDT': 2,    # 3245.67
            'BNBUSDT': 2,    # 245.89
            'LTCUSDT': 2,    # 67.89
            'BCHUSDT': 1,    # 245.8 (исправлено с 2 на 1)
            'DASHUSDT': 2,   # 67.89
            'ETHFIUSDT': 3,  # 3.456 (исправлено с 2 на 3)
            'ZECUSDT': 2,    # 23.45
            'ZENUSDT': 3,    # 12.345 (исправлено с 2 на 3)

            # Coins with 3 digits
            'SOLUSDT': 2,    # 98.45 (исправлено с 3 на 2)
            'UNIUSDT': 3,    # 8.456
            'ATOMUSDT': 3,   # 9.234
            'ETCUSDT': 2,    # 23.45 (исправлено с 3 на 2)
            'AVAXUSDT': 2,   # 32.45 (исправлено с 3 на 2)
            'SUIUSDT': 4,    # 1.2345 (исправлено с 3 на 4)

            # Coins with 4 digits
            'XRPUSDT': 4,    # 0.5432
            'ADAUSDT': 4,    # 0.4321
            'LINKUSDT': 2,   # 15.43 (исправлено с 4 на 2)
            'TONUSDT': 3,    # 2.345 (исправлено с 4 на 3)
            'MATICUSDT': 4,  # 0.8765
            'ASTERUSDT': 4,  # 2.1356 (добавлено для правильного форматирования)
            'DOTUSDT': 3,    # 7.234 (исправлено с 4 на 3)
            'FILUSDT': 3,    # 5.432 (исправлено с 4 на 3)
            'NEARUSDT': 3,   # 3.456 (исправлено с 4 на 3)
            'APTUSDT': 3,    # 8.765 (исправлено с 4 на 3)
            'OPUSDT': 4,     # 2.3456
            'HBARUSDT': 5,   # 0.12345

            # Coins with 5 digits
            'TOWNUSDT': 5,   # 0.02716 (отсутствует на бирже)
            'ENAUSDT': 4,    # 0.6498 (исправлено с 5 на 4)
            'JUPUSDT': 4,    # 0.8765 (исправлено с 5 на 4)
            'WIFUSDT': 3,    # 2.345 (исправлено с 5 на 3)

            # Memecoins with 6 digits
            'DOGEUSDT': 5,   # 0.07845 (исправлено с 6 на 5)
            'PEPEUSDT': 8,   # 0.00012345 (исправлено с 6 на 8)
            'SHIBUSDT': 8,   # 0.00002345 (исправлено с 6 на 8)
            'FLOKIUSDT': 8,  # 0.00004567 (исправлено с 6 на 8)
            'PENGUUSDT': 6,  # 0.000078
            'BONKUSDT': 8,   # 0.00012345 (исправлено с 6 на 8)
            'MEMEUSDT': 6,   # 0.000045
            'BOMEUSDT': 6,   # 0.000078

            # Additional: new/frequently used pairs
            'TRUMPUSDT': 2,  # 1.32 (исправлено с 4 на 2)
            'TRAMUSDT': 4,   # отсутствует на бирже
            'WLDUSDT': 3,    # 1.324 (исправлено с 4 на 3)

            # Additional symbols from system logs
            'AAVEUSDT': 2,    # 15.43 (исправлено с 4 на 2)
            'ALICEUSDT': 4,   # 0.1234
            'ALPINEUSDT': 3,  # 0.123 (исправлено с 4 на 3)
            'ARBUSDT': 4,     # 0.1234
            'ATMUSDT': 3,     # 0.123 (исправлено с 4 на 3)
            'AVNTUSDT': 4,    # 0.1234
            'BAKEUSDT': 4,    # 0.1234
            'BARDUSDT': 4,    # 0.1234
            'BIOUSDT': 4,     # 0.1234
            'CITYUSDT': 3,    # 0.123 (исправлено с 4 на 3)
            'CRVUSDT': 4,     # 0.1234
            'EDENUSDT': 4,    # 0.1234
            'EIGENUSDT': 3,   # 0.123 (исправлено с 4 на 3)
            'EURUSDT': 4,     # 0.1234
            'FDUSDUSDT': 4,   # 0.1234
            'FETUSDT': 3,     # 0.123 (исправлено с 4 на 3)
            'FFUSDT': 5,      # 0.12345 (исправлено с 4 на 5)
            'FORMUSDT': 4,    # 1.2218
            'HEIUSDT': 4,     # 0.1234
            'HEMIUSDT': 4,    # 0.1234
            'HIFIUSDT': 4,    # 0.1234
            'JUVUSDT': 3,     # 0.123 (исправлено с 4 на 3)
            'KAITOUSDT': 4,   # 0.1234
            'LAZIOUSDT': 3,   # 0.123 (исправлено с 4 на 3)
            'LDOUSDT': 4,    # 0.1234
            'LINEAUSDT': 5,   # 0.12345 (исправлено с 4 на 5)
            'MIRAUSDT': 4,    # 0.1234
            'MUBARAKUSDT': 5, # 0.12345 (исправлено с 4 на 5)
            'NOMUSDT': 5,     # 0.12345 (исправлено с 4 на 5)
            'ONDOUSDT': 4,    # 0.1234
            'PAXGUSDT': 2,    # 0.12 (исправлено с 4 на 2)
            'PIVXUSDT': 4,    # 0.1234
            'PUMPUSDT': 6,    # 0.123456 (исправлено с 4 на 6)
            'QUICKUSDT': 5,   # 0.12345 (исправлено с 4 на 5)
            'SEIUSDT': 4,     # 0.1234
            'SLFUSDT': 4,     # 0.1234
            'SNXUSDT': 3,     # 0.123 (исправлено с 4 на 3)
            'SOMIUSDT': 4,    # 0.1234
            'STRKUSDT': 4,    # 0.1234
            'TAOUSDT': 1,     # 0.1 (исправлено с 4 на 1)
            'TRXUSDT': 4,     # 0.1234
            'TSTUSDT': 5,     # 0.12345 (исправлено с 4 на 5)
            'USDCUSDT': 4,    # 0.1234
            'USDEUSDT': 4,    # 0.1234
            'WLFIUSDT': 4,    # 0.1234
            'XLMUSDT': 4,     # 0.1234
            'XPLUSDT': 4,     # 0.1234
            'TUTUSDT': 5,     # 0.11000 - добавлен для правильного отображения TP1/TP2

            # Дополнительные популярные монеты
            'PLUMEUSDT': 5,   # 0.09000
            'NOTUSDT': 5,     # 0.01234
            'IOUSDT': 4,      # 0.1234
            'WUSDT': 4,       # 0.1234
            'CATUSDT': 5,     # 0.01234
            'POPCATUSDT': 6,  # 0.000078
            'MINAUSDT': 4,    # 0.1234
            'KASUSDT': 5,     # 0.01234
            'RNDRUSDT': 3,    # 1.234
            'MANTAUSDT': 4,   # 0.1234
            'PIXELUSDT': 4,   # 0.1234
            'PORTALUSDT': 4,  # 0.1234
            'PDAUSDT': 4,     # 0.1234
            'AXLUSDT': 4,     # 0.1234
            'METISUSDT': 2,   # 12.34
            'ALTUSDT': 4,     # 0.1234
            'JTOUSDT': 4,     # 0.1234
            'ACEUSDT': 3,     # 1.234
            'NFPUSDT': 4,     # 0.1234
            'AIUSDT': 4,      # 0.1234
            'XAIUSDT': 4,     # 0.1234
        }

        if symbol in precision_map:
            return precision_map[symbol]
        else:
            # For other USDT pairs use improved default logic
            if any(
                high_precision in symbol
                for high_precision in ['PENGU', 'SHIB', 'DOGE', 'PEPE', 'FLOKI', 'BONK', 'MEME', 'BOME']
            ):
                return 6  # High precision for memecoins
            elif any(mid_precision in symbol for mid_precision in ['XRP', 'ADA', 'DOT', 'LINK', 'TOWN', 'ENA', 'JUP', 'WIF', 'XLM', 'TRX', 'AAVE', 'ALICE', 'ALPINE', 'ARB', 'ATM', 'AVNT', 'BAKE', 'BARD', 'BIO', 'CITY', 'CRV', 'EDEN', 'EIGEN', 'EUR', 'FDUSD', 'FET', 'FF', 'HEI', 'HEMI', 'HIFI', 'JUV', 'KAITO', 'LAZIO', 'LDO', 'LINEA', 'MIRA', 'MUBARAK', 'NOM', 'ONDO', 'PAXG', 'PIVX', 'PUMP', 'QUICK', 'SEI', 'SLF', 'SNX', 'SOMI', 'STRK', 'TAO', 'TST', 'USDC', 'USDE', 'WLFI', 'XPLUS']):
                return 4  # Medium precision
            elif any(low_precision in symbol for low_precision in ['SOL', 'UNI', 'ATOM', 'ETC', 'AVAX', 'SUI']):
                return 3  # Low precision
            else:
                return 2  # Standard precision
    else:
        return 2


def get_full_price_format(symbol):
    """
    Returns format for full price display as on exchange
    """
    precision = get_symbol_precision(symbol)
    return f"{{:.{precision}f}}"


def get_price_precision_from_tick(price_tick):
    """
    Determines number of decimal places for price based on price_tick
    """
    if price_tick == 0:
        return 8  # Maximum precision by default

    # Handle scientific notation (e.g., 1e-06)
    if 'e' in str(price_tick).lower():
        tick_str = str(price_tick).lower()
        if 'e-' in tick_str:
            precision = int(tick_str.split('e-')[1])
            return precision
        elif 'e+' in tick_str:
            # For large numbers (e.g., 1e+3 = 1000)
            return 0
        else:
            return 8  # Default

    # Convert price_tick to number of decimal places
    tick_str = str(price_tick)
    if '.' in tick_str:
        return len(tick_str.split('.')[1])
    else:
        return 0


# List of pairs that don't exist on exchanges or are stablecoins
INVALID_PAIRS = {
    'BONKUSDT',  # Doesn't exist on Binance
    'STOPUSDT',  # High-risk token
    # Don't hard-block memecoins: they'll be filtered by market cap/volume
    
    # Stablecoins - exclude from signal generation
    'USDTUSDT', 'USDCUSDT', 'BUSDUSDT', 'FDUSDUSDT', 'TUSDUSDT', 
    'USDDUSDT', 'USDEUSDT', 'DAIUSDT', 'FRAXUSDT', 'LUSDUSDT',
    'USTCUSDT', 'USTUSDT', 'MIMUSDT', 'ALGUSDT', 'EURSUSDT', 'USD1USDT'
}


def is_valid_pair(symbol):
    """Checks if pair is valid for trading"""
    return symbol not in INVALID_PAIRS
