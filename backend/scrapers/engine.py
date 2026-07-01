"""
Margin Runner — International Deal Scraper Engine
Scrapes discount/clearance deal sources in NL, DE, BE.
Selectors tuned per source via live HTML inspection (2026-07-01).
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import execute, query

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,de;q=0.7",
}


def parse_euro_price(text: str) -> float:
    """Extract euro price from text like '€ 99,99' or '99,99€' or '€ 2,21/l'."""
    m = re.search(r'€?\s*(\d+[.,]\d{2})', text.replace('\u202f', ' ').replace('\xa0', ' '))
    if m:
        return float(m.group(1).replace(',', '.'))
    return 0.0


class DealScraper:
    """Base class for country-specific deal scrapers."""
    country: str = ""
    currency: str = "EUR"
    source_name: str = ""
    source_url: str = ""

    def fetch(self, url: str) -> Optional[str]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            print(f"  [ERR] {self.source_name}: {e}")
            return None

    def parse(self, html: str) -> list[dict]:
        raise NotImplementedError

    def run(self) -> list[dict]:
        print(f"\n🔍 {self.source_name} ({self.country})")
        html = self.fetch(self.source_url)
        if not html:
            return []
        deals = self.parse(html)
        saved = 0
        for deal in deals:
            deal["country"] = self.country
            deal["currency"] = self.currency
            deal["source_name"] = self.source_name
            deal["source_url"] = self.source_url
            deal["date_found"] = datetime.now().isoformat()
            if self._save_deal(deal):
                saved += 1
        print(f"  → {len(deals)} found, {saved} new saved")
        return deals

    def _save_deal(self, deal: dict) -> bool:
        existing = query(
            "SELECT id FROM deals WHERE product_name = ? AND source_website = ?",
            (deal["product_name"], deal["source_name"])
        )
        if existing:
            return False
        execute(
            """INSERT INTO deals
               (product_name, sourcing_cost, market_price, platform,
                estimated_margin_percent, source_website, source_location,
                status, date_found, currency, country)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
            (
                deal["product_name"],
                deal["sourcing_cost"],
                deal["market_price"],
                deal.get("platform", "eBay"),
                deal.get("estimated_margin_percent", 0),
                deal["source_name"],
                deal.get("source_location", ""),
                deal["date_found"],
                deal["currency"],
                deal["country"],
            ),
        )
        return True


# ─── Netherlands ────────────────────────────────────────────────────

class ActionScraper(DealScraper):
    """
    Action.nl — discount retailer.
    Structure: div.grid with items in div.w-(--itemWidth)
    Each item has text like "Product Name | details | € 2,21/l | ..."
    """
    country = "NL"
    currency = "EUR"
    source_name = "Action NL"
    source_url = "https://www.action.com/nl-nl/"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        # Find the main product grid
        grid = soup.find('div', class_=re.compile(r'grid-flow-col'))
        if not grid:
            return deals
        for item in grid.find_all('div', class_=re.compile(r'w-\(--itemWidth\)')):
            text = item.get_text(strip=True, separator=' | ')
            # Extract product name (before first |)
            parts = [p.strip() for p in text.split('|')]
            if not parts or not parts[0]:
                continue
            name = parts[0]
            # Find price in the text
            price = parse_euro_price(text)
            if price <= 0:
                continue
            # Action's prices are already low retail; estimate flip at 2x
            deals.append({
                "product_name": name,
                "sourcing_cost": round(price, 2),
                "market_price": round(price * 2.0, 2),
                "platform": "eBay",
                "source_location": "Netherlands",
                "estimated_margin_percent": 50.0,
            })
        return deals


class BolComScraper(DealScraper):
    """
    Bol.com — NL/BE marketplace. Static fetch often returns cookie-wall.
    Falls back to browser-based approach if static fails.
    """
    country = "NL"
    currency = "EUR"
    source_name = "Bol.com Deals"
    source_url = "https://www.bol.com/nl/nl/l/aanbiedingen/"

    def parse(self, html):
        deals = []
        soup = BeautifulSoup(html, "lxml")
        # Try to find SSR-rendered products
        for item in soup.find_all(['div', 'li'], class_=re.compile(r'product|card|item', re.I)):
            title_el = item.find(['h2', 'h3', 'a'], class_=re.compile(r'title|name', re.I))
            price_el = item.find(class_=re.compile(r'price|promo', re.I))
            if title_el and price_el:
                name = title_el.get_text(strip=True)
                price = parse_euro_price(price_el.get_text())
                if name and price > 5:
                    deals.append({
                        "product_name": name,
                        "sourcing_cost": round(price, 2),
                        "market_price": round(price * 1.5, 2),
                        "platform": "eBay",
                        "source_location": "Netherlands",
                    })
        return deals


