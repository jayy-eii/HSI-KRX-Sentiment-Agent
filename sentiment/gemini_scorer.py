#!/usr/bin/env python3
"""Gemini Multilingual Financial Sentiment Scoring Pipeline.

Scores social media sentiment for HKEX and KRX listed equities using Google Gemini API.
Features:
  - Multilingual support (Chinese, Korean, English) with market context.
  - Target-specific sentiment scoring (handles multi-ticker posts accurately).
  - Batch inference (10-15 posts per request) for high speed and token efficiency.
  - Automatic model fallback (gemini-3.6-flash -> gemini-3.5-flash-lite) and exponential backoff.
  - Checkpoint and resume support: skips already scored posts.
  - Preserves full UTF-8-sig master dataset with added sentiment metrics.

Usage:
  python sentiment/gemini_scorer.py [--batch-size 12] [--limit 20] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts.csv"
OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts_scored.csv"

# Recommended models in order of priority
MODELS_PRIORITY = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

SYSTEM_PROMPT = """You are an expert quantitative financial analyst specializing in Hong Kong (HKEX) and South Korean (KRX) equities.
Your task is to analyze social media posts and evaluate investor sentiment towards the specified target ticker.

For each post in the input list:
1. Evaluate sentiment specifically directed at the specified 'ticker' (not general macro or competitors).
2. Assign:
   - 'post_id': exact post_id provided in the input
   - 'sentiment_score': float from -1.0 (extremely bearish) to +1.0 (extremely bullish). 0.0 is neutral.
   - 'sentiment_label': exactly one of ["bullish", "bearish", "neutral"]
   - 'confidence': float between 0.0 and 1.0 representing your certainty
   - 'reasoning': a concise 1-sentence explanation in English explaining key market catalysts or investor attitude

