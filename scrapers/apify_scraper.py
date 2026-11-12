"""Production Apify Scraper for Hong Kong & South Korean Market Sentiment.

Collects discussion posts for HKEX and KRX equities across four verified actors:
- KR/naver:    hgservices~naver-stock-discussion-scraper (Naver stock boards)
- HK/lihkg:    claude_code_reviewer~lihkg-scraper-en (LIHKG forum)
- HK/telegram: lofomachines~telegram-keyword-search-scraper (Telegram public channels)
  Fallback:    tri_angle~telegram-scraper (Telegram profile/channel scraper)
- KR/blind:    hypebridge~blind-post-scraper (TeamBlind professional community)

Execution Order (most useful sources finish first):
1. naver
2. lihkg
3. telegram
4. blind

Normalized Schema (17 columns):
exchange, source, ticker, post_id, timestamp_utc, text, likes, dislikes,
reposts, replies, views, author, author_followers, url, query, language,
source_native_sentiment

Timezone Handling Logic:
- LIHKG: Timestamps originate in Hong Kong local time (Asia/Hong_Kong, UTC+8).
  If naive, localized to Asia/Hong_Kong and converted to UTC.
  If already timezone-aware (e.g. trailing 'Z'), converted directly to UTC.
- Naver: Discussion timestamps originate in Korea Standard Time (Asia/Seoul, UTC+9).
  If naive, localized to Asia/Seoul and converted to UTC.
  If already timezone-aware (e.g. '+09:00'), converted directly to UTC.
- Telegram & Blind: Standard ISO8601 UTC offsets or 'Z'. Naive timestamps default to UTC.
Output timestamps are formatted as ISO8601 UTC strings (YYYY-MM-DDTHH:MM:SSZ).
"""

import argparse
import json
import logging
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
import pandas as pd
from apify_client import ApifyClient

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("apify_scraper")

# Normalized CSV Schema Columns
NORMALIZED_COLUMNS = [
    "exchange",
    "source",
    "ticker",
    "post_id",
    "timestamp_utc",
    "text",
    "likes",
    "dislikes",
    "reposts",
    "replies",
    "views",
    "author",
    "author_followers",
    "url",
    "query",
    "language",
    "source_native_sentiment",
]

# Source execution pipeline (exchange, source) in priority order
SOURCE_PIPELINE: List[Tuple[str, str]] = [
    ("KR", "naver"),
    ("HK", "lihkg"),
    ("HK", "telegram"),
    ("KR", "telegram"),
]

# Actor definitions & proportional caps ensuring all runs stay within budget
ACTOR_CONFIGS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("KR", "naver"): {
        "actor_id": "hgservices~naver-stock-discussion-scraper",
        "exchange": "KR",
        "source": "naver",
        "default_max_items": 200,   # 200 posts per stock
        "default_max_charge": 0.15, # 5 * 0.15 = $0.75 worst-case
        "default_tz": "Asia/Seoul",
        "default_lang": "ko",
    },
    ("HK", "lihkg"): {
        "actor_id": "claude_code_reviewer~lihkg-scraper-en",
        "exchange": "HK",
        "source": "lihkg",
        "default_max_items": 30,    # 30 items per ticker
        "default_max_charge": 0.08, # 5 * 0.08 = $0.40 worst-case
        "default_tz": "Asia/Hong_Kong",
        "default_lang": "zh",
    },
    ("HK", "telegram"): {
        "actor_id": "lofomachines~telegram-keyword-search-scraper",
        "fallback_actor_id": "tri_angle~telegram-scraper",
        "exchange": "HK",
        "source": "telegram",
        "default_max_items": 100,
        "default_max_charge": 0.08, # 5 * 0.08 = $0.40 worst-case
        "default_tz": "UTC",
        "default_lang": "zh",
    },
    ("KR", "telegram"): {
        "actor_id": "lofomachines~telegram-keyword-search-scraper",
        "fallback_actor_id": "tri_angle~telegram-scraper",
        "exchange": "KR",
        "source": "telegram",
        "default_max_items": 30,    # 30 items per keyword
        "default_max_charge": 0.08, # 5 * 0.08 = $0.40 worst-case
        "default_tz": "UTC",
        "default_lang": "ko",
    },
}

# Telegram Finance Relevance Terms (Hong Kong / Chinese)
TELEGRAM_FINANCE_TERMS = [
    "股", "股價", "股价", "港股", "目標價", "目标价", "升", "跌",
    "買入", "沽", "牛", "熊", "財報", "业绩", "業績", "stock",
    "shares", "price target", "bullish", "bearish"
]

# Korean Telegram Finance Relevance Terms
KOREAN_FINANCE_TERMS = [
    "주가", "주식", "목표가", "매수", "매도", "상승", "하락",
    "급등", "급락", "실적", "종목", "개미", "외인", "코스피", "반등"
]

# Event rate reference table for cost tracking
EVENT_RATES = {
    "hgservices~naver-stock-discussion-scraper": {
        "apify-actor-start": 0.00005,
        "stock-checked": 0.002,
        "post": 0.0025,
    },
    "hypebridge~blind-post-scraper": {
        "apify-default-dataset-item": 0.0225,
    },
    "lofomachines~telegram-keyword-search-scraper": {
        "apify-actor-start": 0.00005,
        "apify-default-dataset-item": 0.0025,
    },
    "claude_code_reviewer~lihkg-scraper-en": {
        "apify-actor-start": 0.005,
        "search-listing": 0.002,
        "product-detail": 0.008,
        "review-item": 0.003,
        "ai-label": 0.002,
    },
}


