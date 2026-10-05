"""
Motor Principal del Bot de Trading Autónomo Profesional.
- Estrategia cuantitativa en velas de 5 minutos (filtrado de ruido y falsas rupturas).
- Control de asimetría positiva: Dejar correr beneficios con ratio 2.5:1.
- Cálculo exacto de P&L real en salidas y notificaciones (solucionando el bug de +$0.00).
- Cooldown anti-sobreoperativa (15 min) para evitar entrar en bucles de consolidación.
- Detección de horario bursátil: acciones solo en horario oficial, cripto 24/7.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import logging
from datetime import datetime

import config
from alpaca_service import AlpacaService
from ai_analyst import AIAnalyst
from news_service import NewsService
from strategy import evaluate_market_data
from market_screener import scan_promising_assets, scan_futures_candidates
from notifier import (
    notify_bot_started,
    notify_order_placed,
    notify_tp_hit,
    notify_sl_hit,
    notify_dynamic_exit,
    notify_circuit_breaker_triggered,
    notify_market_reopened,
    notify_periodic_status,
    send_telegram_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TradingBot")


def format_price(price: float) -> str:
    """Formatea precios con decimales apropiados según su magnitud."""
    if price < 1.0:
        return f"${price:.4f}"
    elif price < 10.0:
        return f"${price:.3f}"
    return f"${price:.2f}"


def calculate_order_qty(symbol: str, price: float, risk_usd: float) -> float:
    """Calcula la cantidad adecuada de acciones, futuros o criptomonedas según el capital asignado."""
    if price <= 0:
        return 0.0

    clean_s = symbol.replace("/", "")
    # Si es un instrumento de futuros / materias primas / apalancado, aplicar tamaño reducido ("sin demasiado dinero")
    if clean_s in config.FUTURES_SYMBOLS:
        risk_usd = config.FUTURES_RISK_PER_TRADE_USD

    is_crypto = "/" in symbol or (symbol.endswith("USD") and len(symbol) > 4)
    if is_crypto:
        # Cripto admite decimales finos según el valor unitario
        raw_qty = risk_usd / price
        if raw_qty < 0.001:
            return round(raw_qty, 6)
        elif raw_qty < 0.1:
            return round(raw_qty, 5)
        elif raw_qty < 10.0:
            return round(raw_qty, 3)
        else:
            return round(raw_qty, 1)
    else:
        # Acciones y ETFs con órdenes bracket en Alpaca suelen requerir número entero de acciones
        qty = int(risk_usd / price)
        return float(max(1, qty))


def get_unique_positions_count(positions_dict: dict) -> int:
    """Cuenta el número de activos únicos en posiciones abiertas (evitando duplicados con y sin barra)."""
    unique_symbols = set()
    for s in positions_dict.keys():
        unique_symbols.add(s.replace("/", ""))
    return len(unique_symbols)


def get_current_equity_safe(alpaca_service):
    try:
        acc = alpaca_service.get_account_summary()
        return float(acc["portfolio_value"]), float(acc["cash"]), float(acc["invested"])
    except Exception:
        return None, None, None


def run_bot():
    print("=" * 60)
    print("      [+] INICIANDO BOT DE TRADING AUTONOMO PROFESIONAL")
    print("=" * 60)

    try:
        alpaca = AlpacaService()
    except Exception as e:
        logger.error(f"Error al conectar con Alpaca: {e}")
        logger.error("Por favor revisa tus credenciales en el archivo .env")
        return

    # Comprobación de cuenta
    try:
        account = alpaca.get_account_summary()
        logger.info(f"Conexión exitosa con Alpaca!")
        logger.info(f"Modo: {'[SIMULADOR - Paper Trading]' if account['paper'] else '[REAL - Dinero Real]'}")
        logger.info(f"Saldo en Efectivo: ${account['cash']:,.2f}")
        logger.info(f"Poder de Compra: ${account['buying_power']:,.2f}")
        logger.info(f"Valor de Portafolio: ${account['portfolio_value']:,.2f}")
        logger.info(f"Dinero Invertido: ${account['invested']:,.2f}")
        logger.info(f"Máximo de posiciones simultáneas: {config.MAX_ACTIVE_POSITIONS}")
    except Exception as e:
        logger.error(f"Fallo al obtener estado de cuenta: {e}")
        return

    analyst = AIAnalyst()
    news_service = NewsService()
    logger.info(f"Cerebro IA Activo: Google Gemini (API configurada: {analyst.is_available()})")

    # Notificar inicio a Telegram
    notify_bot_started(
        paper_mode=account["paper"],
        symbols=config.SYMBOLS,
        risk_usd=config.RISK_PER_TRADE_USD,
        total_equity=float(account["portfolio_value"]),
        cash=float(account["cash"]),
        invested=float(account["invested"])
    )

    # Registro de posiciones previas y cooldown anti-sobreoperativa
    previous_positions = {}
    cooldown_tracker = {}  # symbol -> timestamp de última salida

    # Circuito de Seguridad (Circuit Breaker)
    session_starting_equity = float(account["portfolio_value"])
    circuit_breaker_active = False
    last_heartbeat_time = time.time()

    try:
        while True:
            cycle_start = time.time()
            logger.info("-" * 50)

            # Comprobación de Circuito de Seguridad (Circuit Breaker)
            try:
                latest_acc = alpaca.get_account_summary()
                current_equity = float(latest_acc["portfolio_value"])
                current_cash = float(latest_acc["cash"])
                current_invested = float(latest_acc["invested"])
                session_drawdown = session_starting_equity - current_equity

                # Si la pérdida de sesión supera el umbral, activar pausa de emergencia
                if not circuit_breaker_active and (session_drawdown >= config.MAX_DAILY_DRAWDOWN_USD or current_equity < 99400.0):
                    circuit_breaker_active = True
                    logger.warning(
                        f"🚨 CIRCUITO DE SEGURIDAD ACTIVADO: Pérdida acumulada = ${session_drawdown:.2f} "
                        f"(Umbral máximo: ${config.MAX_DAILY_DRAWDOWN_USD:.2f}). Pausando compras..."
                    )
                    notify_circuit_breaker_triggered(
                        session_drawdown,
                        config.MAX_DAILY_DRAWDOWN_USD,
                        total_equity=current_equity,
                        cash=current_cash,
                        invested=current_invested
                    )

                # Si el circuito de seguridad está activo, esperar a la apertura de Wall Street
                if circuit_breaker_active:
                    if alpaca.is_market_open():
                        logger.info("🔔 ¡Wall Street ha abierto! Reiniciando Circuito de Seguridad y reanudando operaciones.")
                        session_starting_equity = current_equity
                        circuit_breaker_active = False
                        notify_market_reopened()
                    else:
                        logger.info(
                            f"⏸️ Bot en pausa de seguridad (Drawdown sesión: -${session_drawdown:.2f}). "
                            f"Esperando apertura de Wall Street mañana a las 15:30 (hora española)..."
                        )
                        time.sleep(60)
                        continue
            except Exception as e:
                logger.error(f"Error al verificar estado de cuenta en circuit breaker: {e}")

            is_mkt_open = alpaca.is_market_open()
            status_mkt_str = "ABIERTO" if is_mkt_open else "CERRADO (Solo Cripto 24/7)"
            logger.info(f"Escaneando mercado... [{datetime.now().strftime('%H:%M:%S')}] | Bolsa EE.UU.: {status_mkt_str}")

            # 1. Obtener posiciones actuales reales de Alpaca
            try:
                current_positions = alpaca.get_open_positions()
            except Exception as e:
                logger.error(f"Error al consultar posiciones abiertas: {e}")
                current_positions = previous_positions.copy()

            # 2. Detectar si alguna posición previa se cerró automáticamente en Alpaca (TP o SL bracket)
            for prev_sym, prev_data in list(previous_positions.items()):
                clean_sym = prev_sym.replace("/", "")
                has_active = (clean_sym in current_positions or prev_sym in current_positions)
                if not has_active:
                    entry_p = prev_data.get("avg_entry_price", 0.0)
                    qty = prev_data.get("qty", 1.0)
                    last_p = alpaca.get_latest_price(prev_sym) or prev_data.get("current_price", entry_p)

                    # Cálculo EXACTO de P&L real (soluciona el bug de +$0.00)
                    if entry_p > 0 and last_p > 0 and qty > 0:
                        real_pnl = (last_p - entry_p) * qty
                    else:
                        real_pnl = prev_data.get("unrealized_pl", 0.0)

                    logger.info(
                        f"Posición en {prev_sym} cerrada en el exchange. "
                        f"Entrada=${entry_p:.2f}, Salida=${last_p:.2f}, P&L=${real_pnl:+.2f}"
                    )

                    eq_now, cash_now, inv_now = get_current_equity_safe(alpaca)
                    if real_pnl >= 0:
                        notify_tp_hit(prev_sym, last_p, real_pnl, total_equity=eq_now, cash=cash_now, invested=inv_now)
                    else:
                        notify_sl_hit(prev_sym, last_p, real_pnl, total_equity=eq_now, cash=cash_now, invested=inv_now)

                    # Activar cooldown de 15 min en este activo
                    cooldown_tracker[prev_sym] = time.time()
                    cooldown_tracker[clean_sym] = time.time()
                    previous_positions.pop(prev_sym, None)

            # 3. GESTIÓN DE SALIDAS DINÁMICAS ("DEJAR CORRER GANANCIAS")
            active_symbols_evaluated = set()
            for symbol, pos in list(current_positions.items()):
                clean_sym = symbol.replace("/", "")
                if clean_sym in active_symbols_evaluated:
                    continue
                active_symbols_evaluated.add(clean_sym)

                pos_price_str = format_price(pos['avg_entry_price'])
                cur_price_str = format_price(pos['current_price'])
                pnl = pos['unrealized_pl']
                pnl_pct = pos['unrealized_plpc'] * 100.0

                logger.info(
                    f"[{symbol}] Posición Activa: Qty={pos['qty']} | "
                    f"Entrada={pos_price_str} | Actual={cur_price_str} | "
                    f"P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)"
                )

                # El bot vigila la posición: las órdenes bracket de Alpaca ejecutan automáticamente
                # la salida al llegar al valor esperado de subida (Take Profit) o al Stop Loss de seguridad.
                pass

            # Actualizar registro de posiciones con los datos reales de Alpaca
            previous_positions = current_positions.copy()

            # Enviar actualización periódica de estado a Telegram si han pasado HEARTBEAT_INTERVAL_MINUTES
            if time.time() - last_heartbeat_time >= config.HEARTBEAT_INTERVAL_MINUTES * 60:
                try:
                    summary = []
                    seen_s = set()
                    for sym, pos_d in current_positions.items():
                        c_s = sym.replace("/", "")
                        if c_s in seen_s:
                            continue
                        seen_s.add(c_s)
                        summary.append({
                            "symbol": sym,
                            "pnl": pos_d.get("unrealized_pl", 0.0),
                            "pnl_pct": pos_d.get("unrealized_plpc", 0.0) * 100.0,
                            "current_price": pos_d.get("current_price", 0.0)
                        })
                    eq_now, cash_now, inv_now = get_current_equity_safe(alpaca)
                    notify_periodic_status(eq_now, cash_now, inv_now, summary)
                    last_heartbeat_time = time.time()
                except Exception as e:
                    logger.error(f"Error enviando actualización periódica de estado: {e}")

            # 4. GESTIÓN DE ENTRADAS ("CUÁNDO METER CON CONFIRMACIÓN")
            active_count = get_unique_positions_count(current_positions)
            available_slots = max(0, config.MAX_ACTIVE_POSITIONS - active_count)
            logger.info(f"Posiciones activas: {active_count}/{config.MAX_ACTIVE_POSITIONS} | Huecos disponibles: {available_slots}")

            if available_slots > 0:
                if config.AUTO_DISCOVERY:
                    top_candidates = scan_promising_assets(
                        alpaca,
                        max_candidates=10,
                        include_stocks=is_mkt_open,
                        include_crypto=True
                    )
                    candidate_symbols = [c["symbol"] for c in top_candidates]
                    for s in config.SYMBOLS:
                        if s not in candidate_symbols:
                            candidate_symbols.append(s)

                    # Escáner selectivo de futuros / materias primas ("de vez en cuando sin demasiado dinero")
                    futures_active = sum(1 for s in current_positions.keys() if s.replace("/", "") in config.FUTURES_SYMBOLS)
                    if is_mkt_open and futures_active < config.MAX_FUTURES_POSITIONS:
                        futures_cand = scan_futures_candidates(alpaca)
                        if futures_cand:
                            top_future = futures_cand[0]["symbol"]
                            if top_future not in candidate_symbols:
                                logger.info(f"⚡ Oportunidad selectiva de Futuros detectada: {top_future} (+{futures_cand[0]['change_24h_pct']}%)")
                                candidate_symbols.append(top_future)
                else:
                    candidate_symbols = config.SYMBOLS

                for symbol in candidate_symbols:
                    if available_slots <= 0:
                        break

                    clean_s = symbol.replace("/", "")
                    is_crypto = "/" in symbol or (symbol.endswith("USD") and len(symbol) > 4)

                    # Si la bolsa americana está cerrada, omitir acciones
                    if not is_mkt_open and not is_crypto:
                        continue

                    # Filtro de Cooldown: evitar volver a entrar al mismo activo si acaba de salir
                    last_exit_time = cooldown_tracker.get(symbol, 0) or cooldown_tracker.get(clean_s, 0)
                    cooldown_remaining = (config.COOLDOWN_MINUTES * 60) - (time.time() - last_exit_time)
                    if cooldown_remaining > 0:
                        continue

                    # Saltar si ya tenemos posición abierta en este activo
                    if symbol in current_positions or clean_s in current_positions:
                        continue

                    # Descargar velas de 5 minutos
                    bars_df = alpaca.get_bars(symbol, limit=40)
                    if bars_df.empty or len(bars_df) < 20:
                        continue

                    price = float(bars_df["close"].iloc[-1])
                    price_str = format_price(price)

                    # Preparar métricas y velas de la gráfica para el análisis de la IA
                    close = bars_df["close"]
                    high = bars_df["high"]
                    low = bars_df["low"]
                    vol = bars_df["volume"]

                    ema9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
                    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
                    delta = close.diff()
                    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
                    rs = gain / loss
                    rsi = float((100 - (100 / (1 + rs))).iloc[-1])
                    support = float(low.tail(20).min())
                    resistance = float(high.tail(20).max())
                    avg_vol = float(vol.tail(14).mean()) if len(vol) >= 14 else 1.0
                    last_vol = float(vol.iloc[-1]) if len(vol) > 0 else 1.0

                    recent_candles = []
                    for idx, row in bars_df.tail(8).iterrows():
                        recent_candles.append({
                            "time": str(idx)[-8:],
                            "open": round(float(row["open"]), 2),
                            "high": round(float(row["high"]), 2),
                            "low": round(float(row["low"]), 2),
                            "close": round(float(row["close"]), 2),
                            "volume": int(row["volume"])
                        })

                    tech_data = {
                        "current_price": price,
                        "EMA_9": round(ema9, 2),
                        "EMA_21": round(ema21, 2),
                        "RSI_14": round(rsi, 2),
                        "support_level": round(support, 2),
                        "resistance_level": round(resistance, 2),
                        "dist_to_support_pct": round((price - support) / price * 100, 2),
                        "dist_to_resistance_pct": round((resistance - price) / price * 100, 2),
                        "volume_ratio": round(last_vol / avg_vol, 2) if avg_vol > 0 else 1.0,
                        "last_candles": recent_candles
                    }

                    # Buscar noticias y tuits en vivo
                    clean_sym_name = symbol.replace("/", "").replace("USD", "")
                    asset_news = news_service.search_live_web_and_tweets(f"{clean_sym_name} stock crypto news OR earnings OR tweet", max_items=3)
                    asset_news_text = "\n".join([f"- [{item.get('source', 'Web')}] {item.get('title', '')}" for item in asset_news])
                    context_news = f"Catalizadores en vivo para {symbol}:\n{asset_news_text or 'Sin alertas de última hora.'}"

                    # 🧠 CONSULTAR A LA IA (Google Gemini): Analiza la gráfica, predice el movimiento y toma la decisión
                    logger.info(f"🧠 Consultando a Google Gemini para {symbol} ({price_str}) - Analizando gráfica y prediciendo movimiento...")
                    ai_res = analyst.analyze_crypto_stock(
                        symbol=symbol,
                        current_price=price,
                        technical_data=tech_data,
                        context_news=context_news
                    )

                    decision = ai_res.get("decision", "HOLD")
                    conviction = ai_res.get("conviction", 0)
                    chart_prediction = ai_res.get("chart_prediction", "")
                    pattern = ai_res.get("pattern_detected", "")
                    r_r = float(ai_res.get("risk_reward_ratio", 2.0) or 2.0)
                    model_used = ai_res.get("model_used", "gemini")

                    logger.info(
                        f"[{symbol}] Veredicto IA [{model_used}]: {decision} | Convicción: {conviction}/10 | "
                        f"Patrón: {pattern} | Predicción: {chart_prediction[:80]}..."
                    )

                    # La IA es quien decide la compra basándose en su predicción técnica
                    if decision == "BUY" and conviction >= 7 and r_r >= 1.8:
                        qty = calculate_order_qty(symbol, price, config.RISK_PER_TRADE_USD)
                        if qty <= 0:
                            logger.warning(f"Cantidad calculada es 0 para {symbol} con riesgo de ${config.RISK_PER_TRADE_USD}")
                            continue

                        # Extraer valor esperado de subida y stop loss calculados por la IA
                        target_tp_price = ai_res.get("predicted_target_price")
                        target_sl_price = ai_res.get("predicted_stop_loss_price")
                        tp_pct = float(ai_res.get("target_take_profit_pct", 3.0)) / 100.0
                        sl_pct = float(ai_res.get("target_stop_loss_pct", 1.2)) / 100.0

                        logger.info(
                            f"🚀 ¡COMPRA AUTORIZADA POR LA IA PARA {symbol}! "
                            f"Predicción: {chart_prediction} | TP esperado: {target_tp_price} (+{tp_pct*100:.1f}%) | SL: {target_sl_price} (-{sl_pct*100:.1f}%)"
                        )

                        try:
                            order, tp_price, sl_price = alpaca.place_bracket_order(
                                symbol=symbol,
                                qty=qty,
                                current_price=price,
                                tp_pct=tp_pct,
                                sl_pct=sl_pct,
                                target_tp_price=target_tp_price,
                                target_sl_price=target_sl_price
                            )
                            logger.info(f"[OK] Orden bracket enviada con ID: {order.id} (Valor esperado TP={tp_price}, SL={sl_price})")
                            eq_now, cash_now, inv_now = get_current_equity_safe(alpaca)
                            notify_order_placed(
                                symbol=symbol,
                                qty=qty,
                                entry_price=price,
                                tp_price=tp_price,
                                sl_price=sl_price,
                                total_equity=eq_now,
                                cash=cash_now,
                                invested=inv_now,
                                ai_prediction=chart_prediction,
                                pattern=pattern,
                                reason=ai_res.get("rationale")
                            )

                            # Registrar posición localmente
                            pos_data = {
                                "qty": qty,
                                "avg_entry_price": price,
                                "current_price": price,
                                "unrealized_pl": 0.0,
                                "unrealized_plpc": 0.0,
                                "target_tp_price": tp_price,
                                "target_sl_price": sl_price,
                                "ai_prediction": chart_prediction
                            }
                            current_positions[symbol] = pos_data
                            current_positions[clean_s] = pos_data
                            previous_positions[symbol] = pos_data
                            previous_positions[clean_s] = pos_data
                            available_slots -= 1
                            logger.info(f"Huecos restantes disponibles para nuevas compras: {available_slots}")
                            break
                        except Exception as e:
                            logger.error(f"Error al enviar orden bracket para {symbol}: {e}")

            # 5. Esperar antes del siguiente ciclo
            elapsed = time.time() - cycle_start
            wait_time = max(1, config.CHECK_INTERVAL_SECONDS - int(elapsed))
            logger.info(f"Ciclo completado. Esperando {wait_time}s antes del próximo escaneo...")
            time.sleep(wait_time)

    except KeyboardInterrupt:
        logger.info("\nBot detenido manualmente por el usuario. Las órdenes bracket activas continúan protegidas en Alpaca.")
        send_telegram_message("🛑 <b>Bot de Trading detenido</b> manualmente.")
    except Exception as e:
        logger.critical(f"Error inesperado en el bucle principal: {e}", exc_info=True)


if __name__ == "__main__":
    run_bot()