Input is a JSON array of posts.
You MUST respond with ONLY a valid JSON array of objects adhering strictly to the schema."""


def score_batch_with_gemini(
    batch: List[Dict[str, Any]],
    api_key: str,
    models: List[str] = MODELS_PRIORITY,
    max_retries: int = 3,
) -> Optional[List[Dict[str, Any]]]:
    """Call Gemini API to score a batch of posts with fallback and backoff."""
    payload_posts = []
    for item in batch:
        pid = item["post_id"]
        try:
            pid = int(pid)
        except (ValueError, TypeError):
            pid = str(pid)
        payload_posts.append({
            "post_id": pid,
            "ticker": str(item["ticker"]),
            "exchange": str(item.get("exchange", "")),
            "text": str(item.get("text", ""))[:400],
        })

    prompt = f"{SYSTEM_PROMPT}\n\nPosts to analyze:\n{json.dumps(payload_posts, ensure_ascii=False, indent=2)}"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        for attempt in range(max_retries):
            try:
                resp = requests.post(url, headers=headers, json=body, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        text_res = candidates[0]["content"]["parts"][0]["text"]
                        parsed = json.loads(text_res)
                        if isinstance(parsed, list):
                            return parsed
                        elif isinstance(parsed, dict) and "results" in parsed:
                            return parsed["results"]
                elif resp.status_code in (429, 503):
                    wait_time = (2 ** attempt) * 4
                    print(f"  [WARN] {model} returned {resp.status_code}. Backing off {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  [WARN] {model} returned HTTP {resp.status_code}")
                    break  # Try next model in priority
            except Exception as exc:
                wait_time = (2 ** attempt) * 4
                err_type = type(exc).__name__
                print(f"  [WARN] {model} request failed ({err_type}). Retrying in {wait_time}s...")
                time.sleep(wait_time)

    return None


def run_sentiment_pipeline(
    input_path: Path = INPUT_CSV,
    output_path: Path = OUTPUT_CSV,
    batch_size: int = 12,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> pd.DataFrame:
    """Execute end-to-end sentiment scoring pipeline."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found at {input_path}")

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    print(f"[INFO] Loaded {len(df)} total posts from {input_path}")

    if limit is not None and limit > 0:
        df = df.head(limit).copy()
        print(f"[INFO] Limit applied: processing first {limit} posts")

    if dry_run:
        print("[DRY-RUN] Previewing sample batch without scoring entire dataset...")
        api_key = config.get_gemini_api_key(required=True)
        sample_batch = df.head(3).to_dict(orient="records")
        results = score_batch_with_gemini(sample_batch, api_key)
        print("[DRY-RUN RESULTS]:")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return df

    api_key = config.get_gemini_api_key(required=True)

    # Check for existing checkpoint
    scored_dict: Dict[Tuple[Any, str], Dict[str, Any]] = {}
    if output_path.exists():
        try:
            df_existing = pd.read_csv(output_path, encoding="utf-8-sig")
            if "gemini_sentiment_score" in df_existing.columns:
                valid_existing = df_existing.dropna(subset=["gemini_sentiment_score"])
                for _, row in valid_existing.iterrows():
                    reason = str(row.get("gemini_reasoning", ""))
                    # Treat failed fallback rows as pending re-scoring
                    if any(term in reason.lower() for term in ["fallback", "failure", "missing"]):
                        continue
                    key = (row["post_id"], str(row["ticker"]))
                    scored_dict[key] = {
                        "gemini_sentiment_score": float(row["gemini_sentiment_score"]),
                        "gemini_sentiment_label": str(row["gemini_sentiment_label"]),
                        "gemini_confidence": float(row["gemini_confidence"]),
                        "gemini_reasoning": reason,
                    }
                print(f"[INFO] Resuming from verified checkpoint: {len(scored_dict)} high-confidence posts already scored.")
        except Exception as e:
            print(f"[WARN] Could not parse existing checkpoint ({e}). Starting fresh.")

    # Identify pending rows
    pending_indices = []
    for idx, row in df.iterrows():
        key = (row["post_id"], str(row["ticker"]))
        if key not in scored_dict:
            pending_indices.append(idx)

    print(f"[INFO] Pending posts to score: {len(pending_indices)} / {len(df)}")

    if not pending_indices:
        print("[SUCCESS] All posts are already scored in checkpoint.")
        return pd.read_csv(output_path, encoding="utf-8-sig")

    # Process in batches
    total_batches = (len(pending_indices) + batch_size - 1) // batch_size
    print(f"[INFO] Starting batch scoring across {total_batches} batches (batch_size={batch_size})...\n")

    for b_idx in range(total_batches):
        start_i = b_idx * batch_size
        end_i = min(start_i + batch_size, len(pending_indices))
        batch_row_indices = pending_indices[start_i:end_i]

        batch_items = []
        for i in batch_row_indices:
            raw_pid = df.loc[i, "post_id"]
            try:
                clean_pid = int(raw_pid)
            except (ValueError, TypeError):
                clean_pid = str(raw_pid)
            batch_items.append({
                "post_id": clean_pid,
                "ticker": str(df.loc[i, "ticker"]),
                "exchange": str(df.loc[i, "exchange"]),
                "text": str(df.loc[i, "text"]),
            })

        print(f"[{b_idx + 1}/{total_batches}] Scoring batch {b_idx + 1} ({len(batch_items)} posts)...", end=" ", flush=True)
        scored_results = score_batch_with_gemini(batch_items, api_key)

        if scored_results:
            # Map by post_id
            score_by_id = {}
            for item in scored_results:
                pid = item.get("post_id")
                score_by_id[str(pid)] = item
                score_by_id[pid] = item

            matched = 0
            for i in batch_row_indices:
                pid = df.loc[i, "post_id"]
                tck = str(df.loc[i, "ticker"])
                res = score_by_id.get(pid) or score_by_id.get(str(pid))
                if res:
                    scored_dict[(pid, tck)] = {
                        "gemini_sentiment_score": float(res.get("sentiment_score", 0.0)),
                        "gemini_sentiment_label": str(res.get("sentiment_label", "neutral")),
                        "gemini_confidence": float(res.get("confidence", 0.5)),
                        "gemini_reasoning": str(res.get("reasoning", "")),
                    }
                    matched += 1
                else:
                    # Neutral fallback if post was missing in response
                    scored_dict[(pid, tck)] = {
                        "gemini_sentiment_score": 0.0,
                        "gemini_sentiment_label": "neutral",
                        "gemini_confidence": 0.5,
                        "gemini_reasoning": "Model response missing; defaulted to neutral.",
                    }

            print(f"Done ({matched}/{len(batch_items)} matched).")
        else:
            print("FAILED (Defaulting batch to neutral fallback).")
            for i in batch_row_indices:
                pid = df.loc[i, "post_id"]
                tck = str(df.loc[i, "ticker"])
                scored_dict[(pid, tck)] = {
                    "gemini_sentiment_score": 0.0,
                    "gemini_sentiment_label": "neutral",
                    "gemini_confidence": 0.5,
                    "gemini_reasoning": "Batch call failure; defaulted to neutral.",
                }

        # Incremental checkpoint save every 3 batches or on final batch
        if (b_idx + 1) % 3 == 0 or (b_idx + 1) == total_batches:
            _save_checkpoint(df, scored_dict, output_path)

        # Gentle pause to respect rate limits (4.5s keeps RPM under 14)
        time.sleep(4.5)

    final_df = _save_checkpoint(df, scored_dict, output_path)
    _print_summary(final_df)
    return final_df