def to_dict(obj: Any) -> Dict[str, Any]:
    """Convert SDK model, dataclass, or dictionary to standard dict."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return vars(obj)
    return {}


def parse_to_utc_iso(
    dt_val: Any, default_tz: str = "UTC"
) -> Tuple[Optional[str], Optional[datetime]]:
    """Parse various timestamp formats and convert to ISO8601 UTC string.

    Timezone Logic:
    - If dt_val is already timezone-aware (contains explicit offset or 'Z'),
      it is converted directly to UTC.
    - If dt_val is naive (no timezone metadata), it is localized using the platform's
      native timezone (Asia/Hong_Kong for LIHKG, Asia/Seoul for Naver, UTC for Telegram/Blind),
      then converted to UTC.
    """
    if not dt_val:
        return None, None
    try:
        if isinstance(dt_val, (int, float)):
            if dt_val > 1e11:
                dt_obj = datetime.fromtimestamp(dt_val / 1000.0, tz=timezone.utc)
            else:
                dt_obj = datetime.fromtimestamp(dt_val, tz=timezone.utc)
            return dt_obj.strftime("%Y-%m-%dT%H:%M:%SZ"), dt_obj

        dt_str = str(dt_val).strip()
        dt_obj = date_parser.parse(dt_str)
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=ZoneInfo(default_tz))

        utc_dt = dt_obj.astimezone(timezone.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), utc_dt
    except Exception:
        return None, None


def is_telegram_post_relevant(
    text: str, ticker: str, asset_cfg: Dict[str, Any], exchange: str = "HK"
) -> bool:
    """Tightened Telegram relevance filter for HK and KR.

    For HK:
    Keep a post ONLY if:
    (a) it contains the ticker code in a stock-like form (0700, 00700, $0700, 700.HK, etc. for each ticker), OR
    (b) it contains the Chinese company name (traditional or simplified, e.g. 騰訊/腾讯, 阿里巴巴/阿里, 美團/美团, 小米, 滙豐/汇丰)
        AND at least one finance term.
    A bare English company name alone is NOT enough.

    For KR:
    Keep a post ONLY if:
    (a) it contains the ticker code in a stock-like form (005930, $005930, etc.), OR
    (b) it contains the Korean company name/alias (삼성전자/삼전, SK하이닉스/하이닉스, 네이버, 카카오, 현대차/현대자동차)
        AND at least one Korean finance term (주가, 주식, 목표가, 매수, 매도, 상승, 하락, 급등, 급락, 실적, 종목, 개미, 외인, 코스피, 반등).
    """
    if not text:
        return False
    text_lower = text.lower()

    if exchange == "KR":
        # (a) Check Korean ticker code in stock-like form
        stock_like = asset_cfg.get("stock_like_tickers") or [
            asset_cfg.get("plain_ticker", "").lower(),
            f"${asset_cfg.get('plain_ticker', '').lower()}",
        ]
        for stk in stock_like:
            if stk and stk.lower() in text_lower:
                return True

        # (b) Check Korean company name / alias + at least one Korean finance term
        korean_names = asset_cfg.get("korean_names") or [asset_cfg.get("name_local", "")]
        has_korean_name = any(kn and kn.lower() in text_lower for kn in korean_names)
        if has_korean_name:
            has_finance_term = any(term in text for term in KOREAN_FINANCE_TERMS)
            if has_finance_term:
                return True
        return False

    # Default to HK logic
    # (a) Check ticker code in stock-like form
    stock_like = asset_cfg.get("stock_like_tickers") or [
        asset_cfg.get("plain_ticker", "").lower(),
        asset_cfg.get("yfinance_ticker", "").lower(),
        f"${asset_cfg.get('plain_ticker', '').lower()}",
    ]
    for stk in stock_like:
        if stk and stk.lower() in text_lower:
            return True

    # (b) Check Chinese company name + at least one finance term
    chinese_names = asset_cfg.get("chinese_names") or [asset_cfg.get("name_local", "")]
    has_chinese_name = any(cn and cn.lower() in text_lower for cn in chinese_names)
    if has_chinese_name:
        has_finance_term = any(term.lower() in text_lower for term in TELEGRAM_FINANCE_TERMS)
        if has_finance_term:
            return True

    return False


def get_actual_run_cost(client: ApifyClient, run_id: str, actor_id: str) -> Tuple[float, float, float]:
    """Fetch updated run object from Apify to determine actual cost.

    Returns:
        (usage_total_usd, charged_events_usd, effective_cost)
    """
    time.sleep(1.0)  # Brief grace period for event settlement
    try:
        run_obj = client.run(run_id).get()
        run_dict = to_dict(run_obj)

        usage_total = float(run_dict.get("usage_total_usd") or run_dict.get("usageTotalUsd") or 0.0)

        # 1. Try event_usage directly
        event_usage = run_dict.get("event_usage") or run_dict.get("eventUsage") or {}
        charged_events_usd = 0.0
        if isinstance(event_usage, dict) and event_usage:
            for ev_data in event_usage.values():
                if isinstance(ev_data, dict):
                    charged_events_usd += float(ev_data.get("event_total_usd") or ev_data.get("eventTotalUsd") or 0.0)

        # 2. If event_usage not populated, compute from charged_event_counts and reference table
        if charged_events_usd == 0.0:
            counts = run_dict.get("charged_event_counts") or run_dict.get("chargedEventCounts") or {}
            rates = EVENT_RATES.get(actor_id, {})
            for ev_name, count in counts.items():
                rate = rates.get(ev_name, 0.0)
                charged_events_usd += float(count) * rate

        effective_cost = max(usage_total, charged_events_usd)
        return usage_total, charged_events_usd, effective_cost
    except Exception as exc:
        logger.warning("Could not fetch full cost details for run %s: %s", run_id, exc)
        return 0.0, 0.0, 0.0


# ---------------------------------------------------------------------------
# Item Normalization Functions
# ---------------------------------------------------------------------------

def normalize_lihkg_item(
    item: Dict[str, Any], ticker: str, query: str, cutoff_dt: datetime
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Normalize raw LIHKG item to schema."""
    post_id = str(item.get("thread_id") or "")
    if not post_id:
        return None, "missing_post_id"

    iso_str, dt_obj = parse_to_utc_iso(item.get("created_at"), default_tz="Asia/Hong_Kong")
    if dt_obj and dt_obj < cutoff_dt:
        return None, "older_than_cutoff"

    title = str(item.get("title") or "").strip()
    content = str(item.get("content") or item.get("own_text") or "").strip()
    text = f"{title}\n\n{content}" if title and content else (title or content)

    row = {
        "exchange": "HK",
        "source": "lihkg",
        "ticker": ticker,
        "post_id": post_id,
        "timestamp_utc": iso_str,
        "text": text,
        "likes": item.get("like_count"),
        "dislikes": item.get("dislike_count"),
        "reposts": None,
        "replies": item.get("reply_count"),
        "views": None,
        "author": item.get("author"),
        "author_followers": None,
        "url": item.get("thread_url") or f"https://lihkg.com/thread/{post_id}/page/1",
        "query": query,
        "language": "zh",
        "source_native_sentiment": item.get("ai_sentiment"),
    }
    return row, "ok"


