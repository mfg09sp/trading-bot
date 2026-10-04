# 📘 Manual de Inversión y Diagnóstico de Mercado (Investment Playbook)

> **Mandato Permanente del Usuario:**  
> *"Si algo no va bien, investiga qué puede estar pasando: revisa los principios y patrones de inversión y averigua qué ocurre fuera del gráfico (macroeconomía, geopolítica). No para una sola vez, sino siempre."*

---

## 1. Los Tres Ejes de Diagnóstico Obligatorios

Cada vez que el bot experimente una racha adversa, estancamiento o un movimiento brusco, el análisis debe desglosarse en estos 3 niveles:

```
                  ┌────────────────────────────────────────┐
                  │    DIAGNÓSTICO INTEGRAL DE MERCADO     │
                  └───────────────────┬────────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
         ▼                            ▼                            ▼
  [1. TÉCNICO & PATRONES]     [2. FUERA DEL GRÁFICO]       [3. CUANTITATIVO]
  - Soportes / Resistencias   - Noticias Reserva Federal   - Preservación capital
  - Falsas rupturas           - Datos IPC / Inflación      - Ratio Riesgo/Beneficio
  - Divergencias RSI          - Conflictos geopolíticos    - Drawdown máximo
  - Compresión volatilidad    - Rendimiento Bonos (Yields) - Control de exposición
```

---

## 2. Eje 1: Patrones de Gráfico y Acción del Precio

1. **Rupturas Falsas ("Bull Traps"):**
   - *Qué es:* El precio supera una resistencia con entusiasmo pero pierde volumen inmediatamente y se desploma.
   - *Diagnóstico:* Ocurre frecuentemente en mercados laterales sin tendencia institucional.
   - *Corrección:* Exigir confirmación de volumen y cierre de vela consistente antes de entrar en rupturas.

2. **Divergencias RSI (Señal de Alerta Temprana):**
   - *Qué es:* El precio marca un nuevo máximo, pero el RSI marca un máximo más bajo.
   - *Diagnóstico:* Agotamiento de la fuerza compradora; el precio suele corregir bruscamente.
   - *Corrección:* La salida dinámica implementada en `strategy.py` detecta giros en RSI > 70 para adelantarse al giro.

3. **Compresión y Expansión de Volatilidad:**
   - *Qué es:* Periodos de rango estrecho (baja volatilidad) son seguidos invariablemente por explosiones direccionales.
   - *Diagnóstico:* Entrar en el medio de una compresión suele generar órdenes de stop por ruido lateral.

---

## 3. Eje 2: Fuera del Gráfico (Macroeconomía y Geopolítica)

El análisis técnico **nunca opera en el vacío**. Un tweet, un dato de empleo o una declaración de tipos puede invalidar cualquier patrón técnico en segundos:

1. **La Reserva Federal (Fed) y Tipos de Interés:**
   - Las declaraciones de miembros de la Fed (como las capturadas hoy por nuestro `market_intelligence.py`) sobre si recortarán o mantendrán tipos afectan directamente al S&P 500 (`SPY`) y a las tecnológicas de alto crecimiento (`NVDA`, `TSLA`, `MSFT`).
2. **Inflación (CPI / PCE) y Rendimientos de Bonos (Treasury Yields):**
   - Si los rendimientos de los bonos a 10 años suben, el dinero institucional sale de la renta variable de riesgo hacia la renta fija, provocando caídas generalizadas independientemente del análisis técnico.
3. **Eventos Geopolíticos y Petróleo:**
   - Tensiones bélicas, bloqueos comerciales o sanciones provocan picos en el petróleo y en el oro, induciendo aversión al riesgo (*Risk-Off*) en acciones y criptomonedas.
4. **Regulaciones y Noticias Cripto:**
   - Demandas de la SEC, aprobaciones de ETFs o cambios legislativos mueven a `BTC` y altcoins en cuestión de minutos.

---

## 4. Eje 3: Principios Clásicos de Gestión de Capital

1. **Preservación Estricta:**
   - Es preferible perderse una subida que sufrir una pérdida catastrófica. La regla número uno de Warren Buffett: *"Nunca pierdas dinero"*.
2. **Corte Rápido de Pérdidas:**
   - Todas las órdenes cuentan con Stop Loss inmutable en Alpaca (-1.0%) y salidas dinámicas por ruptura de soporte para no dejar correr operaciones perdedoras.
3. **El S&P 500 (`SPY`) como Filtro Rector:**
   - Si el S&P 500 está en tendencia bajista clara, la probabilidad de éxito de compras en acciones individuales disminuye drásticamente. El bot debe adoptar una postura defensiva.

---

## 5. Herramienta Automatizada: `market_intelligence.py`

El proyecto cuenta con el módulo `market_intelligence.py` integrado directamente con la API de noticias de Alpaca:
* Descarga titulares y noticias financieras en tiempo real.
* Filtra palabras clave críticas (`fed`, `inflation`, `yields`, `war`, `tariff`, etc.).
* Evalúa el régimen del S&P 500 (`BULL_TREND`, `BEAR_TREND`, `CHOPPY_RANGING`).
* Se ejecuta automáticamente y puede consultarse en cualquier momento.
