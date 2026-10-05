"""
Servicio de Monitorización de Noticias, Redes y Declaraciones Públicas.
Rastrea titulares en tiempo real sobre Elon Musk (X/Twitter), Donald Trump (Truth Social),
la Reserva Federal (Jerome Powell) y Criptomonedas para usarlos como catalizadores en Polymarket.
"""

from __future__ import annotations
import logging
import re
import xml.etree.ElementTree as ET
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("NewsService")


class NewsService:
    TOPICS = {
        "elon_musk_tweets": "Elon+Musk+tweet+OR+X+post+OR+Tesla+OR+SpaceX",
        "donald_trump_truth": "Donald+Trump+Truth+Social+OR+speech+OR+rally",
        "tech_ai_breakthroughs": "OpenAI+OR+ChatGPT+OR+Sam+Altman+OR+Nvidia+tweet",
        "fed_rates_macro": "Federal+Reserve+rates+OR+Jerome+Powell+OR+inflation",
        "crypto_market": "Bitcoin+OR+Ethereum+ETF+OR+crypto+regulation",
        "geopolitics_breaking": "breaking+news+White+House+OR+Pentagon+OR+UN+OR+war",
        "election_polling": "poll+election+odds+prediction+OR+approval+rating"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        })

    def fetch_topic_news(self, query: str, max_items: int = 10) -> List[Dict[str, Any]]:
        """Descarga los últimos titulares desde el feed RSS de Google News."""
        url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        items = []
        try:
            res = self.session.get(url, timeout=8)
            if res.status_code != 200:
                logger.warning(f"Error HTTP {res.status_code} al consultar noticias para {query}")
                return []

            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:max_items]:
                raw_title = item.find("title").text if item.find("title") is not None else ""
                clean_title = re.sub(r"<[^<]+?>", "", raw_title).strip()
                
                # Extraer fuente del título si viene en formato 'Título - Fuente'
                source = ""
                if " - " in clean_title:
                    parts = clean_title.rsplit(" - ", 1)
                    clean_title = parts[0]
                    source = parts[1]

                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""

                if clean_title:
                    items.append({
                        "title": clean_title,
                        "source": source,
                        "pub_date": pub_date,
                        "link": link
                    })
        except Exception as e:
            logger.error(f"Error al parsear noticias para {query}: {e}")

        return items

    def search_live_web_and_tweets(self, question: str, max_items: int = 6) -> List[Dict[str, Any]]:
        """
        Realiza una búsqueda dirigida en internet y redes sociales (X/Twitter, noticias y declaraciones)
        específicamente para los protagonistas y entidades de la pregunta de Polymarket.
        """
        clean_q = re.sub(r"[^\w\s]", " ", question)
        words = clean_q.split()
        stop_words = {
            "will", "the", "and", "from", "that", "this", "what", "which", "after", "before",
            "october", "november", "december", "january", "winner", "most", "votes", "round",
            "between", "first", "next", "win", "post", "tweets", "posts", "market", "power"
        }
        keywords = [w for w in words if len(w) > 2 and w.lower() not in stop_words]
        search_terms = keywords[:4] if keywords else words[:3]
        target_query = "+".join(search_terms) + "+tweet+OR+X+OR+statement+OR+news"

        logger.info(f"[Live Web & Tweets] Investigando en internet y redes para: '{' '.join(search_terms)}'")
        return self.fetch_topic_news(target_query, max_items=max_items)

    def get_latest_catalysts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Obtiene las noticias y declaraciones más recientes agrupadas por temática."""
        catalysts = {}
        for category, query in self.TOPICS.items():
            news = self.fetch_topic_news(query, max_items=5)
            catalysts[category] = news
        return catalysts

    def find_catalyst_for_question(self, question: str, catalysts: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        """
        Busca si alguna noticia reciente de Elon, Trump o Macroeconomía coincide
        con las palabras clave de la pregunta de Polymarket.
        """
        q_words = set(re.findall(r"\b[A-Za-z]{4,}\b", question.lower()))
        # Quitar palabras genéricas
        stop_words = {"will", "after", "before", "what", "which", "price", "than", "more", "less", "above", "below"}
        keywords = q_words - stop_words

        best_match = None
        best_score = 0

        for cat, news_list in catalysts.items():
            for news in news_list:
                title_words = set(re.findall(r"\b[A-Za-z]{4,}\b", news["title"].lower()))
                common = keywords.intersection(title_words)
                score = len(common)
                if score > best_score:
                    best_score = score
                    best_match = {
                        "category": cat,
                        "headline": news["title"],
                        "source": news["source"],
                        "date": news["pub_date"],
                        "score": score
                    }

        return best_match if best_score >= 1 else None