class MarktplaatsScraper(DealScraper):
    """
    Marktplaats.nl — JavaScript-rendered (React).
    Static fetch gets the shell but listings are loaded via API.
    """
    country = "NL"
    currency = "EUR"
    source_name = "Marktplaats"
    source_url = "https://www.marktplaats.nl/q/nieuw-ingepakt/"

    def parse(self, html):
        deals = []
        soup = BeautifulSoup(html, "lxml")
        # Try to find SSR-rendered listings or preloaded data
        for item in soup.find_all(['div', 'li'], class_=re.compile(r'listing|hz-Listing', re.I)):
            title_el = item.find(['h2', 'h3', 'a', 'span'], class_=re.compile(r'title|name', re.I))
            price_el = item.find(class_=re.compile(r'price|amount', re.I))
            if title_el:
                name = title_el.get_text(strip=True)
                price = parse_euro_price(price_el.get_text()) if price_el else 0
                if name and len(name) > 5 and price > 5:
                    deals.append({
                        "product_name": f"[Marktplaats] {name}",
                        "sourcing_cost": round(price, 2),
                        "market_price": round(price * 1.35, 2),
                        "platform": "Facebook Marketplace",
                        "source_location": "Netherlands",
                    })
        return deals


class MediamarktNLScraper(DealScraper):
    """MediaMarkt NL Outlet — JavaScript-rendered."""
    country = "NL"
    currency = "EUR"
    source_name = "MediaMarkt NL Outlet"
    source_url = "https://www.mediamarkt.nl/nl/category/_open-box-983674.html"

    def parse(self, html):
        return []  # JS-rendered, needs browser


# ─── Germany ─────────────────────────────────────────────────────────

class MyDealzScraper(DealScraper):
    """
    MyDealz.de — Germany's largest deal community.
    Structure: article.thread > div.threadListCard > strong.thread-title
    Price is embedded in title text (e.g. "für 99,99€")
    """
    country = "DE"
    currency = "EUR"
    source_name = "MyDealz"
    source_url = "https://www.mydealz.de/new?page=1"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for art in soup.find_all('article', class_=re.compile(r'thread')):
            title_el = art.find('strong', class_='thread-title')
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            # Extract price from title text (e.g. "für 99,99€" or "ab 5,00€")
            price = parse_euro_price(title)
            if price <= 0:
                # Try to find price in the full article text
                price = parse_euro_price(art.get_text())
            if price <= 0 or not title:
                continue
            deals.append({
                "product_name": title,
                "sourcing_cost": round(price, 2),
                "market_price": round(price * 1.5, 2),
                "platform": "eBay",
                "source_location": "Germany",
                "estimated_margin_percent": 33.3,
            })
        return deals[:20]


class MediamarktDEScraper(DealScraper):
    """MediaMarkt DE Outlet — JavaScript-rendered."""
    country = "DE"
    currency = "EUR"
    source_name = "MediaMarkt DE Outlet"
    source_url = "https://www.mediamarkt.de/de/category/_outlet-983674.html"

    def parse(self, html):
        return []  # JS-rendered


class LidlDEScraper(DealScraper):
    """
    Lidl.de — weekly specials. Static HTML has deal data.
    """
    country = "DE"
    currency = "EUR"
    source_name = "Lidl DE Angebote"
    source_url = "https://www.lidl.de/c/angebote"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        # Look for product data in script tags or SSR elements
        for item in soup.find_all(['div', 'article'], class_=re.compile(r'product|retail|tile|card', re.I)):
            title_el = item.find(['h2', 'h3', 'span'], class_=re.compile(r'title|name|head', re.I))
            price_el = item.find(class_=re.compile(r'price|main', re.I))
            if title_el:
                name = title_el.get_text(strip=True)
                price = parse_euro_price(price_el.get_text()) if price_el else parse_euro_price(item.get_text())
                if name and price > 0:
                    deals.append({
                        "product_name": f"[Lidl] {name}",
                        "sourcing_cost": round(price, 2),
                        "market_price": round(price * 1.8, 2),
                        "platform": "eBay",
                        "source_location": "Germany",
                    })
        return deals


