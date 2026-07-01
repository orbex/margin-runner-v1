"""
Margin Runner — International Deal Scraper Engine
Scrapes discount/clearance deal sources in NL, DE, BE.
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Import our database
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import execute, query

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,de;q=0.7",
}

CURRENCY_RATES = {"EUR": 1.0, "USD": 0.92}  # rough, for normalization


class DealScraper:
    """Base class for country-specific deal scrapers."""

    country: str = ""
    currency: str = "EUR"
    source_name: str = ""
    source_url: str = ""

    def fetch(self, url: str) -> Optional[str]:
        """Fetch a URL and return HTML text."""
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            # Detect encoding
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            print(f"  [ERR] {self.source_name}: {e}")
            return None

    def parse(self, html: str) -> list[dict]:
        """Parse HTML into deal dicts. Override in subclasses."""
        raise NotImplementedError

    def run(self) -> list[dict]:
        """Fetch + parse + save. Returns deals found."""
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
        """Insert a deal if it doesn't already exist (by product name + source)."""
        existing = query(
            "SELECT id FROM deals WHERE product_name = ? AND source_website = ?",
            (deal["product_name"], deal["source_name"])
        )
        if existing:
            return False

        # Normalize price to EUR for comparison
        cost_eur = deal.get("sourcing_cost", 0)
        price_eur = deal.get("market_price", 0)

        execute(
            """INSERT INTO deals
               (product_name, sourcing_cost, market_price, platform,
                estimated_margin_percent, source_website, source_location,
                status, date_found, currency, country)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
            (
                deal["product_name"],
                cost_eur,
                price_eur,
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


# ─── Netherlands Scrapers ─────────────────────────────────────────────

class ActionScraper(DealScraper):
    """Action.nl — discount retailer, weekly deals."""
    country = "NL"
    currency = "EUR"
    source_name = "Action NL"
    source_url = "https://www.action.com/nl-nl/"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        # Action's current weekly deals section
        for item in soup.select(".product-card, .product-item, [data-product]"):
            name_el = item.select_one(".product-card__title, .product-title, h3, a[title]")
            price_el = item.select_one(".product-card__price, .price, .product-price")
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 0:
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price * 0.5, 2),  # Action already low, estimate 50% of retail
                    "market_price": round(price * 2.0, 2),
                    "platform": "eBay",
                    "source_location": "Netherlands",
                })
        return deals


class MediamarktNLScraper(DealScraper):
    """Mediamarkt.nl — clearance/outlet section."""
    country = "NL"
    currency = "EUR"
    source_name = "MediaMarkt NL Outlet"
    source_url = "https://www.mediamarkt.nl/nl/category/_open-box-983674.html"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select('[data-test="product-card"], .product-grid__item, article'):
            name_el = item.select_one('[data-test="product-title"], h3, .product-name')
            price_el = item.select_one('[data-test="price"], .price, [data-price]')
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 10:
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.4, 2),  # ~30% margin
                    "platform": "eBay",
                    "source_location": "Netherlands",
                })
        return deals


class MarktplaatsScraper(DealScraper):
    """Marktplaats.nl — largest NL marketplace (like FB Marketplace)."""
    country = "NL"
    currency = "EUR"
    source_name = "Marktplaats"
    source_url = "https://www.marktplaats.nl/q/nieuw-ingepakt/"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select('[data-testid="listing"], .hz-Listing, article'):
            name_el = item.select_one('[data-testid="title"], .title, h2')
            price_el = item.select_one('[data-testid="price"], .price, [class*="price"]')
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and 5 < price < 500:
                deals.append({
                    "product_name": f"[Marktplaats] {name}",
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.35, 2),
                    "platform": "Facebook Marketplace",
                    "source_location": "Netherlands",
                })
        return deals


# ─── Germany Scrapers ─────────────────────────────────────────────────

class MyDealzScraper(DealScraper):
    """MyDealz.de — Germany's largest deal community."""
    country = "DE"
    currency = "EUR"
    source_name = "MyDealz"
    source_url = "https://www.mydealz.de/new?page=1"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select(".thread, article, [data-thread-id]"):
            name_el = item.select_one(".thread-title, .topic-title, h2 a, a[title]")
            price_el = item.select_one(".thread-price, .price, .offer-price, [class*='price']")
            if not name_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "") if price_el else "0"
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                price = 0
            if name and price > 0:
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.5, 2),
                    "platform": "eBay",
                    "source_location": "Germany",
                    "estimated_margin_percent": 33.3,
                })
        return deals[:20]


