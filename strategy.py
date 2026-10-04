"""
Módulo de Estrategia Técnica Cuantitativa y Gestión de Señales.
Basado en principios clásicos de inversión (Alexander Elder, Mark Minervini, John Murphy):
- Análisis en velas de 5 minutos para eliminar ruido de 1 minuto.
- Confirmación de tendencia y momentum antes de entrar.
- Asimetría positiva: Dejar correr las ganancias y evitar cortar operaciones prematuramente.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcula el Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Calcula la Media Móvil Exponencial (EMA)."""
    return series.ewm(span=span, adjust=False).mean()


def evaluate_market_data(
    df: pd.DataFrame,
    entry_price: float = 0.0
) -> Tuple[str, Dict[str, Any]]:
    """
    Evalúa las velas históricas y calcula indicadores para emitir señales:
    - 'BUY': Momento óptimo de entrada con confirmación técnica.
    - 'SELL': Momento óptimo de salida (solo si se alcanzó beneficio sólido o cambio estructural).
    - 'HOLD': Mantener la posición y dejar trabajar al trade.
    """
    if df is None or len(df) < 25:
        return "HOLD", {"reason": "Datos insuficientes (se necesitan al menos 25 velas)"}

    close = df["close"]

    # Indicadores técnicos
    rsi_series = calculate_rsi(close, period=14)
    ema_fast = calculate_ema(close, span=9)
    ema_slow = calculate_ema(close, span=21)

    current_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])

    current_rsi = float(rsi_series.iloc[-1])
    prev_rsi = float(rsi_series.iloc[-2])

    current_ema_fast = float(ema_fast.iloc[-1])
    current_ema_slow = float(ema_slow.iloc[-1])
    prev_ema_fast = float(ema_fast.iloc[-2])
    prev_ema_slow = float(ema_slow.iloc[-2])

    indicators = {
        "price": current_close,
        "rsi": round(current_rsi, 2),
        "ema_fast": round(current_ema_fast, 2),
        "ema_slow": round(current_ema_slow, 2)
    }

    # ========================================================
    # SEÑALES DE SALIDA ('SELL') - Solo si tenemos posición abierta
    # ========================================================
    if entry_price > 0:
        profit_pct = (current_close - entry_price) / entry_price

        # Regla 1: Bloqueo de Ganancias (Trailing Profit)
        # Solo aseguramos ganancias si el trade ya tiene un beneficio sustancial (> 1.2%)
        # y vemos agotamiento evidente en RSI (> 72 y girando)
        if profit_pct >= 0.012 and current_rsi >= 72.0 and current_rsi < prev_rsi:
            indicators["reason"] = f"Asegurando ganancias (+{profit_pct*100:.2f}%) ante agotamiento de RSI"
            return "SELL", indicators

        # Regla 2: Salida por Reversión Estructural (Cruce de la Muerte en 5m)
        # Solo cerramos si EMA 9 cruza hacia abajo EMA 21 con precio debajo y pérdida real
        bearish_cross = prev_ema_fast >= prev_ema_slow and current_ema_fast < current_ema_slow and current_close < current_ema_slow
        if bearish_cross and profit_pct < -0.006:
            indicators["reason"] = "Corte defensivo por cruce bajista EMA(9/21)"
            return "SELL", indicators

        # En cualquier otro caso, DEJAR CORRER la posición hacia el Take Profit
        return "HOLD", indicators

    # ========================================================
    # SEÑALES DE ENTRADA ('BUY') - Filtrado de Calidad
    # ========================================================
    # 1. Rebote en sobreventa confirmado (RSI saliendo de zona de descuento < 38 hacia arriba)
    oversold_rebound = prev_rsi < 38.0 and current_rsi >= 38.0 and current_close > prev_close

    # 2. Cruce Dorado EMA (EMA 9 cruza hacia arriba a EMA 21 en 5m con precio por encima)
    golden_cross = prev_ema_fast <= prev_ema_slow and current_ema_fast > current_ema_slow and current_close > current_ema_fast

    # 3. Ruptura de Impulso y Tendencia Sólida (Precio > EMA9 > EMA21 con RSI saludable 52-66)
    momentum_breakout = (
        current_close > current_ema_fast > current_ema_slow
        and 52.0 <= current_rsi <= 66.0
        and current_close > prev_close
        and current_ema_fast > prev_ema_fast
    )

    if golden_cross:
        indicators["reason"] = "Cruce dorado confirmado EMA(9/21)"
        return "BUY", indicators
    elif oversold_rebound:
        indicators["reason"] = "Rebote confirmado desde sobreventa RSI (<38)"
        return "BUY", indicators
    elif momentum_breakout:
        indicators["reason"] = "Impulso de tendencia alcista sólido (Precio > EMA9 > EMA21)"
        return "BUY", indicators

    return "HOLD", indicators
