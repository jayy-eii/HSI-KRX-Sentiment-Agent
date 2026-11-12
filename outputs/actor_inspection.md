# Apify Actor Inspection Report

> Generated via `scrapers/inspect_actors.py` querying Apify REST API (`/v2/acts/` and `/v2/actor-builds/`).

## HK/lihkg (Primary): `claude_code_reviewer~lihkg-scraper-en`

**Title**: LIHKG Scraper – Keyword Search, Replies & HK Social Listening  
**Role / Scope**: LIHKG forum scraper for Hong Kong retail discussion & sentiment  
**Latest Build ID**: `uvaFPHU5cU8QdaXif`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `PAY_PER_EVENT`
  - **`apify-actor-start`** (`Actor Start`): `$0.00500` (One-time per run) — Charged when the Actor starts running. Number of events charged depends on Actor memory (one event per GB, minimum one event).
  - **`search-listing`** (`Thread`): `$0.00200` (Per event) — Charged per LIHKG thread listed — title, author, reply count, likes/dislikes.
  - **`product-detail`** (`Thread content`): `$0.00800` (Per event) — Charged per LIHKG thread fetched — main post content, author, category.
  - **`review-item`** (`Reply`): `$0.00300` (Per event) — Charged per LIHKG reply — floor, author, content, time.
  - **`ai-label`** (`AI sentiment label`): `$0.00200` (Per event) — Charged per successfully labelled row when AI sentiment labels are on — relevance, sentiment score and label, intent and confidence. Rows whose labelling fails are not charged.

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `mode` | `string` | No | `thread-list` | What do you want to scrape? Pick a mode and fill in the matching fields below. |
| `catIds` | `array` | No | `[]` | LIHKG category IDs (numeric), e.g. 1 (Chat), 2 (Sports), 5 (Current Affairs). Used by listing mode. Enter all to expand to every one of the 37 postable categories (aggregate boards such as Hot / Latest / Custom are excluded automatically); maxItems is a per-category cap, not a total. |
| `threadIds` | `array` | No | `[]` | LIHKG thread IDs (numeric), e.g. 1234567. Used by thread mode. |
| `threadUrls` | `array` | No | `[]` | Full LIHKG thread URLs, e.g. https://lihkg.com/thread/1234567/page/1. The thread ID is extracted automatically. |
| `bulkInput` | `string` | No | *None* | **One item per line** (press Enter for a new line, no quotes or commas). Treated as category IDs in listing mode, thread IDs/URLs in thread mode, or keywords in search mode, and merged into the matching field above at runtime. Fastest way is to copy a whole column from Google Sheets / Excel. |
| `maxItems` | `integer` | No | `50` | Listing mode: max threads per category. Thread mode: max threads to scrape (replies are all fetched by default; set maxReplies to cap replies per thread, by floor). Search mode: max results per keyword. Maximum 2000. |
| `maxReplies` | `integer` | No | *None* | Thread mode only. Maximum number of replies to collect per thread. Every reply is billed as one review-item and a long thread can have thousands of replies, so set this to cap your cost per thread. Takes the first N reply floors of each thread (by floor number; deleted floors can make it slightly fewer than N). Leave empty for no limit (default: the whole thread). Unrelated to Max items, which limits the number of threads. |
| `keywords` | `array` | No | `[]` | Search mode: the keywords to search for (brand names, product names, property developers); each keyword runs its own search. Listing mode: only keep threads whose title contains at least one keyword (filter; leave empty for no filtering). Bulk-pasted lines are merged in here in search mode. |
| `order` | `string` | No | `desc_reply_time` | Search mode only. Latest replies first suits monitoring (with dateFrom it also stops paging early); newest threads first shows freshly opened threads; relevance first suits research. |
| `dateFrom` | `string` | No | *None* | Formats: relative 3d (last 3 days), 12h (last 12 hours), 2w (last 2 weeks), or an absolute date MM/DD/YY. Leave empty for no filtering. When set, paging also stops early, which keeps scheduled monitoring cheap. |
| `aiLabels` | `boolean` | No | `False` | When on, every row gets extra AI-judged fields: whether it concerns your tracked topic (ai_relevance), a sentiment score and negative/neutral/positive label (ai_sentiment, ai_sentiment_label), the intent (ai_intent: complaint / praise / question / other) and a confidence score for each. Each successfully labelled row is billed $0.002 (the ai-label event); rows whose labelling fails are not billed. Text is sent to TypeSafe (US) for processing. Free plan: the first 20 rows per run are labelled. Off by default. |
| `aiTopic` | `string` | No | *None* | Optional. The AI judges whether each post is about this brand or topic (ai_relevance). When empty: search mode uses the row's search keyword; category-listing and thread modes skip the relevance question and ai_relevance is null, while the other labels are still produced. Only used when AI sentiment labels are on. |
| `onlyNew` | `boolean` | No | `False` | When on, only items NOT returned by earlier runs with the same state key are returned; already-seen items are skipped and not charged. List/search modes identify items by thread ID, thread mode by reply ID (the thread's main post is output only for a new thread or together with a new reply). The first run behaves like a normal run and seeds the memory. Off by default; behaviour is then exactly as before. |
| `stateKey` | `string` | No | *None* | Name for the remembered state. Leave empty to derive it from the mode and filters, so the same scheduled input continues where it left off; set it to keep separate memories for different schedules or integrations (most API callers reuse inputs). Letters, digits, underscore and hyphen only, 1-100 characters. Only used when "Only new items" is on. |
| `proxyConfiguration` | `object` | No | `{"useApifyProxy": true}` | Apify datacenter proxy is on by default. Without a proxy your run shares the platform's egress IPs with every other run, so LIHKG rate-limits you for traffic you never sent (429s, missing reply pages). Responses are small JSON, so proxy bandwidth cost is negligible. Turn it off only for local testing or your own proxyUrls. |

### 3. Output Fields (seen in README / Dataset Schema)

- `thread_id` (string): Unique LIHKG thread identifier
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
- (Replies mode includes `floor`, `author_id`, `content`, `own_text`, `like_count`, `dislike_count`)

### 4. Operational Limits & Usage Notes

- **Authentication / Login**: No LIHKG account or login required (uses public `api_v2` JSON endpoint).
- **Date Filter**: `dateFrom` accepts ISO-8601 or `YYYY-MM-DD` timestamps to only fetch active threads since that date.
- **Max Items**: `maxItems` caps threads collected (default 50); `maxReplies` caps replies per thread.
- **Language**: Posts are in Cantonese / Traditional Chinese. Does not auto-translate.

---

## HK/telegram (Primary): `lofomachines~telegram-keyword-search-scraper`

**Title**: Telegram Keyword Search Scraper  
**Role / Scope**: Telegram keyword search & channel post scraper  
**Latest Build ID**: `Vt2rkr7t08wgcE4lD`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `PAY_PER_EVENT`
  - **`apify-actor-start`** (`Actor Start`): `$0.00005` (One-time per run) — Charged when the Actor starts running. Number of events charged depends on Actor memory (one event per GB, minimum one event).
  - **`apify-default-dataset-item`** (`result`): `$0.00250` (Per event) — Single result in the default dataset.

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `mode` | `string` | **Yes** | `channel` | Choose how to discover Telegram posts: - **Keyword Search** — searches your keywords across any public channel. Best for topic discovery. - **Channel Scraping** — paginates backwards through the history of channels you already know. Best for monitoring specific sources. |
| `keywords` | `array` | No | *None* | Words or phrases to search for. Each entry triggers a separate search across public Telegram posts. Example: `bitcoin`, `NATO offensive`, `crypto airdrop`. |
| `afterDate` | `string` | No | *None* | Return only posts published **on or after** this date. Select a specific date or type a relative expression — e.g. `7 days`, `2 weeks`, `1 month`, `1 year`. Leave empty for no lower bound. *(Optional)* |
| `beforeDate` | `string` | No | *None* | Return only posts published **before** this date. Leave empty for no upper bound. *(Optional)* |
| `maxResultsPerKeyword` | `integer` | No | `100` | Maximum number of search results to collect per keyword. Results arrive in pages of 10 — higher values give broader coverage but take longer to run. |
| `countryCode` | `string` | No | `us` | Regional bias for search results. Affects which regional results are prioritised. Select from the list or type any [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) code. *(Optional)* |
| `languageCode` | `string` | No | `en` | Language preference for search results. Select from the list or type any [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes) code. *(Optional)* |
| `channels` | `array` | No | *None* | Public Telegram channel usernames to scrape. The `@` prefix is optional — both `durov` and `@durov` are accepted. Add one username per line. |
| `channelMaxMessages` | `integer` | No | `100` | Maximum number of messages to collect per channel. The scraper stops as soon as this limit **or** the *Published after* cutoff is reached — whichever comes first. |
| `channelAfterDate` | `string` | No | *None* | Collect only messages published **on or after** this date (inclusive). Select a specific date or type a relative expression — e.g. `7 days`, `2 weeks`, `1 month`, `1 year`. Leave empty to collect the most recent messages up to the limit above. *(Optional)* |

### 3. Output Fields (seen in README / Dataset Schema)

- `messageId` (integer): Telegram message ID
- `text` (string): Extracted text content of post/message
- `date` (string / timestamp): Message publication date
- `channelTitle` (string): Name of the publishing Telegram channel
- `channelUsername` (string): Public channel @handle
- `views` (integer): Total view count
- `shares` / `forwards` (integer): Forward/share count
- `reactions` (object): User reaction counters (emojis)
- `url` (string): Direct message web preview link (`https://t.me/...`)
- `mediaType` (string | null): Photos, videos, documents indicator

### 4. Operational Limits & Usage Notes

- **Authentication / Login**: No Telegram account or API credentials required (scrapes public web preview `t.me/s/`).
- **Modes**: `"keyword"` searches across indexed public channels; `"channel"` scrapes specific public channels by username.
- **Date Filters**: `afterDate` and `beforeDate` (or `channelAfterDate`) filter messages by date.
- **Limits**: `maxResultsPerKeyword` (default 100) or `channelMaxMessages` (default 100).

---

## KR/naver (Primary): `hgservices~naver-stock-discussion-scraper`

**Title**: Naver Stock Discussion Scraper (종목토론실)  
**Role / Scope**: Naver stock discussion boards (종목토론실) scraper for KRX/US stocks  
**Latest Build ID**: `h2uKereB2fQ51QUnT`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `PAY_PER_EVENT`
  - **`apify-actor-start`** (`Actor Start`): `$0.00005` (One-time per run) — Charged when the Actor starts running. Number of events charged depends on Actor memory (one event per GB, minimum one event).
  - **`stock-checked`** (`Stock checked`): `$0.00200` (Per event) — Charged once for each valid stock in the input, also when the stock has no posts. Unknown stocks are free. If two inputs name the same stock (for example 086520 and 에코프로), you pay once.
  - **`post`** (`Scraped discussion post`): Tiered pricing (GOLD: $0.00100, PLATINUM: $0.00100, DIAMOND: $0.00100, SILVER: $0.00150, BRONZE: $0.00200, FREE: $0.00250) (Per event) — Charged once for each discussion post in the results. Notice rows that explain an empty, unknown, or failed stock are free.

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `stocks` | `array` | **Yes** | *None* | One stock per line: a Korean stock code (005930), a foreign ticker (AAPL, TSLA), a stock name (삼성전자, 테슬라) or a Naver stock URL (finance.naver.com/item/board.naver?code=005930 or m.stock.naver.com/...). |
| `dateFrom` | `string` | No | *None* | Return only posts written on or after this date (Korea time), format YYYY-MM-DD. Leave empty to get posts until the cap. |
| `maxResults` | `integer` | No | `100` | The most posts to return for each stock, newest first. 0 = all (busy stocks have tens of thousands of posts a month). You pay per post. |

### 3. Output Fields (seen in README / Dataset Schema)

- `type` (string): Row type (`"post"` or notice)
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
- `url` (string): Direct mobile web post link

### 4. Operational Limits & Usage Notes

- **Authentication / Login**: No Naver account and no login required (accesses public mobile boards).
- **Date Filter**: `dateFrom` (format `YYYY-MM-DD`) stops collection once posts older than this date are reached.
- **Max Items**: `maxResults` controls max posts per stock (default 100, `0` for all).
- **Coverage**: Covers KOSPI, KOSDAQ, Korean ETFs, and US equities (e.g. TSLA, NVDA).

---

## KR/blind (Primary): `hypebridge~blind-post-scraper`

**Title**: Blind Post Scraper | Posts, Comments & Polls  
**Role / Scope**: TeamBlind discussions, posts, and comments extractor  
**Latest Build ID**: `PYTwD9WshFq5x0SSv`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `PAY_PER_EVENT`
  - **`apify-default-dataset-item`** (`Post`): Tiered pricing (FREE: $0.02250, BRONZE: $0.02100, SILVER: $0.01950, GOLD: $0.01800, PLATINUM: $0.01800, DIAMOND: $0.01800) (Per event) — One public post row with available text, engagement and any requested publicly exposed comments or poll choices.

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `startUrls` | `array` | **Yes** | `[{"url": "https://www.teamblind.com/?sort=pop"}]` | English TeamBlind public feeds, channels, company discussions, keyword search or /post/ URLs on teamblind.com or www.teamblind.com. Direct post URLs always receive details. Up to 100 start URLs. Private groups and localized market URLs are unsupported and skipped with a warning. |
| `maxItems` | `integer` | No | `100` | Maximum delivered posts across the run, capped at 10,000. For compatibility, 0 uses the 10,000-post safety cap. |
| `scrapePostsFromLists` | `boolean` | No | `False` | Follow post links from feed, company, channel and search pages to extract the full available post text and public poll data. The post is delivered once. Direct post URLs always receive detail extraction. |
| `scrapeComments` | `boolean` | No | `False` | Include available public comments on post detail pages, up to Max comments per post. Enable full details when starting from a feed. Login-restricted comments and replies may be unavailable. |
| `maxComments` | `integer` | No | `10` | Maximum public comments per post, capped at 100. For compatibility, 0 uses the 100-comment safety cap. The source may expose fewer comments than its displayed total. |
| `debugMode` | `boolean` | No | `False` | Save at most two diagnostic HTML snippets, each capped at 200,000 characters, when extraction cannot complete. |
| `maxPages` | `integer` | No | `20` | Stop after this many public feed, company, channel or search pages per start URL, or sooner when Max items is reached or no more public pages are available. Collected results are kept if another page is refused. |
| `maxCommentPages` | `integer` | No | `10` | Maximum additional public comment pages per post, when the source exposes them. Stop sooner at Max comments. If another page is refused, available comments are kept; signed-in comments may remain inaccessible. |
| `maxConcurrency` | `integer` | No | `3` | Limit requests processed at once. Lower this value when the site is limiting requests. |

### 3. Output Fields (seen in README / Dataset Schema)

- `articleAlias` (string): Unique Blind thread alias / slug
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
- `url` (string): Direct Blind post URL

### 4. Operational Limits & Usage Notes

- **Authentication / Login**: No login needed for public feeds and search results. Private company-internal lounges remain inaccessible.
- **Start URLs**: Accepts search URLs (`https://www.teamblind.com/search/<keyword>`), channels, or company boards.
- **Max Items**: `maxItems` caps posts across the run (default 100); `maxPages` limits pagination.
- **Domain Restriction**: Operates on English/US `teamblind.com`. Localized `/kr/` paths are skipped.

---

## Fallback telegram (1): `tri_angle~telegram-scraper`

**Title**: Telegram Scraper  
**Role / Scope**: Public Telegram channel messages and profile scraper  
**Latest Build ID**: `TBon8sA3dOgiMwckf`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `PAY_PER_EVENT`
  - **`result`** (`Result`): Tiered pricing (FREE: $0.00500, BRONZE: $0.00200, SILVER: $0.00170, GOLD: $0.00125, PLATINUM: $0.00080, DIAMOND: $0.00050) (Per event) — A result of one item in a dataset
  - **`start`** (`Start Run`): Tiered pricing (FREE: $0.00010, BRONZE: $0.00009, SILVER: $0.00008, GOLD: $0.00007, PLATINUM: $0.00006, DIAMOND: $0.00005) (One-time per run) — The cost to start a actor run

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `collectMessages` | `boolean` | No | `True` | Scrape messages of provided profiles. |
| `profiles` | `array` | **Yes** | *None* | The profiles to look for. Must be exact. You can also provide a link to the profile, e.g. https://t.me/telegram |
| `oldestMessageDate` | `string` | No | *None* | Works only when collecting messages. Only messages uploaded after or on this date will be scraped. |
| `scrapeLastNDays` | `integer` | No | *None* | Specify how old scraped posts can be (in days). Putting <code>1</code> will get you only today's posts, <code>2</code> - tomorrow's and today's, and so on. If the <code>Post newer than</code> field was set, the most recent post will be chosen. |

### 3. Output Fields (seen in README / Dataset Schema)

- `username` (string): Channel @handle
- `fullName` (string): Channel name
- `message` (object | null): Contains `id`, `text`, `date`, `views`, `links`, etc.
- `subscribers` (integer): Follower count

### 4. Operational Limits & Usage Notes

- **Authentication / Login**: No account required.
- **Limitations**: Only scrapes specific known profiles/channels passed in `profiles` array. Does not perform cross-channel keyword searches.

---

## Fallback telegram (2): `curious_coder~telegram-scraper`

**Title**: Telegram Messages Scraper  
**Role / Scope**: Telegram group/channel messages scraper (requires auth/QR)  
**Latest Build ID**: `GyYP9WfVPGHtPDHSw`

### 1. Pricing Model & Charge Events

- **Pricing Model**: `FREE`
- **Free Usage**: Standard Apify platform compute credits apply.

### 2. Exact Input Schema Fields

| Field Name | Type | Required | Default | Description / Title |
|---|---|:---:|---|---|
| `authToken` | `string` | No | *None* | Used to authorize with telegram <p> If not provied, you will be asked to scan a QR code to generate the token |
| `scrapeGroup` | `string` | **Yes** | *None* | Group or channel URL, @name or ID<p>To get the URL, go to [web.telegram.org](https://web.telegram.org) and open that group or channel, then copy the URL from the address bar. <p> Examples: <ul><li> `@group_name` </li><li> `https://t.me/group_name` </li><li> `1691104978` </li><li> `https://web.telegram.org/k/#-1949445241` </li> |
| `startPage` | `integer` | No | `1` | Page number to start scraping messages from (newest messages are on page 1) |
| `count` | `integer` | No | *None* | Maximum number of messages to scrape. Leave empty to scrape all available messages. |
| `proxy.ip` | `string` | No | *None* | IP |
| `proxy.port` | `integer` | No | *None* | Port |
| `proxy.username` | `string` | No | *None* | Username |
| `proxy.password` | `string` | No | *None* | Password |

### 3. Output Fields (seen in README / Dataset Schema)

- `id` (integer): Message ID
- `dateISO` (string): Timestamp
- `text` (string): Message content
- `fromUsername` (string): Sender username
- `views` (integer): View counter
- `replyToMsgId` (integer | null): Reply pointer

### 4. Operational Limits & Usage Notes

- **CRITICAL RESTRICTION**: Requires interactive QR code scan or `authToken` session from web.telegram.org! Cannot run headless without prior user authentication.
- **Group Scope**: Scrapes a specific target group/channel URL.

---
