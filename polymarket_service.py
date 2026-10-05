"""
Servicio para interactuar con la API pública de Polymarket (Gamma API).
Permite buscar mercados activos, consultar probabilidades y filtrar por volumen o temática.
"""

import logging
import json
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger("PolymarketService")


class PolymarketService:
    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        })

    def get_active_events(self, tag_slug: Optional[str] = None, limit: int = 50, order_by: str = "volume24hr") -> List[Dict[str, Any]]:
        """
        Obtiene eventos activos ordenados por volumen.
        tag_slug puede ser: 'politics', 'crypto', 'business', 'pop-culture', etc.
        """
        url = f"{self.BASE_URL}/events"
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": order_by,
            "ascending": "false"
        }
        if tag_slug:
            params["tag_slug"] = tag_slug

        try:
            res = self.session.get(url, params=params, timeout=10)
            if res.status_code == 200:
                return res.json()
            else:
                logger.error(f"Error al consultar eventos en Polymarket: {res.status_code}")
                return []
        except Exception as e:
            logger.error(f"Excepción al conectar con Polymarket Gamma API: {e}")
            return []

    def get_event_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Busca un evento específico por su slug."""
        url = f"{self.BASE_URL}/events"
        try:
            res = self.session.get(url, params={"slug": slug}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data[0] if data else None
        except Exception as e:
            logger.error(f"Error al obtener evento por slug {slug}: {e}")
        return None

    def get_market_by_id(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene y normaliza un mercado específico directamente por su ID."""
        url = f"{self.BASE_URL}/markets/{market_id}"
        try:
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                raw_m = res.json()
                return self.parse_market_info(raw_m)
        except Exception as e:
            logger.error(f"Error al obtener mercado por id {market_id}: {e}")
        return None

    def parse_market_info(self, raw_market: Dict[str, Any], event_title: str = "", event_slug: str = "") -> Optional[Dict[str, Any]]:
        """Normaliza los datos de un mercado individual de Polymarket."""
        try:
            market_id = str(raw_market.get("id"))
            question = raw_market.get("question", "")
            if not question:
                return None

            slug = raw_market.get("slug", event_slug or "")
            outcomes_raw = raw_market.get("outcomes", "[]")
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else (outcomes_raw or [])
            
            prices_raw = raw_market.get("outcomePrices", "[]")
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else (prices_raw or [])

            if not outcomes or not prices or len(outcomes) != len(prices):
                return None

            price_map = {}
            for outcome, price_str in zip(outcomes, prices):
                try:
                    price_map[outcome] = float(price_str)
                except (ValueError, TypeError):
                    price_map[outcome] = 0.0

            vol_24h = float(raw_market.get("volume24hr") or 0.0)
            total_vol = float(raw_market.get("volume") or 0.0)
            closed = bool(raw_market.get("closed", False))
            active = bool(raw_market.get("active", True))

            url = f"https://polymarket.com/market/{slug}" if slug else "https://polymarket.com"

            return {
                "id": market_id,
                "question": question,
                "event_title": event_title or question,
                "slug": slug,
                "url": url,
                "outcomes": outcomes,
                "prices": price_map,
                "volume24hr": vol_24h,
                "total_volume": total_vol,
                "active": active,
                "closed": closed,
                "end_date": raw_market.get("endDate", ""),
                "description": raw_market.get("description", "")
            }
        except Exception as e:
            logger.debug(f"Error normalizando mercado: {e}")
            return None

    def search_markets_by_keywords(self, keywords: List[str], limit_per_cat: int = 40) -> List[Dict[str, Any]]:
        """
        Busca mercados activos relacionados con palabras clave (Trump, Musk, Fed, etc.)
        en las categorías más relevantes de Polymarket.
        """
        categories = ["politics", "crypto", "business", "science", "pop-culture", "sports", None]
        seen_ids = set()
        matched_markets = []

        keywords_lower = [k.lower() for k in keywords]

        for cat in categories:
            events = self.get_active_events(tag_slug=cat, limit=limit_per_cat, order_by="volume24hr")
            for ev in events:
                ev_title = ev.get("title", "")
                ev_slug = ev.get("slug", "")
                ev_desc = ev.get("description", "")
                
                # Comprobar si el evento o sus mercados coinciden
                title_matches = any(kw in ev_title.lower() or kw in ev_desc.lower() for kw in keywords_lower)

                for m in ev.get("markets", []):
                    m_id = str(m.get("id"))
                    if m_id in seen_ids:
                        continue

                    m_question = m.get("question", "")
                    q_matches = any(kw in m_question.lower() for kw in keywords_lower)

                    if title_matches or q_matches or not keywords:
                        parsed = self.parse_market_info(m, event_title=ev_title, event_slug=ev_slug)
                        if parsed and parsed["active"] and not parsed["closed"]:
                            # Filtrar mercados con volumen mínimo para que sean líquidos
                            if parsed["total_volume"] > 5000:
                                seen_ids.add(m_id)
                                matched_markets.append(parsed)

        # Ordenar por volumen en 24h
        matched_markets.sort(key=lambda x: x["volume24hr"], reverse=True)
        return matched_markets
