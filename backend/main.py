"""
Margin Runner — Web Dashboard
FastAPI backend serving deal pipeline, buys, and sales data.
Self-contained — uses local SQLite database, no external dependencies.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import query

app = FastAPI(title="Margin Runner Dashboard")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
HERE = Path(__file__).parent


# --- API Endpoints ---

@app.get("/api/dashboard")
def get_dashboard():
    """Aggregate KPIs and top deals for the dashboard overview."""
    deals = query(
        "SELECT id, product_name, sourcing_cost, market_price, "
        "estimated_margin_percent, platform, status "
        "FROM deals WHERE status = 'new' "
        "ORDER BY estimated_margin_percent DESC"
    )

    total_deals = len(deals)
    total_pipeline_value = sum(d["market_price"] or 0 for d in deals)
    avg_margin = (
        sum(d["estimated_margin_percent"] or 0 for d in deals) / total_deals
        if total_deals > 0
        else 0
    )

    inv_stats = query(
        "SELECT COUNT(*) as count, "
        "COALESCE(SUM(purchase_price), 0) as total_cost "
        "FROM inventory WHERE status != 'sold'"
    )
    inv_count = inv_stats[0]["count"] if inv_stats else 0
    inv_cost = inv_stats[0]["total_cost"] if inv_stats else 0

    sales_stats = query(
        "SELECT COUNT(*) as count, "
        "COALESCE(SUM(net_profit), 0) as total_profit "
        "FROM sales"
    )
    sales_count = sales_stats[0]["count"] if sales_stats else 0
    total_profit = sales_stats[0]["total_profit"] if sales_stats else 0.0

    top_deals = deals[:5] if deals else []

    return {
        "total_deals": total_deals,
        "total_pipeline_value": round(total_pipeline_value, 2),
        "avg_margin_percent": round(avg_margin, 2),
        "weekly_profit_target": 2000.0,
        "current_weekly_profit": round(total_profit, 2),
        "progress_percent": round((total_profit / 2000) * 100, 1) if total_profit > 0 else 0,
        "inventory_count": inv_count,
        "inventory_cost": round(inv_cost, 2),
        "sales_count": sales_count,
        "top_deals": top_deals,
    }


@app.get("/api/deals")
def get_deals():
    """Full deals pipeline."""
    deals = query(
        "SELECT id, product_name, sourcing_cost, market_price, "
        "estimated_fees, estimated_margin, estimated_margin_percent, "
        "platform, source_website, source_location, status, date_found "
        "FROM deals ORDER BY estimated_margin_percent DESC"
    )
    return {"deals": deals}


@app.get("/api/sales")
def get_sales():
    """Sales history — real data if exists, empty array if not."""
    sales = query(
        "SELECT s.id, s.inventory_id, s.sale_price, s.platform_fees, "
        "s.shipping_cost, s.tax, s.net_profit, s.actual_margin_percent, "
        "s.sale_date, i.product_name "
        "FROM sales s LEFT JOIN inventory i ON s.inventory_id = i.id "
        "ORDER BY s.sale_date DESC"
    )
    return {"sales": sales}


@app.get("/api/inventory")
def get_inventory():
    """Current inventory."""
    items = query(
        "SELECT id, deal_id, product_name, purchase_price, "
        "purchase_date, source, status, listing_price, platform "
        "FROM inventory ORDER BY purchase_date DESC"
    )
    return {"inventory": items}


# --- Serve Frontend ---

@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/{page}")
def serve_page(page: str):
    if page in ("buys", "sales", "inventory"):
        return FileResponse(STATIC_DIR / f"{page}.html")
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(__import__('os').environ.get("PORT", 8000)), reload=False)