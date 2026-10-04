import json
from polymarket_service import PolymarketService

s = PolymarketService()

print("=== MERCADOS DESTACADOS DE POLITICA Y ACTUALIDAD ===")
politics = s.get_active_events(tag_slug="politics", limit=15, order_by="volume24hr")
for e in politics[:8]:
    title = e.get("title", "")
    vol = e.get("volume24hr", 0) or 0
    print(f"\n[EVENTO] {title} (Vol 24h: ${vol:,.0f})")
    for m in e.get("markets", [])[:3]:
        q = m.get("question", "")
        prices = m.get("outcomePrices", "")
        print(f"   - Pregunta: {q}")
        print(f"     Precios: {prices}")

print("\n=== MERCADOS DIRECTOS DE TRUMP, ELON MUSK Y FED ===")
markets = s.search_markets_by_keywords(["Trump", "Musk", "Fed", "Powell"], limit_per_cat=40)
for m in markets:
    q = m["question"]
    ql = q.lower()
    if any(k in ql for k in ["trump", "musk", "fed ", "federal reserve", "powell"]):
        prices = m.get("prices", {})
        vol = m.get("total_volume", 0)
        print(f"* {q}")
        print(f"  Precios: {prices} | Volumen: ${vol:,.0f} | ID: {m['id']}")