class MediamarktDEScraper(DealScraper):
    """Mediamarkt.de — Restposten / Outlet."""
    country = "DE"
    currency = "EUR"
    source_name = "MediaMarkt DE Outlet"
    source_url = "https://www.mediamarkt.de/de/category/_outlet-983674.html"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select('[data-test="product-card"], article, .product-tile'):
            name_el = item.select_one('[data-test="product-title"], h3, .product-name')
            price_el = item.select_one('[data-test="price"], .price, .product-price')
            old_el = item.select_one('[data-test="old-price"], .old-price, .sr-only')
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 10:
                # If there's an old price, use it; else estimate market price
                if old_el:
                    old_text = old_el.get_text(strip=True).replace(",", ".").replace("€", "")
                    try:
                        market = float(re.findall(r"[\d.]+", old_text)[0])
                    except (IndexError, ValueError):
                        market = round(price * 1.35, 2)
                else:
                    market = round(price * 1.35, 2)
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price, 2),
                    "market_price": market,
                    "platform": "eBay",
                    "source_location": "Germany",
                })
        return deals


class LidlDEScraper(DealScraper):
    """Lidl.de — weekly specials (Angebote)."""
    country = "DE"
    currency = "EUR"
    source_name = "Lidl DE Angebote"
    source_url = "https://www.lidl.de/c/angebote"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select(".product-grid__item, [data-product-id], article"):
            name_el = item.select_one(".product__title, h3, .title")
            price_el = item.select_one(".price__main, .price, [class*='price']")
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "").replace("–", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 0:
                deals.append({
                    "product_name": f"[Lidl] {name}",
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.8, 2),
                    "platform": "eBay",
                    "source_location": "Germany",
                })
        return deals


# ─── Belgium Scrapers ────────────────────────────────────────────────

class TweedehandsScraper(DealScraper):
    """2dehands.be — Belgian marketplace."""
    country = "BE"
    currency = "EUR"
    source_name = "2dehands BE"
    source_url = "https://www.2dehands.be/l/nieuw-in-verpakking/"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select('[data-testid="listing"], .hz-Listing, article'):
            name_el = item.select_one('[data-testid="title"], .title, h2')
            price_el = item.select_one('[data-testid="price"], .price, [class*="price"]')
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and 5 < price < 500:
                deals.append({
                    "product_name": f"[2dehands] {name}",
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.35, 2),
                    "platform": "Facebook Marketplace",
                    "source_location": "Belgium",
                })
        return deals


class VandenBorreScraper(DealScraper):
    """Vanden Borre BE — open box / clearance."""
    country = "BE"
    currency = "EUR"
    source_name = "Vanden Borre Outlet"
    source_url = "https://www.vandenborre.be/open-box"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select(".product-card, article, [data-product]"):
            name_el = item.select_one(".product-card__title, h3, .product-name")
            price_el = item.select_one(".product-card__price, .price, .product-price, [data-price]")
            old_el = item.select_one(".old-price, .before, .strike")
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 10:
                if old_el:
                    old_text = old_el.get_text(strip=True).replace(",", ".").replace("€", "")
                    try:
                        market = float(re.findall(r"[\d.]+", old_text)[0])
                    except (IndexError, ValueError):
                        market = round(price * 1.4, 2)
                else:
                    market = round(price * 1.4, 2)
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price, 2),
                    "market_price": market,
                    "platform": "eBay",
                    "source_location": "Belgium",
                })
        return deals


class BolComScraper(DealScraper):
    """Bol.com — NL/BE marketplace, lightning deals."""
    country = "NL"
    currency = "EUR"
    source_name = "Bol.com Deals"
    source_url = "https://www.bol.com/nl/nl/l/aanbiedingen/"

    def parse(self, html):
        soup = BeautifulSoup(html, "lxml")
        deals = []
        for item in soup.select('[data-test="product-card"], .product-item, article'):
            name_el = item.select_one('[data-test="title"], h3, .product-title, a[title]')
            price_el = item.select_one('[data-test="price"], .price, .promo-price')
            if not name_el or not price_el:
                continue
            name = name_el.get_text(strip=True)
            price_text = price_el.get_text(strip=True).replace(",", ".").replace("€", "")
            try:
                price = float(re.findall(r"[\d.]+", price_text)[0])
            except (IndexError, ValueError):
                continue
            if name and price > 5:
                deals.append({
                    "product_name": name,
                    "sourcing_cost": round(price, 2),
                    "market_price": round(price * 1.5, 2),
                    "platform": "eBay",
                    "source_location": "Netherlands",
                })
        return deals


# ─── Scraper Registry ─────────────────────────────────────────────────

ALL_SCRAPERS: list[DealScraper] = [
    # Netherlands
    ActionScraper(),
    MediamarktNLScraper(),
    MarktplaatsScraper(),
    BolComScraper(),
    # Germany
    MyDealzScraper(),
    MediamarktDEScraper(),
    LidlDEScraper(),
    # Belgium
    TweedehandsScraper(),
    VandenBorreScraper(),
]


def run_all():
    """Run every scraper and return total deals found."""
    total = 0
    start = time.time()
    print("=" * 60)
    print("🌍 Margin Runner — International Scraper Run")
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
    """Run scrapers for a specific country (NL, DE, BE)."""
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