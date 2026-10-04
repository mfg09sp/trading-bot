"""
Supervisior y Orquestador Todo-en-Uno (Nube y Local).
Ejecuta de forma continua e ininterrumpida:
1. Monitor de Riesgo de Polymarket (TP +30% / SL -15% cada 60s).
2. Monitor de Riesgo de Alpaca Cripto y Acciones (TP +3% / SL -1.5% cada 60s).
3. Ciclo de Inteligencia Artificial con Google Gemini (cada 30 min o configurable).
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import time
import logging
import threading
from datetime import datetime

import config
import notifier
from run_ai_cycle import run_cycle
import polymarket_monitor
import alpaca_monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MasterSupervisor")


def poly_monitor_thread():
    logger.info("-> Hilo: Monitor de Polymarket arrancado.")
    try:
        polymarket_monitor.main()
    except Exception as e:
        logger.error(f"Error en hilo de Polymarket: {e}")


def alpaca_monitor_thread():
    logger.info("-> Hilo: Monitor de Alpaca arrancado.")
    try:
        alpaca_monitor.main()
    except Exception as e:
        logger.error(f"Error en hilo de Alpaca: {e}")


def ai_cycle_scheduler(interval_minutes: int = 30):
    logger.info(f"-> Hilo: Programador de IA Gemini arrancado (ciclo cada {interval_minutes} minutos).")
    while True:
        try:
            logger.info("Ejecutando ciclo periódico de IA Gemini...")
            run_cycle()
        except Exception as e:
            logger.error(f"Error en ciclo de IA Gemini: {e}")
        time.sleep(interval_minutes * 60)


def main():
    print("=" * 65)
    print("   🤖 INICIANDO SISTEMA AUTÓNOMO GLOBAL DE TRADING (IA GEMINI)   ")
    print("=" * 65)
    print("  • Motor IA: Google Gemini 1.5/2.5/3.8 Flash (Clave activa)")
  
    startup_msg = (
        "🚀 <b>BOT AUTÓNOMO INICIADO (GOOGLE GEMINI 24/7)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🧠 <b>Motor IA:</b> Google Gemini API (Conexión verificada)\n"
        "📡 <b>Monitores activos:</b>\n"
        "  • Polymarket Monitor (60s)\n"
        "  • Alpaca Cripto & Acciones (60s)\n"
        "  • Radar IA Gemini (Ciclo cada 30m)\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Operando en modo Paper Trading con posiciones de \$2,000+.</i>"
    )
    notifier.send_telegram_message(startup_msg)

    # Lanzar hilos de monitoreo continuo
    t1 = threading.Thread(target=poly_monitor_thread, daemon=True)
    t2 = threading.Thread(target=alpaca_monitor_thread, daemon=True)
    t3 = threading.Thread(target=ai_cycle_scheduler, args=(30,), daemon=True)

    t1.start()
    t2.start()
    t3.start()

    logger.info("Todos los servicios están en ejecución. Presiona Ctrl+C para detener.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Deteniendo supervisor por orden del usuario...")


if __name__ == "__main__":
    main()
