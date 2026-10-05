"""
Script de Ejecución Inmediata de Inversión a Largo Plazo: S&P 500 (SPY).
Invierte $50,000.00 USD en el índice S&P 500 (SPY) a través de Alpaca.
Estrategia: Buy & Hold a muy largo plazo, SIN Stop Loss ni Take Profit.
"""

from __future__ import annotations
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import logging
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

import config
from alpaca_service import AlpacaService
import notifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SP500_Investment")


def main():
    target_investment_usd = 50000.0
    symbol = "SPY"

    logger.info("=================================================================")
    logger.info("   EJECUTANDO INVERSIÓN A LARGO PLAZO EN EL S&P 500 (SPY)       ")
    logger.info("=================================================================")

    alpaca = AlpacaService()
    account = alpaca.get_account_summary()
    cash = float(account["cash"])
    portfolio_val = float(account["portfolio_value"])

    logger.info(f"Saldo en cuenta Alpaca: ${portfolio_val:,.2f} USD")
    logger.info(f"Efectivo disponible: ${cash:,.2f} USD")

    if cash < target_investment_usd:
        logger.error(f"Efectivo insuficiente (${cash:,.2f}) para invertir ${target_investment_usd:,.2f}")
        return

    # Obtener cotización actual de SPY
    current_price = alpaca.get_latest_price(symbol)
    if not current_price or current_price <= 0:
        logger.error("No se pudo obtener la cotización actual de SPY.")
        return

    logger.info(f"Cotización actual de SPY (S&P 500 ETF): ${current_price:,.2f} USD")

    # Intentar orden nocional exacta ($50,000 USD) o cálculo de acciones enteras
    order = None
    filled_qty = None
    filled_price = None

    try:
        logger.info(f"Enviando orden de compra nocional por ${target_investment_usd:,.2f} USD...")
        order_data = MarketOrderRequest(
            symbol=symbol,
            notional=round(target_investment_usd, 2),
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        order = alpaca.trading_client.submit_order(order_data)
        logger.info(f"Orden nocional enviada con ID: {order.id}")
    except Exception as e:
        logger.warning(f"Orden nocional falló ({e}). Intentando con número entero de acciones...")
        qty = int(target_investment_usd / current_price)
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        order = alpaca.trading_client.submit_order(order_data)
        logger.info(f"Orden por {qty} acciones enviada con ID: {order.id}")

    # Esperar confirmación de ejecución
    time.sleep(3)
    try:
        latest_order = alpaca.trading_client.get_order_by_id(order.id)
        logger.info(f"Estado de la orden: {latest_order.status}")
        filled_qty = float(latest_order.filled_qty) if latest_order.filled_qty else None
        filled_price = float(latest_order.filled_avg_price) if latest_order.filled_avg_price else current_price
    except Exception as ex:
        logger.warning(f"Error consultando estado de orden: {ex}")
        filled_price = current_price

    # Obtener estado de posición abierta
    positions = alpaca.get_open_positions()
    spy_pos = positions.get("SPY", {})
    actual_qty = float(spy_pos.get("qty", filled_qty or (target_investment_usd / current_price)))
    actual_price = float(spy_pos.get("avg_entry_price", filled_price or current_price))
    actual_val = actual_qty * actual_price

    logger.info("-----------------------------------------------------------------")
    logger.info(f"¡INVERSIÓN EN S&P 500 COMPLETADA CON ÉXITO!")
    logger.info(f"Activo: {symbol} (SPDR S&P 500 ETF Trust)")
    logger.info(f"Cantidad de acciones: {actual_qty:.4f}")
    logger.info(f"Precio de entrada: ${actual_price:,.2f} USD")
    logger.info(f"Capital total invertido: ${actual_val:,.2f} USD")
    logger.info(f"Stop Loss: DESACTIVADO (Buy & Hold a muy largo plazo)")
    logger.info(f"Take Profit: DESACTIVADO (Crecimiento compuesto)")
    logger.info("-----------------------------------------------------------------")

    # Notificar a Telegram
    updated_acct = alpaca.get_account_summary()
    msg = (
        f"🏛️ <b>NUEVA INVERSIÓN A LARGO PLAZO: S&P 500 (SPY)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Activo:</b> SPY (SPDR S&P 500 ETF Trust)\n"
        f"🔹 <b>Estrategia:</b> Buy & Hold a muy largo plazo\n"
        f"💰 <b>Capital Invertido:</b> <b>${actual_val:,.2f} USD</b>\n"
        f"📊 <b>Acciones compradas:</b> {actual_qty:.4f} unidades\n"
        f"💵 <b>Precio de Compra:</b> ${actual_price:,.2f} USD\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Stop Loss:</b> <b>DESACTIVADO</b> (Sin venta por caídas temporales)\n"
        f"🎯 <b>Take Profit:</b> <b>DESACTIVADO</b> (Dejar componer a largo plazo)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💼 <b>Patrimonio Total:</b> ${float(updated_acct['portfolio_value']):,.2f} USD\n"
        f"💵 <b>Efectivo Libre Restante:</b> ${float(updated_acct['cash']):,.2f} USD\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>El bot mantendrá este activo blindado en cartera sin aplicar salidas automáticas.</i>"
    )
    notifier.send_telegram_message(msg)
    logger.info("Notificación enviada a Telegram con éxito.")


if __name__ == "__main__":
    main()
