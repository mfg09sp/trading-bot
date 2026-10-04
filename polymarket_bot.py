"""
Bot Autónomo de Predicción e Inversión en Polymarket (Modo Simulación / Paper Trading).
Rastrea mercados en tiempo real, analiza noticias y tuits de Elon Musk, Donald Trump,
la Reserva Federal y Cripto, y ejecuta apuestas simuladas con gestión de riesgo y alertas a Telegram.
"""

import sys
import time
import logging
import argparse
from typing import Dict, Any, List

import config
from polymarket_service import PolymarketService
from news_service import NewsService
from polymarket_paper import PolymarketPaperEngine
import notifier

# Configuración de salida en consola con UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("PolymarketBot")


class PolymarketBot:
    def __init__(self):
        self.poly_service = PolymarketService()
        self.news_service = NewsService()
        self.paper_engine = PolymarketPaperEngine()
        self.search_keywords = ["Trump", "Elon", "Musk", "Fed", "Bitcoin", "Election", "Midterms"]

    def run_cycle(self) -> None:
        """Ejecuta un ciclo completo de evaluación de Polymarket."""
        logger.info("========== Iniciando ciclo de análisis de Polymarket ==========")
        
        # 1. Evaluar posiciones abiertas (Take Profit, Stop Loss, Resoluciones)
        closed_trades = self.paper_engine.update_and_evaluate_positions(self.poly_service)
        summary = self.paper_engine.get_summary()

        for trade in closed_trades:
            notifier.notify_polymarket_close(trade, summary)

        # 2. Comprobar si hay espacio para nuevas posiciones
        if not self.paper_engine.can_open_position(config.POLYMARKET_MAX_BET_USDC):
            logger.info(f"Límite de posiciones ({summary['active_positions_count']}/{config.POLYMARKET_MAX_POSITIONS}) o saldo insuficiente (${summary['cash_usdc']:.2f} USDC).")
            return

        # 3. Obtener catalizadores de noticias recientes
        logger.info("Consultando noticias y tuits recientes sobre Elon, Trump, Fed y Cripto...")
        catalysts = self.news_service.get_latest_catalysts()

        # 4. Escanear mercados líquidos en Polymarket
        logger.info(f"Buscando mercados activos en Polymarket con palabras clave: {self.search_keywords}...")
        markets = self.poly_service.search_markets_by_keywords(self.search_keywords, limit_per_cat=30)
        logger.info(f"Se encontraron {len(markets)} mercados líquidos en Polymarket.")

        # 5. Analizar y seleccionar las mejores oportunidades
        for m in markets:
            if not self.paper_engine.can_open_position(config.POLYMARKET_MAX_BET_USDC):
                break

            m_id = m["id"]
            if m_id in self.paper_engine.data.get("active_positions", {}):
                continue

            q = m["question"]
            prices = m.get("prices", {})

            # Buscar si alguna noticia reciente afecta a este mercado
            match = self.news_service.find_catalyst_for_question(q, catalysts)
            
            # Estrategia de toma de decisión:
            # Seleccionar mercados donde el precio esté entre 0.15 y 0.80 (margen de beneficio)
            # y haya catalizador informativo o volumen elevado.
            chosen_outcome = None
            entry_price = 0.0

            yes_price = prices.get("Yes", 0.0)
            no_price = prices.get("No", 0.0)

            # Criterio A: Si hay noticia relevante y el mercado cotiza en rango razonable
            if match and match.get("score", 0) >= 2:
                # Si el SÍ cotiza con descuento (ej. entre 0.20 y 0.65)
                if 0.20 <= yes_price <= 0.65:
                    chosen_outcome = "Yes"
                    entry_price = yes_price
                elif 0.20 <= no_price <= 0.65:
                    chosen_outcome = "No"
                    entry_price = no_price

            # Criterio B: Mercados de gran volumen (> $50,000) con probabilidad asimétrica atractiva
            elif m.get("volume24hr", 0.0) > 50000:
                if 0.25 <= yes_price <= 0.55:
                    chosen_outcome = "Yes"
                    entry_price = yes_price
                    match = {
                        "category": "Alto Volumen",
                        "headline": f"Mercado con alto volumen en 24h (${m['volume24hr']:,.0f}) y probabilidad atractiva ({yes_price*100:.1f}%)",
                        "source": "Polymarket CLOB",
                        "score": 1
                    }

            if chosen_outcome and entry_price > 0:
                bet_amount = min(config.POLYMARKET_MAX_BET_USDC, summary["cash_usdc"])
                if bet_amount >= 10.0:
                    pos = self.paper_engine.open_position(m, chosen_outcome, bet_amount, match)
                    if pos:
                        updated_summary = self.paper_engine.get_summary()
                        notifier.notify_polymarket_bet(
                            question=q,
                            outcome=chosen_outcome,
                            entry_price=entry_price,
                            invested_usd=bet_amount,
                            shares=pos["shares"],
                            url=pos["url"],
                            catalyst=match,
                            summary=updated_summary
                        )
                        time.sleep(1)  # Pequeña pausa entre notificaciones

        final_summary = self.paper_engine.get_summary()
        logger.info(f"Ciclo finalizado. Estado cartera: ${final_summary['total_equity_usdc']:.2f} USDC (Libre: ${final_summary['cash_usdc']:.2f} | En apuestas: ${final_summary['invested_usdc']:.2f})")


