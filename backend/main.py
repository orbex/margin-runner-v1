"""
Margin Runner — Web Dashboard
FastAPI backend serving deal pipeline, buys, and sales data.
Self-contained — uses local SQLite database, no external dependencies.
Includes: international scrapers, country filtering, inventory management.
"""
from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import query

app = FastAPI(title="Margin Runner Dashboard")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ─── Helper ──────────────────────────────────────────────────────────

def get_deals_raw(where: str = "1=1", order: str = "estimated_margin_percent DESC"):
    """Generic deal query with filters."""
    return query(
        f"SELECT id, product_name, sourcing_cost, market_price, "
        f"estimated_fees, estimated_margin, estimated_margin_percent, "
        f"platform, source_website, source_location, status, date_found, "
        f"country, currency "
        f"FROM deals WHERE {where} ORDER BY {order}"
    )


# ─── Core API ────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard():
    """Aggregate KPIs and top deals for the dashboard overview."""
    all_deals = get_deals_raw("status = 'new'")
    nl = get_deals_raw("status = 'new' AND country = 'NL'")
    de = get_deals_raw("status = 'new' AND country = 'DE'")
    be = get_deals_raw("status = 'new' AND country = 'BE'")
    us = get_deals_raw("status = 'new' AND (country IS NULL OR country = 'US')")

    def pipeline_value(ds):
        return round(sum(d.get("market_price") or 0 for d in ds), 2)

    def avg_margin(ds):
        if not ds:
            return 0
        return round(sum(d.get("estimated_margin_percent") or 0 for d in ds) / len(ds), 2)

    inv = query(
        "SELECT COUNT(*) as c, COALESCE(SUM(purchase_price),0) as t "
        "FROM inventory WHERE status != 'sold'"
    )
    sales = query(
        "SELECT COUNT(*) as c, COALESCE(SUM(net_profit),0) as t FROM sales"
    )

    return {
        "total_deals": len(all_deals),
        "total_pipeline_value": pipeline_value(all_deals),
        "avg_margin_percent": avg_margin(all_deals),
        "weekly_profit_target": 2000.0,
        "current_weekly_profit": round(sales[0]["t"], 2) if sales else 0,
        "inventory_count": inv[0]["c"] if inv else 0,
        "inventory_cost": round(inv[0]["t"], 2) if inv else 0,
        "sales_count": sales[0]["c"] if sales else 0,
        "top_deals": all_deals[:5],
        # Country breakdown
        "by_country": {
            "NL": {"count": len(nl), "value": pipeline_value(nl), "avg_margin": avg_margin(nl)},
            "DE": {"count": len(de), "value": pipeline_value(de), "avg_margin": avg_margin(de)},
            "BE": {"count": len(be), "value": pipeline_value(be), "avg_margin": avg_margin(be)},
            "US": {"count": len(us), "value": pipeline_value(us), "avg_margin": avg_margin(us)},
        },
    }


@app.get("/api/deals")
def get_deals(country: str = Query(None, regex="^(NL|DE|BE|US)?$")):
    """Full deals pipeline, optionally filtered by country."""
    if country:
        w = f"status = 'new' AND country = '{country}'"
    else:
        w = "status = 'new'"
    return {"deals": get_deals_raw(w)}


@app.get("/api/sales")
def get_sales():
    s = query(
        "SELECT s.id, s.inventory_id, s.sale_price, s.platform_fees, "
        "s.shipping_cost, s.tax, s.net_profit, s.actual_margin_percent, "
        "s.sale_date, i.product_name "
        "FROM sales s LEFT JOIN inventory i ON s.inventory_id = i.id "
        "ORDER BY s.sale_date DESC"
    )
    return {"sales": s}


@app.get("/api/inventory")
def get_inventory():
    items = query(
        "SELECT id, deal_id, product_name, purchase_price, "
        "purchase_date, source, status, listing_price, platform "
        "FROM inventory ORDER BY purchase_date DESC"
    )
    return {"inventory": items}


# ─── Scraper Endpoints ───────────────────────────────────────────────

@app.post("/api/scrape")
def trigger_scrape(country: str = Query(None, regex="^(NL|DE|BE)?$")):
    """Run scrapers and import deals into the database."""
    from scrapers.engine import run_all, run_country
    try:
        if country:
            total = run_country(country)
            return {"status": "ok", "country": country, "deals_found": total}
        else:
            total = run_all()
            return {"status": "ok", "deals_found": total}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/scrape/status")
def scraper_status():
    """List available scrapers and their sources."""
    from scrapers.engine import ALL_SCRAPERS
    return {
        "scrapers": [
            {"name": s.source_name, "country": s.country, "url": s.source_url}
            for s in ALL_SCRAPERS
        ]
    }


# ─── Frontend ────────────────────────────────────────────────────────

@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{page}")
def serve_page(page: str):
    if page in ("buys", "sales", "inventory", "scrapers"):
        return FileResponse(STATIC_DIR / f"{page}.html")
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)