def normalize_telegram_item(
    item: Dict[str, Any], ticker: str, query: str, cutoff_dt: datetime, exchange: str = "HK"
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Normalize raw Telegram item to schema."""
    post_id = str(item.get("id") or item.get("messageId") or "")
    if not post_id:
        return None, "missing_post_id"

    raw_date = item.get("date") or item.get("processed_at")
    iso_str, dt_obj = parse_to_utc_iso(raw_date, default_tz="UTC")
    if dt_obj and dt_obj < cutoff_dt:
        return None, "older_than_cutoff"

    text = str(item.get("text") or "").strip()

    reactions = item.get("reactions")
    likes = 0
    if isinstance(reactions, dict):
        likes = sum(v for v in reactions.values() if isinstance(v, (int, float)))
    elif isinstance(reactions, (int, float)):
        likes = int(reactions)
    elif item.get("likes") is not None:
        likes = item.get("likes")

    reposts = item.get("shares") or item.get("forwards")
    views = item.get("view_count") or item.get("views")

    channel_info = item.get("channel_info") or {}
    author_followers = channel_info.get("subscribers") if isinstance(channel_info, dict) else None
    author = str(item.get("sender") or item.get("source_name") or "")

    row = {
        "exchange": exchange,
        "source": "telegram",
        "ticker": ticker,
        "post_id": post_id,
        "timestamp_utc": iso_str,
        "text": text,
        "likes": likes,
        "dislikes": None,
        "reposts": reposts,
        "replies": None,
        "views": views,
        "author": author,
        "author_followers": author_followers,
        "url": item.get("source_url") or item.get("url"),
        "query": query,
        "language": "ko" if exchange == "KR" else "zh",
        "source_native_sentiment": None,
    }
    return row, "ok"
    return row, "ok"


def normalize_naver_item(
    item: Dict[str, Any], ticker: str, query: str, cutoff_dt: datetime
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Normalize raw Naver item to schema. (Every post from discussion board is relevant)."""
    if item.get("type") == "notice":
        return None, "notice_skipped"

    post_id = str(item.get("postId") or "")
    if not post_id:
        return None, "missing_post_id"

    raw_date = item.get("writtenAt") or item.get("createdAt")
    iso_str, dt_obj = parse_to_utc_iso(raw_date, default_tz="Asia/Seoul")
    if dt_obj and dt_obj < cutoff_dt:
        return None, "older_than_cutoff"

    title = str(item.get("title") or "").strip()
    body = str(item.get("text") or item.get("content") or "").strip()
    text = f"{title}\n\n{body}" if title and body else (title or body)

    row = {
        "exchange": "KR",
        "source": "naver",
        "ticker": ticker,
        "post_id": post_id,
        "timestamp_utc": iso_str,
        "text": text,
        "likes": item.get("likes"),
        "dislikes": item.get("dislikes"),
        "reposts": None,
        "replies": None,
        "views": item.get("views"),
        "author": item.get("author"),
        "author_followers": None,
        "url": item.get("url"),
        "query": query,
        "language": "ko",
        "source_native_sentiment": None,
    }
    return row, "ok"


def normalize_blind_item(
    item: Dict[str, Any], ticker: str, query: str, cutoff_dt: datetime
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Normalize raw Blind item to schema."""
    post_id = str(item.get("articleAlias") or item.get("id") or "")
    if not post_id:
        return None, "missing_post_id"

    raw_date = item.get("postedAt")
    iso_str, dt_obj = parse_to_utc_iso(raw_date, default_tz="UTC")
    if dt_obj and dt_obj < cutoff_dt:
        return None, "older_than_cutoff"

    title = str(item.get("title") or "").strip()
    body = str(item.get("content") or item.get("description") or item.get("contentPreview") or "").strip()
    text = f"{title}\n\n{body}" if title and body else (title or body)

    row = {
        "exchange": "KR",
        "source": "blind",
        "ticker": ticker,
        "post_id": post_id,
        "timestamp_utc": iso_str,
        "text": text,
        "likes": item.get("likes"),
        "dislikes": None,
        "reposts": None,
        "replies": item.get("commentCount"),
        "views": item.get("views"),
        "author": item.get("author"),
        "author_followers": None,
        "url": item.get("url"),
        "query": query,
        "language": item.get("language") or "en",
        "source_native_sentiment": None,
    }
    return row, "ok"


# ---------------------------------------------------------------------------
# Scraper Engine Class
# ---------------------------------------------------------------------------

class ProductionApifyScraper:
    """Production scraper orchestrator running KR naver, HK lihkg, HK telegram, and KR telegram."""

    def __init__(
        self,
        client: Optional[ApifyClient] = None,
        budget_usd: float = 0.8,
        lookback_days: int = config.LOOKBACK_DAYS,
        timeout_seconds: int = 180,
        naver_max_results: int = 200,
        naver_max_charge: float = 0.15,
        lihkg_max_items: int = 30,
        lihkg_max_charge: float = 0.08,
        hk_telegram_max_results: int = 100,
        hk_telegram_max_charge: float = 0.08,
        kr_telegram_max_results: int = 30,
        kr_telegram_max_charge: float = 0.08,
        force: bool = False,
        merge_scrape: Optional[str] = None,
    ):
        self.client = client
        self.budget_usd = budget_usd
        self.lookback_days = lookback_days
        self.timeout_seconds = timeout_seconds

        self.caps: Dict[Tuple[str, str], Dict[str, Any]] = {
            ("KR", "naver"): {"max_items": naver_max_results, "max_charge": naver_max_charge},
            ("HK", "lihkg"): {"max_items": lihkg_max_items, "max_charge": lihkg_max_charge},
            ("HK", "telegram"): {"max_items": hk_telegram_max_results, "max_charge": hk_telegram_max_charge},
            ("KR", "telegram"): {"max_items": kr_telegram_max_results, "max_charge": kr_telegram_max_charge},
        }

        self.force = force
        self.merge_scrape = merge_scrape
        self.total_spent_usd = 0.0
        self.actor_spent: Dict[Tuple[str, str], float] = {k: 0.0 for k in ACTOR_CONFIGS}
        self.seen_posts: Set[Tuple[str, str, str]] = set()
        self.cutoff_dt = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

    def plan_queries(
        self, tickers: List[str], only_source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate dry-run execution plan ordered by SOURCE_PIPELINE."""
        plans = []

        for target_exchange, src in SOURCE_PIPELINE:
            pipe_key = (target_exchange, src)
            if pipe_key not in ACTOR_CONFIGS:
                continue

            if only_source:
                os_lower = only_source.strip().lower()
                matches = (
                    os_lower == src.lower()
                    or os_lower == f"{target_exchange.lower()}_{src.lower()}"
                    or os_lower == f"{src.lower()}_{target_exchange.lower()}"
                    or os_lower == f"{target_exchange.lower()}/{src.lower()}"
                )
                if not matches:
                    continue

            cfg = ACTOR_CONFIGS[pipe_key]
            cap_info = self.caps[pipe_key]

            for ticker in tickers:
                asset = config.ASSETS.get(ticker)
                if not asset or asset["exchange"] != target_exchange:
                    continue

                query_desc = ""
                run_input: Dict[str, Any] = {}

                if src == "naver":
                    stock_code = asset.get("naver_code") or asset.get("plain_ticker")
                    query_desc = f"Stock Code: {stock_code}"
                    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
                    cutoff_kst_str = (now_kst - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")
                    run_input = {
                        "stocks": [stock_code],
                        "maxResults": cap_info["max_items"],
                        "dateFrom": cutoff_kst_str,
                    }
                elif src == "lihkg":
                    keywords = asset.get("lihkg_keywords") or [f"{asset.get('name_local')} {asset.get('plain_ticker')}"]
                    query_desc = ", ".join(keywords)
                    run_input = {
                        "mode": "search",
                        "keywords": keywords,
                        "maxItems": cap_info["max_items"],
                        "dateFrom": f"{self.lookback_days}d",
                    }
                elif src == "telegram":
                    if target_exchange == "KR":
                        keywords = asset.get("telegram_keywords") or [
                            f"{asset.get('name_local')} 주가",
                            f"{asset.get('plain_ticker')}",
                        ]
                        query_desc = ", ".join(keywords)
                        run_input = {
                            "mode": "keyword",
                            "keywords": keywords,
                            "maxResultsPerKeyword": max(10, cap_info["max_items"]),
                            "languageCode": "ko",
                            "countryCode": "KR",
                            "afterDate": f"{self.lookback_days} days",
                        }
                    else:
                        keywords = asset.get("telegram_keywords") or [
                            f"{asset.get('name_local')} 股價",
                            f"${asset.get('plain_ticker')}",
                        ]
                        query_desc = ", ".join(keywords)
                        run_input = {
                            "mode": "keyword",
                            "keywords": keywords,
                            "maxResultsPerKeyword": max(10, cap_info["max_items"]),
                            "languageCode": "zh",
                            "afterDate": f"{self.lookback_days} days",
                        }

                plans.append({
                    "ticker": ticker,
                    "exchange": target_exchange,
                    "source": src,
                    "pipeline_key": pipe_key,
                    "actor_id": cfg["actor_id"],
                    "query_description": query_desc,
                    "run_input": run_input,
                    "max_items": cap_info["max_items"],
                    "worst_case_cost_usd": cap_info["max_charge"],
                })
        return plans

    def execute_plan(
        self, tickers: List[str], only_source: Optional[str] = None
    ) -> Tuple[Dict[Tuple[str, str], List[Dict[str, Any]]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Execute scraper plan in strict priority order across pipeline."""
        if not self.client:
            raise ValueError("ApifyClient must be initialized for execution.")

        plans = self.plan_queries(tickers, only_source=only_source)
        results_by_pipe: Dict[Tuple[str, str], List[Dict[str, Any]]] = {k: [] for k in SOURCE_PIPELINE}
        summary_metrics: List[Dict[str, Any]] = []
        skipped_plans: List[Dict[str, Any]] = []

        # Group plans by pipeline key
        plans_by_pipe: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for p in plans:
            plans_by_pipe.setdefault(p["pipeline_key"], []).append(p)

        for pipe_key in SOURCE_PIPELINE:
            if pipe_key not in plans_by_pipe:
                continue
            pipe_plans = plans_by_pipe[pipe_key]
            exchange, src = pipe_key
            cache_file = config.RAW_DATA_DIR / f"posts_{exchange}_{src}.csv"

            # Check if this source should be merge-scraped
            is_merge_scrape = False
            if self.merge_scrape:
                ms_lower = self.merge_scrape.strip().lower()
                is_merge_scrape = (
                    ms_lower == src.lower()
                    or ms_lower == f"{exchange.lower()}_{src.lower()}"
                    or ms_lower == f"{exchange.lower()}/{src.lower()}"
                )

            # Check cache
            if cache_file.exists() and not self.force and not is_merge_scrape:
                logger.info(
                    "[CACHE] Found %s. Skipping live scrape for %s/%s (use --force or --merge-scrape to scrape).",
                    cache_file.name,
                    exchange,
                    src,
                )
                try:
                    cached_df = pd.read_csv(cache_file, encoding="utf-8-sig")
                    cached_rows = cached_df.to_dict(orient="records")
                    results_by_pipe[pipe_key].extend(cached_rows)
                    for r in cached_rows:
                        self.seen_posts.add((src, str(r.get("post_id")), str(r.get("ticker"))))

                    for p in pipe_plans:
                        t_rows = [r for r in cached_rows if str(r.get("ticker")) == p["ticker"]]
                        ts_list = [r["timestamp_utc"] for r in t_rows if r.get("timestamp_utc")]
                        summary_metrics.append({
                            "exchange": exchange,
                            "source": src,
                            "ticker": p["ticker"],
                            "raw_count": len(t_rows),
                            "kept_count": len(t_rows),
                            "dropped_count": 0,
                            "min_date": min(ts_list) if ts_list else "N/A",
                            "max_date": max(ts_list) if ts_list else "N/A",
                            "cost_usd": 0.0,
                            "status": "CACHED",
                        })
                    continue
                except Exception as e:
                    logger.warning("Error reading cache file %s: %s. Re-scraping.", cache_file, e)

            # Pre-load existing items into seen_posts if merge-scraping
            if is_merge_scrape and cache_file.exists():
                try:
                    existing_df = pd.read_csv(cache_file, encoding="utf-8-sig")
                    for r in existing_df.to_dict(orient="records"):
                        self.seen_posts.add((src, str(r.get("post_id")), str(r.get("ticker"))))
                    logger.info("Loaded %d existing posts from %s for deduplication.", len(existing_df), cache_file.name)
                except Exception as e:
                    logger.warning("Could not pre-load %s: %s", cache_file.name, e)

            # Live Scraping
            for plan in pipe_plans:
                ticker = plan["ticker"]
                actor_id = plan["actor_id"]
                run_input = plan["run_input"]
                cap_cost = plan["worst_case_cost_usd"]

                # Global budget guard check
                if self.total_spent_usd + 0.0001 >= self.budget_usd:
                    logger.warning(
                        "Budget limit reached ($%.4f >= $%.4f). Skipping remaining runs.",
                        self.total_spent_usd,
                        self.budget_usd,
                    )
                    skipped_plans.append(plan)
                    continue

                logger.info("Executing %s/%s for %s (%s)...", exchange, src, ticker, actor_id)

                raw_items: List[Dict[str, Any]] = []
                cost = 0.0
                err: Optional[str] = None
                run_id: Optional[str] = None

                try:
                    keywords_cnt = len(run_input.get("keywords", [])) if "keywords" in run_input else 1
                    call_max_items = plan["max_items"] * max(1, keywords_cnt)

                    run = self.client.actor(actor_id).call(
                        run_input=run_input,
                        max_items=call_max_items,
                        max_total_charge_usd=Decimal(str(cap_cost)),
                        run_timeout=timedelta(seconds=self.timeout_seconds),
                    )

                    if not run:
                        err = "Actor call returned empty run object"
                    else:
                        run_id = run.id if hasattr(run, "id") else run.get("id")
                        dataset_id = run.default_dataset_id if hasattr(run, "default_dataset_id") else run.get("defaultDatasetId")
                        if dataset_id:
                            for it in self.client.dataset(dataset_id).iterate_items():
                                raw_items.append(to_dict(it))

                        # Settle and fetch actual cost
                        usage_total, charged_events_usd, cost = get_actual_run_cost(self.client, run_id, actor_id)
                        logger.info(
                            "Cost for %s/%s (%s): usageTotalUsd=$%.6f, chargedEventsCost=$%.6f -> Effective Cost: $%.6f",
                            exchange,
                            src,
                            ticker,
                            usage_total,
                            charged_events_usd,
                            cost,
                        )

                    # Trigger Telegram Fallback if primary fails
                    if src == "telegram" and err:
                        fallback_id = ACTOR_CONFIGS[pipe_key].get("fallback_actor_id")
                        if fallback_id:
                            logger.warning(
                                "Primary Telegram actor failed (%s). Triggering fallback %s...",
                                err,
                                fallback_id,
                            )
                            fb_input = {
                                "profiles": ["telegram", "stocks"],
                                "collectMessages": True,
                                "scrapeLastNDays": self.lookback_days,
                            }
                            fb_run = self.client.actor(fallback_id).call(
                                run_input=fb_input,
                                max_items=call_max_items,
                                max_total_charge_usd=Decimal(str(cap_cost)),
                                run_timeout=timedelta(seconds=self.timeout_seconds),
                            )
                            if fb_run:
                                fb_run_id = fb_run.id if hasattr(fb_run, "id") else fb_run.get("id")
                                fb_ds = fb_run.default_dataset_id if hasattr(fb_run, "default_dataset_id") else fb_run.get("defaultDatasetId")
                                if fb_ds:
                                    for it in self.client.dataset(fb_ds).iterate_items():
                                        raw_items.append(to_dict(it))
                                _, _, fb_cost = get_actual_run_cost(self.client, fb_run_id, fallback_id)
                                cost += fb_cost
                                err = None

                except Exception as e:
                    logger.error("Exception occurred while scraping %s/%s for %s: %s", exchange, src, ticker, e)
                    err = str(e)

                self.total_spent_usd += cost
                self.actor_spent[pipe_key] = self.actor_spent.get(pipe_key, 0.0) + cost

                # Process items
                asset_cfg = config.ASSETS.get(ticker, {})
                kept_rows: List[Dict[str, Any]] = []
                dropped_count = 0
                timestamps: List[datetime] = []

                for it in raw_items:
                    row: Optional[Dict[str, Any]] = None

                    if src == "naver":
                        row, reason = normalize_naver_item(it, ticker, plan["query_description"], self.cutoff_dt)
                    elif src == "lihkg":
                        row, reason = normalize_lihkg_item(it, ticker, plan["query_description"], self.cutoff_dt)
                    elif src == "telegram":
                        row, reason = normalize_telegram_item(it, ticker, plan["query_description"], self.cutoff_dt, exchange=exchange)
                        if row and not is_telegram_post_relevant(row["text"], ticker, asset_cfg, exchange=exchange):
                            row = None

                    if not row:
                        dropped_count += 1
                        continue

                    # Deduplication on (source, post_id, ticker)
                    dedup_key = (src, str(row["post_id"]), ticker)
                    if dedup_key in self.seen_posts:
                        dropped_count += 1
                        continue

                    self.seen_posts.add(dedup_key)
                    kept_rows.append(row)
                    if row["timestamp_utc"]:
                        try:
                            parsed_dt = date_parser.parse(row["timestamp_utc"])
                            timestamps.append(parsed_dt)
                        except Exception:
                            pass

                # Coverage time span output for Naver
                if src == "naver" and timestamps:
                    min_dt = min(timestamps)
                    max_dt = max(timestamps)
                    span = max_dt - min_dt
                    hrs = span.total_seconds() / 3600.0
                    days = span.total_seconds() / 86400.0
                    logger.info(
                        "[NAVER COVERAGE] %s: %d posts cover %.1f days (%.1f hours) from %s to %s",
                        ticker,
                        len(kept_rows),
                        days,
                        hrs,
                        min_dt.strftime("%Y-%m-%d %H:%M UTC"),
                        max_dt.strftime("%Y-%m-%d %H:%M UTC"),
                    )

                logger.info(
                    "Finished %s/%s for %s: %d raw, %d kept, %d dropped (cost: $%.6f USD)",
                    exchange,
                    src,
                    ticker,
                    len(raw_items),
                    len(kept_rows),
                    dropped_count,
                    cost,
                )

                results_by_pipe[pipe_key].extend(kept_rows)
                min_str = min(timestamps).strftime("%Y-%m-%dT%H:%M:%SZ") if timestamps else "N/A"
                max_str = max(timestamps).strftime("%Y-%m-%dT%H:%M:%SZ") if timestamps else "N/A"

                summary_metrics.append({
                    "exchange": exchange,
                    "source": src,
                    "ticker": ticker,
                    "raw_count": len(raw_items),
                    "kept_count": len(kept_rows),
                    "dropped_count": dropped_count,
                    "min_date": min_str,
                    "max_date": max_str,
                    "cost_usd": cost,
                    "status": "ERROR" if err else "SUCCESS",
                })

            # Save CSV outputs for this pipe_key
            out_rows = results_by_pipe[pipe_key]
            if cache_file.exists() and not self.force:
                try:
                    df_old = pd.read_csv(cache_file, encoding="utf-8-sig")
                    df_new = pd.DataFrame(out_rows, columns=NORMALIZED_COLUMNS) if out_rows else pd.DataFrame(columns=NORMALIZED_COLUMNS)
                    combined = pd.concat([df_old, df_new], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["source", "post_id", "ticker"], keep="last")
                    combined.to_csv(cache_file, index=False, encoding="utf-8-sig")
                    results_by_pipe[pipe_key] = combined.to_dict(orient="records")
                    logger.info("Merged and saved %d total posts to %s", len(combined), cache_file)
                    continue
                except Exception as e:
                    logger.warning("Error merging CSV %s: %s", cache_file, e)

            if out_rows:
                df_new = pd.DataFrame(out_rows, columns=NORMALIZED_COLUMNS)
                df_new.to_csv(cache_file, index=False, encoding="utf-8-sig")
                logger.info("Saved %d posts to %s", len(df_new), cache_file)

        return results_by_pipe, summary_metrics, skipped_plans


# ---------------------------------------------------------------------------
# Reporting & Display Helpers
# ---------------------------------------------------------------------------

def display_plan_table(plans: List[Dict[str, Any]], budget_usd: float) -> None:
    """Print dry-run plan table and total worst-case cost."""
    print("\n" + "=" * 95)
    print("PLANNED SCRAPING QUERIES (DRY-RUN)")
    print("=" * 95)
    print(
        f"{'Order':<6} {'Exch':<5} {'Source':<10} {'Ticker':<11} {'Cap':<6} {'Max USD':<9} {'Query / Stock':<42}"
    )
    print("-" * 95)

    total_worst_case = 0.0
    for idx, p in enumerate(plans, 1):
        total_worst_case += p["worst_case_cost_usd"]
        print(
            f"{idx:<6} {p['exchange']:<5} {p['source']:<10} {p['ticker']:<11} {p['max_items']:<6} "
            f"${p['worst_case_cost_usd']:<8.2f} {p['query_description'][:42]:<42}"
        )

    print("-" * 95)
    print(f"Total Planned Calls:    {len(plans)}")
    print(f"Total Worst-Case Cost:  ${total_worst_case:.2f} USD")
    print(f"Global Budget Guard:    ${budget_usd:.2f} USD")
    print("=" * 95 + "\n")


def display_summary_table(
    summary_metrics: List[Dict[str, Any]],
    total_spent_usd: float,
    budget_usd: float,
    skipped_plans: List[Dict[str, Any]],
) -> None:
    """Print comprehensive scraping summary table."""
    print("\n" + "=" * 110)
    print("SCRAPING SUMMARY TABLE")
    print("=" * 110)
    print(
        f"{'Exch':<5} {'Source':<10} {'Ticker':<11} {'Raw':<6} {'Kept':<6} {'Dropped':<8} "
        f"{'Date Range (UTC)':<38} {'Cost (USD)':<12} {'Status'}"
    )
    print("-" * 110)

    total_raw = sum(m["raw_count"] for m in summary_metrics)
    total_kept = sum(m["kept_count"] for m in summary_metrics)
    total_dropped = sum(m["dropped_count"] for m in summary_metrics)

    for m in summary_metrics:
        d_range = f"{m['min_date'][:16]} to {m['max_date'][:16]}" if m['min_date'] != "N/A" else "N/A"
        print(
            f"{m.get('exchange', ''):<5} {m['source']:<10} {m['ticker']:<11} {m['raw_count']:<6} {m['kept_count']:<6} "
            f"{m['dropped_count']:<8} {d_range:<38} ${m['cost_usd']:<11.6f} {m['status']}"
        )

    print("-" * 110)
    print(
        f"{'TOTAL':<28} {total_raw:<6} {total_kept:<6} {total_dropped:<8} "
        f"{'-':<38} ${total_spent_usd:<11.6f}"
    )
    print(f"Total Budget Spent:     ${total_spent_usd:.6f} / ${budget_usd:.2f} USD")

    if skipped_plans:
        print("\n[ALERT] Budget guard stopped execution early. The following runs were skipped:")
        for sp in skipped_plans:
            print(f"  - [{sp['exchange']}/{sp['source']}] {sp['ticker']} (Query: {sp['query_description']})")

    print("=" * 110 + "\n")


def display_samples_per_source(results_by_pipe: Dict[Tuple[str, str], List[Dict[str, Any]]], num_samples: int = 3) -> None:
    """Print sample rows per pipeline source with text truncated to 120 chars."""
    print("=" * 110)
    print(f"SAMPLE ROWS PER SOURCE (First {num_samples} rows, text truncated to 120 chars)")
    print("=" * 110)

    for pipe_key in SOURCE_PIPELINE:
        rows = results_by_pipe.get(pipe_key, [])
        exchange, src = pipe_key
        print(f"\n--- [Source: {exchange} / {src.upper()}] Total Collected: {len(rows)} posts ---")
        if not rows:
            print("  (No posts collected)")
            continue

        for i, r in enumerate(rows[:num_samples], 1):
            text = r.get("text") or ""
            clean_text = " ".join(text.split())
            truncated = clean_text[:117] + "..." if len(clean_text) > 120 else clean_text

            print(f"  [{i}] ID: {r.get('post_id')} | Ticker: {r.get('ticker')} | UTC: {r.get('timestamp_utc')} | Likes: {r.get('likes')}")
            print(f"      Author: {r.get('author')} | URL: {r.get('url')}")
            print(f"      Text:   \"{truncated}\"")

    print("\n" + "=" * 110 + "\n")


def display_timestamp_sanity_check(results_by_pipe: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> None:
    """Timestamp sanity check: print min, max, current UTC time, and flag posts >5m in future."""
    now_utc = datetime.now(timezone.utc)
    future_limit = now_utc + timedelta(minutes=5)

    print("=" * 110)
    print("TIMESTAMP SANITY CHECK")
    print(f"Current System UTC Time: {now_utc.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 110)
    print(
        f"{'Source':<16} {'Posts Checked':<14} {'Min Timestamp (UTC)':<24} {'Max Timestamp (UTC)':<24} {'Future (>5m)':<12} {'Sanity Status'}"
    )
    print("-" * 110)

    for pipe_key in SOURCE_PIPELINE:
        rows = results_by_pipe.get(pipe_key, [])
        exchange, src = pipe_key
        source_label = f"{exchange}/{src}"
        timestamps: List[datetime] = []
        future_posts: List[Dict[str, Any]] = []

        for r in rows:
            ts_str = r.get("timestamp_utc")
            if not ts_str:
                continue
            try:
                dt = date_parser.parse(ts_str)
                timestamps.append(dt)
                if dt > future_limit:
                    future_posts.append(r)
            except Exception:
                pass

        if not timestamps:
            print(f"{source_label:<16} {0:<14} {'N/A':<24} {'N/A':<24} {0:<12} {'NO DATA'}")
            continue

        min_str = min(timestamps).strftime("%Y-%m-%dT%H:%M:%SZ")
        max_str = max(timestamps).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = "PASSED" if not future_posts else f"FAILED ({len(future_posts)} future)"

        print(
            f"{source_label:<16} {len(timestamps):<14} {min_str:<24} {max_str:<24} {len(future_posts):<12} {status}"
        )

        for fp in future_posts:
            print(f"  [FLAGGED FUTURE TIMESTAMP] Post ID: {fp.get('post_id')} | Ticker: {fp.get('ticker')} | Timestamp: {fp.get('timestamp_utc')}")

    print("=" * 110 + "\n")


# ---------------------------------------------------------------------------
# CLI Argument Parser & Entrypoint
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Production Apify post scraper for HK and KR retail market sentiment."
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated ticker list. Defaults to all 10 assets in config.",
    )
    parser.add_argument(
        "--only",
        type=str,
        choices=["naver", "lihkg", "telegram", "kr_telegram", "hk_telegram"],
        default=None,
        help="Scrape only one specific source platform.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned queries and worst-case cost, then exit without calling Apify.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cached CSV files and force re-scraping from Apify actors.",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=0.8,
        help="Global USD budget guard (default: $0.80 USD).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Per-actor timeout in seconds (default: 180s).",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=config.LOOKBACK_DAYS,
        help=f"Lookback window in days (default: {config.LOOKBACK_DAYS}).",
    )
    parser.add_argument(
        "--naver-max-results",
        type=int,
        default=200,
        help="Max results cap per stock for Naver (default: 200).",
    )
    parser.add_argument(
        "--naver-max-charge",
        type=float,
        default=0.15,
        help="Max USD charge cap for Naver actor run (default: 0.15).",
    )
    parser.add_argument(
        "--lihkg-max-items",
        type=int,
        default=30,
        help="Max items cap per ticker for LIHKG (default: 30).",
    )
    parser.add_argument(
        "--lihkg-max-charge",
        type=float,
        default=0.08,
        help="Max USD charge cap for LIHKG actor run (default: 0.08).",
    )
    parser.add_argument(
        "--hk-telegram-max-results",
        type=int,
        default=100,
        help="Max results cap per keyword for HK Telegram (default: 100).",
    )
    parser.add_argument(
        "--hk-telegram-max-charge",
        type=float,
        default=0.08,
        help="Max USD charge cap for HK Telegram actor run (default: 0.08).",
    )
    parser.add_argument(
        "--kr-telegram-max-results",
        type=int,
        default=30,
        help="Max results cap per keyword for KR Telegram (default: 30).",
    )
    parser.add_argument(
        "--kr-telegram-max-charge",
        type=float,
        default=0.08,
        help="Max USD charge cap for KR Telegram actor run (default: 0.08).",
    )
    parser.add_argument(
        "--merge-scrape",
        type=str,
        default=None,
        help="Scrape this source and merge with existing CSV without deleting old data (e.g. 'lihkg').",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Determine tickers to process
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = list(config.ASSETS.keys())

    scraper = ProductionApifyScraper(
        client=None,
        budget_usd=args.budget,
        lookback_days=args.lookback_days,
        timeout_seconds=args.timeout,
        naver_max_results=args.naver_max_results,
        naver_max_charge=args.naver_max_charge,
        lihkg_max_items=args.lihkg_max_items,
        lihkg_max_charge=args.lihkg_max_charge,
        hk_telegram_max_results=args.hk_telegram_max_results,
        hk_telegram_max_charge=args.hk_telegram_max_charge,
        kr_telegram_max_results=args.kr_telegram_max_results,
        kr_telegram_max_charge=args.kr_telegram_max_charge,
        force=args.force,
        merge_scrape=args.merge_scrape,
    )

    # 1. Dry-Run Check
    if args.dry_run:
        plans = scraper.plan_queries(tickers, only_source=args.only)
        display_plan_table(plans, args.budget)
        return

    # 2. Live Run: initialize Apify client (never log or print token)
    token = config.get_apify_token(required=True)
    client = ApifyClient(token=token)
    scraper.client = client

    # Execute plan in priority order
    results_by_pipe, summary_metrics, skipped_plans = scraper.execute_plan(tickers, only_source=args.only)

    # 3. Print Summary Table
    display_summary_table(summary_metrics, scraper.total_spent_usd, args.budget, skipped_plans)

    # 4. Print Sample Rows
    display_samples_per_source(results_by_pipe, num_samples=3)

    # 5. Timestamp Sanity Check
    display_timestamp_sanity_check(results_by_pipe)


if __name__ == "__main__":
    main()
