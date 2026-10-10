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
import requests
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


    def fetch_official_congress_disclosures(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Descarga el feed oficial de declaraciones de congresistas y senadores de EE.UU.
        (STOCK Act - House Clerk y Senate eFD) con tickers, político, fecha e importe.
        Fuente 100% libre y actualizada en tiempo real sin requerir APIs de pago como Quiver Quant.
        """
        url = "https://raw.githubusercontent.com/kadoa-org/congress-trading-monitor/main/public/data/trades.json"
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                purchases = [
                    t for t in data
                    if t.get("ticker") and t.get("transaction_type") == "Purchase"
                ]
                purchases.sort(key=lambda x: str(x.get("filing_date", "")), reverse=True)
                return purchases[:limit]
        except Exception as e:
            logger.warning(f"No se pudo consultar el feed del Congreso: {e}")
        return []

    def get_super_investor_candidates(self) -> List[Dict[str, Any]]:
        """
        Combina las carteras de los Super Inversores, las noticias y el feed oficial
        del Congreso de EE.UU. para generar la lista priorizada de símbolos para Alpaca.
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

        # 3. Enriquecer con declaraciones oficiales del Congreso (STOCK Act en vivo)
        congress_filings = self.fetch_official_congress_disclosures(limit=25)
        for cf in congress_filings:
            sym = cf.get("ticker", "").upper().strip()
            if not sym:
                continue
            filer = cf.get("filer_name", "Congresista EE.UU.")
            party = cf.get("party", "")
            amt = cf.get("amount_range_label", "")
            f_date = cf.get("filing_date", "")
            headline = f"Compra oficial de {filer} ({party}) por {amt} reportada el {f_date}"
            
            # Prioridad especial a Nancy Pelosi y altos importes
            is_pelosi = "pelosi" in filer.lower()
            bonus = 4 if is_pelosi else 2

            if sym in candidates_map:
                if filer not in candidates_map[sym]["investors"]:
                    candidates_map[sym]["investors"].append(f"{filer} (Congreso EE.UU.)")
                candidates_map[sym]["latest_news"].append(headline)
                candidates_map[sym]["conviction_score"] += bonus
            else:
                candidates_map[sym] = {
                    "symbol": sym,
                    "investors": [f"{filer} (Congreso EE.UU.)"],
                    "styles": [f"STOCK Act filing: {amt}"],
                    "latest_news": [headline],
                    "conviction_score": 7 + bonus
                }

        # Convertir a lista y ordenar por puntuación de convicción
        ranked_list = list(candidates_map.values())
        ranked_list.sort(key=lambda x: x["conviction_score"], reverse=True)
        return ranked_list
