"""Scraper discovery utility for Apify Store actors.

Searches the public Apify Store API for actors matching candidate keywords,
prints a structured summary table for each keyword, and persists candidate
metadata to outputs/actor_candidates.csv.
"""

import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

# Ensure project root is available in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

# Search configuration
APIFY_STORE_URL = "https://api.apify.com/v2/store"
SEARCH_KEYWORDS: List[str] = [
    "lihkg",
    "futu",
    "moomoo",
    "aastocks",
    "etnet",
    "naver",
    "naver finance",
    "daum",
    "telegram",
    "blind",
]
RESULT_LIMIT_PER_KEYWORD = 20
OUTPUT_CSV_PATH = PROJECT_ROOT / "outputs" / "actor_candidates.csv"

CSV_FIELDNAMES = [
    "keyword",
    "actor_id",
    "title",
    "total_users",
    "total_runs",
    "pricing_model",
    "last_modified_date",
    "short_description",
]


def get_request_headers() -> Dict[str, str]:
    """Build request headers, optionally adding Apify authorization token if present.

    Returns:
        Dictionary of headers for requests.
    """
    headers = {
        "Accept": "application/json",
        "User-Agent": "hsi-sentiment-agent/1.0",
    }
    token = config.get_apify_token(required=False)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def format_actor_item(keyword: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and normalize relevant actor fields from an Apify Store API item.

    Args:
        keyword: The search keyword that matched this actor.
        item: Raw item dictionary returned by the Apify Store API.

    Returns:
        Normalized dictionary matching CSV_FIELDNAMES.
    """
    username = item.get("username")
    name = item.get("name")
    if username and name:
        actor_id = f"{username}/{name}"
    elif name:
        actor_id = str(name)
    else:
        actor_id = str(item.get("id", "N/A"))

    title = (item.get("title") or "").strip()

    stats = item.get("stats") or {}
    total_users = stats.get("totalUsers", 0)
    total_runs = stats.get("totalRuns", 0)

    pricing_info = item.get("currentPricingInfo") or {}
    pricing_model = pricing_info.get("pricingModel") or item.get("pricingModel") or "FREE"

    # Last modified date: check modifiedAt, then currentPricingInfo startedAt, then stats lastRunStartedAt
    last_modified = (
        item.get("modifiedAt")
        or pricing_info.get("startedAt")
        or stats.get("lastRunStartedAt")
        or "N/A"
    )

    raw_description = item.get("description") or ""
    # Clean whitespace and newlines for consistent display and storage
    short_description = " ".join(raw_description.split())

    return {
        "keyword": keyword,
        "actor_id": actor_id,
        "title": title,
        "total_users": total_users,
        "total_runs": total_runs,
        "pricing_model": pricing_model,
        "last_modified_date": last_modified,
        "short_description": short_description,
    }


def truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if it exceeds max_len.

    Args:
        text: Input string.
        max_len: Maximum length.

    Returns:
        Truncated string.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def print_table(records: List[Dict[str, Any]]) -> None:
    """Print formatted ASCII table of actor candidate records to stdout.

    Args:
        records: List of normalized actor records.
    """
    if not records:
        print("  (No actors found)")
        return

    col_widths = {
        "keyword": 14,
        "actor_id": 36,
        "title": 32,
        "total_users": 8,
        "total_runs": 10,
        "pricing_model": 15,
        "last_modified_date": 20,
        "short_description": 45,
    }

    header_line = (
        f"| {'Keyword':<{col_widths['keyword']}} "
        f"| {'Actor ID':<{col_widths['actor_id']}} "
        f"| {'Title':<{col_widths['title']}} "
        f"| {'Users':>{col_widths['total_users']}} "
        f"| {'Runs':>{col_widths['total_runs']}} "
        f"| {'Pricing':<{col_widths['pricing_model']}} "
        f"| {'Last Modified':<{col_widths['last_modified_date']}} "
        f"| {'Short Description':<{col_widths['short_description']}} |"
    )
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths.values()) + "+"

    print(separator)
    print(header_line)
    print(separator)

    for r in records:
        print(
            f"| {truncate(str(r['keyword']), col_widths['keyword']):<{col_widths['keyword']}} "
            f"| {truncate(str(r['actor_id']), col_widths['actor_id']):<{col_widths['actor_id']}} "
            f"| {truncate(str(r['title']), col_widths['title']):<{col_widths['title']}} "
            f"| {str(r['total_users']):>{col_widths['total_users']}} "
            f"| {str(r['total_runs']):>{col_widths['total_runs']}} "
            f"| {truncate(str(r['pricing_model']), col_widths['pricing_model']):<{col_widths['pricing_model']}} "
            f"| {truncate(str(r['last_modified_date']), col_widths['last_modified_date']):<{col_widths['last_modified_date']}} "
            f"| {truncate(str(r['short_description']), col_widths['short_description']):<{col_widths['short_description']}} |"
        )
    print(separator)


def search_actors_for_keyword(
    keyword: str, headers: Dict[str, str], timeout: int = 15
) -> List[Dict[str, Any]]:
    """Query Apify Store API for a specific keyword.

    Args:
        keyword: Search query keyword.
        headers: Request headers.
        timeout: Request timeout in seconds.

    Returns:
        List of formatted actor dictionaries.
    """
    params = {
        "search": keyword,
        "limit": RESULT_LIMIT_PER_KEYWORD,
    }
    response = requests.get(
        APIFY_STORE_URL,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data", {}).get("items", [])

    return [format_actor_item(keyword, it) for it in items]


def main() -> None:
    """Execute Apify Store search across all keywords and write results to CSV."""
    headers = get_request_headers()
    has_token = bool(config.get_apify_token(required=False))
    print("=" * 80)
    print("APIFY STORE ACTOR DISCOVERY")
    print(f"Target: {APIFY_STORE_URL}")
    print(f"Token present in env: {'Yes (Authorization header added)' if has_token else 'No (Public access)'}")
    print(f"Keywords to search ({len(SEARCH_KEYWORDS)}): {', '.join(SEARCH_KEYWORDS)}")
    print("=" * 80)

    all_records: List[Dict[str, Any]] = []

    for keyword in SEARCH_KEYWORDS:
        print(f"\n>>> Searching Apify Store for keyword: '{keyword}'...")
        try:
            records = search_actors_for_keyword(keyword, headers)
            print(f"Found {len(records)} candidate actor(s) for '{keyword}':")
            print_table(records)
            all_records.extend(records)
        except requests.exceptions.Timeout:
            print(f"  [ERROR] Request timed out while searching for '{keyword}'. Continuing...")
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Network / API error for '{keyword}': {e}. Continuing...")
        except Exception as e:
            print(f"  [ERROR] Unexpected error processing '{keyword}': {e}. Continuing...")

    # Save all gathered candidates to outputs/actor_candidates.csv
    OUTPUT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerows(all_records)
        print("\n" + "=" * 80)
        print(f"SUCCESS: Saved {len(all_records)} total candidate actor(s) to:")
        print(f"  {OUTPUT_CSV_PATH.resolve()}")
        print("=" * 80)
    except Exception as e:
        print(f"\n[ERROR] Failed to save CSV file to {OUTPUT_CSV_PATH}: {e}")


if __name__ == "__main__":
    main()
