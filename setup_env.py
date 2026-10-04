"""
Script auxiliar para configurar .env en entornos de CI/CD (GitHub Actions)
de forma limpia, segura y sin errores de caracteres especiales de shell.
"""

import os

alpaca_key = (os.getenv("ALPACA_API_KEY") or os.getenv("ALPACA_APT_KEY") or "").strip()
alpaca_secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
tele_token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
tele_chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

env_content = f"""ALPACA_API_KEY={alpaca_key}
ALPACA_SECRET_KEY={alpaca_secret}
ALPACA_PAPER=true
GEMINI_API_KEY={gemini_key}
TELEGRAM_BOT_TOKEN={tele_token}
TELEGRAM_CHAT_ID={tele_chat}
RISK_PER_TRADE_USD=2500.0
TAKE_PROFIT_PCT=0.025
STOP_LOSS_PCT=0.010
"""

with open(".env", "w", encoding="utf-8") as f:
    f.write(env_content)

print(f"Archivo .env configurado correctamente en el servidor (Gemini Key: {'OK' if gemini_key else 'FALTA'}, Alpaca Key: {'OK' if alpaca_key else 'FALTA'}).")
