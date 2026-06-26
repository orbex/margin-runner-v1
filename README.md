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

The database seeds itself with 25 deals on first run. No setup needed.

## Deploy to a Free Host

### Render
1. Push this repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Connect your repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Deploy — you'll get a `https://your-app.onrender.com` URL

### Railway
1. Push to GitHub
2. Create a new project on [Railway](https://railway.app)
3. Set start command: `cd backend && python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT`

### Fly.io
```bash
fly launch
fly deploy
```

## Structure

```
├── backend/
│   ├── main.py            # FastAPI server (API + static files)
│   └── database.py        # Self-contained SQLite DB (auto-seeds 25 deals)
├── static/
│   ├── index.html         # Dashboard — KPIs, top deals, progress bar
│   ├── buys.html          # Full deal pipeline with search/filter
│   └── sales.html         # Sales tracking (fills as you sell)
├── docs/
│   ├── buying_plan.md     # Verified sourcing links & ROI
│   ├── listing_content.md # Optimized listing copy
│   └── ops/               # Margin calculator, dashboard tools
├── Procfile               # Render / Heroku deployment
├── runtime.txt            # Python version
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