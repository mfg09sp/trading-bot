"""
Monitor Continuo de Gestión de Riesgo para Polymarket (Paper Trading).
Supervisa en segundo plano cada 60 segundos las posiciones abiertas para ejecutar
Take Profit (+30%), Stop Loss (-15%) o Resoluciones oficiales en tiempo real,
notificando al instante por Telegram.
"""

import sys
import time
import logging
from polymarket_service import PolymarketService
from polymarket_paper import PolymarketPaperEngine
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
logger = logging.getLogger("PolymarketMonitor")


def main():
    service = PolymarketService()
    engine = PolymarketPaperEngine()

    logger.info("Iniciando Monitor de Riesgo de Polymarket en segundo plano (vigilancia cada 60s)...")
    
    while True:
        try:
            # Releer estado del ledger por si la IA ha añadido nuevas posiciones
            engine.data = engine._load_ledger()
            active_count = len(engine.data.get("active_positions", {}))

            if active_count > 0:
                closed = engine.update_and_evaluate_positions(service)
                if closed:
                    summary = engine.get_summary()
                    for trade in closed:
                        notifier.notify_polymarket_close(trade, summary)

            time.sleep(60)

        except Exception as e:
            logger.error(f"Error en bucle de monitor de Polymarket: {e}", exc_info=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
