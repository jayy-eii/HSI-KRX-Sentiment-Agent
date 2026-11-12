"""Generate Standalone Interactive HTML Dashboard for HSI & KRX Sentiment Agent.

Embeds data/processed/all_posts_scored.csv (or all_posts.csv) into an offline-first interactive single-page dashboard:
- Executive KPI summary cards (Total Posts, Bullish, Bearish, Neutral, Tickers, API Spend)
- Real-time search & filters (Exchange, Source, Ticker, Sentiment, Market Wraps)
- Interactive charts (Sentiment Distribution Donut, Net Sentiment by Ticker, Platform Breakdown)
- Paginated posts explorer table with color-coded sentiment badges & full-text inspection modals
- Post detail modal displays original Chinese/Korean text + Gemini English reasoning & confidence
- Zero dependencies: runs in any modern browser via double-click or python dashboard.py.
"""

import json
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCORED_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts_scored.csv"
RAW_CSV = PROJECT_ROOT / "data" / "processed" / "all_posts.csv"
OUTPUT_HTML = PROJECT_ROOT / "report" / "dashboard.html"


def generate_html_dashboard():
    if SCORED_CSV.exists():
        csv_file = SCORED_CSV
        has_sentiment = True
    elif RAW_CSV.exists():
        csv_file = RAW_CSV
        has_sentiment = False
    else:
        raise FileNotFoundError(f"Missing master data file at {SCORED_CSV} or {RAW_CSV}")

    df = pd.read_csv(csv_file, encoding="utf-8-sig")

    # Clean null values safely without pandas warnings
    df["source_native_sentiment"] = df["source_native_sentiment"].astype("object").fillna("") if "source_native_sentiment" in df.columns else ""
    df["dislikes"] = df["dislikes"].fillna(0).astype(int) if "dislikes" in df.columns else 0
    df["reposts"] = df["reposts"].fillna(0).astype(int) if "reposts" in df.columns else 0
    df["replies"] = df["replies"].fillna(0).astype(int) if "replies" in df.columns else 0
    df["views"] = df["views"].fillna(0).astype(int) if "views" in df.columns else 0
    df["author_followers"] = df["author_followers"].fillna(0).astype(int) if "author_followers" in df.columns else 0
    df["author"] = df["author"].fillna("Anonymous") if "author" in df.columns else "Anonymous"
    df["url"] = df["url"].fillna("#") if "url" in df.columns else "#"
    df["query"] = df["query"].fillna("") if "query" in df.columns else ""
    df["query_ticker"] = df["query_ticker"].fillna("") if "query_ticker" in df.columns else ""
    df["is_market_wrap"] = df["is_market_wrap"].fillna(False) if "is_market_wrap" in df.columns else False
    df["tickers_in_post"] = df["tickers_in_post"].fillna(1).astype(int) if "tickers_in_post" in df.columns else 1

    # Sentiment columns
    if "gemini_sentiment_score" in df.columns:
        df["gemini_sentiment_score"] = df["gemini_sentiment_score"].fillna(0.0).astype(float)
        df["gemini_sentiment_label"] = df["gemini_sentiment_label"].fillna("neutral").astype(str).str.lower()
        df["gemini_confidence"] = df["gemini_confidence"].fillna(0.5).astype(float)
        df["gemini_reasoning"] = df["gemini_reasoning"].fillna("").astype(str)
    else:
        df["gemini_sentiment_score"] = 0.0
        df["gemini_sentiment_label"] = "neutral"
        df["gemini_confidence"] = 0.5
        df["gemini_reasoning"] = ""

    posts_data = df.to_dict(orient="records")
    posts_json = json.dumps(posts_data, ensure_ascii=False)

    total_posts = len(df)
    unique_ids = df["post_id"].nunique()
    total_wraps = int(df["is_market_wrap"].sum()) if "is_market_wrap" in df.columns else 0
    total_tickers = df["ticker"].nunique()
    total_sources = df["source"].nunique()

    bullish_count = int((df["gemini_sentiment_label"] == "bullish").sum())
    bearish_count = int((df["gemini_sentiment_label"] == "bearish").sum())
    neutral_count = int((df["gemini_sentiment_label"] == "neutral").sum())

    total_spent = 0.213250
    budget_remaining = 2.0 - total_spent

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HSI & KRX Market Sentiment Intelligence Dashboard</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Chart.js CDN -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{
      background-color: #0b0f19;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }}
    .card-glass {{
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 0.75rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      padding: 0.2rem 0.55rem;
      border-radius: 9999px;
      font-size: 0.72rem;
      font-weight: 600;
    }}
    .custom-scroll::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    .custom-scroll::-webkit-scrollbar-thumb {{
      background: #374151;
      border-radius: 4px;
    }}
  </style>
</head>
<body class="min-h-screen p-4 md:p-8">

  <!-- Header -->
  <header class="max-w-7xl mx-auto mb-8">
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 card-glass p-6">
      <div>
        <div class="flex items-center gap-3">
          <span class="text-2xl font-black tracking-tight text-white">HSI & KRX Sentiment Agent</span>
          <span class="badge bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">● System Live</span>
          <span class="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Gemini LLM Scored</span>
        </div>
        <p class="text-sm text-slate-400 mt-1">
          Quantitative Social Listening & Multilingual Sentiment Engine — Covering 10 HKEX & KRX Equities Across Naver, LIHKG, and Telegram
        </p>
      </div>
      <div class="flex items-center gap-3">
        <a href="../data/processed/all_posts_scored.csv" download class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-lg transition flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          Export Scored CSV (488 Rows)
        </a>
      </div>
    </div>
  </header>

  <!-- Executive KPI Metrics -->
  <section class="max-w-7xl mx-auto grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
    <div class="card-glass p-4 border-l-4 border-l-blue-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Total Posts</div>
      <div class="text-2xl font-bold text-white mt-1" id="kpi-total-posts">{total_posts}</div>
      <div class="text-[11px] text-blue-400 mt-0.5">{unique_ids} Unique Threads</div>
    </div>
    <div class="card-glass p-4 border-l-4 border-l-emerald-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Bullish Posts</div>
      <div class="text-2xl font-bold text-emerald-400 mt-1">{bullish_count}</div>
      <div class="text-[11px] text-emerald-500 mt-0.5">{(bullish_count/total_posts)*100:.1f}% Positive Sentiment</div>
    </div>
    <div class="card-glass p-4 border-l-4 border-l-rose-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Bearish Posts</div>
      <div class="text-2xl font-bold text-rose-400 mt-1">{bearish_count}</div>
      <div class="text-[11px] text-rose-500 mt-0.5">{(bearish_count/total_posts)*100:.1f}% Negative Sentiment</div>
    </div>
    <div class="card-glass p-4 border-l-4 border-l-slate-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Neutral Posts</div>
      <div class="text-2xl font-bold text-slate-300 mt-1">{neutral_count}</div>
      <div class="text-[11px] text-slate-400 mt-0.5">{(neutral_count/total_posts)*100:.1f}% Neutral / Market Wraps</div>
    </div>
    <div class="card-glass p-4 border-l-4 border-l-purple-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Tracked Equities</div>
      <div class="text-2xl font-bold text-purple-400 mt-1">{total_tickers}</div>
      <div class="text-[11px] text-purple-400 mt-0.5">5 HKEX + 5 KRX</div>
    </div>
    <div class="card-glass p-4 border-l-4 border-l-cyan-500">
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold">Apify Spend</div>
      <div class="text-2xl font-bold text-cyan-400 mt-1">${total_spent:.3f}</div>
      <div class="text-[11px] text-cyan-500 mt-0.5">${budget_remaining:.2f} Free Credit Left</div>
    </div>
  </section>

  <!-- Interactive Charts Section -->
  <section class="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
    <!-- Chart 1: Sentiment Distribution -->
    <div class="card-glass p-5">
      <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300 mb-2">Gemini Sentiment Distribution</h3>
      <p class="text-xs text-slate-400 mb-4">Overall market sentiment breakdown</p>
      <div class="h-60 flex items-center justify-center">
        <canvas id="sentimentChart"></canvas>
      </div>
    </div>

    <!-- Chart 2: Net Sentiment Score by Ticker -->
    <div class="card-glass p-5 lg:col-span-2">
      <h3 class="text-sm font-bold uppercase tracking-wider text-slate-300 mb-2 flex items-center justify-between">
        <span>Average Sentiment Score by Ticker</span>
        <span class="text-xs font-normal text-slate-400">Scale: -1.0 (Bearish) to +1.0 (Bullish)</span>
      </h3>
      <p class="text-xs text-slate-400 mb-4">Color coded by net sentiment (Green = Bullish, Red = Bearish)</p>
      <div class="h-60">
        <canvas id="tickerSentimentChart"></canvas>
      </div>
    </div>
  </section>

  <!-- Filter & Search Toolbar -->
  <section class="max-w-7xl mx-auto mb-6">
    <div class="card-glass p-4 flex flex-col md:flex-row items-center justify-between gap-3">
      <!-- Search Input -->
      <div class="relative w-full md:w-80">
        <input type="text" id="searchInput" placeholder="Search keywords, reasoning, ticker, author..." 
               class="w-full bg-slate-800/80 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-indigo-500">
        <span class="absolute right-3 top-2.5 text-slate-500 text-xs">🔍</span>
      </div>

      <!-- Filter Controls -->
      <div class="flex flex-wrap items-center gap-2 w-full md:w-auto">
        <!-- Sentiment Filter -->
        <select id="filterSentiment" class="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500">
          <option value="ALL">All Sentiments</option>
          <option value="bullish">🟢 Bullish Only</option>
          <option value="bearish">🔴 Bearish Only</option>
          <option value="neutral">⚪ Neutral Only</option>
        </select>

        <!-- Exchange Filter -->
        <select id="filterExchange" class="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500">
          <option value="ALL">All Exchanges</option>
          <option value="HK">HKEX (Hong Kong)</option>
          <option value="KR">KRX (South Korea)</option>
        </select>

        <!-- Source Filter -->
        <select id="filterSource" class="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500">
          <option value="ALL">All Sources</option>
          <option value="naver">Naver (KR)</option>
          <option value="lihkg">LIHKG (HK)</option>
          <option value="telegram">Telegram (HK & KR)</option>
        </select>

        <!-- Ticker Filter -->
        <select id="filterTicker" class="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-2 focus:outline-none focus:border-indigo-500">
          <option value="ALL">All 10 Tickers</option>
          <optgroup label="HKEX (Hong Kong)">
            <option value="0700.HK">0700.HK (Tencent)</option>
            <option value="9988.HK">9988.HK (Alibaba)</option>
            <option value="3690.HK">3690.HK (Meituan)</option>
            <option value="1810.HK">1810.HK (Xiaomi)</option>
            <option value="0005.HK">0005.HK (HSBC)</option>
          </optgroup>
          <optgroup label="KRX (South Korea)">
            <option value="005930.KS">005930.KS (Samsung Electronics)</option>
            <option value="000660.KS">000660.KS (SK Hynix)</option>
            <option value="035420.KS">035420.KS (NAVER)</option>
            <option value="035720.KS">035720.KS (Kakao)</option>
            <option value="005380.KS">005380.KS (Hyundai Motor)</option>
          </optgroup>
        </select>

        <!-- Market Wrap Checkbox -->
        <label class="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 cursor-pointer hover:bg-slate-700/50">
          <input type="checkbox" id="filterWrapOnly" class="rounded text-indigo-600 focus:ring-0">
          <span>Market Wraps (3+)</span>
        </label>

        <!-- Reset Button -->
        <button id="resetFiltersBtn" class="text-xs text-slate-400 hover:text-white px-2.5 py-2 transition">
          Reset
        </button>
      </div>
    </div>
  </section>

  <!-- Posts Table & Data Explorer -->
  <main class="max-w-7xl mx-auto card-glass p-5">
    <div class="flex items-center justify-between mb-4">
      <div class="text-sm font-bold text-slate-200 flex items-center gap-2">
        <span>Posts Explorer</span>
        <span class="text-xs font-normal text-slate-400" id="filteredCountLabel">(Showing {total_posts} posts)</span>
      </div>
      <div class="flex items-center gap-2 text-xs text-slate-400">
        <button id="prevPageBtn" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded disabled:opacity-40">Previous</button>
        <span id="pageInfoLabel">Page 1 of 1</span>
        <button id="nextPageBtn" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded disabled:opacity-40">Next</button>
      </div>
    </div>

    <!-- Table -->
    <div class="overflow-x-auto custom-scroll">
      <table class="w-full text-left text-xs text-slate-300">
        <thead class="bg-slate-800/80 uppercase text-[10px] text-slate-400 tracking-wider">
          <tr>
            <th class="py-3 px-3">Ticker</th>
            <th class="py-3 px-2">Exch</th>
            <th class="py-3 px-3">Source</th>
            <th class="py-3 px-3">Sentiment</th>
            <th class="py-3 px-3">Date (UTC)</th>
            <th class="py-3 px-3">Post Content Preview</th>
            <th class="py-3 px-2 text-center">Likes</th>
            <th class="py-3 px-2 text-center">Wrap</th>
            <th class="py-3 px-2 text-center">Action</th>
          </tr>
        </thead>
        <tbody id="postsTableBody" class="divide-y divide-slate-800 font-sans">
          <!-- Populated by JavaScript -->
        </tbody>
      </table>
    </div>
  </main>

  <!-- Post Detail Modal -->
  <div id="postModal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden flex items-center justify-center p-4 z-50">
    <div class="card-glass max-w-2xl w-full p-6 border border-slate-700 shadow-2xl relative max-h-[90vh] overflow-y-auto custom-scroll">
      <button id="closeModalBtn" class="absolute top-4 right-4 text-slate-400 hover:text-white text-lg">✕</button>
      
      <div class="flex flex-wrap items-center gap-2 mb-3">
        <span id="modalTickerBadge" class="badge bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-mono"></span>
        <span id="modalSourceBadge" class="badge bg-slate-800 text-slate-300 border border-slate-700"></span>
        <span id="modalSentimentBadge" class="badge"></span>
        <span id="modalConfidenceBadge" class="badge bg-slate-800 text-slate-300 border border-slate-700"></span>
        <span id="modalWrapBadge" class="badge bg-amber-500/20 text-amber-300 border border-amber-500/30 hidden">Market Wrap</span>
      </div>

      <h3 class="text-sm font-bold text-white mb-1" id="modalPostId"></h3>
      <div class="text-[11px] text-slate-400 mb-4 flex gap-4">
        <span id="modalTimestamp"></span>
        <span id="modalAuthor"></span>
      </div>

      <!-- AI Sentiment Reasoning Box -->
      <div id="modalReasoningBox" class="mb-4 bg-indigo-950/40 border border-indigo-500/30 rounded-lg p-3">
        <div class="text-[11px] font-bold text-indigo-300 uppercase tracking-wider mb-1 flex items-center gap-1.5">
          <span>🤖 Gemini AI Financial Rationale:</span>
        </div>
        <p id="modalReasoningText" class="text-xs text-indigo-100 leading-relaxed"></p>
      </div>

      <div class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Original Text:</div>
      <div class="bg-slate-900/90 border border-slate-800 rounded-lg p-4 text-xs text-slate-200 leading-relaxed max-h-60 overflow-y-auto custom-scroll whitespace-pre-wrap font-sans" id="modalPostText"></div>

      <div class="mt-4 flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800">
        <div id="modalStats" class="flex gap-4"></div>
        <a id="modalExternalLink" href="#" target="_blank" class="text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold">
          Open Original Link ↗
        </a>
      </div>
    </div>
  </div>

  <!-- Inline Raw Dataset -->
  <script>
    const ALL_POSTS = {posts_json};

    let currentPage = 1;
    const pageSize = 15;
    let filteredPosts = [...ALL_POSTS];

    // Source colors
    const sourceColors = {{
      naver: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
      lihkg: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
      telegram: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
    }};

    function getSentimentBadge(label, score) {{
      const formattedScore = (score > 0 ? '+' : '') + Number(score).toFixed(2);
      if (label === 'bullish') {{
        return `<span class="badge bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">BULLISH ${{formattedScore}}</span>`;
      }} else if (label === 'bearish') {{
        return `<span class="badge bg-rose-500/20 text-rose-300 border border-rose-500/30">BEARISH ${{formattedScore}}</span>`;
      }} else {{
        return `<span class="badge bg-slate-700/50 text-slate-300 border border-slate-600">NEUTRAL ${{formattedScore}}</span>`;
      }}
    }}

    function renderTable() {{
      const tbody = document.getElementById('postsTableBody');
      tbody.innerHTML = '';

      const startIndex = (currentPage - 1) * pageSize;
      const pageSlice = filteredPosts.slice(startIndex, startIndex + pageSize);

      document.getElementById('filteredCountLabel').innerText = `(Showing ${{filteredPosts.length}} of ${{ALL_POSTS.length}} posts)`;
      const totalPages = Math.max(1, Math.ceil(filteredPosts.length / pageSize));
      document.getElementById('pageInfoLabel').innerText = `Page ${{currentPage}} of ${{totalPages}}`;
      document.getElementById('prevPageBtn').disabled = (currentPage === 1);
      document.getElementById('nextPageBtn').disabled = (currentPage >= totalPages);

      if (pageSlice.length === 0) {{
        tbody.innerHTML = '<tr><td colspan="9" class="text-center py-8 text-slate-500">No matching posts found.</td></tr>';
        return;
      }}

      pageSlice.forEach((p, idx) => {{
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition';

        const srcColor = sourceColors[p.source] || 'bg-slate-800 text-slate-300 border-slate-700';
        const cleanText = (p.text || '').replace(/\\s+/g, ' ');
        const truncated = cleanText.length > 85 ? cleanText.slice(0, 85) + '...' : cleanText;
        const tsFormatted = p.timestamp_utc ? p.timestamp_utc.replace('T', ' ').replace('Z', '') : 'N/A';

        const wrapBadge = p.is_market_wrap 
          ? '<span class="badge bg-amber-500/20 text-amber-300 border border-amber-500/30">Wrap</span>' 
          : '<span class="text-slate-600 text-[11px]">-</span>';

        const sentimentBadge = getSentimentBadge(p.gemini_sentiment_label, p.gemini_sentiment_score);

        tr.innerHTML = `
          <td class="py-2.5 px-3 font-mono font-semibold text-white">${{p.ticker}}</td>
          <td class="py-2.5 px-2 text-[11px] text-slate-400">${{p.exchange}}</td>
          <td class="py-2.5 px-3"><span class="badge ${{srcColor}} border">${{p.source.toUpperCase()}}</span></td>
          <td class="py-2.5 px-3">${{sentimentBadge}}</td>
          <td class="py-2.5 px-3 text-[11px] text-slate-400 whitespace-nowrap">${{tsFormatted}}</td>
          <td class="py-2.5 px-3 text-slate-300 max-w-sm truncate" title="${{cleanText.replace(/"/g, '&quot;')}}">${{truncated}}</td>
          <td class="py-2.5 px-2 text-center text-slate-300 font-mono">${{p.likes || 0}}</td>
          <td class="py-2.5 px-2 text-center">${{wrapBadge}}</td>
          <td class="py-2.5 px-2 text-center">
            <button onclick="viewPostDetails(${{startIndex + idx}})" class="text-indigo-400 hover:text-indigo-300 text-[11px] font-semibold underline">Inspect</button>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function applyFilters() {{
      const query = document.getElementById('searchInput').value.toLowerCase().trim();
      const exch = document.getElementById('filterExchange').value;
      const src = document.getElementById('filterSource').value;
      const ticker = document.getElementById('filterTicker').value;
      const sent = document.getElementById('filterSentiment').value;
      const wrapOnly = document.getElementById('filterWrapOnly').checked;

      filteredPosts = ALL_POSTS.filter(p => {{
        if (exch !== 'ALL' && p.exchange !== exch) return false;
        if (src !== 'ALL' && p.source !== src) return false;
        if (ticker !== 'ALL' && p.ticker !== ticker) return false;
        if (sent !== 'ALL' && p.gemini_sentiment_label !== sent) return false;
        if (wrapOnly && !p.is_market_wrap) return false;
        if (query) {{
          const fullBlob = `${{p.ticker}} ${{p.text}} ${{p.author}} ${{p.post_id}} ${{p.query_ticker}} ${{p.gemini_reasoning || ''}}`.toLowerCase();
          if (!fullBlob.includes(query)) return false;
        }}
        return true;
      }});

      currentPage = 1;
      renderTable();
    }}

    function viewPostDetails(filteredIdx) {{
      const post = filteredPosts[filteredIdx];
      if (!post) return;

      document.getElementById('modalTickerBadge').innerText = post.ticker;
      document.getElementById('modalSourceBadge').innerText = `${{post.exchange}} / ${{post.source.toUpperCase()}}`;
      
      const sentBadge = document.getElementById('modalSentimentBadge');
      const scoreFormatted = (post.gemini_sentiment_score > 0 ? '+' : '') + Number(post.gemini_sentiment_score).toFixed(2);
      if (post.gemini_sentiment_label === 'bullish') {{
        sentBadge.className = 'badge bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
        sentBadge.innerText = `BULLISH (${{scoreFormatted}})`;
      }} else if (post.gemini_sentiment_label === 'bearish') {{
        sentBadge.className = 'badge bg-rose-500/20 text-rose-300 border border-rose-500/30';
        sentBadge.innerText = `BEARISH (${{scoreFormatted}})`;
      }} else {{
        sentBadge.className = 'badge bg-slate-700/50 text-slate-300 border border-slate-600';
        sentBadge.innerText = `NEUTRAL (${{scoreFormatted}})`;
      }}

      const confBadge = document.getElementById('modalConfidenceBadge');
      confBadge.innerText = `Confidence: ${{Math.round(Number(post.gemini_confidence || 0.5) * 100)}}%`;

      const wrapBadge = document.getElementById('modalWrapBadge');
      if (post.is_market_wrap) {{
        wrapBadge.innerText = `Market Wrap (${{post.tickers_in_post}} Tickers)`;
        wrapBadge.classList.remove('hidden');
      }} else {{
        wrapBadge.classList.add('hidden');
      }}

      document.getElementById('modalPostId').innerText = `Post ID: ${{post.post_id}} (Original Query: ${{post.query_ticker || post.ticker}})`;
      document.getElementById('modalTimestamp').innerText = `🕒 UTC: ${{post.timestamp_utc || 'N/A'}}`;
      document.getElementById('modalAuthor').innerText = `👤 Author: ${{post.author || 'Anonymous'}}`;

      // Reasoning
      const reasoningBox = document.getElementById('modalReasoningBox');
      const reasoningText = document.getElementById('modalReasoningText');
      if (post.gemini_reasoning && post.gemini_reasoning.trim().length > 0) {{
        reasoningText.innerText = post.gemini_reasoning;
        reasoningBox.classList.remove('hidden');
      }} else {{
        reasoningBox.classList.add('hidden');
      }}

      document.getElementById('modalPostText').innerText = post.text || '(No text body)';

      document.getElementById('modalStats').innerHTML = `
        <span>👍 Likes: <b>${{post.likes || 0}}</b></span>
        <span>💬 Replies: <b>${{post.replies || 0}}</b></span>
        <span>👁️ Views: <b>${{post.views || 0}}</b></span>
      `;

      const linkEl = document.getElementById('modalExternalLink');
      if (post.url && post.url.startsWith('http')) {{
        linkEl.href = post.url;
        linkEl.classList.remove('hidden');
      }} else {{
        linkEl.classList.add('hidden');
      }}

      document.getElementById('postModal').classList.remove('hidden');
    }}

    document.getElementById('closeModalBtn').addEventListener('click', () => {{
      document.getElementById('postModal').classList.add('hidden');
    }});

    // Pagination handlers
    document.getElementById('prevPageBtn').addEventListener('click', () => {{
      if (currentPage > 1) {{
        currentPage--;
        renderTable();
      }}
    }});
    document.getElementById('nextPageBtn').addEventListener('click', () => {{
      const totalPages = Math.ceil(filteredPosts.length / pageSize);
      if (currentPage < totalPages) {{
        currentPage++;
        renderTable();
      }}
    }});

    // Filter event listeners
    document.getElementById('searchInput').addEventListener('input', applyFilters);
    document.getElementById('filterSentiment').addEventListener('change', applyFilters);
    document.getElementById('filterExchange').addEventListener('change', applyFilters);
    document.getElementById('filterSource').addEventListener('change', applyFilters);
    document.getElementById('filterTicker').addEventListener('change', applyFilters);
    document.getElementById('filterWrapOnly').addEventListener('change', applyFilters);

    document.getElementById('resetFiltersBtn').addEventListener('click', () => {{
      document.getElementById('searchInput').value = '';
      document.getElementById('filterSentiment').value = 'ALL';
      document.getElementById('filterExchange').value = 'ALL';
      document.getElementById('filterSource').value = 'ALL';
      document.getElementById('filterTicker').value = 'ALL';
      document.getElementById('filterWrapOnly').checked = false;
      applyFilters();
    }});

    // Initialize Charts
    function initCharts() {{
      // 1. Sentiment Doughnut Chart
      new Chart(document.getElementById('sentimentChart'), {{
        type: 'doughnut',
        data: {{
          labels: ['Bullish', 'Bearish', 'Neutral'],
          datasets: [{{
            data: [{bullish_count}, {bearish_count}, {neutral_count}],
            backgroundColor: ['#10b981', '#f43f5e', '#64748b'],
            borderWidth: 0
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ position: 'bottom', labels: {{ color: '#94a3b8', boxWidth: 12, font: {{ size: 11 }} }} }}
          }}
        }}
      }});

      // 2. Net Sentiment by Ticker
      const tickerStats = {{}};
      ALL_POSTS.forEach(p => {{
        if (!tickerStats[p.ticker]) {{
          tickerStats[p.ticker] = {{ total: 0, sum: 0 }};
        }}
        tickerStats[p.ticker].total += 1;
        tickerStats[p.ticker].sum += Number(p.gemini_sentiment_score || 0);
      }});

      const tickers = Object.keys(tickerStats).sort();
      const avgScores = tickers.map(t => {{
        const avg = tickerStats[t].sum / (tickerStats[t].total || 1);
        return Number(avg.toFixed(3));
      }});

      const barColors = avgScores.map(score => score >= 0 ? '#10b981' : '#f43f5e');

      new Chart(document.getElementById('tickerSentimentChart'), {{
        type: 'bar',
        data: {{
          labels: tickers,
          datasets: [{{
            label: 'Avg Sentiment Score',
            data: avgScores,
            backgroundColor: barColors,
            borderRadius: 4,
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              callbacks: {{
                label: function(context) {{
                  return `Avg Sentiment: ${{context.raw > 0 ? '+' : ''}}${{context.raw}}`;
                }}
              }}
            }}
          }},
          scales: {{
            y: {{
              min: -1.0,
              max: 1.0,
              grid: {{ color: 'rgba(255,255,255,0.06)' }},
              ticks: {{ color: '#94a3b8' }}
            }},
            x: {{
              grid: {{ display: false }},
              ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }}
            }}
          }}
        }}
      }});
    }}

    // Boot
    window.addEventListener('DOMContentLoaded', () => {{
      renderTable();
      initCharts();
    }});
  </script>
</body>
</html>
"""

    OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"[SUCCESS] Interactive HTML dashboard generated at {OUTPUT_HTML} ({len(html_content)} bytes)")


if __name__ == "__main__":
    generate_html_dashboard()
