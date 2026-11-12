# HSI & KRX Sentiment Agent

An end-to-end quantitative social sentiment and price prediction intelligence pipeline for equities listed on the **Hong Kong Exchanges (HKEX)** and **Korea Exchange (KRX)**.

---

## Executive Summary & Deliverables

This repository contains the complete quantitative pipeline: social data collection, relevance filtering, offline multi-ticker cross-tagging, **Google Gemini LLM multilingual sentiment scoring**, and an interactive intelligence dashboard for **10 major equities** across Hong Kong and South Korea:

* **HKEX (Hong Kong)**: Tencent (`0700.HK`), Alibaba (`9988.HK`), Meituan (`3690.HK`), Xiaomi (`1810.HK`), HSBC (`0005.HK`).
* **KRX (South Korea)**: Samsung Electronics (`005930.KS`), SK Hynix (`000660.KS`), NAVER (`035420.KS`), Kakao (`035720.KS`), Hyundai Motor (`005380.KS`).

### Key Highlights
1. **4 Verified High-Signal Sources**:
   - **KR / Naver Stock Discussion**: Real-time retail investor boards (`posts_KR_naver.csv`).
   - **HK / LIHKG Forum**: Major Hong Kong retail investment and stock listening forum (`posts_HK_lihkg.csv`).
   - **HK / Telegram Public Channels**: Finance-filtered Hong Kong market and tech coverage (`posts_HK_telegram.csv`).
   - **KR / Telegram Public Channels**: Korean language retail & institutional market channels (`posts_KR_telegram.csv`).
2. **Master Dataset**: **488 verified posts** compiled into [`data/processed/all_posts_scored.csv`](data/processed/all_posts_scored.csv) with a normalized 24-column schema (UTF-8-sig for native Excel/Numbers support in Chinese & Korean).
3. **Multilingual Gemini LLM Sentiment Scoring**:
   - Scores each post specifically for the assigned equity ticker on a continuous scale from `-1.0` (Bearish) to `+1.0` (Bullish).
   - Generates English financial rationale and model certainty confidence rating.
   - Breakdown: **84 Bullish**, **85 Bearish**, **319 Neutral / Market Wraps**.
4. **Multi-Ticker Cross-Tagging**: Market wrap posts mentioning multiple equities are automatically mapped to each referenced ticker with `query_ticker`, `tickers_in_post`, and `is_market_wrap` flags.
5. **Cost Efficiency**: Entire scraping run was completed for only **$0.213 USD** on Apify (saving > $1.78 USD of the free tier credit), with sentiment scoring completed within the Google AI Studio free tier ($0.00).

---

## How to Run & View the Complete Work

Reviewers and senior team members can inspect the complete pipeline and dataset using any of the following three methods:

### Option 1: Interactive Web Dashboard (Recommended)

Run the included local web application:

```bash
# Using project virtual environment
./venv/bin/python dashboard.py

# Or if your environment is already activated
python dashboard.py
```

* **What happens**: Starts an interactive local server at `http://localhost:8000` and automatically opens your default browser.
* **Features**:
  - **Executive KPI Cards**: Real-time totals, Bullish/Bearish/Neutral counts, ticker count, and API budget efficiency.
  - **Interactive Charts**: Gemini Sentiment Distribution donut chart, net sentiment score by ticker bar chart, and platform breakdown.
  - **Search & Filters**: Instantly filter by Sentiment (Bullish/Bearish/Neutral), Exchange (HKEX/KRX), Platform (Naver/LIHKG/Telegram), Ticker code, or Market Wraps.
  - **Post Inspector**: Click **Inspect** on any row to view full original Chinese/Korean text, Gemini AI English financial reasoning, confidence score, engagement stats (likes, views, replies), and permalink URLs.
  - **One-Click Export**: Download the scored 488-row master dataset directly from the UI.

---

### Option 2: Direct Offline HTML View (Zero Server Needed)

You can view the dashboard completely offline without starting any server or running any commands:

1. Navigate to [`report/dashboard.html`](report/dashboard.html).
2. Double-click the file to open it in **Google Chrome**, **Safari**, or **Microsoft Edge**.
3. All 488 posts, sentiment scores, and interactive Chart.js visualizations are embedded directly inside the HTML file.

---

### Option 3: Direct Master CSV Inspection

Open the scored master dataset in Microsoft Excel, Apple Numbers, or Python:

```bash
# Path to master scored dataset
data/processed/all_posts_scored.csv
```

```python
import pandas as pd
df = pd.read_csv("data/processed/all_posts_scored.csv", encoding="utf-8-sig")
print(df.info())
print(df["gemini_sentiment_label"].value_counts())
print(df.groupby("ticker")["gemini_sentiment_score"].mean())
```

---

## Dataset Breakdown & Sentiment Summary

