# 🤖 Bot de Trading Autónomo con Alpaca y Telegram

Este proyecto implementa el sistema de trading algorítmico autónomo que viste en el vídeo:
1. **Paper Trading inicial (100% seguro y gratis):** Viene preconfigurado con una cuenta demo de **100.000 $ virtuales** en Alpaca para probar estrategias sin arriesgar ni un solo euro.
2. **Órdenes Bracket Seguras:** Cada compra coloca inmediatamente una orden de **Take Profit** y **Stop Loss** registrada directamente en el exchange. Si el bot se apaga o se va la luz, tu capital sigue protegido en el broker.
3. **Notificaciones Instantáneas en el Móvil:** Avisos en tiempo real por **Telegram** al abrir una operación y en el momento exacto en el que se alcanza el Take Profit (ganancia) o Stop Loss.
4. **Compatible desde España / Europa:** Alpaca Markets permite registro inmediato y acceso a su API para operar acciones de EE.UU. (AAPL, NVDA, TSLA...) y criptomonedas.
5. **Transición a Dinero Real:** Cuando estés satisfecho con las pruebas, solo cambias `ALPACA_PAPER=false` y tus claves reales en el archivo `.env`.

---

## 📁 Estructura del Proyecto

```text
trading-bot/
├── .env                  <-- Tus claves de Alpaca y Telegram (¡no compartir!)
├── .env.example          <-- Plantilla de ejemplo
├── config.py             <-- Configuración y parámetros de riesgo
├── alpaca_service.py     <-- Conector con la API de Alpaca (bracket orders, datos)
├── strategy.py           <-- Indicadores técnicos (RSI, medias móviles EMA)
├── notifier.py           <-- Notificaciones formateadas para Telegram
├── bot.py                <-- Motor principal de ejecución autónoma
├── test_setup.py         <-- Script de diagnóstico y prueba de conexión
└── requirements.txt      <-- Dependencias necesarias
```

---

## 🚀 Guía Rápida de Configuración (5 minutos)

### Paso 1: Obtener las claves de Alpaca Paper Trading (Gratis)
1. Ve a [https://alpaca.markets](https://alpaca.markets) y crea una cuenta gratuita.
2. En el panel lateral izquierdo, asegúrate de seleccionar **Paper Trading** (Modo Simulador).
3. En la sección **API Keys** (derecha o panel lateral), haz clic en **Generate New Key**.
4. Verás dos valores:
   - **API Key ID** (ej: `PK...`)
   - **Secret Key** (ej: `w8A...`)
5. Copia ambos valores.

### Paso 2: Configurar las Notificaciones en Telegram (Opcional pero muy recomendado)
1. Abre Telegram y busca al usuario oficial **`@BotFather`**.
2. Escribe `/newbot`, ponle un nombre a tu bot (ej. `MiTradingBot`) y un username (ej. `mi_trader_antigravity_bot`).
3. Te dará un **Token HTTP API** (ej: `7123456789:AAH...`). Cópialo.
4. Para obtener tu ID personal, busca en Telegram el bot **`@userinfobot`** y dale a Iniciar. Te responderá con tu **Id numérico** (ej: `123456789`).
5. Abre un chat con tu propio bot que acabas de crear y dale a **Iniciar** (para que tenga permiso de enviarte mensajes).

### Paso 3: Rellenar el archivo `.env`
Abre el archivo `.env` dentro de la carpeta `trading-bot` e introduce tus datos:

```env
ALPACA_API_KEY=tu_api_key_de_alpaca
ALPACA_SECRET_KEY=tu_secret_key_de_alpaca
ALPACA_PAPER=true

TELEGRAM_BOT_TOKEN=tu_token_de_botfather
TELEGRAM_CHAT_ID=tu_chat_id_numerico

SYMBOLS=AAPL,NVDA,TSLA,MSFT
RISK_PER_TRADE_USD=50.0
TAKE_PROFIT_PCT=0.015
STOP_LOSS_PCT=0.010
CHECK_INTERVAL_SECONDS=60
```

---

## 🧪 Paso 4: Probar la Conexión

Ejecuta el script de diagnóstico para comprobar que todo esté correcto sin arriesgar nada:

```powershell
python test_setup.py
```

Si todo está bien configurado, verás:
- Tu saldo virtual de 100.000 $.
- La cotización en tiempo real de los activos.
- Un mensaje de confirmación que llegará a tu Telegram.

---

## 🏃 Paso 5: Iniciar el Bot Autónomo

Para arrancar el bucle continuo de trading:

```powershell
python bot.py
```

El bot:
- Revisará las velas de precios en cada ciclo.
- Calculará los indicadores (RSI y cruces de medias móviles).
- Si detecta oportunidad de entrada, colocará la orden de compra con **Take Profit** y **Stop Loss** automáticos.
- Te enviará un mensaje a Telegram en cada evento importante.
- Para detener el bot de forma segura, presiona `Ctrl + C` en la terminal. Las órdenes activas seguirán protegidas en Alpaca.

---

## 💰 ¿Cómo pasar a Dinero Real cuando quieras?

Una vez hayas probado la estrategia durante días o semanas con dinero ficticio:
1. En tu cuenta de Alpaca, completa la verificación de identidad (KYC) y añade fondos (mediante transferencia SEPA o bancaria).
2. Cambia la vista a **Live Trading** y genera un nuevo par de claves API reales.
3. En el archivo `.env`, cambia:
   ```env
   ALPACA_PAPER=false
   ALPACA_API_KEY=tu_clave_real
   ALPACA_SECRET_KEY=tu_secreto_real
   ```
4. ¡Listo! El bot operará exactamente con las mismas reglas pero con dinero real y con el límite por operación (`RISK_PER_TRADE_USD`) que tú elijas.
