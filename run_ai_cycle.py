"""
Ciclo Unificado de Inteligencia Artificial (Polymarket + Alpaca Cripto y Acciones).
Utiliza Google Gemini (con la API Key del usuario) para analizar de forma exhaustiva
noticias, tuits, probabilidades de Polymarket y setups técnicos en Alpaca.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import os
import time
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

import config
from ai_analyst import AIAnalyst
from news_service import NewsService
from polymarket_service import PolymarketService
from polymarket_paper import PolymarketPaperEngine
from alpaca_service import AlpacaService
import notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("UnifiedAICycle")


def run_cycle():
    logger.info("=================================================================")
    logger.info("   INICIANDO CICLO DE ANÁLISIS CUANTITATIVO CON GOOGLE GEMINI    ")
    logger.info("=================================================================")

    # 1. Inicializar servicios y analista de IA
    analyst = AIAnalyst()
    if not analyst.is_available():
        logger.error("No se detectó GEMINI_API_KEY en el entorno.")
        return

    poly_service = PolymarketService()
    poly_paper = PolymarketPaperEngine()
    news_service = NewsService()
    alpaca = AlpacaService()

    # 1.5. Evaluar salidas de posiciones abiertas en Polymarket (Take Profit / Stop Loss)
    logger.info("Evaluando Take Profit y Stop Loss de posiciones de Polymarket...")
    closed_trades = poly_paper.update_and_evaluate_positions(poly_service)
    for trade in closed_trades:
        notifier.notify_polymarket_close(trade, poly_paper.get_summary())

    # 2. Recopilar contexto informativo masivo (Noticias, RSS, Tuits, Macro)
    logger.info("1/4. Recopilando noticias de Trump, Elon Musk, Fed, Cripto e IA...")
    catalysts = news_service.get_latest_catalysts()
    all_news = []
    for cat, items in catalysts.items():
        for item in items:
            all_news.append(f"- [{cat.upper()}] {item.get('title', '')} (Fuente: {item.get('source', 'Web')})")
    
    news_summary_text = "\n".join(all_news[:25])
    logger.info(f"Se recopilaron {len(all_news)} catalizadores informativos.")

    # 3. Analizar Polymarket con mayor amplitud de categorías
    logger.info("2/4. Escaneando mercados líquidos en Polymarket...")
    poly_summary = poly_paper.get_summary()
    keywords = ["Trump", "Elon", "Musk", "Fed", "Bitcoin", "Crypto", "Election", "Economy", "AI", "Tariff"]
    markets = poly_service.search_markets_by_keywords(keywords, limit_per_cat=30)
    
    poly_trades_executed = 0
    for m in markets:
        # Si ya alcanzamos el límite de posiciones o no hay saldo suficiente
        if not poly_paper.can_open_position(config.POLYMARKET_MAX_BET_USDC):
            break

        m_id = m.get("id")
        if m_id in poly_paper.data.get("active_positions", {}):
            continue

        q = m.get("question", "")
        prices = m.get("prices", {})
        yes_p = prices.get("Yes", 0.0)
        no_p = prices.get("No", 0.0)

        # Filtrar mercados con liquidez o precios con margen de beneficio
        if (yes_p < 0.05 or yes_p > 0.95) and (no_p < 0.05 or no_p > 0.95):
            continue

        logger.info(f"Consultando a Gemini para Polymarket: {q[:60]}... (Yes: ${yes_p:.3f}, No: ${no_p:.3f})")
        
        # Consultar Gemini
        analysis = analyst.analyze_market_opportunity(
            market_question=q,
            current_prices={"YES": yes_p, "NO": no_p},
            context_news=news_summary_text,
            contract_rules=m.get("description", "Resolución estándar oficial")
        )

        decision = analysis.get("decision", "PASS")
        conviction = analysis.get("conviction", 0)
        rationale = analysis.get("rationale", "")
        model_used = analysis.get("model_used", "gemini")

        logger.info(f"-> Veredicto Gemini [{model_used}]: {decision} (Convicción: {conviction}/10)")

        if decision in ["BUY_YES", "BUY_NO"] and conviction >= 7:
            chosen_outcome = "Yes" if decision == "BUY_YES" else "No"
            entry_price = yes_p if decision == "BUY_YES" else no_p
            bet_amount = min(config.POLYMARKET_MAX_BET_USDC, poly_summary["cash_usdc"])

            if bet_amount >= 10.0 and entry_price > 0:
                pos = poly_paper.open_position(m, chosen_outcome, bet_amount, {
                    "category": "Análisis Gemini",
                    "headline": rationale[:180],
                    "source": f"Google {model_used}",
                    "score": conviction
                })
                if pos:
                    poly_trades_executed += 1
                    updated_summary = poly_paper.get_summary()
                    notifier.notify_polymarket_bet(
                        question=q,
                        outcome=chosen_outcome,
                        entry_price=entry_price,
                        invested_usd=bet_amount,
                        shares=pos["shares"],
                        url=pos["url"],
                        catalyst={
                            "category": f"IA Gemini ({model_used})",
                            "headline": rationale,
                            "source": f"Convicción {conviction}/10 | Ventaja: {analysis.get('edge_pct', 0)}%"
                        },
                        summary=updated_summary
                    )
                    logger.info(f"¡Posición abierta en Polymarket por ${bet_amount} USDC!")
                    break  # Abrir 1 posición por ciclo para diversificar gradualmente

    # 4. Analizar Alpaca Cripto y Acciones
    logger.info("3/4. Analizando activos en Alpaca (Cripto y Acciones)...")
    alpaca_positions = alpaca.get_open_positions()
    alpaca_summary = alpaca.get_account_summary()
    alpaca_cash = float(alpaca_summary.get("cash", 0.0))
    logger.info(f"Saldo disponible en Alpaca: ${alpaca_cash:,.2f} USD")

    # Lista de activos candidatos para evaluar (Cripto 24/7 y Acciones de Wall Street)
    candidates = ["BTC/USD", "ETH/USD", "SOL/USD", "AAPL", "NVDA", "TSLA", "MSFT", "GOOGL"]
    
    alpaca_trades_executed = 0
    for sym in candidates:
        clean_sym = sym.replace("/", "")
        # Si ya tenemos posición abierta en este activo, no sobreoperar
        if sym in alpaca_positions or clean_sym in alpaca_positions:
            logger.info(f"Posición ya existente para {sym}, se mantiene monitorización.")
            continue

        if alpaca_cash < config.RISK_PER_TRADE_USD:
            logger.info("Saldo de efectivo insuficiente para nueva posición en Alpaca.")
            break

        # Obtener precio actual y datos técnicos
        cur_price = alpaca.get_current_price(sym)
        if cur_price <= 0:
            continue

        bars = alpaca.get_bars(sym, limit=30)
        tech_data = {"current_price": cur_price}
        if not bars.empty and len(bars) >= 14:
            close = bars["close"]
            ema9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
            ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])
            tech_data.update({
                "EMA_9": round(ema9, 2),
                "EMA_21": round(ema21, 2),
                "RSI_14": round(rsi, 2),
                "trend": "Alcista" if ema9 > ema21 else "Bajista/Lateral"
            })

        logger.info(f"Consultando a Gemini para {sym} (${cur_price:,.2f})...")
        crypto_analysis = analyst.analyze_crypto_stock(
            symbol=sym,
            current_price=cur_price,
            technical_data=tech_data,
            context_news=news_summary_text
        )

        c_decision = crypto_analysis.get("decision", "HOLD")
        c_conviction = crypto_analysis.get("conviction", 0)
        c_rationale = crypto_analysis.get("rationale", "")
        c_model = crypto_analysis.get("model_used", "gemini")

        logger.info(f"-> Veredicto Gemini [{c_model}] para {sym}: {c_decision} (Convicción: {c_conviction}/10)")

        if c_decision == "BUY" and c_conviction >= 7:
            # Calcular cantidad (decimal para cripto, entero para acciones)
            is_crypto = "/" in sym
            if is_crypto:
                qty = round(config.RISK_PER_TRADE_USD / cur_price, 4)
            else:
                qty = float(max(1, int(config.RISK_PER_TRADE_USD / cur_price)))

            if qty > 0:
                logger.info(f"Ejecutando orden de compra en Alpaca para {qty} {sym}...")
                tp_pct = float(crypto_analysis.get("target_take_profit_pct", 3.0)) / 100.0
                sl_pct = float(crypto_analysis.get("target_stop_loss_pct", 1.5)) / 100.0
                
                order = alpaca.place_bracket_order(
                    symbol=sym,
                    qty=qty,
                    side="buy",
                    take_profit_pct=tp_pct,
                    stop_loss_pct=sl_pct
                )
                if order:
                    alpaca_trades_executed += 1
                    notifier.notify_order_placed(
                        symbol=sym,
                        side="buy",
                        qty=qty,
                        price=cur_price,
                        reason=f"Análisis Gemini ({c_model}) | Convicción {c_conviction}/10: {c_rationale}"
                    )
                    logger.info(f"¡Orden ejecutada con éxito en Alpaca para {sym}!")
                    break

    # 5. Reporte consolidado de cartera
    logger.info("4/4. Generando balance global consolidado...")
    final_poly = poly_paper.get_summary()
    final_alpaca = alpaca.get_account_summary()
    
    status_msg = (
        f"🤖 <b>REPORTE DE CICLO DE INTELIGENCIA (GOOGLE GEMINI)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 <b>Modelo IA Activo:</b> Google Gemini Flash (Contexto 1M tokens)\n"
        f"⚡ <b>Operaciones ejecutadas:</b> Polymarket: {poly_trades_executed} | Alpaca: {alpaca_trades_executed}\n\n"
        f"💼 <b>POLYMARKET (Paper):</b>\n"
        f"• Saldo Total: <b>${final_poly['total_equity_usdc']:,.2f} USDC</b>\n"
        f"• Efectivo Libre: ${final_poly['cash_usdc']:,.2f} USDC\n"
        f"• En Apuestas: ${final_poly['invested_usdc']:,.2f} USDC ({final_poly['active_positions_count']} activas)\n\n"
        f"📈 <b>ALPACA (Paper):</b>\n"
        f"• Saldo Total: <b>${float(final_alpaca.get('portfolio_value', 0)):,.2f} USD</b>\n"
        f"• Efectivo Libre: ${float(final_alpaca.get('cash', 0)):,.2f} USD\n"
        f"• En Inversión: ${float(final_alpaca.get('long_market_value', 0)):,.2f} USD\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <i>Monitores de riesgo activos 24/7 vigilando Take Profit y Stop Loss.</i>"
    )
    notifier.send_telegram_message(status_msg)
    logger.info("Ciclo de inteligencia completado y reporte enviado a Telegram.")


if __name__ == "__main__":
    run_cycle()
