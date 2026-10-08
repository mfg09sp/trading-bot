"""
Generador de Informes Interactivos de Cartera para Telegram.
Genera el desglose completo y detallado de Alpaca, Polymarket y Capital Total,
exactamente con el mismo formato que solicita el usuario.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import logging
from typing import Dict, Any, Tuple
from alpaca_service import AlpacaService
from polymarket_service import PolymarketService
from polymarket_paper import PolymarketPaperEngine
import config

logger = logging.getLogger("TelegramReporter")


def generate_portfolio_report() -> str:
    """
    Genera el informe completo de la cartera en formato HTML para Telegram.
    """
    # 1. Obtener datos de Alpaca
    alpaca_equity = 0.0
    alpaca_cash = 0.0
    alpaca_positions = {}
    alpaca_error = None

    try:
        alpaca = AlpacaService()
        acc = alpaca.get_account_summary()
        alpaca_equity = float(acc.get("portfolio_value", 0.0))
        alpaca_cash = float(acc.get("cash", 0.0))
        alpaca_positions = alpaca.get_open_positions()
    except Exception as e:
        alpaca_error = str(e)
        logger.error(f"Error consultando Alpaca para reporte: {e}")

    # 2. Obtener datos de Polymarket
    poly_equity = 0.0
    poly_cash = 0.0
    poly_positions = {}
    poly_summary = {}
    poly_error = None

    try:
        poly_engine = PolymarketPaperEngine()
        poly_engine.data = poly_engine._load_ledger()
        poly_summary = poly_engine.get_summary()
        poly_equity = float(poly_summary.get("total_equity_usdc", 0.0))
        poly_cash = float(poly_summary.get("cash_usdc", 0.0))
        poly_positions = poly_engine.data.get("active_positions", {})
    except Exception as e:
        poly_error = str(e)
        logger.error(f"Error consultando Polymarket para reporte: {e}")

    total_combined = alpaca_equity + poly_equity

    # 3. Construir mensaje HTML para Telegram
    lines = []
    lines.append("📊 <b>INFORME DETALLADO DE TU CARTERA</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 <b>CAPITAL TOTAL COMBINADO:</b> <code>${total_combined:,.2f} USD</code>\n")

    # --- SECCIÓN ALPACA ---
    lines.append("🏛️ <b>1. ALPACA (BOLSA Y CRIPTOMONEDAS)</b>")
    if alpaca_error:
        lines.append(f"⚠️ <i>Error consultando Alpaca: {alpaca_error}</i>")
    else:
        lines.append(f"• <b>Valor Total:</b> <code>${alpaca_equity:,.2f} USD</code>")
        lines.append(f"• <b>Efectivo Libre:</b> <code>${alpaca_cash:,.2f} USD</code>")
        lines.append("")

        # Posición destacada: S&P 500 (SPY)
        spy_pos = None
        other_alpaca = []
        seen_syms = set()

        for sym, p in alpaca_positions.items():
            cs = sym.replace("/", "")
            if cs in seen_syms:
                continue
            seen_syms.add(cs)
            if sym in getattr(config, "LONG_TERM_SYMBOLS", ["SPY", "VOO", "IVV"]):
                spy_pos = p
            else:
                other_alpaca.append((sym, p))

        if spy_pos:
            qty = float(spy_pos.get("qty", 0.0))
            entry_p = float(spy_pos.get("avg_entry_price", 0.0))
            cur_p = float(spy_pos.get("current_price", 0.0))
            mv = float(spy_pos.get("market_value", 0.0))
            pl = float(spy_pos.get("unrealized_pl", 0.0))
            pl_pct = float(spy_pos.get("unrealized_plpc", 0.0)) * 100.0
            emoji_pl = "🟢" if pl >= 0 else "🔴"
            lines.append("🛡️ <b>S&P 500 (SPY) [A Largo Plazo / Blindado]:</b>")
            lines.append(f"  • Cantidad: {qty:.2f} acciones (${entry_p:,.2f} ➔ <b>${cur_p:,.2f}</b>)")
            lines.append(f"  • Valor Actual: <code>${mv:,.2f} USD</code>")
            lines.append(f"  • P&L: <b>{pl:+,.2f} USD ({pl_pct:+.2f}%)</b> {emoji_pl}")
            lines.append("  • <i>Sin Stop Loss. Buy & Hold estratégico.</i>\n")

        if other_alpaca:
            lines.append("📈 <b>Otras Posiciones en Bolsa y Cripto:</b>")
            for sym, p in other_alpaca:
                cur_p = float(p.get("current_price", 0.0))
                pl = float(p.get("unrealized_pl", 0.0))
                pl_pct = float(p.get("unrealized_plpc", 0.0)) * 100.0
                emoji_pl = "🟢" if pl >= 0 else "🔴"
                lines.append(f"  • <b>{sym}:</b> {pl:+,.2f} USD ({pl_pct:+.2f}%) {emoji_pl} (a ${cur_p:,.2f})")
            lines.append("")

        # Radar de Super Inversores
        try:
            from super_investor_service import SuperInvestorService
            super_svc = SuperInvestorService()
            super_cands = super_svc.get_super_investor_candidates()[:4]
            if super_cands:
                lines.append("🐳 <b>Radar de Super Inversores (Pelosi, Buffett & Whales):</b>")
                for sc in super_cands:
                    lines.append(f"  • <b>{sc['symbol']}:</b> {', '.join(sc['investors'][:2])}")
                lines.append("")
        except Exception as e:
            logger.debug(f"Error cargando super inversores para reporte: {e}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # --- SECCIÓN POLYMARKET ---
    lines.append("🗳️ <b>2. POLYMARKET (MERCADOS DE PREDICCIÓN)</b>")
    if poly_error:
        lines.append(f"⚠️ <i>Error consultando Polymarket: {poly_error}</i>")
    else:
        lines.append(f"• <b>Patrimonio Total:</b> <code>${poly_equity:,.2f} USDC</code>")
        lines.append(f"• <b>Saldo Líquido:</b> <code>${poly_cash:,.2f} USDC</code>")
        lines.append("")

        # Posición destacada: Pedro Sánchez
        sanchez_pos = None
        other_poly = []

        for mid, p in poly_positions.items():
            q_text = str(p.get("question", ""))
            if "802374" in str(mid) or "Sanchez" in q_text or "Sánchez" in q_text:
                sanchez_pos = p
            else:
                other_poly.append(p)

        if sanchez_pos:
            shares = float(sanchez_pos.get("shares", 0.0))
            entry_p = float(sanchez_pos.get("entry_price", 0.0))
            cur_p = float(sanchez_pos.get("current_price", 0.0))
            inv = float(sanchez_pos.get("invested_usd", 0.0))
            cur_val = float(sanchez_pos.get("current_value", 0.0))
            pl = float(sanchez_pos.get("unrealized_pnl", 0.0))
            pl_pct = float(sanchez_pos.get("unrealized_pnl_pct", 0.0))
            emoji_pl = "🟢" if pl >= 0 else "🔴"
            lines.append("🛡️ <b>Pedro Sánchez [Convicción / Sin Stop Loss]:</b>")
            lines.append(f"  • Elección: <b>{sanchez_pos.get('outcome', 'YES')}</b> ({shares:,.1f} contratos)")
            lines.append(f"  • Invertido: ${inv:,.2f} ➔ Valor Hoy: <code>${cur_val:,.2f} USDC</code>")
            lines.append(f"  • Cuota: ${entry_p:.3f} ➔ <b>${cur_p:.3f}</b>")
            lines.append(f"  • P&L: <b>{pl:+,.2f} USDC ({pl_pct:+.2f}%)</b> {emoji_pl}")
            lines.append("  • <i>Sin Stop Loss. Take Profit automático fijado al subir a $6,000 USD (+20%).</i>\n")

        if other_poly:
            lines.append("🔮 <b>Otras Apuestas Activas:</b>")
            for p in other_poly[:6]:  # Mostrar las 6 más relevantes para no saturar
                q_short = p.get("question", "")[:38] + "..." if len(p.get("question", "")) > 38 else p.get("question", "")
                outcome = p.get("outcome", "")
                pl = float(p.get("unrealized_pnl", 0.0))
                pl_pct = float(p.get("unrealized_pnl_pct", 0.0))
                emoji_pl = "🟢" if pl >= 0 else "🔴"
                lines.append(f"  • <b>{q_short}</b> ({outcome}): {pl:+,.2f} USD ({pl_pct:+.1f}%) {emoji_pl}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤖 <i>Operando 24/7 en la nube con Google Gemini.</i>")
    lines.append("💡 <i>Escribe /estado o 'como va' en cualquier momento para actualizar.</i>")

    return "\n".join(lines)


if __name__ == "__main__":
    report = generate_portfolio_report()
    print(report)
