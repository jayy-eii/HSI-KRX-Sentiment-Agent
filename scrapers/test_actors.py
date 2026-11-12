"""Test runner for Apify social-post scraper actors.

Runs a tiny test for each specified scraper actor with strict cost ($0.10)
and timeout (120s) limits, saving sample data to data/raw/ and printing
summary metrics.
"""

import json
import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from apify_client import ApifyClient

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

# Hard Configuration Limits
MAX_TOTAL_CHARGE_USD = Decimal("0.10")
TIMEOUT_SECONDS = 120
MAX_ITEMS_CAP = 5

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Also ensure alt directory exists for dual-workspace synchronization
ALT_RAW_DATA_DIR = Path("/Users/jayjadhao/documents/hsi-sentiment-agent/data/raw")
ALT_RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


ACTOR_TESTS = [
    {
        "platform": "lihkg",
        "actor_id": "claude_code_reviewer~lihkg-scraper-en",
        "actor_name": "lihkg-scraper-en",
        "alias": "lihkg",
        "input": {
            "mode": "search",
            "keywords": ["騰訊"],
            "maxItems": 5,
        },
        "is_fallback": False,
    },
    {
        "platform": "telegram",
        "actor_id": "lofomachines~telegram-keyword-search-scraper",
        "actor_name": "telegram-keyword-search-scraper",
        "alias": "telegram",
        "input": {
            "mode": "keyword",
            "keywords": ["Tencent"],
            "maxResultsPerKeyword": 10,  # Schema requires integer >= 10
        },
        "is_fallback": False,
    },
    {
        "platform": "naver",
        "actor_id": "hgservices~naver-stock-discussion-scraper",
        "actor_name": "naver-stock-discussion-scraper",
        "alias": "naver",
        "input": {
            "stocks": ["005930"],
            "maxResults": 5,
        },
        "is_fallback": False,
    },
    {
        "platform": "blind",
        "actor_id": "hypebridge~blind-post-scraper",
        "actor_name": "blind-post-scraper",
        "alias": "blind",
        "input": {
            "startUrls": [{"url": "https://www.teamblind.com/search/Samsung"}],
            "maxItems": 5,
            "scrapePostsFromLists": True,
        },
        "is_fallback": False,
    },
]

FALLBACK_TELEGRAM_ACTORS = [
    {
        "platform": "telegram (fallback 1)",
        "actor_id": "tri_angle~telegram-scraper",
        "actor_name": "tri_angle-telegram-scraper",
        "alias": "telegram_fallback_1",
        "input": {
            "profiles": ["telegram"],
            "collectMessages": True,
            "scrapeLastNDays": 2,
        },
        "is_fallback": True,
    },
    {
        "platform": "telegram (fallback 2)",
        "actor_id": "curious_coder~telegram-scraper",
        "actor_name": "curious_coder-telegram-scraper",
        "alias": "telegram_fallback_2",
        "input": {
            "scrapeGroup": "https://t.me/telegram",
            "count": 10,  # Schema requires integer >= 10
        },
        "is_fallback": True,
    },
]


def to_dict(obj: Any) -> Dict[str, Any]:
    """Normalize Pydantic model, dataclass, or dictionary to dict."""
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


def extract_sample_text(item: Dict[str, Any]) -> str:
    """Find the most relevant text body in a sample item and truncate to 150 chars."""
    for key in ["own_text", "content", "text", "description", "contentPreview", "title"]:
        val = item.get(key)
        if val and isinstance(val, str) and val.strip():
            clean = " ".join(val.split())
            if len(clean) > 150:
                return clean[:147] + "..."
            return clean
    return "N/A (no body text found)"


