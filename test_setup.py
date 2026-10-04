"""
Script de diagnóstico y prueba del entorno.
Verifica que las credenciales de Alpaca funcionen y envía un mensaje de prueba a Telegram.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import config
from notifier import send_telegram_message


def run_diagnostics():
    print("=" * 60)
    print("   [+] DIAGNOSTICO Y PRUEBA DEL BOT DE TRADING")
    print("=" * 60)

    # 1. Comprobar .env
    print("\n1. Verificando variables de configuracion (.env)...")
    print(f"   * ALPACA_API_KEY: {'[CONFIGURADA OK]' if config.ALPACA_API_KEY else '[FALTA - VACIA]'}")
    print(f"   * ALPACA_SECRET_KEY: {'[CONFIGURADA OK]' if config.ALPACA_SECRET_KEY else '[FALTA - VACIA]'}")
    print(f"   * MODO TRADING: {'[SIMULADOR - Paper Trading]' if config.ALPACA_PAPER else '[REAL - Dinero Real]'}")
    print(f"   * TELEGRAM_BOT_TOKEN: {'[CONFIGURADO OK]' if config.TELEGRAM_BOT_TOKEN else '[FALTA (opcional)]'}")
    print(f"   * TELEGRAM_CHAT_ID: {'[CONFIGURADO OK]' if config.TELEGRAM_CHAT_ID else '[FALTA (opcional)]'}")
    print(f"   * SIMBOLOS A VIGILAR: {', '.join(config.SYMBOLS)}")
    print(f"   * RIESGO POR OPERACION: ${config.RISK_PER_TRADE_USD:.2f}")
    print(f"   * TAKE PROFIT: {config.TAKE_PROFIT_PCT * 100:.1f}%")
    print(f"   * STOP LOSS: {config.STOP_LOSS_PCT * 100:.1f}%")

    if not config.ALPACA_API_KEY or not config.ALPACA_SECRET_KEY:
        print("\n[!] ATENCION: Debes colocar tus claves de Alpaca en el archivo .env")
        print("    Abre el archivo: trading-bot/.env y pega tu ALPACA_API_KEY y ALPACA_SECRET_KEY")
        print("    (Guia en README.md)")
        return

    # 2. Conexión con Alpaca
    print("\n2. Probando conexion con Alpaca Markets...")
    try:
        from alpaca_service import AlpacaService
        alpaca = AlpacaService()
        acct = alpaca.get_account_summary()
        print("   [OK] Conexion con Alpaca establecida con exito!")
        print(f"        - ID de Cuenta: {acct['id']}")
        print(f"        - Estado: {acct['status']}")
        print(f"        - Saldo en Efectivo: ${acct['cash']:,.2f}")
        print(f"        - Poder de Compra: ${acct['buying_power']:,.2f}")
        print(f"        - Valor del Portafolio: ${acct['portfolio_value']:,.2f}")

        # 3. Comprobar obtención de datos
        test_symbol = config.SYMBOLS[0] if config.SYMBOLS else "AAPL"
        print(f"\n3. Probando descarga de cotizaciones para {test_symbol}...")
        bars = alpaca.get_bars(test_symbol, limit=5)
        if not bars.empty and "close" in bars.columns:
            last_price = bars["close"].iloc[-1]
            print(f"   [OK] Datos recibidos correctamente. Ultimo precio de {test_symbol}: ${last_price:.2f}")
        else:
            print(f"   [!] No se recibieron velas para {test_symbol} (podria ser fuera de horario o simbolo no admitido en plan gratuito)")
    except Exception as e:
        print(f"   [ERROR] Error conectando a Alpaca: {e}")

    # 4. Prueba de Telegram
    print("\n4. Probando notificaciones de Telegram...")
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        test_msg = (
            "🔔 <b>PRUEBA DE CONEXIÓN EXITOSA</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Tu bot de trading autónomo configurado en Antigravity se comunica correctamente con tu Telegram.\n"
            "¡Todo listo para operar en Paper Trading!"
        )
        ok = send_telegram_message(test_msg)
        if ok:
            print("   [OK] Mensaje de prueba enviado a tu Telegram. Revisa tu chat.")
        else:
            print("   [ERROR] Fallo el envio a Telegram. Comprueba tu token y chat ID.")
    else:
        print("   [INFO] Telegram no configurado todavia en .env. Puedes agregarlo para recibir avisos en tu movil.")

    print("\n" + "=" * 60)
    print("   Diagnostico finalizado.")
    print("=" * 60)


if __name__ == "__main__":
    run_diagnostics()
