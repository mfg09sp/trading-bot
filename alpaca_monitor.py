"""
Monitor de Supervisión y Riesgo de Alpaca (Acciones y Criptomonedas).
Supervisa en segundo plano cada 60 segundos las posiciones abiertas en Alpaca para
ejecutar Take Profit, Stop Loss o salidas dinámicas, enviando el desglose completo
de tu dinero a Telegram.
NO realiza compras a ciegas; las decisiones de entrada las toma la IA con investigación.
"""

import sys
import time
import logging
from datetime import datetime

import config
from alpaca_service import AlpacaService
import notifier

# Configuración UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AlpacaMonitor")


def get_current_equity_safe(alpaca: AlpacaService):
    try:
        summary = alpaca.get_account_summary()
        return summary["portfolio_value"], summary["cash"], summary.get("long_market_value", 0.0)
    except Exception as e:
        logger.error(f"Error consultando saldo de cuenta: {e}")
        return None, None, None


def main():
    alpaca = AlpacaService()
    logger.info("Iniciando Monitor de Riesgo de Alpaca en segundo plano (vigilancia cada 60s)...")
    
    last_heartbeat = time.time()

    while True:
        try:
            positions = alpaca.get_open_positions()
            current_equity, cash, invested = get_current_equity_safe(alpaca)

            for sym, pos in list(positions.items()):
                # Omitir duplicados de indexación con barra
                if "/" in sym and sym.replace("/", "") in positions:
                    continue

                # Proteger activos de convicción a largo plazo (sin Stop Loss ni Take Profit)
                if sym in getattr(config, "LONG_TERM_SYMBOLS", ["SPY", "VOO", "IVV"]):
                    continue

                cur_p = pos.get("current_price", 0.0)
                entry_p = pos.get("avg_entry_price", cur_p)
                qty = pos.get("qty", 0.0)
                pnl = pos.get("unrealized_pl", 0.0)
                pnl_pct = pos.get("unrealized_plpc", 0.0)

                is_crypto = "/" in sym or (sym.endswith("USD") and len(sym) > 4)
                
                # Umbrales de salida ampliados (Swing trading con margen anti-barridos)
                tp_threshold = 0.060 if is_crypto else 0.055  # +6.0% cripto, +5.5% acciones
                sl_threshold = -0.035 if is_crypto else -0.028 # -3.5% cripto, -2.8% acciones

                should_close = False
                is_tp = False

                if pnl_pct >= tp_threshold:
                    should_close = True
                    is_tp = True
                elif pnl_pct <= sl_threshold:
                    should_close = True
                    is_tp = False

                if should_close and cur_p > 0:
                    real_pnl = (cur_p - entry_p) * qty
                    logger.info(f"[{sym}] Activando salida de riesgo: {'Take Profit' if is_tp else 'Stop Loss'}. P&L: ${real_pnl:+.2f} ({pnl_pct*100:+.2f}%)")
                    res = alpaca.close_position(sym)
                    if res:
                        time.sleep(1)
                        eq_now, cash_now, inv_now = get_current_equity_safe(alpaca)
                        if is_tp:
                            notifier.notify_tp_hit(sym, cur_p, real_pnl, total_equity=eq_now, cash=cash_now, invested=inv_now)
                        else:
                            notifier.notify_sl_hit(sym, cur_p, real_pnl, total_equity=eq_now, cash=cash_now, invested=inv_now)

            # Envío periódico de estado cada 30 minutos
            if time.time() - last_heartbeat >= config.HEARTBEAT_INTERVAL_MINUTES * 60:
                summary = []
                seen = set()
                for sym, pos_d in positions.items():
                    c_s = sym.replace("/", "")
                    if c_s in seen:
                        continue
                    seen.add(c_s)
                    summary.append({
                        "symbol": sym,
                        "pnl": pos_d.get("unrealized_pl", 0.0),
                        "pnl_pct": pos_d.get("unrealized_plpc", 0.0) * 100.0,
                        "current_price": pos_d.get("current_price", 0.0)
                    })
                notifier.notify_periodic_status(current_equity, cash, invested, summary)
                last_heartbeat = time.time()

            time.sleep(60)

        except Exception as e:
            logger.error(f"Error en bucle de monitor de Alpaca: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
