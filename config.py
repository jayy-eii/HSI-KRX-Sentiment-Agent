"""Configuration module for hsi-sentiment-agent.

This module defines project paths, asset definitions across HKEX and KRX exchanges,
lookback parameters, market timezones, close times, and configurable data sources.
Environment variables (APIFY_TOKEN, EXA_API_KEY, GEMINI_API_KEY) are loaded via python-dotenv,
with validation performed on demand when a key is needed.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Ensure output and data directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Explicitly load .env from THIS project folder
load_dotenv(BASE_DIR / ".env")

# Expose API keys at module level without raising errors at import time
APIFY_TOKEN: Optional[str] = os.getenv("APIFY_TOKEN")
EXA_API_KEY: Optional[str] = os.getenv("EXA_API_KEY")
GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")


def require_api_key(key_name: str) -> str:
    """Retrieve an API key from environment or raise an informative error if missing.

    Args:
        key_name: The environment variable name (e.g. 'APIFY_TOKEN').

    Returns:
        The API key string if present and non-empty.

    Raises:
        ValueError: If the key is not set or empty.
    """
    val = os.getenv(key_name)
    if not val or not val.strip():
        raise ValueError(
            f"Missing required API key / environment variable: '{key_name}'. "
            f"Please configure '{key_name}' in your .env file."
        )
    return val.strip()


def get_apify_token(required: bool = False) -> Optional[str]:
    """Retrieve the Apify API token.

    Args:
        required: If True, raises ValueError when the token is missing.

    Returns:
        The token string, or None if not set and not required.
    """
    if required:
        return require_api_key("APIFY_TOKEN")
    val = os.getenv("APIFY_TOKEN")
    return val.strip() if val and val.strip() else None


def get_exa_api_key(required: bool = True) -> Optional[str]:
    """Retrieve the Exa API key.

    Args:
        required: If True, raises ValueError when the key is missing.

    Returns:
        The API key string, or None if not set and not required.
    """
    if required:
        return require_api_key("EXA_API_KEY")
    val = os.getenv("EXA_API_KEY")
    return val.strip() if val and val.strip() else None


def get_gemini_api_key(required: bool = True) -> Optional[str]:
    """Retrieve the Google Gemini API key.

    Args:
        required: If True, raises ValueError when the key is missing.

    Returns:
        The API key string, or None if not set and not required.
    """
    if required:
        return require_api_key("GEMINI_API_KEY")
    val = os.getenv("GEMINI_API_KEY")
    return val.strip() if val and val.strip() else None


# Lookback window in days for feature generation and sentiment aggregation
LOOKBACK_DAYS: int = 10

# Asset definitions per exchange
ASSETS: Dict[str, Dict[str, Any]] = {
    # HKEX (Exchange: HK)
    "0700.HK": {
        "exchange": "HK",
        "yfinance_ticker": "0700.HK",
        "plain_ticker": "0700",
        "name_en": "Tencent Holdings",
        "name_local": "騰訊控股",
        "lihkg_keywords": ["騰訊 0700", "騰訊 股價", "0700", "騰訊 業績", "騰訊"],
        "telegram_keywords": ["騰訊 股價", "腾讯控股 00700", "港股 騰訊", "$0700"],
        "stock_like_tickers": ["0700", "00700", "$0700", "700.hk", "0700.hk", "$tcehy"],
        "chinese_names": ["騰訊", "腾讯", "騰訊控股", "腾讯控股", "Tencent"],
        "search_keywords": [
            "$0700",
            "$0700.HK",
            "$TCEHY",
            "0700",
            "0700.HK",
            "700",
            "Tencent",
            "Tencent Holdings",
            "騰訊控股",
            "騰訊",
            "腾讯",
        ],
    },
    "9988.HK": {
        "exchange": "HK",
        "yfinance_ticker": "9988.HK",
        "plain_ticker": "9988",
        "name_en": "Alibaba Group",
        "name_local": "阿里巴巴",
        "lihkg_keywords": ["阿里 9988", "阿里 股價", "9988", "阿里 業績", "阿里巴巴 股價", "阿里巴巴", "阿里"],
        "telegram_keywords": ["阿里巴巴 股價", "阿里巴巴 09988", "港股 阿里", "$9988"],
        "stock_like_tickers": ["9988", "09988", "$9988", "9988.hk", "09988.hk", "$baba"],
        "chinese_names": ["阿里巴巴", "阿里", "Alibaba", "BABA"],
        "search_keywords": [
            "$9988",
            "$9988.HK",
            "$BABA",
            "9988",
            "9988.HK",
            "Alibaba",
            "Alibaba Group",
            "阿里巴巴",
            "阿里巴巴集團",
            "阿里",
        ],
    },
    "3690.HK": {
        "exchange": "HK",
        "yfinance_ticker": "3690.HK",
        "plain_ticker": "3690",
        "name_en": "Meituan",
        "name_local": "美團",
        "lihkg_keywords": ["美團 3690", "美團 股價", "3690", "美團 業績", "美團"],
        "telegram_keywords": ["美團 股價", "美团 03690", "港股 美團", "$3690"],
        "stock_like_tickers": ["3690", "03690", "$3690", "3690.hk", "03690.hk"],
        "chinese_names": ["美團", "美团", "Meituan"],
        "search_keywords": [
            "$3690",
            "$3690.HK",
            "3690",
            "3690.HK",
            "Meituan",
            "美團",
            "美團點評",
            "美团",
        ],
    },
    "1810.HK": {
        "exchange": "HK",
        "yfinance_ticker": "1810.HK",
        "plain_ticker": "1810",
        "name_en": "Xiaomi Corporation",
        "name_local": "小米集團",
        "lihkg_keywords": ["小米 1810", "小米 股價", "1810", "小米 業績", "小米"],
        "telegram_keywords": ["小米 股價", "小米集團 01810", "港股 小米", "$1810"],
        "stock_like_tickers": ["1810", "01810", "$1810", "1810.hk", "01810.hk", "$xiacy"],
        "chinese_names": ["小米", "Xiaomi"],
        "search_keywords": [
            "$1810",
            "$1810.HK",
            "$XIACY",
            "1810",
            "1810.HK",
            "Xiaomi",
            "Xiaomi Corporation",
            "小米集團",
            "小米",
        ],
    },
    "0005.HK": {
        "exchange": "HK",
        "yfinance_ticker": "0005.HK",
        "plain_ticker": "0005",
        "name_en": "HSBC Holdings",
        "name_local": "滙豐控股",
        "lihkg_keywords": ["滙豐 0005", "滙豐 股價", "0005", "滙豐 業績", "滙豐", "匯豐 股價"],
        "telegram_keywords": ["滙豐 股價", "汇丰控股 00005", "港股 滙豐", "$0005"],
        "stock_like_tickers": ["0005", "00005", "$0005", "0005.hk", "00005.hk", "$hsbc"],
        "chinese_names": ["滙豐", "匯豐", "汇丰", "HSBC", "大笨象"],
        "search_keywords": [
            "$0005",
            "$0005.HK",
            "$HSBC",
            "0005",
            "0005.HK",
            "5",
            "HSBC",
            "HSBC Holdings",
            "滙豐控股",
            "滙豐",
            "匯豐",
            "大笨象",
        ],
    },
    # KRX (Exchange: KR)
    "005930.KS": {
        "exchange": "KR",
        "yfinance_ticker": "005930.KS",
        "plain_ticker": "005930",
        "name_en": "Samsung Electronics",
        "name_local": "삼성전자",
        "naver_code": "005930",
        "telegram_keywords": ["삼성전자 주가", "005930"],
        "korean_names": ["삼성전자", "삼전", "Samsung Electronics", "Samsung"],
        "stock_like_tickers": ["005930", "$005930", "005930.ks"],
        "blind_query": "Samsung",
        "search_keywords": [
            "$005930",
            "$005930.KS",
            "005930",
            "005930.KS",
            "Samsung Electronics",
            "Samsung",
            "삼성전자",
            "삼전",
        ],
    },
    "000660.KS": {
        "exchange": "KR",
        "yfinance_ticker": "000660.KS",
        "plain_ticker": "000660",
        "name_en": "SK Hynix",
        "name_local": "SK하이닉스",
        "naver_code": "000660",
        "telegram_keywords": ["SK하이닉스 주가", "000660"],
        "korean_names": ["SK하이닉스", "하이닉스", "SK Hynix", "SK hynix"],
        "stock_like_tickers": ["000660", "$000660", "000660.ks"],
        "blind_query": "SK Hynix",
        "search_keywords": [
            "$000660",
            "$000660.KS",
            "000660",
            "000660.KS",
            "SK Hynix",
            "SK하이닉스",
            "하이닉스",
        ],
    },
    "035420.KS": {
        "exchange": "KR",
        "yfinance_ticker": "035420.KS",
        "plain_ticker": "035420",
        "name_en": "NAVER",
        "name_local": "네이버",
        "naver_code": "035420",
        "telegram_keywords": ["네이버 주가", "035420"],
        "korean_names": ["네이버", "NAVER", "Naver"],
        "stock_like_tickers": ["035420", "$035420", "035420.ks"],
        "blind_query": "Naver",
        "search_keywords": [
            "$035420",
            "$035420.KS",
            "035420",
            "035420.KS",
            "NAVER",
            "Naver",
            "네이버",
        ],
    },
    "035720.KS": {
        "exchange": "KR",
        "yfinance_ticker": "035720.KS",
        "plain_ticker": "035720",
        "name_en": "Kakao",
        "name_local": "카카오",
        "naver_code": "035720",
        "telegram_keywords": ["카카오 주가", "035720"],
        "korean_names": ["카카오", "Kakao"],
        "stock_like_tickers": ["035720", "$035720", "035720.ks"],
        "blind_query": "Kakao",
        "search_keywords": [
            "$035720",
            "$035720.KS",
            "035720",
            "035720.KS",
            "Kakao",
            "카카오",
        ],
    },
    "005380.KS": {
        "exchange": "KR",
        "yfinance_ticker": "005380.KS",
        "plain_ticker": "005380",
        "name_en": "Hyundai Motor",
        "name_local": "현대자동차",
        "naver_code": "005380",
        "telegram_keywords": ["현대차 주가", "005380"],
        "korean_names": ["현대차", "현대자동차", "Hyundai Motor", "Hyundai"],
        "stock_like_tickers": ["005380", "$005380", "005380.ks"],
        "blind_query": "Hyundai Motor",
        "search_keywords": [
            "$005380",
            "$005380.KS",
            "005380",
            "005380.KS",
            "Hyundai Motor",
            "Hyundai",
            "현대자동차",
            "현대차",
        ],
    },
}

# Assets grouped by exchange
ASSETS_BY_EXCHANGE: Dict[str, Dict[str, Dict[str, Any]]] = {
    "HK": {k: v for k, v in ASSETS.items() if v["exchange"] == "HK"},
    "KR": {k: v for k, v in ASSETS.items() if v["exchange"] == "KR"},
}

# Data sources per exchange (configurable, easy to swap)
SOURCES: Dict[str, List[str]] = {
    "HK": ["lihkg", "telegram"],
    "KR": ["naver", "telegram"],
}

# Market timezones
TIMEZONES: Dict[str, str] = {
    "HK": "Asia/Hong_Kong",
    "KR": "Asia/Seoul",
}

# Local market close times
MARKET_CLOSE_TIMES: Dict[str, str] = {
    "HK": "16:00",
    "KR": "15:30",
}

# Comprehensive exchange configuration dictionary
EXCHANGES: Dict[str, Dict[str, Any]] = {
    "HK": {
        "name": "HKEX",
        "timezone": TIMEZONES["HK"],
        "market_close_time": MARKET_CLOSE_TIMES["HK"],
        "sources": SOURCES["HK"],
        "assets": list(ASSETS_BY_EXCHANGE["HK"].keys()),
    },
    "KR": {
        "name": "KRX",
        "timezone": TIMEZONES["KR"],
        "market_close_time": MARKET_CLOSE_TIMES["KR"],
        "sources": SOURCES["KR"],
        "assets": list(ASSETS_BY_EXCHANGE["KR"].keys()),
    },
}
