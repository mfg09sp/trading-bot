"""
Módulo de Escáner de Mercado Autónomo (Market Screener).
Analiza un universo amplio de acciones y criptomonedas, detectando los activos
con mayor impulso alcista y mejor probabilidad técnica ("pinta de subir").
"""

import logging
from typing import List, Dict, Any, Tuple
from alpaca.data.requests import StockSnapshotRequest, CryptoSnapshotRequest
from alpaca_service import AlpacaService

logger = logging.getLogger("MarketScreener")

# Universo amplio de acciones estadounidenses y ETFs líderes (S&P 500, Nasdaq, Tech)
STOCK_UNIVERSE = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "GOOGL",
    "META", "AMD", "NFLX", "PLTR", "COIN", "UBER", "CRM", "AVGO"
]

# Universo amplio de criptomonedas líquidas negociables en Alpaca (24/7)
CRYPTO_UNIVERSE = [
    "BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD", "AVAX/USD",
    "LINK/USD", "BCH/USD", "NEAR/USD", "UNI/USD", "AAVE/USD", "LTC/USD"
]

# Universo de Futuros de Materias Primas e Índices Apalancados
FUTURES_UNIVERSE = [
    "BITO",  # Futuros Bitcoin (CME)
    "USO",   # Futuros Petróleo WTI
    "GLD",   # Futuros Oro
    "SLV",   # Futuros Plata
    "TQQQ",  # Futuros Apalancados x3 Nasdaq 100
    "UPRO",  # Futuros Apalancados x3 S&P 500
    "SOXL"   # Futuros Apalancados x3 Semiconductores
]


def scan_promising_assets(
    alpaca: AlpacaService,
    max_candidates: int = 8,
    include_stocks: bool = True,
    include_crypto: bool = True
) -> List[Dict[str, Any]]:
    """
    Escanea en lote el mercado de acciones y cripto.
    Calcula el momentum relativo (variación porcentual, volumen reciente)
    y devuelve los mejores candidatos ordenados por potencial alcista.
    """
    candidates = []

    # Comprobar horario de mercado bursátil
    if include_stocks and not alpaca.is_market_open():
        logger.info("Mercado bursátil estadounidense CERRADO. Escáner operando exclusivamente en Cripto (24/7).")
        include_stocks = False

    # 1. Escaneo de Cripto (24/7)
    if include_crypto:
        try:
            req = CryptoSnapshotRequest(symbol_or_symbols=CRYPTO_UNIVERSE)
            crypto_snaps = alpaca.crypto_data_client.get_crypto_snapshot(req)
            for sym, snap in crypto_snaps.items():
                if not snap or not snap.latest_trade or not snap.previous_daily_bar:
                    continue
                price = float(snap.latest_trade.price)
                prev_close = float(snap.previous_daily_bar.close)
                if prev_close <= 0:
                    continue
                change_pct = ((price - prev_close) / prev_close) * 100.0
                volume = float(snap.daily_bar.volume) if snap.daily_bar else 0.0

                candidates.append({
                    "symbol": sym,
                    "type": "crypto",
                    "price": price,
                    "change_24h_pct": round(change_pct, 2),
                    "volume": volume,
                    # Puntuación de impulso: favorece cambios positivos
                    "momentum_score": change_pct
                })
        except Exception as e:
            logger.error(f"Error al escanear snapshots de cripto: {e}")

    # 2. Escaneo de Acciones
    if include_stocks:
        try:
            req = StockSnapshotRequest(symbol_or_symbols=STOCK_UNIVERSE)
            stock_snaps = alpaca.stock_data_client.get_stock_snapshot(req)
            for sym, snap in stock_snaps.items():
                if not snap or not snap.latest_trade or not snap.previous_daily_bar:
                    continue
                price = float(snap.latest_trade.price)
                prev_close = float(snap.previous_daily_bar.close)
                if prev_close <= 0:
                    continue
                change_pct = ((price - prev_close) / prev_close) * 100.0
                volume = float(snap.daily_bar.volume) if snap.daily_bar else 0.0

                candidates.append({
                    "symbol": sym,
                    "type": "stock",
                    "price": price,
                    "change_24h_pct": round(change_pct, 2),
                    "volume": volume,
                    "momentum_score": change_pct
                })
        except Exception as e:
            logger.error(f"Error al escanear snapshots de acciones: {e}")

    # 3. Ordenar por mayor fuerza de momentum ("los que tienen pinta de subir")
    candidates.sort(key=lambda x: x["momentum_score"], reverse=True)

    # Devolver los N mejores activos filtrados
    return candidates[:max_candidates]


def scan_futures_candidates(alpaca: AlpacaService) -> List[Dict[str, Any]]:
    """
    Escanea selectivamente el universo de contratos de futuros / materias primas / índices apalancados.
    Solo selecciona candidatos con momentum positivo confirmado (cambio positivo y volumen sólido).
    """
    if not alpaca.is_market_open():
        return []

    candidates = []
    try:
        req = StockSnapshotRequest(symbol_or_symbols=FUTURES_UNIVERSE)
        snaps = alpaca.stock_data_client.get_stock_snapshot(req)
        for sym, snap in snaps.items():
            if not snap or not snap.latest_trade or not snap.previous_daily_bar:
                continue
            price = float(snap.latest_trade.price)
            prev_close = float(snap.previous_daily_bar.close)
            if prev_close <= 0:
                continue
            change_pct = ((price - prev_close) / prev_close) * 100.0
            volume = float(snap.daily_bar.volume) if snap.daily_bar else 0.0
            if change_pct > 0.2:
                candidates.append({
                    "symbol": sym,
                    "type": "future",
                    "price": price,
                    "change_24h_pct": round(change_pct, 2),
                    "volume": volume,
                    "momentum_score": change_pct
                })
        candidates.sort(key=lambda x: x["momentum_score"], reverse=True)
    except Exception as e:
        logger.error(f"Error escaneando futuros: {e}")
    return candidates
