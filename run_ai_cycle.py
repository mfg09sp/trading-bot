"""
Ciclo Unificado de Inteligencia Artificial (Polymarket + Alpaca Cripto y Acciones).
Utiliza Google Gemini (con la API Key del usuario) para analizar de forma exhaustiva
noticias, tuits, probabilidades de Polymarket y setups técnicos en Alpaca.
"""

from __future__ import annotations
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
from super_investor_service import SuperInvestorService
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

    # 1.6. Evaluar salidas de posiciones abiertas en Alpaca (Take Profit / Stop Loss / ±$50)
    logger.info("Evaluando Take Profit y Stop Loss de posiciones de Alpaca (Bolsa y Cripto)...")
    try:
        alpaca_positions_check = alpaca.get_open_positions()
        alp_summary = alpaca.get_account_summary()
        current_eq = float(alp_summary.get("portfolio_value", 0.0))
        current_cash = float(alp_summary.get("cash", 0.0))
        current_inv = float(alp_summary.get("long_market_value", 0.0))

        for sym, pos in list(alpaca_positions_check.items()):
            clean_sym = sym.replace("/", "").upper()
            if clean_sym in config.LONG_TERM_SYMBOLS:
                # Activo de cartera a largo plazo (Buy & Hold): Sin Stop Loss ni Take Profit
                continue

            cur_p = pos.get("current_price", 0.0)
            entry_p = pos.get("avg_entry_price", cur_p)
            qty = pos.get("qty", 0.0)
            pnl = pos.get("unrealized_pl", 0.0)
            pnl_pct = pos.get("unrealized_plpc", 0.0)

            is_crypto = "/" in sym or (sym.endswith("USD") and len(sym) > 4)
            tp_pct_thresh = 0.060 if is_crypto else 0.055  # +6.0% cripto, +5.5% acciones
            sl_pct_thresh = -0.035 if is_crypto else -0.028 # -3.5% cripto, -2.8% acciones (margen profesional para swing trading)

            should_close = False
            is_tp = False

            # Venta por Take Profit al valor esperado de subida (ej. >= +2.5% acciones / +3.0% cripto)
            if pnl_pct >= tp_pct_thresh:
                should_close = True
                is_tp = True
            # Venta por Stop Loss de protección (ej. <= -1.0% acciones / -1.5% cripto)
            elif pnl_pct <= sl_pct_thresh:
                should_close = True
                is_tp = False

            if should_close and cur_p > 0:
                logger.info(f"[{sym}] Activando salida de riesgo en Alpaca ({'Take Profit (Valor Esperado Alcanzado)' if is_tp else 'Stop Loss'}). P&L: ${pnl:+.2f}")
                res = alpaca.close_position(sym)
                if res:
                    time.sleep(1)
                    if is_tp:
                        notifier.notify_tp_hit(sym, cur_p, pnl, total_equity=current_eq, cash=current_cash, invested=current_inv)
                    else:
                        notifier.notify_sl_hit(sym, cur_p, pnl, total_equity=current_eq, cash=current_cash, invested=current_inv)
    except Exception as e:
        logger.error(f"Error evaluando salidas en Alpaca: {e}")

    # 2. Recopilar contexto informativo masivo (Noticias, RSS, Tuits, Macro)
    logger.info("1/4. Recopilando noticias de Trump, Elon Musk, Fed, Cripto e IA...")
    catalysts = news_service.get_latest_catalysts()
    all_news = []
    for cat, items in catalysts.items():
        for item in items:
            all_news.append(f"- [{cat.upper()}] {item.get('title', '')} (Fuente: {item.get('source', 'Web')})")
    
    news_summary_text = "\n".join(all_news[:25])
    logger.info(f"Se recopilaron {len(all_news)} catalizadores informativos.")

    # 3. Analizar Polymarket con rastreo profundo de anomalías matemáticas (1X2 Deportes, Longshots, Desfase)
    logger.info("2/4. Escaneando anomalías cuantitativas en Polymarket (Regla 1X2, Longshots, Ineficiencias)...")
    poly_summary = poly_paper.get_summary()
    markets = poly_service.get_anomaly_candidate_markets(limit_total=30)
    active_poly_ids = set(poly_paper.data.get("active_positions", {}).keys())
    # Evaluar hasta 12 candidatos con mayor puntuación de anomalía
    unheld_markets = [m for m in markets if m.get("id") not in active_poly_ids][:12]
    
    poly_trades_executed = 0
    available_poly_cash = float(poly_summary.get("cash_usdc", 0.0))

    for m in unheld_markets:
        # Si ya alcanzamos el límite de posiciones o no hay saldo suficiente (mínimo $50 USDC)
        if available_poly_cash < 50.0 or not poly_paper.can_open_position(50.0):
            logger.info("Saldo en Polymarket inferior al mínimo de $50 USDC o límite de posiciones alcanzado.")
            break

        m_id = m.get("id")

        q = m.get("question", "")
        prices = m.get("prices", {})
        yes_p = prices.get("Yes", 0.0)
        no_p = prices.get("No", 0.0)

        # Filtrar mercados ilíquidos
        if (yes_p < 0.05 or yes_p > 0.95) and (no_p < 0.05 or no_p > 0.95):
            continue

        anomaly_tags_str = ", ".join(m.get("anomaly_tags", ["Análisis Cuantitativo"]))

        # Investigar tuits, declaraciones y noticias específicas en vivo para esta pregunta
        targeted_news = news_service.search_live_web_and_tweets(q, max_items=5)
        targeted_text = "\n".join([f"- [{item.get('source', 'Web')}] {item.get('title', '')} ({item.get('pub_date', '')})" for item in targeted_news])
        combined_context = (
            f"=== ANOMALÍAS DETECTADAS POR EL SCANNER ===\n{anomaly_tags_str}\n\n"
            f"=== TUITS Y NOTICIAS EN VIVO PARA ESTA PREGUNTA ===\n{targeted_text or 'Sin menciones específicas en los últimos minutos.'}\n\n"
            f"=== CONTEXTO GLOBAL Y REDES (TRUMP, ELON MUSK, MACRO, CRIPTO) ===\n{news_summary_text}"
        )

        logger.info(f"Consultando a Gemini para Polymarket: {q[:60]}... (Yes: ${yes_p:.3f}, No: ${no_p:.3f}) [Anomalía: {anomaly_tags_str}]")
        
        # Consultar Gemini con contexto enriquecido en vivo
        analysis = analyst.analyze_market_opportunity(
            market_question=q,
            current_prices={"YES": yes_p, "NO": no_p},
            context_news=combined_context,
            contract_rules=m.get("description", "Resolución estándar oficial")
        )

        decision = analysis.get("decision", "PASS")
        conviction = analysis.get("conviction", 0)
        rationale = analysis.get("rationale", "")
        model_used = analysis.get("model_used", "gemini")
        anomaly_detected = analysis.get("anomaly_type", anomaly_tags_str)

        logger.info(f"-> Veredicto Gemini [{model_used}]: {decision} (Convicción: {conviction}/10 | Anomalía: {anomaly_detected})")

        if decision in ["BUY_YES", "BUY_NO"] and conviction >= 7:
            chosen_outcome = "Yes" if decision == "BUY_YES" else "No"
            entry_price = yes_p if decision == "BUY_YES" else no_p
            bet_amount = min(config.POLYMARKET_MAX_BET_USDC, available_poly_cash)

            if bet_amount >= 10.0 and entry_price > 0:
                pos = poly_paper.open_position(m, chosen_outcome, bet_amount, {
                    "category": f"Anomalía: {anomaly_detected[:30]}",
                    "headline": rationale[:180],
                    "source": f"Google {model_used}",
                    "score": conviction
                })
                if pos:
                    poly_trades_executed += 1
                    available_poly_cash = max(0.0, available_poly_cash - bet_amount)
                    updated_summary = poly_paper.get_summary()
                    notifier.notify_polymarket_bet(
                        question=q,
                        outcome=chosen_outcome,
                        entry_price=entry_price,
                        invested_usd=bet_amount,
                        shares=pos["shares"],
                        url=pos["url"],
                        catalyst={
                            "category": f"IA Gemini [{anomaly_detected}]",
                            "headline": rationale,
                            "source": f"Convicción {conviction}/10 | Ventaja: {analysis.get('edge_pct', 0)}%"
                        },
                        summary=updated_summary
                    )
                    logger.info(f"¡Posición abierta en Polymarket por ${bet_amount} USDC!")
                    if poly_trades_executed >= 2:
                        break  # Hasta 2 posiciones de alta convicción por ciclo para diversificar gradualmente

    # 4. Analizar Alpaca Cripto y Acciones con Radar de Super Inversores
    logger.info("3/4. Analizando activos en Alpaca (Super Inversores + Cripto 24/7)...")
    alpaca_positions = alpaca.get_open_positions()
    alpaca_summary = alpaca.get_account_summary()
    alpaca_cash = float(alpaca_summary.get("cash", 0.0))
    logger.info(f"Saldo disponible en Alpaca: ${alpaca_cash:,.2f} USD")

    super_investor_svc = SuperInvestorService(news_service=news_service)
    super_inv_cands = super_investor_svc.get_super_investor_candidates()
    super_inv_map = {c["symbol"]: c for c in super_inv_cands}

    # Fusión de activos: Criptomonedas líquidas + Acciones de Super Inversores + Megacaps
    crypto_candidates = ["BTC/USD", "ETH/USD", "SOL/USD", "DOGE/USD", "AVAX/USD", "LINK/USD"]
    super_inv_symbols = [c["symbol"] for c in super_inv_cands[:12]]
    core_megacaps = ["NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AMD", "PLTR", "COIN", "NFLX", "AVGO", "ARM", "SMCI", "UBER"]

    candidates = []
    seen_syms = set()
    for s in crypto_candidates + super_inv_symbols + core_megacaps:
        if s not in seen_syms:
            seen_syms.add(s)
            candidates.append(s)
    
    alpaca_trades_executed = 0
    ai_insights: List[str] = []
    for sym in candidates:
        clean_sym = sym.replace("/", "").upper()
        # Omitir activos de cartera a largo plazo (Buy & Hold)
        if clean_sym in config.LONG_TERM_SYMBOLS:
            continue

        # Si ya tenemos posición abierta en este activo, no sobreoperar
        if sym in alpaca_positions or clean_sym in alpaca_positions:
            logger.info(f"Posición ya existente para {sym}, se mantiene monitorización.")
            continue

        if alpaca_cash < config.RISK_PER_TRADE_USD:
            logger.info("Saldo de efectivo insuficiente para nueva posición en Alpaca.")
            break

        # Obtener precio actual y datos técnicos
        cur_price = alpaca.get_latest_price(sym) or alpaca.get_current_price(sym) or 0.0
        if cur_price <= 0:
            continue

        bars = alpaca.get_bars(sym, limit=30)
        tech_data = {"current_price": cur_price}
        if not bars.empty and len(bars) >= 14:
            close = bars["close"]
            high = bars["high"]
            low = bars["low"]
            vol = bars["volume"]

            ema9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
            ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            support = float(low.tail(20).min())
            resistance = float(high.tail(20).max())
            dist_support_pct = round((cur_price - support) / cur_price * 100, 2)
            dist_resist_pct = round((resistance - cur_price) / cur_price * 100, 2)
            avg_vol = float(vol.tail(14).mean()) if len(vol) >= 14 else 1.0
            last_vol = float(vol.iloc[-1]) if len(vol) > 0 else 1.0
            vol_ratio = round(last_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            # Detección algorítmica de patrones chartistas
            detected_patterns = []
            if ema9 > ema21 and close.iloc[-1] > ema9:
                detected_patterns.append("Cruce alcista EMA9/EMA21 con Momentum")
            if rsi < 38 and dist_support_pct < 1.5:
                detected_patterns.append("Rebote en Soporte Clave con RSI en Sobreventa")
            if cur_price >= resistance * 0.995 and vol_ratio > 1.2:
                detected_patterns.append("Ruptura Alcista de Resistencia (Breakout con Volumen)")
            if not detected_patterns:
                detected_patterns.append("Rango de Consolidación Lateral")

            tech_data.update({
                "EMA_9": round(ema9, 2),
                "EMA_21": round(ema21, 2),
                "RSI_14": round(rsi, 2),
                "trend": "Alcista" if ema9 > ema21 else "Bajista/Lateral",
                "support_level": round(support, 2),
                "resistance_level": round(resistance, 2),
                "dist_to_support_pct": dist_support_pct,
                "dist_to_resistance_pct": dist_resist_pct,
                "volume_expansion_ratio": vol_ratio,
                "algorithmic_patterns": detected_patterns,
                "minimum_profitability_target": "Ratio Riesgo/Beneficio >= 2.0"
            })

        # Búsqueda en vivo de tuits y noticias específicas del activo
        clean_sym_name = sym.replace("/", "").replace("USD", "")
        asset_news = news_service.search_live_web_and_tweets(f"{clean_sym_name} stock crypto news OR earnings OR tweet", max_items=4)
        asset_news_text = "\n".join([f"- [{item.get('source', 'Web')}] {item.get('title', '')} ({item.get('pub_date', '')})" for item in asset_news])
        alpaca_context = f"=== TUITS Y NOTICIAS EN VIVO DE {sym} ===\n{asset_news_text or 'Sin alertas de última hora.'}\n\n=== CONTEXTO MACRO Y REDES ===\n{news_summary_text}"

        super_inv_data = super_inv_map.get(clean_sym)
        super_inv_tag = f" [Super Inversor: {', '.join(super_inv_data['investors'][:2])}]" if super_inv_data else ""
        logger.info(f"Consultando a Gemini para {sym} (${cur_price:,.2f}){super_inv_tag} con análisis técnico algorítmico y tuits...")
        crypto_analysis = analyst.analyze_crypto_stock(
            symbol=sym,
            current_price=cur_price,
            technical_data=tech_data,
            context_news=alpaca_context,
            super_investor_data=super_inv_data
        )

        c_decision = crypto_analysis.get("decision", "HOLD")
        c_conviction = crypto_analysis.get("conviction", 0)
        c_rationale = crypto_analysis.get("rationale", "")
        c_model = crypto_analysis.get("model_used", "gemini")

        logger.info(f"-> Veredicto Gemini [{c_model}] para {sym}: {c_decision} (Convicción: {c_conviction}/10)")

        r_r = float(crypto_analysis.get("risk_reward_ratio", 2.0) or 2.0)
        pattern_detected = crypto_analysis.get("pattern_detected", "Patrón Cuantitativo")
        profitability = crypto_analysis.get("profitability_assessment", "")
        inv_label = f" (🐳 {', '.join(super_inv_data['investors'][:1])})" if super_inv_data else ""

        ai_insights.append(f"• <b>{sym}{inv_label}:</b> {c_decision} (Convicción {c_conviction}/10) | {pattern_detected}")

        if c_decision == "BUY" and c_conviction >= 7 and r_r >= 1.8:
            # Calcular cantidad (decimal para cripto, entero para acciones)
            is_crypto = "/" in sym
            if is_crypto:
                qty = round(config.RISK_PER_TRADE_USD / cur_price, 4)
            else:
                qty = float(max(1, int(config.RISK_PER_TRADE_USD / cur_price)))

            if qty > 0:
                logger.info(f"Ejecutando orden de compra en Alpaca para {qty} {sym} (Patrón: {pattern_detected}, R:R: {r_r}:1)...")
                target_tp_price = crypto_analysis.get("predicted_target_price")
                target_sl_price = crypto_analysis.get("predicted_stop_loss_price")
                chart_pred = crypto_analysis.get("chart_prediction", "")
                tp_pct = float(crypto_analysis.get("target_take_profit_pct", 6.0 if is_crypto else 5.5)) / 100.0
                sl_pct = float(crypto_analysis.get("target_stop_loss_pct", 3.5 if is_crypto else 2.8)) / 100.0
                
                order, tp_price, sl_price = alpaca.place_bracket_order(
                    symbol=sym,
                    qty=qty,
                    current_price=cur_price,
                    tp_pct=tp_pct,
                    sl_pct=sl_pct,
                    target_tp_price=target_tp_price,
                    target_sl_price=target_sl_price
                )
                if order:
                    alpaca_trades_executed += 1
                    notifier.notify_order_placed(
                        symbol=sym,
                        qty=qty,
                        entry_price=cur_price,
                        tp_price=tp_price,
                        sl_price=sl_price,
                        total_equity=current_eq,
                        cash=current_cash,
                        invested=current_inv,
                        ai_prediction=chart_pred,
                        pattern=pattern_detected,
                        reason=c_rationale
                    )
                    logger.info(f"¡Orden ejecutada con éxito en Alpaca para {sym}! TP={tp_price}, SL={sl_price}")
                    if alpaca_trades_executed >= 2:
                        break

    # 5. Reporte consolidado de cartera con radar de riesgo y análisis de IA
    logger.info("4/4. Generando balance global consolidado y radar de riesgo...")
    final_poly = poly_paper.get_summary()
    final_alpaca = alpaca.get_account_summary()
    alpaca_open_pos = alpaca.get_open_positions()

    # Construir Radar en vivo de Stop Loss y Take Profit
    risk_radar_lines = []
    seen_radar_syms = set()
    for sym, pos_data in alpaca_open_pos.items():
        cs = sym.replace("/", "").upper()
        if cs in seen_radar_syms:
            continue
        seen_radar_syms.add(cs)

        cur_p = float(pos_data.get("current_price", 0.0))
        entry_p = float(pos_data.get("avg_entry_price", cur_p))
        pnl = float(pos_data.get("unrealized_pl", 0.0))
        pnl_pct = float(pos_data.get("unrealized_plpc", 0.0)) * 100.0

        if cs in config.LONG_TERM_SYMBOLS:
            risk_radar_lines.append(f"• <b>{sym}:</b> {pnl_pct:+.2f}% 🛡️ <i>(Inversión Largo Plazo blindada sin SL)</i>")
        else:
            is_crypto = "/" in sym or (sym.endswith("USD") and len(sym) > 4)
            tp_thresh = 6.0 if is_crypto else 5.5
            sl_thresh = -3.5 if is_crypto else -2.8
            tp_price_val = entry_p * (1.0 + tp_thresh / 100.0)
            sl_price_val = entry_p * (1.0 + sl_thresh / 100.0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            risk_radar_lines.append(
                f"• <b>{sym}:</b> {pnl_pct:+.2f}% {emoji} (a ${cur_p:,.2f})\n"
                f"   🎯 TP: ${tp_price_val:,.2f} (+{tp_thresh:.1f}%) | 🛑 SL: ${sl_price_val:,.2f} ({sl_thresh:.1f}%)"
            )

    # Posición destacada de Polymarket en el radar
    poly_radar_lines = []
    for mid, p_data in poly_paper.data.get("active_positions", {}).items():
        if p_data.get("no_stop_loss"):
            pnl_pct = float(p_data.get("unrealized_pnl_pct", 0.0))
            poly_radar_lines.append(f"• <b>Pedro Sánchez (YES):</b> {pnl_pct:+.1f}% 🛡️ <i>(Blindado sin SL hasta elecciones)</i>")

    # Radar de Super Inversores (Pelosi, Buffett, Druckenmiller, Insiders)
    super_radar_lines = []
    for c in super_inv_cands[:4]:
        s_sym = c["symbol"]
        inv_names = ", ".join(c["investors"][:2])
        super_radar_lines.append(f"• <b>{s_sym}:</b> 🐳 {inv_names}")
    super_radar_block = "\n".join(super_radar_lines)

    risk_radar_block = "\n".join(risk_radar_lines[:8])
    poly_radar_block = "\n".join(poly_radar_lines)
    ai_block = "\n".join(ai_insights[:5]) if ai_insights else "• Vigilancia técnica de posiciones abiertas dentro de parámetros normales."

    total_combined_eq = float(final_alpaca.get("portfolio_value", 0)) + float(final_poly.get("total_equity_usdc", 0))

    action_summary = "💤 Sin operaciones nuevas (posiciones en rango normal)."
    if poly_trades_executed > 0 or alpaca_trades_executed > 0:
        action_summary = f"🚀 <b>Nuevas operaciones ejecutadas:</b> Polymarket: {poly_trades_executed} | Alpaca: {alpaca_trades_executed}"

    status_msg = (
        f"🤖 <b>REPORTE DE CICLO IA (GOOGLE GEMINI 24/7)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>CAPITAL COMBINADO:</b> <code>${total_combined_eq:,.2f} USD</code>\n"
        f"{action_summary}\n\n"
        f"🐳 <b>RADAR DE SUPER INVERSORES (PELOSI, BUFFETT & WHALES):</b>\n"
        f"{super_radar_block}\n\n"
        f"🎯 <b>RADAR DE SALIDAS (STOP LOSS Y TAKE PROFIT):</b>\n"
        f"{risk_radar_block}\n"
        f"{poly_radar_block}\n\n"
        f"🧠 <b>ANÁLISIS DE LA IA ESTE CICLO:</b>\n"
        f"{ai_block}\n"
        f"📰 <i>Catalizadores macro: {len(all_news)} noticias y tuits analizados.</i>\n\n"
        f"💼 <b>SALDOS EN TIEMPO REAL:</b>\n"
        f"• <b>Alpaca:</b> ${float(final_alpaca.get('portfolio_value', 0)):,.2f} USD (Libre: ${float(final_alpaca.get('cash', 0)):,.2f})\n"
        f"• <b>Polymarket:</b> ${final_poly['total_equity_usdc']:,.2f} USDC (Libre: ${final_poly['cash_usdc']:,.2f})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Escribe /estado o 'como va' para el desglose completo.</i>"
    )
    notifier.send_telegram_message(status_msg)
    logger.info("Ciclo de inteligencia completado y reporte enviado a Telegram.")


if __name__ == "__main__":
    run_cycle()
