"""
Escuchador Interactivo de Mensajes de Telegram para el Bot de Trading.
Permite al usuario interactuar en tiempo real con su bot desde Telegram:
- Responde a /estado, /informe, /cartera o 'como va' con el informe completo de inversiones.
- Responde a /ayuda con los comandos disponibles.
- Responde a /analisis ejecutando un ciclo inmediato de Google Gemini.
- Puede ejecutarse en modo continuo o por un tiempo limitado (--duration en segundos).
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import argparse
import logging
import requests
from typing import Optional

import config
import notifier
from telegram_reporter import generate_portfolio_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TelegramListener")


def send_reply(chat_id: str, text: str) -> bool:
    """Envía una respuesta al chat especificado."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            return True
        elif res.status_code == 400:
            # Fallback a texto plano si falla el parseo de HTML
            clean_text = text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("<code>", "").replace("</code>", "")
            res2 = requests.post(url, json={"chat_id": chat_id, "text": clean_text}, timeout=10)
            return res2.status_code == 200
    except Exception as e:
        logger.error(f"Error enviando respuesta a Telegram: {e}")
    return False


def get_help_message() -> str:
    return (
        "🤖 <b>COMANDOS DISPONIBLES EN TU BOT DE TRADING</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• <b>/estado</b> o <i>como va</i>: Informe completo y actualizado de tu cartera (Alpaca + Polymarket + SP500 + Pedro Sánchez).\n"
        "• <b>/informe</b> o <b>/cartera</b>: Mismo reporte detallado de tus inversiones.\n"
        "• <b>/analisis</b>: Ejecuta un ciclo de análisis y predicción con Google Gemini en el acto.\n"
        "• <b>/ayuda</b>: Muestra este mensaje de ayuda.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>El bot vigila los mercados las 24 horas del día en la nube.</i>"
    )


def process_message(msg: dict) -> None:
    chat_id = str(msg.get("chat", {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    user_name = msg.get("from", {}).get("first_name", "Usuario")

    if not text:
        return

    logger.info(f"Mensaje recibido de {user_name} ({chat_id}): '{text}'")

    clean_text = text.lower().replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").strip()

    # Comandos para pedir el informe de cartera
    report_keywords = [
        "/estado", "/informe", "/cartera", "/balance", "/resumen", "/portfolio",
        "como va", "cómo va", "como va todo", "cómo va todo", "estado", "informe",
        "cartera", "balance", "resumen", "cuanto", "cuánto", "inversiones", "saldo"
    ]

    is_report_request = any(clean_text == kw or clean_text.startswith(kw) for kw in report_keywords)

    if is_report_request:
        logger.info(f"Generando y enviando informe solicitado por {user_name}...")
        report = generate_portfolio_report()
        send_reply(chat_id, report)
        return

    # Comando para forzar análisis de IA bajo demanda
    if clean_text in ["/analisis", "/análisis", "/scan", "/escanear", "analizar"]:
        logger.info(f"Ejecutando análisis de IA bajo demanda solicitado por {user_name}...")
        send_reply(chat_id, "🧠 <b>Google Gemini:</b> <i>Iniciando análisis cuántico de gráficos y mercados bajo demanda...</i>")
        try:
            from run_ai_cycle import run_cycle
            run_cycle()
            send_reply(chat_id, "✅ <b>Análisis completado.</b> Los datos y posiciones actualizadas han sido procesados.")
        except Exception as e:
            send_reply(chat_id, f"⚠️ Error durante el análisis: {e}")
        return

    # Comando de ayuda
    if clean_text in ["/help", "/ayuda", "ayuda", "help"]:
        send_reply(chat_id, get_help_message())
        return

    # Si escribe cualquier otra cosa, responder amablemente con la ayuda
    reply = (
        f"Hola {user_name}! 👋\n\n"
        "Escribe <b>/estado</b> o <b>'como va'</b> para ver tu informe completo de inversiones en cualquier momento."
    )
    send_reply(chat_id, reply)


def listen_loop(duration_seconds: int = 0) -> None:
    """
    Bucle de escucha de mensajes vía long polling.
    Si duration_seconds > 0, se detiene tras ese número de segundos.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("No se ha configurado TELEGRAM_BOT_TOKEN.")
        return

    logger.info(f"Iniciando escucha interactiva de Telegram (Duración: {duration_seconds if duration_seconds > 0 else 'Indefinida'}s)...")

    start_time = time.time()
    offset: Optional[int] = None

    # Primero limpiar mensajes muy viejos obteniendo el último offset
    try:
        res = requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates?offset=-1&timeout=2",
            timeout=5
        )
        if res.status_code == 200:
            updates = res.json().get("result", [])
            if updates:
                offset = updates[-1]["update_id"] + 1
    except Exception as e:
        logger.warning(f"Aviso al sincronizar offset inicial de Telegram: {e}")

    while True:
        # Verificar si se cumplió la duración
        if duration_seconds > 0 and (time.time() - start_time) >= duration_seconds:
            logger.info(f"Sesión de escucha de {duration_seconds}s finalizada.")
            break

        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {
                "timeout": 5,
                "limit": 10
            }
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                for u in updates:
                    offset = u["update_id"] + 1
                    msg = u.get("message")
                    if msg:
                        process_message(msg)

            time.sleep(1)

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            logger.error(f"Error en bucle de Telegram listener: {e}")
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="Escuchador de Telegram interactivo")
    parser.add_argument("--duration", type=int, default=0, help="Duración en segundos para escuchar antes de salir (0 = infinito)")
    args = parser.parse_args()

    listen_loop(duration_seconds=args.duration)


if __name__ == "__main__":
    main()