def run_single_actor_test(client: ApifyClient, test_cfg: Dict[str, Any]) -> Dict[str, Any]:
    actor_id = test_cfg["actor_id"]
    actor_name = test_cfg["actor_name"]
    alias = test_cfg["alias"]
    platform = test_cfg["platform"]
    run_input = test_cfg["input"]
    
    print("=" * 70)
    print(f"RUNNING TEST: {platform} ({actor_id})")
    print(f"  Input: {json.dumps(run_input, ensure_ascii=False)}")
    print(f"  Hard Limits: max_total_charge_usd={MAX_TOTAL_CHARGE_USD}, timeout={TIMEOUT_SECONDS}s")
    
    result = {
        "platform": platform,
        "actor_id": actor_id,
        "actor_name": actor_name,
        "status": "FAIL",
        "items_count": 0,
        "fields": [],
        "cost_usd": None,
        "sample_item": None,
        "error": None,
    }
    
    try:
        # Call actor via apify-client
        run = client.actor(actor_id).call(
            run_input=run_input,
            max_items=MAX_ITEMS_CAP,
            max_total_charge_usd=MAX_TOTAL_CHARGE_USD,
            run_timeout=timedelta(seconds=TIMEOUT_SECONDS),
        )
        
        if not run:
            result["error"] = "Actor call returned empty run object."
            return result
            
        run_dict = to_dict(run)
        run_status = run_dict.get("status")
        run_id = run_dict.get("id")
        usage_usd = run_dict.get("usage_total_usd") or run_dict.get("usageTotalUsd")
        result["cost_usd"] = float(usage_usd) if usage_usd is not None else None
        
        print(f"  Run finished: ID={run_id}, Status={run_status}")
        if result["cost_usd"] is not None:
            print(f"  Total Cost: ${result['cost_usd']:.6f} USD")
        else:
            print("  Total Cost: Not returned in run summary (Free/Standard compute)")
            
        dataset_id = run_dict.get("default_dataset_id") or run_dict.get("defaultDatasetId")
        if not dataset_id:
            result["error"] = f"Run status is {run_status}, but no defaultDatasetId returned."
            return result
            
        # Fetch items (cap at 5 items)
        items_page = client.dataset(dataset_id).list_items(limit=MAX_ITEMS_CAP)
        items = items_page.items if hasattr(items_page, "items") else list(items_page)
        
        # Ensure items are standard dicts
        normalized_items = [to_dict(it) for it in items[:MAX_ITEMS_CAP]]
        result["items_count"] = len(normalized_items)
        
        if normalized_items:
            result["status"] = "SUCCESS"
            sample = normalized_items[0]
            result["sample_item"] = sample
            result["fields"] = list(sample.keys())
            
            # Save raw results
            for out_base in [RAW_DATA_DIR, ALT_RAW_DATA_DIR]:
                file1 = out_base / f"sample_{actor_name}.json"
                file2 = out_base / f"sample_{alias}.json"
                content_str = json.dumps(normalized_items, ensure_ascii=False, indent=2)
                file1.write_text(content_str, encoding="utf-8")
                file2.write_text(content_str, encoding="utf-8")
                
            print(f"  Saved {len(normalized_items)} items to data/raw/sample_{actor_name}.json and data/raw/sample_{alias}.json")
        else:
            if run_status == "SUCCEEDED":
                result["status"] = "SUCCESS (0 items)"
                result["error"] = "Run succeeded, but dataset returned 0 items for this test query."
            else:
                result["status"] = f"FAIL ({run_status})"
                result["error"] = f"Run finished with status {run_status} and 0 items."

    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = str(e)
        print(f"  Exception caught: {e}")

    return result


def main():
    token = config.get_apify_token(required=True)
    client = ApifyClient(token=token)
    
    results = []
    telegram_failed = False
    
    # Run primary tests
    for test in ACTOR_TESTS:
        res = run_single_actor_test(client, test)
        results.append(res)
        
        # Check if telegram primary failed
        if test["platform"] == "telegram" and not res["status"].startswith("SUCCESS"):
            telegram_failed = True
            print("  [ALERT] Primary Telegram actor failed. Triggering fallback telegram actors...")

    # Run fallback telegram tests only if primary failed
    if telegram_failed:
        for fb_test in FALLBACK_TELEGRAM_ACTORS:
            fb_res = run_single_actor_test(client, fb_test)
            results.append(fb_res)

    # Print summary
    print("\n" + "=" * 80)
    print("ACTOR TEST SUMMARY")
    print("=" * 80)
    for r in results:
        cost_str = f"${r['cost_usd']:.6f} USD" if r['cost_usd'] is not None else "N/A"
        print(f"\nActor: {r['actor_id']} ({r['platform']})")
        print(f"  Status:         {r['status']}")
        print(f"  Items Count:    {r['items_count']}")
        print(f"  Total Cost:     {cost_str}")
        print(f"  Output Fields:  {r['fields']}")
        if r['sample_item']:
            sample_text = extract_sample_text(r['sample_item'])
            print(f"  Sample Snippet: \"{sample_text}\"")
        if r['error']:
            print(f"  Notes/Error:    {r['error']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
