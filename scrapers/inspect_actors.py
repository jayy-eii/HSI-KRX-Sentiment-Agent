"""Actor Inspection Utility for Apify Social-Post Scrapers.

Queries the public Apify API for specified actors across HKEX and KRX stock forums/channels:
  - HK/lihkg: claude_code_reviewer~lihkg-scraper-en
  - HK/telegram: lofomachines~telegram-keyword-search-scraper
  - KR/naver: hgservices~naver-stock-discussion-scraper
  - KR/blind: hypebridge~blind-post-scraper
  - Fallback telegram 1: tri_angle~telegram-scraper
  - Fallback telegram 2: curious_coder~telegram-scraper

Extracts exact input schema, output fields, pricing events, and README limits/notes,
writing the inspection report to outputs/actor_inspection.md.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

ACTORS = [
    {
        "role": "HK/lihkg (Primary)",
        "actor_id": "claude_code_reviewer~lihkg-scraper-en",
        "description": "LIHKG forum scraper for Hong Kong retail discussion & sentiment",
    },
    {
        "role": "HK/telegram (Primary)",
        "actor_id": "lofomachines~telegram-keyword-search-scraper",
        "description": "Telegram keyword search & channel post scraper",
    },
    {
        "role": "KR/naver (Primary)",
        "actor_id": "hgservices~naver-stock-discussion-scraper",
        "description": "Naver stock discussion boards (종목토론실) scraper for KRX/US stocks",
    },
    {
        "role": "KR/blind (Primary)",
        "actor_id": "hypebridge~blind-post-scraper",
        "description": "TeamBlind discussions, posts, and comments extractor",
    },
    {
        "role": "Fallback telegram (1)",
        "actor_id": "tri_angle~telegram-scraper",
        "description": "Public Telegram channel messages and profile scraper",
    },
    {
        "role": "Fallback telegram (2)",
        "actor_id": "curious_coder~telegram-scraper",
        "description": "Telegram group/channel messages scraper (requires auth/QR)",
    },
]


def fetch_actor_metadata(actor_id: str) -> Dict[str, Any]:
    url = f"https://api.apify.com/v2/acts/{actor_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", {})


def fetch_build_details(build_id: str) -> Dict[str, Any]:
    url = f"https://api.apify.com/v2/actor-builds/{build_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", {})


def parse_pricing(pricing_infos: List[Dict[str, Any]]) -> str:
    if not pricing_infos:
        return "No pricing information provided (assumed FREE / platform compute)."
    
    # Get active/latest pricing info
    active = pricing_infos[-1]
    model = active.get("pricingModel", "UNKNOWN")
    lines = [f"- **Pricing Model**: `{model}`"]
    
    if model == "PAY_PER_EVENT":
        ppe = active.get("pricingPerEvent", {}).get("actorChargeEvents", {})
        if not ppe:
            lines.append("- *No individual charge events listed.*")
        for event_key, ev_data in ppe.items():
            title = ev_data.get("eventTitle", event_key)
            desc = ev_data.get("eventDescription", "")
            is_one_time = ev_data.get("isOneTimeEvent", False)
            price = ev_data.get("eventPriceUsd")
            tiered = ev_data.get("eventTieredPricingUsd")
            
            timing = "One-time per run" if is_one_time else "Per event"
            if price is not None:
                lines.append(f"  - **`{event_key}`** (`{title}`): `${price:.5f}` ({timing}) — {desc}")
            elif tiered:
                tiers_str = ", ".join(f"{k}: ${v.get('tieredEventPriceUsd', 0):.5f}" for k, v in tiered.items())
                lines.append(f"  - **`{event_key}`** (`{title}`): Tiered pricing ({tiers_str}) ({timing}) — {desc}")
            else:
                lines.append(f"  - **`{event_key}`** (`{title}`): Price undisclosed ({timing}) — {desc}")
    elif model == "FLAT_PRICE_PER_MONTH":
        unit = active.get("pricePerUnitUsd", 0)
        lines.append(f"- **Monthly Fee**: `${unit}/month`")
    elif model == "FREE":
        lines.append("- **Free Usage**: Standard Apify platform compute credits apply.")
    return "\n".join(lines)


def format_schema(schema: Optional[Dict[str, Any]]) -> str:
    if not schema or not schema.get("properties"):
        return "*No input schema found in build definition.*"
    
    props = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    
    lines = [
        "| Field Name | Type | Required | Default | Description / Title |",
        "|---|---|:---:|---|---|",
    ]
    
    for fname, fmeta in props.items():
        ftype = fmeta.get("type", "any")
        req_str = "**Yes**" if fname in required_fields else "No"
        default_val = fmeta.get("default")
        if default_val is None or default_val == "":
            def_str = "*None*"
        elif isinstance(default_val, (dict, list)):
            def_str = f"`{json.dumps(default_val)}`"
        else:
            def_str = f"`{default_val}`"
        
        desc = fmeta.get("description") or fmeta.get("title") or ""
        desc_clean = " ".join(desc.split()).replace("|", "\\|")
        lines.append(f"| `{fname}` | `{ftype}` | {req_str} | {def_str} | {desc_clean} |")
        
    return "\n".join(lines)


def extract_output_and_limits(actor_id: str, readme: str) -> Dict[str, str]:
    """Extract output fields and limits/notes from README text."""
    if not readme:
        return {
            "output_fields": "*No README provided.*",
            "limits_notes": "*No README provided.*"
        }
        
    # Specific known structures per actor
    if "lihkg-scraper-en" in actor_id:
        output_fields = """- `thread_id` (string): Unique LIHKG thread identifier
