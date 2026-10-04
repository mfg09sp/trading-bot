"""
Módulo de Inteligencia de Mercado, Macroeconomía y Patrones Técnicos.
Permite analizar qué ocurre "fuera del gráfico":
- Noticias financieras en tiempo real y alertas geopolíticas / macroeconómicas.
- Detección de régimen de mercado a través del S&P 500 (SPY).
- Diagnóstico integral de causas ante rachas de mercado complejas o pérdidas.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from alpaca.data.historical.news import NewsClient, NewsRequest
import config
from alpaca_service import AlpacaService

logger = logging.getLogger("MarketIntelligence")

# Palabras clave de alto impacto macroeconómico y geopolítico
MACRO_KEYWORDS = [
    "war", "guerra", "conflict", "conflicto", "fed", "federal reserve",
    "interest rate", "tasas de interes", "inflation", "inflacion", "cpi",
    "tariff", "aranceles", "sanction", "sanciones", "crude", "oil", "petroleo",
    "middle east", "ukraine", "taiwan", "china", "sec", "crypto ban",
    "recession", "recesion", "debt", "crisis", "yields", "bonds"
]


class MarketIntelligence:
    def __init__(self):
        try:
            self.news_client = NewsClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY)
        except Exception as e:
            logger.error(f"Error inicializando NewsClient: {e}")
            self.news_client = None

    def fetch_live_news(self, symbols: Optional[List[str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Descarga las últimas noticias financieras en vivo desde Alpaca."""
        if not self.news_client:
            return []

        try:
            req = NewsRequest(symbols=symbols, limit=limit) if symbols else NewsRequest(limit=limit)
            response = self.news_client.get_news(req)
            news_items = []
            for n in response.data.get("news", []):
                news_items.append({
                    "id": getattr(n, "id", None),
                    "headline": getattr(n, "headline", ""),
                    "summary": getattr(n, "summary", ""),
                    "symbols": getattr(n, "symbols", []),
                    "created_at": getattr(n, "created_at", None),
                    "url": getattr(n, "url", "")
                })
            return news_items
        except Exception as e:
            logger.error(f"Error obteniendo noticias: {e}")
            return []

    def detect_geopolitical_or_macro_events(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Escanea las noticias recientes en busca de acontecimientos
        geopolíticos, inflación, decisiones de la Fed o tensiones globales.
        """
        news = self.fetch_live_news(limit=limit)
        flagged = []

        for item in news:
            text = (item["headline"] + " " + item["summary"]).lower()
            matching_keywords = [kw for kw in MACRO_KEYWORDS if kw in text]
            if matching_keywords:
                flagged.append({
                    "headline": item["headline"],
                    "symbols": item["symbols"],
                    "keywords": matching_keywords,
                    "created_at": item["created_at"],
                    "url": item["url"]
                })

        return flagged

    def diagnose_market_regime(self, alpaca: AlpacaService) -> Dict[str, Any]:
        """
        Analiza el estado general de la economía y el mercado
        utilizando el S&P 500 (SPY) como termómetro principal.
        """
        spy_bars = alpaca.get_bars("SPY", limit=50)
        if spy_bars.empty or len(spy_bars) < 25:
            return {
                "regime": "UNKNOWN",
                "reason": "Datos insuficientes de SPY"
            }

        close = spy_bars["close"]
        price = float(close.iloc[-1])
        ema_9 = float(close.ewm(span=9, adjust=False).mean().iloc[-1])
        ema_21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
        ema_50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close) >= 50 else ema_21

        # RSI de SPY
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        # Determinación de régimen
        if price > ema_21 and ema_9 > ema_21 and rsi > 50:
            regime = "BULL_TREND"
            desc = "Mercado alcista saludable y con fuerza compradora."
        elif price < ema_21 and ema_9 < ema_21 and rsi < 48:
            regime = "BEAR_TREND"
            desc = "Mercado bajista o bajo presión vendedora macro."
        else:
            regime = "CHOPPY_RANGING"
            desc = "Mercado lateral o indeciso (riesgo de rupturas falsas / 'whipsaws')."

        return {
            "spy_price": round(price, 2),
            "spy_rsi": round(rsi, 2),
            "regime": regime,
            "description": desc,
            "trend_alignment": "ALCISTA" if regime == "BULL_TREND" else ("BAJISTA" if regime == "BEAR_TREND" else "LATERAL")
        }

    def generate_full_market_diagnostic(self, alpaca: AlpacaService) -> Dict[str, Any]:
        """
        Genera una auditoría completa que combina:
        1. Régimen del S&P 500 (tendencia general).
        2. Alertas geopolíticas y macroeconómicas vivas.
        3. Recomendación de adaptación para el bot.
        """
        regime = self.diagnose_market_regime(alpaca)
        macro_alerts = self.detect_geopolitical_or_macro_events(limit=25)

        diagnostic = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_regime": regime,
            "macro_alerts_count": len(macro_alerts),
            "top_macro_alerts": macro_alerts[:5],
            "recommendation": ""
        }

        if regime["regime"] == "BEAR_TREND":
            diagnostic["recommendation"] = (
                "Cautela: El S&P 500 está perdiendo soportes. Ajustar posiciones a menor tamaño "
                "o priorizar activos descorrelacionados / cripto."
            )
        elif regime["regime"] == "CHOPPY_RANGING":
            diagnostic["recommendation"] = (
                "Mercado en rango lateral: Cuidado con las compras en rupturas falsas. "
                "Privilegiar compras en soportes extremos (RSI bajo) antes que compras de impulso."
            )
        else:
            diagnostic["recommendation"] = (
                "Entorno favorable: El índice rector acompaña el movimiento. "
                "Las estrategias de momentum y seguimiento de tendencia tienen alta probabilidad."
            )

        return diagnostic
