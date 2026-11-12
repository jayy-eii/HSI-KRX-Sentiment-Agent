"""FastAPI Application for HSI & KRX Sentiment Intelligence Pipeline.

Exposes endpoints for:
- Health check (GET /)
- Interactive web dashboard (GET /dashboard)
- Posts data explorer (GET /api/posts)
- Sentiment summary statistics (GET /api/summary)
- Scraper execution and dry-run (POST /api/scrape/dry-run, POST /api/scrape)
"""

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import config

PROJECT_ROOT = Path(__file__).resolve().parent
SCORED_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts_scored.csv"
RAW_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts.csv"
DASHBOARD_HTML = PROJECT_ROOT / "public" / "index.html"
if not DASHBOARD_HTML.exists():
    DASHBOARD_HTML = PROJECT_ROOT / "report" / "dashboard.html"

app = FastAPI(
    title="HSI & KRX Sentiment Intelligence API",
    description="Quantitative social sentiment & scraper API covering 10 HKEX and KRX equities.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_dataset() -> pd.DataFrame:
    """Load latest scored dataset or fallback to raw dataset."""
    target_csv = SCORED_CSV if SCORED_CSV.exists() else RAW_CSV
    if not target_csv.exists():
        raise HTTPException(status_code=404, detail="Processed dataset not found.")
    df = pd.read_csv(target_csv, encoding="utf-8-sig")
    return df.fillna({
        "gemini_sentiment_score": 0.0,
        "gemini_sentiment_label": "neutral",
        "gemini_confidence": 0.5,
        "gemini_reasoning": "",
        "likes": 0,
        "views": 0,
        "replies": 0,
        "reposts": 0,
    })


@app.get("/", tags=["Health Check"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint exposing system status and dataset metrics."""
    data_loaded = SCORED_CSV.exists() or RAW_CSV.exists()
    post_count = 0
    if data_loaded:
        try:
            df = load_dataset()
            post_count = len(df)
        except Exception:
            pass

    return {
        "status": "healthy",
        "service": "HSI & KRX Sentiment Intelligence API",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_ready": data_loaded,
        "total_posts_indexed": post_count,
        "tracked_equities_count": len(config.ASSETS),
        "endpoints": {
            "health_check": "/",
            "interactive_dashboard": "/dashboard",
            "posts_explorer": "/api/posts",
            "sentiment_summary": "/api/summary",
            "scraper_dry_run": "/api/scrape/dry-run",
            "api_documentation": "/docs",
        },
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    """Serves the standalone interactive Chart.js & Tailwind dashboard."""
    if DASHBOARD_HTML.exists():
        return HTMLResponse(content=DASHBOARD_HTML.read_text(encoding="utf-8"), status_code=200)
    raise HTTPException(status_code=404, detail="Dashboard HTML template not found.")


@app.get("/api/posts", tags=["Data Explorer"])
def get_posts(
    ticker: Optional[str] = Query(None, description="Filter by ticker (e.g. 0700.HK, 005930.KS)"),
    exchange: Optional[str] = Query(None, description="Filter by exchange (HK or KR)"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (bullish, bearish, neutral)"),
    source: Optional[str] = Query(None, description="Filter by source (naver, lihkg, telegram)"),
    limit: int = Query(50, ge=1, le=500, description="Number of posts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> Dict[str, Any]:
    """Query and filter scored social sentiment posts across HKEX and KRX."""
    df = load_dataset()

    if ticker:
        df = df[df["ticker"].str.upper() == ticker.upper()]
    if exchange:
        df = df[df["exchange"].str.upper() == exchange.upper()]
    if sentiment and "gemini_sentiment_label" in df.columns:
        df = df[df["gemini_sentiment_label"].str.lower() == sentiment.lower()]
    if source:
        df = df[df["source"].str.lower() == source.lower()]

    total_matched = len(df)
    paginated = df.iloc[offset : offset + limit]
    records = paginated.to_dict(orient="records")

    return {
        "total_matched": total_matched,
        "offset": offset,
        "limit": limit,
        "count": len(records),
        "posts": records,
    }


@app.get("/api/summary", tags=["Sentiment Analytics"])
def get_sentiment_summary() -> Dict[str, Any]:
    """Retrieve aggregate market sentiment metrics by ticker and exchange."""
    df = load_dataset()

    sentiment_distribution = {}
    if "gemini_sentiment_label" in df.columns:
        sentiment_distribution = df["gemini_sentiment_label"].value_counts().to_dict()

    ticker_stats = []
    if "gemini_sentiment_score" in df.columns:
        grouped = df.groupby(["exchange", "ticker"]).agg(
            total_posts=("post_id", "count"),
            mean_sentiment=("gemini_sentiment_score", "mean"),
            mean_confidence=("gemini_confidence", "mean"),
        ).reset_index()

        for _, row in grouped.iterrows():
            ticker_stats.append({
                "exchange": row["exchange"],
                "ticker": row["ticker"],
                "total_posts": int(row["total_posts"]),
                "mean_sentiment": round(float(row["mean_sentiment"]), 3),
                "mean_confidence": round(float(row["mean_confidence"]), 2),
            })

    return {
        "total_posts": len(df),
        "sentiment_distribution": sentiment_distribution,
        "ticker_breakdown": ticker_stats,
    }


@app.post("/api/scrape/dry-run", tags=["Scraper Management"])
def scrape_dry_run(exchange: Optional[str] = None) -> Dict[str, Any]:
    """Dry-run planned scraper queries, target actors, and estimated Apify spend ($0.00 cost)."""
    try:
        from scrapers.apify_scraper import ProductionApifyScraper

        scraper = ProductionApifyScraper()
        tickers = [
            t for t, data in config.ASSETS.items()
            if exchange is None or data.get("exchange", "").upper() == exchange.upper()
        ]
        plan = scraper.plan_queries(tickers)
        total_estimated_cost = sum(item.get("worst_case_cost_usd", 0.0) for item in plan)

        return {
            "status": "dry_run_success",
            "planned_tasks_count": len(plan),
            "estimated_max_cost_usd": round(total_estimated_cost, 4),
            "safe_budget_limit_usd": scraper.budget_usd,
            "tasks_preview": plan[:10],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dry-run inspection failed: {str(exc)}")


@app.post("/api/scrape", tags=["Scraper Management"])
def trigger_scrape(
    exchange: Optional[str] = Query(None, description="Exchange to scrape: HK, KR, or None for all"),
    dry_run: bool = Query(True, description="Default True for budget safety"),
) -> Dict[str, Any]:
    """Trigger the production Apify scraping pipeline (defaults to safe dry-run)."""
    if dry_run:
        return scrape_dry_run(exchange=exchange)

    # Verify API token is configured in environment
    try:
        token = config.get_apify_token(required=True)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="APIFY_TOKEN is not set in environment variables. Add APIFY_TOKEN in Vercel settings.",
        )

    try:
        from scrapers.apify_scraper import ProductionApifyScraper
        from apify_client import ApifyClient

        client = ApifyClient(token)
        scraper = ProductionApifyScraper(client=client)
        tickers = [
            t for t, data in config.ASSETS.items()
            if exchange is None or data.get("exchange", "").upper() == exchange.upper()
        ]
        plan = scraper.plan_queries(tickers)
        results = scraper.execute_plan(plan)
        return {
            "status": "scrape_completed",
            "total_items_scraped": len(results),
            "exchange": exchange or "ALL",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scraping run failed: {str(exc)}")