def main():
    parser = argparse.ArgumentParser(description="Bot Autónomo de Polymarket Paper Trading")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo de análisis y sale")
    parser.add_argument("--status", action="store_true", help="Muestra el resumen y posiciones activas de Polymarket")
    args = parser.parse_args()

    bot = PolymarketBot()

    if args.status:
        s = bot.paper_engine.get_summary()
        print("\n" + "="*50)
        print("  💼 RESUMEN DE CARTERA POLYMARKET (Paper Trading)")
        print("="*50)
        print(f"  💵 Efectivo libre en cartera: ${s['cash_usdc']:,.2f} USDC")
        print(f"  📊 Dinero en apuestas activas: ${s['invested_usdc']:,.2f} USDC")
        print(f"  💼 Valor total de la cartera: ${s['total_equity_usdc']:,.2f} USDC")
        print(f"  📈 P&L no realizado: ${s['unrealized_pnl_usdc']:+,.2f} USDC ({s['unrealized_pnl_pct']:+.2f}%)")
        print(f"  🏆 Historial de aciertos: {s['win_count']} ganadas / {s['loss_count']} perdidas")
        print(f"  🎯 Apuestas activas: {s['active_positions_count']}")
        print("-"*50)
        for i, pos in enumerate(bot.paper_engine.data.get("active_positions", {}).values(), 1):
            q = pos.get("question", "")
            out = pos.get("outcome", "")
            ep = pos.get("entry_price", 0.0)
            cp = pos.get("current_price", 0.0)
            inv = pos.get("invested_usd", 0.0)
            val = pos.get("current_value", inv)
            pnl = val - inv
            pnl_p = (cp - ep) / ep * 100 if ep > 0 else 0.0
            print(f"  {i}. [{out}] {q[:55]}...")
            print(f"     Entrada: ${ep:.3f} | Actual: ${cp:.3f} | Invertido: ${inv:.2f} | P&L: ${pnl:+.2f} ({pnl_p:+.1f}%)")
        print("="*50 + "\n")
        return

    if args.once:
        bot.run_cycle()
        return

    logger.info(f"Iniciando bucle de supervisión continua de Polymarket (cada {config.POLYMARKET_POLL_INTERVAL_SECONDS}s)...")
    while True:
        try:
            bot.run_cycle()
        except Exception as e:
            logger.error(f"Error inesperado en el ciclo del bot de Polymarket: {e}", exc_info=True)
        time.sleep(config.POLYMARKET_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
