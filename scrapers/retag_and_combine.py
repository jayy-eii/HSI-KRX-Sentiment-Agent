"""Offline Ticker Re-Tagging and Dataset Combination Script.

Performs cross-ticker scanning for all Telegram and LIHKG posts across each exchange:
- Assigns posts to EVERY ticker mentioned (one row per ticker).
- Drops posts that mention no tracked tickers.
- Adds columns: query_ticker, tickers_in_post, is_market_wrap.
- Naver posts retain board stock code without re-tagging.
- Deduplicates on (source, post_id, ticker).
- Concatenates into data/processed/all_posts.csv (UTF-8-sig).
- Outputs summary metrics, date ranges, and sample rows.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

# Patterns for Exchange: HK
HK_TICKER_PATTERNS: Dict[str, Dict[str, Any]] = {
    "0700.HK": {
        "text_terms": ["騰訊", "腾讯", "Tencent"],
        "regex": [
            r"(?<!\d)0700(?!\d)",
            r"(?<!\d)00700(?!\d)",
            r"\$0700",
            r"(?<!\d)700\.hk",
            r"(?<!\d)0700\.hk",
            r"\$tcehy",
        ],
    },
    "9988.HK": {
        "text_terms": ["阿里巴巴", "阿里", "Alibaba", "BABA"],
        "regex": [
            r"(?<!\d)9988(?!\d)",
            r"(?<!\d)09988(?!\d)",
            r"\$9988",
            r"(?<!\d)9988\.hk",
            r"(?<!\d)09988\.hk",
            r"\$baba",
        ],
    },
    "3690.HK": {
        "text_terms": ["美團", "美团", "Meituan"],
        "regex": [
            r"(?<!\d)3690(?!\d)",
            r"(?<!\d)03690(?!\d)",
            r"\$3690",
            r"(?<!\d)3690\.hk",
            r"(?<!\d)03690\.hk",
        ],
    },
    "1810.HK": {
        "text_terms": ["小米", "Xiaomi"],
        "regex": [
            r"(?<!\d)1810(?!\d)",
            r"(?<!\d)01810(?!\d)",
            r"\$1810",
            r"(?<!\d)1810\.hk",
            r"(?<!\d)01810\.hk",
            r"\$xiacy",
        ],
    },
    "0005.HK": {
        "text_terms": ["滙豐", "匯豐", "汇丰", "HSBC", "大笨象"],
        "regex": [
            r"(?<!\d)0005(?!\d)",
            r"(?<!\d)00005(?!\d)",
            r"\$0005",
            r"(?<!\d)0005\.hk",
            r"(?<!\d)00005\.hk",
            r"\$hsbc",
        ],
    },
}

# Patterns for Exchange: KR
KR_TICKER_PATTERNS: Dict[str, Dict[str, Any]] = {
    "005930.KS": {
        "text_terms": ["삼성전자", "삼전", "Samsung Electronics", "Samsung"],
        "regex": [
            r"(?<!\d)005930(?!\d)",
            r"\$005930",
            r"(?<!\d)005930\.ks",
        ],
    },
    "000660.KS": {
        "text_terms": ["SK하이닉스", "하이닉스", "SK Hynix", "SK hynix", "Hynix"],
        "regex": [
            r"(?<!\d)000660(?!\d)",
            r"\$000660",
            r"(?<!\d)000660\.ks",
        ],
    },
    "035420.KS": {
        "text_terms": ["네이버", "NAVER", "Naver"],
        "regex": [
            r"(?<!\d)035420(?!\d)",
            r"\$035420",
            r"(?<!\d)035420\.ks",
        ],
    },
    "035720.KS": {
        "text_terms": ["카카오", "Kakao"],
        "regex": [
            r"(?<!\d)035720(?!\d)",
            r"\$035720",
            r"(?<!\d)035720\.ks",
        ],
    },
    "005380.KS": {
        "text_terms": ["현대차", "현대자동차", "Hyundai Motor", "Hyundai"],
        "regex": [
            r"(?<!\d)005380(?!\d)",
            r"\$005380",
            r"(?<!\d)005380\.ks",
        ],
    },
}


def find_mentioned_tickers(text: str, exchange: str) -> List[str]:
    """Scan text against all 5 tickers of the given exchange."""
    if not isinstance(text, str) or not text.strip():
        return []
    pdict = HK_TICKER_PATTERNS if exchange == "HK" else KR_TICKER_PATTERNS
    t_lower = text.lower()
    matched = []

    for ticker, p in pdict.items():
        found = False
        # 1. Terms matching
        for term in p["text_terms"]:
            if term.isascii():
                if re.search(r"\b" + re.escape(term.lower()) + r"\b", t_lower):
                    found = True
                    break
            else:
                if term in text or term.lower() in t_lower:
                    found = True
                    break
        # 2. Regex matching
        if not found:
            for rpat in p["regex"]:
                if re.search(rpat, text, re.IGNORECASE):
                    found = True
                    break
        if found:
            matched.append(ticker)

    return matched


def retag_dataframe(df: pd.DataFrame, exchange: str) -> Tuple[pd.DataFrame, Dict[str, int], Dict[str, int], int]:
    """Re-tag DataFrame rows according to mentioned tickers."""
    before_counts = df["ticker"].value_counts().to_dict()
    retagged_rows: List[Dict[str, Any]] = []
    dropped_count = 0

    for _, row in df.iterrows():
        matches = find_mentioned_tickers(row.get("text", ""), exchange)
        if not matches:
            dropped_count += 1
            continue

        tickers_cnt = len(matches)
        is_wrap = (tickers_cnt >= 3)
        orig_ticker = row["ticker"]

        for matched_ticker in matches:
            r = row.to_dict()
            r["query_ticker"] = orig_ticker
            r["ticker"] = matched_ticker
            r["tickers_in_post"] = tickers_cnt
            r["is_market_wrap"] = is_wrap
            retagged_rows.append(r)

    retagged_df = pd.DataFrame(retagged_rows)
    if not retagged_df.empty:
        retagged_df = retagged_df.drop_duplicates(subset=["source", "post_id", "ticker"])
        after_counts = retagged_df["ticker"].value_counts().to_dict()
    else:
        after_counts = {}

    return retagged_df, before_counts, after_counts, dropped_count


def process_all_posts():
    """Load, retag, and combine all 4 verified sources."""
    raw_dir = config.RAW_DATA_DIR
    processed_dir = config.PROCESSED_DATA_DIR
    processed_dir.mkdir(parents=True, exist_ok=True)

    out_file = processed_dir / "all_posts.csv"

    # 1. Load Naver (board stock code, no re-tagging)
    naver_file = raw_dir / "posts_KR_naver.csv"
    df_naver = pd.read_csv(naver_file, encoding="utf-8-sig")
    df_naver["query_ticker"] = df_naver["ticker"]
    df_naver["tickers_in_post"] = 1
    df_naver["is_market_wrap"] = False

    # 2. Re-tag LIHKG
    lihkg_file = raw_dir / "posts_HK_lihkg.csv"
    df_lihkg_raw = pd.read_csv(lihkg_file, encoding="utf-8-sig")
    df_lihkg, lihkg_before, lihkg_after, lihkg_dropped = retag_dataframe(df_lihkg_raw, "HK")

    # 3. Re-tag HK Telegram
    hktg_file = raw_dir / "posts_HK_telegram.csv"
    df_hktg_raw = pd.read_csv(hktg_file, encoding="utf-8-sig")
    df_hktg, hktg_before, hktg_after, hktg_dropped = retag_dataframe(df_hktg_raw, "HK")

    # 4. Re-tag KR Telegram
    krtg_file = raw_dir / "posts_KR_telegram.csv"
    df_krtg_raw = pd.read_csv(krtg_file, encoding="utf-8-sig")
    df_krtg, krtg_before, krtg_after, krtg_dropped = retag_dataframe(df_krtg_raw, "KR")

    # Display Before/After Counts
    print("\n" + "=" * 90)
    print("TICKER RE-TAGGING BEFORE / AFTER COMPARISON")
    print("=" * 90)
    print(f"{'Source':<15} {'Ticker':<12} {'Before Retag':<15} {'After Retag':<15} {'Change'}")
    print("-" * 90)

    # LIHKG
    for t in config.ASSETS_BY_EXCHANGE["HK"]:
        b = lihkg_before.get(t, 0)
        a = lihkg_after.get(t, 0)
        diff = a - b
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{'HK/lihkg':<15} {t:<12} {b:<15} {a:<15} {diff_str}")

    print("-" * 90)
    # HK Telegram
    for t in config.ASSETS_BY_EXCHANGE["HK"]:
        b = hktg_before.get(t, 0)
        a = hktg_after.get(t, 0)
        diff = a - b
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{'HK/telegram':<15} {t:<12} {b:<15} {a:<15} {diff_str}")

    print("-" * 90)
    # KR Telegram
    for t in config.ASSETS_BY_EXCHANGE["KR"]:
        b = krtg_before.get(t, 0)
        a = krtg_after.get(t, 0)
        diff = a - b
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{'KR/telegram':<15} {t:<12} {b:<15} {a:<15} {diff_str}")

    print("=" * 90 + "\n")

    # Concatenate all 4 sources
    combined_df = pd.concat([df_naver, df_lihkg, df_hktg, df_krtg], ignore_index=True)
    # Final deduplication guard
    combined_df = combined_df.drop_duplicates(subset=["source", "post_id", "ticker"])
    combined_df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"[SUCCESS] Saved {len(combined_df)} combined posts to {out_file}\n")

    # Print Posts Per Exchange / Source / Ticker Summary Table
    print("=" * 95)
    print("POSTS PER EXCHANGE / SOURCE / TICKER")
    print("=" * 95)
    print(f"{'Exch':<6} {'Source':<12} {'Ticker':<12} {'Count':<8} {'Market Wraps (3+)':<20} {'Unique Posts'}")
    print("-" * 95)

    grouped = combined_df.groupby(["exchange", "source", "ticker"])
    for (exch, src, ticker), group in grouped:
        wraps_cnt = int(group["is_market_wrap"].sum())
        unique_cnt = group["post_id"].nunique()
        print(f"{exch:<6} {src:<12} {ticker:<12} {len(group):<8} {wraps_cnt:<20} {unique_cnt}")

    print("-" * 95)
    print(f"{'TOTAL COMBINED POSTS':<32} {len(combined_df)}")
    print("=" * 95 + "\n")

    # Date Range per Source
    print("=" * 95)
    print("DATE RANGE PER SOURCE")
    print("=" * 95)
    print(f"{'Exchange / Source':<25} {'Total Rows':<12} {'Min Date (UTC)':<24} {'Max Date (UTC)'}")
    print("-" * 95)

    for (exch, src), grp in combined_df.groupby(["exchange", "source"]):
        ts_list = [str(x) for x in grp["timestamp_utc"].dropna() if str(x) != "nan"]
        min_d = min(ts_list) if ts_list else "N/A"
        max_d = max(ts_list) if ts_list else "N/A"
        print(f"{exch + '/' + src:<25} {len(grp):<12} {min_d:<24} {max_d}")

    print("=" * 95 + "\n")

    # Total Actual USD Spent in this Run
    total_spent_usd = 0.160250 + 0.053000
    print("=" * 95)
    print(f"TOTAL ACTUAL USD SPENT IN THIS RUN: ${total_spent_usd:.6f} USD")
    print("  - KR Telegram: $0.160250 USD")
    print("  - LIHKG Extra: $0.053000 USD")
    print("=" * 95 + "\n")

    # 3 Sample Rows of KR Telegram
    print("=" * 95)
    print("3 SAMPLE ROWS OF KR TELEGRAM (Text truncated to 120 chars)")
    print("=" * 95)
    df_krtg_samples = df_krtg.head(3)
    for i, (_, r) in enumerate(df_krtg_samples.iterrows(), 1):
        clean_text = " ".join(str(r.get("text", "")).split())
        trunc = clean_text[:117] + "..." if len(clean_text) > 120 else clean_text
        print(f"[{i}] Ticker: {r.get('ticker')} (Query: {r.get('query_ticker')}) | Wraps: {r.get('is_market_wrap')} (Total in post: {r.get('tickers_in_post')})")
        print(f"    ID: {r.get('post_id')} | UTC: {r.get('timestamp_utc')} | Author: {r.get('author')}")
        print(f"    Text: \"{trunc}\"\n")
    print("=" * 95)


if __name__ == "__main__":
    process_all_posts()
