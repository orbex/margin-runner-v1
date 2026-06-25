# Margin Runner

**Arbitrage business dashboard — track deals, buys, and sales.**  
Target: $2,000/week net profit.

## Quick Start

```bash
pip install -r requirements.txt
cd backend
python3 main.py
# Open http://localhost:8000
```

## Structure

```
├── backend/
│   └── main.py            # FastAPI server (API + static files)
├── static/
│   ├── index.html         # Dashboard — KPIs, top deals, progress
│   ├── buys.html          # Full deal pipeline with search/filter
│   └── sales.html         # Sales tracking (fills as you sell)
├── docs/
│   ├── buying_plan.md     # Verified sourcing links & ROI
│   ├── listing_content.md # Optimized listing copy
│   └── ops/               # Margin calculator, dashboard tools
└── requirements.txt
```

## API Endpoints

| Endpoint | Returns |
|---|---|
| `/api/dashboard` | KPIs + top 5 deals |
| `/api/deals` | Full pipeline (25 deals) |
| `/api/sales` | Sales history |
| `/api/inventory` | Current inventory |

## Strategy

- **eBay-first** — outperforms Amazon FBA for items under $300
- **Marketplace** — for bulky items (TVs, furniture) — 0% fees
- **Amazon FBA** — only for items over $300
- **5% safety buffer** on all costs