# ─── Belgium ────────────────────────────────────────────────

class TweedehandsScraper(DealScraper):
    """
    2dehands.be — Belgian marketplace. JavaScript-rendered (React).
    """
    country = "BE"
    currency = "EUR"
    source_name = "2dehands BE"
    source_url = "https://www.2dehands.be/l/nieuw-in-verpakking/"

    def parse(self, html):
        deals = []
        soup = BeautifulSoup(html, "lxml")
        for item in soup.find_all(['div', 'li'], class_=re.compile(r'listing|hz-Listing', re.I)):
            title_el = item.find(['h2', 'h3', 'a', 'span'], class_=re.compile(r'title|name', re.I))
            price_el = item.find(class_=re.compile(r'price|amount', re.I))
            if title_el:
                name = title_el.get_text(strip=True)
                price = parse_euro_price(price_el.get_text()) if price_el else 0
                if name and len(name) > 5 and price > 5:
                    deals.append({
                        "product_name": f"[2dehands] {name}",
                        "sourcing_cost": round(price, 2),
                        "market_price": round(price * 1.35, 2),
                        "platform": "Facebook Marketplace",
                        "source_location": "Belgium",
                    })
        return deals


class VandenBorreScraper(DealScraper):
    """
    Vanden Borre BE — open box clearance.
    Structure: div.row > a (title), div.product-price / div.price (price)
    """
    country = "BE"
    currency = "EUR"
    source_name = "Vanden Borre Outlet"
    source_url = "https://www.vandenborre.be/open-box"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        seen = set()
        for row in soup.find_all('div', class_='row'):
            # Find product link - look for a with substantial text
            title_el = None
            for a in row.find_all('a', href=True):
                txt = a.get_text(strip=True)
                if len(txt) > 10 and ('product' in a.get('href','') or len(txt) > 15):
                    title_el = a
                    break
            if not title_el:
                continue
            name = title_el.get_text(strip=True)
            price_el = row.find('div', class_=re.compile(r'price|product-price', re.I))
            if not price_el:
                continue
            price_text = price_el.get_text(strip=True)
            price = parse_euro_price(price_text)
            if not name or price <= 5 or name in seen:
                continue
            seen.add(name)
            deals.append({
                "product_name": name,
                "sourcing_cost": round(price, 2),
                "market_price": round(price * 1.4, 2),
                "platform": "eBay",
                "source_location": "Belgium",
            })
        return deals


# ─── Scraper Registry ─────────────────────────────────────────────────

ALL_SCRAPERS: list[DealScraper] = [
    # Netherlands (static HTML)
    ActionScraper(),
    BolComScraper(),
    # Germany (static HTML)
    MyDealzScraper(),
    LidlDEScraper(),
    # Belgium (static HTML)
    VandenBorreScraper(),
    # JS-rendered (limited HTML parsing)
    MarktplaatsScraper(),
    TweedehandsScraper(),
    MediamarktNLScraper(),
    MediamarktDEScraper(),
]


def run_all():
    """Run every scraper and return total deals found."""
    total = 0
    start = time.time()
    print("=" * 60)
    print(f"🌍 Margin Runner — International Scraper Run")
    print(f"   {len(ALL_SCRAPERS)} scrapers • {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    for scraper in ALL_SCRAPERS:
        deals = scraper.run()
        total += len(deals)
    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"✅ Done: {total} deals from {len(ALL_SCRAPERS)} sources in {elapsed:.1f}s")
    print(f"{'=' * 60}")
    return total


def run_country(country: str):
    total = 0
    for scraper in ALL_SCRAPERS:
        if scraper.country.upper() == country.upper():
            deals = scraper.run()
            total += len(deals)
    print(f"\n🇪🇺 {country}: {total} deals")
    return total


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run_country(sys.argv[1])
    else:
        run_all()