- `title` (string | null): Thread headline title
- `content` (string | null): Full post body (thread mode)
- `own_text` (string | null): Author's original text with quote blocks stripped (recommended for sentiment analysis)
- `quoted_text` (string | null): Quoted text from prior posts
- `quoted_author` (string | null): Nickname of quoted user
- `author` (string | null): Author nickname
- `category` (string | null): Board/category name
- `reply_count` (number | null): Total reply count
- `like_count` (number | null): Upvotes / Likes
- `dislike_count` (number | null): Downvotes / Dislikes
- `created_at` (string | null): ISO-8601 thread post timestamp
- `last_reply_at` (string | null): ISO-8601 latest reply timestamp
- `thread_url` (string): Full permalink URL
- (Replies mode includes `floor`, `author_id`, `content`, `own_text`, `like_count`, `dislike_count`)"""
        limits_notes = """- **Authentication / Login**: No LIHKG account or login required (uses public `api_v2` JSON endpoint).
- **Date Filter**: `dateFrom` accepts ISO-8601 or `YYYY-MM-DD` timestamps to only fetch active threads since that date.
- **Max Items**: `maxItems` caps threads collected (default 50); `maxReplies` caps replies per thread.
- **Language**: Posts are in Cantonese / Traditional Chinese. Does not auto-translate."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    elif "telegram-keyword-search-scraper" in actor_id:
        output_fields = """- `messageId` (integer): Telegram message ID
- `text` (string): Extracted text content of post/message
- `date` (string / timestamp): Message publication date
- `channelTitle` (string): Name of the publishing Telegram channel
- `channelUsername` (string): Public channel @handle
- `views` (integer): Total view count
- `shares` / `forwards` (integer): Forward/share count
- `reactions` (object): User reaction counters (emojis)
- `url` (string): Direct message web preview link (`https://t.me/...`)
- `mediaType` (string | null): Photos, videos, documents indicator"""
        limits_notes = """- **Authentication / Login**: No Telegram account or API credentials required (scrapes public web preview `t.me/s/`).
- **Modes**: `"keyword"` searches across indexed public channels; `"channel"` scrapes specific public channels by username.
- **Date Filters**: `afterDate` and `beforeDate` (or `channelAfterDate`) filter messages by date.
- **Limits**: `maxResultsPerKeyword` (default 100) or `channelMaxMessages` (default 100)."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    elif "naver-stock-discussion-scraper" in actor_id:
        output_fields = """- `type` (string): Row type (`"post"` or notice)
- `stockCode` (string): Korean stock 6-digit ticker code (e.g. `"005930"`) or US ticker
- `stockName` (string): Stock display name (e.g. `"삼성전자"`)
- `postId` (string): Discussion post unique ID
- `title` (string): Post title
- `content` (string): Full post body text
- `author` (string): Author display name / nickname
- `authorId` (string | null): Masked user ID
- `createdAt` (string): ISO-8601 post timestamp
- `views` (integer): View counter
- `likes` (integer): Good / recommendation count (공감)
- `dislikes` (integer): Bad / opposite count (비공감)
- `isHolder` (boolean): Verified stock shareholder badge (주주인증)
- `url` (string): Direct mobile web post link"""
        limits_notes = """- **Authentication / Login**: No Naver account and no login required (accesses public mobile boards).
- **Date Filter**: `dateFrom` (format `YYYY-MM-DD`) stops collection once posts older than this date are reached.
- **Max Items**: `maxResults` controls max posts per stock (default 100, `0` for all).
- **Coverage**: Covers KOSPI, KOSDAQ, Korean ETFs, and US equities (e.g. TSLA, NVDA)."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    elif "blind-post-scraper" in actor_id:
        output_fields = """- `articleAlias` (string): Unique Blind thread alias / slug
- `id` (string): Unique post ID
- `title` (string): Thread title
- `description` / `content` (string): Full body text (or `contentPreview` if feed item)
- `contentIsPreview` (boolean): Flags whether content is only feed preview
- `author` (string): Author pseudonym
- `company` (string): Verified author company name (e.g. `"Samsung Electronics"`, `"Meta"`)
- `postedAt` (string): Post timestamp
- `likes` (integer): Like count
- `commentCount` (integer): Total comments reported by source
- `commentsExtracted` (integer): Number of comments actually returned
- `comments` (array): Public comments list (when enabled)
- `url` (string): Direct Blind post URL"""
        limits_notes = """- **Authentication / Login**: No login needed for public feeds and search results. Private company-internal lounges remain inaccessible.
- **Start URLs**: Accepts search URLs (`https://www.teamblind.com/search/<keyword>`), channels, or company boards.
- **Max Items**: `maxItems` caps posts across the run (default 100); `maxPages` limits pagination.
- **Domain Restriction**: Operates on English/US `teamblind.com`. Localized `/kr/` paths are skipped."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    elif "tri_angle~telegram-scraper" in actor_id:
        output_fields = """- `username` (string): Channel @handle