def _save_checkpoint(
    df: pd.DataFrame,
    scored_dict: Dict[Tuple[Any, str], Dict[str, Any]],
    output_path: Path,
) -> pd.DataFrame:
    """Merge scores into dataframe and persist to CSV with UTF-8-sig."""
    df_out = df.copy()
    scores = []
    labels = []
    confidences = []
    reasonings = []

    for _, row in df_out.iterrows():
        key = (row["post_id"], str(row["ticker"]))
        item = scored_dict.get(key, {})
        scores.append(item.get("gemini_sentiment_score", None))
        labels.append(item.get("gemini_sentiment_label", None))
        confidences.append(item.get("gemini_confidence", None))
        reasonings.append(item.get("gemini_reasoning", None))

    df_out["gemini_sentiment_score"] = scores
    df_out["gemini_sentiment_label"] = labels
    df_out["gemini_confidence"] = confidences
    df_out["gemini_reasoning"] = reasonings

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(output_path, index=False, encoding="utf-8-sig")
    return df_out


def _print_summary(df: pd.DataFrame) -> None:
    """Print executive sentiment distribution summary."""
    print("\n" + "=" * 80)
    print("  GEMINI MULTILINGUAL FINANCIAL SENTIMENT SCORING SUMMARY")
    print("=" * 80)
    print(f"  * Total Posts Scored: {len(df)}")
    
    if "gemini_sentiment_label" in df.columns:
        print("\n  [Sentiment Label Distribution]:")
        dist = df["gemini_sentiment_label"].value_counts()
        for label, count in dist.items():
            pct = (count / len(df)) * 100
            print(f"    - {label.upper():<10}: {count:>4} posts ({pct:.1f}%)")

    if "gemini_sentiment_score" in df.columns:
        print("\n  [Average Sentiment Score by Ticker]:")
        ticker_summary = df.groupby(["exchange", "ticker"]).agg(
            mean_sentiment=("gemini_sentiment_score", "mean"),
            mean_conf=("gemini_confidence", "mean"),
            post_count=("post_id", "count"),
        ).reset_index()
        for _, r in ticker_summary.iterrows():
            sentiment_bar = "+" if r['mean_sentiment'] > 0 else ""
            print(f"    [{r['exchange']}] {r['ticker']:<10}: Mean Score = {sentiment_bar}{r['mean_sentiment']:.3f} | Conf = {r['mean_conf']:.2f} | Count = {r['post_count']}")

    print("=" * 80 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Gemini Financial Sentiment Scorer")
    parser.add_argument("--batch-size", type=int, default=12, help="Posts per Gemini API request")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of posts to process")
    parser.add_argument("--dry-run", action="store_true", help="Test sample batch without writing files")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_sentiment_pipeline(
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
    )
