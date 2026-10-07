import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
from alpaca_service import AlpacaService
from polymarket_service import PolymarketService
from polymarket_paper import PolymarketPaperEngine

print("==================================================================")
print("                    ESTADO DETALLADO DE INVERSIONES               ")
print("==================================================================")

try:
    alpaca = AlpacaService()
    acc = alpaca.get_account_summary()
    print("\n📈 [ALPACA - BOLSA Y CRIPTOMONEDAS]")
    print(f"  • Valor Total de la Cuenta:  ${acc['portfolio_value']:,.2f} USD")
    print(f"  • Efectivo Libre:            ${acc['cash']:,.2f} USD")
    print(f"  • Capital Invertido:         ${acc.get('long_market_value', 0):,.2f} USD")
    
    positions = alpaca.get_open_positions()
    print("\n  --- Desglose de Posiciones Abiertas en Alpaca ---")
    seen = set()
    for sym, p in positions.items():
        cs = sym.replace("/", "")
        if cs in seen:
            continue
        seen.add(cs)
        qty = float(p.get("qty", 0.0))
        entry_p = float(p.get("avg_entry_price", 0.0))
        cur_p = float(p.get("current_price", 0.0))
        mv = float(p.get("market_value", 0.0))
        pl = float(p.get("unrealized_pl", 0.0))
        pl_pct = float(p.get("unrealized_plpc", 0.0)) * 100.0

        tag = ""
        if sym in ["SPY", "VOO", "IVV"]:
            tag = " 🛡️ [A LARGO PLAZO / SIN STOP LOSS]"
        
        print(f"  • {sym:<7}{tag}")
        print(f"    Cantidad: {qty:.4f} | Entrada: ${entry_p:,.2f} | Actual: ${cur_p:,.2f}")
        print(f"    Valor Total: ${mv:,.2f} USD | Ganancia/Pérdida: ${pl:+,.2f} USD ({pl_pct:+.2f}%)")
except Exception as e:
    print(f"Error consultando Alpaca: {e}")

try:
    print("\n" + "=" * 66)
    print("🔮 [POLYMARKET - MERCADOS DE PREDICCIÓN]")
    poly_engine = PolymarketPaperEngine()
    poly_engine.data = poly_engine._load_ledger()
    summary = poly_engine.get_summary()

    print(f"  • Patrimonio Total en Polymarket: ${summary['total_equity_usdc']:,.2f} USDC")
    print(f"  • Saldo Líquido Disponible:      ${summary['cash_usdc']:,.2f} USDC")
    print(f"  • P&L No Realizado (Flotante):   ${summary['unrealized_pnl_usdc']:+,.2f} USDC ({summary['unrealized_pnl_pct']:+.2f}%)")
    print(f"  • P&L Realizado (Cerradas):      ${summary['realized_pnl_usdc']:+,.2f} USDC")
    print(f"  • Operaciones Ganadas/Perdidas:   {summary['win_count']} Ganadas / {summary['loss_count']} Perdidas")

    print("\n  --- Desglose de Apuestas Activas en Polymarket ---")
    for mid, p in poly_engine.data.get("active_positions", {}).items():
        nsl = " 🛡️ [CONVICCIÓN / SIN STOP LOSS]" if p.get("no_stop_loss") else ""
        print(f"  • {p.get('question')}{nsl}")
        print(f"    Opción: {p.get('outcome')} | Títulos: {p.get('shares'):,.1f} | Entrada: ${p.get('entry_price', 0):.3f} | Actual: ${p.get('current_price', 0):.3f}")
        print(f"    Invertido: ${p.get('invested_usd', 0):,.2f} USD | Valor Hoy: ${p.get('current_value', 0):,.2f} USD | P&L: ${p.get('unrealized_pnl', 0):+,.2f} USD ({p.get('unrealized_pnl_pct', 0):+.2f}%)")
except Exception as e:
    print(f"Error consultando Polymarket: {e}")

print("\n==================================================================")
