"""
Servicio de conexión y operativa con Alpaca Markets.
Permite consultar cuenta, obtener precios históricos y colocar órdenes bracket (TP/SL).
"""

import time
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime, timedelta, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.common.enums import Sort

import config

logger = logging.getLogger("AlpacaService")


class AlpacaService:
    def __init__(self):
        config.validate_config(require_telegram=False)

        self.trading_client = TradingClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY,
            paper=config.ALPACA_PAPER
        )
        self.stock_data_client = StockHistoricalDataClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY
        )
        self.crypto_data_client = CryptoHistoricalDataClient(
            api_key=config.ALPACA_API_KEY,
            secret_key=config.ALPACA_SECRET_KEY
        )

    def get_account_summary(self) -> Dict[str, Any]:
        """Obtiene el resumen de la cuenta (saldo, poder de compra, estado)."""
        acct = self.trading_client.get_account()
        cash = float(acct.cash)
        portfolio_val = float(acct.portfolio_value)
        long_val = getattr(acct, "long_market_value", None)
        invested = float(long_val) if long_val is not None else max(0.0, portfolio_val - cash)
        return {
            "id": acct.id,
            "status": acct.status,
            "currency": acct.currency,
            "cash": cash,
            "portfolio_value": portfolio_val,
            "invested": invested,
            "buying_power": float(acct.buying_power),
            "trading_blocked": acct.trading_blocked,
            "paper": config.ALPACA_PAPER
        }

    def get_open_positions(self) -> Dict[str, Any]:
        """Devuelve un diccionario de posiciones abiertas indexado por símbolo."""
        positions = self.trading_client.get_all_positions()
        pos_map = {}
        for p in positions:
            data = {
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc)
            }
            pos_map[p.symbol] = data
            # Indexar también la versión con barra para cripto si aplica (BTCUSD -> BTC/USD)
            if p.symbol.endswith("USD") and "/" not in p.symbol and len(p.symbol) > 3:
                pos_map[f"{p.symbol[:-3]}/{p.symbol[-3:]}"] = data
            elif "/" in p.symbol:
                pos_map[p.symbol.replace("/", "")] = data
        return pos_map

    def is_market_open(self) -> bool:
        """Comprueba si el mercado de valores estadounidense está abierto actualmente."""
        try:
            return bool(self.trading_client.get_clock().is_open)
        except Exception:
            return False

    def get_bars(
        self,
        symbol: str,
        limit: int = 50,
        timeframe: Optional[TimeFrame] = None
    ) -> pd.DataFrame:
        """
        Descarga las últimas barras de precio (por defecto velas de 5 minutos
        para filtrar el ruido aleatorio del mercado de 1 minuto).
        """
        tf = timeframe or TimeFrame(5, TimeFrameUnit.Minute)
        is_crypto = "/" in symbol or (symbol.endswith("USD") and len(symbol) > 4)

        try:
            if is_crypto:
                crypto_symbol = symbol if "/" in symbol else f"{symbol[:-3]}/{symbol[-3:]}"
                req = CryptoBarsRequest(
                    symbol_or_symbols=crypto_symbol,
                    timeframe=tf,
                    limit=limit,
                    sort=Sort.DESC
                )
                bars = self.crypto_data_client.get_crypto_bars(req)
                df = bars.df
            else:
                req = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=tf,
                    limit=limit,
                    sort=Sort.DESC
                )
                bars = self.stock_data_client.get_stock_bars(req)
                df = bars.df

            if df.empty:
                return pd.DataFrame()

            # Si el DataFrame tiene MultiIndex (symbol, timestamp), reindexar
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol if not is_crypto else crypto_symbol, level=0)

            # Reordenar cronológicamente para calcular indicadores correctamente
            df = df.sort_index()

            return df
        except Exception as e:
            logger.error(f"Error descargando barras para {symbol}: {e}")
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Obtiene el último precio de cierre disponible de un símbolo."""
        df = self.get_bars(symbol, limit=2)
        if not df.empty and "close" in df.columns:
            return float(df["close"].iloc[-1])
        return None

    def place_bracket_order(
        self,
        symbol: str,
        qty: float,
        current_price: float,
        tp_pct: float,
        sl_pct: float
    ):
        """
        Coloca una orden bracket atómica:
        - Orden principal: Compra a mercado
        - Orden de Take Profit: Venta límite a current_price * (1 + tp_pct)
        - Orden de Stop Loss: Venta stop a current_price * (1 - sl_pct)
        Ambas quedan registradas y aseguradas directamente en Alpaca.
        """
        if current_price < 1.0:
            tp_price = round(current_price * (1.0 + tp_pct), 4)
            sl_price = round(current_price * (1.0 - sl_pct), 4)
        elif current_price < 50.0:
            tp_price = round(current_price * (1.0 + tp_pct), 3)
            sl_price = round(current_price * (1.0 - sl_pct), 3)
        else:
            tp_price = round(current_price * (1.0 + tp_pct), 2)
            sl_price = round(current_price * (1.0 - sl_pct), 2)

        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,
            take_profit=TakeProfitRequest(limit_price=tp_price),
            stop_loss=StopLossRequest(stop_price=sl_price)
        )

        logger.info(f"Enviando orden bracket para {symbol}: Qty={qty}, TP={tp_price}, SL={sl_price}")
        order = self.trading_client.submit_order(order_data)
        return order, tp_price, sl_price

    def get_open_orders(self) -> List[Any]:
        """Obtiene la lista de órdenes pendientes."""
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        return self.trading_client.get_orders(filter=req)

    def cancel_orders_for_symbol(self, symbol: str) -> None:
        """Cancela las órdenes abiertas asociadas a un activo para liberar sus acciones retenidas."""
        clean = symbol.replace("/", "")
        try:
            open_orders = self.get_open_orders()
            for o in open_orders:
                if getattr(o, "symbol", "").replace("/", "") == clean:
                    try:
                        self.trading_client.cancel_order_by_id(o.id)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error cancelando órdenes previas para {symbol}: {e}")

    def close_position(self, symbol: str) -> Optional[Any]:
        """
        Cierra una posición abierta inmediatamente a precio de mercado.
        Cancela automáticamente cualquier orden bracket pendiente vinculada en Alpaca.
        """
        try:
            logger.info(f"Cerrando posición en {symbol} a precio de mercado...")
            # Cancelar primero órdenes pendientes (TP/SL) para liberar acciones retenidas (held_for_orders)
            self.cancel_orders_for_symbol(symbol)
            time.sleep(0.5)

            clean = symbol.replace("/", "")
            try:
                return self.trading_client.close_position(clean)
            except Exception:
                alt_sym = f"{clean[:-3]}/{clean[-3:]}" if len(clean) > 5 else clean
                return self.trading_client.close_position(alt_sym)
        except Exception as e:
            logger.error(f"Error al cerrar posición en {symbol}: {e}")
            return None
