"""
Módulo de Notificaciones.
Envía alertas y resúmenes de operaciones a Telegram y la consola.
"""

import sys
import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

logger = logging.getLogger("Notifier")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)


def send_telegram_message(message: str) -> bool:
    """
    Envía un mensaje de texto a través del bot de Telegram.
    Devuelve True si se envió con éxito, False en caso contrario.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("[Telegram omitido] Alerta solo en consola (configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env si deseas recibir avisos en el móvil).")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
        if response.status_code == 200:
            logger.info("Aviso enviado con éxito a Telegram.")
            return True
        elif response.status_code == 400:
            # Reintentar en texto plano si Telegram rechaza etiquetas o caracteres como < o >
            payload_plain = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
            }
            res_plain = requests.post(url, json=payload_plain, timeout=8)
            if res_plain.status_code == 200:
                logger.info("Aviso enviado con éxito a Telegram (modo texto plano).")
                return True
            logger.error(f"Error reintentando en texto plano: {res_plain.status_code} - {res_plain.text}")
        else:
            logger.error(f"Error al enviar mensaje a Telegram: {response.status_code} - {response.text}")
        return False
    except Exception as e:
        logger.error(f"Excepción de conexión al enviar mensaje a Telegram: {e}")
        return False


def _fmt(val: float) -> str:
    if abs(val) < 1.0:
        return f"${val:.4f}"
    elif abs(val) < 10.0:
        return f"${val:.3f}"
    return f"${val:.2f}"


def _equity_footer(total_equity: float = None, cash: float = None, invested: float = None) -> str:
    if total_equity is not None:
        lines = []
        if invested is not None:
            lines.append(f"📊 <b>Dinero Invertido:</b> ${invested:,.2f}")
        if cash is not None:
            lines.append(f"💵 <b>En Cartera (Efectivo):</b> ${cash:,.2f}")
        lines.append(f"💼 <b>Total de tu Dinero:</b> ${total_equity:,.2f}")
        return "\n".join(lines) + "\n"
    return ""


def notify_bot_started(paper_mode: bool, symbols: list, risk_usd: float, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    mode_str = "SIMULADOR (Paper Trading 100k$)" if paper_mode else "REAL (Dinero Real)"
    footer = _equity_footer(total_equity, cash, invested)
    footer_block = f"━━━━━━━━━━━━━━━━━━\n{footer}" if footer else ""
    msg = (
        f"🤖 <b>Bot de Trading Autónomo Iniciado</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<b>Entorno:</b> {mode_str}\n"
        f"<b>Activos en vigilancia:</b> {', '.join(symbols)}\n"
        f"<b>Riesgo por operación:</b> ${risk_usd:.2f}\n"
        f"{footer_block}"
        f"<b>Estado:</b> Monitoreando mercado activamente..."
    )
    logger.info(f"[NOTIFICACIÓN] Bot iniciado en modo {mode_str}")
    send_telegram_message(msg)


def notify_order_placed(symbol: str, qty: float, entry_price: float, tp_price: float, sl_price: float, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    profit_pct = ((tp_price - entry_price) / entry_price) * 100
    loss_pct = ((entry_price - sl_price) / entry_price) * 100
    qty_str = f"{qty:.6f}".rstrip("0").rstrip(".") if qty < 1 else f"{qty:.2f}"
    footer = _equity_footer(total_equity, cash, invested)
    footer_str = f"{footer}━━━━━━━━━━━━━━━━━━\n" if footer else ""
    msg = (
        f"🚀 <b>NUEVA ORDEN EJECUTADA: {symbol}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Acción:</b> COMPRA (Long)\n"
        f"🔹 <b>Cantidad:</b> {qty_str}\n"
        f"🔹 <b>Precio Entrada:</b> {_fmt(entry_price)}\n"
        f"🎯 <b>Take Profit:</b> {_fmt(tp_price)} (+{profit_pct:.1f}%)\n"
        f"🛑 <b>Stop Loss:</b> {_fmt(sl_price)} (-{loss_pct:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer_str}"
        f"<i>Orden bracket vinculada y protegida en el exchange.</i>"
    )
    logger.info(f"[NOTIFICACIÓN] Orden compra enviada en {symbol} - TP: {_fmt(tp_price)}, SL: {_fmt(sl_price)}")
    send_telegram_message(msg)


def notify_tp_hit(symbol: str, exit_price: float, pnl_usd: float, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    footer = _equity_footer(total_equity, cash, invested)
    footer_str = f"━━━━━━━━━━━━━━━━━━\n{footer}" if footer else ""
    msg = (
        f"🎯 <b>OBJETIVO ALCANZADO (Take Profit)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Activo:</b> {symbol}\n"
        f"✅ <b>Precio de Cierre:</b> {_fmt(exit_price)}\n"
        f"💰 <b>Ganancia Asegurada:</b> +${pnl_usd:.2f}\n"
        f"{footer_str}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Posición cerrada con éxito. Beneficio consolidado.</i>"
    )
    logger.info(f"[NOTIFICACIÓN] TP Alcanzado en {symbol} (+${pnl_usd:.2f})")
    send_telegram_message(msg)


def notify_sl_hit(symbol: str, exit_price: float, pnl_usd: float, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    footer = _equity_footer(total_equity, cash, invested)
    footer_str = f"━━━━━━━━━━━━━━━━━━\n{footer}" if footer else ""
    msg = (
        f"🛑 <b>PROTECCIÓN ACTIVADA (Stop Loss)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Activo:</b> {symbol}\n"
        f"⚠️ <b>Precio de Cierre:</b> {_fmt(exit_price)}\n"
        f"📉 <b>Pérdida Cortada:</b> -${abs(pnl_usd):.2f}\n"
        f"{footer_str}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Posición cortada para proteger el capital.</i>"
    )
    logger.info(f"[NOTIFICACIÓN] SL Activado en {symbol} (-${abs(pnl_usd):.2f})")
    send_telegram_message(msg)


def notify_dynamic_exit(symbol: str, exit_price: float, pnl_usd: float, reason: str, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    sign = "+" if pnl_usd >= 0 else "-"
    emoji = "💰" if pnl_usd >= 0 else "🛡️"
    title = "CIERRE DINÁMICO (Toma de Beneficios)" if pnl_usd >= 0 else "SALIDA TÉCNICA (Protección de Capital)"
    footer = _equity_footer(total_equity, cash, invested)
    footer_str = f"{footer}━━━━━━━━━━━━━━━━━━\n" if footer else ""
    msg = (
        f"{emoji} <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Activo:</b> {symbol}\n"
        f"🔹 <b>Precio de Salida:</b> {_fmt(exit_price)}\n"
        f"🔹 <b>Resultado P&L:</b> {sign}${abs(pnl_usd):.2f}\n"
        f"🔹 <b>Motivo:</b> {reason}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer_str}"
        f"<i>El bot cerró la posición para optimizar ganancias o evitar retrocesos.</i>"
    )
    logger.info(f"[NOTIFICACIÓN] Salida dinámica en {symbol} ({sign}${abs(pnl_usd):.2f}) - {reason}")
    send_telegram_message(msg)


def notify_circuit_breaker_triggered(loss_amount: float, limit_amount: float, total_equity: float = None, cash: float = None, invested: float = None) -> None:
    footer = _equity_footer(total_equity, cash, invested)
    footer_str = f"{footer}━━━━━━━━━━━━━━━━━━\n" if footer else ""
    msg = (
        f"🚨 <b>CIRCUITO DE SEGURIDAD ACTIVADO (Circuit Breaker)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>Límite de pérdida de sesión alcanzado:</b> -${abs(loss_amount):.2f}\n"
        f"🛡️ <b>Umbral de protección:</b> ${limit_amount:.2f}\n"
        f"🛑 <b>Acción:</b> Nuevas operaciones pausadas automáticamente para blindar tu capital.\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer_str}"
        f"⏳ <b>Reanudación:</b> En espera de la apertura de Wall Street a las 15:30 (hora española)."
    )
    logger.warning(f"[CIRCUIT BREAKER] Pausa de seguridad activada. Pérdida: ${loss_amount:.2f}")
    send_telegram_message(msg)


def notify_market_reopened() -> None:
    msg = (
        f"🔔 <b>¡APERTURA DE MERCADO DE WALL STREET!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 La bolsa de EE.UU. acaba de abrir sus puertas.\n"
        f"🚀 El bot reanuda operaciones normales en acciones (SPY, QQQ, NVDA, TSLA...) y criptomonedas."
    )
    logger.info("[MERCADO ABIERTO] Wall Street abierto. Reanudando operativa normal.")
    send_telegram_message(msg)


def notify_periodic_status(total_equity: float, cash: float, invested: float, positions_summary: list) -> None:
    """Envía un resumen de latido para que el usuario sepa que el bot sigue activo y cómo van sus posiciones."""
    pos_lines = []
    for p in positions_summary:
        sym = p.get("symbol", "")
        pnl = p.get("pnl", 0.0)
        pnl_pct = p.get("pnl_pct", 0.0)
        cur_p = p.get("current_price", 0.0)
        sign = "+" if pnl >= 0 else ""
        emoji = "🟢" if pnl >= 0 else "🔴"
        pos_lines.append(f"{emoji} <b>{sym}:</b> {_fmt(cur_p)} | {sign}${pnl:.2f} ({sign}{pnl_pct:.2f}%)")

    pos_text = "\n".join(pos_lines) if pos_lines else "• Sin posiciones activas en este momento"
    footer = _equity_footer(total_equity, cash, invested)

    msg = (
        f"⏱️ <b>ESTADO DE MERCADO (Bot Activo)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👀 <b>Posiciones en vigilancia:</b>\n"
        f"{pos_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer}"
        f"<i>El bot continúa analizando el mercado cada 60s.</i>"
    )
    logger.info("[NOTIFICACIÓN] Enviando actualización periódica de estado a Telegram.")
    send_telegram_message(msg)


def notify_polymarket_bet(
    question: str,
    outcome: str,
    entry_price: float,
    invested_usd: float,
    shares: float,
    url: str,
    catalyst: dict,
    summary: dict
) -> None:
    """Notifica la apertura de una posición simulada en Polymarket."""
    cat_text = ""
    if catalyst and catalyst.get("headline"):
        cat_text = (
            f"📰 <b>Catalizador detectado (Noticia / Redes):</b>\n"
            f"• <i>{catalyst.get('headline')}</i>\n"
            f"• Fuente: {catalyst.get('source', 'Web')} | Categoría: {catalyst.get('category', 'Actualidad')}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

    prob_pct = entry_price * 100.0
    msg = (
        f"🔮 <b>NUEVA APUESTA POLYMARKET (Paper Trading)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Mercado:</b> {question}\n"
        f"🎯 <b>Predicción:</b> <b>{outcome.upper()}</b> ({prob_pct:.1f}% prob. | ${_fmt(entry_price)})\n"
        f"💵 <b>Inversión:</b> ${invested_usd:.2f} USDC ({shares:.1f} contratos)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{cat_text}"
        f"📊 <b>Estado Cartera Polymarket:</b>\n"
        f"• En apuestas activas: ${summary.get('invested_usdc', 0.0):.2f} USDC\n"
        f"• En cartera (efectivo libre): ${summary.get('cash_usdc', 0.0):.2f} USDC\n"
        f"• 💼 <b>Total Cartera:</b> ${summary.get('total_equity_usdc', 0.0):.2f} USDC\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <a href=\"{url}\">Ver mercado en Polymarket</a>"
    )
    logger.info(f"[TELEGRAM POLYMARKET] Notificando apuesta en '{question}' ({outcome})")
    send_telegram_message(msg)


def notify_polymarket_close(
    trade: dict,
    summary: dict
) -> None:
    """Notifica el cierre de una posición en Polymarket (Take Profit, Stop Loss o Resolución)."""
    pnl = trade.get("realized_pnl", 0.0)
    pnl_pct = trade.get("realized_pnl_pct", 0.0)
    sign = "+" if pnl >= 0 else ""
    emoji = "🟢" if pnl >= 0 else "🔴"
    close_reason = trade.get("close_reason", "Cierre")

    msg = (
        f"🏁 <b>CIERRE EN POLYMARKET: {close_reason}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Mercado:</b> {trade.get('question', '')}\n"
        f"🎯 <b>Opción:</b> {trade.get('outcome', '').upper()} (Entrada: ${_fmt(trade.get('entry_price', 0.0))} ➔ Salida: ${_fmt(trade.get('exit_price', 0.0))})\n"
        f"{emoji} <b>Resultado:</b> <b>{sign}${pnl:.2f} USDC</b> ({sign}{pnl_pct:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Estado Cartera Polymarket:</b>\n"
        f"• En cartera (efectivo): ${summary.get('cash_usdc', 0.0):.2f} USDC\n"
        f"• 💼 <b>Total Cartera:</b> ${summary.get('total_equity_usdc', 0.0):.2f} USDC\n"
        f"• Historial: 🏆 {summary.get('win_count', 0)} aciertos | ❌ {summary.get('loss_count', 0)} fallos\n"
        f"• P&L Acumulado: {sign}${summary.get('realized_pnl_usdc', 0.0):.2f} USDC"
    )
    logger.info(f"[TELEGRAM POLYMARKET CIERRE] {close_reason}: {sign}${pnl:.2f}")
    send_telegram_message(msg)


def notify_alpaca_ai_trade(
    symbol: str,
    action: str,
    qty: float,
    entry_price: float,
    tp_price: float,
    sl_price: float,
    thesis: str,
    total_equity: float = None,
    cash: float = None,
    invested: float = None
) -> None:
    """Notifica una operación en Alpaca decidida tras un análisis profundo de la IA."""
    profit_pct = ((tp_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0.0
    loss_pct = ((entry_price - sl_price) / entry_price) * 100 if entry_price > 0 else 0.0
    qty_str = f"{qty:.6f}".rstrip("0").rstrip(".") if qty < 1 else f"{qty:.2f}"
    footer = _equity_footer(total_equity, cash, invested)

    msg = (
        f"🤖 <b>NUEVA OPERACIÓN EN ALPACA (Decisión de la IA)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔹 <b>Activo:</b> {symbol}\n"
        f"🔹 <b>Acción:</b> {action.upper()}\n"
        f"🔹 <b>Cantidad:</b> {qty_str}\n"
        f"🔹 <b>Precio Entrada:</b> {_fmt(entry_price)}\n"
        f"🎯 <b>Take Profit:</b> {_fmt(tp_price)} (+{profit_pct:.1f}%)\n"
        f"🛑 <b>Stop Loss:</b> {_fmt(sl_price)} (-{loss_pct:.1f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 <b>Tesis y Razonamiento de la IA:</b>\n"
        f"• <i>{thesis}</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{footer}"
        f"<i>Orden bracket protegida automáticamente en Alpaca.</i>"
    )
    logger.info(f"[TELEGRAM ALPACA IA] Operación enviada en {symbol} ({action}) - {thesis[:50]}...")
    send_telegram_message(msg)