| Exchange | Ticker | Company Name | Total Posts | Bullish | Bearish | Neutral | Mean Sentiment |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **HK** | `0700.HK` | Tencent Holdings | 24 | 4 | 2 | 18 | **+0.017** |
| **HK** | `9988.HK` | Alibaba Group | 40 | 1 | 3 | 36 | **-0.044** |
| **HK** | `3690.HK` | Meituan | 9 | 1 | 0 | 8 | **+0.044** |
| **HK** | `1810.HK` | Xiaomi Corp | 18 | 1 | 2 | 15 | **-0.039** |
| **HK** | `0005.HK` | HSBC Holdings | 3 | 0 | 0 | 3 | **0.000** |
| **KR** | `005930.KS` | Samsung Electronics | 83 | 24 | 14 | 45 | **+0.107** |
| **KR** | `000660.KS` | SK Hynix | 89 | 19 | 18 | 52 | **-0.007** |
| **KR** | `035420.KS` | NAVER Corp | 69 | 12 | 18 | 39 | **-0.058** |
| **KR** | `035720.KS` | Kakao Corp | 76 | 10 | 14 | 52 | **-0.043** |
| **KR** | `005380.KS` | Hyundai Motor | 77 | 12 | 14 | 51 | **-0.046** |
| **TOTAL** | **10 Equities** | — | **488** | **84** | **85** | **319** | **10-day lookback** |

---

## Normalized 24-Column Schema

Every row in [`data/processed/all_posts_scored.csv`](data/processed/all_posts_scored.csv) adheres strictly to the following normalized schema:

| Column | Type | Description |
| :--- | :--- | :--- |
| `exchange` | string | Exchange code (`HK` or `KR`). |
| `source` | string | Platform name (`naver`, `lihkg`, `telegram`). |
| `ticker` | string | Assigned equity ticker (e.g. `0700.HK`, `005930.KS`). |
| `post_id` | string | Platform-native unique post/thread/message identifier. |
| `timestamp_utc` | string | ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`). |
| `text` | string | Cleaned headline and full body content. |
| `likes` | integer | Upvotes / reactions count. |
| `dislikes` | integer | Downvotes count (Naver/LIHKG). |
| `reposts` | integer | Shares or forwards count (Telegram). |
| `replies` | integer | Comment or reply count. |
| `views` | integer | Impression / view count. |
| `author` | string | Author username or posting channel handle. |
| `author_followers` | integer | Channel subscriber count where available. |
| `url` | string | Direct permalink to source post. |
| `query` | string | Search query or stock code that collected the post. |
| `language` | string | Content language (`zh` for Chinese/Cantonese, `ko` for Korean). |
| `source_native_sentiment` | string | Native platform AI sentiment score (if provided). |
| `query_ticker` | string | Original ticker associated with the scraper query. |
| `tickers_in_post` | integer | Count of tracked equities mentioned in this post. |
| `is_market_wrap` | boolean | `True` if 3 or more tracked equities are referenced. |
| `gemini_sentiment_score` | float | Target-specific sentiment score from `-1.0` (bearish) to `+1.0` (bullish). |
| `gemini_sentiment_label` | string | Sentiment category (`bullish`, `bearish`, or `neutral`). |
| `gemini_confidence` | float | Model certainty confidence score (`0.0` to `1.0`). |
| `gemini_reasoning` | string | Gemini AI quantitative reasoning in English. |

---

## Repository Structure

```
hsi-sentiment-agent/
├── dashboard.py                   # One-click launcher for interactive web dashboard
├── config.py                      # Central asset definitions, keywords, & exchange config
├── requirements-dev.txt           # Dependencies (apify-client, pandas, plotly, etc.)
├── README.md                      # Complete executive guide & documentation
├── data/
│   ├── raw/                       # Platform-specific raw CSV files
│   │   ├── posts_KR_naver.csv     # Naver stock discussion posts (295 rows)
│   │   ├── posts_HK_lihkg.csv     # LIHKG forum threads (9 rows)
│   │   ├── posts_HK_telegram.csv  # HK Telegram public posts (58 rows)
│   │   ├── posts_KR_telegram.csv  # KR Telegram public posts (61 rows)
│   │   └── unused/                # Retired sources (e.g. posts_KR_blind.csv)
│   └── processed/
│       ├── all_posts.csv          # Master combined dataset (488 rows)
│       └── all_posts_scored.csv   # Enriched dataset with Gemini sentiment (488 rows)
├── scrapers/
│   ├── apify_scraper.py           # Production Apify scraping engine
│   ├── retag_and_combine.py       # Offline cross-tagging & deduplication pipeline
│   ├── inspect_actors.py          # Actor schema inspector
│   └── test_actors.py             # Actor unit testing harness
├── report/
│   ├── dashboard.html             # Standalone offline HTML dashboard (interactive)
│   └── generate_dashboard.py      # Dashboard HTML generator script
├── sentiment/
│   └── gemini_scorer.py           # Gemini multilingual financial sentiment scorer
├── features/                      # Market indicators + sentiment feature engineering
└── model/                         # Next-day return prediction models (XGBoost/sklearn)
```

---

## Pipeline Execution Commands

If you need to re-run or inspect individual pipeline components:

```bash
# 1. Preview planned scraping queries & worst-case cost (no network calls, $0.00 cost)
./venv/bin/python scrapers/apify_scraper.py --dry-run

# 2. Re-run offline multi-ticker cross-tagging and dataset generation ($0.00 cost)
./venv/bin/python scrapers/retag_and_combine.py

# 3. Run Gemini multilingual financial sentiment scoring
./venv/bin/python sentiment/gemini_scorer.py --batch-size 12

# 4. Re-build the interactive HTML dashboard ($0.00 cost)
./venv/bin/python report/generate_dashboard.py

# 5. Launch the web dashboard server
./venv/bin/python dashboard.py
```
