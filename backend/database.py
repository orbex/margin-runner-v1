"""
Margin Runner — Database Layer
Self-contained SQLite database for the arbitrage dashboard.
Creates tables and seeds data on first run. No external dependencies.
"""
import sqlite3
import os
import json
from pathlib import Path

# Database path — configurable via env var, defaults to local file
DB_PATH = os.environ.get("MARGIN_RUNNER_DB", str(Path(__file__).parent / "margin_runner.db"))


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables and seed data if the database is empty."""
    conn = get_connection()
    cursor = conn.cursor()

    # --- Schema ---
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            sourcing_cost REAL NOT NULL,
            market_price REAL NOT NULL,
            platform TEXT,
            estimated_fees REAL,
            estimated_margin REAL,
            estimated_margin_percent REAL,
            source_url TEXT,
            status TEXT DEFAULT 'new',
            date_found DATETIME DEFAULT CURRENT_TIMESTAMP,
            sourcing_agent_id TEXT,
            source_location TEXT,
            source_website TEXT
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER,
            product_name TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            status TEXT DEFAULT 'received',
            listing_price REAL,
            platform TEXT,
            sku TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals (id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            sale_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            sale_price REAL NOT NULL,
            platform_fees REAL,
            shipping_cost REAL,
            tax REAL,
            net_profit REAL,
            actual_margin_percent REAL,
            FOREIGN KEY (inventory_id) REFERENCES inventory (id)
        );
    """)

    # --- Seed data if empty ---
    count = cursor.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    if count == 0:
        _seed_deals(cursor)
        conn.commit()
        print(f"✅ Database initialized with seed data at {DB_PATH}")
    else:
        print(f"📦 Database already has {count} deals")

    conn.close()


def _seed_deals(cursor):
    """Populate with the current deal pipeline (25 deals from clean pipeline)."""
    deals = [
        # (product_name, sourcing_cost, market_price, platform, estimated_margin_percent, source_website)
        ("TERUNSOUl Headset V5.3", 5.99, 37.99, "amazon", 51.68, "Woot"),
        ("JBL Control 442C/T (Pair)", 89.99, 312.00, "amazon", 50.01, "Woot"),
        ("SYNCO Wireless Mic USB-C", 9.99, 39.99, "amazon", 42.27, "Woot"),
        ("Apple Watch Sport Band", 14.99, 49.00, "amazon", 38.62, "Woot"),
        ("myCharge MagLock 2-pack", 19.99, 59.99, "amazon", 37.68, "Woot"),
        ("Milwaukee M12 Drill", 59.00, 129.00, "amazon", 28.93, "Woot"),
        ("VIZIO 55 inch Quantum 4K QLED TV", 228.00, 349.99, "Facebook Marketplace", 28.34, "Walmart"),
        ("Apple Lightning to USB-C 1M", 4.99, 19.00, "amazon", 25.66, "Woot"),
        ("DeWalt 20V Battery 2-pack", 79.00, 159.00, "amazon", 25.39, "Woot"),
        ("Full Moon Chicken Jerky 24oz", 6.64, 22.00, "amazon", 25.30, "Amazon"),
        ("Bowers & Wilkins Pi6 ANC Earbuds", 79.99, 161.17, "Amazon", 24.47, "Woot"),
        ("Belkin Quick Charge Pad 2-pack", 9.99, 26.99, "amazon", 22.41, "Woot"),
        ("LEGO Star Wars Advent Calendar", 20.00, 45.00, "amazon", 22.39, "Walmart"),
        ("LEGO Bricks Bricks Bricks", 30.00, 60.00, "amazon", 19.33, "Walmart"),
        ("Chicken of the Sea Tuna 48-pack", 23.55, 48.00, "amazon", 18.07, "Amazon"),
        ("Energizer MAX D 8-pack", 4.99, 16.39, "amazon", 16.45, "Woot"),
        ("Slime Digital Tire Gauge", 4.99, 15.87, "amazon", 14.26, "Amazon"),
        ("Rayovac AA Fusion 16pk", 4.99, 14.97, "amazon", 10.09, "Woot"),
        ("Sony HT-A5000 5.1.2ch Soundbar", 296.99, 429.99, "Amazon", 4.33, "Best Buy"),
        ("8BitDo Pro 3 Bluetooth Controller", 37.59, 59.99, "Amazon", 2.65, "Woot"),
        ("Electric Precision Screwdriver (80 bits)", 19.99, 35.92, "Amazon", 2.38, "Woot"),
        ("LEGO Mandalorian Battle Pack", 10.00, 20.00, "amazon", 1.00, "Walmart"),
        ("JandCase Night Lights 2-pack", 4.01, 12.00, "amazon", 0.91, "Amazon"),
        ("Cape Cod Variety Pack Chips", 8.61, 18.00, "amazon", 0.33, "Amazon"),
        ("Energizer 2032 4-pack", 3.49, 9.99, "amazon", -9.98, "Woot"),
    ]

    cursor.executemany(
        """INSERT INTO deals 
           (product_name, sourcing_cost, market_price, platform, 
            estimated_margin_percent, source_website, status)
           VALUES (?, ?, ?, ?, ?, ?, 'new')""",
        deals
    )


def query(sql: str, params: tuple = ()) -> list:
    """Run a SELECT query and return list of dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def execute(sql: str, params: tuple = ()) -> int:
    """Run an INSERT/UPDATE/DELETE and return lastrowid."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


# Initialize on import
init_db()