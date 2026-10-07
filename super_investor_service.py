"""
Servicio de Rastreo de 'Super Inversores', Whales y Transacciones de Insiders.
Monitoriza los movimientos de inversores legendarios con rendimiento demostrado:
1. Nancy Pelosi y Congresistas de EE.UU. (Capitol Trades / Senate & House Stock Watcher)
2. Warren Buffett / Berkshire Hathaway (Presentaciones 13F ante la SEC)
3. Stanley Druckenmiller, Ray Dalio y Michael Burry (Top Macro Hedge Funds)
4. Compras de Insiders Corporativos (CEOs y directores comprando con su propio dinero - SEC Form 4)

Cruza estos movimientos con el análisis técnico algorítmico y de IA en Alpaca.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from news_service import NewsService

logger = logging.getLogger("SuperInvestorService")


class SuperInvestorService:
    # Cartera base de activos de altísima convicción histórica por Super Inversor
    SUPER_INVESTOR_PROFILES = {
        "NANCY_PELOSI_CONGRESS": {
            "name": "Nancy Pelosi & Capitol Trades",
            "description": "Cartera de congresistas de EE.UU. con histórico extraordinario batiendo a Wall Street",
            "key_holdings": ["NVDA", "MSFT", "AAPL", "AVGO", "PANW", "AMZN", "GOOGL", "TSLA"],
            "style": "Tecnología de frontera, semiconductores y opciones LEAPS de alta rentabilidad"
        },
        "WARREN_BUFFETT_BERKSHIRE": {
            "name": "Warren Buffett (Berkshire Hathaway)",
            "description": "Mayor inversor de valor de la historia, allocation masivo de capital y fosos defensivos",
            "key_holdings": ["AAPL", "OXY", "KO", "BAC", "CB", "CVX", "AXP"],
            "style": "Fuerte flujo de caja, ventajas competitivas duraderas y recompras de acciones"
        },
        "TOP_HEDGE_FUND_WHALES": {
            "name": "Stanley Druckenmiller & Michael Burry",
            "description": "Gestores de fondos macro con mayor retorno ajustado al riesgo por década",
            "key_holdings": ["PLTR", "ARM", "SMCI", "META", "AMD", "COIN", "UBER"],
            "style": "Momentum institucional, aceleración de IA y giros asimétricos"
        }
    }

    def __init__(self, news_service: Optional[NewsService] = None):
        self.news = news_service or NewsService()

    def fetch_live_super_investor_disclosures(self) -> List[Dict[str, Any]]:
        """
        Rastrea en vivo noticias y filtraciones recientes de compras de congresistas,
        presentaciones 13F ante la SEC y compras de insiders.
        """
        queries = [
            ("Nancy Pelosi", "Nancy+Pelosi+stock+purchase+OR+trade+disclosure+OR+NVDA"),
            ("Warren Buffett", "Warren+Buffett+Berkshire+Hathaway+buys+stock+13F+filing"),
            ("Congresistas EE.UU.", "Congress+stock+trading+disclosure+purchase+filing"),
            ("Insiders Corporativos", "insider+buying+stock+CEO+director+SEC+Form+4+open+market")
        ]

        live_filings = []
        for entity_name, q in queries:
            news_items = self.news.fetch_topic_news(q, max_items=4)
            for item in news_items:
                title = item.get("title", "")
                # Extraer tickers potenciales (1 a 5 letras mayúsculas como NVDA, AAPL, etc.)
                tickers_found = self._extract_tickers_from_text(title)
                live_filings.append({
                    "entity": entity_name,
                    "headline": title,
                    "source": item.get("source", "Finanzas"),
                    "date": item.get("pub_date", ""),
                    "detected_tickers": tickers_found
                })
        return live_filings

    def _extract_tickers_from_text(self, text: str) -> List[str]:
        """Detecta tickers de acciones mencionados en el titular."""
        common_words = {"THE", "AND", "FOR", "NEW", "BUY", "TOP", "HAS", "ITS", "ARE", "OUT", "SEC", "CEO", "CFO", "NOW", "ALL", "BIG", "MAY"}
        candidates = re.findall(r"\b[A-Z]{2,5}\b", text)
        valid = []
        known_stocks = {
            "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "GOOG", "META", "TSLA", "AMD",
            "PLTR", "COIN", "NFLX", "AVGO", "ARM", "SMCI", "UBER", "OXY", "PANW",
            "BABA", "CRWD", "DIS", "BA", "BAC", "KO", "CB", "CVX", "INTC", "QCOM"
        }
        for c in candidates:
            if c in known_stocks and c not in common_words:
                if c not in valid:
                    valid.append(c)
        return valid

    def get_super_investor_candidates(self) -> List[Dict[str, Any]]:
        """
        Combina las carteras de los Super Inversores con las noticias de última hora
        para generar una lista priorizada de símbolos con su catalizador correspondiente.
        """
        candidates_map: Dict[str, Dict[str, Any]] = {}

        # 1. Añadir activos centrales de cada Super Inversor
        for prof_key, prof in self.SUPER_INVESTOR_PROFILES.items():
            for sym in prof["key_holdings"]:
                if sym not in candidates_map:
                    candidates_map[sym] = {
                        "symbol": sym,
                        "investors": [prof["name"]],
                        "styles": [prof["style"]],
                        "latest_news": [],
                        "conviction_score": 8
                    }
                else:
                    candidates_map[sym]["investors"].append(prof["name"])
                    candidates_map[sym]["conviction_score"] += 1

        # 2. Enriquecer con noticias de compras recientes en directo
        live_disclosures = self.fetch_live_super_investor_disclosures()
        for disc in live_disclosures:
            for sym in disc.get("detected_tickers", []):
                if sym in candidates_map:
                    candidates_map[sym]["latest_news"].append(disc["headline"])
                    candidates_map[sym]["conviction_score"] += 2
                else:
                    candidates_map[sym] = {
                        "symbol": sym,
                        "investors": [disc["entity"]],
                        "styles": ["Compra reciente detectada en filing oficial"],
                        "latest_news": [disc["headline"]],
                        "conviction_score": 8
                    }

        # Convertir a lista y ordenar por puntuación de convicción
        ranked_list = list(candidates_map.values())
        ranked_list.sort(key=lambda x: x["conviction_score"], reverse=True)
        return ranked_list