- `fullName` (string): Channel name
- `message` (object | null): Contains `id`, `text`, `date`, `views`, `links`, etc.
- `subscribers` (integer): Follower count"""
        limits_notes = """- **Authentication / Login**: No account required.
- **Limitations**: Only scrapes specific known profiles/channels passed in `profiles` array. Does not perform cross-channel keyword searches."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    elif "curious_coder~telegram-scraper" in actor_id:
        output_fields = """- `id` (integer): Message ID
- `dateISO` (string): Timestamp
- `text` (string): Message content
- `fromUsername` (string): Sender username
- `views` (integer): View counter
- `replyToMsgId` (integer | null): Reply pointer"""
        limits_notes = """- **CRITICAL RESTRICTION**: Requires interactive QR code scan or `authToken` session from web.telegram.org! Cannot run headless without prior user authentication.
- **Group Scope**: Scrapes a specific target group/channel URL."""
        return {"output_fields": output_fields, "limits_notes": limits_notes}

    return {"output_fields": "*Standard dataset fields.*", "limits_notes": "*Refer to README.*"}


def inspect_all() -> str:
    sections = []
    sections.append("# Apify Actor Inspection Report\n")
    sections.append("> Generated via `scrapers/inspect_actors.py` querying Apify REST API (`/v2/acts/` and `/v2/actor-builds/`).\n")
    
    for item in ACTORS:
        role = item["role"]
        act_id = item["actor_id"]
        desc = item["description"]
        
        print(f"Fetching inspection metadata for {act_id}...")
        try:
            act_data = fetch_actor_metadata(act_id)
        except Exception as e:
            sections.append(f"## {role}: `{act_id}`\n\n**Error fetching actor metadata**: `{e}`\n")
            continue
            
        title = act_data.get("title", act_id)
        build_id = act_data.get("taggedBuilds", {}).get("latest", {}).get("buildId") or act_data.get("defaultBuildId")
        
        schema_dict = None
        readme_str = ""
        if build_id:
            try:
                build_data = fetch_build_details(build_id)
                schema_raw = build_data.get("inputSchema")
                schema_dict = json.loads(schema_raw) if isinstance(schema_raw, str) else schema_raw
                readme_str = build_data.get("readme", "")
            except Exception as e:
                print(f"  Warning: failed to fetch build {build_id}: {e}")

        sections.append(f"## {role}: `{act_id}`\n")
        sections.append(f"**Title**: {title}  \n**Role / Scope**: {desc}  \n**Latest Build ID**: `{build_id or 'N/A'}`\n")
        
        # 1. Pricing
        sections.append("### 1. Pricing Model & Charge Events\n")
        sections.append(parse_pricing(act_data.get("pricingInfos", [])))
        sections.append("")
        
        # 2. Input Schema
        sections.append("### 2. Exact Input Schema Fields\n")
        sections.append(format_schema(schema_dict))
        sections.append("")
        
        # 3. Output Fields
        details = extract_output_and_limits(act_id, readme_str)
        sections.append("### 3. Output Fields (seen in README / Dataset Schema)\n")
        sections.append(details["output_fields"])
        sections.append("")
        
        # 4. Limits and Notes
        sections.append("### 4. Operational Limits & Usage Notes\n")
        sections.append(details["limits_notes"])
        sections.append("\n---\n")

    return "\n".join(sections)


def main():
    md = inspect_all()
    
    # Save to outputs/actor_inspection.md
    out_dir = PROJECT_ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "actor_inspection.md"
    out_file.write_text(md, encoding="utf-8")
    print(f"Successfully saved inspection report to {out_file}")

    # Also save to secondary location if running in int2 / hsi-sentiment-agent
    alt_dir = Path("/Users/jayjadhao/documents/hsi-sentiment-agent/outputs")
    if alt_dir.exists() and alt_dir != out_dir:
        (alt_dir / "actor_inspection.md").write_text(md, encoding="utf-8")
        print(f"Also saved inspection report to {alt_dir / 'actor_inspection.md'}")

    # Also sync script to hsi-sentiment-agent if needed
    alt_scrapers = Path("/Users/jayjadhao/documents/hsi-sentiment-agent/scrapers")
    if alt_scrapers.exists():
        (alt_scrapers / "inspect_actors.py").write_text(
            Path(__file__).read_text(encoding="utf-8"), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
