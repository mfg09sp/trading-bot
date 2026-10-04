"""
Módulo de Configuración central del Bot de Trading.
Carga variables desde el entorno o archivo .env y valida los valores mínimos.
"""

import os
from typing import List
from dotenv import load_dotenv

# Carga variables de entorno desde el archivo .env en la misma carpeta
load_dotenv()

# Credenciales de Alpaca (soporta tanto ALPACA_API_KEY como ALPACA_APT_KEY)
ALPACA_API_KEY: str = (os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_APT_KEY") or "").strip()
ALPACA_SECRET_KEY: str = os.getenv("ALPACA_SECRET_KEY", "").strip()
ALPACA_PAPER: bool = os.getenv("ALPACA_PAPER", "true").lower() in ("true", "1", "yes")

# Credenciales de Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Parámetros de Trading
_symbols_raw: str = os.getenv("SYMBOLS", "AAPL,NVDA,TSLA,MSFT")
SYMBOLS: List[str] = [s.strip().upper() for s in _symbols_raw.split(",") if s.strip()]

RISK_PER_TRADE_USD: float = float(os.getenv("RISK_PER_TRADE_USD", "2500.0"))  # Aumentado 50x (de $50 a $2500 por trade)
TAKE_PROFIT_PCT: float = float(os.getenv("TAKE_PROFIT_PCT", "0.015"))  # 1.5%
STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "0.010"))      # 1.0%
CHECK_INTERVAL_SECONDS: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))
MAX_ACTIVE_POSITIONS: int = int(os.getenv("MAX_ACTIVE_POSITIONS", "10"))
AUTO_DISCOVERY: bool = os.getenv("AUTO_DISCOVERY", "true").lower() in ("true", "1", "yes")
COOLDOWN_MINUTES: int = int(os.getenv("COOLDOWN_MINUTES", "15"))
MAX_DAILY_DRAWDOWN_USD: float = float(os.getenv("MAX_DAILY_DRAWDOWN_USD", "2500.0"))
HEARTBEAT_INTERVAL_MINUTES: int = int(os.getenv("HEARTBEAT_INTERVAL_MINUTES", "30"))

# Operativa de Futuros / Materias Primas / ETFs Apalancados
FUTURES_SYMBOLS: List[str] = ["BITO", "USO", "GLD", "SLV", "TQQQ", "UPRO", "SOXL"]
FUTURES_RISK_PER_TRADE_USD: float = float(os.getenv("FUTURES_RISK_PER_TRADE_USD", "2500.0"))  # Aumentado a $2,500
MAX_FUTURES_POSITIONS: int = int(os.getenv("MAX_FUTURES_POSITIONS", "2"))

# Base URLs
if ALPACA_PAPER:
    ALPACA_BASE_URL = "https://paper-api.alpaca.markets"
    ALPACA_DATA_URL = "https://data.alpaca.markets"
else:
    ALPACA_BASE_URL = "https://api.alpaca.markets"
    ALPACA_DATA_URL = "https://data.alpaca.markets"

# Parámetros de Polymarket (Paper Trading / Simulación)
POLYMARKET_STARTING_BALANCE_USDC: float = float(os.getenv("POLYMARKET_STARTING_BALANCE_USDC", "20000.0"))  # $20,000 USDC
POLYMARKET_MAX_BET_USDC: float = float(os.getenv("POLYMARKET_MAX_BET_USDC", "2000.0"))  # $2,000 USDC por apuesta directa
POLYMARKET_MAX_POSITIONS: int = int(os.getenv("POLYMARKET_MAX_POSITIONS", "8"))
POLYMARKET_TAKE_PROFIT_PCT: float = float(os.getenv("POLYMARKET_TAKE_PROFIT_PCT", "0.30"))  # +30%
POLYMARKET_STOP_LOSS_PCT: float = float(os.getenv("POLYMARKET_STOP_LOSS_PCT", "0.15"))      # -15%
POLYMARKET_POLL_INTERVAL_SECONDS: int = int(os.getenv("POLYMARKET_POLL_INTERVAL_SECONDS", "300"))  # 5 minutos


def validate_config(require_telegram: bool = False) -> None:
    """Valida que existan las credenciales mínimas necesarias para operar."""
    errors = []
    if not ALPACA_API_KEY:
        errors.append("Falta ALPACA_API_KEY en el archivo .env")
    if not ALPACA_SECRET_KEY:
        errors.append("Falta ALPACA_SECRET_KEY en el archivo .env")
    if require_telegram:
        if not TELEGRAM_BOT_TOKEN:
            errors.append("Falta TELEGRAM_BOT_TOKEN en el archivo .env")
        if not TELEGRAM_CHAT_ID:
            errors.append("Falta TELEGRAM_CHAT_ID en el archivo .env")

    if errors:
        msg = "\n".join(f" - {err}" for err in errors)
        raise ValueError(f"Configuración incompleta:\n{msg}")
