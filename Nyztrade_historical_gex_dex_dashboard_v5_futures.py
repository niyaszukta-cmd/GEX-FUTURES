# ============================================================================
# NYZTrade UNIFIED GEX/DEX Dashboard - INDEX + STOCK OPTIONS
# Features: Weekly/Monthly Options | VANNA & CHARM | Gamma Flip Zones
#           Smart Caching | Volume Overlay | Volume Spike Detection
#           Significant GEX Classification (Addition vs Unwind)
# Supports: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY + 30 F&O Stocks
# ============================================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
from datetime import datetime, timedelta
import pytz
import requests
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import warnings
import hashlib
import json
import os
import pickle
from pathlib import Path
try:
    import pyotp
    PYOTP_AVAILABLE = True
except ImportError:
    PYOTP_AVAILABLE = False
warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIG & STYLING
# ============================================================================

st.set_page_config(
    page_title="NYZTrade Unified - GEX & VANNA Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

    header[data-testid="stHeader"] a[href*="github"] { display: none !important; }
    button[kind="header"][data-testid="baseButton-header"] svg { display: none !important; }
    a[aria-label*="GitHub"], a[aria-label*="github"], a[href*="github.com"] { display: none !important; }

    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #111827;
        --bg-card: #1a2332;
        --bg-card-hover: #232f42;
        --accent-green: #10b981;
        --accent-red: #ef4444;
        --accent-blue: #3b82f6;
        --accent-purple: #8b5cf6;
        --accent-yellow: #f59e0b;
        --accent-cyan: #06b6d4;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border-color: #2d3748;
    }

    .stApp { background: linear-gradient(135deg, var(--bg-primary) 0%, #0f172a 50%, var(--bg-primary) 100%); }

    .main-header {
        background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(139,92,246,0.1) 100%);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 24px 32px;
        margin-bottom: 24px;
        backdrop-filter: blur(10px);
    }
    .main-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .sub-title { font-family: 'JetBrains Mono', monospace; color: var(--text-secondary); font-size: 0.9rem; margin-top: 8px; }

    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
    }
    .metric-card:hover { background: var(--bg-card-hover); transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.3); }
    .metric-card.positive { border-left: 4px solid var(--accent-green); }
    .metric-card.negative { border-left: 4px solid var(--accent-red); }
    .metric-card.neutral  { border-left: 4px solid var(--accent-yellow); }

    .metric-label  { font-family: 'JetBrains Mono', monospace; color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }
    .metric-value  { font-family: 'Space Grotesk', sans-serif; font-size: 1.75rem; font-weight: 700; color: var(--text-primary); line-height: 1.2; }
    .metric-value.positive { color: var(--accent-green); }
    .metric-value.negative { color: var(--accent-red); }
    .metric-value.neutral  { color: var(--accent-yellow); }
    .metric-delta  { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; margin-top: 8px; color: var(--text-secondary); }

    .live-indicator {
        display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px;
        background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
        border-radius: 20px; animation: pulse 2s ease-in-out infinite;
    }
    .live-dot { width: 8px; height: 8px; background: var(--accent-red); border-radius: 50%; animation: blink 1.5s ease-in-out infinite; }

    .index-badge {
        display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px;
        background: rgba(139,92,246,0.2); border: 1px solid rgba(139,92,246,0.4);
        border-radius: 12px; color: #a78bfa; font-size: 0.75rem; font-weight: 600;
    }
    .stock-badge {
        display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px;
        background: rgba(6,182,212,0.2); border: 1px solid rgba(6,182,212,0.4);
        border-radius: 12px; color: #22d3ee; font-size: 0.75rem; font-weight: 600;
    }
    .spike-legend {
        padding: 10px 16px;
        background: rgba(59,130,246,0.08);
        border: 1px solid rgba(59,130,246,0.25);
        border-radius: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem;
        color: #94a3b8;
        line-height: 1.8;
    }

    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
    @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.3} }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CONFIGURATION
# ============================================================================

# ============================================================================

# ████████████████████████████████████████████████████████████████████████████
# ██                  H e d G E X   M A S T E R   C O N F I G              ██
# ██  Edit ONLY this section — everything else is automatic.                ██
# ████████████████████████████████████████████████████████████████████████████

# ── Dhan API Token ────────────────────────────────────────────────────────────
# Paste fresh token here whenever it expires (every ~30 days).
HEDGEX_DHAN_TOKEN = ("eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJ1c2VyUmVnaW9uIjoiUjEiLCJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzkwNjE1NzA5LCJhcHBfaWQiOiJhYjYxZmJmOSIsImlhdCI6MTc5MDUyOTMwOSwidG9rZW5Db25zdW1lclR5cGUiOiJBUFAiLCJ3ZWJob29rVXJsIjoiIiwiZGhhbkNsaWVudElkIjoiMTEwMDQ4MDM1NCJ9.B89tI8C_ar6rdAlHNgV03iAdE3oQIDzq5SDeNj-V9AkJpzd6ckC5AochbWXSd-tvL83e7IIeozakVLfrptbORQ")

# ── Login Credentials ─────────────────────────────────────────────────────────
# role = "admin"  → full access + cache clear
# role = "user"   → full access, NO cache clear
HEDGEX_USERS = {
    "admin":   {"password": "hedgex_admin_4444",  "role": "admin"},
    "niyas":   {"password": "nyztrade@4444",       "role": "admin"},
    "user1":   {"password": "greenhedgex",        "role": "user"},
    "user2":   {"password": "hedgex_user2",        "role": "user"},
}

# ── Video Tutorials (Veed.io embed codes) ────────────────────────────────────
# Add / remove / reorder entries freely.
# embed: paste the full <iframe> embed code from Veed.io share → Embed
HEDGEX_VIDEOS = [
    {
        "title":     "01 · Introduction",
        "desc":      "Prelude",
        # thumbnail: paste the Veed.io thumbnail/poster URL (right-click video → copy image address)
        # or leave "" to show a placeholder card instead
        "thumbnail": "",   # ← e.g. "https://cdn.veed.io/thumb/abc123.jpg"
        # topics: list of areas covered shown beside the video
        "topics": [
            "General discussion on HedGEX and Why we need this",
            
        ],
        # HOW TO ADD EMBED: use single-quote string — iframe src="..." uses double-quotes inside
        "embed": '<iframe src="https://veed.io/embed/681df571-f6aa-4bd4-8fe2-7309c04cb3ee?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="The Prelude" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',
    },
    {
        "title":     "02 · Basics of Option and Hedging",
        "desc":      "Deep dive into basics of options",
        "thumbnail": "",
        "topics": [
            "What is option? ",
            "Why option trading?",
            "How market makers trade options?",
            "Options from Option Buyers and Sellers perspective",
            "All chapters practical oriented",
            
        ],
        "embed": '<iframe src="https://veed.io/embed/f0394d7c-d4be-4ad1-8d0a-7b36e2982389?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="Basics of Options and Hedging" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },
    {
        "title":     "03 · Option moneyness",
        "desc":      "How to select strikes? ATM, ITM , OTM deep analysis",
        "thumbnail": "",
        "topics": [
            "What is ATM , when to choose ATM?",
            "What is ITM , when to choose ITM?",
            "What is OTM , when to choose OTM?",
            "IStrike selection using GEX",
            "All chapters practical oriented",
         
        ],
        "embed": '<iframe src="https://veed.io/embed/c05fa625-30c1-4d46-8115-6b924df873a9?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="Option Moneyness (Practical on ATM ITM OTM)" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },

    {
        "title":     "04 · Option Greeks (First Order)",
        "desc":      "How to understand Greeks in simple language",
        "thumbnail": "",
        "topics": [
            "Practical insights on Delta",
            "Practical insights on GAMMA",
            "Practical insights on theta",
            "How Greeks change option pricing (Black Scholes)",
            "How to check profitability probability of option with Greeks",
            "All chapters with practical focus and commonman understanding",
            
        ],
        "embed": '<iframe src="https://veed.io/embed/da16724d-fe2a-4e54-938a-c345e36f63de?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="Option Greeks (practical on GAMMA , DELTA..etc)" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },

    {
        "title":     "05 · Introduction to HedGEX platform",
        "desc":      "How to use HedGEX overview",
        "thumbnail": "",
        "topics": [
            "Basic Usage Guidelines on HedGEX option analytics platform",
            
        ],
        "embed": '<iframe src="https://veed.io/embed/347f70f6-8064-4261-b441-a8ecce5ffeb5?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="Introduction to HedGEX dashboard" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },

    {
        "title":     "06 · Advanced GEX, VANNA , CASCADE analytics",
        "desc":      "How to trade options based on GEX, VANNA,and CASCADE",
        "thumbnail": "",
        "topics": [
            "Basics of Gamma EXPOSURE- Call Gamma Wall, Put Gamma Wall",
            "GEX for Option sellers",
            "GEX for Option Buyers",
            "Understanding Dealerflow using GEX",
            "Marking Dealer-flow/option flow using GEX S/R levels (Sellers' Iron Condor)",
            "Strike selection based on GEX and Enhanced GEX (unwinding) ",
            
        ],
        "embed": '<iframe src="https://www.veed.io/embed/bfb639b1-62ed-4174-9118-d95ad7c1979b?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="Screen Recording - May 3, 2026" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },

     {
        "title":     "07 · GEX formations masterclass for Intraday and BTST options (MOST IMPORTANT CHAPTER)",
        "desc":      "How to trade Intraday and BTST options based on GEX Formations",
        "thumbnail": "",
        "topics": [
            "Basics of GEX formations for Intraday and BTST 9:20 rule and 3:20 rule respectively",
            "Bull ramps and Bear ramps",
            "Sellers' Condors",
            "Continuous bull ramp and continuous bear ramps",
            "GEX VOID or GEX brackets for S/R markings (most important)",
            "GAMMA BLAST setups (Jackpots!!)",
            
        ],
        "embed": '<iframe src="https://www.veed.io/embed/20a94300-8c67-4c08-9af2-a406de91a61e?watermark=0&color=&sharing=0&title=1" width="744" height="504" frameborder="0" title="GEX formations masterclass for Intraday and BTST options" webkitallowfullscreen mozallowfullscreen allowfullscreen></iframe>',   # ← replace with '<iframe ...></iframe>' using single quotes
    },
]




# ████████████████████████████████████████████████████████████████████████████
# ██            END OF MASTER CONFIG — do not edit below this line          ██
# ████████████████████████████████████████████████████████████████████████████

# AUTO TOKEN MANAGER
# ============================================================================

# Access token: now read from HEDGEX_DHAN_TOKEN in MASTER CONFIG above
# Falls back to the hardcoded token below if secrets not configured.
# To update token without redeploying, just edit secrets.toml:
#   DHAN_ACCESS_TOKEN = "eyJ..."
# Token sourced from HEDGEX_DHAN_TOKEN in MASTER CONFIG (top of file)
_FALLBACK_TOKEN = HEDGEX_DHAN_TOKEN

def _auto_generate_token() -> str:
    """
    Auto-generates a fresh Dhan access token using TOTP.
    Reads credentials from Streamlit secrets (st.secrets).

    Required entries in .streamlit/secrets.toml:
        DHAN_CLIENT_ID   = "1100480354"
        DHAN_PIN         = "123456"       # your 6-digit Dhan PIN
        DHAN_TOTP_SECRET = "ABCD1234..."  # TOTP secret from Dhan web

    Falls back to hardcoded token if secrets or pyotp not available.
    Token is cached in st.session_state for the session lifetime —
    only one API call per app session, not per page rerun.
    """
    # Return cached token if already generated this session
    if "dhan_access_token" in st.session_state:
        return st.session_state["dhan_access_token"]

    # Check prerequisites
    if not PYOTP_AVAILABLE:
        return _FALLBACK_TOKEN

    try:
        client_id   = st.secrets.get("DHAN_CLIENT_ID",   None)
        pin         = st.secrets.get("DHAN_PIN",         None)
        totp_secret = st.secrets.get("DHAN_TOTP_SECRET", None)
    except Exception:
        return _FALLBACK_TOKEN

    if not all([client_id, pin, totp_secret]):
        # Secrets not configured — use fallback silently
        return _FALLBACK_TOKEN

    try:
        totp_code = pyotp.TOTP(totp_secret).now()
        resp = requests.post(
            "https://auth.dhan.co/app/generateAccessToken",
            params={
                "dhanClientId": client_id,
                "pin":          pin,
                "totp":         totp_code,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data  = resp.json()
            token = data.get("accessToken", _FALLBACK_TOKEN)
            # Cache in session — won't call API again until app restarts
            st.session_state["dhan_access_token"] = token
            st.session_state["dhan_token_expiry"]  = data.get("expiryTime", "")
            st.session_state["dhan_token_source"]  = "AUTO_TOTP"
            return token
        else:
            st.session_state["dhan_access_token"] = _FALLBACK_TOKEN
            st.session_state["dhan_token_source"]  = "FALLBACK"
            return _FALLBACK_TOKEN
    except Exception:
        st.session_state["dhan_access_token"] = _FALLBACK_TOKEN
        st.session_state["dhan_token_source"]  = "FALLBACK"
        return _FALLBACK_TOKEN


@dataclass
class DhanConfig:
    client_id: str = "1100480354"
    access_token: str = field(default_factory=_auto_generate_token)

DHAN_INDEX_SECURITY_IDS = {
    "NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 442, "SENSEX": 51
}
# Symbols that trade on BSE_FNO instead of NSE_FNO
BSE_FNO_SYMBOLS = {"SENSEX"}

# ── Futures (FUTIDX) near-month security IDs ────────────────────────────────
# These are Dhan's security IDs for the near-month futures contract.
# They are STATIC per symbol — Dhan resolves near-month dynamically via expiryCode=1.
DHAN_FUTURES_SECURITY_IDS = {
    "NIFTY":      13,   # NIFTY FUTIDX — same underlying ID, instrument="FUTIDX"
    "BANKNIFTY":  25,
    "FINNIFTY":   27,
    "MIDCPNIFTY": 442,
    "SENSEX":     51,
}

def fetch_futures_ltp(symbol: str) -> float:
    """
    Fetch the near-month futures LTP for an index symbol via Dhan /v2/data/quote.
    Returns futures LTP as float, or 0.0 on any error (safe fallback to spot mode).

    Dhan quote endpoint:
      POST https://api.dhan.co/v2/data/quote
      Body: { "NSE_FNO": [ {"securityId": "<id>", "instrument": "FUTIDX"} ] }
      Response: { "data": { "NSE_FNO": { "<id>": { "lastTradedPrice": <float> } } } }
    """
    try:
        config   = DhanConfig()
        headers  = {
            "access-token":  config.access_token,
            "client-id":     config.client_id,
            "Content-Type":  "application/json",
        }
        sec_id   = DHAN_FUTURES_SECURITY_IDS.get(symbol)
        if sec_id is None:
            return 0.0

        exchange = "BSE_FNO" if symbol in BSE_FNO_SYMBOLS else "NSE_FNO"
        payload  = {
            exchange: [
                {"securityId": str(sec_id), "instrument": "FUTIDX"}
            ]
        }
        resp = requests.post(
            "https://api.dhan.co/v2/data/quote",
            headers=headers, json=payload, timeout=8
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            exch_data = data.get(exchange, {})
            # Key may be the securityId as string
            for key, val in exch_data.items():
                ltp = val.get("lastTradedPrice", val.get("ltp", val.get("LTP", 0)))
                if ltp and float(ltp) > 0:
                    return float(ltp)
        return 0.0
    except Exception:
        return 0.0
DHAN_STOCK_SECURITY_IDS = {
    "RELIANCE": 2885, "TCS": 11536, "HDFCBANK": 1333, "INFY": 1594,
    "ICICIBANK": 4963, "SBIN": 3045, "BHARTIARTL": 1195, "ITC": 1660,
    "KOTAKBANK": 1922, "LT": 2980, "AXISBANK": 5900, "HINDUNILVR": 1394,
    "WIPRO": 3787, "MARUTI": 10999, "BAJFINANCE": 317, "HCLTECH": 7229,
    "ASIANPAINT": 157, "TITAN": 3506, "ULTRACEMCO": 11532, "SUNPHARMA": 3351,
    "TATAMOTORS": 3456, "TATASTEEL": 3499, "TECHM": 13538, "POWERGRID": 2752,
    "NTPC": 11630, "ONGC": 2475, "M&M": 2031, "BAJAJFINSV": 16675,
    "ADANIPORTS": 3718, "COALINDIA": 20374,
}

INDEX_CONFIG = {
    "NIFTY":      {"contract_size": 25,  "strike_interval": 50,   "type": "INDEX"},
    "BANKNIFTY":  {"contract_size": 15,  "strike_interval": 100,  "type": "INDEX"},
    "FINNIFTY":   {"contract_size": 40,  "strike_interval": 50,   "type": "INDEX"},
    "MIDCPNIFTY": {"contract_size": 75,  "strike_interval": 25,   "type": "INDEX"},
    "SENSEX":     {"contract_size": 10,  "strike_interval": 200,  "type": "INDEX", "exchange": "BSE_FNO"},
}
STOCK_CONFIG = {
    "RELIANCE":   {"lot_size": 250,  "strike_interval": 10,  "type": "STOCK"},
    "TCS":        {"lot_size": 150,  "strike_interval": 25,  "type": "STOCK"},
    "HDFCBANK":   {"lot_size": 550,  "strike_interval": 10,  "type": "STOCK"},
    "INFY":       {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "ICICIBANK":  {"lot_size": 550,  "strike_interval": 10,  "type": "STOCK"},
    "SBIN":       {"lot_size": 1500, "strike_interval": 5,   "type": "STOCK"},
    "BHARTIARTL": {"lot_size": 410,  "strike_interval": 10,  "type": "STOCK"},
    "ITC":        {"lot_size": 1600, "strike_interval": 5,   "type": "STOCK"},
    "KOTAKBANK":  {"lot_size": 400,  "strike_interval": 25,  "type": "STOCK"},
    "LT":         {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "AXISBANK":   {"lot_size": 600,  "strike_interval": 10,  "type": "STOCK"},
    "HINDUNILVR": {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "WIPRO":      {"lot_size": 1200, "strike_interval": 5,   "type": "STOCK"},
    "MARUTI":     {"lot_size": 75,   "strike_interval": 50,  "type": "STOCK"},
    "BAJFINANCE": {"lot_size": 125,  "strike_interval": 50,  "type": "STOCK"},
    "HCLTECH":    {"lot_size": 350,  "strike_interval": 25,  "type": "STOCK"},
    "ASIANPAINT": {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "TITAN":      {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "ULTRACEMCO": {"lot_size": 100,  "strike_interval": 50,  "type": "STOCK"},
    "SUNPHARMA":  {"lot_size": 400,  "strike_interval": 25,  "type": "STOCK"},
    "TATAMOTORS": {"lot_size": 1250, "strike_interval": 5,   "type": "STOCK"},
    "TATASTEEL":  {"lot_size": 900,  "strike_interval": 5,   "type": "STOCK"},
    "TECHM":      {"lot_size": 400,  "strike_interval": 25,  "type": "STOCK"},
    "POWERGRID":  {"lot_size": 1800, "strike_interval": 5,   "type": "STOCK"},
    "NTPC":       {"lot_size": 2250, "strike_interval": 5,   "type": "STOCK"},
    "ONGC":       {"lot_size": 2475, "strike_interval": 5,   "type": "STOCK"},
    "M&M":        {"lot_size": 300,  "strike_interval": 25,  "type": "STOCK"},
    "BAJAJFINSV": {"lot_size": 500,  "strike_interval": 10,  "type": "STOCK"},
    "ADANIPORTS": {"lot_size": 250,  "strike_interval": 25,  "type": "STOCK"},
    "COALINDIA":  {"lot_size": 2040, "strike_interval": 5,   "type": "STOCK"},
}
SYMBOL_CONFIG = {**INDEX_CONFIG, **STOCK_CONFIG}
STOCK_CATEGORIES = {
    "Banking & Finance": ["HDFCBANK","ICICIBANK","SBIN","KOTAKBANK","AXISBANK","BAJFINANCE","BAJAJFINSV"],
    "IT & Technology":   ["TCS","INFY","WIPRO","HCLTECH","TECHM"],
    "Energy & Power":    ["RELIANCE","ONGC","POWERGRID","NTPC","COALINDIA"],
    "Auto & Industrial": ["MARUTI","TATAMOTORS","M&M","LT"],
    "FMCG & Consumer":   ["HINDUNILVR","ITC","ASIANPAINT","TITAN"],
    "Others":            ["SUNPHARMA","TATASTEEL","BHARTIARTL","ADANIPORTS","ULTRACEMCO"],
}

IST = pytz.timezone('Asia/Kolkata')
MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE   = 9,  15
MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE = 15, 30

# ============================================================================
# CACHE MANAGER
# ============================================================================

class CacheManager:
    def __init__(self):
        self.cache_dir = "/tmp/nyztrade_unified_cache"
        os.makedirs(self.cache_dir, exist_ok=True)

    def _generate_cache_key(self, symbol, date, strikes, interval, expiry_code, expiry_flag, instrument_type):
        key_data = f"{symbol}_{date}_{sorted(strikes)}_{interval}_{expiry_code}_{expiry_flag}_{instrument_type}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key): return os.path.join(self.cache_dir, f"{cache_key}.pkl")
    def _get_meta_path(self, cache_key): return os.path.join(self.cache_dir, f"{cache_key}_meta.json")

    def is_current_trading_day(self, target_date):
        return datetime.strptime(target_date, '%Y-%m-%d').date() == datetime.now(IST).date()

    def is_market_hours(self):
        now = datetime.now(IST)
        open_t  = now.replace(hour=MARKET_OPEN_HOUR,  minute=MARKET_OPEN_MINUTE,  second=0, microsecond=0)
        close_t = now.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)
        return open_t <= now <= close_t

    def get_cached_data(self, symbol, date, strikes, interval, expiry_code, expiry_flag, instrument_type):
        cache_key  = self._generate_cache_key(symbol, date, strikes, interval, expiry_code, expiry_flag, instrument_type)
        cache_path = self._get_cache_path(cache_key)
        meta_path  = self._get_meta_path(cache_key)
        if not os.path.exists(cache_path) or not os.path.exists(meta_path):
            return None, None, None
        try:
            df = pd.read_pickle(cache_path)
            with open(meta_path) as f:
                meta = json.load(f)
            last_ts = df['timestamp'].max() if len(df) > 0 and 'timestamp' in df.columns else None
            if isinstance(last_ts, str):
                last_ts = pd.to_datetime(last_ts)
            return df, meta, last_ts
        except Exception as e:
            st.warning(f"Cache read error: {e}")
            return None, None, None

    def save_to_cache(self, df, meta, symbol, date, strikes, interval, expiry_code, expiry_flag, instrument_type):
        cache_key  = self._generate_cache_key(symbol, date, strikes, interval, expiry_code, expiry_flag, instrument_type)
        try:
            df.to_pickle(self._get_cache_path(cache_key))
            with open(self._get_meta_path(cache_key), 'w') as f:
                json.dump(meta, f)
        except Exception as e:
            st.warning(f"Cache write error: {e}")

    def merge_incremental_data(self, cached_df, new_df):
        if cached_df is None or len(cached_df) == 0: return new_df
        if new_df is None or len(new_df) == 0: return cached_df
        combined = pd.concat([cached_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['timestamp','strike'], keep='last')
        return combined.sort_values(['timestamp','strike']).reset_index(drop=True)

    def clear_cache(self, symbol=None, date=None):
        try:
            for f in os.listdir(self.cache_dir):
                fp = os.path.join(self.cache_dir, f)
                if symbol is None and date is None:
                    os.remove(fp)
                elif f.startswith(f"{symbol}_{date}"):
                    os.remove(fp)
        except Exception as e:
            st.warning(f"Cache clear error: {e}")

    def get_cache_stats(self):
        try:
            files = [f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')]
            size  = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in files)
            return {'num_entries': len(files), 'total_size_mb': size / (1024*1024)}
        except:
            return {'num_entries': 0, 'total_size_mb': 0}

cache_manager = CacheManager()

# ============================================================================
# BLACK-SCHOLES CALCULATOR
# ============================================================================

class BlackScholesCalculator:
    @staticmethod
    def calculate_d1(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0: return 0
        return (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))

    @staticmethod
    def calculate_d2(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0: return 0
        return BlackScholesCalculator.calculate_d1(S, K, T, r, sigma) - sigma * np.sqrt(T)

    @staticmethod
    def calculate_gamma(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            return norm.pdf(d1) / (S * sigma * np.sqrt(T))
        except: return 0

    @staticmethod
    def calculate_call_delta(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
        try: return norm.cdf(BlackScholesCalculator.calculate_d1(S, K, T, r, sigma))
        except: return 0

    @staticmethod
    def calculate_put_delta(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
        try: return norm.cdf(BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)) - 1
        except: return 0

    @staticmethod
    def calculate_vanna(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            d2 = BlackScholesCalculator.calculate_d2(S, K, T, r, sigma)
            return -norm.pdf(d1) * d2 / sigma
        except: return 0

    @staticmethod
    def calculate_charm(S, K, T, r, sigma, option_type='call'):
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0: return 0
        try:
            d1 = BlackScholesCalculator.calculate_d1(S, K, T, r, sigma)
            d2 = BlackScholesCalculator.calculate_d2(S, K, T, r, sigma)
            return -norm.pdf(d1) * (2*r*T - d2*sigma*np.sqrt(T)) / (2*T*sigma*np.sqrt(T))
        except: return 0

# ============================================================================
# GAMMA FLIP ZONE CALCULATOR
# ============================================================================

def identify_gamma_flip_zones(df: pd.DataFrame, spot_price: float) -> List[Dict]:
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    flip_zones = []
    for i in range(len(df_sorted) - 1):
        cur_gex  = df_sorted.iloc[i]['net_gex']
        nxt_gex  = df_sorted.iloc[i+1]['net_gex']
        cur_str  = df_sorted.iloc[i]['strike']
        nxt_str  = df_sorted.iloc[i+1]['strike']
        if (cur_gex > 0 and nxt_gex < 0) or (cur_gex < 0 and nxt_gex > 0):
            flip_str = cur_str + (nxt_str - cur_str) * (abs(cur_gex) / (abs(cur_gex) + abs(nxt_gex)))
            if spot_price < flip_str:
                direction, arrow, color = ("upward","↑","#ef4444") if cur_gex > 0 else ("downward","↓","#10b981")
            else:
                direction, arrow, color = ("downward","↓","#10b981") if cur_gex < 0 else ("upward","↑","#ef4444")
            flip_zones.append({
                'strike': flip_str, 'lower_strike': cur_str, 'upper_strike': nxt_str,
                'lower_gex': cur_gex, 'upper_gex': nxt_gex,
                'direction': direction, 'arrow': arrow, 'color': color,
                'flip_type': 'Positive→Negative' if cur_gex > 0 else 'Negative→Positive',
            })
    return flip_zones

# ============================================================================
# VOLUME OVERLAY HELPERS
# ============================================================================

def _add_volume_overlay_horizontal(fig, df_sorted: pd.DataFrame):
    if 'call_volume' not in df_sorted.columns or 'put_volume' not in df_sorted.columns:
        return fig
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['call_volume'].fillna(0),
        orientation='h', name='Call Volume',
        marker=dict(color='rgba(16,185,129,0.22)', line=dict(width=0)),
        xaxis='x2',
        hovertemplate='Strike: %{y:,.0f}<br>Call Vol: %{x:,.0f}<extra></extra>',
        showlegend=True, legendgroup='volume',
    ))
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['put_volume'].fillna(0),
        orientation='h', name='Put Volume',
        marker=dict(color='rgba(239,68,68,0.22)', line=dict(width=0)),
        xaxis='x3',
        hovertemplate='Strike: %{y:,.0f}<br>Put Vol: %{x:,.0f}<extra></extra>',
        showlegend=True, legendgroup='volume',
    ))
    return fig

def _configure_volume_xaxis2(fig, df_sorted: pd.DataFrame):
    PADDING = 4.5
    max_call = max(df_sorted['call_volume'].fillna(0).max() if 'call_volume' in df_sorted.columns else 1, 1)
    max_put  = max(df_sorted['put_volume'].fillna(0).max()  if 'put_volume'  in df_sorted.columns else 1, 1)
    fig.update_layout(
        xaxis2=dict(overlaying='x', side='top', title='Call Vol', range=[0, max_call*PADDING],
                    showgrid=False, showline=False, zeroline=False,
                    tickfont=dict(color='rgba(16,185,129,0.65)',size=9),
                    title_font=dict(color='rgba(16,185,129,0.65)',size=10),
                    color='rgba(16,185,129,0.65)'),
        xaxis3=dict(overlaying='x', side='top', title='Put Vol', range=[0, max_put*PADDING],
                    showgrid=False, showline=False, zeroline=False,
                    tickfont=dict(color='rgba(239,68,68,0.65)',size=9),
                    title_font=dict(color='rgba(239,68,68,0.65)',size=10),
                    color='rgba(239,68,68,0.65)'),
    )
    return fig

# ============================================================================
# VOLUME SPIKE DETECTION
# ============================================================================

def detect_volume_spikes(timeline_df: pd.DataFrame,
                          z_threshold: float = 2.0,
                          rolling_window: int = 5) -> pd.DataFrame:
    """
    Detects volume spikes and GEX shift events on the intraday timeline.
    Uses a hybrid z-score: rolling(15 bars) with global session baseline fallback.

    Added columns:
      vol_spike, call_vol_spike, put_vol_spike  – bool flags
      vol_z_score, call_vol_z, put_vol_z        – standardised z-scores
      gex_change, gex_z_score, gex_shift_spike  – GEX rate-of-change analysis
      spike_type       – CALL_DOMINANT | PUT_DOMINANT | MIXED | ''
      spike_strength   – EXTREME | STRONG | MODERATE | ''
      gex_confirmation – CONFIRMED_BULLISH | CONFIRMED_BEARISH | DIVERGENCE | UNCONFIRMED
      event_label      – short icon + strength label for chart annotation
    """
    df = timeline_df.copy().sort_values('timestamp').reset_index(drop=True)

    def _z_score(series: pd.Series, window: int) -> pd.Series:
        # Trimmed baseline: exclude top 10% so spike rows don't inflate
        # the mean/std and dilute their own z-score
        q90      = series.quantile(0.90)
        baseline = series[series <= q90]
        g_mean   = baseline.mean() if len(baseline) > 0 else series.mean()
        g_std    = baseline.std()  if len(baseline) > 1 else series.std()
        g_std    = g_std if g_std > 0 else 1.0
        r_mean   = series.rolling(window, min_periods=max(3, window // 2)).mean()
        r_std    = series.rolling(window, min_periods=max(3, window // 2)).std()
        # Fill early NaNs and zero-std periods with trimmed global baseline
        r_mean   = r_mean.fillna(g_mean)
        r_std    = r_std.fillna(g_std).replace(0, g_std)
        return (series - r_mean) / r_std

    LONG_WINDOW = max(rolling_window * 3, 15)

    df['vol_z_score'] = _z_score(df['total_volume'], LONG_WINDOW)
    df['call_vol_z']  = _z_score(df['call_volume'],  LONG_WINDOW)
    df['put_vol_z']   = _z_score(df['put_volume'],   LONG_WINDOW)

    df['vol_spike']      = df['vol_z_score']  > z_threshold
    df['call_vol_spike'] = df['call_vol_z']   > z_threshold
    df['put_vol_spike']  = df['put_vol_z']    > z_threshold

    df['gex_change']      = df['net_gex'].diff().fillna(0)
    # Use the same trimmed z-score for GEX changes so that sessions
    # with uniformly tiny GEX moves don't suppress the spike flag
    df['gex_z_score']     = _z_score(df['gex_change'].abs(), LONG_WINDOW)
    df['gex_shift_spike'] = df['gex_z_score'] > z_threshold

    spike_types, spike_strengths, gex_confirmations, event_labels = [], [], [], []

    for _, row in df.iterrows():
        z        = row['vol_z_score']
        czz      = row['call_vol_z']
        pzz      = row['put_vol_z']
        is_spike = bool(row['vol_spike'])

        strength = '' if not is_spike else ('EXTREME' if z > 4.0 else ('STRONG' if z > 3.0 else 'MODERATE'))
        # Use actual call/put volume ratio for dominance — more reliable
        # than comparing z-scores which share a common distorted baseline
        if not is_spike:
            stype = ''
        else:
            cv_raw = row.get('call_volume', 0)
            pv_raw = row.get('put_volume',  0)
            ratio  = cv_raw / (pv_raw + 1)   # +1 avoids division by zero
            if   ratio > 1.5:  stype = 'CALL_DOMINANT'
            elif ratio < 0.67: stype = 'PUT_DOMINANT'
            else:              stype = 'MIXED'

        gex_up      = row['gex_change'] > 0
        gex_down    = row['gex_change'] < 0
        gex_sig     = bool(row['gex_shift_spike'])
        gex_moving  = row['gex_change'] != 0

        if not is_spike:
            gex_conf = 'UNCONFIRMED'
        # Confirmed: volume direction AND GEX direction agree + GEX move is significant
        elif stype == 'CALL_DOMINANT' and gex_up and gex_sig:
            gex_conf = 'CONFIRMED_BULLISH'
        elif stype == 'PUT_DOMINANT' and gex_down and gex_sig:
            gex_conf = 'CONFIRMED_BEARISH'
        # Divergence: volume direction CONFLICTS with GEX direction.
        # Does NOT require gex_sig — direction conflict alone is enough.
        # Also catches MIXED spikes where GEX is repositioning hard.
        elif stype == 'CALL_DOMINANT' and gex_down and gex_moving:
            gex_conf = 'DIVERGENCE'
        elif stype == 'PUT_DOMINANT' and gex_up and gex_moving:
            gex_conf = 'DIVERGENCE'
        elif stype == 'MIXED' and abs(row['gex_z_score']) > z_threshold * 0.75:
            # Both sides spiking + any meaningful GEX repositioning = split market, divergent flow.
            # Use a lower GEX threshold for MIXED (75% of main threshold) because the volume
            # signal itself is already ambiguous — any dealer move is meaningful here.
            gex_conf = 'DIVERGENCE'
        else:
            gex_conf = 'UNCONFIRMED'

        label = '' if not is_spike else (
            {'CONFIRMED_BULLISH':'🚀','CONFIRMED_BEARISH':'💥','DIVERGENCE':'⚠️','UNCONFIRMED':'📊'}.get(gex_conf,'📊')
            + f" {strength[:3]}"
        )

        spike_types.append(stype)
        spike_strengths.append(strength)
        gex_confirmations.append(gex_conf)
        event_labels.append(label)

    df['spike_type']       = spike_types
    df['spike_strength']   = spike_strengths
    df['gex_confirmation'] = gex_confirmations
    df['event_label']      = event_labels

    return df


def _action_hint(row) -> str:
    conf       = row['gex_confirmation']
    stype      = row['spike_type']
    gex_change = row.get('gex_change', 0)
    if conf == 'CONFIRMED_BULLISH':
        return '🟢 Watch for squeeze up'
    if conf == 'CONFIRMED_BEARISH':
        return '🔴 Watch for squeeze down'
    if conf == 'DIVERGENCE':
        # Be explicit about which side is conflicting
        if stype == 'CALL_DOMINANT':
            return '⚠️ Calls bought but GEX falling — dealers fading buyers, watch for failed breakout'
        if stype == 'PUT_DOMINANT':
            return '⚠️ Puts bought but GEX rising — bear trap risk, watch for squeeze up'
        if stype == 'MIXED':
            dir_str = 'rising' if gex_change > 0 else 'falling'
            return f'⚠️ Mixed vol spike + GEX {dir_str} hard — split market, resolution pending'
        return '⚠️ Conflicting signals — wait for clarity'
    if stype == 'CALL_DOMINANT':    return '🟡 Call accumulation (unconfirmed by GEX)'
    if stype == 'PUT_DOMINANT':     return '🟡 Put accumulation (unconfirmed by GEX)'
    return '⬜ Monitor'


def build_spike_summary(df_spikes: pd.DataFrame, unit_label: str = "B") -> pd.DataFrame:
    spikes = df_spikes[df_spikes['vol_spike']].copy()
    if spikes.empty:
        return pd.DataFrame()
    rows = []
    for _, r in spikes.iterrows():
        rows.append({
            'Time'               : r['timestamp'].strftime('%H:%M'),
            'Spike Type'         : r['spike_type'],
            'Strength'           : r['spike_strength'],
            'GEX Signal'         : r['gex_confirmation'],
            'Vol Z-Score'        : f"{r['vol_z_score']:.1f}σ",
            'Call Vol'           : f"{r.get('call_volume',0):,.0f}",
            'Put Vol'            : f"{r.get('put_volume',0):,.0f}",
            'Total Vol'          : f"{r.get('total_volume',0):,.0f}",
            f'GEX Δ ({unit_label})': f"{r['gex_change']:+.4f}",
            'Spot'               : f"₹{r.get('spot_price',0):,.2f}",
            'Action'             : _action_hint(r),
        })
    return pd.DataFrame(rows)

# ============================================================================
# INTRADAY TIMELINE WITH VOLUME SPIKE DETECTION  (replaces old version)
# ============================================================================

def create_vanna_spike_panel(
    df: pd.DataFrame,
    unit_label: str = "B",
    z_threshold: float = 2.0,
) -> Tuple[go.Figure, pd.DataFrame]:
    """
    Compact 2-row spike panel for the VANNA overlay tab.
      Row 1 — Volume Z-Score bars + Net VANNA flow line (secondary y)
      Row 2 — Spike event markers coloured by GEX confirmation type
    """
    agg_cols = {k: v for k, v in {
        'net_gex'    : 'sum', 'net_vanna'   : 'sum',
        'spot_price' : 'first',
        'call_volume': 'sum', 'put_volume'  : 'sum', 'total_volume': 'sum',
    }.items() if k in df.columns}

    timeline_df = (df.groupby('timestamp').agg(agg_cols)
                     .reset_index().sort_values('timestamp'))
    df_spikes   = detect_volume_spikes(timeline_df, z_threshold=z_threshold)
    ts          = df_spikes['timestamp']

    spike_rows = df_spikes[df_spikes['vol_spike']]
    n_spikes   = len(spike_rows)
    n_bull = (spike_rows['gex_confirmation'] == 'CONFIRMED_BULLISH').sum()
    n_bear = (spike_rows['gex_confirmation'] == 'CONFIRMED_BEARISH').sum()
    n_div  = (spike_rows['gex_confirmation'] == 'DIVERGENCE').sum()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            'Volume Z-Score  ·  Net VANNA flow (secondary axis)',
            'Spike Events  (shape & colour = GEX confirmation type)',
        ),
        vertical_spacing=0.08,
        row_heights=[0.52, 0.48],
        specs=[[{"secondary_y": True}],
               [{"secondary_y": False}]],
    )

    # ── Row 1: Z-score bars ───────────────────────────────────────────────
    z_colors = [
        '#dc2626' if z > 4.0 else
        '#ef4444' if z > 3.0 else
        '#f59e0b' if z > z_threshold else
        '#334155'
        for z in df_spikes['vol_z_score']
    ]
    fig.add_trace(go.Bar(
        x=ts, y=df_spikes['vol_z_score'].clip(lower=0),
        marker_color=z_colors, name='Volume Z-Score',
        hovertemplate='%{x|%H:%M}<br>Z-Score: %{y:.2f}σ<extra></extra>',
    ), row=1, col=1, secondary_y=False)

    for level, color, label in [
        (z_threshold, 'rgba(245,158,11,0.75)', f'Threshold ({z_threshold:.1f}σ)'),
        (3.0,         'rgba(239,68,68,0.50)',  'Strong (3σ)'),
        (4.0,         'rgba(220,38,38,0.70)',  'Extreme (4σ)'),
    ]:
        fig.add_hline(y=level, line_dash='dash', line_color=color, line_width=1.5,
                      annotation_text=label, annotation_position='top right',
                      annotation=dict(font=dict(color=color, size=9)), row=1, col=1)

    # Net VANNA on secondary y — spike + VANNA surge = institutional move
    if 'net_vanna' in df_spikes.columns:
        mv_colors = ['rgba(16,185,129,0.8)' if v > 0 else 'rgba(239,68,68,0.8)'
                     for v in df_spikes['net_vanna']]
        fig.add_trace(go.Scatter(
            x=ts, y=df_spikes['net_vanna'],
            mode='lines+markers',
            line=dict(color='rgba(6,182,212,0.7)', width=1.5, dash='dot'),
            marker=dict(size=4, color=mv_colors),
            fill='tozeroy', fillcolor='rgba(6,182,212,0.05)',
            name='Net VANNA flow',
            hovertemplate='%{x|%H:%M}<br>Net VANNA: %{y:.4f}<extra></extra>',
        ), row=1, col=1, secondary_y=True)

    # Coloured spike vlines into row 1
    for _, sr in spike_rows.iterrows():
        vc = {'CONFIRMED_BULLISH':'rgba(16,185,129,0.25)',
              'CONFIRMED_BEARISH':'rgba(239,68,68,0.25)',
              'DIVERGENCE'       :'rgba(245,158,11,0.20)',
              'UNCONFIRMED'      :'rgba(139,92,246,0.15)'}.get(sr['gex_confirmation'],'rgba(255,255,255,0.1)')
        fig.add_vline(x=sr['timestamp'].timestamp()*1000,
                      line_dash='dot', line_color=vc, line_width=1.5, row=1, col=1)

    # ── Row 2: Spike event markers ────────────────────────────────────────
    CONF_STYLE = {
        'CONFIRMED_BULLISH': ('#10b981', 'triangle-up',   18, '🚀 Confirmed Bullish'),
        'CONFIRMED_BEARISH': ('#ef4444', 'triangle-down', 18, '💥 Confirmed Bearish'),
        'DIVERGENCE':        ('#f59e0b', 'diamond',       16, '⚠️ Divergence'),
        'UNCONFIRMED':       ('#8b5cf6', 'circle',        12, '📊 Unconfirmed'),
    }
    for conf_key, (color, symbol, size, legend_name) in CONF_STYLE.items():
        mask = df_spikes['vol_spike'] & (df_spikes['gex_confirmation'] == conf_key)
        sub  = df_spikes[mask]
        if sub.empty: continue
        fig.add_trace(go.Scatter(
            x=sub['timestamp'], y=sub['vol_z_score'].clip(upper=6),
            mode='markers+text',
            marker=dict(symbol=symbol, size=size, color=color,
                        line=dict(color='white', width=1.5)),
            text=sub['event_label'], textposition='top center',
            textfont=dict(color='white', size=9),
            name=legend_name,
            customdata=np.stack([
                sub['spike_type'].values,
                sub['spike_strength'].values,
                sub.get('call_volume', pd.Series([0]*len(sub))).values,
                sub.get('put_volume',  pd.Series([0]*len(sub))).values,
                sub['gex_change'].values,
            ], axis=-1),
            hovertemplate=(
                '%{x|%H:%M}<br>Type: %{customdata[0]}<br>'
                'Strength: %{customdata[1]}<br>'
                'Call Vol: %{customdata[2]:,.0f}<br>'
                'Put Vol: %{customdata[3]:,.0f}<br>'
                f'GEX Δ: %{{customdata[4]:+.4f}}{unit_label}<extra></extra>'
            ),
        ), row=2, col=1)

    fig.add_hline(y=z_threshold, line_dash='dash',
                  line_color='rgba(245,158,11,0.4)', line_width=1, row=2, col=1)

    # ── Layout ────────────────────────────────────────────────────────────
    if n_spikes:
        summary = f"🚀 {n_bull} Bull · 💥 {n_bear} Bear · ⚠️ {n_div} Divergence"
    else:
        summary = "No spikes detected at current threshold"

    fig.update_layout(
        title=dict(
            text=(
                f'<b>⚡ Volume Spike × VANNA Coincidence</b>  '
                f'<span style="font-size:12px;color:#94a3b8;">({n_spikes} spikes — {summary})</span><br>'
                f'<sub>'
                f'🚀 Call spike + GEX ↑ = Bullish confirmed  |  '
                f'💥 Put spike + GEX ↓ = Bearish confirmed  |  '
                f'⚠️ Conflict = Divergence  |  '
                f'Cyan dashed = Net VANNA (spike + VANNA surge = institutional conviction)'
                f'</sub>'
            ),
            font=dict(size=13, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=430,
        barmode='overlay',
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.7)',
            bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=60, r=60, t=110, b=40),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    fig.update_yaxes(title_text='Z-Score (σ)',   row=1, col=1, secondary_y=False,
                     gridcolor='rgba(128,128,128,0.15)', range=[0, None])
    fig.update_yaxes(title_text='Net VANNA',     row=1, col=1, secondary_y=True,
                     showgrid=False, zeroline=True,
                     zerolinecolor='rgba(6,182,212,0.3)', zerolinewidth=1)
    fig.update_yaxes(title_text='Spike Z-Score', row=2, col=1,
                     gridcolor='rgba(128,128,128,0.15)', range=[0, None])
    fig.update_xaxes(title_text='Time (IST)',    row=2, col=1)

    return fig, df_spikes


def create_intraday_timeline_with_spikes(df: pd.DataFrame,
                                          unit_label: str = "B",
                                          z_threshold: float = 2.0) -> Tuple[go.Figure, pd.DataFrame]:
    """
    5-row intraday chart:
      Row 1 – Net GEX bars  +  |GEX Δ| rate line (secondary y)
      Row 2 – Spot price area
      Row 3 – Call / Put volume stacked bars  +  total volume line
      Row 4 – Volume Z-Score with severity bands
      Row 5 – Spike event markers, colour-coded by GEX confirmation
    Returns (fig, df_spikes)
    """
    agg_cols = {k: v for k, v in {
        'net_gex': 'sum', 'net_dex': 'sum', 'spot_price': 'first',
        'call_volume': 'sum', 'put_volume': 'sum', 'total_volume': 'sum',
    }.items() if k in df.columns}

    timeline_df = (df.groupby('timestamp').agg(agg_cols)
                     .reset_index().sort_values('timestamp'))

    df_spikes = detect_volume_spikes(timeline_df, z_threshold=z_threshold)

    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            f'Net GEX ({unit_label})  +  GEX Δ Rate',
            'Spot Price',
            'Call vs Put Volume',
            'Volume Z-Score  (spike sensitivity threshold shown as dashed line)',
            'Spike Events  (shape & colour = GEX confirmation type)',
        ),
        vertical_spacing=0.04,
        row_heights=[0.26, 0.15, 0.22, 0.18, 0.19],
        specs=[[{"secondary_y": True}],[{"secondary_y": False}],
               [{"secondary_y": False}],[{"secondary_y": False}],
               [{"secondary_y": False}]],
    )

    ts = df_spikes['timestamp']

    # ── Row 1: GEX bars + |GEX Δ| secondary line ────────────────────────────
    gex_colors = ['#10b981' if v > 0 else '#ef4444' for v in df_spikes['net_gex']]
    fig.add_trace(go.Bar(
        x=ts, y=df_spikes['net_gex'], marker_color=gex_colors,
        name='Net GEX', showlegend=True,
        hovertemplate=f'%{{x|%H:%M}}<br>GEX: %{{y:.4f}}{unit_label}<extra></extra>',
    ), row=1, col=1, secondary_y=False)

    fig.add_trace(go.Scatter(
        x=ts, y=df_spikes['gex_change'].abs(),
        mode='lines', line=dict(color='rgba(245,158,11,0.8)', width=1.5, dash='dot'),
        fill='tozeroy', fillcolor='rgba(245,158,11,0.07)',
        name='|GEX Δ| rate', showlegend=True,
        hovertemplate=f'%{{x|%H:%M}}<br>|GEX Δ|: %{{y:.4f}}{unit_label}<extra></extra>',
    ), row=1, col=1, secondary_y=True)

    # ── Row 2: Spot price ────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=ts, y=df_spikes['spot_price'],
        mode='lines', line=dict(color='#3b82f6', width=2),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.07)',
        name='Spot Price', showlegend=True,
        hovertemplate='%{x|%H:%M}<br>₹%{y:,.2f}<extra></extra>',
    ), row=2, col=1)

    # subtle vertical lines at spike timestamps crossing into spot row
    for _, sr in df_spikes[df_spikes['vol_spike']].iterrows():
        fig.add_vline(x=sr['timestamp'].timestamp()*1000,
                      line_dash='dot', line_color='rgba(255,255,255,0.05)',
                      line_width=1, row=2, col=1)

    # ── Row 3: Call / Put volume stacked + total line ────────────────────────
    fig.add_trace(go.Bar(
        x=ts, y=df_spikes['call_volume'],
        name='Call Volume', marker=dict(color='rgba(16,185,129,0.70)', line=dict(width=0)),
        hovertemplate='%{x|%H:%M}<br>Call Vol: %{y:,.0f}<extra></extra>', showlegend=True,
    ), row=3, col=1)
    fig.add_trace(go.Bar(
        x=ts, y=df_spikes['put_volume'],
        name='Put Volume', marker=dict(color='rgba(239,68,68,0.70)', line=dict(width=0)),
        hovertemplate='%{x|%H:%M}<br>Put Vol: %{y:,.0f}<extra></extra>', showlegend=True,
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=ts, y=df_spikes['total_volume'],
        mode='lines', line=dict(color='rgba(255,255,255,0.45)', width=1.5),
        name='Total Volume', showlegend=True,
        hovertemplate='%{x|%H:%M}<br>Total: %{y:,.0f}<extra></extra>',
    ), row=3, col=1)

    # ── Row 4: Z-score bars ──────────────────────────────────────────────────
    z_colors = ['#dc2626' if z > 4.0 else ('#ef4444' if z > 3.0 else ('#f59e0b' if z > 2.0 else '#64748b'))
                for z in df_spikes['vol_z_score']]
    fig.add_trace(go.Bar(
        x=ts, y=df_spikes['vol_z_score'].clip(lower=0),
        marker_color=z_colors,
        name='Volume Z-Score', showlegend=True,
        hovertemplate='%{x|%H:%M}<br>Z-Score: %{y:.2f}σ<extra></extra>',
    ), row=4, col=1)

    for level, color, label in [
        (z_threshold, 'rgba(245,158,11,0.75)', f'Threshold ({z_threshold}σ)'),
        (3.0,         'rgba(239,68,68,0.50)',  'Strong (3σ)'),
        (4.0,         'rgba(220,38,38,0.70)',  'Extreme (4σ)'),
    ]:
        fig.add_hline(y=level, line_dash='dash', line_color=color, line_width=1.5,
                      annotation_text=label, annotation_position='top right',
                      annotation=dict(font=dict(color=color, size=9)), row=4, col=1)

    # ── Row 5: Spike event markers ───────────────────────────────────────────
    CONF_STYLE = {
        'CONFIRMED_BULLISH': ('#10b981', 'triangle-up',   18, '🚀 Confirmed Bullish'),
        'CONFIRMED_BEARISH': ('#ef4444', 'triangle-down', 18, '💥 Confirmed Bearish'),
        'DIVERGENCE':        ('#f59e0b', 'diamond',       16, '⚠️ Divergence'),
        'UNCONFIRMED':       ('#8b5cf6', 'circle',        12, '📊 Unconfirmed'),
    }
    for conf_key, (color, symbol, size, legend_name) in CONF_STYLE.items():
        mask = df_spikes['vol_spike'] & (df_spikes['gex_confirmation'] == conf_key)
        sub  = df_spikes[mask]
        if sub.empty: continue
        fig.add_trace(go.Scatter(
            x=sub['timestamp'],
            y=sub['vol_z_score'].clip(upper=6),
            mode='markers+text',
            marker=dict(symbol=symbol, size=size, color=color, line=dict(color='white', width=1.5)),
            text=sub['event_label'],
            textposition='top center',
            textfont=dict(color='white', size=9),
            name=legend_name, showlegend=True,
            customdata=np.stack([
                sub['spike_type'].values,
                sub['spike_strength'].values,
                sub.get('call_volume', pd.Series([0]*len(sub))).values,
                sub.get('put_volume',  pd.Series([0]*len(sub))).values,
                sub['gex_change'].values,
            ], axis=-1),
            hovertemplate=(
                '%{x|%H:%M}<br>Type: %{customdata[0]}<br>Strength: %{customdata[1]}<br>'
                'Call Vol: %{customdata[2]:,.0f}<br>Put Vol: %{customdata[3]:,.0f}<br>'
                f'GEX Δ: %{{customdata[4]:+.4f}}{unit_label}<extra></extra>'
            ),
        ), row=5, col=1)

    fig.add_hline(y=z_threshold, line_dash='dash',
                  line_color='rgba(245,158,11,0.4)', line_width=1, row=5, col=1)

    # ── Layout ───────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                "<b>📈 Intraday Timeline — Volume Spike & GEX Overlay</b><br>"
                "<sub>🚀 Confirmed Bullish = Call spike + GEX rising | "
                "💥 Confirmed Bearish = Put spike + GEX falling | "
                "⚠️ Divergence = Volume & GEX conflict | "
                "📊 Unconfirmed = Volume spike, GEX flat | "
                "✏️ Use toolbar to draw</sub>"
            ),
            font=dict(size=15, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=1180,
        barmode='stack',
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=60, r=60, t=140, b=60),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
                      modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'))

    fig.update_yaxes(title_text=f'GEX (₹{unit_label})',      row=1, col=1, secondary_y=False, gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text=f'|GEX Δ| (₹{unit_label})',  row=1, col=1, secondary_y=True,  showgrid=False)
    fig.update_yaxes(title_text='Spot Price (₹)',             row=2, col=1, gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text='Volume (contracts)',         row=3, col=1, gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text='Z-Score (σ)',                row=4, col=1, gridcolor='rgba(128,128,128,0.15)', range=[0,None])
    fig.update_yaxes(title_text='Spike Z-Score',              row=5, col=1, gridcolor='rgba(128,128,128,0.15)', range=[0,None])
    fig.update_xaxes(title_text='Time (IST)',                 row=5, col=1)

    return fig, df_spikes

# ============================================================================
# SIGNIFICANT GEX CLASSIFICATION  (Addition vs Unwind)
# ============================================================================

def classify_gex_significance(df: pd.DataFrame, spot_price: float) -> pd.DataFrame:
    """
    Classifies each strike's GEX into:
      STRONG_ADD | STRONG_UNWIND | WEAK_ADD | WEAK_UNWIND | NOISE

    Significance Score = |ΔOI| × gamma × volume_weight × atm_weight
    """
    df = df.copy()
    OI_CHANGE_THRESHOLD_PCT = 0.02
    VOLUME_CONFIRM_PCT      = 0.15
    ATM_BAND_PCT            = 0.03

    total_call_vol = df['call_volume'].sum() if 'call_volume' in df.columns else 1
    total_put_vol  = df['put_volume'].sum()  if 'put_volume'  in df.columns else 1

    bs_calc = BlackScholesCalculator()
    r, tte  = 0.07, 7/365

    scores, categories = [], []

    for _, row in df.iterrows():
        spot   = row.get('spot_price', spot_price)
        strike = row['strike']
        call_oi_now    = row.get('call_oi', 0)
        put_oi_now     = row.get('put_oi', 0)
        call_oi_change = row.get('call_oi_change', 0)
        put_oi_change  = row.get('put_oi_change', 0)
        call_vol       = row.get('call_volume', 0)
        put_vol        = row.get('put_volume', 0)
        call_iv        = row.get('call_iv', 15)
        put_iv         = row.get('put_iv', 15)

        dist_pct   = abs(strike - spot) / spot
        atm_weight = np.exp(-dist_pct / ATM_BAND_PCT)

        call_vol_share = call_vol / total_call_vol if total_call_vol > 0 else 0
        put_vol_share  = put_vol  / total_put_vol  if total_put_vol  > 0 else 0
        vol_weight = 1 + (call_vol_share + put_vol_share) * 5

        call_iv_d = call_iv / 100 if call_iv > 1 else call_iv
        put_iv_d  = put_iv  / 100 if put_iv  > 1 else put_iv
        gamma = bs_calc.calculate_gamma(spot, strike, tte, r, (call_iv_d + put_iv_d) / 2)

        net_oi_change = call_oi_change - put_oi_change
        score = abs(net_oi_change) * gamma * vol_weight * atm_weight * spot**2
        scores.append(score)

        base_oi        = max(call_oi_now + put_oi_now, 1)
        oi_change_pct  = abs(net_oi_change) / base_oi
        is_meaningful  = oi_change_pct > OI_CHANGE_THRESHOLD_PCT
        is_vol_confirm = (call_vol_share > VOLUME_CONFIRM_PCT or put_vol_share > VOLUME_CONFIRM_PCT)
        is_near_atm    = dist_pct < ATM_BAND_PCT

        if net_oi_change > 0:
            cat = ('STRONG_ADD'   if is_meaningful and (is_vol_confirm or is_near_atm)
                   else 'WEAK_ADD' if is_meaningful else 'NOISE')
        elif net_oi_change < 0:
            cat = ('STRONG_UNWIND'   if is_meaningful and (is_vol_confirm or is_near_atm)
                   else 'WEAK_UNWIND' if is_meaningful else 'NOISE')
        else:
            cat = 'NOISE'
        categories.append(cat)

    df['significance_score'] = scores
    df['gex_category']       = categories
    max_score = max(scores) if max(scores) > 0 else 1
    df['significance_pct'] = df['significance_score'] / max_score * 100
    return df


def create_significant_gex_chart(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> Tuple[go.Figure, pd.DataFrame]:
    """
    Significant GEX chart that visually separates:
      STRONG_ADD     → Bright Green  (solid border)
      STRONG_UNWIND  → Bright Red    (solid border)
      WEAK_ADD       → Dim Green     (transparent)
      WEAK_UNWIND    → Dim Red       (transparent)
      NOISE          → Gray          (very transparent)
    Secondary axis shows Significance Score as a dotted line.
    Returns (fig, df_classified)
    """
    df_classified = classify_gex_significance(df, spot_price)
    df_sorted     = df_classified.sort_values('strike').reset_index(drop=True)
    flip_zones    = identify_gamma_flip_zones(df_sorted, spot_price)

    COLOR_MAP = {
        'STRONG_ADD'   : ('#10b981', 0.95, 2),
        'STRONG_UNWIND': ('#ef4444', 0.95, 2),
        'WEAK_ADD'     : ('#10b981', 0.30, 0),
        'WEAK_UNWIND'  : ('#ef4444', 0.30, 0),
        'NOISE'        : ('#64748b', 0.18, 0),
    }
    LABEL_MAP = {
        'STRONG_ADD'   : '🟢 Strong Addition  (High Significance)',
        'STRONG_UNWIND': '🔴 Strong Unwind    (High Significance)',
        'WEAK_ADD'     : '🟩 Weak Addition    (Low Significance)',
        'WEAK_UNWIND'  : '🟥 Weak Unwind      (Low Significance)',
        'NOISE'        : '⬜ Noise / Residual OI',
    }

    fig = go.Figure()

    for cat, (color, opacity, bw) in COLOR_MAP.items():
        sub = df_sorted[df_sorted['gex_category'] == cat]
        if sub.empty: continue
        fig.add_trace(go.Bar(
            y=sub['strike'], x=sub['net_gex'], orientation='h',
            name=LABEL_MAP[cat],
            marker=dict(color=color, opacity=opacity, line=dict(color='white', width=bw)),
            customdata=np.stack([
                sub['significance_pct'].values,
                sub.get('call_oi_change', pd.Series([0]*len(sub))).values,
                sub.get('put_oi_change',  pd.Series([0]*len(sub))).values,
                sub.get('total_volume',   pd.Series([0]*len(sub))).values,
            ], axis=-1),
            hovertemplate=(
                f'Strike: %{{y:,.0f}}<br>Net GEX: %{{x:.4f}}{unit_label}<br>'
                'Significance: %{customdata[0]:.1f}%<br>'
                'Call OI Δ: %{customdata[1]:,.0f}<br>'
                'Put OI Δ: %{customdata[2]:,.0f}<br>'
                'Volume: %{customdata[3]:,.0f}<extra></extra>'
            ),
        ))

    # Significance score line (secondary x)
    fig.add_trace(go.Scatter(
        y=df_sorted['strike'], x=df_sorted['significance_pct'],
        mode='lines+markers', name='Significance Score (%)',
        line=dict(color='#f59e0b', width=2, dash='dot'),
        marker=dict(size=5, color='#f59e0b'),
        xaxis='x4',
        hovertemplate='Strike: %{y:,.0f}<br>Score: %{x:.1f}%<extra></extra>',
    ))

    fig = _add_volume_overlay_horizontal(fig, df_sorted)

    fig.add_hline(y=spot_price, line_dash='dash', line_color='white', line_width=3,
                  annotation_text=f'Spot: {spot_price:,.2f}', annotation_position='top right',
                  annotation=dict(font=dict(size=12, color='white', family='Arial Black')))
    fig.add_vline(x=0, line_dash='dot', line_color='gray', line_width=2)

    for zone in flip_zones:
        fig.add_hline(y=zone['strike'], line_dash='dot',
                      line_color=zone['color'], line_width=2,
                      annotation_text=f"🔄 Flip {zone['arrow']} {zone['strike']:,.0f}",
                      annotation_position='left',
                      annotation=dict(font=dict(size=10, color=zone['color']),
                                      bgcolor='rgba(0,0,0,0.7)', bordercolor=zone['color'], borderwidth=1))
        fig.add_hrect(y0=zone['lower_strike'], y1=zone['upper_strike'],
                      fillcolor=zone['color'], opacity=0.05, line_width=0)

    fig.update_layout(
        title=dict(
            text=(
                '<b>🎯 Significant GEX: Addition vs Unwind Classification</b><br>'
                '<sub>🟢 Strong Add = OI↑ + Vol/ATM confirmed | 🔴 Strong Unwind = OI↓ + Vol/ATM confirmed | '
                'Dim = Low significance | ⬜ Noise | 🟡 dotted = Significance Score | ✏️ toolbar to draw</sub>'
            ),
            font=dict(size=15, color='white'),
        ),
        xaxis_title=f'GEX (₹ {unit_label})',
        yaxis_title='Strike Price',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=760,
        barmode='overlay', bargap=0.15,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=10), bgcolor='rgba(0,0,0,0.8)',
                    bordercolor='white', borderwidth=1),
        hovermode='closest',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True,
                   zeroline=True, zerolinecolor='rgba(255,255,255,0.3)', zerolinewidth=2),
        xaxis4=dict(overlaying='x', side='bottom', title='Significance Score (%)',
                    range=[0, 500], showgrid=False, showline=False, zeroline=False,
                    tickfont=dict(color='rgba(245,158,11,0.7)', size=9),
                    title_font=dict(color='rgba(245,158,11,0.7)', size=10)),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        margin=dict(l=80, r=80, t=120, b=80),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
                      modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'))

    return fig, df_classified

# ============================================================================
# STANDARD VISUALIZATION FUNCTIONS (unchanged from original, all with Volume Overlay)
# ============================================================================

def create_separate_gex_chart(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> go.Figure:
    df_sorted  = df.sort_values('strike').reset_index(drop=True)
    colors     = ['#10b981' if x > 0 else '#ef4444' for x in df_sorted['net_gex']]
    flip_zones = identify_gamma_flip_zones(df_sorted, spot_price)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df_sorted['strike'], x=df_sorted['net_gex'], orientation='h',
                         marker_color=colors, name='Net GEX', showlegend=True,
                         hovertemplate=f'Strike: %{{y:,.0f}}<br>Net GEX: %{{x:.4f}}{unit_label}<extra></extra>'))
    fig = _add_volume_overlay_horizontal(fig, df_sorted)
    fig.add_hline(y=spot_price, line_dash='dash', line_color='#06b6d4', line_width=3,
                  annotation_text=f'Spot: {spot_price:,.2f}', annotation_position='top right',
                  annotation=dict(font=dict(size=12, color='white')))
    for zone in flip_zones:
        fig.add_hline(y=zone['strike'], line_dash='dot', line_color=zone['color'], line_width=2,
                      annotation_text=f"🔄 Flip {zone['arrow']} {zone['strike']:,.0f}",
                      annotation_position='left',
                      annotation=dict(font=dict(size=10, color=zone['color']),
                                      bgcolor='rgba(0,0,0,0.7)', bordercolor=zone['color'], borderwidth=1))
        fig.add_hrect(y0=zone['lower_strike'], y1=zone['upper_strike'],
                      fillcolor=zone['color'], opacity=0.1, line_width=0,
                      annotation_text=zone['arrow'], annotation_position='right',
                      annotation=dict(font=dict(size=16, color=zone['color'])))
    fig.update_layout(
        title=dict(text='<b>🎯 Gamma Exposure (GEX) with Flip Zones</b><br><sub>Green/Red = Net GEX | 🟩🟥 = Call/Put Volume (top axis) | ✏️ toolbar to draw</sub>',
                   font=dict(size=18, color='white')),
        xaxis_title=f'GEX (₹ {unit_label})', yaxis_title='Strike Price',
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(26,35,50,0.8)',
        height=700, barmode='overlay',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=11), bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1),
        hovermode='closest',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        margin=dict(l=80, r=80, t=80, b=80), dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
                      modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'))
    return fig


def compute_gex_strike_probability(
    df_sorted: pd.DataFrame,
    spot_price: float,
    flip_zones: list,
    unit_label: str = "B",
) -> pd.DataFrame:
    """
    Computes per-strike directional probability (bull% / bear%) for the GEX overlay chart.

    Signals (all per-strike, independent):
      1. GEX sign × magnitude   (40%) — positive GEX = dealer support = bullish
      2. Call/Put volume ratio  (25%) — call-heavy = bullish flow
      3. OI GEX vs Original GEX alignment (20%) — same sign = confirmation, opposite = divergence
      4. Distance from spot     (15%) — ATM strikes dominate

    Overlaid flags:
      • VOLUME_SPIKE   — z-score > 2.5 on total_volume at this strike (relative to cross-strike)
      • DIVERGENCE     — enhanced OI GEX and original GEX have opposite signs (conflicting dealer view)
      • NEAR_FLIP_ZONE — strike within 0.5% of a GEX flip zone (transition zone)

    Returns df_sorted with added columns:
      bull_prob, bear_prob, prob_direction, prob_icon, vol_flag, div_flag, flip_flag, hover_text
    """
    df = df_sorted.copy()

    # ── Signal 1: GEX sign × magnitude (40%) ─────────────────────────────
    max_gex = df['net_gex'].abs().max() or 1.0
    gex_norm = df['net_gex'] / max_gex                  # -1 to +1
    gex_bull = ((gex_norm + 1) / 2 * 100).clip(0, 100)  # 0→100
    gex_bear = (100 - gex_bull)

    # ── Signal 2: Call/Put volume ratio (25%) ─────────────────────────────
    cv = df['call_volume'].fillna(0).clip(lower=0)
    pv = df['put_volume'].fillna(0).clip(lower=0)
    total = (cv + pv).replace(0, 1)
    vol_bull = (cv / total * 100).clip(0, 100)
    vol_bear = (100 - vol_bull)

    # ── Signal 3: Enhanced OI GEX vs Original GEX alignment (20%) ────────
    enh = df.get('enhanced_oi_gex', pd.Series(0.0, index=df.index)).fillna(0)
    orig = df['net_gex'].fillna(0)
    # Same sign = confirmed = neutral (50/50), opposite sign = divergence
    # When aligned: bull if both positive, bear if both negative
    # When diverged: skew toward bear (divergence = uncertainty = discount bull)
    align_bull = []
    for e, o in zip(enh, orig):
        if o > 0 and e > 0:       align_bull.append(65.0)   # confirmed bullish
        elif o < 0 and e < 0:     align_bull.append(35.0)   # confirmed bearish
        elif o > 0 and e < 0:     align_bull.append(42.0)   # divergence → bearish lean
        elif o < 0 and e > 0:     align_bull.append(58.0)   # divergence → bullish lean
        else:                     align_bull.append(50.0)   # one is zero
    align_bull = pd.Series(align_bull, index=df.index)
    align_bear = 100 - align_bull

    # ── Signal 4: Distance weight (15%) ───────────────────────────────────
    dist_pct = ((df['strike'] - spot_price).abs() / spot_price * 100).clip(lower=0)
    # Nearer = higher weight. Exponential decay: weight = e^(-d/2)
    dist_weight = np.exp(-dist_pct / 2.0)          # 0 to 1
    # Distance alone doesn't give direction — it amplifies the other signals
    # We fold it into a weighted composite below

    # ── Weighted composite ────────────────────────────────────────────────
    w1, w2, w3 = 0.40, 0.25, 0.20
    w4 = 0.15  # distance weight modifier (not a separate signal, but a scalar)

    # Distance bonus: if above spot, slightly favour bull (momentum), below = bear
    pos_above = (df['strike'] >= spot_price).astype(float)  # 1 if above
    dist_dir_bonus = (pos_above - 0.5) * dist_weight * 10  # ±0 to ±5 pts

    raw_bull = (w1*gex_bull + w2*vol_bull + w3*align_bull) + dist_dir_bonus * w4 * 10
    raw_bear = (w1*gex_bear + w2*vol_bear + w3*align_bear) - dist_dir_bonus * w4 * 10

    # Normalise so they sum to 100
    total_score = (raw_bull + raw_bear).replace(0, 100)
    df['bull_prob'] = (raw_bull / total_score * 100).clip(0, 100).round(1)
    df['bear_prob'] = (100 - df['bull_prob']).round(1)

    # ── Direction + icon ─────────────────────────────────────────────────
    def _dir(bull):
        if bull >= 60: return 'BULLISH', '🟢'
        if bull <= 40: return 'BEARISH', '🔴'
        return 'NEUTRAL', '⬜'

    dirs, icons = zip(*[_dir(b) for b in df['bull_prob']])
    df['prob_direction'] = list(dirs)
    df['prob_icon']      = list(icons)

    # ── Volume spike flag (per-strike, z-score across strikes) ───────────
    tv = df['total_volume'].fillna(0)
    tv_mean = tv.mean(); tv_std = tv.std() or 1.0
    tv_z = (tv - tv_mean) / tv_std
    df['vol_flag'] = tv_z > 2.5   # True if this strike has anomalous volume vs peers

    # ── GEX divergence flag (enhanced vs original sign conflict) ─────────
    df['div_flag'] = (
        (enh > 0) & (orig < 0) |
        (enh < 0) & (orig > 0)
    )

    # ── Flip zone proximity flag ──────────────────────────────────────────
    flip_strikes = [z['strike'] for z in flip_zones]
    def _near_flip(strike):
        return any(abs(strike - fz) / max(spot_price, 1) * 100 < 0.5 for fz in flip_strikes)
    df['flip_flag'] = df['strike'].apply(_near_flip)

    # ── Composite flag icon for chart annotation ──────────────────────────
    def _composite_icon(row):
        icons = []
        if row['vol_flag']:  icons.append('⚡')
        if row['div_flag']:  icons.append('⚠️')
        if row['flip_flag']: icons.append('🔄')
        return ' '.join(icons)
    df['flag_icons'] = df.apply(_composite_icon, axis=1)

    # ── Rich hover text ───────────────────────────────────────────────────
    def _hover(row):
        flags = []
        if row['vol_flag']:  flags.append('⚡ Vol Spike')
        if row['div_flag']:  flags.append('⚠️ GEX Divergence')
        if row['flip_flag']: flags.append('🔄 Near Flip Zone')
        flag_str = ' | '.join(flags) if flags else '—'
        return (
            f"Strike: ₹{row['strike']:,.0f}<br>"
            f"{row['prob_icon']} Bull: {row['bull_prob']:.0f}% | Bear: {row['bear_prob']:.0f}%<br>"
            f"Direction: {row['prob_direction']}<br>"
            f"Flags: {flag_str}<br>"
            f"GEX: {row['net_gex']:.2f} | Vol: {row.get('total_volume',0):,.0f}"
        )
    df['hover_text'] = df.apply(_hover, axis=1)

    return df


def create_enhanced_gex_overlay_chart(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> go.Figure:
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    for col in ['net_gex','call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df_sorted.columns: df_sorted[col] = 0.0
        df_sorted[col] = df_sorted[col].fillna(0)
    df_sorted['enhanced_oi_gex'] = 0.0
    bs_calc = BlackScholesCalculator()
    try:
        total_vol = df_sorted['total_volume'].sum()
        for idx, row in df_sorted.iterrows():
            spot = row.get('spot_price', spot_price); strike = row['strike']
            if spot <= 0 or strike <= 0: continue
            tte = 7/365
            civ = row['call_iv']/100 if row['call_iv'] > 1 else row['call_iv']
            piv = row['put_iv']/100  if row['put_iv']  > 1 else row['put_iv']
            cg = bs_calc.calculate_gamma(spot, strike, tte, 0.07, civ)
            pg = bs_calc.calculate_gamma(spot, strike, tte, 0.07, piv)
            vw = 1 + (row['total_volume'] / total_vol) if total_vol > 0 else 1.0
            iv_adj = 1 + ((civ+piv)/2 * 2)
            dw = 1 / (1 + abs(strike-spot)/spot * 2)
            sc = 1e9 if unit_label == 'B' else 1e7
            cs = 25
            df_sorted.loc[idx, 'enhanced_oi_gex'] = (
                (row['call_oi_change'] * cg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc -
                (row['put_oi_change']  * pg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc
            )
    except: pass
    max_gex = df_sorted['net_gex'].abs().max()
    max_enh = df_sorted['enhanced_oi_gex'].abs().max()
    flip_zones = identify_gamma_flip_zones(df_sorted, spot_price)

    # ── Per-strike directional probability ───────────────────────────────
    df_prob = compute_gex_strike_probability(df_sorted, spot_price, flip_zones, unit_label)

    fig = go.Figure()

    # ── Original GEX bars ────────────────────────────────────────────────
    orig_colors = ['#10b981' if x > 0 else '#ef4444' for x in df_sorted['net_gex']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['net_gex'], orientation='h',
        marker=dict(color=orig_colors, opacity=0.6, line=dict(width=0)),
        name=f'Original GEX – Max: {max_gex:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Original GEX: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    # ── Enhanced OI GEX bars ─────────────────────────────────────────────
    enh_colors = ['#8b5cf6' if x > 0 else '#f59e0b' for x in df_sorted['enhanced_oi_gex']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['enhanced_oi_gex'], orientation='h',
        marker=dict(color=enh_colors, opacity=0.85, line=dict(color='white', width=1)),
        name=f'Enhanced OI GEX – Max: {max_enh:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Enhanced OI GEX: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    # ── Volume overlay ───────────────────────────────────────────────────
    fig = _add_volume_overlay_horizontal(fig, df_sorted)

    # ── Probability bars on right-side x-axis (x4) ───────────────────────
    # Bull% bars: green, pointing right from 0 to bull_prob
    # Bear% bars: red, pointing left from 0 (negative)
    bull_colors_prob = [
        'rgba(16,185,129,0.75)' if d == 'BULLISH' else
        'rgba(16,185,129,0.35)' if d == 'NEUTRAL' else
        'rgba(16,185,129,0.20)'
        for d in df_prob['prob_direction']
    ]
    bear_colors_prob = [
        'rgba(239,68,68,0.75)' if d == 'BEARISH' else
        'rgba(239,68,68,0.35)' if d == 'NEUTRAL' else
        'rgba(239,68,68,0.20)'
        for d in df_prob['prob_direction']
    ]
    fig.add_trace(go.Bar(
        y=df_prob['strike'],
        x=df_prob['bull_prob'],
        orientation='h',
        name='🟢 Bull Prob%',
        xaxis='x4',
        marker=dict(color=bull_colors_prob, line=dict(width=0)),
        hovertemplate='%{customdata}<extra></extra>',
        customdata=df_prob['hover_text'],
        legendgroup='prob',
    ))
    fig.add_trace(go.Bar(
        y=df_prob['strike'],
        x=-df_prob['bear_prob'],    # negative = leftward from centre
        orientation='h',
        name='🔴 Bear Prob%',
        xaxis='x4',
        marker=dict(color=bear_colors_prob, line=dict(width=0)),
        hovertemplate='%{customdata}<extra></extra>',
        customdata=df_prob['hover_text'],
        showlegend=True,
        legendgroup='prob',
    ))

    # ── 50% centre line on prob axis ─────────────────────────────────────
    fig.add_shape(
        type='line', xref='x4', yref='paper',
        x0=0, x1=0, y0=0, y1=1,
        line=dict(color='rgba(255,255,255,0.25)', width=1.5, dash='dot'),
    )

    # ── Flag markers: volume spikes, divergences, flip-zone strikes ───────
    flagged = df_prob[df_prob['flag_icons'] != ''].copy()
    if not flagged.empty:
        fig.add_trace(go.Scatter(
            x=[52] * len(flagged),   # just right of centre on x4 scale
            y=flagged['strike'],
            xaxis='x4',
            mode='text',
            text=flagged['flag_icons'],
            textfont=dict(size=11),
            name='⚡⚠️🔄 Flags',
            hovertemplate='%{customdata}<extra></extra>',
            customdata=flagged['hover_text'],
            showlegend=True,
        ))

    # ── Spot line ─────────────────────────────────────────────────────────
    fig.add_hline(
        y=spot_price, line_dash='dash', line_color='white', line_width=3,
        annotation_text=f'Spot: {spot_price:,.2f}', annotation_position='top right',
        annotation=dict(font=dict(size=12, color='white', family='Arial Black')),
    )
    fig.add_vline(x=0, line_dash='dot', line_color='gray', line_width=2)

    # ── GEX flip zone lines ───────────────────────────────────────────────
    for zone in flip_zones:
        fig.add_hline(
            y=zone['strike'], line_dash='dot', line_color=zone['color'], line_width=2,
            annotation_text=f"🔄 {zone['strike']:,.0f}", annotation_position='left',
            annotation=dict(font=dict(size=10, color=zone['color']),
                            bgcolor='rgba(0,0,0,0.7)', bordercolor=zone['color'], borderwidth=1),
        )
        fig.add_hrect(
            y0=zone['lower_strike'], y1=zone['upper_strike'],
            fillcolor=zone['color'], opacity=0.05, line_width=0,
        )

    # ── Probability axis 50% labels ───────────────────────────────────────
    # Annotate the prob axis header
    y_max = df_prob['strike'].max()
    fig.add_annotation(
        x=50, y=y_max, xref='x4', yref='y',
        text='<b>← Bear% | Bull% →</b>',
        showarrow=False,
        font=dict(size=9, color='#94a3b8'),
        xanchor='center', yanchor='bottom',
        bgcolor='rgba(0,0,0,0.6)', borderwidth=0,
    )

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                '<b>🚀 Enhanced GEX Overlay: Original vs Enhanced OI GEX</b><br>'
                '<sub>Green/Red = All effects | Purple/Gold = OI Δ with Greeks+Vol+IV+Distance | '
                '🟩🟥 = Volume | <b>Right panel:</b> 🟢 Bull% / 🔴 Bear% per strike '
                '| ⚡ Vol Spike · ⚠️ GEX Divergence · 🔄 Near Flip | ✏️ toolbar to draw</sub>'
            ),
            font=dict(size=15, color='white'),
        ),
        xaxis_title=f'GEX (₹ {unit_label})',
        yaxis_title='Strike Price',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=750,
        barmode='overlay',
        bargap=0.15,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1,
        ),
        hovermode='closest',
        xaxis=dict(
            gridcolor='rgba(128,128,128,0.2)', showgrid=True,
            zeroline=True, zerolinecolor='rgba(255,255,255,0.3)', zerolinewidth=2,
            domain=[0, 0.68],   # GEX bars use left 68%
        ),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        # x4 = probability panel on right
        xaxis4=dict(
            overlaying=None,
            anchor='y',
            side='right',
            position=1.0,
            domain=[0.72, 1.0],  # right 28%
            range=[-100, 100],
            showgrid=False,
            showline=True,
            linecolor='rgba(255,255,255,0.2)',
            zeroline=True,
            zerolinecolor='rgba(255,255,255,0.4)',
            zerolinewidth=1.5,
            tickvals=[-75, -50, -25, 0, 25, 50, 75],
            ticktext=['75%', '50%', '25%', '0', '25%', '50%', '75%'],
            tickfont=dict(size=8, color='#94a3b8'),
            title=dict(text='Bear% ← | → Bull%', font=dict(size=9, color='#94a3b8')),
        ),
        margin=dict(l=80, r=120, t=110, b=80),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    return fig




def compute_enhanced_oi_gex_column(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> pd.DataFrame:
    """
    Compute enhanced_oi_gex for every row in df and store it as a column.
    This is the same formula used inside create_enhanced_oi_gex_only_chart()
    but writes the result back to the dataframe so cascade math and KPIs can use it.
    Formula: (call_oi_change × Cγ − put_oi_change × Pγ) × 1.5 × vol_weight × iv_adj × dist_weight × spot² × lot / sc
    """
    df = df.copy()
    for col in ['call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df.columns: df[col] = 0.0
        df[col] = df[col].fillna(0)
    df['enhanced_oi_gex'] = 0.0
    bs_calc   = BlackScholesCalculator()
    sc        = 1e9 if unit_label == 'B' else 1e7
    cs        = 25
    total_vol = max(df['total_volume'].sum(), 1)
    try:
        for idx, row in df.iterrows():
            spot  = row.get('spot_price', spot_price)
            strike = row['strike']
            if spot <= 0 or strike <= 0: continue
            civ = row['call_iv']/100 if row['call_iv'] > 1 else row['call_iv']
            piv = row['put_iv'] /100 if row['put_iv']  > 1 else row['put_iv']
            cg  = bs_calc.calculate_gamma(spot, strike, 7/365, 0.07, civ)
            pg  = bs_calc.calculate_gamma(spot, strike, 7/365, 0.07, piv)
            vw  = 1 + (row['total_volume'] / total_vol)
            iv_adj = 1 + ((civ + piv) / 2 * 2)
            dw  = 1 / (1 + abs(strike - spot) / spot * 2)
            df.loc[idx, 'enhanced_oi_gex'] = (
                (row['call_oi_change'] * cg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc -
                (row['put_oi_change']  * pg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc
            )
    except: pass
    return df



def detect_enhanced_gex_spikes(
    df: pd.DataFrame,
    spot_col: str = 'spot_price',
    unit_label: str = "B",
    strike_band: int = 3,
    spike_threshold: float = 5000.0,
) -> pd.DataFrame:
    """
    Intraday Enhanced OI GEX Spike Detector.

    For every timestamp:
      1. Compute enhanced_oi_gex for each strike (same formula as the chart).
      2. Find strikes within ±(strike_band) strikes of the ATM strike.
      3. Sum the absolute enhanced_oi_gex for NEGATIVE (gold) and POSITIVE (purple)
         bars separately within that near-spot band.
      4. Flag the timestamp as a spike if either:
           |gold_sum| >= spike_threshold  (large negative GEX cluster = bear fuel)
           |purple_sum| >= spike_threshold (large positive GEX cluster = bull brake)

    Returns a timeline DataFrame with columns:
      timestamp, spot, atm_strike,
      near_gold_gex  (sum of negative enhanced_oi_gex near spot),
      near_purple_gex(sum of positive enhanced_oi_gex near spot),
      near_net_gex   (net = purple + gold),
      near_abs_gex   (|gold| + |purple|),
      gold_spike     (bool — |gold| >= threshold),
      purple_spike   (bool — |purple| >= threshold),
      any_spike      (bool — either),
      spike_type     ('GOLD_BEAR'|'PURPLE_BULL'|'BOTH'|''),
      spike_strength ('EXTREME'|'STRONG'|'MODERATE'|''),
      spike_label    (short annotation text),
      spike_color    (hex color for chart),
    """
    bs_calc   = BlackScholesCalculator()
    sc        = 1e9 if unit_label == 'B' else 1e7
    cs        = 25

    all_ts = sorted(df['timestamp'].unique())
    rows   = []

    for ts in all_ts:
        grp = df[df['timestamp'] == ts].copy()
        if grp.empty:
            continue

        spot    = float(grp[spot_col].iloc[0])
        total_vol = max(grp['total_volume'].fillna(0).sum(), 1)

        # Compute enhanced_oi_gex per strike at this timestamp
        grp = grp.copy()
        grp['_enh_gex'] = 0.0
        for idx, row in grp.iterrows():
            strike = row['strike']
            if spot <= 0 or strike <= 0:
                continue
            civ = row.get('call_iv', 15)
            piv = row.get('put_iv',  15)
            civ = civ / 100 if civ > 1 else civ
            piv = piv / 100 if piv > 1 else piv
            cg  = bs_calc.calculate_gamma(spot, strike, 7/365, 0.07, civ)
            pg  = bs_calc.calculate_gamma(spot, strike, 7/365, 0.07, piv)
            vw  = 1 + (row.get('total_volume', 0) / total_vol)
            iv_adj = 1 + ((civ + piv) / 2 * 2)
            dw  = 1 / (1 + abs(strike - spot) / spot * 2)
            coc = row.get('call_oi_change', 0)
            poc = row.get('put_oi_change',  0)
            grp.loc[idx, '_enh_gex'] = (
                (coc * cg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc -
                (poc * pg * 1.5 * vw * iv_adj * dw * spot**2 * cs) / sc
            )

        # Find ATM strike (nearest to spot)
        strikes_sorted = sorted(grp['strike'].unique())
        if not strikes_sorted:
            continue
        atm_strike = min(strikes_sorted, key=lambda k: abs(k - spot))
        atm_idx    = strikes_sorted.index(atm_strike)

        # Near-spot band: ±strike_band strikes around ATM
        lo_idx = max(0, atm_idx - strike_band)
        hi_idx = min(len(strikes_sorted) - 1, atm_idx + strike_band)
        near_strikes = strikes_sorted[lo_idx : hi_idx + 1]
        near_df = grp[grp['strike'].isin(near_strikes)]

        gold_sum   = near_df[near_df['_enh_gex'] < 0]['_enh_gex'].sum()   # negative = gold
        purple_sum = near_df[near_df['_enh_gex'] > 0]['_enh_gex'].sum()   # positive = purple
        net_gex    = gold_sum + purple_sum
        abs_gex    = abs(gold_sum) + abs(purple_sum)

        gold_spike   = abs(gold_sum)   >= spike_threshold
        purple_spike = abs(purple_sum) >= spike_threshold

        if gold_spike and purple_spike:
            spike_type = 'BOTH'
            color = '#f59e0b'
        elif gold_spike:
            spike_type = 'GOLD_BEAR'
            color = '#ef4444'
        elif purple_spike:
            spike_type = 'PURPLE_BULL'
            color = '#8b5cf6'
        else:
            spike_type = ''
            color = '#334155'

        any_spike = gold_spike or purple_spike

        # Strength tiers
        if any_spike:
            max_abs = max(abs(gold_sum), abs(purple_sum))
            if max_abs >= spike_threshold * 3:
                strength = 'EXTREME'
            elif max_abs >= spike_threshold * 2:
                strength = 'STRONG'
            else:
                strength = 'MODERATE'
        else:
            strength = ''

        # Short annotation label
        if spike_type == 'GOLD_BEAR':
            label = f'🔴 {strength[:3]} GOLD {abs(gold_sum):.0f}{unit_label}'
        elif spike_type == 'PURPLE_BULL':
            label = f'🟣 {strength[:3]} PURPLE {purple_sum:.0f}{unit_label}'
        elif spike_type == 'BOTH':
            label = f'⚡ {strength[:3]} BOTH ±{abs_gex:.0f}{unit_label}'
        else:
            label = ''

        rows.append({
            'timestamp'   : ts,
            'spot'        : spot,
            'atm_strike'  : atm_strike,
            'near_gold_gex'  : round(gold_sum,   2),
            'near_purple_gex': round(purple_sum, 2),
            'near_net_gex'   : round(net_gex,    2),
            'near_abs_gex'   : round(abs_gex,    2),
            'gold_spike'     : gold_spike,
            'purple_spike'   : purple_spike,
            'any_spike'      : any_spike,
            'spike_type'     : spike_type,
            'spike_strength' : strength,
            'spike_label'    : label,
            'spike_color'    : color,
        })

    return pd.DataFrame(rows).sort_values('timestamp').reset_index(drop=True)


def create_enhanced_gex_spike_chart(
    spike_df: pd.DataFrame,
    unit_label: str = "B",
    spike_threshold: float = 5000.0,
    strike_band: int = 3,
) -> go.Figure:
    """
    3-row intraday chart showing Enhanced OI GEX spike activity near spot:
      Row 1 – Gold (negative) and Purple (positive) near-spot GEX bars over time
               with threshold bands and spike markers
      Row 2 – Net near-spot GEX line (purple if positive, gold if negative)
               shows whether bull brakes or bear fuel dominate near ATM
      Row 3 – Spike event markers coloured by type
    """
    if spike_df.empty:
        fig = go.Figure()
        fig.update_layout(template='plotly_dark', height=300,
                          title='No Enhanced OI GEX spike data available')
        return fig

    ts = spike_df['timestamp']
    n_spikes  = spike_df['any_spike'].sum()
    n_gold    = spike_df['gold_spike'].sum()
    n_purple  = spike_df['purple_spike'].sum()
    n_both    = (spike_df['spike_type'] == 'BOTH').sum()

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            f'Near-Spot Enhanced OI GEX (±{strike_band} strikes from ATM)  '
            f'·  Threshold: ±{spike_threshold:,.0f}{unit_label}',
            f'Net Near-Spot GEX  (Purple = bull brakes dominate | Gold = bear fuel dominates)',
            f'Spike Events  (🔴 Gold/Bear · 🟣 Purple/Bull · ⚡ Both)',
        ),
        vertical_spacing=0.07,
        row_heights=[0.44, 0.28, 0.28],
    )

    # ── Row 1: Gold bars (negative, below axis) + Purple bars (positive, above) ──
    fig.add_trace(go.Bar(
        x=ts, y=spike_df['near_gold_gex'],
        name=f'🟡 Gold (Bear Fuel) near spot',
        marker=dict(
            color=['#dc2626' if abs(v) >= spike_threshold else '#f59e0b'
                   for v in spike_df['near_gold_gex']],
            opacity=0.85, line=dict(width=0),
        ),
        hovertemplate=(
            '%{x|%H:%M}<br>'
            f'Gold GEX near spot: %{{y:.2f}}{unit_label}<br>'
            '<extra></extra>'
        ),
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=ts, y=spike_df['near_purple_gex'],
        name=f'🟣 Purple (Bull Brake) near spot',
        marker=dict(
            color=['#6d28d9' if v >= spike_threshold else '#8b5cf6'
                   for v in spike_df['near_purple_gex']],
            opacity=0.85, line=dict(width=0),
        ),
        hovertemplate=(
            '%{x|%H:%M}<br>'
            f'Purple GEX near spot: %{{y:.2f}}{unit_label}<br>'
            '<extra></extra>'
        ),
    ), row=1, col=1)

    # Threshold lines
    for level, color, label in [
        ( spike_threshold, 'rgba(139,92,246,0.7)',  f'+{spike_threshold:,.0f}{unit_label} Bull threshold'),
        (-spike_threshold, 'rgba(239,68,68,0.7)',   f'-{spike_threshold:,.0f}{unit_label} Bear threshold'),
        ( spike_threshold*2, 'rgba(109,40,217,0.5)', f'+{spike_threshold*2:,.0f} STRONG'),
        (-spike_threshold*2, 'rgba(185,28,28,0.5)',  f'-{spike_threshold*2:,.0f} STRONG'),
        ( spike_threshold*3, 'rgba(76,29,149,0.6)',  f'+{spike_threshold*3:,.0f} EXTREME'),
        (-spike_threshold*3, 'rgba(127,29,29,0.6)',  f'-{spike_threshold*3:,.0f} EXTREME'),
    ]:
        fig.add_hline(
            y=level, line_dash='dash', line_color=color, line_width=1.5,
            annotation_text=label, annotation_position='right',
            annotation=dict(font=dict(color=color, size=8)),
            row=1, col=1,
        )

    # Zero line
    fig.add_hline(y=0, line_dash='dot', line_color='rgba(255,255,255,0.3)',
                  line_width=1, row=1, col=1)

    # Spike vlines on row 1
    for _, sr in spike_df[spike_df['any_spike']].iterrows():
        vc = {'GOLD_BEAR':   'rgba(239,68,68,0.20)',
              'PURPLE_BULL': 'rgba(139,92,246,0.20)',
              'BOTH':        'rgba(245,158,11,0.25)'}.get(sr['spike_type'], 'rgba(255,255,255,0.08)')
        fig.add_vline(x=sr['timestamp'].timestamp()*1000,
                      line_dash='dot', line_color=vc, line_width=1.5, row=1, col=1)

    # ── Row 2: Net near-spot GEX line ────────────────────────────────────────
    net_colors = ['#8b5cf6' if v > 0 else '#f59e0b' for v in spike_df['near_net_gex']]
    fig.add_trace(go.Scatter(
        x=ts, y=spike_df['near_net_gex'],
        mode='lines+markers',
        line=dict(color='rgba(255,255,255,0.5)', width=1.5),
        marker=dict(size=5, color=net_colors, line=dict(color='white', width=1)),
        fill='tozeroy',
        fillcolor='rgba(139,92,246,0.06)',
        name='Net Near-Spot GEX',
        hovertemplate=(
            '%{x|%H:%M}<br>'
            f'Net: %{{y:.2f}}{unit_label}<br>'
            '<extra></extra>'
        ),
    ), row=2, col=1)
    fig.add_hline(y=0, line_dash='dot', line_color='rgba(255,255,255,0.3)',
                  line_width=1, row=2, col=1)

    # ── Row 3: Spike event markers ────────────────────────────────────────────
    SPIKE_STYLE = {
        'GOLD_BEAR':   ('#ef4444', 'triangle-down', 18, '🔴 Bear Fuel (Gold) Spike'),
        'PURPLE_BULL': ('#8b5cf6', 'triangle-up',   18, '🟣 Bull Brake (Purple) Spike'),
        'BOTH':        ('#f59e0b', 'diamond',        20, '⚡ Both — Contested Zone'),
    }
    for stype, (color, symbol, size, legend_name) in SPIKE_STYLE.items():
        mask = spike_df['spike_type'] == stype
        sub  = spike_df[mask]
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub['timestamp'],
            y=sub['near_abs_gex'],
            mode='markers+text',
            marker=dict(symbol=symbol, size=size, color=color,
                        line=dict(color='white', width=1.5)),
            text=sub['spike_label'],
            textposition='top center',
            textfont=dict(color='white', size=8, family='JetBrains Mono'),
            name=legend_name,
            customdata=sub[['spike_strength','near_gold_gex','near_purple_gex',
                             'near_net_gex','atm_strike']].values,
            hovertemplate=(
                '%{x|%H:%M}<br>'
                'Strength: %{customdata[0]}<br>'
                f'Gold: %{{customdata[1]:.2f}}{unit_label}<br>'
                f'Purple: %{{customdata[2]:.2f}}{unit_label}<br>'
                f'Net: %{{customdata[3]:.2f}}{unit_label}<br>'
                'ATM Strike: ₹%{customdata[4]:,.0f}<extra></extra>'
            ),
        ), row=3, col=1)

    fig.add_hline(y=spike_threshold, line_dash='dash',
                  line_color='rgba(245,158,11,0.4)', line_width=1, row=3, col=1)

    # ── Layout ────────────────────────────────────────────────────────────────
    summary = f"🔴 {n_gold} Gold · 🟣 {n_purple} Purple · ⚡ {n_both} Both"
    fig.update_layout(
        title=dict(
            text=(
                f'<b>⚡ Enhanced OI GEX Near-Spot Spike Monitor</b>  '
                f'<span style="font-size:12px;color:#94a3b8;">'
                f'({n_spikes} spikes — {summary})</span><br>'
                f'<sub>'
                f'🔴 Large GOLD (negative) cluster near ATM = bear fuel building → price can fall fast  |  '
                f'🟣 Large PURPLE (positive) cluster near ATM = bull brakes = resistance to further fall  |  '
                f'⚡ Both = contested zone, wait for resolution'
                f'</sub>'
            ),
            font=dict(size=13, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=560,
        barmode='overlay',
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.7)',
            bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=60, r=140, t=110, b=40),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    fig.update_yaxes(title_text=f'GEX ({unit_label})',  row=1, col=1,
                     gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text=f'Net GEX ({unit_label})', row=2, col=1,
                     gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text=f'|GEX| ({unit_label})',   row=3, col=1,
                     gridcolor='rgba(128,128,128,0.15)', range=[0, None])
    fig.update_xaxes(title_text='Time (IST)', row=3, col=1)

    return fig

def compute_gex_cascade(df: pd.DataFrame, spot_price: float, unit_label: str,
                         contract_size: int, gex_col: str = 'net_gex',
                         vanna_zones: list = None, iv_regime: str = 'FLAT',
                         symbol: str = 'NIFTY') -> pd.DataFrame:
    """
    Cascade Mathematics with VANNA Floor Integration.

    Base formula:
      pts_per_unit = 0.007  (empirical: 1B GEX → 0.007 pts on NIFTY)
      net_gex is stored in B units (~1-200B per strike for NIFTY)
      pts_raw = |net_gex_B| × 0.007  →  ~0.007 to 1.4 pts per strike

    VANNA Zone Adjustments (adj applied to pts_raw):
      strength = normalised zone magnitude vs max zone magnitude (0.25 to 1.0)
      — normalised against max zone so adjustments are relative, not absolute.

      SUPPORT_FLOOR + IV COMPRESSING → absorbs up to 60% (strong hold)
      SUPPORT_FLOOR + IV FLAT        → absorbs up to 35%
      SUPPORT_FLOOR + IV EXPANDING   → amplifies up to 20% (floor at risk)
      TRAP_DOOR     + IV EXPANDING   → amplifies up to 30% (trap armed)
      TRAP_DOOR     + IV FLAT        → amplifies up to 15%
      TRAP_DOOR     + IV COMPRESSING → absorbs up to 10%
      LOC (VACUUM_ZONE) + IV EXPANDING → absorbs up to 50% (dealers buy, absorb sellers)
      RESISTANCE    + IV EXPANDING   → amplifies up to 20%
      RESISTANCE    + IV FLAT/COMP   → absorbs up to 15%

    vanna_adj column: adjustment multiplier (>1 = amplify, <1 = absorb)
    vanna_note column: which zone is influencing this strike
    vanna_adj_pct column: human-readable % change (+30% or −60%)
    """
    import numpy as np
    pts_per_unit = 0.007   # empirical: 1B GEX → 0.007 pts

    df_c = df.sort_values('strike').reset_index(drop=True).copy()
    if gex_col not in df_c.columns:
        return pd.DataFrame()

    df_c['gex_raw']    = df_c[gex_col].fillna(0)
    df_c['vanna_adj']  = 1.0
    df_c['vanna_note'] = ''

    # ── Strike interval for proximity matching ────────────────────────────
    strike_diffs    = df_c['strike'].diff().abs().dropna()
    actual_interval = float(strike_diffs[strike_diffs > 0].median()) if len(strike_diffs[strike_diffs > 0]) > 0 else 50.0
    vanna_proximity = actual_interval * 1.0

    # ── Apply VANNA zone influence per strike ─────────────────────────────
    if vanna_zones:
        # Normalise strength against the maximum zone magnitude so that the
        # strongest zone gets full effect (strength=1.0) and weaker zones
        # get proportionally less. This fixes the old (mag / (mag+10)) formula
        # which collapsed to near-zero for VANNA magnitudes in the 0.04-0.5B range.
        mags = [z.get('magnitude', 0.0) for z in vanna_zones]
        max_mag = max(mags) if mags else 1.0
        if max_mag <= 0:
            max_mag = 1.0

        for z in vanna_zones:
            zk   = z['strike']
            role = z['role']
            mag  = z.get('magnitude', 0.0)
            # strength: 0.25 (weakest zone) to 1.0 (strongest zone)
            # ensures even the weakest zone has some effect
            strength = max(0.25, mag / max_mag)
            close_mask = (df_c['strike'] - zk).abs() <= vanna_proximity

            if not close_mask.any():
                continue

            if role == 'SUPPORT_FLOOR':
                if iv_regime == 'COMPRESSING':
                    adj  = 1.0 - 0.60 * strength
                    note = f'🛡️ Support Floor @{zk:,.0f} [IV COMPRESS → hold −{60*strength:.0f}%]'
                elif iv_regime == 'FLAT':
                    adj  = 1.0 - 0.35 * strength
                    note = f'🛡️ Support Floor @{zk:,.0f} [IV FLAT → moderate −{35*strength:.0f}%]'
                else:
                    adj  = 1.0 + 0.20 * strength
                    note = f'🛡️⚠️ Support Floor @{zk:,.0f} [IV EXPAND → at risk +{20*strength:.0f}%]'

            elif role == 'TRAP_DOOR':
                if iv_regime == 'EXPANDING':
                    adj  = 1.0 + 0.30 * strength
                    note = f'⚠️ Trap Door @{zk:,.0f} [IV EXPAND → ARMED +{30*strength:.0f}%]'
                elif iv_regime == 'FLAT':
                    adj  = 1.0 + 0.15 * strength
                    note = f'⚠️ Trap Door @{zk:,.0f} [IV FLAT → risk +{15*strength:.0f}%]'
                else:
                    adj  = 1.0 - 0.10 * strength
                    note = f'⚠️ Trap Door @{zk:,.0f} [IV COMPRESS → weakened −{10*strength:.0f}%]'

            elif role == 'VACUUM_ZONE':
                if iv_regime == 'EXPANDING':
                    adj  = 1.0 - 0.50 * strength
                    note = f'🚀 Vacuum @{zk:,.0f} [IV EXPAND → absorbs −{50*strength:.0f}%]'
                else:
                    adj  = 1.0
                    note = ''

            elif role == 'RESISTANCE_CEILING':
                if iv_regime == 'EXPANDING':
                    adj  = 1.0 + 0.20 * strength
                    note = f'🔴 Resistance @{zk:,.0f} [IV EXPAND → holds +{20*strength:.0f}%]'
                else:
                    adj  = 1.0 - 0.15 * strength
                    note = f'🔴 Resistance @{zk:,.0f} [IV COMPRESS → fades −{15*strength:.0f}%]'
            else:
                adj  = 1.0
                note = ''

            if note:
                # Only update if this zone gives a stronger adjustment than existing
                existing = df_c.loc[close_mask, 'vanna_adj']
                stronger = (adj - 1.0).__abs__() > (existing - 1.0).abs()
                df_c.loc[close_mask & stronger, 'vanna_adj']  = adj
                df_c.loc[close_mask & stronger, 'vanna_note'] = note

    # ── Compute pts: base then VANNA-adjusted ─────────────────────────────
    df_c['pts_raw']    = (df_c['gex_raw'].abs() * pts_per_unit).clip(upper=500)
    df_c['pts_impact'] = (df_c['pts_raw'] * df_c['vanna_adj']).round(2).clip(lower=0, upper=600)

    # ── Bear cascade: below spot, top→bottom ──────────────────────────────
    bear_df = df_c[df_c['strike'] <= spot_price].copy().sort_values('strike', ascending=False)
    bear_df['cascade_direction'] = 'BEAR'
    bear_df['cumulative_pts']    = bear_df['pts_impact'].cumsum().round(1)
    bear_df['gex_sign_label']    = bear_df['gex_raw'].apply(
        lambda x: '🟡 Negative (Gold)' if x < 0 else '🟣 Positive (Purple)')
    bear_df['role'] = bear_df.apply(
        lambda r: (r['vanna_note'] if r['vanna_note'] else
                   ('Accelerates fall 🔴' if r['gex_raw'] < 0 else 'Brakes fall 🟢')), axis=1)

    # ── Bull cascade: above spot, bottom→top ──────────────────────────────
    bull_df = df_c[df_c['strike'] > spot_price].copy().sort_values('strike', ascending=True)
    bull_df['cascade_direction'] = 'BULL'
    bull_df['cumulative_pts']    = bull_df['pts_impact'].cumsum().round(1)
    bull_df['gex_sign_label']    = bull_df['gex_raw'].apply(
        lambda x: '🟣 Positive (Purple)' if x > 0 else '🟡 Negative (Gold)')
    bull_df['role'] = bull_df.apply(
        lambda r: (r['vanna_note'] if r['vanna_note'] else
                   ('Accelerates rise 🔴' if r['gex_raw'] < 0 else 'Brakes rise 🟢')), axis=1)

    result = pd.concat([bear_df, bull_df], ignore_index=True)
    result['pts_raw']        = result['pts_raw'].round(1)
    result['pts_impact']     = result['pts_impact'].round(1)
    result['cumulative_pts'] = result['cumulative_pts'].round(1)
    result['gex_raw_disp']   = result['gex_raw'].apply(lambda x: f"{x:+.4f}{unit_label}")
    result['vanna_adj_pct']  = result['vanna_adj'].apply(
        lambda x: f"+{(x-1)*100:.0f}% 🔺" if x > 1.05 else
                  (f"−{(1-x)*100:.0f}% 🛡️" if x < 0.95 else "—"))
    return result


def create_enhanced_oi_gex_only_chart(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> go.Figure:
    """Standalone Enhanced OI GEX chart — purple/gold bars only, with spot line, flip zones, volume overlay.
    Uses pre-computed enhanced_oi_gex column if available (from compute_enhanced_oi_gex_column),
    otherwise computes it on the fly.
    """
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    for col in ['net_gex','call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df_sorted.columns: df_sorted[col] = 0.0
        df_sorted[col] = df_sorted[col].fillna(0)

    # Use pre-computed column if present and populated, else compute now
    if 'enhanced_oi_gex' not in df_sorted.columns or df_sorted['enhanced_oi_gex'].abs().sum() == 0:
        df_sorted = compute_enhanced_oi_gex_column(df_sorted, spot_price, unit_label)
    else:
        df_sorted['enhanced_oi_gex'] = df_sorted['enhanced_oi_gex'].fillna(0)

    max_enh   = df_sorted['enhanced_oi_gex'].abs().max() or 1
    flip_zones = identify_gamma_flip_zones(df_sorted, spot_price)
    fig = go.Figure()

    # Enhanced OI GEX bars
    enh_colors = ['#8b5cf6' if x > 0 else '#f59e0b' for x in df_sorted['enhanced_oi_gex']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['enhanced_oi_gex'], orientation='h',
        marker=dict(color=enh_colors, opacity=0.88, line=dict(color='white', width=1)),
        name=f'Enhanced OI GEX – Max: {max_enh:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Enhanced OI GEX: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    fig = _add_volume_overlay_horizontal(fig, df_sorted)

    # Spot line
    fig.add_hline(y=spot_price, line=dict(color='white', dash='dash', width=2),
                  annotation_text=f'Spot: {spot_price:,.2f}',
                  annotation_position='right',
                  annotation=dict(font=dict(color='white', size=11), bgcolor='rgba(0,0,0,0.7)'))

    # Flip zone lines
    for z in flip_zones:
        fig.add_hline(y=z['strike'], line=dict(color=z.get('color','#f59e0b'), dash='dot', width=1.5),
                      annotation_text=f"🔄 ₹{z['strike']:,.0f}",
                      annotation_position='left',
                      annotation=dict(font=dict(color=z.get('color','#f59e0b'), size=9), bgcolor='rgba(0,0,0,0.6)'))

    fig.update_layout(
        title=dict(
            text=(
                '<b>🚀 Enhanced OI GEX</b><br>'
                '<sub>Purple = Positive OI-weighted GEX | Gold = Negative | '
                f'🟩🟥 = Volume | Max: {max_enh:.4f}{unit_label}</sub>'
            ),
            font=dict(size=15, color='white'),
        ),
        xaxis_title=f'Enhanced OI GEX (₹ {unit_label})',
        yaxis_title='Strike Price',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=750,
        barmode='overlay',
        bargap=0.15,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=11),
                    bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1),
        hovermode='closest',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True,
                   zeroline=True, zerolinecolor='rgba(255,255,255,0.3)', zerolinewidth=2),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        margin=dict(l=80, r=160, t=110, b=80),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    return fig


def create_enhanced_oi_vanna_only_chart(
    df: pd.DataFrame, spot_price: float, unit_label: str = "B",
    df_full: pd.DataFrame = None, tte: float = 7/365,
    iv_df_override: pd.DataFrame = None,
) -> go.Figure:
    """Standalone Enhanced OI VANNA chart — pink/magenta bars only, with VANNA flip zones, spot line, volume overlay."""
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    for col in ['net_vanna','call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df_sorted.columns: df_sorted[col] = 0.0
        df_sorted[col] = df_sorted[col].fillna(0)

    df_sorted['enhanced_oi_vanna'] = 0.0
    bs_calc   = BlackScholesCalculator()
    total_vol = max(df_sorted['total_volume'].sum(), 1)
    sc = 1e9 if unit_label == 'B' else 1e7
    try:
        for idx, row in df_sorted.iterrows():
            spot_r = row.get('spot_price', spot_price); strike = row['strike']
            if spot_r <= 0 or strike <= 0: continue
            civ = row['call_iv']/100 if row['call_iv'] > 1 else row['call_iv']
            piv = row['put_iv'] /100 if row['put_iv']  > 1 else row['put_iv']
            cv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, civ)
            pv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, piv)
            vw  = 1 + (row['total_volume'] / total_vol)
            iv_adj = 1 + ((civ + piv) / 2 * 3)
            dw  = 1 / (1 + abs(strike - spot_r) / spot_r * 1.5)
            df_sorted.loc[idx, 'enhanced_oi_vanna'] = (
                (row['call_oi_change'] * cv * 2.0 * vw * iv_adj * dw * spot_r * 25) / sc +
                (row['put_oi_change']  * pv * 2.0 * vw * iv_adj * dw * spot_r * 25) / sc
            )
    except: pass

    vanna_flips = identify_vanna_flip_zones(df_sorted, spot_price)
    if iv_df_override is not None and len(iv_df_override) > 0:
        iv_df = iv_df_override
    else:
        iv_df = compute_iv_trend(df_full if df_full is not None else df)

    _liv      = iv_df.iloc[-1] if len(iv_df) > 0 else None
    iv_regime = str(_liv['iv_regime']) if _liv is not None and 'iv_regime' in _liv.index else 'FLAT'
    iv_skew   = float(_liv['iv_skew']) if _liv is not None and 'iv_skew'   in _liv.index else 0.0
    rc = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(iv_regime,'#94a3b8')

    max_enh_van = df_sorted['enhanced_oi_vanna'].abs().max() or 1
    fig = go.Figure()

    # Enhanced OI VANNA bars
    enh_col = ['#ec4899' if x >= 0 else '#be185d' for x in df_sorted['enhanced_oi_vanna']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['enhanced_oi_vanna'], orientation='h',
        marker=dict(color=enh_col, opacity=0.88, line=dict(color='white', width=1)),
        name=f'Enhanced OI VANNA – Max: {max_enh_van:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Enhanced OI VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    fig = _add_volume_overlay_horizontal(fig, df_sorted)

    # Spot line
    fig.add_hline(y=spot_price, line=dict(color='white', dash='dash', width=2),
                  annotation_text=f'Spot: {spot_price:,.2f}',
                  annotation_position='right',
                  annotation=dict(font=dict(color='white', size=11), bgcolor='rgba(0,0,0,0.7)'))

    # VANNA flip zone lines
    for z in vanna_flips:
        fig.add_hline(
            y=z['strike'], line=dict(color=z['color'], dash='dash', width=2.5),
            annotation_text=f"{z['icon']} ₹{z['strike']:,.0f} · "
            f"{'LOC' if z['role']=='VACUUM_ZONE' else z['role'].replace('_',' ')} [{iv_regime}]",
            annotation_position='right',
            annotation=dict(font=dict(color=z['color'], size=10, family='Arial Black'),
                            bgcolor='rgba(0,0,0,0.80)', bordercolor=z['color'], borderwidth=1.5),
        )

    fig.update_layout(
        title=dict(
            text=(
                f'<b>🌊 Enhanced OI VANNA</b><br>'
                f'<sub>Pink = Positive OI-weighted VANNA | Deep Pink = Negative | '
                f'🟩🟥 = Volume | IV: <b style="color:{rc}">{iv_regime}</b> | Skew: {iv_skew:+.1f}% | '
                f'Max: {max_enh_van:.4f}{unit_label}</sub>'
            ),
            font=dict(size=15, color='white'),
        ),
        xaxis_title=f'Enhanced OI VANNA [{unit_label}]',
        yaxis_title='Strike Price',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=780,
        barmode='overlay',
        bargap=0.15,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=11),
                    bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1),
        hovermode='closest',
        xaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True,
                   zeroline=True, zerolinecolor='rgba(255,255,255,0.3)', zerolinewidth=2),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        margin=dict(l=80, r=220, t=110, b=80),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    return fig

def create_enhanced_vanna_overlay_chart(
    df: pd.DataFrame,
    spot_price: float,
    unit_label: str = "B",
    df_full: pd.DataFrame = None,
    tte: float = 7/365,
    iv_df_override: pd.DataFrame = None,
) -> Tuple[go.Figure, pd.DataFrame, pd.DataFrame]:
    """
    Enhanced VANNA Overlay — preserves the EXACT original chart appearance:
      • Cyan/teal bars = Original VANNA
      • Pink/magenta bars = Enhanced OI VANNA
      • Green/red volume overlay on left axis (separate x-axis like original)
      • White dashed spot line
      • GEX flip zone dotted lines (original behavior)
    ADDED (as overlays on the same chart, not a separate column):
      • VANNA flip zone dashed lines — colour-coded by role, with icon+label annotations
      • Shaded bands at each flip zone
    Returns (fig, prob_df, iv_df)  — prob_df and iv_df used by the tab for the section below the chart.
    """
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    for col in ['net_vanna','call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df_sorted.columns: df_sorted[col] = 0.0
        df_sorted[col] = df_sorted[col].fillna(0)

    # ── Enhanced OI VANNA (same formula as original) ──────────────────────
    df_sorted['enhanced_oi_vanna'] = 0.0
    bs_calc   = BlackScholesCalculator()
    total_vol = max(df_sorted['total_volume'].sum(), 1)
    sc = 1e9 if unit_label == 'B' else 1e7
    cs = 25
    try:
        for idx, row in df_sorted.iterrows():
            spot_r = row.get('spot_price', spot_price)
            strike = row['strike']
            if spot_r <= 0 or strike <= 0: continue
            civ = row['call_iv']/100 if row['call_iv'] > 1 else row['call_iv']
            piv = row['put_iv'] /100 if row['put_iv']  > 1 else row['put_iv']
            cv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, civ)
            pv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, piv)
            vw  = 1 + (row['total_volume'] / total_vol)
            iv_adj = 1 + ((civ + piv) / 2 * 3)
            dw  = 1 / (1 + abs(strike - spot_r) / spot_r * 1.5)
            df_sorted.loc[idx, 'enhanced_oi_vanna'] = (
                (row['call_oi_change'] * cv * 2.0 * vw * iv_adj * dw * spot_r * cs) / sc +
                (row['put_oi_change']  * pv * 2.0 * vw * iv_adj * dw * spot_r * cs) / sc
            )
    except: pass

    # ── Flip zones & probability ──────────────────────────────────────────
    gex_flips   = identify_gamma_flip_zones(df_sorted, spot_price)
    vanna_flips = identify_vanna_flip_zones(df_sorted, spot_price)
    # Use caller-supplied iv_df (pre-sliced to selected timestamp) if available
    if iv_df_override is not None and len(iv_df_override) > 0:
        iv_df = iv_df_override
    else:
        iv_df = compute_iv_trend(df_full if df_full is not None else df)
    prob_df     = compute_breakout_probability(vanna_flips, iv_df, spot_price, tte)

    max_vanna   = df_sorted['net_vanna'].abs().max() or 1
    max_enh_van = df_sorted['enhanced_oi_vanna'].abs().max() or 1

    _liv      = iv_df.iloc[-1] if len(iv_df) > 0 else None
    iv_regime = str(_liv['iv_regime'])  if _liv is not None and 'iv_regime' in _liv.index else 'FLAT'
    iv_skew   = float(_liv['iv_skew'])  if _liv is not None and 'iv_skew'   in _liv.index else 0.0

    # ── SINGLE go.Figure — identical to original chart construction ───────
    fig = go.Figure()

    # Original VANNA (cyan/teal)
    orig_col = ['#06b6d4' if x >= 0 else '#0891b2' for x in df_sorted['net_vanna']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['net_vanna'],
        orientation='h',
        marker=dict(color=orig_col, opacity=0.6, line=dict(width=0)),
        name=f'Original VANNA – Max: {max_vanna:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Original VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    # Enhanced OI VANNA (pink/magenta)
    enh_col = ['#ec4899' if x >= 0 else '#be185d' for x in df_sorted['enhanced_oi_vanna']]
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['enhanced_oi_vanna'],
        orientation='h',
        marker=dict(color=enh_col, opacity=0.85, line=dict(color='white', width=1)),
        name=f'Enhanced OI VANNA – Max: {max_enh_van:.4f}{unit_label}',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Enhanced OI VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ))

    # Volume overlay (original _add_volume_overlay_horizontal behaviour)
    fig = _add_volume_overlay_horizontal(fig, df_sorted)

    # Spot line (identical to original)
    fig.add_hline(
        y=spot_price, line_dash='dash', line_color='white', line_width=3,
        annotation_text=f'Spot: {spot_price:,.2f}',
        annotation_position='top right',
        annotation=dict(font=dict(size=12, color='white', family='Arial Black')),
    )
    fig.add_vline(x=0, line_dash='dot', line_color='gray', line_width=2)

    # GEX flip zones (identical to original — subtle dotted lines on left)
    for zone in gex_flips:
        fig.add_hline(
            y=zone['strike'], line_dash='dot',
            line_color=zone['color'], line_width=1, opacity=0.3,
            annotation_text=f"🔄 {zone['strike']:,.0f}",
            annotation_position='left',
            annotation=dict(font=dict(size=9, color=zone['color']),
                            bgcolor='rgba(0,0,0,0.5)',
                            bordercolor=zone['color'], borderwidth=1),
        )

    # ── VANNA flip zones — all zones, side-aware annotations ─────────────
    # above-spot zones (Vacuum, Resistance) → annotate on RIGHT side
    # below-spot zones (Trap Door, Support Floor) → annotate on LEFT side
    # This prevents stacking and ensures all four zone types are visible
    for z in vanna_flips:  # no cap — show ALL zones
        ann_pos = 'right' if z['above_spot'] else 'left'
        # Shaded band between the two bounding strikes
        fig.add_hrect(
            y0=z['lower_strike'], y1=z['upper_strike'],
            fillcolor=z['color'], opacity=0.10, line_width=0,
        )
        # Dashed line at the interpolated flip strike
        fig.add_hline(
            y=z['strike'],
            line_dash='dash', line_color=z['color'], line_width=2.5,
            annotation_text=f"{z['icon']} ₹{z['strike']:,.0f} · "
            f"{'LOC' if z['role']=='VACUUM_ZONE' else z['role'].replace('_',' ')} [{iv_regime}]",
            annotation_position=ann_pos,
            annotation=dict(
                font=dict(color=z['color'], size=10, family='Arial Black'),
                bgcolor='rgba(0,0,0,0.85)',
                bordercolor=z['color'], borderwidth=1.5,
            ),
        )

    # ── Layout — preserved exactly from original ───────────────────────────
    rc = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(iv_regime,'#94a3b8')
    fig.update_layout(
        title=dict(
            text=(
                f'<b>🌊 Enhanced VANNA Overlay: Original vs Enhanced OI VANNA</b><br>'
                f'<sub>Cyan/Teal = All effects | Pink/Magenta = OI Δ with Vol+IV+Distance+VANNA | '
                f'🟩🟥 = Volume | ✏️ toolbar to draw | '
                f'⚡ VANNA Flip: 🔴 Resistance · 🚀 Vacuum · ⚠️ Trap Door · 🛡️ Support | '
                f'IV: <b style="color:{rc}">{iv_regime}</b> | Skew: {iv_skew:+.1f}%</sub>'
            ),
            font=dict(size=15, color='white'),
        ),
        xaxis_title=f'VANNA (dDelta/dVol) [{unit_label}]',
        yaxis_title='Strike Price',
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=780,
        barmode='overlay',
        bargap=0.15,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='white', size=11),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1,
        ),
        hovermode='closest',
        xaxis=dict(
            gridcolor='rgba(128,128,128,0.2)', showgrid=True,
            zeroline=True, zerolinecolor='rgba(255,255,255,0.3)', zerolinewidth=2,
        ),
        yaxis=dict(gridcolor='rgba(128,128,128,0.2)', showgrid=True, autorange=True),
        margin=dict(l=80, r=200, t=110, b=80),  # extra right margin for annotations
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    return fig, prob_df, iv_df


def create_standard_vanna_chart(df: pd.DataFrame, spot_price: float,
                                 unit_label: str = "B",
                                 iv_regime: str = "FLAT") -> go.Figure:
    """
    Standard VANNA chart (Call VANNA | Put VANNA side-by-side).
    Now includes all VANNA flip zone lines:
      🔴 Resistance Ceiling  🚀 Vacuum Zone
      ⚠️ Trap Door           🛡️ Support Floor
    Above-spot zones annotated on right, below-spot on left.
    """
    df_sorted = df.sort_values('strike').reset_index(drop=True)

    # Compute VANNA flip zones from net_vanna
    vanna_flips_std = identify_vanna_flip_zones(df_sorted, spot_price)

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('📈 Call VANNA', '📉 Put VANNA'),
        horizontal_spacing=0.12
    )

    # Call VANNA bars
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['call_vanna'], orientation='h',
        marker=dict(color=['#10b981' if x > 0 else '#ef4444' for x in df_sorted['call_vanna']]),
        name='Call VANNA',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Call VANNA: %{{x:.4f}}{unit_label}<extra></extra>'
    ), row=1, col=1)

    # Put VANNA bars
    fig.add_trace(go.Bar(
        y=df_sorted['strike'], x=df_sorted['put_vanna'], orientation='h',
        marker=dict(color=['#10b981' if x > 0 else '#ef4444' for x in df_sorted['put_vanna']]),
        name='Put VANNA',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Put VANNA: %{{x:.4f}}{unit_label}<extra></extra>'
    ), row=1, col=2)

    # Spot lines on both panels
    for col in [1, 2]:
        fig.add_hline(
            y=spot_price, line_dash='dash', line_color='white', line_width=2,
            annotation_text=f'Spot: {spot_price:,.2f}',
            annotation_position='top right',
            annotation=dict(font=dict(size=10, color='white', family='Arial Black')),
            row=1, col=col
        )

    # ── VANNA flip zone lines on BOTH panels ─────────────────────────────
    # above-spot zones → annotate right (col=2), below-spot → annotate left (col=1)
    # We draw on BOTH panels simultaneously (no row/col = applies to all)
    zone_colors = {
        'VACUUM_ZONE':         ('#10b981', '🚀', 'dash',  2.5),
        'RESISTANCE_CEILING':  ('#ef4444', '🔴', 'dash',  2.5),
        'TRAP_DOOR':           ('#f59e0b', '⚠️', 'dash',  2.5),
        'SUPPORT_FLOOR':       ('#06b6d4', '🛡️', 'dash',  2.5),
    }
    for z in vanna_flips_std:
        role   = z['role']
        zcolor, zicon, zdash, zwidth = zone_colors.get(
            role, ('#94a3b8', '📍', 'dot', 1.5))
        ann_pos = 'right' if z['above_spot'] else 'left'
        label   = (
                    f"{zicon} ₹{z['strike']:,.0f} · "
                    f"{'LOC' if role == 'VACUUM_ZONE' else role.replace('_',' ')} [{iv_regime}]"
                )

        # Shaded band — applied to both panels (no row/col)
        fig.add_hrect(
            y0=z['lower_strike'], y1=z['upper_strike'],
            fillcolor=zcolor, opacity=0.08, line_width=0,
        )

        # Draw on call VANNA panel (col=1) with annotation on appropriate side
        fig.add_hline(
            y=z['strike'],
            line_dash=zdash, line_color=zcolor, line_width=zwidth,
            annotation_text=label,
            annotation_position=ann_pos,
            annotation=dict(
                font=dict(color=zcolor, size=9, family='Arial Black'),
                bgcolor='rgba(0,0,0,0.85)',
                bordercolor=zcolor, borderwidth=1.2,
            ),
            row=1, col=1
        )
        # Draw on put VANNA panel (col=2) — line only, no duplicate annotation
        fig.add_hline(
            y=z['strike'],
            line_dash=zdash, line_color=zcolor, line_width=zwidth,
            row=1, col=2
        )

    iv_color = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(iv_regime,'#94a3b8')

    fig.update_layout(
        title=dict(
            text=(
                f'<b>🌊 VANNA Exposure (dDelta/dVol)</b><br>'
                f'<sub>✏️ toolbar to draw | '
                f'🔴 Resistance · 🚀 Vacuum · ⚠️ Trap Door · 🛡️ Support | '
                f'IV: <b style="color:{iv_color}">{iv_regime}</b></sub>'
            ),
            font=dict(size=16, color='white')
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=650,
        showlegend=False,
        hovermode='closest',
        margin=dict(l=80, r=150, t=110, b=80),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2))
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b')
    )
    fig.update_xaxes(
        title_text=f'VANNA (₹ {unit_label})',
        gridcolor='rgba(128,128,128,0.2)', showgrid=True
    )
    fig.update_yaxes(
        title_text='Strike Price',
        gridcolor='rgba(128,128,128,0.2)', showgrid=True
    )
    return fig



# ============================================================================
# VANNA INSTITUTIONAL SIGNAL ENGINE
# ============================================================================

def compute_vanna_institutional_signals(df: pd.DataFrame,
                                         spot_price: float,
                                         unit_label: str = "B") -> dict:
    """
    Computes three institutional activity scores from VANNA data:

    1. VANNA Acceleration  – rate of change of vanna per strike
       Signal: large players initiating/closing at a specific strike.

    2. VANNA Concentration Score  – top-3 strikes as % of total VANNA
       Signal: >60% = single block position (institutional)
                <40% = distributed/unwinding

    3. Call/Put VANNA Asymmetry – ratio of call_vanna / |put_vanna|
       Signal: >2.0  = dealers net-long vol on calls → upward price pressure
               <0.5  = dealers net-long vol on puts  → downward price pressure
               ~1.0  = balanced / hedged book

    Returns a dict with annotated DataFrames and scalar KPIs.
    """
    df_s = df.sort_values('strike').reset_index(drop=True).copy()

    # ── ensure required columns exist ────────────────────────────────────────
    for col in ['call_vanna','put_vanna','net_vanna','call_volume','put_volume',
                'total_volume','call_iv','put_iv']:
        if col not in df_s.columns:
            df_s[col] = 0.0
        df_s[col] = pd.to_numeric(df_s[col], errors='coerce').fillna(0)

    # ── 1. VANNA ACCELERATION ─────────────────────────────────────────────────
    # Rate of change along the strike axis (spatial derivative).
    # Large acceleration = dealer position wall at that strike.
    df_s['vanna_accel'] = df_s['net_vanna'].diff().fillna(0)
    df_s['vanna_accel_abs'] = df_s['vanna_accel'].abs()
    max_accel = df_s['vanna_accel_abs'].max() or 1
    df_s['vanna_accel_pct'] = df_s['vanna_accel_abs'] / max_accel * 100

    # Z-score of acceleration — marks statistically anomalous strikes
    accel_mean = df_s['vanna_accel_abs'].mean()
    accel_std  = df_s['vanna_accel_abs'].std() or 1
    df_s['vanna_accel_z'] = (df_s['vanna_accel_abs'] - accel_mean) / accel_std

    # Label each strike
    def _accel_label(z):
        if z > 3.0: return '🔴 EXTREME WALL'
        if z > 2.0: return '🟠 STRONG WALL'
        if z > 1.0: return '🟡 MODERATE WALL'
        return ''
    df_s['accel_label'] = df_s['vanna_accel_z'].apply(_accel_label)

    # ── 2. VANNA CONCENTRATION SCORE ─────────────────────────────────────────
    total_vanna_abs = df_s['net_vanna'].abs().sum() or 1
    top3_vanna_abs  = df_s['net_vanna'].abs().nlargest(3).sum()
    concentration   = top3_vanna_abs / total_vanna_abs * 100

    if concentration >= 60:
        conc_label = '🎯 CONCENTRATED — Institutional Block Detected'
        conc_color = '#ef4444'
        conc_signal = 'CONCENTRATED'
    elif concentration >= 45:
        conc_label = '⚠️ SEMI-CONCENTRATED — Watch for Block'
        conc_color = '#f59e0b'
        conc_signal = 'SEMI'
    elif concentration <= 30:
        conc_label = '📤 DISTRIBUTING — Position Unwinding'
        conc_color = '#06b6d4'
        conc_signal = 'DISTRIBUTING'
    else:
        conc_label = '🔵 DISPERSED — Normal Market Making'
        conc_color = '#8b5cf6'
        conc_signal = 'DISPERSED'

    # Mark top-3 strikes
    top3_strikes = df_s.nlargest(3, 'vanna_accel_abs')['strike'].values
    df_s['is_top3'] = df_s['strike'].isin(top3_strikes)

    # ── 3. CALL/PUT VANNA ASYMMETRY ───────────────────────────────────────────
    call_vanna_total = df_s['call_vanna'].sum()
    put_vanna_total  = df_s['put_vanna'].sum()
    asym_ratio = call_vanna_total / (abs(put_vanna_total) + 1e-9)

    # Per-strike asymmetry for bar overlay
    df_s['asym_ratio'] = df_s['call_vanna'] / (df_s['put_vanna'].abs() + 1e-9)
    df_s['asym_ratio'] = df_s['asym_ratio'].clip(-5, 5)   # cap for display

    if asym_ratio > 2.0:
        asym_label  = '📈 CALL-HEAVY: Dealers exposed to upside vol → upward price pressure likely'
        asym_color  = '#10b981'
        asym_signal = 'CALL_HEAVY'
    elif asym_ratio < 0.5:
        asym_label  = '📉 PUT-HEAVY: Dealers exposed to downside vol → downward price pressure likely'
        asym_color  = '#ef4444'
        asym_signal = 'PUT_HEAVY'
    else:
        asym_label  = '⚖️ BALANCED: Hedged book, no directional pressure from VANNA'
        asym_color  = '#8b5cf6'
        asym_signal = 'BALANCED'

    return {
        'df': df_s,
        'concentration': concentration,
        'conc_label': conc_label,
        'conc_color': conc_color,
        'conc_signal': conc_signal,
        'top3_strikes': top3_strikes,
        'call_vanna_total': call_vanna_total,
        'put_vanna_total': put_vanna_total,
        'asym_ratio': asym_ratio,
        'asym_label': asym_label,
        'asym_color': asym_color,
        'asym_signal': asym_signal,
    }


def create_vanna_institutional_chart(df: pd.DataFrame,
                                      spot_price: float,
                                      unit_label: str = "B") -> Tuple[go.Figure, dict]:
    """
    4-panel institutional VANNA chart:
      Row 1 – Net VANNA bars + VANNA Acceleration overlay (secondary x)
      Row 2 – VANNA Acceleration Z-score (strike-axis bar chart)
      Row 3 – Call vs Put VANNA side-by-side with Asymmetry ratio line
      Row 4 – Concentration heatmap: per-strike share of total VANNA
    """
    signals = compute_vanna_institutional_signals(df, spot_price, unit_label)
    df_s    = signals['df']

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=False,   # horizontal bars — strikes on y-axis
        subplot_titles=(
            '🌊 Net VANNA  +  Acceleration Overlay  (dealer position walls)',
            '⚡ VANNA Acceleration Z-Score  (anomalous = institutional wall)',
            '📊 Call vs Put VANNA  +  Asymmetry Ratio  (directional pressure)',
            '🎯 VANNA Concentration  (% of total per strike)',
        ),
        vertical_spacing=0.07,
        row_heights=[0.30, 0.22, 0.26, 0.22],
        specs=[
            [{"secondary_y": True}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
            [{"secondary_y": False}],
        ],
    )

    strikes = df_s['strike']

    # ── Row 1: Net VANNA bars + acceleration overlay ──────────────────────────
    vanna_colors = ['#06b6d4' if v > 0 else '#ec4899' for v in df_s['net_vanna']]
    fig.add_trace(go.Bar(
        y=strikes, x=df_s['net_vanna'], orientation='h',
        marker=dict(color=vanna_colors, opacity=0.85, line=dict(width=0)),
        name='Net VANNA',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Net VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ), row=1, col=1, secondary_y=False)

    # Acceleration as scatter on secondary x
    fig.add_trace(go.Scatter(
        y=strikes, x=df_s['vanna_accel_abs'],
        mode='lines+markers',
        line=dict(color='rgba(245,158,11,0.9)', width=2),
        marker=dict(size=df_s['vanna_accel_z'].clip(lower=0)*3+4,
                    color='rgba(245,158,11,0.85)',
                    line=dict(color='white', width=1)),
        name='|VANNA Acceleration|',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>|Accel|: %{{x:.4f}}{unit_label}<br>Z: %{{customdata:.1f}}σ<extra></extra>',
        customdata=df_s['vanna_accel_z'],
    ), row=1, col=1, secondary_y=True)

    # Spot line
    fig.add_hline(y=spot_price, line_dash='dash', line_color='white', line_width=2,
                  annotation_text=f'Spot ₹{spot_price:,.0f}',
                  annotation=dict(font=dict(color='white', size=10), bgcolor='rgba(0,0,0,0.6)'),
                  row=1, col=1)

    # Mark top-3 institutional walls
    for s in signals['top3_strikes']:
        fig.add_hline(y=s, line_dash='dot', line_color='#f59e0b', line_width=1.5,
                      annotation_text=f'⚡ Wall ₹{s:,.0f}',
                      annotation_position='right',
                      annotation=dict(font=dict(color='#f59e0b', size=9),
                                      bgcolor='rgba(0,0,0,0.7)', bordercolor='#f59e0b', borderwidth=1),
                      row=1, col=1)

    # ── Row 2: Acceleration Z-score bars ─────────────────────────────────────
    z_colors = ['#dc2626' if z > 3 else ('#f97316' if z > 2 else ('#f59e0b' if z > 1 else '#334155'))
                for z in df_s['vanna_accel_z']]
    fig.add_trace(go.Bar(
        y=strikes, x=df_s['vanna_accel_z'].clip(lower=0),
        orientation='h', marker=dict(color=z_colors, line=dict(width=0)),
        name='Acceleration Z-Score',
        hovertemplate='Strike: %{y:,.0f}<br>Accel Z: %{x:.2f}σ<br>%{customdata}<extra></extra>',
        customdata=df_s['accel_label'],
    ), row=2, col=1)

    # Threshold lines on row 2
    for level, color, label in [(1.0,'rgba(245,158,11,0.6)','1σ moderate'),
                                  (2.0,'rgba(249,115,22,0.7)','2σ strong'),
                                  (3.0,'rgba(220,38,38,0.8)','3σ extreme')]:
        fig.add_vline(x=level, line_dash='dash', line_color=color, line_width=1,
                      annotation_text=label,
                      annotation=dict(font=dict(color=color, size=8)),
                      row=2, col=1)

    fig.add_hline(y=spot_price, line_dash='dash', line_color='rgba(255,255,255,0.3)',
                  line_width=1, row=2, col=1)

    # ── Row 3: Call vs Put VANNA + Asymmetry line ────────────────────────────
    fig.add_trace(go.Bar(
        y=strikes, x=df_s['call_vanna'],
        orientation='h', name='Call VANNA',
        marker=dict(color='rgba(16,185,129,0.75)', line=dict(width=0)),
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Call VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ), row=3, col=1, secondary_y=False)

    fig.add_trace(go.Bar(
        y=strikes, x=df_s['put_vanna'],
        orientation='h', name='Put VANNA',
        marker=dict(color='rgba(239,68,68,0.75)', line=dict(width=0)),
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Put VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ), row=3, col=1, secondary_y=False)

    # Asymmetry ratio on secondary axis
    asym_color_per_bar = ['#10b981' if r > 2.0 else ('#ef4444' if r < 0.5 else '#8b5cf6')
                          for r in df_s['asym_ratio']]
    fig.add_trace(go.Scatter(
        y=strikes, x=df_s['asym_ratio'],
        mode='lines+markers',
        line=dict(color='rgba(255,255,255,0.7)', width=1.5, dash='dot'),
        marker=dict(size=5, color=asym_color_per_bar, line=dict(color='white', width=1)),
        name='Call/Put VANNA Ratio',
        hovertemplate='Strike: %{y:,.0f}<br>Asymmetry: %{x:.2f}x<extra></extra>',
    ), row=3, col=1, secondary_y=True)

    # Reference lines at 2.0 and 0.5 on secondary axis
    fig.add_hline(y=spot_price, line_dash='dash', line_color='rgba(255,255,255,0.3)',
                  line_width=1, row=3, col=1)

    # ── Row 4: Concentration heatmap (per-strike % of total VANNA) ────────────
    df_s['vanna_share_pct'] = df_s['net_vanna'].abs() / (total_vanna_abs := df_s['net_vanna'].abs().sum() or 1) * 100
    share_colors = ['#dc2626' if p > 20 else ('#f97316' if p > 10 else ('#f59e0b' if p > 5 else '#334155'))
                    for p in df_s['vanna_share_pct']]
    fig.add_trace(go.Bar(
        y=strikes, x=df_s['vanna_share_pct'],
        orientation='h', marker=dict(color=share_colors, line=dict(width=0)),
        name='VANNA Share %',
        hovertemplate='Strike: %{y:,.0f}<br>Share: %{x:.1f}%<extra></extra>',
    ), row=4, col=1)

    # Mark concentration threshold
    fig.add_vline(x=20, line_dash='dash', line_color='rgba(220,38,38,0.7)', line_width=1.5,
                  annotation_text='20% wall threshold',
                  annotation=dict(font=dict(color='rgba(220,38,38,0.8)', size=9)),
                  row=4, col=1)

    fig.add_hline(y=spot_price, line_dash='dash', line_color='rgba(255,255,255,0.3)',
                  line_width=1, row=4, col=1)

    # ── Global layout ─────────────────────────────────────────────────────────
    conc_pct = signals['concentration']
    asym     = signals['asym_ratio']
    fig.update_layout(
        title=dict(
            text=(
                f'<b>🏦 VANNA Institutional Activity Monitor</b><br>'
                f'<sub>'
                f'Concentration: {conc_pct:.1f}% → {signals["conc_label"]}  |  '
                f'Asymmetry: {asym:.2f}x → {signals["asym_label"]}'
                f'</sub>'
            ),
            font=dict(size=14, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=1200,
        barmode='overlay',
        hovermode='closest',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=80, r=100, t=130, b=60),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )

    # Axis labels
    fig.update_xaxes(title_text=f'Net VANNA ({unit_label})', gridcolor='rgba(128,128,128,0.15)', row=1, col=1)
    fig.update_xaxes(title_text='Accel Z-Score (σ)',         gridcolor='rgba(128,128,128,0.15)', row=2, col=1)
    fig.update_xaxes(title_text=f'VANNA ({unit_label})',     gridcolor='rgba(128,128,128,0.15)', row=3, col=1)
    fig.update_xaxes(title_text='VANNA Share (%)',           gridcolor='rgba(128,128,128,0.15)', row=4, col=1)
    for r in range(1, 5):
        fig.update_yaxes(title_text='Strike', gridcolor='rgba(128,128,128,0.15)',
                         autorange=True, row=r, col=1)
    fig.update_yaxes(title_text=f'|Accel| ({unit_label})', secondary_y=True, showgrid=False, row=1, col=1)
    fig.update_yaxes(title_text='Asym Ratio (x)',           secondary_y=True, showgrid=False, row=3, col=1)

    return fig, signals


def create_vanna_intraday_clock(df_full: pd.DataFrame,
                                 spot_price: float,
                                 unit_label: str = "B") -> go.Figure:
    """
    Intraday VANNA drift chart — shows how VANNA migrates across strikes
    through the trading session. This is the 'institutional clock'.

    3-row chart:
      Row 1 – VANNA centre-of-gravity (weighted mean strike) over time
               shows dealers rolling positions up/down
      Row 2 – Concentration score over time (% in top-3 strikes)
               spike = block position being initiated
      Row 3 – Call/Put VANNA asymmetry ratio over time
               >2.0 = upward pressure building, <0.5 = downward
    """
    # Aggregate by timestamp
    agg = {}
    for ts, grp in df_full.groupby('timestamp'):
        cv_sum  = grp['call_vanna'].sum()
        pv_sum  = grp['put_vanna'].sum()
        nv_abs  = grp['net_vanna'].abs()
        tot_abs = nv_abs.sum() or 1

        # centre of gravity: weighted mean strike by |net_vanna|
        cog = (grp['strike'] * nv_abs).sum() / tot_abs

        # concentration: top-3 share
        top3  = nv_abs.nlargest(3).sum()
        conc  = top3 / tot_abs * 100

        # asymmetry ratio
        asym  = cv_sum / (abs(pv_sum) + 1e-9)
        asym  = max(-5, min(5, asym))   # clip for display

        agg[ts] = {'cog': cog, 'concentration': conc, 'asym_ratio': asym,
                   'call_vanna': cv_sum, 'put_vanna': pv_sum,
                   'spot': grp['spot_price'].iloc[0]}

    if not agg:
        return go.Figure()

    clock_df = pd.DataFrame(agg).T.reset_index().rename(columns={'index':'timestamp'})
    clock_df = clock_df.sort_values('timestamp')
    ts = clock_df['timestamp']

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=(
            '🧲 VANNA Centre-of-Gravity  (weighted mean strike — shows position rolling)',
            '🎯 Concentration Score Over Time  (spike = block position initiated)',
            '⚖️ Call/Put VANNA Asymmetry Over Time  (>2.0 = upward pressure | <0.5 = downward)',
        ),
        vertical_spacing=0.08,
        row_heights=[0.38, 0.30, 0.32],
        specs=[[{"secondary_y": True}],
               [{"secondary_y": False}],
               [{"secondary_y": False}]],
    )

    # ── Row 1: CoG + spot price ───────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=ts, y=clock_df['spot'],
        mode='lines', name='Spot Price',
        line=dict(color='rgba(59,130,246,0.6)', width=1.5),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.05)',
        hovertemplate='%{x|%H:%M}<br>Spot: ₹%{y:,.2f}<extra></extra>',
    ), row=1, col=1, secondary_y=False)

    fig.add_trace(go.Scatter(
        x=ts, y=clock_df['cog'],
        mode='lines+markers', name='VANNA CoG (Gravity Strike)',
        line=dict(color='#f59e0b', width=2.5),
        marker=dict(size=6, color='#f59e0b', line=dict(color='white', width=1)),
        hovertemplate='%{x|%H:%M}<br>CoG Strike: ₹%{y:,.2f}<extra></extra>',
    ), row=1, col=1, secondary_y=True)

    # ── Row 2: Concentration score ────────────────────────────────────────────
    conc_colors = ['#dc2626' if c >= 60 else ('#f97316' if c >= 45 else ('#8b5cf6' if c <= 30 else '#334155'))
                   for c in clock_df['concentration']]
    fig.add_trace(go.Bar(
        x=ts, y=clock_df['concentration'],
        marker_color=conc_colors, name='Concentration %',
        hovertemplate='%{x|%H:%M}<br>Concentration: %{y:.1f}%<extra></extra>',
    ), row=2, col=1)

    for level, color, label in [
        (60, 'rgba(220,38,38,0.8)',  '60% — Institutional Block'),
        (45, 'rgba(249,115,22,0.6)', '45% — Semi-concentrated'),
        (30, 'rgba(6,182,212,0.5)',  '30% — Distributing'),
    ]:
        fig.add_hline(y=level, line_dash='dash', line_color=color, line_width=1.5,
                      annotation_text=label, annotation_position='right',
                      annotation=dict(font=dict(color=color, size=9)), row=2, col=1)

    # ── Row 3: Asymmetry ratio ────────────────────────────────────────────────
    asym_colors = ['#10b981' if r > 2.0 else ('#ef4444' if r < 0.5 else '#8b5cf6')
                   for r in clock_df['asym_ratio']]
    fig.add_trace(go.Scatter(
        x=ts, y=clock_df['asym_ratio'],
        mode='lines+markers', name='Asym Ratio',
        line=dict(color='rgba(255,255,255,0.5)', width=1.5),
        marker=dict(size=8, color=asym_colors, line=dict(color='white', width=1.5)),
        hovertemplate='%{x|%H:%M}<br>Asym: %{y:.2f}x<extra></extra>',
    ), row=3, col=1)

    # Fill zones
    fig.add_hrect(y0=2.0,  y1=5.0,  fillcolor='rgba(16,185,129,0.08)',  line_width=0, row=3, col=1)
    fig.add_hrect(y0=-5.0, y1=0.5,  fillcolor='rgba(239,68,68,0.08)',   line_width=0, row=3, col=1)
    for level, color, label in [
        (2.0,  'rgba(16,185,129,0.7)',  '2.0x — Call Heavy (↑ pressure)'),
        (1.0,  'rgba(139,92,246,0.4)',  '1.0x — Balanced'),
        (0.5,  'rgba(239,68,68,0.7)',   '0.5x — Put Heavy (↓ pressure)'),
    ]:
        fig.add_hline(y=level, line_dash='dash', line_color=color, line_width=1.5,
                      annotation_text=label, annotation_position='right',
                      annotation=dict(font=dict(color=color, size=9)), row=3, col=1)

    # ── Global layout ─────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                '<b>🕐 VANNA Institutional Clock — Intraday Position Drift</b><br>'
                '<sub>'
                '🧲 CoG rising with spot = dealers rolling up (trend day) | '
                'CoG flat despite spot move = reversion likely | '
                '🎯 Conc spike = block initiated | '
                '⚖️ Asym >2.0 = upward pressure | <0.5 = downward pressure'
                '</sub>'
            ),
            font=dict(size=14, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=900,
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=70, r=100, t=130, b=60),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    fig.update_xaxes(title_text='Time (IST)', gridcolor='rgba(128,128,128,0.15)', row=3, col=1)
    fig.update_yaxes(title_text='Spot (₹)',           secondary_y=False, gridcolor='rgba(128,128,128,0.15)', row=1, col=1)
    fig.update_yaxes(title_text='CoG Strike (₹)',     secondary_y=True,  showgrid=False, row=1, col=1)
    fig.update_yaxes(title_text='Concentration (%)',  gridcolor='rgba(128,128,128,0.15)', row=2, col=1)
    fig.update_yaxes(title_text='Asym Ratio (x)',     gridcolor='rgba(128,128,128,0.15)', row=3, col=1)

    return fig


# ============================================================================
# VANNA FLIP ZONE ENGINE + BREAKOUT PROBABILITY
# ============================================================================

def identify_vanna_flip_zones(df: pd.DataFrame, spot_price: float) -> List[Dict]:
    """
    Find strikes where cumulative net VANNA crosses zero.
    Returns list of flip zone dicts with direction, magnitude and zone type.

    Zone types:
      POS_TO_NEG  – positive VANNA above → negative below (trap door)
      NEG_TO_POS  – negative VANNA above → positive below (spring floor)

    Spot-relative role:
      flip above spot + POS_TO_NEG  → resistance ceiling (IV expansion = breakdown)
      flip above spot + NEG_TO_POS  → vacuum / acceleration zone (IV expansion = squeeze UP)
      flip below spot + POS_TO_NEG  → trap door  (IV expansion = acceleration DOWN)
      flip below spot + NEG_TO_POS  → support floor (IV compression = hold)
    """
    df_s = df.sort_values('strike').reset_index(drop=True)
    zones = []
    for i in range(len(df_s) - 1):
        cur_v  = df_s.iloc[i]['net_vanna']
        nxt_v  = df_s.iloc[i+1]['net_vanna']
        cur_k  = df_s.iloc[i]['strike']
        nxt_k  = df_s.iloc[i+1]['strike']
        if (cur_v > 0 and nxt_v < 0) or (cur_v < 0 and nxt_v > 0):
            # linear interpolation for exact flip level
            w         = abs(cur_v) / (abs(cur_v) + abs(nxt_v) + 1e-12)
            flip_k    = cur_k + (nxt_k - cur_k) * w
            magnitude = (abs(cur_v) + abs(nxt_v)) / 2
            flip_type = 'POS_TO_NEG' if cur_v > 0 else 'NEG_TO_POS'
            above_spot = flip_k > spot_price

            # Determine role
            if above_spot and flip_type == 'POS_TO_NEG':
                role = 'RESISTANCE_CEILING'
                role_desc = 'Resistance ceiling — IV ↑ = breakdown through here'
                color = '#ef4444'
                icon  = '🔴'
            elif above_spot and flip_type == 'NEG_TO_POS':
                role = 'VACUUM_ZONE'
                role_desc = 'LOC (Line of Control) — IV ↑ = rapid squeeze UP'
                color = '#10b981'
                icon  = '🚀'
            elif not above_spot and flip_type == 'POS_TO_NEG':
                role = 'TRAP_DOOR'
                role_desc = 'Trap door — IV ↑ = acceleration DOWN below this level'
                color = '#f59e0b'
                icon  = '⚠️'
            else:  # below spot, NEG_TO_POS
                role = 'SUPPORT_FLOOR'
                role_desc = 'Support floor — IV compression holds price up'
                color = '#06b6d4'
                icon  = '🛡️'

            zones.append({
                'strike'      : flip_k,
                'lower_strike': cur_k,
                'upper_strike': nxt_k,
                'lower_vanna' : cur_v,
                'upper_vanna' : nxt_v,
                'flip_type'   : flip_type,
                'role'        : role,
                'role_desc'   : role_desc,
                'magnitude'   : magnitude,
                'above_spot'  : above_spot,
                'color'       : color,
                'icon'        : icon,
                'distance_pct': abs(flip_k - spot_price) / spot_price * 100,
            })
    return sorted(zones, key=lambda z: abs(z['strike'] - spot_price))


def compute_iv_trend(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate call_iv and put_iv at ATM strike across timestamps.
    Returns a timeline DataFrame with IV trend and rate-of-change.
    ATM = strike closest to spot at each timestamp.
    """
    rows = []
    for ts, grp in df.sort_values('timestamp').groupby('timestamp'):
        spot   = grp['spot_price'].iloc[0]
        # find ATM row
        atm_idx = (grp['strike'] - spot).abs().idxmin()
        atm_row = grp.loc[atm_idx]
        call_iv = atm_row.get('call_iv', 15)
        put_iv  = atm_row.get('put_iv',  15)
        avg_iv  = (call_iv + put_iv) / 2
        # skew: call_iv - put_iv, positive = calls expensive (fear of rally)
        skew    = call_iv - put_iv
        rows.append({
            'timestamp': ts,
            'spot'     : spot,
            'call_iv'  : call_iv,
            'put_iv'   : put_iv,
            'avg_iv'   : avg_iv,
            'iv_skew'  : skew,
        })
    iv_df = pd.DataFrame(rows).sort_values('timestamp').reset_index(drop=True)
    if len(iv_df) > 1:
        iv_df['iv_change']     = iv_df['avg_iv'].diff().fillna(0)
        iv_df['iv_expanding']  = iv_df['iv_change'] > 0
        # rolling 3-bar IV slope
        iv_df['iv_slope']      = iv_df['avg_iv'].rolling(3, min_periods=1).apply(
            lambda x: (x.iloc[-1] - x.iloc[0]) / max(len(x)-1, 1), raw=False)
        iv_df['iv_regime']     = iv_df['iv_slope'].apply(
            lambda s: 'EXPANDING' if s > 0.1 else ('COMPRESSING' if s < -0.1 else 'FLAT'))
    else:
        iv_df['iv_change']    = 0.0
        iv_df['iv_expanding'] = False
        iv_df['iv_slope']     = 0.0
        iv_df['iv_regime']    = 'FLAT'
    return iv_df


def compute_breakout_probability(
    flip_zones: List[Dict],
    iv_df: pd.DataFrame,
    spot_price: float,
    tte: float = 7/365,
    df_selected: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Score each VANNA flip zone for DIRECTIONAL breakout probability.

    Per-zone scores (0-100):
      bull_score  – probability this zone drives a BULLISH move
      bear_score  – probability this zone drives a BEARISH move
      final_score – max(bull, bear) — overall activation probability
      direction   – BULLISH / BEARISH / CONFLICTED / NEUTRAL

    Zone × IV logic:
      LOC (VACUUM_ZONE) + IV EXPANDING   → strong BULLISH (dealers forced to BUY delta)
      LOC (VACUUM_ZONE) + IV COMPRESSING → weak BEARISH  (dealers sell delta, fade move)
      RESISTANCE_CEILING + IV EXPANDING  → strong BEARISH (dealers forced to SELL delta)
      RESISTANCE_CEILING + IV COMPRESSING→ weak BULLISH  (ceiling absorbed, grind up)
      TRAP_DOOR + IV EXPANDING           → strong BEARISH (drop accelerates below)
      TRAP_DOOR + IV COMPRESSING         → weak BULLISH  (floor recovers)
      SUPPORT_FLOOR + IV COMPRESSING     → strong BULLISH (dealers buy delta, floor holds)
      SUPPORT_FLOOR + IV EXPANDING       → BEARISH (paradox: floor breaks under vol)

    Session-level bias signals also returned in each row:
      vanna_balance  – net VANNA above spot vs below spot
      skew_bias      – call IV vs put IV tilt
      spot_zone_pos  – is spot above or below nearest flip zone
    """
    if not flip_zones or iv_df.empty:
        return pd.DataFrame()

    latest_iv   = iv_df.iloc[-1]
    iv_regime   = str(latest_iv['iv_regime']) if 'iv_regime' in latest_iv.index else 'FLAT'
    iv_skew     = float(latest_iv['iv_skew'])   if 'iv_skew'   in latest_iv.index else 0.0
    call_iv_cur = float(latest_iv['call_iv'])   if 'call_iv'   in latest_iv.index else 15.0
    put_iv_cur  = float(latest_iv['put_iv'])    if 'put_iv'    in latest_iv.index else 15.0
    max_mag     = max(z['magnitude'] for z in flip_zones) or 1

    # ── Session-level directional signals ────────────────────────────────
    # 1. VANNA balance: sum |VANNA| above vs below spot
    vanna_above = sum(z['magnitude'] for z in flip_zones if z['above_spot'])
    vanna_below = sum(z['magnitude'] for z in flip_zones if not z['above_spot'])
    total_mag   = vanna_above + vanna_below or 1
    # >50 means more sensitivity above → IV expansion pulls price UP more
    vanna_balance_pct = vanna_above / total_mag * 100   # >50 = bullish bias

    # 2. Skew bias: positive skew = calls expensive = institutional long delta
    # normalise to 0-100 (50 = neutral, >50 = bullish, <50 = bearish)
    skew_bias_pct = np.clip(50 + iv_skew * 4, 0, 100)

    # 3. IV regime bias: expanding IV + more VANNA above = bullish ignition
    #                    expanding IV + more VANNA below = bearish ignition
    if iv_regime == 'EXPANDING':
        iv_dir_bias = 'BULLISH' if vanna_above > vanna_below else 'BEARISH'
    elif iv_regime == 'COMPRESSING':
        iv_dir_bias = 'BEARISH' if vanna_above > vanna_below else 'BULLISH'
    else:
        iv_dir_bias = 'NEUTRAL'

    rows = []
    for z in flip_zones:
        dist_pct = z['distance_pct']
        role     = z['role']

        # ── Distance multiplier ────────────────────────────────────────────
        # ATM (dist≈0) → mult≈1.0  |  Far OTM (dist>3%) → mult→0
        # CRITICAL: dist is a MULTIPLIER on the IV signal, NOT an additive
        # term. The old additive approach added ~29pts equally to both bull
        # and bear, compressing the gap and causing BEARISH to read CONFLICTED.
        dist_mult = np.exp(-dist_pct / 1.5)           # 0.0 – 1.0

        # ── Magnitude & TTE multipliers ────────────────────────────────────
        mag_mult = min(1.0, z['magnitude'] / max_mag)  # 0.0 – 1.0
        tte_mult = min(1.0, 1.0 / (tte * 365 * 0.5 + 1))  # 0.0 – 1.0

        # ── Bull / Bear IV base scores — these SET the directional gap ─────
        # dist/mag/tte scale amplitude; they do NOT compress the gap.
        if role == 'VACUUM_ZONE':
            if iv_regime == 'EXPANDING':
                bull_iv, bear_iv = 90, 10
            elif iv_regime == 'FLAT':
                bull_iv, bear_iv = 35, 65   # ceiling, bear lean
            else:  # COMPRESSING
                bull_iv, bear_iv = 15, 85   # dealers selling hard into zone

        elif role == 'RESISTANCE_CEILING':
            if iv_regime == 'EXPANDING':
                bull_iv, bear_iv = 10, 90
            elif iv_regime == 'FLAT':
                bull_iv, bear_iv = 35, 65
            else:  # COMPRESSING
                bull_iv, bear_iv = 65, 35   # ceiling absorbed, grind up

        elif role == 'TRAP_DOOR':
            if iv_regime == 'EXPANDING':
                bull_iv, bear_iv = 5,  95
            elif iv_regime == 'FLAT':
                bull_iv, bear_iv = 30, 70
            else:  # COMPRESSING
                bull_iv, bear_iv = 70, 30   # floor recovers

        else:  # SUPPORT_FLOOR
            if iv_regime == 'COMPRESSING':
                bull_iv, bear_iv = 90, 10
            elif iv_regime == 'FLAT':
                bull_iv, bear_iv = 60, 40
            else:  # EXPANDING
                bull_iv, bear_iv = 15, 85   # floor breaks

        # ── Skew alignment bonus (±15 pts) ────────────────────────────────
        skew_bull_bonus = np.clip(iv_skew * 3, -15, 15)
        skew_bear_bonus = np.clip(-iv_skew * 3, -15, 15)

        # ── VANNA balance bonus (±10 pts) ─────────────────────────────────
        if z['above_spot']:
            vb_bull = np.clip((vanna_balance_pct - 50) * 0.6, -10, 10)
            vb_bear = -vb_bull
        else:
            vb_bear = np.clip((50 - vanna_balance_pct) * 0.6, -10, 10)
            vb_bull = -vb_bear

        # ── Combine: IV signal × (dist × mag) amplitude + tte + bonuses ───
        # Gap between bull_iv and bear_iv is preserved through multiplication.
        amplitude  = dist_mult * mag_mult
        bull_score = np.clip(bull_iv * amplitude + tte_mult * 5 + skew_bull_bonus + vb_bull, 0, 100)
        bear_score = np.clip(bear_iv * amplitude + tte_mult * 5 + skew_bear_bonus + vb_bear, 0, 100)

        final_score = max(bull_score, bear_score)

        # ── Direction: adaptive threshold ─────────────────────────────────
        # ATM zones need smaller gap (15pt) — signal is very clear.
        # Far OTM zones need bigger gap (25pt) — uncertainty is higher.
        dir_threshold = 15 + dist_pct * 10   # 15 at ATM → 25 at 1% distance
        diff = bull_score - bear_score
        if   diff >  dir_threshold: direction = 'BULLISH'
        elif diff < -dir_threshold: direction = 'BEARISH'
        elif final_score >= 25:     direction = 'CONFLICTED'
        else:                       direction = 'NEUTRAL'

        dir_color = {'BULLISH':'#10b981','BEARISH':'#ef4444',
                     'CONFLICTED':'#f59e0b','NEUTRAL':'#64748b'}[direction]
        dir_icon  = {'BULLISH':'🟢','BEARISH':'🔴',
                     'CONFLICTED':'⚡','NEUTRAL':'⬜'}[direction]

        if final_score >= 70:   signal = '🔥 HIGH'
        elif final_score >= 50: signal = '⚡ MOD'
        elif final_score >= 30: signal = '👁️ WATCH'
        else:                   signal = '💤 LOW'

        rows.append({
            'strike'           : z['strike'],
            'role'             : role,
            'role_desc'        : z['role_desc'],
            'icon'             : z['icon'],
            'color'            : z['color'],
            'distance_pct'     : dist_pct,
            'flip_type'        : z['flip_type'],
            'magnitude'        : z['magnitude'],
            'above_spot'       : z['above_spot'],
            'bull_score'       : bull_score,
            'bear_score'       : bear_score,
            'final_score'      : final_score,
            'direction'        : direction,
            'dir_color'        : dir_color,
            'dir_icon'         : dir_icon,
            'signal'           : signal,
            'iv_regime'        : iv_regime,
            'iv_skew'          : iv_skew,
            'vanna_balance_pct': vanna_balance_pct,
            'skew_bias_pct'    : skew_bias_pct,
            'iv_dir_bias'      : iv_dir_bias,
        })

    return pd.DataFrame(rows).sort_values('final_score', ascending=False).reset_index(drop=True)


def compute_session_bias(
    flip_zones: List[Dict],
    iv_df: pd.DataFrame,
    df_selected: pd.DataFrame,
    spot_price: float,
) -> Dict:
    """
    Compute a single session-level BULLISH / BEARISH score (0-100 each).

    Combines four independent signals:
      1. VANNA zone balance    — more activation potential above vs below spot
      2. IV skew               — call IV vs put IV premium
      3. Net VANNA above/below — raw dealer exposure tilt
      4. IV regime direction   — is vol expanding toward bullish or bearish zones

    Returns dict with bull_pct, bear_pct, bias, confidence, explanation lines.
    """
    if not flip_zones or iv_df.empty:
        return {'bull_pct':50,'bear_pct':50,'bias':'NEUTRAL',
                'confidence':'LOW','lines':[],'iv_regime':'FLAT','iv_skew':0}

    latest_iv = iv_df.iloc[-1]
    iv_regime = str(latest_iv['iv_regime']) if 'iv_regime' in latest_iv.index else 'FLAT'
    iv_skew   = float(latest_iv['iv_skew']) if 'iv_skew'   in latest_iv.index else 0.0

    signals   = {}
    lines     = []

    # ── Signal 1: VANNA balance (which side has more flip magnitude) ──────
    v_above = sum(z['magnitude'] for z in flip_zones if z['above_spot'])
    v_below = sum(z['magnitude'] for z in flip_zones if not z['above_spot'])
    total_v = v_above + v_below or 1
    v_pct   = v_above / total_v * 100   # >50 = more VANNA above
    # More VANNA above + expanding IV = dealers buy delta = bullish
    # More VANNA below + expanding IV = dealers sell delta = bearish
    if iv_regime == 'EXPANDING':
        # More VANNA above + expanding IV = dealers forced to buy delta above = bullish
        sig1_bull = v_pct
        sig1_bear = 100 - v_pct
    elif iv_regime == 'COMPRESSING':
        # More VANNA above + compressing IV = dealers selling into rallies = bearish
        sig1_bull = 100 - v_pct
        sig1_bear = v_pct
    else:
        # FLAT IV: VANNA above still creates resistance (dealers sell small into rallies)
        # Not fully reversed but bear-leaning when v_pct > 50
        # v_pct=70 (70% above) → sig1_bull=40, sig1_bear=60
        sig1_bull = np.clip(50 - (v_pct - 50) * 0.4, 0, 100)
        sig1_bear = 100 - sig1_bull

    signals['vanna_balance'] = (sig1_bull, sig1_bear)
    dir1 = '🟢 Bullish' if sig1_bull > sig1_bear + 10 else ('🔴 Bearish' if sig1_bear > sig1_bull + 10 else '⚖️ Neutral')
    lines.append(f"VANNA Balance: {v_pct:.0f}% above spot | IV {iv_regime} → {dir1}")

    # ── Signal 2: IV Skew ─────────────────────────────────────────────────
    # Positive skew: calls pricier → institutional buying upside → bullish
    skew_bull = np.clip(50 + iv_skew * 5, 0, 100)
    skew_bear = 100 - skew_bull
    signals['skew'] = (skew_bull, skew_bear)
    dir2 = '🟢 Call heavy' if iv_skew > 1 else ('🔴 Put heavy' if iv_skew < -1 else '⚖️ Neutral')
    lines.append(f"IV Skew: {iv_skew:+.1f}% (CE-PE) → {dir2}")

    # ── Signal 3: Net VANNA above vs below — IV-regime-aware ────────────
    # CRITICAL: direction interpretation FLIPS based on IV regime.
    #
    # Positive VANNA above spot means:
    #   IV EXPANDING  → dealers MUST BUY delta above → squeeze UP → BULLISH
    #   IV COMPRESSING→ dealers SELL delta into rallies → cap/resistance → BEARISH
    #   IV FLAT       → dealers mildly selling into rallies (resistance lean) → SLIGHTLY BEARISH
    #
    # Positive VANNA below spot means:
    #   IV EXPANDING  → dealers MUST SELL delta below → accelerate DOWN → BEARISH
    #   IV COMPRESSING→ dealers BUY delta on dips → support → BULLISH
    net_above = 0.0; net_below = 0.0
    if df_selected is not None and 'net_vanna' in df_selected.columns:
        net_above = df_selected[df_selected['strike'] > spot_price]['net_vanna'].sum()
        net_below = df_selected[df_selected['strike'] < spot_price]['net_vanna'].sum()
    total_net = abs(net_above) + abs(net_below) or 1
    above_pct = net_above / total_net   # +1 = all above, -1 = all below

    if iv_regime == 'EXPANDING':
        # VANNA above + expanding = forced dealer buying above = bullish
        nv_bull = np.clip(50 + above_pct * 50, 0, 100)
    elif iv_regime == 'COMPRESSING':
        # VANNA above + compressing = dealers selling rallies = bearish
        nv_bull = np.clip(50 - above_pct * 50, 0, 100)
    else:  # FLAT — slight resistance lean when VANNA concentrated above
        # above_pct > 0 means more VANNA above → slight bear lean (capping effect)
        nv_bull = np.clip(50 - above_pct * 25, 0, 100)
    nv_bear = 100 - nv_bull

    signals['net_vanna'] = (nv_bull, nv_bear)
    if iv_regime == 'EXPANDING':
        dir3 = '🟢 Bullish' if net_above > 0 else '🔴 Bearish'
    elif iv_regime == 'COMPRESSING':
        dir3 = '🔴 Bearish (VANNA caps rally)' if net_above > 0 else '🟢 Bullish (VANNA supports dip)'
    else:
        dir3 = '⚖️ Slight bear lean (VANNA above = resistance)' if net_above > 0 else '⚖️ Slight bull lean'
    lines.append(f"Net VANNA: above={net_above:.2f} below={net_below:.2f} | IV {iv_regime} → {dir3}")

    # ── Signal 4: Zone role count — IV-regime-adjusted ───────────────────
    # Zone roles are only as valid as the IV regime confirms them.
    # LOC = bullish ONLY if IV is expanding (squeeze fuel)
    #             = bearish (ceiling) if IV is flat or compressing
    # RESISTANCE_CEILING = bearish if IV expanding, weakly bullish if compressing
    # TRAP_DOOR = bearish always (worst when IV expands)
    # SUPPORT_FLOOR = bullish if IV compressing, bearish if IV expanding
    bull_score_r = 0.0
    bear_score_r = 0.0
    for z in flip_zones:
        r = z['role']
        if r == 'VACUUM_ZONE':
            if iv_regime == 'EXPANDING':
                bull_score_r += 1.0
            elif iv_regime == 'FLAT':
                bear_score_r += 0.5   # ceiling effect
            else:  # COMPRESSING
                bear_score_r += 1.0
        elif r == 'RESISTANCE_CEILING':
            if iv_regime == 'EXPANDING':
                bear_score_r += 1.0
            elif iv_regime == 'FLAT':
                bear_score_r += 0.6
            else:  # COMPRESSING
                bull_score_r += 0.3   # weakly absorbed
        elif r == 'TRAP_DOOR':
            if iv_regime == 'EXPANDING':
                bear_score_r += 1.0
            elif iv_regime == 'FLAT':
                bear_score_r += 0.7
            else:  # COMPRESSING
                bull_score_r += 0.4   # bounce likely
        else:  # SUPPORT_FLOOR
            if iv_regime == 'COMPRESSING':
                bull_score_r += 1.0
            elif iv_regime == 'FLAT':
                bull_score_r += 0.5
            else:  # EXPANDING
                bear_score_r += 0.8   # floor at risk

    tot_r = bull_score_r + bear_score_r or 1
    role_bull = bull_score_r / tot_r * 100
    role_bear = bear_score_r / tot_r * 100
    signals['zone_roles'] = (role_bull, role_bear)
    dir4 = '🟢 Bullish zones confirmed by IV' if role_bull > role_bear + 10         else ('🔴 Bearish zones confirmed by IV' if role_bear > role_bull + 10 else '⚖️ Mixed')
    n_bull_raw = sum(1 for z in flip_zones if z['role'] in ('VACUUM_ZONE','SUPPORT_FLOOR'))
    n_bear_raw = sum(1 for z in flip_zones if z['role'] in ('RESISTANCE_CEILING','TRAP_DOOR'))
    lines.append(f"Zone Roles: {n_bull_raw} structural bull / {n_bear_raw} structural bear | IV-adj → {dir4}")

    # ── Weighted aggregate ────────────────────────────────────────────────
    weights = {'vanna_balance':0.35, 'skew':0.25, 'net_vanna':0.25, 'zone_roles':0.15}
    bull_final = sum(weights[k] * signals[k][0] for k in weights)
    bear_final = sum(weights[k] * signals[k][1] for k in weights)

    # Normalise to sum to 100
    total = bull_final + bear_final or 1
    bull_pct = round(bull_final / total * 100, 1)
    bear_pct = round(bear_final / total * 100, 1)

    diff = bull_pct - bear_pct
    if   diff >  20: bias = 'BULLISH'
    elif diff < -20: bias = 'BEARISH'
    else:            bias = 'CONFLICTED'

    if   abs(diff) >= 30: confidence = 'HIGH'
    elif abs(diff) >= 15: confidence = 'MODERATE'
    else:                 confidence = 'LOW'

    return {
        'bull_pct'  : bull_pct,
        'bear_pct'  : bear_pct,
        'bias'      : bias,
        'confidence': confidence,
        'lines'     : lines,
        'iv_regime' : iv_regime,
        'iv_skew'   : iv_skew,
        'vanna_balance_pct': v_above / total_v * 100,
        'net_vanna_above': net_above,
        'net_vanna_below': net_below,
    }


def create_vanna_flip_breakout_chart(
    df_selected: pd.DataFrame,
    df_full: pd.DataFrame,
    spot_price: float,
    unit_label: str = "B",
    tte: float = 7/365,
) -> Tuple[go.Figure, pd.DataFrame, pd.DataFrame]:
    """
    5-row VANNA Flip & Breakout Probability chart:
      Row 1 — VANNA profile (strike axis) with flip zones annotated
      Row 2 — Spot price intraday with flip zone horizontal bands
      Row 3 — ATM IV trend: call IV, put IV, skew
      Row 4 — Breakout probability score per flip zone (horizontal bar)
      Row 5 — IV regime timeline (EXPANDING / COMPRESSING / FLAT)

    Returns (fig, flip_zones_df, iv_df)
    """
    df_s     = df_selected.sort_values('strike').reset_index(drop=True)
    iv_df    = compute_iv_trend(df_full)
    flip_zones = identify_vanna_flip_zones(df_s, spot_price)
    prob_df    = compute_breakout_probability(flip_zones, iv_df, spot_price, tte)

    # ── Row 1 & Row 4 are different axes — use make_subplots with mixed
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=False,                 # Row 1 uses strike axis; rows 2-5 use time axis
        subplot_titles=(
            f'VANNA Profile (Strike Axis) + Flip Zones',
            'Spot Price Intraday with VANNA Flip Levels',
            'ATM Implied Volatility Trend (Call IV / Put IV / Skew)',
            'Breakout Probability Score per Flip Zone',
            'IV Regime Timeline (EXPANDING → Vol-driven moves likely)',
        ),
        vertical_spacing=0.06,
        row_heights=[0.28, 0.16, 0.18, 0.20, 0.18],
        specs=[
            [{"secondary_y": False}],
            [{"secondary_y": False}],
            [{"secondary_y": True}],
            [{"secondary_y": False}],
            [{"secondary_y": False}],
        ],
    )

    # ── Row 1: VANNA profile horizontal bars ─────────────────────────────────
    vanna_colors = ['#06b6d4' if v >= 0 else '#f59e0b' for v in df_s['net_vanna']]
    fig.add_trace(go.Bar(
        y=df_s['strike'], x=df_s['net_vanna'],
        orientation='h',
        marker=dict(color=vanna_colors, opacity=0.8, line=dict(color='rgba(255,255,255,0.1)', width=0.5)),
        name='Net VANNA',
        hovertemplate=f'Strike: %{{y:,.0f}}<br>Net VANNA: %{{x:.4f}}{unit_label}<extra></extra>',
    ), row=1, col=1)

    # Spot line on VANNA chart
    fig.add_hline(y=spot_price, line_dash='dash', line_color='white', line_width=2.5,
                  annotation_text=f'Spot ₹{spot_price:,.0f}',
                  annotation=dict(font=dict(color='white', size=11, family='Arial Black'),
                                  bgcolor='rgba(0,0,0,0.7)'),
                  annotation_position='right', row=1, col=1)
    fig.add_vline(x=0, line_dash='dot', line_color='rgba(255,255,255,0.3)', line_width=1.5, row=1, col=1)

    # Annotate flip zones on VANNA chart
    for z in flip_zones[:8]:    # max 8 to avoid clutter
        fig.add_hline(
            y=z['strike'], line_dash='dot', line_color=z['color'], line_width=2.5,
            annotation_text=f"{z['icon']} {z['strike']:,.0f} ({z['role'].replace('_',' ')})",
            annotation_position='left',
            annotation=dict(font=dict(color=z['color'], size=9),
                            bgcolor='rgba(0,0,0,0.75)', bordercolor=z['color'], borderwidth=1),
            row=1, col=1,
        )
        fig.add_hrect(
            y0=z['lower_strike'], y1=z['upper_strike'],
            fillcolor=z['color'], opacity=0.07, line_width=0, row=1, col=1,
        )

    # ── Row 2: Spot price intraday ────────────────────────────────────────────
    ts = iv_df['timestamp']
    fig.add_trace(go.Scatter(
        x=ts, y=iv_df['spot'],
        mode='lines', line=dict(color='#3b82f6', width=2),
        fill='tozeroy', fillcolor='rgba(59,130,246,0.06)',
        name='Spot Price',
        hovertemplate='%{x|%H:%M}<br>₹%{y:,.2f}<extra></extra>',
    ), row=2, col=1)

    # Flip zone horizontal lines on spot chart
    for z in flip_zones[:8]:
        fig.add_hline(
            y=z['strike'], line_dash='dot', line_color=z['color'], line_width=1.8,
            annotation_text=f"{z['icon']} {z['strike']:,.0f}",
            annotation_position='right',
            annotation=dict(font=dict(color=z['color'], size=9),
                            bgcolor='rgba(0,0,0,0.6)', bordercolor=z['color'], borderwidth=1),
            row=2, col=1,
        )

    # ── Row 3: ATM IV trend ───────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=ts, y=iv_df['call_iv'],
        mode='lines', line=dict(color='#10b981', width=2),
        name='Call IV (%)',
        hovertemplate='%{x|%H:%M}<br>Call IV: %{y:.1f}%<extra></extra>',
    ), row=3, col=1, secondary_y=False)

    fig.add_trace(go.Scatter(
        x=ts, y=iv_df['put_iv'],
        mode='lines', line=dict(color='#ef4444', width=2),
        name='Put IV (%)',
        hovertemplate='%{x|%H:%M}<br>Put IV: %{y:.1f}%<extra></extra>',
    ), row=3, col=1, secondary_y=False)

    # IV skew on secondary y
    skew_colors = ['#10b981' if s > 0 else '#ef4444' for s in iv_df['iv_skew']]
    fig.add_trace(go.Bar(
        x=ts, y=iv_df['iv_skew'],
        marker=dict(color=skew_colors, opacity=0.5),
        name='IV Skew (Call−Put)',
        hovertemplate='%{x|%H:%M}<br>Skew: %{y:+.1f}%<extra></extra>',
        yaxis='y6',
    ), row=3, col=1, secondary_y=True)

    fig.add_hline(y=0, line_dash='dot', line_color='rgba(255,255,255,0.2)', line_width=1, row=3, col=1)

    # ── Row 4: Breakout probability horizontal bars ───────────────────────────
    if not prob_df.empty:
        bar_colors = [r['color'] for _, r in prob_df.iterrows()]
        bar_labels = [f"{r['icon']} ₹{r['strike']:,.0f}" for _, r in prob_df.iterrows()]
        fig.add_trace(go.Bar(
            y=bar_labels,
            x=prob_df['final_score'],
            orientation='h',
            marker=dict(
                color=bar_colors,
                opacity=0.85,
                line=dict(color='white', width=1),
            ),
            text=[f"{r['signal']}  {r['final_score']:.0f}%" for _, r in prob_df.iterrows()],
            textposition='inside',
            textfont=dict(color='white', size=10, family='JetBrains Mono'),
            name='Breakout Prob Score',
            customdata=prob_df[['role_desc','iv_regime','distance_pct','magnitude']].values,
            hovertemplate=(
                'Strike: %{y}<br>'
                'Score: %{x:.1f}%<br>'
                'Role: %{customdata[0]}<br>'
                'IV Regime: %{customdata[1]}<br>'
                'Distance: %{customdata[2]:.2f}%<br>'
                'VANNA Mag: %{customdata[3]:.4f}<extra></extra>'
            ),
        ), row=4, col=1)

        # threshold lines on prob chart
        for level, color, label in [
            (70, 'rgba(239,68,68,0.8)',   '70% HIGH PROB'),
            (50, 'rgba(245,158,11,0.6)',  '50% MODERATE'),
            (30, 'rgba(100,116,139,0.5)', '30% WATCH'),
        ]:
            fig.add_vline(x=level, line_dash='dash', line_color=color, line_width=1.5,
                          annotation_text=label, annotation_position='top',
                          annotation=dict(font=dict(color=color, size=9)), row=4, col=1)
    else:
        fig.add_annotation(text="No VANNA flip zones detected in current strike range",
                           xref="paper", yref="paper", x=0.5, y=0.5,
                           showarrow=False, font=dict(color="#94a3b8", size=13), row=4, col=1)

    # ── Row 5: IV regime timeline ─────────────────────────────────────────────
    regime_color_map = {'EXPANDING': '#ef4444', 'COMPRESSING': '#10b981', 'FLAT': '#64748b'}
    regime_y_map     = {'EXPANDING': 2, 'COMPRESSING': -2, 'FLAT': 0}

    if 'iv_regime' in iv_df.columns:
        r_colors = [regime_color_map.get(r, '#64748b') for r in iv_df['iv_regime']]
        r_y      = [regime_y_map.get(r, 0)            for r in iv_df['iv_regime']]
        fig.add_trace(go.Bar(
            x=ts, y=r_y,
            marker=dict(color=r_colors, opacity=0.75, line=dict(width=0)),
            name='IV Regime',
            text=iv_df['iv_regime'],
            textposition='inside',
            textfont=dict(color='white', size=9),
            hovertemplate='%{x|%H:%M}<br>Regime: %{text}<br>IV Δ: %{customdata:.2f}%<extra></extra>',
            customdata=iv_df['iv_change'],
        ), row=5, col=1)

        fig.add_trace(go.Scatter(
            x=ts, y=iv_df['iv_slope'],
            mode='lines', line=dict(color='#f59e0b', width=2),
            name='IV Slope (3-bar)',
            hovertemplate='%{x|%H:%M}<br>Slope: %{y:+.2f}%<extra></extra>',
        ), row=5, col=1)

        fig.add_hline(y=0.1,  line_dash='dash', line_color='rgba(239,68,68,0.5)',  line_width=1, row=5, col=1)
        fig.add_hline(y=-0.1, line_dash='dash', line_color='rgba(16,185,129,0.5)', line_width=1, row=5, col=1)
        fig.add_hline(y=0,    line_dash='dot',  line_color='rgba(255,255,255,0.2)', line_width=1, row=5, col=1)

    # ── Layout ───────────────────────────────────────────────────────────────
    latest_regime = iv_df['iv_regime'].iloc[-1] if len(iv_df) > 0 else 'FLAT'
    latest_skew   = iv_df['iv_skew'].iloc[-1]   if len(iv_df) > 0 else 0
    skew_dir      = 'calls expensive (upward lean)' if latest_skew > 0 else 'puts expensive (downward lean)'

    fig.update_layout(
        title=dict(
            text=(
                f'<b>⚡ VANNA Flip Zones & Breakout Probability</b><br>'
                f'<sub>'
                f'🔴 Resistance Ceiling = IV↑ drives breakdown | '
                f'🚀 Vacuum Zone = IV↑ drives squeeze UP | '
                f'⚠️ Trap Door = IV↑ accelerates DOWN | '
                f'🛡️ Support Floor = IV↓ holds price<br>'
                f'Current IV Regime: <b>{latest_regime}</b> | '
                f'IV Skew: {latest_skew:+.1f}% ({skew_dir})'
                f'</sub>'
            ),
            font=dict(size=14, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=1220,
        barmode='overlay',
        hovermode='closest',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.8)', bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        margin=dict(l=80, r=140, t=140, b=60),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )

    # axis labels
    fig.update_xaxes(title_text=f'Net VANNA (₹{unit_label})', row=1, col=1, gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text='Strike Price (₹)',            row=1, col=1, gridcolor='rgba(128,128,128,0.15)', autorange=True)
    fig.update_xaxes(title_text='Time (IST)', gridcolor='rgba(128,128,128,0.15)', row=2, col=1)
    fig.update_yaxes(title_text='Spot (₹)',   row=2, col=1, gridcolor='rgba(128,128,128,0.15)')
    fig.update_xaxes(title_text='Time (IST)', gridcolor='rgba(128,128,128,0.15)', row=3, col=1)
    fig.update_yaxes(title_text='IV (%)',     row=3, col=1, secondary_y=False, gridcolor='rgba(128,128,128,0.15)')
    fig.update_yaxes(title_text='Skew (%)',   row=3, col=1, secondary_y=True, showgrid=False)
    fig.update_xaxes(title_text='Probability Score (%)', gridcolor='rgba(128,128,128,0.15)', row=4, col=1, range=[0,100])
    fig.update_yaxes(title_text='Flip Zone',  row=4, col=1, gridcolor='rgba(128,128,128,0.15)', autorange=True)
    fig.update_xaxes(title_text='Time (IST)', gridcolor='rgba(128,128,128,0.15)', row=5, col=1)
    fig.update_yaxes(title_text='IV Slope / Regime', row=5, col=1, gridcolor='rgba(128,128,128,0.15)')

    return fig, prob_df, iv_df

def detect_vacuum_breakout(
    df: pd.DataFrame,
    tte: float = 7/365,
) -> pd.DataFrame:
    """
    Scans every timestamp to detect when spot price BREAKS and HOLDS above
    a VACUUM ZONE (NEG_TO_POS flip above spot).

    Breakout states per timestamp:
      NO_ZONE       — no LOC found at this bar
      BELOW         — spot below LOC (normal state)
      ATTEMPTED     — spot first crossed above zone this bar (1 bar only so far)
      CONFIRMED     — spot held above zone for ≥2 consecutive bars
      FALSE         — spot crossed back below after attempted breakout
      EXTENDED      — confirmed + IV regime turned EXPANDING (maximum conviction)

    Returns DataFrame with columns:
      timestamp, spot, vacuum_strike, state, state_color, bull_override,
      bull_pct_override, bear_pct_override, label, hover
    """
    all_ts = sorted(df['timestamp'].unique())
    iv_full = compute_iv_trend(df)

    rows_out = []
    prev_state         = 'NO_ZONE'
    attempt_bar        = None   # index when ATTEMPTED started
    last_vacuum_strike = None   # tracks last known LOC strike

    for idx, ts in enumerate(all_ts):
        df_ts    = df[df['timestamp'] == ts].copy()
        if df_ts.empty: continue
        spot_ts  = float(df_ts['spot_price'].iloc[0])
        iv_slice = iv_full[iv_full['timestamp'] <= ts]
        if iv_slice.empty: iv_slice = iv_full.iloc[:1]

        zones        = identify_vanna_flip_zones(df_ts, spot_ts)
        vacuum_zones = [z for z in zones if z['role'] == 'VACUUM_ZONE']

        if not vacuum_zones:
            # No LOC visible at this bar.
            # If spot has moved ABOVE the last known zone → zone was absorbed by price.
            if prev_state in ('CONFIRMED', 'EXTENDED'):
                iv_row = iv_slice.iloc[-1]
                iv_reg = str(iv_row['iv_regime']) if 'iv_regime' in iv_row.index else 'FLAT'
                state  = 'EXTENDED' if iv_reg == 'EXPANDING' else 'CONFIRMED'
            elif prev_state == 'BELOW' and last_vacuum_strike is not None and spot_ts > last_vacuum_strike:
                state = 'ATTEMPTED'   # spot jumped through zone in single bar
                attempt_bar = idx
            elif prev_state == 'ATTEMPTED' and last_vacuum_strike is not None and spot_ts > last_vacuum_strike:
                state = 'CONFIRMED'   # held above — zone absorbed = confirmed
            else:
                state = 'NO_ZONE'
            vacuum_strike = last_vacuum_strike   # carry last known for display
        else:
            # Take nearest LOC
            vz = min(vacuum_zones, key=lambda z: z['distance_pct'])
            vacuum_strike = vz['strike']
            last_vacuum_strike = vacuum_strike   # update tracker
            above = spot_ts > vacuum_strike

            if not above:
                # Spot below zone
                if prev_state in ('ATTEMPTED', 'CONFIRMED', 'EXTENDED'):
                    state = 'FALSE'   # was above, now back below
                    attempt_bar = None
                else:
                    state = 'BELOW'
                    attempt_bar = None
            else:
                # Spot above zone
                if prev_state in ('BELOW', 'FALSE', 'NO_ZONE'):
                    state = 'ATTEMPTED'
                    attempt_bar = idx
                elif prev_state == 'ATTEMPTED':
                    state = 'CONFIRMED'
                elif prev_state in ('CONFIRMED', 'EXTENDED'):
                    iv_row = iv_slice.iloc[-1]
                    iv_reg = str(iv_row['iv_regime']) if 'iv_regime' in iv_row.index else 'FLAT'
                    state  = 'EXTENDED' if iv_reg == 'EXPANDING' else 'CONFIRMED'
                else:
                    state = 'ATTEMPTED'

        # ── Bull override scores based on state ──────────────────────────
        override_map = {
            'NO_ZONE'  : (None,  None,  False),
            'BELOW'    : (None,  None,  False),
            'ATTEMPTED': (72,    28,    True),   # tentative breakout
            'CONFIRMED': (85,    15,    True),   # confirmed — strong bull
            'FALSE'    : (None,  None,  False),  # no override — let normal signals work
            'EXTENDED' : (95,    5,     True),   # IV expanding above zone — maximum conviction
        }
        bull_ov, bear_ov, do_override = override_map.get(state, (None, None, False))

        state_colors = {
            'NO_ZONE'  : '#64748b',
            'BELOW'    : '#94a3b8',
            'ATTEMPTED': '#f59e0b',
            'CONFIRMED': '#10b981',
            'FALSE'    : '#ef4444',
            'EXTENDED' : '#06b6d4',
        }
        state_icons = {
            'NO_ZONE'  : '⬜',
            'BELOW'    : '⬇️',
            'ATTEMPTED': '⚡',
            'CONFIRMED': '🚀',
            'FALSE'    : '❌',
            'EXTENDED' : '🔥',
        }

        label = f"{state_icons.get(state,'')} {state}"
        hover = (
            f"{ts.strftime('%H:%M')} | Spot ₹{spot_ts:,.0f}<br>"
            f"Zone: {'₹' + f'{vacuum_strike:,.0f}' if vacuum_strike else 'none'}<br>"
            f"Breakout State: <b>{state}</b><br>"
            + (f"Bull Override: {bull_ov}% | Bear Override: {bear_ov}%" if do_override else "No override")
        )

        rows_out.append({
            'timestamp'        : ts,
            'spot'             : spot_ts,
            'vacuum_strike'    : vacuum_strike,
            'state'            : state,
            'state_color'      : state_colors.get(state, '#64748b'),
            'state_icon'       : state_icons.get(state, ''),
            'bull_override'    : do_override,
            'bull_pct_override': bull_ov,
            'bear_pct_override': bear_ov,
            'label'            : label,
            'hover'            : hover,
        })
        prev_state = state

    return pd.DataFrame(rows_out)


def create_bias_transition_chart(
    df: pd.DataFrame,
    spot_price: float,
    selected_ts,
    tte: float = 7/365,
) -> go.Figure:
    """
    Plots Bull% and Bear% (from compute_session_bias) across every timestamp
    in the session. Marks:
      🔄 CROSSOVER  — lines cross (Bull overtakes Bear or vice versa)
      ⚡ FLIP       — bias label changes (BULLISH→BEARISH or reverse)
      🔥 SURGE      — either line moves >10% in a single bar
      ▼  Selected   — vertical line at the currently-selected timestamp
    """
    all_ts = sorted(df['timestamp'].unique())
    if len(all_ts) < 2:
        fig = go.Figure()
        fig.update_layout(template='plotly_dark', height=300,
                          title='Not enough timestamps for transition chart')
        return fig

    iv_full = compute_iv_trend(df)

    # Detect vacuum zone breakout states across the full session
    bk_df = detect_vacuum_breakout(df, tte)
    bk_map = {}
    if not bk_df.empty:
        for _, row in bk_df.iterrows():
            bk_map[row['timestamp']] = row

    times, bulls, bears, regimes, skews, biases = [], [], [], [], [], []
    breakout_states = []   # parallel list for override info
    prev_bias = None

    for ts in all_ts:
        df_ts = df[df['timestamp'] == ts].copy()
        if df_ts.empty:
            continue
        spot_ts = float(df_ts['spot_price'].iloc[0])

        iv_slice = iv_full[iv_full['timestamp'] <= ts]
        if iv_slice.empty:
            iv_slice = iv_full.iloc[:1]

        zones  = identify_vanna_flip_zones(df_ts, spot_ts)
        # ── Primary signal: Flip Zone Directional Probability (top zone) ──
        # Use the highest-final_score zone's bull_score / bear_score as the
        # canonical bull/bear values — this is what the banner also shows.
        pz_df = compute_breakout_probability(zones, iv_slice, spot_ts, tte, df_ts)
        if not pz_df.empty:
            top_zone   = pz_df.iloc[0]   # already sorted by final_score desc
            bull_val   = float(top_zone['bull_score'])
            bear_val   = float(top_zone['bear_score'])
            diff_val   = bull_val - bear_val
            dir_thresh = 15 + float(top_zone['distance_pct']) * 10
            if   diff_val >  dir_thresh: bias_val = 'BULLISH'
            elif diff_val < -dir_thresh: bias_val = 'BEARISH'
            elif max(bull_val,bear_val) >= 25: bias_val = 'CONFLICTED'
            else:                        bias_val = 'NEUTRAL'
            iv_regime_val = str(top_zone['iv_regime'])
            iv_skew_val   = float(top_zone['iv_skew'])
        else:
            # Fallback to session bias when no flip zones exist
            bd = compute_session_bias(zones, iv_slice, df_ts, spot_ts)
            bull_val      = bd['bull_pct']
            bear_val      = bd['bear_pct']
            bias_val      = bd['bias']
            iv_regime_val = bd['iv_regime']
            iv_skew_val   = bd['iv_skew']

        # Apply breakout override if active at this timestamp
        bk = bk_map.get(ts)
        if bk is not None and bk['bull_override']:
            bull_val = float(bk['bull_pct_override'])
            bear_val = float(bk['bear_pct_override'])
            bias_val = 'BULLISH'

        times.append(ts)
        bulls.append(bull_val)
        bears.append(bear_val)
        regimes.append(iv_regime_val)
        skews.append(iv_skew_val)
        biases.append(bias_val)
        breakout_states.append(bk['state'] if bk is not None else 'NO_ZONE')

    if not times:
        fig = go.Figure()
        fig.update_layout(template='plotly_dark', height=300)
        return fig

    times_str = [t.strftime('%H:%M') for t in times]

    # ── Detect transition events ─────────────────────────────────────────
    # ── Significant event detection (filtered) ──────────────────────────
    # Rules designed to keep <5 events per chart:
    #   CROSSOVER: lines must cross AND gap must be ≥8% before & after,
    #              AND a minimum of 3 bars cooldown from last crossover
    #   FLIP:      bias label changes BULLISH↔BEARISH (CONFLICTED doesn't count),
    #              AND the new bias is held for ≥2 bars (not a one-bar flicker)
    #   SURGE:     single-bar move ≥15% on either line, NOT immediately reversed
    #              (next bar move is < half the surge size)
    MIN_GAP_BARS   = 3    # minimum bars between same-type events
    MIN_CROSS_DIFF = 8.0  # lines must diverge by ≥8% to qualify as meaningful cross
    SURGE_THRESH   = 15.0 # minimum single-bar move to qualify as surge

    crossovers, flips, surges = [], [], []
    last_cross = -MIN_GAP_BARS

    for i in range(1, len(times)):
        prev_b, curr_b = bulls[i-1], bulls[i]
        prev_r, curr_r = bears[i-1], bears[i]

        # CROSSOVER — must actually cross AND diverge meaningfully after
        prev_bull_lead = prev_b > prev_r
        curr_bull_lead = curr_b > curr_r
        gap_after = abs(curr_b - curr_r)
        if (prev_bull_lead != curr_bull_lead
                and gap_after >= MIN_CROSS_DIFF
                and (i - last_cross) >= MIN_GAP_BARS):
            crossovers.append(i)
            last_cross = i

        # FLIP — BULLISH↔BEARISH only (skip CONFLICTED), held ≥2 bars
        is_directional_flip = (
            biases[i] in ('BULLISH', 'BEARISH')
            and biases[i-1] in ('BEARISH', 'BULLISH')
            and biases[i] != biases[i-1]
        )
        if is_directional_flip:
            # Check it holds for ≥2 bars
            held = (i + 1 < len(biases) and biases[i+1] == biases[i])
            if held:
                flips.append(i)

        # SURGE — ≥15% move NOT immediately reversed
        bull_move = abs(curr_b - prev_b)
        bear_move = abs(curr_r - prev_r)
        max_move  = max(bull_move, bear_move)
        if max_move >= SURGE_THRESH:
            # not immediately reversed
            if i + 1 < len(times):
                next_bull_move = abs(bulls[i+1] - curr_b) if i+1 < len(bulls) else 0
                if next_bull_move < max_move * 0.5:   # reversal < half surge
                    surges.append(i)
            else:
                surges.append(i)

    fig = go.Figure()

    # ── Bull% line ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=times_str, y=bulls,
        mode='lines',
        name='🟢 Bull%',
        line=dict(color='#10b981', width=2.5),
        fill='tozeroy',
        fillcolor='rgba(16,185,129,0.07)',
        hovertemplate='%{x}<br>🟢 Bull: <b>%{y:.1f}%</b><extra></extra>',
    ))

    # ── Bear% line ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=times_str, y=bears,
        mode='lines',
        name='🔴 Bear%',
        line=dict(color='#ef4444', width=2.5),
        fill='tozeroy',
        fillcolor='rgba(239,68,68,0.07)',
        hovertemplate='%{x}<br>🔴 Bear: <b>%{y:.1f}%</b><extra></extra>',
    ))

    # ── 50% neutral reference ─────────────────────────────────────────────
    fig.add_hline(
        y=50, line_dash='dot', line_color='rgba(148,163,184,0.35)', line_width=1.5,
        annotation_text='50% neutral',
        annotation=dict(font=dict(color='#64748b', size=9)),
        annotation_position='right',
    )

    # ── CROSSOVER markers — single consolidated trace ─────────────────────
    # Bull-cross and Bear-cross as two separate traces (different colours)
    bull_cross_x, bull_cross_y, bull_cross_txt = [], [], []
    bear_cross_x, bear_cross_y, bear_cross_txt = [], [], []
    for i in crossovers:
        mid_y = (bulls[i] + bears[i]) / 2
        if bulls[i] > bears[i]:
            bull_cross_x.append(times_str[i])
            bull_cross_y.append(mid_y)
            bull_cross_txt.append(f'🟢 CROSS<br>Bull {bulls[i]:.0f}% overtakes')
        else:
            bear_cross_x.append(times_str[i])
            bear_cross_y.append(mid_y)
            bear_cross_txt.append(f'🔴 CROSS<br>Bear {bears[i]:.0f}% overtakes')

    if bull_cross_x:
        fig.add_trace(go.Scatter(
            x=bull_cross_x, y=bull_cross_y,
            mode='markers+text',
            marker=dict(symbol='star', size=18, color='#10b981',
                        line=dict(color='white', width=1.5)),
            text=['BULL CROSS'] * len(bull_cross_x),
            textposition='top center',
            textfont=dict(color='#10b981', size=9, family='JetBrains Mono'),
            name='🟢 Bull Cross',
            hovertemplate='%{x}<br>%{customdata}<extra></extra>',
            customdata=bull_cross_txt,
        ))
    if bear_cross_x:
        fig.add_trace(go.Scatter(
            x=bear_cross_x, y=bear_cross_y,
            mode='markers+text',
            marker=dict(symbol='star', size=18, color='#ef4444',
                        line=dict(color='white', width=1.5)),
            text=['BEAR CROSS'] * len(bear_cross_x),
            textposition='top center',
            textfont=dict(color='#ef4444', size=9, family='JetBrains Mono'),
            name='🔴 Bear Cross',
            hovertemplate='%{x}<br>%{customdata}<extra></extra>',
            customdata=bear_cross_txt,
        ))

    # ── FLIP markers — single consolidated trace ──────────────────────────
    bull_flip_x, bull_flip_y = [], []
    bear_flip_x, bear_flip_y = [], []
    bull_flip_txt, bear_flip_txt = [], []
    for i in flips:
        if biases[i] == 'BULLISH':
            bull_flip_x.append(times_str[i])
            bull_flip_y.append(bulls[i] + 3)
            bull_flip_txt.append(f'⚡ BULL FLIP<br>{bears[i-1]:.0f}%→{bulls[i]:.0f}% Bull')
        else:
            bear_flip_x.append(times_str[i])
            bear_flip_y.append(bears[i] + 3)
            bear_flip_txt.append(f'⚡ BEAR FLIP<br>{bulls[i-1]:.0f}%→{bears[i]:.0f}% Bear')

    if bull_flip_x:
        fig.add_trace(go.Scatter(
            x=bull_flip_x, y=bull_flip_y,
            mode='markers+text',
            marker=dict(symbol='triangle-up', size=15, color='#10b981',
                        line=dict(color='white', width=1.5)),
            text=['⚡ BULL FLIP'] * len(bull_flip_x),
            textposition='top center',
            textfont=dict(color='#10b981', size=9, family='JetBrains Mono'),
            name='⚡ Bull Flip',
            hovertemplate='%{x}<br>%{customdata}<extra></extra>',
            customdata=bull_flip_txt,
        ))
    if bear_flip_x:
        fig.add_trace(go.Scatter(
            x=bear_flip_x, y=bear_flip_y,
            mode='markers+text',
            marker=dict(symbol='triangle-down', size=15, color='#ef4444',
                        line=dict(color='white', width=1.5)),
            text=['⚡ BEAR FLIP'] * len(bear_flip_x),
            textposition='bottom center',
            textfont=dict(color='#ef4444', size=9, family='JetBrains Mono'),
            name='⚡ Bear Flip',
            hovertemplate='%{x}<br>%{customdata}<extra></extra>',
            customdata=bear_flip_txt,
        ))

    # ── SURGE markers — single consolidated trace ─────────────────────────
    surge_x, surge_y, surge_txt = [], [], []
    for i in surges:
        bull_move = abs(bulls[i] - bulls[i-1])
        bear_move = abs(bears[i] - bears[i-1])
        is_bull_surge = bull_move >= bear_move
        surge_x.append(times_str[i])
        surge_y.append(bulls[i] if is_bull_surge else bears[i])
        surge_txt.append(
            f'🔥 {"BULL" if is_bull_surge else "BEAR"} SURGE<br>'
            f'{("+" if bulls[i]>bulls[i-1] else "")}{bulls[i]-bulls[i-1]:.0f}% Bull  '
            f'{("+" if bears[i]>bears[i-1] else "")}{bears[i]-bears[i-1]:.0f}% Bear'
        )
    if surge_x:
        fig.add_trace(go.Scatter(
            x=surge_x, y=surge_y,
            mode='markers',
            marker=dict(symbol='diamond', size=13, color='#f59e0b',
                        line=dict(color='white', width=1.5)),
            name='🔥 Surge (≥15%)',
            hovertemplate='%{x}<br>%{customdata}<extra></extra>',
            customdata=surge_txt,
        ))

    # ── Shaded background via fillcolor on the scatter fills above ───────
    # (already done via fill='tozeroy' on bull/bear lines — no vrect needed)

    # ── Selected timestamp vertical line ──────────────────────────────────
    sel_str = selected_ts.strftime('%H:%M')
    if sel_str in times_str:
        sel_idx   = times_str.index(sel_str)
        sel_bull  = bulls[sel_idx]
        sel_bear  = bears[sel_idx]
        sel_bias  = biases[sel_idx]
        sel_color = '#10b981' if sel_bias=='BULLISH' else ('#ef4444' if sel_bias=='BEARISH' else '#f59e0b')
        # add_vline fails on categorical x-axis — use add_shape + scatter annotation
        fig.add_shape(
            type='line', xref='x', yref='paper',
            x0=sel_str, x1=sel_str, y0=0, y1=1,
            line=dict(color=sel_color, width=2.5, dash='dash'),
        )
        fig.add_trace(go.Scatter(
            x=[sel_str], y=[102],
            mode='text',
            text=[f'▼ NOW  🟢{sel_bull:.0f}% 🔴{sel_bear:.0f}%'],
            textfont=dict(color=sel_color, size=11, family='Arial Black'),
            textposition='bottom center',
            showlegend=False,
            hoverinfo='skip',
        ))

    # ── VACUUM ZONE BREAKOUT markers ─────────────────────────────────────
    # Three distinct event types: ATTEMPTED (⚡ amber), CONFIRMED (🚀 green), EXTENDED (🔥 cyan)
    # FALSE (❌ red)
    bk_events = {
        'ATTEMPTED': {'x':[], 'y':[], 'txt':[], 'color':'#f59e0b', 'symbol':'triangle-up',    'size':16, 'name':'⚡ Breakout Attempt'},
        'CONFIRMED': {'x':[], 'y':[], 'txt':[], 'color':'#10b981', 'symbol':'star',            'size':22, 'name':'🚀 Breakout Confirmed'},
        'EXTENDED' : {'x':[], 'y':[], 'txt':[], 'color':'#06b6d4', 'symbol':'star',            'size':24, 'name':'🔥 Breakout Extended (IV↑)'},
        'FALSE'    : {'x':[], 'y':[], 'txt':[], 'color':'#ef4444', 'symbol':'x',               'size':14, 'name':'❌ False Breakout'},
    }

    # Add green shaded background from first CONFIRMED bar onward
    confirmed_start = None
    false_end       = None
    for i, (ts_s, state) in enumerate(zip(times_str, breakout_states)):
        if state == 'CONFIRMED' and confirmed_start is None:
            confirmed_start = ts_s
        if state == 'FALSE' and confirmed_start is not None:
            false_end = ts_s
            break

    if confirmed_start is not None:
        end_ts = false_end if false_end else times_str[-1]
        fig.add_shape(
            type='rect', xref='x', yref='paper',
            x0=confirmed_start, x1=end_ts, y0=0, y1=1,
            fillcolor='rgba(16,185,129,0.06)',
            line=dict(color='rgba(16,185,129,0.3)', width=1, dash='dot'),
        )
        fig.add_annotation(
            x=confirmed_start, y=98, xref='x', yref='y',
            text='🚀 BREAKOUT ZONE',
            showarrow=False,
            font=dict(color='#10b981', size=9, family='JetBrains Mono'),
            xanchor='left', bgcolor='rgba(16,185,129,0.15)',
            bordercolor='rgba(16,185,129,0.4)', borderwidth=1,
        )

    # Plot each event state
    for i, (ts_s, state) in enumerate(zip(times_str, breakout_states)):
        if state not in bk_events: continue
        bucket = bk_events[state]
        y_val  = bulls[i] + 4 if state in ('CONFIRMED','EXTENDED','ATTEMPTED') else bears[i] + 4
        bucket['x'].append(ts_s)
        bucket['y'].append(y_val)
        # Get hover from bk_map
        ts_obj = times[i]
        bk_row = bk_map.get(ts_obj)
        bucket['txt'].append(bk_row['hover'] if bk_row is not None else state)

    for state_key, bdata in bk_events.items():
        if not bdata['x']: continue
        show_text = state_key in ('CONFIRMED', 'EXTENDED', 'FALSE')
        fig.add_trace(go.Scatter(
            x=bdata['x'], y=bdata['y'],
            mode='markers+text' if show_text else 'markers',
            marker=dict(symbol=bdata['symbol'], size=bdata['size'],
                        color=bdata['color'], line=dict(color='white', width=1.5)),
            text=[bdata['name'].split(' ',1)[1] if show_text else ''] * len(bdata['x']),
            textposition='top center',
            textfont=dict(color=bdata['color'], size=9, family='JetBrains Mono'),
            name=bdata['name'],
            hovertemplate='%{customdata}<extra></extra>',
            customdata=bdata['txt'],
        ))

    # ── IV Regime as coloured scatter dots along the bottom ─────────────────
    regime_colors = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}
    regime_vals   = [2] * len(times_str)   # fixed y near bottom
    reg_colors    = [regime_colors.get(r, '#64748b') for r in regimes]
    fig.add_trace(go.Scatter(
        x=times_str, y=regime_vals,
        mode='markers',
        marker=dict(color=reg_colors, size=8, symbol='square'),
        name='IV Regime',
        hovertemplate='%{x}<br>IV: %{text}<extra></extra>',
        text=regimes,
        showlegend=True,
    ))

    # ── Summary stats for title ───────────────────────────────────────────
    n_cross = len(crossovers)
    n_flip  = len(flips)
    n_surge = len(surges)
    final_b = bulls[-1]; final_r = bears[-1]
    final_bias_label = biases[-1]
    fb_color = '#10b981' if final_bias_label=='BULLISH' else ('#ef4444' if final_bias_label=='BEARISH' else '#f59e0b')

    # Breakout status summary for title
    bk_states_list = list(breakout_states)
    n_confirmed = bk_states_list.count('CONFIRMED') + bk_states_list.count('EXTENDED')
    n_false     = bk_states_list.count('FALSE')
    bk_status   = ''
    if n_confirmed > 0 and n_false == 0:
        bk_status = f' | 🚀 VACUUM BREAKOUT CONFIRMED ({n_confirmed} bars above zone)'
    elif n_confirmed > 0 and n_false > 0:
        bk_status = f' | ❌ FALSE BREAKOUT ({n_confirmed} bars above, then reversed)'
    elif bk_states_list.count('ATTEMPTED') > 0:
        bk_status = ' | ⚡ BREAKOUT ATTEMPTED (not yet confirmed)'

    fig.update_layout(
        title=dict(
            text=(
                f'<b>📊 Bull vs Bear Probability Transition — Full Session</b><br>'
                f'<sub>'
                f'Significant events only — '
                f'★ {n_cross} cross{"" if n_cross==1 else "es"} (gap≥8%) | '
                f'⚡ {n_flip} directional flip{"" if n_flip==1 else "s"} (held≥2 bars) | '
                f'◆ {n_surge} surge{"" if n_surge==1 else "s"} (≥15% move) | '
                f'Latest: 🟢 {final_b:.0f}% vs 🔴 {final_r:.0f}% → <b>{final_bias_label}</b>'
                f'{bk_status} | '
                f'Dots = IV Regime (🟢 Compress · 🔴 Expand · ⬜ Flat)'
                f'</sub>'
            ),
            font=dict(size=14, color='white'),
        ),
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,35,50,0.8)',
        height=420,
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            font=dict(color='white', size=10),
            bgcolor='rgba(0,0,0,0.7)', bordercolor='rgba(255,255,255,0.2)', borderwidth=1,
        ),
        xaxis=dict(
            title='Time (IST)',
            gridcolor='rgba(128,128,128,0.15)',
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title='Probability %',
            range=[0, 105],
            gridcolor='rgba(128,128,128,0.15)',
            ticksuffix='%',
        ),
        margin=dict(l=60, r=60, t=110, b=50),
        dragmode='drawline',
        newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig.update_layout(
        modebar_add=['drawline','drawopenpath','drawcircle','drawrect','eraseshape'],
        modebar=dict(bgcolor='rgba(0,0,0,0.5)', color='#94a3b8', activecolor='#f59e0b'),
    )
    return fig


def create_dex_chart(df: pd.DataFrame, spot_price: float, unit_label: str = "B") -> go.Figure:
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    colors = ['#10b981' if x > 0 else '#ef4444' for x in df_sorted['net_dex']]
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df_sorted['strike'], x=df_sorted['net_dex'], orientation='h',
                         marker_color=colors, name='Net DEX', showlegend=True,
                         hovertemplate=f'Strike: %{{y:,.0f}}<br>Net DEX: %{{x:.4f}}{unit_label}<extra></extra>'))
    fig = _add_volume_overlay_horizontal(fig, df_sorted)
    fig.add_hline(y=spot_price, line_dash='dash', line_color='#06b6d4', line_width=3,
                  annotation_text=f'Spot: {spot_price:,.2f}', annotation_position='top right')
    fig.update_layout(
        title=dict(text='<b>📊 Delta Exposure (DEX)</b><br><sub>🟩🟥 = Call/Put Volume overlay (top axis)</sub>', font=dict(size=18, color='white')),
        xaxis_title=f'DEX (₹ {unit_label})', yaxis_title='Strike Price',
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(26,35,50,0.8)',
        height=700, barmode='overlay',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=11), bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1),
        hovermode='closest', dragmode='drawline', newshape=dict(line=dict(color='#f59e0b', width=2)),
    )
    fig = _configure_volume_xaxis2(fig, df_sorted)
    fig.update_layout(modebar_add=['drawline','drawopenpath','drawclosedpath','drawcircle','drawrect','eraseshape'])
    return fig


def create_oi_distribution_chart(df: pd.DataFrame, spot_price: float) -> go.Figure:
    df_sorted = df.sort_values('strike').reset_index(drop=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=df_sorted['strike'], x=df_sorted['call_oi'], orientation='h',
                         name='Call OI', marker_color='#10b981', opacity=0.7))
    fig.add_trace(go.Bar(y=df_sorted['strike'], x=-df_sorted['put_oi'], orientation='h',
                         name='Put OI', marker_color='#ef4444', opacity=0.7))
    if 'total_volume' in df_sorted.columns:
        oi_max  = max(df_sorted['call_oi'].max(), df_sorted['put_oi'].max(), 1)
        vol_max = df_sorted['total_volume'].fillna(0).max() or 1
        scale   = oi_max / vol_max
        fig.add_trace(go.Scatter(y=df_sorted['strike'], x=df_sorted['total_volume'].fillna(0)*scale,
                                 mode='lines', line=dict(color='rgba(245,158,11,0.7)', width=2, dash='dot'),
                                 name='Total Volume (scaled)', fill='tozerox', fillcolor='rgba(245,158,11,0.08)',
                                 hovertemplate='Strike: %{y:,.0f}<br>Total Vol: %{customdata:,.0f}<extra></extra>',
                                 customdata=df_sorted['total_volume'].fillna(0)))
    fig.add_hline(y=spot_price, line_dash='dash', line_color='#06b6d4', line_width=2)
    fig.update_layout(
        title=dict(text='<b>📋 Open Interest Distribution</b><br><sub>🟡 Dotted = Total Volume (scaled to OI axis)</sub>', font=dict(size=18, color='white')),
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(26,35,50,0.8)',
        height=600, barmode='overlay', xaxis_title='Open Interest (Contracts)', yaxis_title='Strike Price',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(color='white', size=11), bgcolor='rgba(0,0,0,0.8)', bordercolor='white', borderwidth=1),
    )
    return fig

# ============================================================================
# UNIFIED DATA FETCHER
# ============================================================================

class UnifiedOptionsFetcher:
    def __init__(self, config: DhanConfig):
        self.config  = config
        self.headers = {'access-token': config.access_token, 'client-id': config.client_id, 'Content-Type': 'application/json'}
        self.base_url = "https://api.dhan.co/v2"
        self.bs_calc  = BlackScholesCalculator()
        self.risk_free_rate = 0.07

    def get_instrument_type(self, symbol):
        if symbol in DHAN_INDEX_SECURITY_IDS: return "INDEX"
        if symbol in DHAN_STOCK_SECURITY_IDS:  return "STOCK"
        return "UNKNOWN"

    def get_security_id(self, symbol):
        return DHAN_INDEX_SECURITY_IDS.get(symbol) or DHAN_STOCK_SECURITY_IDS.get(symbol)

    def get_contract_size(self, symbol):
        cfg = SYMBOL_CONFIG.get(symbol, {})
        return cfg.get('contract_size', cfg.get('lot_size', 50))

    def fetch_rolling_data(self, symbol, from_date, to_date, strike_type='ATM', option_type='CALL',
                           interval='60', expiry_code=1, expiry_flag='WEEK'):
        try:
            sec_id     = self.get_security_id(symbol)
            if sec_id is None: return None
            instrument = "OPTIDX" if self.get_instrument_type(symbol) == "INDEX" else "OPTSTK"
            exchange_segment = "BSE_FNO" if symbol in BSE_FNO_SYMBOLS else "NSE_FNO"
            payload = {
                "exchangeSegment": exchange_segment, "interval": interval,
                "securityId": sec_id, "instrument": instrument,
                "expiryFlag": expiry_flag, "expiryCode": expiry_code,
                "strike": strike_type, "drvOptionType": option_type,
                "requiredData": ["open","high","low","close","volume","oi","iv","strike","spot"],
                "fromDate": from_date, "toDate": to_date,
            }
            resp = requests.post(f"{self.base_url}/charts/rollingoption",
                                 headers=self.headers, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get('data', {})
            return None
        except Exception as e:
            st.error(f"API Error: {e}")
            return None

    def process_historical_data(self, symbol, target_date, strikes, interval='60',
                                expiry_code=1, expiry_flag='WEEK',
                                from_timestamp=None, incremental=False):
        target_dt = datetime.strptime(target_date, '%Y-%m-%d')
        from_date = (from_timestamp.strftime('%Y-%m-%d') if incremental and from_timestamp
                     else (target_dt - timedelta(days=2)).strftime('%Y-%m-%d'))
        to_date   = (target_dt + timedelta(days=2)).strftime('%Y-%m-%d')

        instrument_type = self.get_instrument_type(symbol)
        contract_size   = self.get_contract_size(symbol)
        tte             = 7/365 if expiry_flag == 'WEEK' else 30/365
        scaling_factor  = 1e9 if instrument_type == 'INDEX' else 1e7
        unit_label      = 'B'  if instrument_type == 'INDEX' else 'Cr'

        all_data = []
        progress_bar = st.progress(0)
        status_text  = st.empty()
        total_steps  = len(strikes) * 2
        current_step = 0

        for strike_type in strikes:
            mode = "Incremental" if incremental else "Fetching"
            status_text.text(f"[{mode}] {symbol} {strike_type} ({expiry_flag} {expiry_code})...")
            call_data = self.fetch_rolling_data(symbol, from_date, to_date, strike_type, 'CALL', interval, expiry_code, expiry_flag)
            current_step += 1; progress_bar.progress(current_step / total_steps); time.sleep(0.3)
            put_data  = self.fetch_rolling_data(symbol, from_date, to_date, strike_type, 'PUT',  interval, expiry_code, expiry_flag)
            current_step += 1; progress_bar.progress(current_step / total_steps); time.sleep(0.3)
            if not call_data or not put_data: continue
            ce = call_data.get('ce', {}); pe = put_data.get('pe', {})
            if not ce: continue
            for i, ts in enumerate(ce.get('timestamp', [])):
                try:
                    dt_ist = datetime.fromtimestamp(ts, tz=pytz.UTC).astimezone(IST)
                    if dt_ist.date() != target_dt.date(): continue
                    if incremental and from_timestamp and dt_ist <= from_timestamp: continue
                    spot   = ce.get('spot',   [0])[i] if i < len(ce.get('spot',   [])) else 0
                    strike = ce.get('strike', [0])[i] if i < len(ce.get('strike', [])) else 0
                    if spot == 0 or strike == 0: continue
                    call_oi  = ce.get('oi',    [0])[i] if i < len(ce.get('oi',    [])) else 0
                    put_oi   = pe.get('oi',    [0])[i] if i < len(pe.get('oi',    [])) else 0
                    call_vol = ce.get('volume',[0])[i] if i < len(ce.get('volume', [])) else 0
                    put_vol  = pe.get('volume',[0])[i] if i < len(pe.get('volume', [])) else 0
                    call_iv  = ce.get('iv',   [15])[i] if i < len(ce.get('iv',   [])) else 15
                    put_iv   = pe.get('iv',   [15])[i] if i < len(pe.get('iv',   [])) else 15
                    civ_d = call_iv/100 if call_iv > 1 else call_iv
                    piv_d = put_iv /100 if put_iv  > 1 else put_iv
                    cg  = self.bs_calc.calculate_gamma(spot, strike, tte, self.risk_free_rate, civ_d)
                    pg  = self.bs_calc.calculate_gamma(spot, strike, tte, self.risk_free_rate, piv_d)
                    cd  = self.bs_calc.calculate_call_delta(spot, strike, tte, self.risk_free_rate, civ_d)
                    pd_ = self.bs_calc.calculate_put_delta( spot, strike, tte, self.risk_free_rate, piv_d)
                    cv  = self.bs_calc.calculate_vanna(spot, strike, tte, self.risk_free_rate, civ_d)
                    pv  = self.bs_calc.calculate_vanna(spot, strike, tte, self.risk_free_rate, piv_d)
                    cc  = self.bs_calc.calculate_charm(spot, strike, tte, self.risk_free_rate, civ_d, 'call')
                    pc  = self.bs_calc.calculate_charm(spot, strike, tte, self.risk_free_rate, piv_d, 'put')
                    call_close = ce.get('close', [0])[i] if i < len(ce.get('close', [])) else 0
                    put_close  = pe.get('close', [0])[i] if i < len(pe.get('close',  [])) else 0
                    call_open  = ce.get('open',  [0])[i] if i < len(ce.get('open',  [])) else 0
                    put_open   = pe.get('open',  [0])[i] if i < len(pe.get('open',   [])) else 0
                    all_data.append({
                        'timestamp': dt_ist, 'time': dt_ist.strftime('%H:%M IST'),
                        'spot_price': spot, 'strike': strike, 'strike_type': strike_type,
                        'call_oi': call_oi, 'put_oi': put_oi,
                        'call_volume': call_vol, 'put_volume': put_vol, 'total_volume': call_vol + put_vol,
                        'call_iv': call_iv, 'put_iv': put_iv,
                        'call_close': call_close, 'put_close': put_close,
                        'call_open': call_open,   'put_open': put_open,
                        'call_gex': (call_oi*cg*spot**2*contract_size)/scaling_factor,
                        'put_gex':  -(put_oi*pg*spot**2*contract_size)/scaling_factor,
                        'net_gex':  (call_oi*cg - put_oi*pg)*spot**2*contract_size/scaling_factor,
                        'call_dex': (call_oi*cd*spot*contract_size)/scaling_factor,
                        'put_dex':  (put_oi*pd_*spot*contract_size)/scaling_factor,
                        'net_dex':  (call_oi*cd + put_oi*pd_)*spot*contract_size/scaling_factor,
                        'call_vanna': (call_oi*cv*spot*contract_size)/scaling_factor,
                        'put_vanna':  (put_oi*pv*spot*contract_size)/scaling_factor,
                        'net_vanna':  (call_oi*cv + put_oi*pv)*spot*contract_size/scaling_factor,
                        'call_charm': (call_oi*cc*spot*contract_size)/scaling_factor,
                        'put_charm':  (put_oi*pc*spot*contract_size)/scaling_factor,
                        'net_charm':  (call_oi*cc + put_oi*pc)*spot*contract_size/scaling_factor,
                    })
                except: continue
        progress_bar.empty(); status_text.empty()
        if not all_data: return None, None
        df = pd.DataFrame(all_data).sort_values(['strike','timestamp']).reset_index(drop=True)
        # flow columns
        for col in ['call_gex_flow','put_gex_flow','net_gex_flow','call_dex_flow','put_dex_flow','net_dex_flow',
                    'call_oi_change','put_oi_change','call_oi_gex','put_oi_gex','net_oi_gex']:
            df[col] = 0.0
        for strike in df['strike'].unique():
            m = df['strike'] == strike
            sd = df[m]
            if len(sd) > 1:
                for base, flow in [('call_gex','call_gex_flow'),('put_gex','put_gex_flow'),('net_gex','net_gex_flow'),
                                   ('call_dex','call_dex_flow'),('put_dex','put_dex_flow'),('net_dex','net_dex_flow'),
                                   ('call_oi','call_oi_change'),('put_oi','put_oi_change')]:
                    df.loc[m, flow] = sd[base].diff().fillna(0)
        max_gex = df['net_gex'].abs().max()
        df['hedging_pressure'] = (df['net_gex'] / max_gex * 100) if max_gex > 0 else 0
        latest     = df.sort_values('timestamp').iloc[-1]
        spot_prices = df['spot_price'].unique()
        meta = {
            'symbol': symbol, 'instrument_type': instrument_type, 'date': target_date,
            'spot_price': latest['spot_price'],
            'spot_price_min': spot_prices.min(), 'spot_price_max': spot_prices.max(),
            'spot_variation_pct': (spot_prices.max()-spot_prices.min())/spot_prices.mean()*100,
            'total_records': len(df),
            'time_range': f"{df['time'].min()} - {df['time'].max()}",
            'strikes_count': df['strike'].nunique(),
            'interval': f"{interval} minutes" if interval != '1' else '1 minute',
            'expiry_code': expiry_code, 'expiry_flag': expiry_flag,
            'contract_size': contract_size, 'unit_label': unit_label,
            'fetch_time': datetime.now(IST).strftime('%H:%M:%S IST'),
            'is_incremental': incremental,
        }
        return df, meta

# ============================================================================
# SMART DATA FETCHER
# ============================================================================

def fetch_data_with_smart_cache(symbol, target_date, strikes, interval, expiry_code, expiry_flag,
                                 force_refresh=False):
    fetcher          = UnifiedOptionsFetcher(DhanConfig())
    instrument_type  = fetcher.get_instrument_type(symbol)
    is_current_day   = cache_manager.is_current_trading_day(target_date)
    is_market_open   = cache_manager.is_market_hours()
    cached_df, cached_meta, last_ts = cache_manager.get_cached_data(
        symbol, target_date, strikes, interval, expiry_code, expiry_flag, instrument_type)

    if not is_current_day:
        if cached_df is not None and not force_refresh:
            cached_meta['fetch_mode'] = 'cached'
            cached_meta['fetch_time'] = datetime.now(IST).strftime('%H:%M:%S IST')
            return cached_df, cached_meta, 'cached'
        df, meta = fetcher.process_historical_data(symbol, target_date, strikes, interval, expiry_code, expiry_flag)
        if df is not None:
            cache_manager.save_to_cache(df, meta, symbol, target_date, strikes, interval, expiry_code, expiry_flag, instrument_type)
        return df, meta, 'full_fetch'

    if not is_market_open and cached_df is not None and not force_refresh:
        cached_meta['fetch_mode'] = 'cached'
        cached_meta['fetch_time'] = datetime.now(IST).strftime('%H:%M:%S IST')
        return cached_df, cached_meta, 'cached'

    if cached_df is not None and last_ts is not None and not force_refresh:
        new_df, new_meta = fetcher.process_historical_data(
            symbol, target_date, strikes, interval, expiry_code, expiry_flag,
            from_timestamp=last_ts, incremental=True)
        if new_df is not None and len(new_df) > 0:
            merged = cache_manager.merge_incremental_data(cached_df, new_df)
            merged_meta = new_meta.copy()
            merged_meta.update({'total_records': len(merged),
                                'time_range': f"{merged['time'].min()} - {merged['time'].max()}",
                                'fetch_mode': 'incremental', 'new_records': len(new_df)})
            cache_manager.save_to_cache(merged, merged_meta, symbol, target_date, strikes, interval, expiry_code, expiry_flag, instrument_type)
            return merged, merged_meta, 'incremental'
        cached_meta['fetch_mode'] = 'cached'
        cached_meta['fetch_time'] = datetime.now(IST).strftime('%H:%M:%S IST')
        return cached_df, cached_meta, 'cached'

    df, meta = fetcher.process_historical_data(symbol, target_date, strikes, interval, expiry_code, expiry_flag)
    if df is not None:
        cache_manager.save_to_cache(df, meta, symbol, target_date, strikes, interval, expiry_code, expiry_flag, instrument_type)
    return df, meta, 'full_fetch'

# ============================================================================
# MAIN APP
# ============================================================================

# ============================================================================
# LANDING PAGE — Purple / White Theme
# NYZTrade GEX Pro | Integrated — no separate file needed
# ============================================================================

LANDING_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

/* ── root ── */
:root {
  --lp-purple-deep:   #1a0533;
  --lp-purple-mid:    #2d0a5e;
  --lp-purple-accent: #7c3aed;
  --lp-purple-light:  #a855f7;
  --lp-purple-glow:   #c084fc;
}

/* ── hero banner ── */
.lp-hero {
    background: linear-gradient(135deg, #1a0533 0%, #2d0a5e 45%, #3b0764 100%);
    border: 1px solid rgba(168,85,247,0.35);
    border-radius: 20px;
    padding: 36px 40px 28px 40px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.lp-hero::before {
    content: '';
    position: absolute; top: -60px; right: -60px;
    width: 280px; height: 280px; border-radius: 50%;
    background: radial-gradient(circle, rgba(168,85,247,0.18) 0%, transparent 70%);
    pointer-events: none;
}
.lp-logo-row {
    display: flex; align-items: center; justify-content: center;
    gap: 18px; margin-bottom: 22px;
}
.lp-logo-img {
    width: 52px; height: 52px; border-radius: 12px;
    object-fit: cover;
    border: 1px solid rgba(168,85,247,0.5);
    box-shadow: 0 4px 18px rgba(124,58,237,0.4);
}
.lp-logo-placeholder {
    width: 52px; height: 52px; border-radius: 12px;
    background: linear-gradient(135deg, #7c3aed, #a855f7);
    border: 1px solid rgba(168,85,247,0.5);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.2rem; font-weight: 700; color: #fff;
    box-shadow: 0 4px 18px rgba(124,58,237,0.4);
    flex-shrink: 0;
}
.lp-logo-divider {
    width: 1px; height: 36px;
    background: rgba(168,85,247,0.35);
}
.lp-logo-text {
    font-family: 'Space Grotesk', sans-serif;
    line-height: 1.3; text-align: left;
}
.lp-brand-name {
    display: block;
    font-size: 2.2rem; font-weight: 800; letter-spacing: -0.02em;
    background: linear-gradient(135deg, #00f5c4 0%, #00d4ff 50%, #a78bfa 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: drop-shadow(0 0 18px rgba(0,245,196,0.35));
}
.lp-brand-sub {
    font-size: 0.72rem; font-weight: 500;
    color: rgba(255,255,255,0.45);
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.08em; text-transform: uppercase;
}
.lp-badge-row {
    display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px;
}
.lp-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 20px;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem; color: rgba(255,255,255,0.75);
}
.lp-badge-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: #a855f7;
    animation: lp-pulse 2s ease-in-out infinite;
}
.lp-headline {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.0rem; font-weight: 700;
    background: linear-gradient(135deg, #ffffff 0%, #c084fc 60%, #a855f7 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.25; margin-bottom: 10px;
}
.lp-subline {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.88rem; color: rgba(255,255,255,0.55);
    line-height: 1.6; margin-bottom: 18px;
}
.lp-social-row {
    display: flex; gap: 10px; margin-bottom: 4px;
}
.lp-social-btn {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 16px; border-radius: 22px;
    text-decoration: none !important;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.73rem; font-weight: 600;
    transition: opacity 0.2s;
}
.lp-social-yt {
    background: rgba(255,0,0,0.18);
    border: 1px solid rgba(255,0,0,0.35);
    color: #ff6b6b !important;
}
.lp-social-li {
    background: rgba(10,102,194,0.20);
    border: 1px solid rgba(10,102,194,0.40);
    color: #74b3f5 !important;
}
.lp-social-btn:hover { opacity: 0.8; }

/* ── metrics row ── */
.lp-metrics {
    display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
}
.lp-metric {
    flex: 1; min-width: 120px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(168,85,247,0.25);
    border-radius: 12px; padding: 14px 18px;
    text-align: center;
}
.lp-metric-val {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.4rem; font-weight: 700;
    background: linear-gradient(135deg, #c084fc, #a855f7);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.lp-metric-lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem; color: rgba(255,255,255,0.40);
    margin-top: 3px;
}

/* ── feature grid ── */
.lp-features {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 12px; margin-bottom: 20px;
}
.lp-feature {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(168,85,247,0.18);
    border-radius: 12px; padding: 16px 18px;
    transition: border-color 0.2s, background 0.2s;
}
.lp-feature:hover {
    border-color: rgba(168,85,247,0.45);
    background: rgba(124,58,237,0.10);
}
.lp-feature-icon {
    font-size: 1.4rem; margin-bottom: 7px;
}
.lp-feature-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.88rem; font-weight: 600;
    color: #ffffff; margin-bottom: 4px;
}
.lp-feature-desc {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; color: rgba(255,255,255,0.45);
    line-height: 1.55;
}

/* ── founder card ── */
.lp-founder {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(168,85,247,0.22);
    border-radius: 14px; padding: 20px 22px;
    display: flex; gap: 16px; margin-bottom: 20px;
}
.lp-avatar {
    width: 48px; height: 48px; border-radius: 50%;
    background: linear-gradient(135deg, #7c3aed, #a855f7);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.9rem; font-weight: 700; color: #ffffff;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(124,58,237,0.4);
}
.lp-avatar-img {
    width: 52px; height: 52px; border-radius: 50%;
    object-fit: cover; flex-shrink: 0;
    border: 2px solid rgba(168,85,247,0.5);
    box-shadow: 0 4px 12px rgba(124,58,237,0.4);
}
.lp-founder-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem; font-weight: 600; color: #ffffff;
}
.lp-founder-role {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; color: rgba(192,132,252,0.75); margin-top: 2px;
}
.lp-founder-bio {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.76rem; color: rgba(255,255,255,0.50);
    line-height: 1.6; margin-top: 8px;
}
.lp-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.lp-tag {
    padding: 3px 10px; border-radius: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.63rem; font-weight: 600;
}
.lp-tag-purple { background:rgba(124,58,237,0.20); color:#c084fc; border:1px solid rgba(168,85,247,0.3); }
.lp-tag-white  { background:rgba(255,255,255,0.08); color:rgba(255,255,255,0.75); border:1px solid rgba(255,255,255,0.18); }

/* ── disclaimer ── */
.lp-disclaimer {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.66rem; color: rgba(255,255,255,0.28);
    text-align: center; margin-top: 6px;
}
.lp-section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem; color: rgba(192,132,252,0.65);
    text-transform: uppercase; letter-spacing: 0.10em;
    margin-bottom: 10px;
}

@keyframes lp-pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
</style>
"""


# ============================================================================
# AUTHENTICATION SYSTEM
# Credentials in .streamlit/secrets.toml:
#
# [users]
# admin = { password = "adminpass123", role = "admin" }
# user1 = { password = "userpass456", role = "user"  }
# user2 = { password = "pass789",     role = "user"  }
#
# role = "admin" → full access including cache clear
# role = "user"  → full access but NO cache clear
# ============================================================================

def _get_user_db() -> dict:
    """Return user credentials from HEDGEX_USERS in MASTER CONFIG (top of file)."""
    return {str(k): dict(v) for k, v in HEDGEX_USERS.items()}


def _render_login_page() -> None:
    """Render the login form. Sets session_state on success."""
    import base64 as _b64lp

    st.markdown("""
    <style>
    .lp-login-wrap {
        max-width:420px; margin:60px auto; padding:40px 36px;
        background:rgba(10,15,30,0.92);
        border:1.5px solid rgba(99,102,241,0.35);
        border-radius:18px;
        box-shadow:0 8px 48px rgba(0,0,0,0.55);
    }
    .lp-login-brand {
        font-family:'Space Grotesk',sans-serif;
        font-size:2.2rem; font-weight:900;
        background:linear-gradient(135deg,#06b6d4,#818cf8,#c084fc);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
        text-align:center; margin-bottom:4px; letter-spacing:-0.02em;
    }
    .lp-login-sub {
        font-family:'JetBrains Mono',monospace;
        font-size:0.70rem; color:rgba(255,255,255,0.45);
        text-align:center; margin-bottom:28px;
        text-transform:uppercase; letter-spacing:0.12em;
    }
    .lp-login-err {
        background:rgba(239,68,68,0.12);
        border:1px solid rgba(239,68,68,0.4);
        border-radius:8px; padding:8px 14px;
        font-size:0.80rem; color:#f87171;
        margin-bottom:12px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="lp-login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="lp-login-brand">HedGEX</div>', unsafe_allow_html=True)
    st.markdown('<div class="lp-login-sub">powered by NYZTrade · Secure Login</div>', unsafe_allow_html=True)

    username = st.text_input("Username", placeholder="Enter username", key="login_user")
    password = st.text_input("Password", placeholder="Enter password",
                              type="password", key="login_pass")

    if st.button("Login →", use_container_width=True, type="primary"):
        db    = _get_user_db()
        uname = username.strip()
        pwd   = password.strip()
        # Debug: show what we got vs what's stored
        matched = False
        for k, v in db.items():
            if k == uname and v["password"] == pwd:
                matched = True
                st.session_state["auth_user"]      = uname
                st.session_state["auth_role"]      = v["role"]
                st.session_state["auth_logged_in"] = True
                st.session_state.pop("login_error", None)
                st.rerun()
                break
        if not matched:
            st.session_state["login_error"] = True
            # Show which users exist (without passwords) to help debug
            st.error(f"Invalid credentials. Available users: {list(db.keys())}")
            st.caption(f"You entered username: '{uname}' (length {len(uname)})")
            st.caption(f"Password length entered: {len(pwd)}")

    st.markdown('</div>', unsafe_allow_html=True)


def _is_admin() -> bool:
    return st.session_state.get("auth_role", "user") == "admin"


def _current_user() -> str:
    return st.session_state.get("auth_user", "")


def _ensure_authenticated() -> bool:
    """
    Call at top of main(). Returns True if user is logged in.
    Renders login page and returns False if not.
    """
    if not st.session_state.get("auth_logged_in", False):
        _render_login_page()
        return False
    return True


def show_landing() -> bool:
    """Landing page gate. Returns True when user clicks Enter."""
    import base64 as _b64

    LOGO_B64 = "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82NceY59QAAAAAHdw93XHoPTgACRAAAAKAAEASAFAACAAVMCQABAAKAmJAAgFAATEgASgAAJiQFCAAAAWRAAAAKEJiQAFACAAJCgBAALIAAgAFTEgAQCpiQJQJEoALIgAJZAEqYkCwRvjL4jfH7+fmOnF8zG+MRMWRExL51vZx8e4c+oAAAAADu4e7rj0HpwABIgAAAFAACAJACgAABAKBIAAgAFATEgAQACgJiQAJQAAExIChAAAALIgAAAFCExIACgBAAEhQAgAFlEgAQACpiQAAJUxIEoEiUAFkQAEsgA+h6vmvmY6cETBETBETBETBETBET8y8HjMeX1goAAAAADu4e7rj0HpwABIgAAAFAACAJACgAABAALIAAgAFATEgAQACgJiQAJQAAExIChAAAALIgAAAFCExIACgBAAEhQAgAFTEgAQACpiQAAJUxIEoEiUAFkQAEsgCV9fM75omPX8uImLlAREwREwREwRz9HDjfMPP6gAAAAAAHdw93XHoPTgABMSBAAAKAAEASAFAAACAAWQABAAKAmJAAAgFATEgASgAAJiQFCAAAAWRAAAAKEJiQAFACAAJAChAAKmJAAgAFAkAASpiQJQJEoAEiUAJZAEqYkDt5fmJj0/PgERMERMERML81dhW8ewcuwAAAAAADu4e7rj0HpwAAmJAgAAFAACAJACgAABAALIAAgAFATEgAAQCgJiQAJQAAExIChAAAALIgAAAFATEwAAChAAEgBQgAFTEgAQACgSAAJUxIEoEiVMde+XLHt453IzsAJZAEqU75REx6/mRExcxEwQCImCImJeLk9fLzeoJoAAAAAAB3cPd1x6D04AATEgQAACgABAEgBQAAAgAFkAAAQCgJiQAAIBQExIAEoAACYkBQgAAAFkQAAACgJiYAABQgACQAoQACpiQAIABQJAAEqYkCUCTs1zfcx6fm/HH38nL1ecxPn9wASyAn63xhMer5sRMWREwRHz8HpEwQCPP05M64R5vWAAAAAAAA7uHu649B6cAAJiQIAABQAAgCQAoAAAQACyAAAIBQExIAAEAoCYkACUAABMSAoQAAACyIAAABQExMAAAoQABIAUIAATEqAEAAoEgACVMSBKl2a5PU9PzoiYsef2muJ9fPj+sEoSzL06eeEx6vnREwREwR8fXkRX/Hjw9Hb3UndZ2DtwitsKnl2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PPqvaQggfK/fvwQA/Qf/APwFbyv/ANqA8/8AvagQvvfvPPKfF/6ggP1PfgF/q/vU/PFvag/PqPQwFPPPQFVa/wBcugAD5cGj4BTzzzzzzzz6r2kIIH3K2zgEAP0DHHIhf2jLDgL7/wD88DAw18888rzU/qCA6sQ1AX8sFvqy8W9qD9+i84hU889AVVr6B3RID+XBo+AU88888888+q8pCCD9888stCCV9888rW888p888888888+d888888r/qGs8888Aeu8888spW9qD7nc888U889AVVi98888cyXBo+AU88888888+q8pCAd888888KCV9888rW888p88888888869888888r/ue88888Uf8APPPPPPGf6htfPPPPFPPPQFRHPPPPPPP1QavgFPPPPPPPPPqvKQh/PPPPPPKwV/fPPK1/PPKaPPPPPPPPlPfPPPPPK/8Ajzzzzzzfzzzzzzzz1+ofzzzzzxTzz0BDzzzjDnzzy4Gr4BTzzzzzzzz6rykb7zzpVXzzwBf3zzytbzzymzPf/wC888+2988888wh/g888/xk8888o5/888fq0888y4+U889BD888jox9888qq+IU88888888+q8pS1889V3888hX9888rW888p/AUu888+pW94888/8AP/8A7zzwXznzzy773vzzyCpTzzz0MBzzz0HfzzwfXzzzzyir6hTzzzzzzzz6rSkJXzz1VfzzwFf3zzypXzzyn8BQ/wA88uHax4288sZ//wDvPPPfOvPPONvavPPPvtPPPMg1vPPKKXvPPA+fd8P9gavqFPPPPPPPPPqtLQlfPPVV/PPAV1/PPP3/ADzyn8AZzzzzzzz5Rbzzyx3/AO8889868888eIr888++b888+ue888opS888vhqZD/VAW+oU88888888+q89CV889XX888AXq88888888p/AG8888888+UB8888//wDvPPPfP2fPPPKK/PPPvhNPPPPPPPPI6VFfPPPPLqv1QFvqFPPPPPPPPPqvPQlfPPV1/PPAF6d/PPPPPPKfxXPPPPPPPPlFvfPPP/8A7zzz3z8PLzzyivzzz74LLTzzzzzz6mlUnzzzzzyrT0BbahTzzzzzzzz6rT0JXzz1dfzzwBf1PvT+zzzz387zzzzzzzz5RZHTvz//AO88898/AAw/8or888++CVIx888yXhptT+dR088zzd9AWWpU88888888++89DxzWtXOOZwCX9WvMtU888u9gfwyhAgDW98WBAXdI/wCM8C2fPwAcTvn2TTWv/AHfv72k/wB4Gn0P79QynSoP/wAAWWpU88888888++c9DCBV+X++pACX9E76M888409CBNNFOCBW/wDHhQF/I/7BwL6vO4AVVfvJdvas9Avfv1KwhlAbfQ6tnKKGaw//AAhZalTzzzzzzzz77T0MIFX5fz6kAJelfzzzzzzbz0IfLL2J42D2t3eEj1lztGdgC698hX3ayOnE3tYr1f8AFJyvfGDhqmmGKWy9D34oWXpU88888888++U9DCBV+X8+pACXpW88888xV89CD+//AAvaVkl12w6/Lq7g0IgZ78KlfV3PRDS/6QvVP1ag1vsKei0fkSwwRQ1aKFl6VPPPPPPPPPvlPQwgVfl/PqQAk6Ve/wDvsX5fz2oP/wC5C9rWAr8cDr8+voANhBg/tmV9Xo6PdE0mq9x+IqKW+FtgLA+A4aSUDVoqWXpU88888888++U9DCBV+f8APqQQg6VvziQfPl/Pal//AKm6iFY122LML6pz1OBciyylI3lf96d2771Hb06WiHXfnM0NrxQn6fsJWqpZelTzzzzzzzz75b0MIFX7/wA+tBCDpW/+pB8+X89qU/8AqfagVv8A37kAP73/AMDAVr8/qB+8X89W9+/8CV+/UrAXVpA+Dq8Up8XrLVqqXXpU88888888++W9DCBV+/8APvQQA6Xv/qQfvl/PalP/AKn2oFb/AN6pAD+9/wDAwFa/P6gfrF/PVvfv/Alfv1KwF/aQFgqvFKfV66Faql1qGyfPPPPPPPvlvQwgVfv/AD70EAOmr/60H75/72oD/wCp9qBC/wDaqAA/vf8AwIBWvz+oH6hfz1b37/wJX79SsBf2kBYKrxSn1euhmKd9AX6Xzzzzzzz75b0MIBX7/wB+/BADpo/+9B++/wDvagP/AOv2oEL72qgAP71fwIJWvz+oH7xfz1b37/woH79SsBX2kZYKrxSn9fkd4NL9V397zzzzzzz74b0MIBX6v378EAOmj/8A9B++/wDvagP/AOr2oEL72qgAP7xfwIJWvz+oH7xf71b35fyoH79SsFX2lZYKrxSn9evj74pFXVfzzzzzzzz75L2kIBX6v378EAOmj/8A9B++/wDvagPf6vagQvvaKAA/vF/Aglf/AD+oH7xf71f35fyoP79z8FWmlZYKj1T39euiX6oNVTXzzzzzzzz75L2kIAH6v378EAO2j/8A8B++/wDvagPf6vagQvvaKAA/vF/Aglf/AD2oFfh/71f35fyoP77z8FSihZYKl9T/APDr0Ry+pBS288888888+++9pCAB+r9+/BAD9o//APAfvK/vagPf6vagQvvaKgA/vF/Aglf9PagV7P8A71f35fyoP77z8FSihZYcvXj/APHw0DCN9pQc88888888+++9pCCB+r9+/BAD9o//APAfvK/vagPf6vagQvvaKgA/vF/Aglf1PagV6v8A71f35f2oP77z8FSihZ0OEor/APNRULJO8pa888888888p+69pCCB+r9+/BAD9p//APAfvK/vagPf6vagQvvaKgQ/vF/Qglf1PagF+u/vV/fF/ag/vuNw0KKE31RaB+73aEGR/LJVfPPPPPPPPLt/vaQggfq/fvwQA/Yf/wDwHbyv72oD3+72oEL72ioEP/xf+oJD9T34Be6v71fzxf2oP77DokCqOv4JewI+ruiW3zzy1/zzzzzzzzzzyr2kIIHyv378EAP0H/8A8BW8r/8AagPP/vagQvvaKgQ//F/6ggP1PfgF/q/vU/PFvag/KXmHwKS1+pL9Alq72ffPPPPPPPPPPPPPPPPGe6QggfK/fvwQA/Qf/wDwFbyv/wBuA8/+9+BD+9oqBB/8X/qCA/U9+AX+r+9L88W9qDlj9AppfqWv88dWWrq888888888888888888889df8A/wA97wwz3/8Au+899Nf+uMNdPe++Nd9uOPNtNO+/d9tMO/NNc+vf9sMePPc8sVQm9uq+jn9888eWe18888888888888888888888888888888888888888888888888888888888888888888888888888888888vG/8886/t88888sBN88888888888888888888888888888888888888888888888888888888888888888888888888888888888c88888s3c888888c8888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888888/8QAPBEAAQMABQoEBQQBBAMBAAAAAQACAwQQESAwBRITFCExMjNRcRVBUsEiQGGBsTRCofCRI0PR4WBigPH/2gAIAQIBAT8A/wDjOChTT7WjZ1UeRx/uO/wm5No7fK37rw+j+n+T/wArw+j+n+T/AMrw+j+n+SvD6P6f5K8Po/p/krUKP6fytQo/p/K1Cj+n8rUKP6fytQo/p/K1GD0/lajB6fytRg9P5Wowen8rUYPT+VqUHp/K1KD0/lalB6fytSg9P5WpQen8rU4fT+VqcPp/K1OH0/lanD6fytTh9P5Wpw+n8rVIfT+VqkPpWqQ+lapF6VqsXRarF0WqxdFqsXRatF0WrRdFq0XRatH0Wrx9Fq8fRavH0Wrx9Fq8fRaCPotBH0Wgj6LQM6LQs6LQs6LQs6LQs6LQs6LRM6LRM6LRN6LRN6LRt6LRt6LRt6LRtWY1ZjVmBZgWaEWhWBEV2q0rOKzis9yz3LSO6rSO6rSv6rSv6oTuCbSR5hNcHbRitaXHNbvVEyY2P45dp6eVZqOCcE1m+cQ/LlFFGso4YcWm0KKcO2O34mTaGI26V+8/wKjUajgnEN01HENZ+UKNRwzeglzxYd4wqHDppmsO6s1Go/Km6ajjnCOGajhm9E/MeDhZHAMxP0RqNRwDjm6ajjnCOGajhG6Uamm1oODkfmu7e6Nw3DcPyZR+ROEcM1Go3iijdKKKZwjByPzXdve6bhuH5M3Tims3zhmo1FGoooooo3SiimcIwcj813b3wTcPyZulHENZvmo4JqNRRRRRRRRRulFFM4Rg5H5ru3vgn5c3TsWmj9QWmj9QWmj9QQlYTYDiG+ajgkhWhW1FFFFFFFG8UUUzhGDkfmu7e+Ccc4snCbkHMbiHBN81G4UUUUUUbpqKNTOEYOR+a7t74JxziycJuUfmDEOCb5qNwoo1Go3TUa2cIwcj813b3wzinFk4Tco/MF03zglG8ajjmo1s4Rg5H5ru3vfkkZGLXmwKTKsTdjQSjlf/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PXibQkwXz9xYXWOupTUGcfuVFajeNigBAQnD8gEkxUPRLCCIIkmD1Gu5elJeT5xuEN1QWSAwetw5SsSnlHFWbIUOcfpXJzTa4crkRLSOMOXJ1xv3i+FwAzCAhjCGqtnQIfxwBCUtUShKJUQsSF8/j4QYwmMImGcR+5yHEg3oTXKPSvD/AM+TIKhgKXHDdEESTBj7xrKqlTDnbocLmUvYi+ELuSEvBzhhjKJkXM5smN4QgBAwAIYhrrJgoSaGzex843SuTDD58VDml5yn0hVQyp6RxnG6kRaYxkR774XZCXqRrxYlGU6U6Ta8XS+6ynMXEMFcj7QQDgg/CLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITSCLITTCLITSCLITTCLITTCLITTCLITTCLITTCLITTCLITTCLITTCLITTLFkJpliyE0yxZCaZYspNMu+LKTTLviyk0y74spNMu+LKTTLviyk0yxZSaZYspNMu+LKTTLviyk0y74spNMu+LKTTLviyk0y74spNMu+LKTTLviyk0y74spNMu+LKTTLviyk0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74sqemXfFlT0y74syemXfFlT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT0y74syemXfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfFmT94XfCIgscCJmAxobogiSYMfeMDexwq40N8OXyZMQ0zQu5UWxjMHgFeQnv/1lB2P4wBhmCH8pYyN/mwCKgpKlOGMIIYDkKYMQ3I0E0xUWGiQOMShKB3XNLzUvD8p2qB3KwJphfHhD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4wEVArsSnUo8cE/sLWBT+H+52n7nefud5+53n7nefud9+5337nffud9+5337nffudt+5237nbfudt+5237nbPuds+53z7nfPud8+52z7nbPuds+52z7nbPuds+52z7nbPuds+53j7nePud4+53z7nfPudo+52j7naPudo+52j7naPudo+52j7nePud4+53j7nePud4+53j7naPudo+52j7naPudo+52j7naPud8+53z7nfPud8+53z7nfPud8+52z7h2z5nZPud8+53z7nfPud8+53z7nfPud8+53z7nbPuds+52z7nbPud4+53j7nePud4+53D7ncPudg+52D7nYPudg+52D7nYPudh+53H7ncfudx+53H7nY/udj+52H7nY/udj+52P7nY/ud3+53f7nd/udn+52f7nZ/udn+52f7nZ/udn+52f7nd/ud3+53f7nd/udn+5+H+5+H+5+H+52P7nY/ufk/udz+5+T+5+T+53P7n5P7n4P7n4P7nc/ufk/ufk/ufg/ufl/ufl/ufl/ufj/ufj/ufj/ufnvufnvufnvufjvufjvufivufmvufmvufivufivufivufmvufmvufivufivufjvufnvufnvuPC9b/AFK96VYKUIbb0lVC55/wMXG5YBCRPkBAqeRmOeXiwzy8WmSXS+XTIMgulwuFzhCEcwumQWFpeLC4WFwhYWkLHLJwJIeqXkHtpDghcRg8yIgIMETE8W8ZcAIEUdvoee8JCBoBfMovFhkF8vFpkl0vl0yDILpcLhc4QhHMLpkFhaXi8WFhZxhdIWkI4BwQo+u8oKvu6YPLxNaotXgG7DYRNUxckyi8WGQXy8Wl4tLpfM0yC6XC4XCFjklpdMgsLS8XCwsLCzjC6QtIWA6egKjC4W9eR5c/DhvVUCGqSsd5yjKLxYZBfLxaXi0ul8zTIMkuFwhYwyC0umUWcIQulwsLCwtLpC0haVotEKiSoApi3bvDcJzq4GWZRkGQZpaXi0ul88KZJcLhCxhkFpdMos4QhdLhYWFhaXS4QtIZOFg8VwSUPlU57PhN+zXyEIAKBgGWZRkFheM0tLxaXS+R8IZJcLhDWxhkFpdL5aWcIQulwsLCwtLpcIWlh6rrXOr48IOPrphcL5lGQWF4zS0vFpc4QvkfCGSXC4TjaZBaXS0uFpaQuELhYWFhZtC6XCFpYDeq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"
    logo_src = f"data:image/jpeg;base64,{LOGO_B64}"

    st.markdown(LANDING_CSS, unsafe_allow_html=True)

    # ── Build full hero HTML as one string (avoids triple-quote rendering issues) ──
    hero_html = (
        '<div class="lp-hero">'
          '<div class="lp-logo-row">'
            f'<img src="{logo_src}" class="lp-logo-img" alt="NYZTrade Logo">'
            '<div class="lp-logo-divider"></div>'
            '<div class="lp-logo-text">'
              '<span class="lp-brand-name">HedGEX</span>'
              '<span class="lp-brand-sub">powered by NYZTrade</span>'
            '</div>'
          '</div>'
          '<div class="lp-badge-row">'
            '<span class="lp-badge"><span class="lp-badge-dot"></span>LIVE &mdash; NSE &amp; BSE FNO</span>'
            '<span class="lp-badge"><span class="lp-badge-dot"></span>NIFTY &middot; BANKNIFTY &middot; SENSEX &middot; Stocks</span>'
            '<span class="lp-badge"><span class="lp-badge-dot"></span>Weekly &amp; Monthly Expiry</span>'
          '</div>'
          '<div class="lp-headline">HedGEX<br><span style="font-size:1.2rem;color:rgba(255,255,255,0.65);">India&#39;s GEX / VANNA Analytics Platform</span></div>'
          '<div class="lp-subline">'
            'Institutional-grade Gamma Exposure &middot; VANNA Cascade &middot; DEX &middot; Dealer Flow analytics<br>'
            'for NSE &amp; BSE FNO markets &mdash; built for Indian retail &amp; professional traders.'
          '</div>'
          '<div class="lp-social-row">'
            '<a class="lp-social-btn lp-social-yt" href="https://www.youtube.com/@nyztrade" target="_blank">'
              '&#9654; YouTube &mdash; @nyztrade'
            '</a>'
            '<a class="lp-social-btn lp-social-li" href="https://www.linkedin.com/in/drniyas/" target="_blank">'
              'in&nbsp; LinkedIn &mdash; Dr. Niyas N'
            '</a>'
          '</div>'
        '</div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)

    # ── Metrics row ──────────────────────────────────────────────────────────
    metrics_html = (
        '<div class="lp-metrics">'
          '<div class="lp-metric"><div class="lp-metric-val">9</div><div class="lp-metric-lbl">Analytics Tabs</div></div>'
          '<div class="lp-metric"><div class="lp-metric-val">5+</div><div class="lp-metric-lbl">Indices Supported</div></div>'
          '<div class="lp-metric"><div class="lp-metric-val">30+</div><div class="lp-metric-lbl">F&amp;O Stocks</div></div>'
          '<div class="lp-metric"><div class="lp-metric-val">Real-time</div><div class="lp-metric-lbl">Dhan API &middot; Smart Cache</div></div>'
        '</div>'
    )
    st.markdown(metrics_html, unsafe_allow_html=True)

    # ── Features grid ────────────────────────────────────────────────────────
    features = [
        ("🎯", "GEX Analytics",            "Standard + Enhanced OI GEX with dealer flip zones, cascade mathematics &amp; VANNA integration"),
        ("🌊", "VANNA Cascade",             "Flip zone detection &middot; IV-regime-aware breakout probability &middot; Vacuum / Support / Trap Door roles"),
        ("⚡", "Volume Spike Detection",    "Z-score spike engine &middot; Confirmed Bullish / Bearish / Divergence &middot; GEX coincidence panel"),
        ("🚀", "Enhanced OI GEX",           "OI change &times; Greeks &times; Volume &times; IV &times; Distance &middot; Purple/Gold bars &middot; Near-spot spike monitor"),
        ("📊", "Cascade Mathematics",       "Per-instrument calibrated scalars &middot; VANNA floor absorption &middot; Dealer flow bias card"),
        ("🏦", "Institutional Signals",     "VANNA concentration &middot; CoG drift clock &middot; Call/Put asymmetry &middot; Block position detection"),
        ("📡", "Smart Caching",             "Incremental live updates &middot; Historical mode &middot; TOTP auto-token &middot; Dhan rolling options API"),
        ("✏️", "Drawing Tools",             "Freehand lines &middot; circles &middot; rectangles &middot; open/closed paths on every chart"),
    ]
    feat_cards = "".join(
        f'<div class="lp-feature">'
        f'<div class="lp-feature-icon">{icon}</div>'
        f'<div class="lp-feature-title">{title}</div>'
        f'<div class="lp-feature-desc">{desc}</div>'
        f'</div>'
        for icon, title, desc in features
    )
    st.markdown('<div class="lp-section-label">&#9889; Platform Features</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="lp-features">{feat_cards}</div>', unsafe_allow_html=True)

    # ── Founder card ─────────────────────────────────────────────────────────
    tags = [
        ("lp-tag-purple", "PhD Finance"),
        ("lp-tag-white",  "DPIIT Registered"),
        ("lp-tag-purple", "Options Analytics"),
        ("lp-tag-white",  "Startup India"),
        ("lp-tag-purple", "Malayalam YouTube"),
        ("lp-tag-white",  "ICSSR Research"),
    ]
    tags_html = "".join(
        '<span class="lp-tag {}">{}</span>'.format(cls, label)
        for cls, label in tags
    )
    founder_parts = [
        '<div class="lp-section-label">&#128100; About the Creator</div>',
        '<div class="lp-founder">',
        '<img src="{}" class="lp-avatar-img" alt="NYZTrade">'.format(logo_src),
        '<div>',
        '<div class="lp-founder-name">Dr. Niyas N</div>',
        '<div class="lp-founder-role">Founder &amp; Chief Research Officer &middot; NYZTrade Analytics</div>',
        '<div class="lp-founder-bio">',
        'PhD in Finance (Company Valuation &amp; Stock Market Studies) &middot; ICSSR-sponsored research.<br>',
        'Built India&#39;s first retail-grade GEX/VANNA/DEX analytics platform for NSE/BSE FNO markets.<br>',
        'Creator of NYZTrade YouTube &mdash; Malayalam-language options education for Kerala traders.<br>',
        'Active community: 5,000+ traders via Telegram &amp; WhatsApp.',
        '</div>',
        '<div class="lp-tags">{}</div>'.format(tags_html),
        '</div>',
        '</div>',
    ]
    st.markdown("".join(founder_parts), unsafe_allow_html=True)

    # ── Enter button ─────────────────────────────────────────────────────────
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        entered = st.button(
            "🚀  Enter Dashboard  →",
            use_container_width=True,
            type="primary",
            key="lp_enter_button",
        )

    st.markdown(
        '<div class="lp-disclaimer">&#9888;&#65039; For educational and research purposes only. '
        'Not financial advice. &nbsp;&middot;&nbsp; '
        '&copy; 2026 NYZTrade Analytics. All rights reserved.</div>',
        unsafe_allow_html=True,
    )
    return entered



# ============================================================================
# MAIN APP
# ============================================================================

# ============================================================================
# CLOSING WINDOW IV SIGNAL (3:00–3:15 PM → Next Day Bias)
# Empirically validated: EXPANDING IV → 75% BEAR accuracy next morning
# ============================================================================

# Historical accuracy lookup (validated on 430 trades, 203 days)
# Accuracy = next-morning BEAR direction correct (spot moved bearishly).
# BULL accuracy suppressed across all regimes by dataset stop-system bias
# (median stop-out at -51pts regardless of direction).
# gap_down_pct = actual days market gapped DOWN — more reliable than trade accuracy.
# Only EXPANDING->BEARISH is a clean, stop-bias-free directional signal.
_CLOSING_WINDOW_STATS = {
    "EXPANDING":   {
        "bear_acc": 75.0, "bull_acc": 43.0,
        "gap_pts": -17.5, "gap_up_pct": 41.4, "gap_down_pct": 58.9,
        "strength": "STRONG", "color": "#ef4444", "icon": "🔴",
        "bias": "BEARISH",
        "note": "Clean signal: 58.9% of days market gaps DOWN — confirms bear bias",
    },
    "COMPRESSING": {
        "bear_acc": 58.0, "bull_acc": 35.0,
        "gap_pts": +11.0, "gap_up_pct": 56.6, "gap_down_pct": 43.4,
        "strength": "WEAK", "color": "#f59e0b", "icon": "🟡",
        "bias": "MILD_BULLISH",
        "note": "Gap favors UP (56.6% days) but bull trade accuracy unreliable — stop bias in dataset",
    },
    "FLAT": {
        "bear_acc": 57.0, "bull_acc": 30.0,
        "gap_pts": +24.6, "gap_up_pct": 60.0, "gap_down_pct": 40.0,
        "strength": "NONE", "color": "#94a3b8", "icon": "⬜",
        "bias": "NEUTRAL",
        "note": "No reliable directional signal — wait for open confirmation",
    },
}

def compute_closing_window_signal(df: pd.DataFrame, unit_label: str) -> dict:
    """
    Compute the dominant IV regime and average VANNA breakout probability
    in the 3:00–3:15 PM window from today's data.
    Returns dict with regime, probabilities, and next-day bias.
    """
    if df is None or len(df) == 0:
        return {}

    # Filter to 3:00–3:15 PM timestamps
    try:
        ts_col = df["timestamp"].dt
        window_df = df[
            (ts_col.hour == 15) & (ts_col.minute <= 15)
        ].copy()
    except Exception:
        return {}

    if len(window_df) == 0:
        return {"status": "NO_DATA", "message": "No data in 3:00–3:15 PM window yet"}

    # Dominant IV regime in window
    iv_col = None
    for c in ["iv_regime", "IV Regime", "iv_regime_label"]:
        if c in window_df.columns:
            iv_col = c; break

    if iv_col:
        regime_counts = window_df[iv_col].value_counts()
        dominant_iv   = regime_counts.index[0]
        regime_pct    = regime_counts.iloc[0] / len(window_df) * 100
    else:
        # Derive from call_iv vs put_iv trend
        if "call_iv" in window_df.columns and "put_iv" in window_df.columns:
            avg_iv   = (window_df["call_iv"] + window_df["put_iv"]).mean() / 2
            first_iv = (window_df["call_iv"].iloc[0] + window_df["put_iv"].iloc[0]) / 2
            last_iv  = (window_df["call_iv"].iloc[-1] + window_df["put_iv"].iloc[-1]) / 2
            iv_change = last_iv - first_iv
            if iv_change > 0.5:
                dominant_iv = "EXPANDING"
            elif iv_change < -0.5:
                dominant_iv = "COMPRESSING"
            else:
                dominant_iv = "FLAT"
            regime_pct = abs(iv_change) * 10
        else:
            dominant_iv = "FLAT"; regime_pct = 0.0

    # Average net GEX in window (directional lean)
    net_gex_avg = window_df["net_gex"].mean() if "net_gex" in window_df.columns else 0.0

    # Average VANNA (directional pressure)
    net_vanna_avg = window_df["net_vanna"].mean() if "net_vanna" in window_df.columns else 0.0

    # Timestamps in window
    n_bars = window_df["timestamp"].nunique()

    stats = _CLOSING_WINDOW_STATS.get(dominant_iv, _CLOSING_WINDOW_STATS["FLAT"])

    # Adjust confidence based on how many bars we have in window
    if n_bars >= 3:
        confidence = "HIGH"
    elif n_bars >= 1:
        confidence = "MODERATE"
    else:
        confidence = "LOW"

    return {
        "status":        "OK",
        "dominant_iv":   dominant_iv,
        "regime_pct":    regime_pct,
        "n_bars":        n_bars,
        "net_gex_avg":   net_gex_avg,
        "net_vanna_avg": net_vanna_avg,
        "bear_acc":      stats["bear_acc"],
        "bull_acc":      stats["bull_acc"],
        "gap_pts":       stats["gap_pts"],
        "gap_up_pct":    stats["gap_up_pct"],
        "strength":      stats["strength"],
        "color":         stats["color"],
        "icon":          stats["icon"],
        "bias":          stats["bias"],
        "confidence":    confidence,
    }


def render_closing_window_box(signal: dict) -> None:
    """Render the 3:00-3:15 PM closing window IV signal box."""
    if not signal or signal.get("status") == "NO_DATA":
        st.markdown(
            '<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.2);'
            'border-radius:10px;padding:12px 16px;margin-top:10px;text-align:center;">'
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.78rem;color:#64748b;">'
            '&#x23F3; 3:00&#x2013;3:15 PM Closing Window Signal available after 3:00 PM</span></div>',
            unsafe_allow_html=True,
        )
        return

    iv           = signal["dominant_iv"]
    color        = signal["color"]
    icon         = signal["icon"]
    bias         = signal["bias"]
    bear_acc     = signal["bear_acc"]
    bull_acc     = signal["bull_acc"]
    gap_pts      = signal["gap_pts"]
    gap_up       = signal["gap_up_pct"]
    gap_down     = signal.get("gap_down_pct", 100 - gap_up)
    strength     = signal["strength"]
    conf         = signal["confidence"]
    n_bars       = signal["n_bars"]
    net_gex      = signal["net_gex_avg"]
    net_vanna    = signal["net_vanna_avg"]
    signal_note  = signal.get("note", "")

    strength_color = {"STRONG": "#10b981", "MODERATE": "#f59e0b", "WEAK": "#ef4444", "NONE": "#64748b"}[strength]
    conf_color     = {"HIGH": "#10b981", "MODERATE": "#f59e0b", "LOW": "#64748b"}[conf]
    gap_color      = "#ef4444" if gap_pts < 0 else "#10b981"
    gap_arrow      = "&#x2193;" if gap_pts < 0 else "&#x2191;"
    gap_pct_val    = gap_down if gap_pts < 0 else gap_up
    gap_dir_label  = "DOWN" if gap_pts < 0 else "UP"
    gex_color      = "#10b981" if net_gex > 0 else "#ef4444"
    vanna_color    = "#10b981" if net_vanna > 0 else "#ef4444"

    bias_label_map = {
        "BEARISH":      "&#x1F534; BEARISH NEXT OPEN",
        "MILD_BULLISH": "&#x1F7E1; MILD BULLISH BIAS",
        "BULLISH":      "&#x1F7E2; BULLISH NEXT OPEN",
        "NEUTRAL":      "&#x2B1C; NEUTRAL / WAIT",
    }
    bias_label = bias_label_map.get(bias, "&#x2B1C; NEUTRAL")

    parts = [
        '<div style="background:rgba(15,23,42,0.85);border:1.5px solid {}55;border-radius:12px;padding:14px 18px;margin-top:12px;">'.format(color),
        # Header
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:rgba(192,132,252,0.7);text-transform:uppercase;letter-spacing:0.1em;">&#x23F0; 3:00&#x2013;3:15 PM Closing Window Signal</span>',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#64748b;">{} bars &nbsp;|&nbsp; Conf: <b style="color:{};">{}</b></span>'.format(n_bars, conf_color, conf),
        '</div>',
        # Main row
        '<div style="display:flex;gap:10px;align-items:stretch;margin-bottom:10px;flex-wrap:wrap;">',
        # IV pill
        '<div style="flex:1;min-width:110px;padding:10px 12px;background:{0}22;border:1px solid {0}55;border-radius:8px;text-align:center;">'.format(color),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;margin-bottom:4px;">IV REGIME</div>',
        '<div style="font-size:1.0rem;font-weight:700;color:{};font-family:Space Grotesk,sans-serif;">{} {}</div>'.format(color, icon, iv),
        '</div>',
        # Bias
        '<div style="flex:1.5;min-width:150px;padding:10px 12px;background:{0}18;border:2px solid {0}66;border-radius:8px;text-align:center;">'.format(color),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;margin-bottom:4px;">NEXT DAY BIAS</div>',
        '<div style="font-size:0.90rem;font-weight:800;color:{};font-family:Space Grotesk,sans-serif;">{}</div>'.format(color, bias_label),
        '<div style="font-size:0.62rem;color:#64748b;margin-top:2px;">Signal: <b style="color:{};">{}</b></div>'.format(strength_color, strength),
        '</div>',
        # Accuracy
        '<div style="flex:1;min-width:110px;padding:10px 12px;background:rgba(15,23,42,0.5);border:1px solid rgba(148,163,184,0.15);border-radius:8px;text-align:center;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;margin-bottom:4px;">HIST. ACCURACY</div>',
        '<div style="font-size:0.80rem;font-family:JetBrains Mono,monospace;">&#x1F4C9; BEAR <b style="color:#ef4444;">{:.0f}%</b> &nbsp; &#x1F4C8; BULL <b style="color:#10b981;">{:.0f}%</b></div>'.format(bear_acc, bull_acc),
        '<div style="font-size:0.63rem;color:#64748b;margin-top:3px;">n=203 days backtest</div>',
        '</div>',
        '</div>',
        # Bottom metrics row
        '<div style="display:flex;gap:8px;flex-wrap:wrap;">',
        '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(15,23,42,0.5);border:1px solid rgba(148,163,184,0.12);border-radius:6px;">',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;">Expected Gap </span>',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.80rem;font-weight:700;color:{};">{} {:.1f} pts &nbsp;|&nbsp; {:.0f}% days gap {}</span>'.format(gap_color, gap_arrow, abs(gap_pts), gap_pct_val, gap_dir_label),
        '</div>',
        '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(15,23,42,0.5);border:1px solid rgba(148,163,184,0.12);border-radius:6px;">',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;">Window Net GEX </span>',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.80rem;font-weight:700;color:{};">{:+.3f}B</span>'.format(gex_color, net_gex),
        '</div>',
        '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(15,23,42,0.5);border:1px solid rgba(148,163,184,0.12);border-radius:6px;">',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;">Window Net VANNA </span>',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.80rem;font-weight:700;color:{};">{:+.3f}B</span>'.format(vanna_color, net_vanna),
        '</div>',
        '</div>',
    ]

    if signal_note:
        parts.append('<div style="margin-top:6px;font-family:JetBrains Mono,monospace;font-size:0.67rem;color:#f59e0b;padding:5px 8px;background:rgba(245,158,11,0.07);border-radius:4px;">&#x1F50D; {}</div>'.format(signal_note))

    parts.append(
        '<div style="margin-top:6px;font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#475569;">'
        '&#9888;&#65039; IV resets at open &#x2014; confirm fresh reading before entry. '
        'Based on 430 trades / 203 days (Apr 2025&#x2013;Apr 2026). '
        'BULL accuracy suppressed by dataset stop-bias &#x2014; use gap % for bullish reads.'
        '</div>'
    )
    parts.append('</div>')

    st.markdown("".join(parts), unsafe_allow_html=True)


# ============================================================================
# INTRADAY IV REGIME SIGNAL ACCURACY PANEL
# Empirically validated on 1,050 trades (Apr 2025–Apr 2026)
# ============================================================================

# Signal lookup: {IV_Regime: {session: {dir: accuracy%, note, strength}}}
# Sessions: MORNING=9–11AM, MIDDAY=11AM–1PM, AFTERNOON=1–3:30PM
# Source: 1,050 trades backtest — spot_correct = market moved in trade direction
_IV_SIGNAL_TABLE = {
    "EXPANDING": {
        "MORNING":   {
            "BEAR": {"acc": 61.7, "n": 115, "strength": "MODERATE", "color": "#ef4444"},
            "BULL": {"acc": 20.4, "n": 157, "strength": "AVOID",    "color": "#dc2626"},
            "note": "BULL trades fail 79.6% — structural bear regime at open",
        },
        "MIDDAY": {
            "BEAR": {"acc": 83.8, "n": 37,  "strength": "STRONG",   "color": "#ef4444"},
            "BULL": {"acc": 25.0, "n": 40,  "strength": "AVOID",    "color": "#dc2626"},
            "note": "Strongest bear window of the day — 83.8% BEAR accuracy",
        },
        "AFTERNOON": {
            "BEAR": {"acc": 48.3, "n": 29,  "strength": "WEAK",     "color": "#f59e0b"},
            "BULL": {"acc": 24.4, "n": 41,  "strength": "AVOID",    "color": "#dc2626"},
            "note": "Signal weakens — avoid new positions after 1PM in EXPANDING",
        },
    },
    "COMPRESSING": {
        "MORNING": {
            "BEAR": {"acc": 57.4, "n": 141, "strength": "MODERATE", "color": "#f59e0b"},
            "BULL": {"acc": 63.6, "n": 99,  "strength": "MODERATE", "color": "#10b981"},
            "note": "BULL favored 9–10AM (63.6%) — IV compression = dealer buyback",
        },
        "MIDDAY": {
            "BEAR": {"acc": 68.6, "n": 35,  "strength": "STRONG",   "color": "#ef4444"},
            "BULL": {"acc": 69.6, "n": 23,  "strength": "STRONG",   "color": "#10b981"},
            "note": "Both directions reliable — follow GEX cascade for bias",
        },
        "AFTERNOON": {
            "BEAR": {"acc": 46.9, "n": 64,  "strength": "WEAK",     "color": "#f59e0b"},
            "BULL": {"acc": 84.6, "n": 13,  "strength": "STRONG",   "color": "#10b981"},
            "note": "BULL strongly favored 1–3PM with Support Floor + COMPRESSING (84.6% WR, Sharpe 96.5) — highest conviction CALL setup",
        },
    },
    "FLAT": {
        "MORNING": {
            "BEAR": {"acc": 82.7, "n": 75,  "strength": "STRONG",   "color": "#ef4444"},
            "BULL": {"acc": 39.7, "n": 63,  "strength": "WEAK",     "color": "#f59e0b"},
            "note": "FLAT IV morning = strongest bear window (82.7%) — no hedging noise",
        },
        "MIDDAY": {
            "BEAR": {"acc": 60.9, "n": 23,  "strength": "MODERATE", "color": "#ef4444"},
            "BULL": {"acc": 16.7, "n": 18,  "strength": "AVOID",    "color": "#dc2626"},
            "note": "BEAR still dominant midday — BULL extremely unreliable",
        },
        "AFTERNOON": {
            "BEAR": {"acc": 50.0, "n": 20,  "strength": "WEAK",     "color": "#94a3b8"},
            "BULL": {"acc": 66.7, "n": 18,  "strength": "MODERATE", "color": "#10b981"},
            "note": "Regime flips — BULL gains edge after 1PM in FLAT IV",
        },
    },
}

# Top pinpoint signals from 30-min bucket analysis
_IV_TOP_SIGNALS = [
    ("10:00", "FLAT",        "BEAR", 91.7, 12),
    ("12:00", "EXPANDING",   "BEAR", 90.0, 10),
    ("10:30", "EXPANDING",   "BEAR", 83.3, 12),
    ("11:00", "EXPANDING",   "BEAR", 83.3, 12),
    ("11:30", "COMPRESSING", "BEAR", 81.8, 11),
    ("9:00",  "FLAT",        "BEAR", 81.2, 32),
    ("9:30",  "FLAT",        "BEAR", 78.3, 23),
    ("10:00", "COMPRESSING", "BULL", 76.9, 13),
    ("14:00", "COMPRESSING", "BULL", 76.9, 13),
    ("13:00", "COMPRESSING", "BULL", 84.6, 13),  # Floor+COMP 13-15h — highest Sharpe (96.5), confirmed by backtest
    ("9:30",  "COMPRESSING", "BULL", 69.2, 39),
    ("9:30",  "COMPRESSING", "BEAR", 67.9, 53),
    ("9:30",  "EXPANDING",   "BEAR", 67.5, 40),
]


def get_session_label(hour: int, minute: int) -> str:
    mins = hour * 60 + minute
    if mins < 11 * 60:
        return "MORNING"
    elif mins < 13 * 60:
        return "MIDDAY"
    else:
        return "AFTERNOON"


def render_iv_regime_signal_panel(df: pd.DataFrame, unit_label: str) -> None:
    """
    Renders the IV Regime Intraday Signal Accuracy panel inside Tab 0.
    Shows live IV regime + empirical accuracy for current session window.
    """
    try:
        iv_df = compute_iv_trend(df)
    except Exception:
        st.info("IV signal panel: unable to compute IV trend from current data.")
        return

    if iv_df.empty:
        return

    # Current IV regime (latest bar)
    latest      = iv_df.iloc[-1]
    current_iv  = str(latest.get("iv_regime", "FLAT"))
    current_ts  = latest.get("timestamp", None)
    avg_iv_val  = float(latest.get("avg_iv",  15.0))
    iv_slope    = float(latest.get("iv_slope",  0.0))
    iv_skew     = float(latest.get("iv_skew",   0.0))

    # Current session
    if current_ts is not None:
        try:
            hr  = pd.Timestamp(current_ts).hour
            mn  = pd.Timestamp(current_ts).minute
        except Exception:
            hr, mn = 12, 0
    else:
        from datetime import datetime
        import pytz
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
        hr, mn = now.hour, now.minute

    session = get_session_label(hr, mn)
    session_labels = {"MORNING": "Morning  9–11AM",
                      "MIDDAY":  "Midday  11AM–1PM",
                      "AFTERNOON": "Afternoon  1–3:30PM"}
    session_disp = session_labels.get(session, session)

    iv_color = {"EXPANDING": "#ef4444", "COMPRESSING": "#10b981", "FLAT": "#94a3b8"}.get(current_iv, "#94a3b8")
    iv_icon  = {"EXPANDING": "&#x1F4C8;", "COMPRESSING": "&#x1F4C9;", "FLAT": "&#x27A1;"}.get(current_iv, "&#x27A1;")

    sig = _IV_SIGNAL_TABLE.get(current_iv, {}).get(session, {})
    bear_sig = sig.get("BEAR", {"acc": 50, "n": 0, "strength": "UNKNOWN", "color": "#94a3b8"})
    bull_sig = sig.get("BULL", {"acc": 50, "n": 0, "strength": "UNKNOWN", "color": "#94a3b8"})
    note     = sig.get("note", "")

    strength_cfg = {
        "STRONG":   ("STRONG",   "#10b981", "&#x2705;"),
        "MODERATE": ("MODERATE", "#f59e0b", "&#x26A0;&#xFE0F;"),
        "WEAK":     ("WEAK",     "#64748b", "&#x26AA;"),
        "AVOID":    ("AVOID",    "#dc2626", "&#x274C;"),
        "UNKNOWN":  ("?",        "#475569", "&#x2753;"),
    }

    bear_str_lbl, bear_str_col, bear_str_ic = strength_cfg.get(bear_sig["strength"], strength_cfg["UNKNOWN"])
    bull_str_lbl, bull_str_col, bull_str_ic = strength_cfg.get(bull_sig["strength"], strength_cfg["UNKNOWN"])

    skew_color  = "#10b981" if iv_skew > 0 else "#ef4444"
    slope_color = "#ef4444" if iv_slope > 0 else "#10b981"

    # ── Check 30-min pinpoint signals ────────────────────────────────────────
    time_str    = f"{hr:02d}:{(mn // 30) * 30:02d}"
    pinpoint    = [s for s in _IV_TOP_SIGNALS if s[0] == time_str and s[1] == current_iv]

    # ── Render ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### &#x1F9EA; IV Regime Signal Accuracy — Live Intraday Context")

    # Row 1: Header cards
    h1, h2, h3, h4 = st.columns([1.2, 1, 1, 1.2])

    with h1:
        parts = [
            '<div style="background:{}22;border:1.5px solid {}66;border-radius:10px;padding:12px 14px;text-align:center;height:100%;">'.format(iv_color, iv_color),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">Live IV Regime</div>',
            '<div style="font-size:1.4rem;font-weight:800;color:{};font-family:Space Grotesk,sans-serif;">{} {}</div>'.format(iv_color, iv_icon, current_iv),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#64748b;margin-top:4px;">Avg IV: <b style="color:#e2e8f0;">{:.1f}%</b></div>'.format(avg_iv_val),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    with h2:
        parts = [
            '<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.15);border-radius:10px;padding:12px 14px;text-align:center;height:100%;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">Session</div>',
            '<div style="font-size:0.82rem;font-weight:700;color:#e2e8f0;font-family:Space Grotesk,sans-serif;">&#x1F552; {}</div>'.format(session_disp),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    with h3:
        parts = [
            '<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.15);border-radius:10px;padding:12px 14px;text-align:center;height:100%;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">IV Slope</div>',
            '<div style="font-size:1.0rem;font-weight:700;color:{};font-family:JetBrains Mono,monospace;">{:+.2f}</div>'.format(slope_color, iv_slope),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;">Skew: <b style="color:{};">{:+.1f}%</b></div>'.format(skew_color, iv_skew),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    with h4:
        parts = [
            '<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.15);border-radius:10px;padding:12px 14px;text-align:center;height:100%;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;">Backtest Base</div>',
            '<div style="font-size:0.82rem;font-weight:700;color:#c4b5fd;font-family:JetBrains Mono,monospace;">1,050 trades</div>',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;">Apr 2025 &#x2013; Apr 2026</div>',
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    # Row 2: BEAR vs BULL signal cards
    b1, b2 = st.columns(2)

    with b1:
        bar_w = min(bear_sig["acc"], 100)
        parts = [
            '<div style="background:rgba(239,68,68,0.07);border:1.5px solid {}55;border-radius:10px;padding:14px 16px;">'.format(bear_sig["color"]),
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">',
            '<span style="font-family:Space Grotesk,sans-serif;font-size:0.88rem;font-weight:700;color:#ef4444;">&#x1F43B; BEAR Signal</span>',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:{};font-weight:600;">{} {} &nbsp;(n={})</span>'.format(bear_str_col, bear_str_ic, bear_str_lbl, bear_sig["n"]),
            '</div>',
            '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">',
            '<span style="font-size:2.2rem;font-weight:800;color:{};font-family:Space Grotesk,sans-serif;">{:.1f}%</span>'.format(bear_sig["color"], bear_sig["acc"]),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#64748b;">directional accuracy</span>',
            '</div>',
            '<div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;margin-bottom:8px;">',
            '<div style="background:{};width:{:.0f}%;height:6px;border-radius:4px;transition:width 0.5s;"></div>'.format(bear_sig["color"], bar_w),
            '</div>',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#94a3b8;line-height:1.5;">{} + {} + BEAR &rarr; <b style="color:{}">{:.1f}%</b> of time market moved bearishly</div>'.format(current_iv, session_disp.split()[0], bear_sig["color"], bear_sig["acc"]),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    with b2:
        bar_w2 = min(bull_sig["acc"], 100)
        parts = [
            '<div style="background:rgba(16,185,129,0.07);border:1.5px solid {}55;border-radius:10px;padding:14px 16px;">'.format(bull_sig["color"]),
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">',
            '<span style="font-family:Space Grotesk,sans-serif;font-size:0.88rem;font-weight:700;color:#10b981;">&#x1F402; BULL Signal</span>',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:{};font-weight:600;">{} {} &nbsp;(n={})</span>'.format(bull_str_col, bull_str_ic, bull_str_lbl, bull_sig["n"]),
            '</div>',
            '<div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">',
            '<span style="font-size:2.2rem;font-weight:800;color:{};font-family:Space Grotesk,sans-serif;">{:.1f}%</span>'.format(bull_sig["color"], bull_sig["acc"]),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#64748b;">directional accuracy</span>',
            '</div>',
            '<div style="background:rgba(255,255,255,0.06);border-radius:4px;height:6px;margin-bottom:8px;">',
            '<div style="background:{};width:{:.0f}%;height:6px;border-radius:4px;transition:width 0.5s;"></div>'.format(bull_sig["color"], bar_w2),
            '</div>',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#94a3b8;line-height:1.5;">{} + {} + BULL &rarr; <b style="color:{}">{:.1f}%</b> of time market moved bullishly</div>'.format(current_iv, session_disp.split()[0], bull_sig["color"], bull_sig["acc"]),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    # Row 3: Note + pinpoint signal
    note_parts = [
        '<div style="margin-top:8px;background:rgba(124,58,237,0.08);border-left:3px solid #7c3aed;border-radius:0 6px 6px 0;padding:8px 12px;">',
        '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#c4b5fd;">&#x1F4A1; {}</span>'.format(note),
        '</div>',
    ]
    st.markdown("".join(note_parts), unsafe_allow_html=True)

    if pinpoint:
        pin = pinpoint[0]
        pin_color = "#ef4444" if pin[2] == "BEAR" else "#10b981"
        pin_parts = [
            '<div style="margin-top:6px;background:rgba(251,191,36,0.08);border-left:3px solid #fbbf24;border-radius:0 6px 6px 0;padding:8px 12px;">',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#fbbf24;">',
            '&#x1F3AF; Pinpoint signal active: <b>{} {} {}</b> &rarr; <b style="color:{};">{:.1f}% accuracy</b> (n={})'.format(
                pin[0], pin[1], pin[2], pin_color, pin[3], pin[4]),
            '</span></div>',
        ]
        st.markdown("".join(pin_parts), unsafe_allow_html=True)

    # Row 4: Full accuracy heatmap table
    with st.expander("&#x1F4CA; Full Session Accuracy Table — All IV Regimes", expanded=False):
        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;color:#94a3b8;margin-bottom:8px;">'
            'Directional accuracy (%) from 1,050 backtest trades. Higher = market moved in that direction more reliably.'
            '</div>',
            unsafe_allow_html=True,
        )
        rows_data = []
        for iv_r in ["EXPANDING", "COMPRESSING", "FLAT"]:
            for sess in ["MORNING", "MIDDAY", "AFTERNOON"]:
                s = _IV_SIGNAL_TABLE[iv_r][sess]
                rows_data.append({
                    "IV Regime": iv_r,
                    "Session":   sess,
                    "BEAR Acc%": s["BEAR"]["acc"],
                    "BEAR n":    s["BEAR"]["n"],
                    "BEAR Signal": s["BEAR"]["strength"],
                    "BULL Acc%": s["BULL"]["acc"],
                    "BULL n":    s["BULL"]["n"],
                    "BULL Signal": s["BULL"]["strength"],
                    "Note":      s["note"],
                })
        import pandas as _pd_local
        tbl = _pd_local.DataFrame(rows_data)

        def _heat(val, col):
            if "Acc" not in col: return ""
            v = float(val)
            if v >= 75: return "background-color:rgba(16,185,129,0.25);color:#6ee7b7;"
            if v >= 65: return "background-color:rgba(16,185,129,0.12);color:#a7f3d0;"
            if v >= 55: return "background-color:rgba(245,158,11,0.12);color:#fcd34d;"
            if v  < 35: return "background-color:rgba(239,68,68,0.15);color:#fca5a5;"
            return ""

        styled = tbl.style.apply(
            lambda col: [_heat(v, col.name) for v in col], axis=0
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#475569;margin-top:6px;">'
            '&#9888;&#65039; Accuracy = spot moved in trade direction. BULL accuracy in EXPANDING IV '
            'is structurally suppressed (21.8% overall) — market moves bearishly 76.9% of the time when IV expands. '
            'Use gap direction (not trade win rate) for bullish reads.'
            '</div>',
            unsafe_allow_html=True,
        )


# ============================================================================
# STRATEGY FINDER + BUILDER — HedGEX Options Strategy Engine
# ============================================================================

from scipy.stats import norm as _scipy_norm
import math as _math

# ── Strategy definitions ─────────────────────────────────────────────────────
_STRATEGIES = {
    "Bear Put Spread":   {"legs": 2, "type": "DEBIT",  "dir": "BEAR", "vol": "NEUTRAL"},
    "Bull Call Spread":  {"legs": 2, "type": "DEBIT",  "dir": "BULL", "vol": "NEUTRAL"},
    "Long Put":          {"legs": 1, "type": "DEBIT",  "dir": "BEAR", "vol": "BULL"},
    "Long Call":         {"legs": 1, "type": "DEBIT",  "dir": "BULL", "vol": "BULL"},
    "Bear Call Spread":  {"legs": 2, "type": "CREDIT", "dir": "BEAR", "vol": "BEAR"},
    "Bull Put Spread":   {"legs": 2, "type": "CREDIT", "dir": "BULL", "vol": "BEAR"},
    "Iron Condor":       {"legs": 4, "type": "CREDIT", "dir": "NEUTRAL", "vol": "BEAR"},
    "Iron Butterfly":    {"legs": 4, "type": "CREDIT", "dir": "NEUTRAL", "vol": "BEAR"},
    "Short Strangle":    {"legs": 2, "type": "CREDIT", "dir": "NEUTRAL", "vol": "BEAR"},
    "Long Straddle":     {"legs": 2, "type": "DEBIT",  "dir": "NEUTRAL", "vol": "BULL"},
    "Long Strangle":     {"legs": 2, "type": "DEBIT",  "dir": "NEUTRAL", "vol": "BULL"},
    "Synthetic Future":  {"legs": 2, "type": "DEBIT",  "dir": "BULL",   "vol": "NEUTRAL"},
    "Calendar Spread":   {"legs": 2, "type": "DEBIT",  "dir": "NEUTRAL", "vol": "BULL"},
    "Ratio Put Spread":  {"legs": 2, "type": "CREDIT", "dir": "BEAR",   "vol": "NEUTRAL"},
    "Ratio Call Spread": {"legs": 2, "type": "CREDIT", "dir": "BULL",   "vol": "NEUTRAL"},
}

# Regime → strategy fit scoring
_REGIME_FIT = {
    # (iv_regime, gex_bias, cascade_direction) → {strategy: score 0-3}
    ("EXPANDING", "BEAR", "BEAR"): {
        "Bear Put Spread": 3, "Long Put": 3, "Bear Call Spread": 2,
        "Ratio Put Spread": 2, "Long Straddle": 1,
        "Iron Condor": 0, "Short Strangle": 0, "Bull Call Spread": 0,
        "Bull Put Spread": 0, "Iron Butterfly": 0,
    },
    ("EXPANDING", "BULL", "BULL"): {
        "Bull Call Spread": 3, "Long Call": 3, "Bull Put Spread": 2,
        "Ratio Call Spread": 2, "Long Straddle": 1,
        "Iron Condor": 0, "Short Strangle": 0, "Bear Put Spread": 0,
        "Bear Call Spread": 0, "Iron Butterfly": 0,
    },
    ("COMPRESSING", "BEAR", "BEAR"): {
        "Bear Call Spread": 3, "Bear Put Spread": 2, "Iron Condor": 2,
        "Short Strangle": 2, "Iron Butterfly": 1, "Long Straddle": 0,
    },
    ("COMPRESSING", "BULL", "BULL"): {
        "Bull Put Spread": 3, "Bull Call Spread": 2, "Iron Condor": 2,
        "Short Strangle": 2, "Iron Butterfly": 1, "Long Straddle": 0,
    },
    ("COMPRESSING", "NEUTRAL", "NEUTRAL"): {
        "Iron Condor": 3, "Short Strangle": 3, "Iron Butterfly": 2,
        "Bull Put Spread": 1, "Bear Call Spread": 1, "Long Straddle": 0,
    },
    ("FLAT", "BEAR", "BEAR"): {
        "Bear Put Spread": 3, "Bear Call Spread": 2, "Long Put": 2,
        "Iron Condor": 1, "Short Strangle": 1,
    },
    ("FLAT", "BULL", "BULL"): {
        "Bull Call Spread": 3, "Bull Put Spread": 2, "Long Call": 2,
        "Iron Condor": 1, "Short Strangle": 1,
    },
    ("FLAT", "NEUTRAL", "NEUTRAL"): {
        "Iron Condor": 3, "Short Strangle": 2, "Iron Butterfly": 2,
        "Calendar Spread": 2, "Long Straddle": 1,
    },
    ("EXPANDING", "NEUTRAL", "NEUTRAL"): {
        "Long Straddle": 3, "Long Strangle": 3, "Long Put": 1, "Long Call": 1,
        "Iron Condor": 0, "Short Strangle": 0,
    },
}


def _bs_price(S, K, T, r, sigma, opt_type="CE"):
    """Black-Scholes option price."""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if opt_type == "CE" else max(K - S, 0)
        return float(intrinsic)
    d1 = (_math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * _math.sqrt(T))
    d2 = d1 - sigma * _math.sqrt(T)
    if opt_type == "CE":
        return float(S * _scipy_norm.cdf(d1) - K * _math.exp(-r * T) * _scipy_norm.cdf(d2))
    else:
        return float(K * _math.exp(-r * T) * _scipy_norm.cdf(-d2) - S * _scipy_norm.cdf(-d1))


def _bs_greeks(S, K, T, r, sigma, opt_type="CE"):
    """Black-Scholes Greeks."""
    if T <= 0 or sigma <= 0:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "iv": sigma}
    d1 = (_math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * _math.sqrt(T))
    d2 = d1 - sigma * _math.sqrt(T)
    pdf_d1 = _scipy_norm.pdf(d1)
    gamma  = pdf_d1 / (S * sigma * _math.sqrt(T))
    vega   = S * pdf_d1 * _math.sqrt(T) / 100
    if opt_type == "CE":
        delta = _scipy_norm.cdf(d1)
        theta = (-(S * pdf_d1 * sigma) / (2 * _math.sqrt(T))
                 - r * K * _math.exp(-r * T) * _scipy_norm.cdf(d2)) / 365
    else:
        delta = _scipy_norm.cdf(d1) - 1
        theta = (-(S * pdf_d1 * sigma) / (2 * _math.sqrt(T))
                 + r * K * _math.exp(-r * T) * _scipy_norm.cdf(-d2)) / 365
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "iv": sigma}


def compute_strategy_payoff(legs, spot_range, lot_size=1):
    """
    Compute P&L across spot range for a multi-leg strategy.
    legs: list of {"strike": K, "opt_type": CE/PE, "action": BUY/SELL,
                   "premium": px, "qty": n, "lot_size": ls}
    Returns list of (spot, pnl) tuples.
    """
    results = []
    for spot in spot_range:
        pnl = 0.0
        for leg in legs:
            K   = leg["strike"]
            typ = leg["opt_type"]
            act = leg["action"]
            px  = leg["premium"]
            qty = leg["qty"]
            ls  = leg.get("lot_size", lot_size)
            intrinsic = max(spot - K, 0) if typ == "CE" else max(K - spot, 0)
            leg_pnl   = (intrinsic - px) if act == "BUY" else (px - intrinsic)
            pnl += leg_pnl * qty * ls
        results.append((spot, pnl))
    return results


def classify_market_state(iv_regime, net_gex, cascade_bear, cascade_bull, vanna_zones):
    """Classify market into one of 8 regime states."""
    gex_bias = "BULL" if net_gex > 0 else ("BEAR" if net_gex < 0 else "NEUTRAL")
    cascade_dir = "BEAR" if cascade_bear > cascade_bull else (
        "BULL" if cascade_bull > cascade_bear else "NEUTRAL")

    vacuums   = [z for z in vanna_zones if z["role"] == "VACUUM_ZONE"]
    floors    = [z for z in vanna_zones if z["role"] == "SUPPORT_FLOOR"]
    traps     = [z for z in vanna_zones if z["role"] == "TRAP_DOOR"]
    ceilings  = [z for z in vanna_zones if z["role"] == "RESISTANCE_CEILING"]

    if iv_regime == "COMPRESSING" and net_gex > 0 and len(floors) >= 1:
        state = "PINNED"
        desc  = "Market pinned by strong absorption — time decay strategies optimal"
    elif iv_regime == "EXPANDING" and net_gex < 0 and len(vacuums) >= 1:
        state = "BREAKOUT_ARMED"
        desc  = "Explosive move imminent — directional gamma plays"
    elif iv_regime == "EXPANDING" and cascade_dir == "BEAR":
        state = "TRENDING_BEAR"
        desc  = "Strong bearish dealer flow — debit bear strategies"
    elif iv_regime == "EXPANDING" and cascade_dir == "BULL":
        state = "TRENDING_BULL"
        desc  = "Strong bullish dealer flow — debit bull strategies"
    elif iv_regime == "COMPRESSING" and len(floors) >= 2:
        state = "SQUEEZE_BUILDING"
        desc  = "IV compression with multiple floors — pre-explosive setup"
    elif iv_regime == "FLAT" and net_gex > 0:
        state = "MEAN_REVERTING"
        desc  = "Range-bound with absorption walls — credit spreads optimal"
    elif iv_regime == "COMPRESSING" and abs(net_gex) < 500:
        state = "EXPIRY_PINNING"
        desc  = "Max pain mechanics — iron butterfly / condor"
    else:
        state = "TRANSITIONAL"
        desc  = "Mixed signals — wait for regime clarity or use defined-risk spreads"

    return state, gex_bias, cascade_dir, desc


def auto_select_strikes(df_selected, spot_price, strategy_name, iv_regime, symbol):
    """
    GEX-driven automatic strike selection.
    Returns dict of strike selections per leg.
    """
    if df_selected is None or len(df_selected) == 0:
        return {}

    cfg = INDEX_CONFIG.get(symbol, {"strike_interval": 50})
    interval = cfg.get("strike_interval", 50)

    # ATM
    strikes = sorted(df_selected["strike"].unique())
    atm = min(strikes, key=lambda x: abs(x - spot_price))

    # Positive GEX strikes (absorption — natural short strike location)
    pos_gex = df_selected[df_selected["net_gex"] > 0].sort_values("net_gex", ascending=False)
    neg_gex = df_selected[df_selected["net_gex"] < 0].sort_values("net_gex", ascending=True)

    # Strikes above/below spot
    above = sorted([s for s in strikes if s > spot_price])
    below = sorted([s for s in strikes if s < spot_price], reverse=True)

    pos_above = [s for s in pos_gex["strike"].tolist() if s > spot_price]
    pos_below = [s for s in pos_gex["strike"].tolist() if s < spot_price]

    result = {"atm": atm, "interval": interval}

    if strategy_name == "Bear Put Spread":
        result["long_strike"]  = atm
        result["short_strike"] = pos_below[0] if pos_below else (atm - interval * 3)
        result["note"] = "Short at nearest positive GEX below — dealer absorption = natural floor"

    elif strategy_name == "Bull Call Spread":
        result["long_strike"]  = atm
        result["short_strike"] = pos_above[0] if pos_above else (atm + interval * 3)
        result["note"] = "Short at nearest positive GEX above — dealer wall = natural ceiling"

    elif strategy_name == "Long Put":
        result["strike"] = atm
        result["note"]   = "ATM for maximum delta exposure to cascade move"

    elif strategy_name == "Long Call":
        result["strike"] = atm
        result["note"]   = "ATM for maximum delta exposure to cascade move"

    elif strategy_name == "Bear Call Spread":
        result["short_strike"] = pos_above[0] if pos_above else (atm + interval * 2)
        result["long_strike"]  = result["short_strike"] + interval * 2
        result["note"] = "Short below GEX wall — collect credit while wall holds"

    elif strategy_name == "Bull Put Spread":
        result["short_strike"] = pos_below[0] if pos_below else (atm - interval * 2)
        result["long_strike"]  = result["short_strike"] - interval * 2
        result["note"] = "Short above GEX floor — collect credit while floor holds"

    elif strategy_name == "Iron Condor":
        sc = pos_above[0] if pos_above else atm + interval * 3
        sp = pos_below[0] if pos_below else atm - interval * 3
        result["short_call"] = sc; result["long_call"]  = sc + interval * 2
        result["short_put"]  = sp; result["long_put"]   = sp - interval * 2
        result["note"] = "Short strikes at GEX absorption walls — natural range boundaries"

    elif strategy_name == "Iron Butterfly":
        result["atm_call_short"] = atm; result["atm_put_short"] = atm
        result["long_call"] = atm + interval * 3
        result["long_put"]  = atm - interval * 3
        result["note"] = "Body at ATM GEX peak — max pain / expiry pin mechanics"

    elif strategy_name in ("Short Strangle", "Long Straddle", "Long Strangle"):
        sc = pos_above[0] if pos_above else atm + interval * 3
        sp = pos_below[0] if pos_below else atm - interval * 3
        result["call_strike"] = sc if "Strangle" in strategy_name else atm
        result["put_strike"]  = sp if "Strangle" in strategy_name else atm
        result["note"] = "Strangle at GEX walls" if "Strangle" in strategy_name else "Straddle at ATM"

    return result


def get_strategy_recommendations(state, gex_bias, cascade_dir, iv_regime, cascade_bear, cascade_bull):
    """Score and rank all strategies for current regime."""
    key = (iv_regime, gex_bias, cascade_dir)
    scores = _REGIME_FIT.get(key, {})

    # Fallback partial matches
    if not scores:
        for k in _REGIME_FIT:
            if k[0] == iv_regime:
                scores = _REGIME_FIT[k]
                break

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    result = []
    for name, score in ranked:
        if name not in _STRATEGIES:
            continue
        meta_s = _STRATEGIES[name]
        fit_label = {3: "BEST FIT", 2: "GOOD FIT", 1: "VIABLE", 0: "AVOID"}[score]
        fit_color = {3: "#10b981", 2: "#06b6d4", 1: "#f59e0b", 0: "#ef4444"}[score]
        result.append({
            "name": name, "score": score,
            "fit_label": fit_label, "fit_color": fit_color,
            "type": meta_s["type"], "dir": meta_s["dir"], "vol": meta_s["vol"],
        })
    return result


def render_strategy_tab(df_selected, df, spot_price, unit_label, symbol, meta,
                         vanna_zones, iv_regime, net_gex, cascade_bear, cascade_bull):
    """Main renderer for the Strategy Finder + Builder tab."""

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown("### &#x1F3AF; HedGEX Strategy Finder + Builder")
    st.caption("GEX-driven strategy selection with live payoff visualization. "
               "Strike selection powered by cascade mathematics.")

    cfg = INDEX_CONFIG.get(symbol, {"contract_size": 25, "strike_interval": 50})
    lot_size = cfg.get("contract_size", 25)
    interval = cfg.get("strike_interval", 50)

    # ── Market State Banner ───────────────────────────────────────────────────
    state, gex_bias, cascade_dir, state_desc = classify_market_state(
        iv_regime, net_gex, cascade_bear, cascade_bull, vanna_zones)

    state_colors = {
        "BREAKOUT_ARMED":  "#ef4444", "TRENDING_BEAR":  "#ef4444",
        "TRENDING_BULL":   "#10b981", "PINNED":         "#06b6d4",
        "SQUEEZE_BUILDING":"#a855f7", "MEAN_REVERTING": "#f59e0b",
        "EXPIRY_PINNING":  "#8b5cf6", "TRANSITIONAL":   "#94a3b8",
    }
    state_icons = {
        "BREAKOUT_ARMED":  "&#x1F4A5;", "TRENDING_BEAR": "&#x1F43B;",
        "TRENDING_BULL":   "&#x1F402;", "PINNED":        "&#x1F4CC;",
        "SQUEEZE_BUILDING":"&#x26A1;",  "MEAN_REVERTING":"&#x21C4;",
        "EXPIRY_PINNING":  "&#x1F4CD;", "TRANSITIONAL":  "&#x23F3;",
    }
    sc = state_colors.get(state, "#94a3b8")
    si = state_icons.get(state, "&#x2753;")

    iv_color = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")
    gex_color = "#10b981" if gex_bias == "BULL" else ("#ef4444" if gex_bias == "BEAR" else "#94a3b8")
    cas_color = "#10b981" if cascade_dir == "BULL" else ("#ef4444" if cascade_dir == "BEAR" else "#94a3b8")

    banner = [
        '<div style="background:{}15;border:2px solid {}55;border-radius:14px;padding:16px 20px;margin-bottom:16px;">'.format(sc,sc),
        '<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">',
        '<div>',
        '<div style="font-family:Space Grotesk,sans-serif;font-size:1.3rem;font-weight:800;color:{};">{} {}</div>'.format(sc, si, state.replace("_"," ")),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#94a3b8;margin-top:4px;">{}</div>'.format(state_desc),
        '</div>',
        '<div style="display:flex;gap:10px;flex-wrap:wrap;">',
        '<div style="padding:6px 14px;background:{}20;border:1px solid {}50;border-radius:20px;font-family:JetBrains Mono,monospace;font-size:0.72rem;color:{};">IV: <b>{}</b></div>'.format(iv_color,iv_color,iv_color,iv_regime),
        '<div style="padding:6px 14px;background:{}20;border:1px solid {}50;border-radius:20px;font-family:JetBrains Mono,monospace;font-size:0.72rem;color:{};">GEX: <b>{}</b></div>'.format(gex_color,gex_color,gex_color,gex_bias),
        '<div style="padding:6px 14px;background:{}20;border:1px solid {}50;border-radius:20px;font-family:JetBrains Mono,monospace;font-size:0.72rem;color:{};">Cascade: <b>{}</b></div>'.format(cas_color,cas_color,cas_color,cascade_dir),
        '<div style="padding:6px 14px;background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.4);border-radius:20px;font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#c4b5fd;">&#x1FA99; {:.0f} BEAR / {:.0f} BULL pts</div>'.format(cascade_bear, cascade_bull),
        '</div></div></div>',
    ]
    st.markdown("".join(banner), unsafe_allow_html=True)

    # ── Two-column layout: Finder | Builder ───────────────────────────────────
    finder_col, builder_col = st.columns([1, 1.4], gap="medium")

    # ════════════════════════════════════════════════════════════════════════
    # LEFT: STRATEGY FINDER
    # ════════════════════════════════════════════════════════════════════════
    with finder_col:
        st.markdown("#### &#x1F50D; Strategy Finder")

        recs = get_strategy_recommendations(state, gex_bias, cascade_dir, iv_regime,
                                             cascade_bear, cascade_bull)

        best    = [r for r in recs if r["score"] == 3]
        good    = [r for r in recs if r["score"] == 2]
        viable  = [r for r in recs if r["score"] == 1]
        avoid   = [r for r in recs if r["score"] == 0]

        selected_strategy = None

        # Best fit strategies
        if best:
            st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#10b981;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">&#x2B50; Best Fit</div>', unsafe_allow_html=True)
            for r in best:
                type_color = "#ef4444" if r["type"]=="DEBIT" else "#10b981"
                card = [
                    '<div style="background:rgba(16,185,129,0.08);border:1.5px solid rgba(16,185,129,0.4);border-radius:10px;padding:10px 14px;margin-bottom:6px;">',
                    '<div style="display:flex;justify-content:space-between;align-items:center;">',
                    '<span style="font-family:Space Grotesk,sans-serif;font-size:0.9rem;font-weight:700;color:#f1f5f9;">{}</span>'.format(r["name"]),
                    '<div style="display:flex;gap:6px;">',
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.62rem;padding:2px 8px;background:{}25;border:1px solid {}50;border-radius:10px;color:{};">{}</span>'.format(type_color,type_color,type_color,r["type"]),
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.62rem;padding:2px 8px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);border-radius:10px;color:#10b981;">BEST</span>',
                    '</div></div></div>',
                ]
                st.markdown("".join(card), unsafe_allow_html=True)

        # Good + Viable
        if good or viable:
            st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#06b6d4;text-transform:uppercase;letter-spacing:0.1em;margin:8px 0 6px 0;">&#x1F7E6; Also Viable</div>', unsafe_allow_html=True)
            for r in (good + viable):
                type_color = "#ef4444" if r["type"]=="DEBIT" else "#10b981"
                lbl_col = "#06b6d4" if r["score"]==2 else "#f59e0b"
                card = [
                    '<div style="background:rgba(6,182,212,0.05);border:1px solid rgba(6,182,212,0.2);border-radius:8px;padding:8px 12px;margin-bottom:4px;">',
                    '<div style="display:flex;justify-content:space-between;align-items:center;">',
                    '<span style="font-family:Space Grotesk,sans-serif;font-size:0.82rem;font-weight:600;color:#cbd5e1;">{}</span>'.format(r["name"]),
                    '<div style="display:flex;gap:5px;">',
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.60rem;padding:2px 7px;background:{}20;border-radius:8px;color:{};">{}</span>'.format(type_color,type_color,r["type"]),
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.60rem;padding:2px 7px;background:{}15;border-radius:8px;color:{};">{}</span>'.format(lbl_col,lbl_col,r["fit_label"]),
                    '</div></div></div>',
                ]
                st.markdown("".join(card), unsafe_allow_html=True)

        # Avoid
        if avoid:
            with st.expander("&#x274C; Strategies to Avoid", expanded=False):
                for r in avoid[:5]:
                    st.markdown(
                        '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
                        'color:#ef4444;padding:3px 0;">&#x274C; {} — wrong regime</div>'.format(r["name"]),
                        unsafe_allow_html=True)

        st.markdown("---")

        # Strategy selector for builder
        all_names = [r["name"] for r in recs if r["score"] > 0]
        if not all_names:
            all_names = list(_STRATEGIES.keys())

        st.markdown("**&#x1F527; Load into Builder:**")
        selected_strategy = st.selectbox(
            "Select Strategy", all_names,
            index=0, key="strategy_selector",
            label_visibility="collapsed"
        )

        load_btn = st.button("&#x1F4E5;  Auto-fill Strikes from GEX",
                             use_container_width=True, type="primary",
                             key="load_strategy_btn")
        if load_btn:
            st.session_state["selected_strategy"] = selected_strategy
            st.session_state["auto_fill_triggered"] = True
            st.rerun()

    # ════════════════════════════════════════════════════════════════════════
    # RIGHT: STRATEGY BUILDER
    # ════════════════════════════════════════════════════════════════════════
    with builder_col:
        st.markdown("#### &#x1FA9F; Strategy Builder")

        active_strategy = st.session_state.get("selected_strategy", selected_strategy or (all_names[0] if all_names else "Bear Put Spread"))
        auto_fill       = st.session_state.get("auto_fill_triggered", False)

        # Get auto-selected strikes
        auto_strikes = {}
        if auto_fill or True:
            auto_strikes = auto_select_strikes(df_selected, spot_price, active_strategy, iv_regime, symbol)
            if auto_fill:
                st.session_state["auto_fill_triggered"] = False

        all_strikes_list = sorted(df_selected["strike"].unique().tolist()) if df_selected is not None and len(df_selected) > 0 else []
        if not all_strikes_list:
            st.warning("Fetch data first to use the Strategy Builder.")
            return

        # Get IVs from data
        def get_iv_for_strike(strike, opt_type):
            """Get IV as percentage (0-100 range) for a given strike."""
            if df_selected is None: return 18.0
            row = df_selected[df_selected["strike"] == strike]
            if row.empty: return 18.0
            col = "call_iv" if opt_type == "CE" else "put_iv"
            val = float(row[col].iloc[0]) if col in row.columns and len(row) > 0 else 18.0
            if val <= 0: val = 18.0
            return val  # already in percentage form (e.g. 18.0 = 18%)

        def get_real_premium(strike, opt_type):
            """Get real close price from API data, BSM fallback."""
            if df_selected is None: return None
            row = df_selected[df_selected["strike"] == strike]
            if row.empty: return None
            col = "call_close" if opt_type == "CE" else "put_close"
            val = float(row[col].iloc[0]) if col in row.columns and len(row) > 0 else 0.0
            return val if val > 0 else None

        # TTE
        tte_days = 7 if meta.get("expiry_flag","WEEK") == "WEEK" else 30
        tte      = tte_days / 365
        r_rate   = 0.065

        # ── Leg constructor ───────────────────────────────────────────────
        st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;color:#94a3b8;margin-bottom:8px;">Define legs manually or use Auto-fill from Finder</div>', unsafe_allow_html=True)

        # Determine number of legs from strategy
        n_legs = _STRATEGIES.get(active_strategy, {}).get("legs", 2)
        n_legs = st.number_input("Number of Legs", 1, 6, n_legs, key="n_legs_input")

        legs = []
        atm_default = auto_strikes.get("atm", min(all_strikes_list, key=lambda x: abs(x - spot_price)))

        # Smart defaults per strategy
        leg_defaults = _get_leg_defaults(active_strategy, auto_strikes, all_strikes_list, atm_default, interval)

        for i in range(int(n_legs)):
            ld = leg_defaults[i] if i < len(leg_defaults) else {
                "action":"BUY","strike":atm_default,"opt_type":"CE","qty":1}

            with st.expander(f"Leg {i+1}", expanded=True):
                lc1, lc2, lc3, lc4 = st.columns([1,1.5,1,1])
                with lc1:
                    action = st.selectbox("Action", ["BUY","SELL"],
                        index=0 if ld["action"]=="BUY" else 1,
                        key=f"leg_{i}_action")
                with lc2:
                    strike_idx = all_strikes_list.index(ld["strike"]) if ld["strike"] in all_strikes_list else 0
                    strike = st.selectbox("Strike", all_strikes_list,
                        index=strike_idx, key=f"leg_{i}_strike")
                with lc3:
                    opt_type = st.selectbox("Type", ["CE","PE"],
                        index=0 if ld["opt_type"]=="CE" else 1,
                        key=f"leg_{i}_type")
                with lc4:
                    qty = st.number_input("Lots", 1, 50, ld["qty"],
                        key=f"leg_{i}_qty")

                iv_pct   = get_iv_for_strike(strike, opt_type)  # e.g. 18.0
                # Try real API price first
                real_px  = get_real_premium(strike, opt_type)
                if real_px and real_px > 0:
                    premium = real_px
                    px_source = "API"
                else:
                    iv_val  = iv_pct / 100 if iv_pct > 1 else iv_pct
                    premium = _bs_price(spot_price, strike, tte, r_rate, max(iv_val, 0.05), opt_type)
                    px_source = "BSM"
                iv_val = iv_pct / 100 if iv_pct > 1 else iv_pct
                greeks   = _bs_greeks(spot_price, strike, tte, r_rate, max(iv_val, 0.05), opt_type)
                sign     = 1 if action=="BUY" else -1

                # GEX at this strike
                gex_at_strike = 0.0
                if df_selected is not None:
                    row = df_selected[df_selected["strike"]==strike]
                    if not row.empty and "net_gex" in row.columns:
                        gex_at_strike = float(row["net_gex"].iloc[0])
                gex_role = "Absorption &#x1F7E2;" if gex_at_strike > 0 else ("Fuel &#x1F534;" if gex_at_strike < 0 else "Neutral")
                gex_role_color = "#10b981" if gex_at_strike > 0 else ("#ef4444" if gex_at_strike < 0 else "#94a3b8")

                mc1,mc2,mc3,mc4,mc5,mc6 = st.columns(6)
                mc1.metric("LTP", f"Rs{premium:.1f}",
                           delta=px_source, delta_color="normal" if px_source=="API" else "off")
                mc2.metric("Delta", f"{greeks['delta']:+.3f}")
                mc3.metric("Theta/day", f"Rs{greeks['theta']*lot_size*qty:.0f}")
                mc4.metric("Vega", f"{greeks['vega']:.3f}")
                mc5.metric("IV", f"{iv_pct:.1f}%")
                mc6.metric("Margin est.", f"Rs{abs(premium)*lot_size*qty:,.0f}")

                st.markdown(
                    '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#94a3b8;">'
                    'GEX @ strike: <b style="color:{};">{:+.2f}{} — {}</b>'
                    '</div>'.format(gex_role_color, gex_at_strike, unit_label, gex_role),
                    unsafe_allow_html=True,
                )

                legs.append({
                    "strike":   strike,
                    "opt_type": opt_type,
                    "action":   action,
                    "premium":  premium,
                    "qty":      qty,
                    "lot_size": lot_size,
                    "delta":    greeks["delta"] * sign,
                    "gamma":    greeks["gamma"] * sign,
                    "theta":    greeks["theta"] * sign,
                    "vega":     greeks["vega"]  * sign,
                    "iv":       iv_pct,          # percentage, e.g. 18.0
                    "iv_dec":   iv_val,           # decimal, e.g. 0.18
                    "gex":      gex_at_strike,
                    "px_src":   px_source,
                })

        if not legs:
            return

        # ── Position Greeks summary ───────────────────────────────────────
        st.markdown("---")
        net_delta = sum(l["delta"] * l["qty"] * l["lot_size"] for l in legs)
        net_gamma = sum(l["gamma"] * l["qty"] * l["lot_size"] for l in legs)
        net_theta = sum(l["theta"] * l["qty"] * l["lot_size"] for l in legs)
        net_vega  = sum(l["vega"]  * l["qty"] * l["lot_size"] for l in legs)
        net_cost  = sum((l["premium"] * (1 if l["action"]=="BUY" else -1))
                        * l["qty"] * l["lot_size"] for l in legs)

        # ── Compute POP and Total Cost ────────────────────────────────────────
        # POP = Probability of Profit using 1 - |net_delta| approximation
        # More precise: for defined-risk spreads use breakeven distance / ATM IV
        try:
            import math as _m2
            from scipy.stats import norm as _n2
            _avg_iv   = sum(l.get("iv_dec", l["iv"]/100 if l["iv"] > 1 else l["iv"]) for l in legs) / max(len(legs), 1)
            _avg_tte  = tte
            _be_list  = []
            _spot_r   = list(range(int(spot_price * 0.92), int(spot_price * 1.08), int(interval // 2)))
            _py_data  = compute_strategy_payoff(legs, _spot_r, lot_size)
            for _i in range(len(_py_data)-1):
                if _py_data[_i][1] * _py_data[_i+1][1] < 0:
                    _be = _py_data[_i][0] - _py_data[_i][1] * (
                        _py_data[_i+1][0] - _py_data[_i][0]) / (
                        _py_data[_i+1][1] - _py_data[_i][1])
                    _be_list.append(_be)
            if _be_list and _avg_iv > 0 and _avg_tte > 0:
                _pop_vals = []
                for _be in _be_list:
                    _d = (_m2.log(spot_price / _be)) / (_avg_iv * _m2.sqrt(_avg_tte))
                    _pop_vals.append(_n2.cdf(_d) if _be < spot_price else 1 - _n2.cdf(_d))
                pop_pct = min(sum(_pop_vals) / len(_pop_vals) * 100, 99.9)
            else:
                pop_pct = max(0.0, min((1.0 - abs(net_delta) / max(lot_size, 1)) * 100, 99.9))
        except Exception:
            pop_pct = max(0.0, min((1.0 - abs(net_delta) / max(lot_size, 1)) * 100, 99.9))

        total_cost_inr   = abs(net_cost)           # total debit/credit in ₹
        margin_approx    = total_cost_inr * 1.1 if net_cost > 0 else total_cost_inr * 5.0
        pop_color        = "#10b981" if pop_pct >= 60 else ("#f59e0b" if pop_pct >= 45 else "#ef4444")

        g1,g2,g3,g4,g5,g6,g7 = st.columns(7)
        g1.metric("Net Delta",    f"{net_delta:+.2f}",        help="Total directional exposure")
        g2.metric("Net Gamma",    f"{net_gamma:+.5f}",        help="Rate of delta change")
        g3.metric("Net Theta",    f"₹{net_theta:+.0f}/day",   help="Daily time decay")
        g4.metric("Net Vega",     f"{net_vega:+.3f}",         help="IV sensitivity per 1%")
        g5.metric("Net Premium",  f"₹{abs(net_cost):,.0f}",
                  delta="DEBIT" if net_cost > 0 else "CREDIT",
                  delta_color="inverse" if net_cost > 0 else "normal")
        g6.metric("Total Cost",   f"₹{total_cost_inr:,.0f}",
                  delta=f"~₹{margin_approx:,.0f} margin" if net_cost < 0 else "Max loss = premium",
                  delta_color="off")
        g7.metric("POP",          f"{pop_pct:.1f}%",
                  delta="High" if pop_pct >= 60 else ("Moderate" if pop_pct >= 45 else "Low"),
                  delta_color="normal" if pop_pct >= 60 else ("off" if pop_pct >= 45 else "inverse"),
                  help="Probability of Profit — BSM breakeven distance method")

        # ── Payoff Chart ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**&#x1F4C8; Payoff Chart — GEX Overlay**")

        strikes_in_legs = [l["strike"] for l in legs]
        # Wide range: spot ±15% or at least ±12 intervals from outermost strike
        lo = min(min(strikes_in_legs) - interval * 10, spot_price * 0.87)
        hi = max(max(strikes_in_legs) + interval * 10, spot_price * 1.13)
        step = max(int(interval // 4), 5)
        spot_range = list(range(int(lo), int(hi) + 1, step))

        payoff_data = compute_strategy_payoff(legs, spot_range, lot_size)
        xs = [p[0] for p in payoff_data]
        ys = [p[1] for p in payoff_data]

        # Breakevens
        breakevens = []
        for i in range(len(ys)-1):
            if ys[i] * ys[i+1] < 0:
                be = xs[i] - ys[i] * (xs[i+1]-xs[i]) / (ys[i+1]-ys[i])
                breakevens.append(be)

        max_profit = max(ys) if ys else 0
        max_loss   = min(ys) if ys else 0

        # ── Build enhanced payoff chart ───────────────────────────────────────
        from plotly.subplots import make_subplots as _msp
        fig = _msp(
            rows=2, cols=1,
            row_heights=[0.72, 0.28],
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=("P&L at Expiry", "Net GEX Profile"),
        )

        # ── Row 1: Payoff ─────────────────────────────────────────────────────
        # Gradient fill: split into profit and loss zones
        profit_y = [max(y, 0) for y in ys]
        loss_y   = [min(y, 0) for y in ys]

        fig.add_trace(go.Scatter(
            x=xs, y=profit_y, fill="tozeroy",
            fillcolor="rgba(16,185,129,0.18)",
            line=dict(width=0, color="rgba(16,185,129,0)"),
            name="Profit Zone", showlegend=True
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=xs, y=loss_y, fill="tozeroy",
            fillcolor="rgba(239,68,68,0.18)",
            line=dict(width=0, color="rgba(239,68,68,0)"),
            name="Loss Zone", showlegend=True
        ), row=1, col=1)

        # Main P&L curve — thick, glowing
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines",
            line=dict(color="#00f5c4", width=3),
            name="P&L at Expiry"
        ), row=1, col=1)

        # Today's P&L (approximate: time value decay ~50% used)
        ys_today = []
        avg_iv_val = sum(l.get("iv_dec", l["iv"]/100 if l["iv"]>1 else l["iv"]) for l in legs) / max(len(legs),1) / 100
        for s in spot_range:
            pnl_today = 0.0
            for leg in legs:
                k, opt, act, qty = leg["strike"], leg["opt_type"], leg["action"], leg["qty"]
                import math as _mp
                if avg_iv_val > 0 and tte > 0:
                    _tte_half = tte * 0.5
                    _d1 = (_mp.log(s/k) + (0.065+0.5*avg_iv_val**2)*_tte_half) / (avg_iv_val*_mp.sqrt(_tte_half))
                    _d2 = _d1 - avg_iv_val*_mp.sqrt(_tte_half)
                    from scipy.stats import norm as _nn
                    if opt == "CE":
                        mid_px = s*_nn.cdf(_d1) - k*_mp.exp(-0.065*_tte_half)*_nn.cdf(_d2)
                    else:
                        mid_px = k*_mp.exp(-0.065*_tte_half)*_nn.cdf(-_d2) - s*_nn.cdf(-_d1)
                    mid_px = max(mid_px, 0)
                else:
                    mid_px = max(s-k,0) if opt=="CE" else max(k-s,0)
                sign = 1 if act=="BUY" else -1
                pnl_today += sign * (mid_px - leg["premium"]) * qty * lot_size
            ys_today.append(pnl_today)

        fig.add_trace(go.Scatter(
            x=xs, y=ys_today, mode="lines",
            line=dict(color="rgba(250,204,21,0.6)", width=1.5, dash="dot"),
            name="Approx Today P&L"
        ), row=1, col=1)

        # Zero line
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,0.4)",
                      line_width=1)

        # Spot price vertical line
        fig.add_vline(x=spot_price, line_dash="solid",
                      line_color="#06b6d4", line_width=2,
                      annotation_text=f"Spot {spot_price:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(color="#06b6d4", size=11))

        # Breakeven lines
        for j, be in enumerate(breakevens):
            pos = "top left" if j % 2 == 0 else "bottom left"
            fig.add_vline(x=be, line_dash="dot", line_color="#fbbf24", line_width=1.5,
                          annotation_text=f"BE {be:,.0f}",
                          annotation_font=dict(color="#fbbf24", size=10),
                          annotation_position=pos)

        # Cascade target shaded bands
        if cascade_bear > 0:
            tgt = spot_price - cascade_bear
            fig.add_vrect(x0=tgt - interval*1.5, x1=tgt + interval*1.5,
                          fillcolor="rgba(239,68,68,0.10)",
                          line=dict(color="#ef4444", width=1, dash="dot"),
                          annotation_text=f"Bear {cascade_bear:.0f}pt",
                          annotation_font=dict(color="#ef4444", size=10),
                          annotation_position="top left", row=1, col=1)
        if cascade_bull > 0:
            tgt = spot_price + cascade_bull
            fig.add_vrect(x0=tgt - interval*1.5, x1=tgt + interval*1.5,
                          fillcolor="rgba(16,185,129,0.10)",
                          line=dict(color="#10b981", width=1, dash="dot"),
                          annotation_text=f"Bull {cascade_bull:.0f}pt",
                          annotation_font=dict(color="#10b981", size=10),
                          annotation_position="top right", row=1, col=1)

        # Strike markers
        for leg in legs:
            k = leg["strike"]
            act = leg["action"]
            c = "#10b981" if act=="BUY" else "#ef4444"
            fig.add_vline(x=k, line_dash="longdash", line_color=c,
                          line_width=1, opacity=0.5, row=1, col=1)

        # ── Row 2: GEX profile ────────────────────────────────────────────────
        if df_selected is not None and "net_gex" in df_selected.columns:
            gex_sub = df_selected[(df_selected["strike"] >= lo) & (df_selected["strike"] <= hi)].copy()
            fig.add_trace(go.Bar(
                x=gex_sub["strike"], y=gex_sub["net_gex"],
                name="Net GEX",
                marker_color=["rgba(124,58,237,0.55)" if v > 0 else "rgba(234,179,8,0.55)"
                               for v in gex_sub["net_gex"]],
                showlegend=True,
            ), row=2, col=1)
            fig.add_hline(y=0, line_color="rgba(148,163,184,0.3)", line_width=1)

        # ── Layout ────────────────────────────────────────────────────────────
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15,23,42,0)",
            plot_bgcolor="rgba(15,23,42,0.5)",
            height=580,
            margin=dict(l=50, r=30, t=50, b=30),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1,
                font=dict(family="JetBrains Mono", size=10),
                bgcolor="rgba(15,23,42,0.6)",
            ),
            font=dict(family="JetBrains Mono", color="#94a3b8"),
            hoverlabel=dict(bgcolor="rgba(15,23,42,0.9)", font_size=12,
                            font_family="JetBrains Mono"),
            hovermode="x unified",
        )
        fig.update_yaxes(title_text="P&L (Rs)", gridcolor="rgba(148,163,184,0.1)",
                         zerolinecolor="rgba(148,163,184,0.2)",
                         tickformat=",", row=1, col=1)
        fig.update_yaxes(title_text="GEX", gridcolor="rgba(148,163,184,0.06)",
                         row=2, col=1)
        fig.update_xaxes(title_text="Spot Price at Expiry",
                         gridcolor="rgba(148,163,184,0.08)",
                         tickformat=",", row=2, col=1)
        fig.update_annotations(font=dict(family="JetBrains Mono"))
        st.plotly_chart(fig, use_container_width=True)

        # ── Strategy Summary card ─────────────────────────────────────────
        max_risk_label  = f"₹{abs(max_loss):,.0f}"  if max_loss < -1 else "Unlimited"
        max_reward_label= f"₹{max_profit:,.0f}" if max_profit < 1e6 else "Unlimited"
        be_label = " / ".join([f"₹{b:,.0f}" for b in breakevens]) if breakevens else "N/A"

        rr = abs(max_profit / max_loss) if max_loss != 0 and max_profit < 1e6 else 0

        summary_parts = [
            '<div style="background:rgba(15,23,42,0.8);border:1px solid rgba(148,163,184,0.15);border-radius:10px;padding:14px 16px;margin-top:4px;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">&#x1F4CB; Strategy Summary — {}</div>'.format(active_strategy),
            '<div style="display:flex;gap:10px;flex-wrap:wrap;">',
        ]
        for lbl, val, col in [
            ("Max Profit",    max_reward_label, "#10b981"),
            ("Max Loss",      max_risk_label,   "#ef4444"),
            ("Breakeven(s)",  be_label,          "#f59e0b"),
            ("R:R Ratio",     f"{rr:.2f}:1" if rr > 0 else "N/A", "#06b6d4"),
            ("Net Cost",      ("DEBIT ₹{:,.0f}".format(abs(net_cost)) if net_cost>0
                               else "CREDIT ₹{:,.0f}".format(abs(net_cost))),
             "#ef4444" if net_cost>0 else "#10b981"),
        ]:
            summary_parts += [
                '<div style="flex:1;min-width:100px;text-align:center;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;">',
                '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#64748b;">{}</div>'.format(lbl),
                '<div style="font-family:Space Grotesk,sans-serif;font-size:0.88rem;font-weight:700;color:{};">{}</div>'.format(col,val),
                '</div>',
            ]
        summary_parts += ['</div>']

        # GEX alignment assessment
        gex_aligned = sum(1 for l in legs if
            (l["action"]=="BUY" and l["gex"] < 0) or (l["action"]=="SELL" and l["gex"] > 0))
        total_legs = len(legs)
        align_score = gex_aligned / total_legs if total_legs > 0 else 0
        align_color = "#10b981" if align_score >= 0.5 else "#f59e0b"
        align_label = "ALIGNED" if align_score >= 0.5 else "PARTIAL"
        align_icon  = "&#x2705;" if align_score >= 0.5 else "&#x26A0;&#xFE0F;"

        summary_parts += [
            '<div style="margin-top:10px;padding:8px 12px;background:{}15;border-left:3px solid {};border-radius:0 6px 6px 0;">'.format(align_color,align_color),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.70rem;color:{};">{} GEX Alignment: <b>{}</b> — {}/{} legs placed at optimal GEX levels</span>'.format(align_color,align_icon,align_label,gex_aligned,total_legs),
            '</div>',
            '</div>',
        ]
        st.markdown("".join(summary_parts), unsafe_allow_html=True)

        # ── Export — strategy summary only (no signal sharing) ──────────────
        st.markdown("---")
        st.caption("&#x1F4CB; Strategy summary for personal reference only. Not a trading signal.")
        summary_txt = "HedGEX Strategy Builder — Personal Reference\n"
        summary_txt += "="*48 + "\n"
        summary_txt += "Strategy: {}  |  Symbol: {}\n".format(active_strategy, symbol)
        summary_txt += "Spot: Rs{:,.0f}  |  IV Regime: {}  |  State: {}\n\n".format(spot_price, iv_regime, state)
        summary_txt += "Legs:\n"
        for i, l in enumerate(legs):
            summary_txt += "  Leg {}: {} {} {} {}  @ Rs{:.1f}  ({} lots)\n".format(
                i+1, l["action"], symbol, l["opt_type"], int(l["strike"]), l["premium"], l["qty"])
        summary_txt += "\nMax Profit : {}\n".format(max_reward_label)
        summary_txt += "Max Loss   : {}\n".format(max_risk_label)
        summary_txt += "Breakeven  : {}\n".format(be_label)
        summary_txt += "R:R        : {:.2f}:1\n".format(rr)
        summary_txt += "GEX Align  : {}\n".format(align_label)
        summary_txt += "\n[For educational/research use only. Not financial advice.]"
        st.download_button(
            "&#x1F4CB; Save Strategy Summary",
            data=summary_txt,
            file_name="hedgex_strategy_summary.txt",
            mime="text/plain", use_container_width=True,
        )


def _get_leg_defaults(strategy_name, auto_strikes, all_strikes, atm, interval):
    """Return default leg configurations for a given strategy."""
    a = auto_strikes
    def nearest(target):
        if not all_strikes: return atm
        return min(all_strikes, key=lambda x: abs(x - target))

    defs = {
        "Long Call":       [{"action":"BUY",  "strike":nearest(a.get("strike",atm)), "opt_type":"CE","qty":1}],
        "Long Put":        [{"action":"BUY",  "strike":nearest(a.get("strike",atm)), "opt_type":"PE","qty":1}],
        "Bear Put Spread": [
            {"action":"BUY",  "strike":nearest(a.get("long_strike",atm)),                "opt_type":"PE","qty":1},
            {"action":"SELL", "strike":nearest(a.get("short_strike",atm-interval*3)),    "opt_type":"PE","qty":1},
        ],
        "Bull Call Spread":[
            {"action":"BUY",  "strike":nearest(a.get("long_strike",atm)),                "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(a.get("short_strike",atm+interval*3)),    "opt_type":"CE","qty":1},
        ],
        "Bear Call Spread":[
            {"action":"SELL", "strike":nearest(a.get("short_strike",atm+interval*2)),    "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_strike",atm+interval*4)),     "opt_type":"CE","qty":1},
        ],
        "Bull Put Spread": [
            {"action":"SELL", "strike":nearest(a.get("short_strike",atm-interval*2)),    "opt_type":"PE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_strike",atm-interval*4)),     "opt_type":"PE","qty":1},
        ],
        "Iron Condor":     [
            {"action":"SELL", "strike":nearest(a.get("short_call",atm+interval*3)),      "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_call",atm+interval*5)),       "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(a.get("short_put",atm-interval*3)),       "opt_type":"PE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_put",atm-interval*5)),        "opt_type":"PE","qty":1},
        ],
        "Iron Butterfly":  [
            {"action":"SELL", "strike":nearest(a.get("atm_call_short",atm)),             "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_call",atm+interval*3)),       "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(a.get("atm_put_short",atm)),              "opt_type":"PE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("long_put",atm-interval*3)),        "opt_type":"PE","qty":1},
        ],
        "Short Strangle":  [
            {"action":"SELL", "strike":nearest(a.get("call_strike",atm+interval*3)),     "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(a.get("put_strike",atm-interval*3)),      "opt_type":"PE","qty":1},
        ],
        "Long Straddle":   [
            {"action":"BUY",  "strike":nearest(a.get("call_strike",atm)),                "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("put_strike",atm)),                 "opt_type":"PE","qty":1},
        ],
        "Long Strangle":   [
            {"action":"BUY",  "strike":nearest(a.get("call_strike",atm+interval*2)),     "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(a.get("put_strike",atm-interval*2)),      "opt_type":"PE","qty":1},
        ],
        "Synthetic Future":[
            {"action":"BUY",  "strike":nearest(atm),                                     "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(atm),                                     "opt_type":"PE","qty":1},
        ],
        "Ratio Put Spread":[
            {"action":"BUY",  "strike":nearest(atm),                                     "opt_type":"PE","qty":1},
            {"action":"SELL", "strike":nearest(atm-interval*2),                          "opt_type":"PE","qty":2},
        ],
        "Ratio Call Spread":[
            {"action":"BUY",  "strike":nearest(atm),                                     "opt_type":"CE","qty":1},
            {"action":"SELL", "strike":nearest(atm+interval*2),                          "opt_type":"CE","qty":2},
        ],
        "Calendar Spread": [
            {"action":"SELL", "strike":nearest(atm),                                     "opt_type":"CE","qty":1},
            {"action":"BUY",  "strike":nearest(atm),                                     "opt_type":"CE","qty":1},
        ],
    }
    return defs.get(strategy_name, [
        {"action":"BUY", "strike":atm, "opt_type":"CE", "qty":1}
    ])


# ============================================================================
# PROFITABLE SETUPS — Validated trade lists from 1,050-trade backtest
# ============================================================================

_PROFIT_SETUPS = [
    {
        "id": "S1",
        "name": "Bull Call Spread",
        "conditions": "COMPRESSING IV + Afternoon (1-3:30PM) + Cascade ≥150 + Non-Expiry",
        "n": 16, "wr": 87.5, "avg_pnl": 618, "total_pnl": 9891,
        "best": 1318, "worst": -69,
        "color": "#10b981",
        "signal_note": "Short leg captures compressed IV decay. Cascade confirms bull bias. Non-expiry avoids pin risk.",
        "monthly": [
            ("2025-04", 537, 1, 1), ("2025-05", 282, 2, 1),
            ("2025-07", 1327, 2, 2), ("2025-08", 2688, 3, 3),
            ("2025-09", 1295, 2, 1), ("2025-11", 372, 1, 1),
            ("2025-12", 651, 1, 1), ("2026-01", 2739, 4, 4),
        ],
        "trades": [
            ("2025-04-21","14:10","15:25",24143,24121,-22.2,-656, 537,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-05-09","13:20","15:25",23977,24038, 60.7,-823, -69,False,"COMPRESSING",210.4,"EOD_EXIT"),
            ("2025-05-19","15:10","15:25",24945,24935,-10.3,-858, 351,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-07-02","13:20","15:25",25432,25442, 10.7,-370, 778,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-07-09","14:40","15:25",25469,25464, -4.8,-674, 549,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-08","15:05","15:25",24376,24350,-25.9, -12,1212,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-08-11","15:15","15:25",24574,24562,-12.1,-688, 502,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-26","15:10","15:25",24695,24710, 15.7,-100, 974,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-09-08","15:10","15:25",24768,24791, 22.4,-1066,-23,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-09-26","13:50","15:25",24680,24673, -7.1, 141,1318,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-11-07","14:05","15:25",25473,25510, 37.6,-625, 372,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-29","13:40","15:25",25940,25949,  9.4,-538, 651,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2026-01-05","14:10","15:25",26226,26244, 17.8,-262, 901,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2026-01-06","14:10","15:25",26133,26174, 41.5,-110, 902,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2026-01-21","14:25","15:25",25120,25168, 47.2,-681, 232,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-23","13:55","15:25",25049,25064, 14.8,-398, 704,True,"COMPRESSING",225.0,"EOD_EXIT"),
        ],
    },
    {
        "id": "S2",
        "name": "Bull Call Spread (wider gate)",
        "conditions": "COMPRESSING IV + Midday (11AM-1PM) + Cascade ≥150 + Non-Expiry",
        "n": 9, "wr": 66.7, "avg_pnl": 367, "total_pnl": 3300,
        "best": 1138, "worst": -541,
        "color": "#06b6d4",
        "signal_note": "Midday entry avoids morning noise. COMPRESSING IV = structured decay in your favour.",
        "monthly": [
            ("2025-04", 537, 1, 1), ("2025-07", 778, 1, 1),
            ("2025-08", 2688, 3, 3), ("2025-09", 1295, 2, 1),
            ("2025-11", 372, 1, 1),
        ],
        "trades": [
            ("2025-04-21","14:10","15:25",24143,24121,-22.2,-656, 537,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-07-02","13:20","15:25",25432,25442, 10.7,-370, 778,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-08-08","15:05","15:25",24376,24350,-25.9, -12,1212,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-08-11","15:15","15:25",24574,24562,-12.1,-688, 502,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-26","15:10","15:25",24695,24710, 15.7,-100, 974,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-09-08","15:10","15:25",24768,24791, 22.4,-1066,-23,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-09-26","13:50","15:25",24680,24673, -7.1, 141,1318,True,"COMPRESSING",225.0,"EOD_EXIT"),
            ("2025-11-07","14:05","15:25",25473,25510, 37.6,-625, 372,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-29","13:40","15:25",25940,25949,  9.4,-538, 651,True,"COMPRESSING",225.0,"EOD_EXIT"),
        ],
    },
    {
        "id": "S3",
        "name": "Bear Put Spread",
        "conditions": "COMPRESSING IV + Afternoon (1-3:30PM) + Cascade ≥150 + Non-Expiry",
        "n": 38, "wr": 68.4, "avg_pnl": -17, "total_pnl": -635,
        "best": 1155, "worst": -5036,
        "color": "#f59e0b",
        "signal_note": "Breakeven territory — short leg offsets long leg decay. Avoid STOP_HIT exits (4 trades destroyed total PnL). Use EOD-only filter for profitability.",
        "monthly": [
            ("2025-04",1150,3,2),("2025-05",-5124,3,1),("2025-06",-495,2,0),
            ("2025-07",550,2,2),("2025-08",2063,5,5),("2025-09",798,3,2),
            ("2025-10",1107,2,2),("2025-11",937,2,2),("2025-12",206,5,3),
            ("2026-01",-1609,6,4),("2026-02",325,2,1),("2026-04",-543,3,2),
        ],
        "trades": [
            ("2025-04-16","14:05","15:25",23401,23433, 32.2, 250,1038,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-04-23","15:00","15:25",24331,24300,-30.3,-720,  -99,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-04-25","15:05","15:25",24068,23991,-77.0,-127,  210,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-05-02","14:10","15:25",24373,24313,-59.9,-453,    8,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-05-20","14:15","15:25",24727,24713,-13.6,-808,  -96,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-05-27","14:20","14:45",24737,24790, 52.7,-5944,-5036,False,"COMPRESSING",150.0,"STOP_HIT"),
            ("2025-06-24","14:00","15:25",25029,25071, 42.4,-1348,-445,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-06-25","13:15","15:25",25230,25236,  5.8,-860,  -50,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-07-08","15:20","15:25",25520,25523,  2.5,-398,  413,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-07-16","14:35","15:25",25226,25198,-27.5,-535,  136,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-01","15:10","15:25",24545,24572, 26.5,-657,  180,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-04","13:10","15:25",24698,24726, 28.1,-432,  417,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-11","15:15","15:25",24574,24562,-12.1,-294,  418,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-12","15:10","15:25",24490,24485, -4.4,-259,  478,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-08-25","13:30","15:25",24988,24978, -9.7,-170,  570,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-09-03","15:10","15:25",24725,24713,-11.7,-609,  111,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-09-08","14:35","15:25",24874,24791,-83.7, 428,  741,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-09-24","13:25","15:25",25133,25060,-72.1,-458,  -53,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-10-01","14:50","15:25",24849,24853,  3.7,-264,  520,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-10-13","14:55","15:25",25249,25237,-12.0,-156,  587,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-11-07","14:40","15:25",25512,25510, -1.9,-226,  568,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-11-12","13:05","15:25",25915,25874,-41.5,-258,  369,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-05","13:50","15:25",26172,26176,  4.4,  43,  893,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-08","14:10","15:00",25914,25970, 56.4,-2362,-1377,False,"COMPRESSING",150.0,"STOP_HIT"),
            ("2025-12-08","15:05","15:25",25979,25932,-47.0,-710, -113,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-22","14:35","15:25",26166,26162, -3.2,-253,  567,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2025-12-31","14:40","15:25",26184,26141,-42.1,-398,  236,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-12","14:55","15:25",25810,25806, -4.3,-716,   84,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-12","13:05","14:50",25717,25787, 70.7,-2743,-1743,False,"COMPRESSING",150.0,"STOP_HIT"),
            ("2026-01-19","14:15","15:25",25610,25555,-54.5,-537,    1,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-20","15:10","15:25",25217,25225,  8.3,-817,    0,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-21","13:15","15:25",25214,25168,-46.3,-746, -173,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-01-23","13:40","15:25",25049,25064, 15.2,-609,  222,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-02-06","15:05","15:25",25692,25673,-18.9,-795,  -63,False,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-02-16","14:40","15:25",25646,25682, 36.2,-534,  388,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-04-07","15:05","15:25",23125,23129,  4.9, 452, 1155,True,"COMPRESSING",150.0,"EOD_EXIT"),
            ("2026-04-07","14:25","14:55",23015,23096, 81.7,-2921,-2079,False,"COMPRESSING",150.0,"STOP_HIT"),
            ("2026-04-08","13:50","15:25",23964,24012, 48.3,-472,  381,True,"COMPRESSING",150.0,"EOD_EXIT"),
        ],
    },
]



# ============================================================================
# STRATEGY BACKTEST ENGINE — validated on 1,050 trades Apr 2025–Apr 2026
# ============================================================================

_BT_RESULTS = {
    ("Long Call",        "EXPANDING",   "Morning"):   {"wr": 8.4,  "avg": -2890, "n": 155, "cas_avg": -2232},
    ("Long Call",        "EXPANDING",   "Midday"):    {"wr": 19.0, "avg": -2665, "n":  42, "cas_avg": -2232},
    ("Long Call",        "EXPANDING",   "Afternoon"): {"wr": 34.1, "avg": -2390, "n":  41, "cas_avg": -2232},
    ("Long Call",        "COMPRESSING", "Morning"):   {"wr": 32.0, "avg": -1338, "n":  97, "cas_avg": -1047},
    ("Long Call",        "COMPRESSING", "Midday"):    {"wr": 48.0, "avg": -1191, "n":  25, "cas_avg": -1047},
    ("Long Call",        "COMPRESSING", "Afternoon"): {"wr": 50.0, "avg": -1648, "n":  52, "cas_avg": -1047},
    ("Long Call",        "FLAT",        "Morning"):   {"wr": 15.9, "avg": -2582, "n":  63, "cas_avg": -2077},
    ("Long Call",        "FLAT",        "Midday"):    {"wr": 11.1, "avg": -2914, "n":  18, "cas_avg": -2077},
    ("Long Call",        "FLAT",        "Afternoon"): {"wr": 38.9, "avg": -1144, "n":  18, "cas_avg": -2077},
    ("Long Put",         "EXPANDING",   "Morning"):   {"wr": 12.3, "avg": -1851, "n": 114, "cas_avg": -1718},
    ("Long Put",         "EXPANDING",   "Midday"):    {"wr":  0.0, "avg": -3184, "n":  37, "cas_avg": -1718},
    ("Long Put",         "EXPANDING",   "Afternoon"): {"wr": 60.0, "avg": -1041, "n":  30, "cas_avg": -1718},
    ("Long Put",         "COMPRESSING", "Morning"):   {"wr": 15.7, "avg": -1687, "n": 140, "cas_avg": -1345},
    ("Long Put",         "COMPRESSING", "Midday"):    {"wr": 34.3, "avg": -1940, "n":  35, "cas_avg": -1345},
    ("Long Put",         "COMPRESSING", "Afternoon"): {"wr": 47.7, "avg": -1813, "n":  65, "cas_avg": -1345},
    ("Long Put",         "FLAT",        "Morning"):   {"wr":  4.1, "avg": -2722, "n":  74, "cas_avg": -2183},
    ("Long Put",         "FLAT",        "Midday"):    {"wr": 20.8, "avg": -2931, "n":  24, "cas_avg": -2183},
    ("Long Put",         "FLAT",        "Afternoon"): {"wr": 45.0, "avg": -1298, "n":  20, "cas_avg": -2183},
    ("Long Straddle",    "EXPANDING",   "Morning"):   {"wr":  1.0, "avg": -4294, "n":  98, "cas_avg": -4229},
    ("Long Straddle",    "COMPRESSING", "Morning"):   {"wr":  1.4, "avg": -3032, "n":  69, "cas_avg": -2910},
    ("Long Straddle",    "FLAT",        "Morning"):   {"wr":  0.0, "avg": -4173, "n":  37, "cas_avg": -3695},
    ("Bear Put Spread",  "EXPANDING",   "Morning"):   {"wr": 12.3, "avg": -1485, "n": 114, "cas_avg": -1230},
    ("Bear Put Spread",  "EXPANDING",   "Midday"):    {"wr":  0.0, "avg": -2632, "n":  37, "cas_avg": -1230},
    ("Bear Put Spread",  "EXPANDING",   "Afternoon"): {"wr": 60.0, "avg":  -513, "n":  30, "cas_avg": -1230},
    ("Bear Put Spread",  "COMPRESSING", "Morning"):   {"wr": 15.7, "avg": -1207, "n": 140, "cas_avg":  -805},
    ("Bear Put Spread",  "COMPRESSING", "Midday"):    {"wr": 34.3, "avg": -1215, "n":  35, "cas_avg":  -805},
    ("Bear Put Spread",  "COMPRESSING", "Afternoon"): {"wr": 47.7, "avg": -1164, "n":  65, "cas_avg":  -805},
    ("Bear Put Spread",  "FLAT",        "Morning"):   {"wr":  4.1, "avg": -2205, "n":  74, "cas_avg": -1691},
    ("Bear Put Spread",  "FLAT",        "Midday"):    {"wr": 20.8, "avg": -2390, "n":  24, "cas_avg": -1691},
    ("Bear Put Spread",  "FLAT",        "Afternoon"): {"wr": 45.0, "avg":  -894, "n":  20, "cas_avg": -1691},
    ("Bull Call Spread", "EXPANDING",   "Morning"):   {"wr":  8.4, "avg": -1993, "n": 155, "cas_avg": -1459},
    ("Bull Call Spread", "EXPANDING",   "Midday"):    {"wr": 19.0, "avg": -1689, "n":  42, "cas_avg": -1459},
    ("Bull Call Spread", "EXPANDING",   "Afternoon"): {"wr": 34.1, "avg": -1770, "n":  41, "cas_avg": -1459},
    ("Bull Call Spread", "COMPRESSING", "Morning"):   {"wr": 32.0, "avg":  -721, "n":  97, "cas_avg":  -344},
    ("Bull Call Spread", "COMPRESSING", "Midday"):    {"wr": 48.0, "avg":  -642, "n":  25, "cas_avg":  -344},
    ("Bull Call Spread", "COMPRESSING", "Afternoon"): {"wr": 84.6, "avg":  -881, "n":  13, "cas_avg":  -344},  # Floor+COMP 13-15h — backtest confirmed 84.6% WR, Sharpe 96.5
    ("Bull Call Spread", "FLAT",        "Morning"):   {"wr": 15.9, "avg": -1985, "n":  63, "cas_avg": -1424},
    ("Bull Call Spread", "FLAT",        "Midday"):    {"wr": 11.1, "avg": -2123, "n":  18, "cas_avg": -1424},
    ("Bull Call Spread", "FLAT",        "Afternoon"): {"wr": 38.9, "avg":  -580, "n":  18, "cas_avg": -1424},
}

_BT_MONTHLY = [
    ("2025-04", -107353, -125768), ("2025-05", -110740, -133003),
    ("2025-06",  -75345, -100648), ("2025-07",  -36602,  -51703),
    ("2025-08",  -28665,  -44516), ("2025-09",   -8616,  -26134),
    ("2025-10",  -24185,  -44896), ("2025-11",  -33859,  -65646),
    ("2025-12",  -21368,  -44470), ("2026-01",  -42243,  -63823),
    ("2026-02",  -48459,  -74219), ("2026-03", -202592, -228779),
    ("2026-04",  -67690,  -76032),
]

_BT_WINNERS = {
    ("EXPANDING",   "Morning"):   ("Bear Put Spread",  12.3,  -1485),
    ("EXPANDING",   "Midday"):    ("Bull Call Spread", 19.0,  -1689),
    ("EXPANDING",   "Afternoon"): ("Bear Put Spread",  60.0,   -513),
    ("COMPRESSING", "Morning"):   ("Bull Call Spread", 32.0,   -721),
    ("COMPRESSING", "Midday"):    ("Bull Call Spread", 48.0,   -642),
    ("COMPRESSING", "Afternoon"): ("Bull Call Spread", 84.6,   -881),  # Floor+COMP 13-15h backtest: 84.6% WR, Sharpe 96.5
    ("FLAT",        "Morning"):   ("Bull Call Spread", 15.9,  -1985),
    ("FLAT",        "Midday"):    ("Bull Call Spread", 11.1,  -2123),
    ("FLAT",        "Afternoon"): ("Bull Call Spread", 38.9,   -580),
}

_BT_CASCADE_BONUS = {
    ("Bull Call Spread", "COMPRESSING"): {"wr": 50.0, "avg": -344,  "n": 76},  # Full set; w/ Floor filter: 84.6% WR (n=13), Sharpe 96.5
    ("Bear Put Spread",  "COMPRESSING"): {"wr": 30.5, "avg": -805,  "n": 187},
    ("Long Call",        "COMPRESSING"): {"wr": 50.0, "avg": -1047, "n": 76},
    ("Bear Put Spread",  "EXPANDING"):   {"wr": 19.0, "avg": -1230, "n": 137},
    ("Bull Call Spread", "EXPANDING"):   {"wr": 19.5, "avg": -1459, "n": 123},
}


def render_strategy_backtest_tab(iv_regime: str, cascade_bear: float, cascade_bull: float):
    """Render the Strategy Backtest tab with historical performance data."""

    st.markdown("### &#x1F4CA; Strategy Backtest — Historical Performance")
    st.caption(
        "Validated on 1,050 trades (Apr 2025 - Apr 2026). "
        "Spreads use hybrid simulation: real premiums for ATM legs, BSM model for short legs. "
        "All PnL in Rs/lot (NIFTY lot size = 25)."
    )

    from datetime import datetime
    import pytz
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    hr, mn = now.hour, now.minute
    curr_session = get_session_label(hr, mn)
    session_disp = {"MORNING": "Morning 9-11AM", "MIDDAY": "Midday 11AM-1PM",
                    "AFTERNOON": "Afternoon 1-3:30PM"}.get(curr_session, curr_session)

    iv_color = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")

    winner = _BT_WINNERS.get((iv_regime, curr_session.title()), None)
    if winner:
        w_name, w_wr, w_avg = winner
        w_color = "#10b981" if w_avg > -1000 else ("#f59e0b" if w_avg > -1500 else "#ef4444")
        banner_parts = [
            '<div style="background:{0}15;border:2px solid {0}55;border-radius:12px;'
            'padding:14px 18px;margin-bottom:14px;">'.format(iv_color),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;'
            'color:rgba(192,132,252,0.7);text-transform:uppercase;letter-spacing:0.1em;'
            'margin-bottom:8px;">&#x1F3AF; Backtest-Recommended Strategy Now ({} | {})</div>'.format(iv_regime, session_disp),
            '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:1.5rem;'
            'font-weight:800;color:#f1f5f9;">{}</div>'.format(w_name),
            '<div style="display:flex;gap:8px;">',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            'padding:4px 12px;background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);'
            'border-radius:20px;color:#10b981;">WR: {:.1f}%</span>'.format(w_wr),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            'padding:4px 12px;background:{0}15;border:1px solid {0}30;'
            'border-radius:20px;color:{0};">Avg Rs{1:,.0f}/lot</span>'.format(w_color, w_avg),
            '</div></div></div>',
        ]
        st.markdown("".join(banner_parts), unsafe_allow_html=True)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        filter_iv = st.selectbox("Filter IV Regime",
                                  ["All","EXPANDING","COMPRESSING","FLAT"],
                                  index=["All","EXPANDING","COMPRESSING","FLAT"].index(iv_regime)
                                  if iv_regime in ["EXPANDING","COMPRESSING","FLAT"] else 0,
                                  key="bt_iv_filter")
    with fc2:
        filter_sess = st.selectbox("Filter Session",
                                    ["All","Morning","Midday","Afternoon"],
                                    key="bt_sess_filter")
    with fc3:
        filter_strat = st.selectbox("Filter Strategy",
                                     ["All","Long Call","Long Put","Long Straddle",
                                      "Bear Put Spread","Bull Call Spread"],
                                     key="bt_strat_filter")

    rows = []
    for (strat, iv, sess), vals in _BT_RESULTS.items():
        if filter_iv    != "All" and iv    != filter_iv:    continue
        if filter_sess  != "All" and sess  != filter_sess:  continue
        if filter_strat != "All" and strat != filter_strat: continue
        is_current = (iv == iv_regime and sess == curr_session.title())
        cascade_bonus = _BT_CASCADE_BONUS.get((strat, iv), {})
        rows.append({
            "Strategy":          strat,
            "IV Regime":         iv,
            "Session":           sess,
            "WR %":              vals["wr"],
            "Avg PnL/lot":       vals["avg"],
            "n (trades)":        vals["n"],
            "Cascade>=150 WR%":  cascade_bonus.get("wr", ""),
            "Cascade>=150 Avg":  cascade_bonus.get("avg", ""),
            "Current?":          "LIVE NOW" if is_current else "",
        })

    import pandas as _pd2
    tbl = _pd2.DataFrame(rows).sort_values("Avg PnL/lot", ascending=False)

    def _color_pnl(val):
        if not isinstance(val, (int, float)): return ""
        if val > -500:  return "background-color:rgba(16,185,129,0.20);color:#6ee7b7;"
        if val > -1000: return "background-color:rgba(16,185,129,0.10);color:#a7f3d0;"
        if val > -1500: return "background-color:rgba(245,158,11,0.10);color:#fcd34d;"
        if val > -2000: return "background-color:rgba(239,68,68,0.10);color:#fca5a5;"
        return "background-color:rgba(239,68,68,0.20);color:#f87171;"

    def _color_wr(val):
        if not isinstance(val, (int, float)): return ""
        if val >= 50: return "color:#10b981;font-weight:700;"
        if val >= 35: return "color:#6ee7b7;"
        if val >= 20: return "color:#fcd34d;"
        return "color:#f87171;"

    styled = (tbl.style
    .map(_color_pnl, subset=["Avg PnL/lot"])
    .map(_color_wr,  subset=["WR %"]))

    st.dataframe(styled, use_container_width=True, hide_index=True, height=420)

    st.markdown("---")
    st.markdown("#### &#x1F4A1; Key Backtest Findings")

    insights = [
        ("&#x1F3C6; Best single combo",
         "Bull Call Spread + COMPRESSING + Cascade>=150",
         "WR 50%, avg Rs-344/lot (n=76) — highest win rate with lowest avg loss"),
        ("&#x1F4C9; Worst to avoid",
         "Long Straddle in any regime",
         "WR less than 2% across all sessions — premium decay kills both legs"),
        ("&#x26A1; Cascade filter impact",
         "Bear Put Spread + COMPRESSING + Cascade>=150 vs all",
         "avg Rs-805 vs Rs-1,207 — 33% improvement in avg loss"),
        ("&#x1F552; Best time window",
         "EXPANDING IV + Afternoon for Bear Put Spread",
         "60% WR, avg Rs-513 — afternoon VANNA unwind captured"),
        ("&#x1F6AB; Structural trap",
         "Long Straddle + EXPANDING midday",
         "0% WR, avg Rs-4,294 — EXPANDING IV expands one side, destroys the other"),
    ]

    for icon, title, desc in insights:
        parts = [
            '<div style="background:rgba(15,23,42,0.7);border-left:3px solid #7c3aed;'
            'border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px;">',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.82rem;'
            'font-weight:700;color:#e2e8f0;margin-bottom:3px;">{} {}</div>'.format(icon, title),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;'
            'color:#94a3b8;line-height:1.5;">{}</div>'.format(desc),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### &#x1F4C8; Monthly Equity: Bear Put Spread vs Long Put")

    months   = [r[0] for r in _BT_MONTHLY]
    bps_vals = [r[1] for r in _BT_MONTHLY]
    lp_vals  = [r[2] for r in _BT_MONTHLY]
    saved    = [r[2]-r[1] for r in _BT_MONTHLY]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months, y=bps_vals, name="Bear Put Spread",
        marker_color=["rgba(16,185,129,0.7)" if v > -50000 else
                      ("rgba(245,158,11,0.7)" if v > -100000 else "rgba(239,68,68,0.7)")
                      for v in bps_vals],
    ))
    fig.add_trace(go.Scatter(
        x=months, y=lp_vals, name="Long Put (baseline)",
        line=dict(color="#94a3b8", width=2, dash="dot"), mode="lines+markers",
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=months, y=saved, name="Rs Saved by Spread",
        line=dict(color="#10b981", width=1.5), mode="lines",
        fill="tozeroy", fillcolor="rgba(16,185,129,0.08)", yaxis="y2",
    ))
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15,23,42,0)",
        plot_bgcolor="rgba(15,23,42,0.4)",
        height=360, margin=dict(l=40,r=40,t=20,b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(family="JetBrains Mono", size=10)),
        yaxis=dict(title="PnL Rs", gridcolor="rgba(148,163,184,0.1)"),
        yaxis2=dict(title="Rs Saved", overlaying="y", side="right",
                    showgrid=False, tickfont=dict(color="#10b981")),
        xaxis=dict(gridcolor="rgba(148,163,184,0.06)"),
        barmode="group",
    )
    st.plotly_chart(fig, use_container_width=True)

    total_saved = sum(saved)
    st.markdown(
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#10b981;'
        'text-align:center;margin-top:-8px;">&#x1F4B0; Bear Put Spread saved Rs{:,.0f} vs Long Put '
        'over 13 months</div>'.format(total_saved),
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="margin-top:12px;font-family:JetBrains Mono,monospace;font-size:0.62rem;'
        'color:#475569;padding:8px 12px;background:rgba(15,23,42,0.5);border-radius:6px;">'
        '&#9888;&#65039; Backtest uses real premiums for ATM+/-1 legs. '
        'Spread short legs estimated via Black-Scholes. '
        'Past performance does not guarantee future results. Not financial advice.'
        '</div>',
        unsafe_allow_html=True,
    )

def render_profit_setups_tab():
    """Render the Profitable Setups tab with validated trade lists."""

    st.markdown("### &#x1F4B0; Profitable Setups — Backtested Trade Lists")
    st.caption(
        "Exhaustive search across 1,050 trades (Apr 2025 – Apr 2026). "
        "Only setups with n ≥ 8 and WR ≥ 65% or avg PnL > ₹0 are shown. "
        "Spread short legs modelled via Black-Scholes at entry/exit spot."
    )

    # ── Setup selector ────────────────────────────────────────────────────────
    setup_names = [f"{s['id']}: {s['name']} ({s['wr']:.0f}% WR)" for s in _PROFIT_SETUPS]
    sel_idx = st.radio("Select Setup", range(len(setup_names)),
                       format_func=lambda i: setup_names[i],
                       horizontal=True, key="profit_setup_selector")
    setup = _PROFIT_SETUPS[sel_idx]

    color = setup["color"]

    # ── Setup header ──────────────────────────────────────────────────────────
    hdr = [
        '<div style="background:{0}12;border:2px solid {0}55;border-radius:14px;'
        'padding:16px 20px;margin:10px 0 14px 0;">'.format(color),
        '<div style="font-family:Space Grotesk,sans-serif;font-size:1.2rem;'
        'font-weight:800;color:{0};margin-bottom:4px;">&#x2728; {1}</div>'.format(color, setup["name"]),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
        'color:#94a3b8;margin-bottom:12px;">Entry Conditions: <b style="color:#e2e8f0;">'
        '{}</b></div>'.format(setup["conditions"]),
        '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;">',
    ]
    for lbl, val, c in [
        ("Total Trades", str(setup["n"]), "#94a3b8"),
        ("Win Rate",  f"{setup['wr']:.1f}%", "#10b981"),
        ("Avg PnL/lot", f"₹{setup['avg_pnl']:+,.0f}", color),
        ("Total PnL",   f"₹{setup['total_pnl']:+,.0f}", color),
        ("Best Trade",  f"₹{setup['best']:+,.0f}", "#10b981"),
        ("Worst Trade", f"₹{setup['worst']:+,.0f}", "#ef4444"),
    ]:
        hdr += [
            '<div style="flex:1;min-width:100px;padding:8px 12px;'
            'background:rgba(255,255,255,0.04);border:1px solid rgba(148,163,184,0.12);'
            'border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;'
            'color:#64748b;">{}</div>'.format(lbl),
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.88rem;'
            'font-weight:700;color:{};">{}</div>'.format(c, val),
            '</div>',
        ]
    hdr += ['</div>',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;'
            'color:#f59e0b;padding:6px 10px;background:rgba(245,158,11,0.07);'
            'border-radius:4px;">&#x1F4A1; {}</div>'.format(setup["signal_note"]),
            '</div>']
    st.markdown("".join(hdr), unsafe_allow_html=True)

    # ── Trade list table ──────────────────────────────────────────────────────
    st.markdown("#### &#x1F4CB; Full Trade Log")

    import pandas as _pd3
    trades = setup["trades"]
    rows = []
    cumulative = 0
    for t in trades:
        cumulative += t[7]
        rows.append({
            "Date":        t[0],
            "Entry":       t[1],
            "Exit":        t[2],
            "Entry Spot":  f"₹{t[3]:,.0f}",
            "Exit Spot":   f"₹{t[4]:,.0f}",
            "Spot Pts":    f"{t[5]:+.1f}",
            "1-Leg PnL":   f"₹{t[6]:+,.0f}",
            "Spread PnL":  t[7],
            "W/L":         "✅ WIN" if t[8] else "❌ LOSS",
            "IV":          t[9],
            "Cascade":     t[10],
            "Exit Reason": t[11],
            "Cumulative":  cumulative,
        })

    tbl = _pd3.DataFrame(rows)

    def _style_row(row):
        base = [""] * len(row)
        if row["W/L"] == "✅ WIN":
            return ["background-color:rgba(16,185,129,0.10)"] * len(row)
        elif row["Exit Reason"] == "STOP_HIT":
            return ["background-color:rgba(239,68,68,0.18)"] * len(row)
        return ["background-color:rgba(239,68,68,0.06)"] * len(row)

    def _style_pnl(val):
        if not isinstance(val, (int, float)): return ""
        return "color:#10b981;font-weight:700;" if val > 0 else "color:#ef4444;"

    styled = (tbl.style
    .apply(_style_row, axis=1)
    .map(_style_pnl, subset=["Spread PnL","Cumulative"]))

    st.dataframe(styled, use_container_width=True, hide_index=True, height=460)

    # ── Equity curve ─────────────────────────────────────────────────────────
    st.markdown("#### &#x1F4C8; Equity Curve")
    dates  = [t[0] for t in trades]
    pnls   = [t[7] for t in trades]
    cumul  = []
    running = 0
    for p in pnls:
        running += p
        cumul.append(running)

    colors_bar = ["rgba(16,185,129,0.7)" if p > 0 else "rgba(239,68,68,0.7)" for p in pnls]
    stop_xs = [dates[i] for i,t in enumerate(trades) if t[11]=="STOP_HIT"]
    stop_ys = [cumul[i] for i,t in enumerate(trades) if t[11]=="STOP_HIT"]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(len(dates))), y=pnls,
                         marker_color=colors_bar, name="Trade PnL",
                         text=[f"₹{p:+,.0f}" for p in pnls],
                         textposition="outside", textfont=dict(size=9)))
    fig.add_trace(go.Scatter(x=list(range(len(dates))), y=cumul,
                              mode="lines+markers",
                              line=dict(color=color, width=2.5),
                              marker=dict(size=5), name="Cumulative PnL",
                              yaxis="y2"))
    if stop_xs:
        stop_idxs = [i for i,t in enumerate(trades) if t[11]=="STOP_HIT"]
        fig.add_trace(go.Scatter(
            x=stop_idxs, y=[cumul[i] for i in stop_idxs],
            mode="markers", name="STOP_HIT",
            marker=dict(symbol="x", size=14, color="#ef4444", line=dict(width=2)),
        ))
    fig.add_hline(y=0, line_dash="dash", line_color="#475569", line_width=1)
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15,23,42,0)",
        plot_bgcolor="rgba(15,23,42,0.4)",
        height=380, margin=dict(l=40,r=40,t=20,b=60),
        xaxis=dict(tickvals=list(range(len(dates))),
                   ticktext=[f"{d[5:7]}/{d[8:10]}" for d in dates],
                   tickangle=45, gridcolor="rgba(148,163,184,0.06)"),
        yaxis=dict(title="Trade PnL ₹", gridcolor="rgba(148,163,184,0.1)"),
        yaxis2=dict(title="Cumulative ₹", overlaying="y", side="right",
                    showgrid=False, tickfont=dict(color=color)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(family="JetBrains Mono", size=10)),
        bargap=0.25,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Monthly breakdown ─────────────────────────────────────────────────────
    st.markdown("#### &#x1F4C5; Monthly Performance")
    m_rows = []
    for ym, total, trades_n, wins in setup["monthly"]:
        wr = wins/trades_n*100 if trades_n>0 else 0
        m_rows.append({"Month":ym,"Total PnL":total,"Trades":trades_n,
                        "Wins":wins,"WR%":round(wr,1)})
    m_df = _pd3.DataFrame(m_rows)

    def _m_color(val):
        if not isinstance(val,(int,float)): return ""
        return "color:#10b981;font-weight:700;" if val>0 else "color:#ef4444;"

    st.dataframe(
        m_df.style.map(_m_color, subset=["Total PnL"]),
        use_container_width=True, hide_index=True
    )

    # ── Key rules ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### &#x1F4CB; Entry Checklist for This Setup")

    rules = {
        "S1": [
            "&#x2705; IV Regime = COMPRESSING (check Tab 5 VANNA or Tab 0 IV panel)",
            "&#x2705; Entry time between 1:00 PM – 3:20 PM IST",
            "&#x2705; Cascade Pts ≥ 150 (check Tab 3 Enhanced OI GEX cascade table)",
            "&#x2705; NOT an expiry day (sidebar Expiry Code 1 on non-Thursday/Friday)",
            "&#x2705; Buy ATM+1 CALL + Sell ATM+3 CALL simultaneously",
            "&#x2705; Hold to EOD (3:25 PM) — do NOT use a stop loss",
            "&#x274C; Skip if IV is EXPANDING or FLAT",
            "&#x274C; Skip if Cascade Pts < 150",
            "&#x274C; Skip on expiry days — pin risk destroys spread value",
        ],
        "S2": [
            "&#x2705; IV Regime = COMPRESSING",
            "&#x2705; Entry time between 11:00 AM – 3:20 PM IST (wider window)",
            "&#x2705; Cascade Pts ≥ 125",
            "&#x2705; NOT an expiry day",
            "&#x2705; Buy ATM+1 CALL + Sell ATM+3 CALL",
            "&#x2705; Hold to EOD — no stop loss",
            "&#x26A0;&#xFE0F; One outlier (2025-06-24 STOP_HIT) destroyed ₹2,551 — the stop cost more than 4 winning trades",
        ],
        "S3": [
            "&#x2705; IV Regime = COMPRESSING",
            "&#x2705; Entry time between 1:00 PM – 3:20 PM IST",
            "&#x2705; Cascade Pts ≥ 150",
            "&#x2705; NOT an expiry day",
            "&#x2705; Buy ATM-1 PUT + Sell ATM-3 PUT",
            "&#x2705; Hold to EOD only — 4 STOP_HIT trades destroyed total profitability",
            "&#x274C; This setup is breakeven (₹-635 total) — use Setup 1 for profits",
            "&#x26A0;&#xFE0F; EOD-only filter (remove all STOP_HIT trades) makes this profitable: +₹4,401 from 34 trades",
        ],
    }

    for rule in rules.get(setup["id"], []):
        color_r = "#10b981" if "✅" in rule or "2705" in rule else (
                  "#ef4444" if "❌" in rule or "274C" in rule else "#f59e0b")
        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            'color:{};padding:3px 0;line-height:1.6;">{}</div>'.format(color_r, rule),
            unsafe_allow_html=True
        )

    st.markdown(
        '<div style="margin-top:12px;font-family:JetBrains Mono,monospace;font-size:0.62rem;'
        'color:#475569;padding:8px 12px;background:rgba(15,23,42,0.5);border-radius:6px;">'
        '&#9888;&#65039; All trades are historical simulations. Spread short leg premiums estimated via BSM. '
        'Past performance does not guarantee future results. Not SEBI-registered investment advice.'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# LIVE STRATEGY SCREENER — Real-time option prices via Dhan API
# Scans all strategies against live data, scores and ranks them
# ============================================================================

import math as _ms
from scipy.stats import norm as _ns

def _bs_live(S, K, T, r, sigma, opt="CE"):
    """BSM price for live screener."""
    if T <= 0 or sigma <= 0:
        return max(S-K,0) if opt=="CE" else max(K-S,0)
    d1 = (_ms.log(S/K) + (r+0.5*sigma**2)*T) / (sigma*_ms.sqrt(T))
    d2 = d1 - sigma*_ms.sqrt(T)
    if opt=="CE": return S*_ns.cdf(d1) - K*_ms.exp(-r*T)*_ns.cdf(d2)
    return K*_ms.exp(-r*T)*_ns.cdf(-d2) - S*_ns.cdf(-d1)

def _bs_pop(S, K_be, T, sigma):
    """BSM probability that spot will be above/below breakeven."""
    if T <= 0 or sigma <= 0: return 50.0
    try:
        d = (_ms.log(S / K_be)) / (sigma * _ms.sqrt(T))
        return float(_ns.cdf(d) * 100)
    except Exception:
        return 50.0

def _bs_delta(S, K, T, r, sigma, opt="CE"):
    if T <= 0 or sigma <= 0: return 0.0
    d1 = (_ms.log(S/K) + (r+0.5*sigma**2)*T)/(sigma*_ms.sqrt(T))
    return float(_ns.cdf(d1)) if opt=="CE" else float(_ns.cdf(d1)-1)


def fetch_live_option_prices(symbol, df_selected, meta):
    """
    Fetch REAL option LTP via Dhan option chain API.
    Primary: GET /v2/optionchain  -> live LTP for every strike
    Fallback 1: call_close / put_close from last fetched bar (historical close)
    Fallback 2: BSM using IV from df_selected
    Returns dict: {strike: {"CE": ltp, "PE": ltp, "call_iv": v, "put_iv": v, "source": str}}
    """
    import math as _mf
    from scipy.stats import norm as _nf

    if df_selected is None or len(df_selected) == 0:
        return {}

    spot     = float(df_selected["spot_price"].iloc[0]) if "spot_price" in df_selected.columns else 0
    r_rate   = 0.065
    tte_days = 7 if meta.get("expiry_flag","WEEK") == "WEEK" else 30
    tte      = tte_days / 365
    expiry_flag = meta.get("expiry_flag","WEEK")
    expiry_code = int(meta.get("expiry_code", 1))

    def bsm_px(S, K, T, iv_pct, opt="CE"):
        sigma = (iv_pct / 100) if iv_pct > 1 else iv_pct
        sigma = max(sigma, 0.05)
        if T <= 0 or S <= 0 or K <= 0:
            return max(S-K, 0) if opt == "CE" else max(K-S, 0)
        try:
            d1 = (_mf.log(S/K) + (r_rate + 0.5*sigma**2)*T) / (sigma*_mf.sqrt(T))
            d2 = d1 - sigma*_mf.sqrt(T)
            if opt == "CE":
                return max(S*_nf.cdf(d1) - K*_mf.exp(-r_rate*T)*_nf.cdf(d2), 0)
            return max(K*_mf.exp(-r_rate*T)*_nf.cdf(-d2) - S*_nf.cdf(-d1), 0)
        except Exception:
            return max(S-K, 0) if opt == "CE" else max(K-S, 0)

    # ── Step 1: Try Dhan Option Chain API for live LTP ────────────────────────
    chain_prices = {}
    try:
        config     = DhanConfig()
        headers    = {
            "access-token": config.access_token,
            "client-id":    config.client_id,
            "Content-Type": "application/json",
        }
        sec_id     = DHAN_INDEX_SECURITY_IDS.get(symbol) or DHAN_STOCK_SECURITY_IDS.get(symbol)
        exchange   = "BSE_FNO" if symbol in BSE_FNO_SYMBOLS else "NSE_FNO"
        instrument = "OPTIDX" if symbol in DHAN_INDEX_SECURITY_IDS else "OPTSTK"

        if sec_id:
            payload = {
                "UnderlyingScrip": int(sec_id),
                "UnderlyingSeg":   exchange,
                "Expiry":          expiry_flag,
                "ExpiryCode":      expiry_code,
            }
            resp = requests.post(
                "https://api.dhan.co/v2/optionchain",
                headers=headers, json=payload, timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                # Dhan option chain response structure:
                # data["data"] = list of {strike_price, call_ltp, put_ltp, call_iv, put_iv, ...}
                chain_data = data.get("data", data.get("optionData", []))
                if isinstance(chain_data, list):
                    for item in chain_data:
                        k = float(item.get("strikePrice", item.get("strike_price", 0)))
                        if k <= 0: continue
                        chain_prices[k] = {
                            "CE":      float(item.get("callLTP",  item.get("call_ltp",  0)) or 0),
                            "PE":      float(item.get("putLTP",   item.get("put_ltp",   0)) or 0),
                            "call_iv": float(item.get("callIV",   item.get("call_iv",  18)) or 18),
                            "put_iv":  float(item.get("putIV",    item.get("put_iv",   18)) or 18),
                            "source":  "LIVE",
                        }
                elif isinstance(chain_data, dict):
                    # Alternative response format: {"CE": {...}, "PE": {...}}
                    for opt_type, strikes in chain_data.items():
                        if opt_type not in ("CE","PE","callData","putData"): continue
                        ot = "CE" if "call" in opt_type.lower() or opt_type=="CE" else "PE"
                        for strike_str, vals in strikes.items():
                            try:
                                k = float(strike_str)
                                if k not in chain_prices:
                                    chain_prices[k] = {"CE":0,"PE":0,"call_iv":18,"put_iv":18,"source":"LIVE"}
                                chain_prices[k][ot]  = float(vals.get("ltp", vals.get("LTP", 0)) or 0)
                                iv_key = "call_iv" if ot=="CE" else "put_iv"
                                chain_prices[k][iv_key] = float(vals.get("iv", vals.get("IV", 18)) or 18)
                            except Exception: continue
    except Exception as _chain_err:
        pass  # silent fallback

    # ── Step 2: Build final prices dict — live > bar close > BSM ─────────────
    prices = {}
    for _, row in df_selected.iterrows():
        k   = float(row["strike"])
        civ = float(row.get("call_iv", 18) or 18)
        piv = float(row.get("put_iv",  18) or 18)

        # Try LIVE chain first
        if k in chain_prices and chain_prices[k]["CE"] > 0:
            prices[k] = chain_prices[k].copy()
            prices[k]["call_iv"] = chain_prices[k]["call_iv"] or civ
            prices[k]["put_iv"]  = chain_prices[k]["put_iv"]  or piv
            continue

        # Try last bar close
        ce_bar = float(row.get("call_close", 0) or 0)
        pe_bar = float(row.get("put_close",  0) or 0)

        if ce_bar > 0 or pe_bar > 0:
            prices[k] = {
                "CE":      ce_bar  if ce_bar  > 0 else bsm_px(spot, k, tte, civ, "CE"),
                "PE":      pe_bar  if pe_bar  > 0 else bsm_px(spot, k, tte, piv, "PE"),
                "call_iv": civ, "put_iv": piv,
                "source":  "BAR_CLOSE",
            }
            continue

        # BSM fallback
        prices[k] = {
            "CE":      bsm_px(spot, k, tte, civ, "CE"),
            "PE":      bsm_px(spot, k, tte, piv, "PE"),
            "call_iv": civ, "put_iv": piv,
            "source":  "BSM",
        }

    return prices


def screen_all_strategies(spot_price, strikes_sorted, live_prices, iv_regime,
                           cascade_bear, cascade_bull, vanna_zones,
                           lot_size, tte, symbol):
    """
    Screens all strategy templates against live data.
    Returns list of scored strategy dicts.
    """
    r = 0.065
    interval = strikes_sorted[1] - strikes_sorted[0] if len(strikes_sorted) > 1 else 50
    atm = min(strikes_sorted, key=lambda x: abs(x - spot_price))

    # Positive GEX strikes (absorption)
    pos_gex_above = [s for s in strikes_sorted if s > spot_price]
    pos_gex_below = [s for s in strikes_sorted if s < spot_price]

    def nearest(target):
        return min(strikes_sorted, key=lambda x: abs(x-target))

    def px(strike, opt):
        """Get real premium; BSM fallback already applied in fetch_live_option_prices."""
        if strike not in live_prices:
            # full BSM fallback for strikes not in live_prices
            iv_default = 0.18
            return _bs_live(spot_price, strike, tte, r, iv_default, opt)
        raw = live_prices[strike].get(opt, 0.0)
        if raw > 0:
            return raw
        # BSM fallback using real IV
        iv_raw = live_prices[strike].get("call_iv" if opt=="CE" else "put_iv", 18.0)
        iv     = (iv_raw / 100) if iv_raw > 1 else iv_raw
        return _bs_live(spot_price, strike, tte, r, max(iv, 0.05), opt)

    def get_iv(strike, opt):
        if strike not in live_prices: return 18.0
        iv_raw = live_prices[strike].get("call_iv" if opt=="CE" else "put_iv", 18.0)
        return float(iv_raw) if iv_raw > 0 else 18.0

    def get_iv_pct(strike, opt):
        """Return IV as percentage (0-100 range)."""
        iv = get_iv(strike, opt)
        return iv if iv > 1 else iv * 100

    def price_source(strike):
        if strike not in live_prices: return "BSM"
        return live_prices[strike].get("source", "BSM")

    vacuums   = [z for z in vanna_zones if z["role"]=="VACUUM_ZONE"]
    floors    = [z for z in vanna_zones if z["role"]=="SUPPORT_FLOOR"]
    traps     = [z for z in vanna_zones if z["role"]=="TRAP_DOOR"]
    gex_bias  = "BULL" if cascade_bull > cascade_bear else "BEAR"
    max_cas   = max(cascade_bear, cascade_bull)

    # ── Strategy templates ────────────────────────────────────────────────────
    sc_above = nearest(pos_gex_above[0]) if pos_gex_above else nearest(atm + interval*3)
    sc_below = nearest(pos_gex_below[0]) if pos_gex_below else nearest(atm - interval*3)

    # ── Cascade-aware strike selection ───────────────────────────────────────
    # Bear strategies: use positive GEX below spot as short leg (absorption)
    # Bull strategies: use positive GEX above spot as short leg (absorption)
    bear_short = nearest(sc_below) if pos_gex_below else nearest(atm - interval*3)
    bull_short = nearest(sc_above) if pos_gex_above else nearest(atm + interval*3)

    # Bear cascade active: prefer bear strategies; bull cascade: prefer bull
    bear_cascade_active = cascade_bear >= 100
    bull_cascade_active = cascade_bull >= 100

    templates = [
        # ── PROVEN PROFITABLE (stars from backtest) ───────────────────────────
        {
            "name": "Bull Call Spread",
            "stars": 5,  # 87.5% WR, +Rs618 avg — BEST SETUP
            "legs": [
                {"strike": atm,        "opt": "CE", "action": "BUY",  "qty": 1},
                {"strike": bull_short, "opt": "CE", "action": "SELL", "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Afternoon (13–15h)",
            "best_wr": 87.5, "cascade_dir": "BULL",
            "note": "Backtest: 87.5% WR, avg +Rs618/lot in COMPRESSING afternoon. Floor+COMP 13–15h = 84.6% WR, Sharpe 96.5 (highest single setup)",
        },
        {
            "name": "Bear Put Spread",
            "stars": 4,  # 68.4% WR, near breakeven
            "legs": [
                {"strike": atm,        "opt": "PE", "action": "BUY",  "qty": 1},
                {"strike": bear_short, "opt": "PE", "action": "SELL", "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Afternoon",
            "best_wr": 68.4, "cascade_dir": "BEAR",
            "note": "Backtest: 68.4% WR — best with EOD exit, no stop loss",
        },
        {
            "name": "Bear Call Spread",
            "stars": 3,  # credit spread, bear bias
            "legs": [
                {"strike": bull_short,                      "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": nearest(bull_short+interval*2),  "opt": "CE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "EXPANDING", "best_sess": "Midday",
            "best_wr": 60.0, "cascade_dir": "BEAR",
            "note": "Short at GEX absorption above spot — collect credit while wall holds",
        },
        {
            "name": "Bull Put Spread",
            "stars": 3,  # credit spread, bull bias
            "legs": [
                {"strike": bear_short,                      "opt": "PE", "action": "SELL", "qty": 1},
                {"strike": nearest(bear_short-interval*2),  "opt": "PE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Morning",
            "best_wr": 55.0, "cascade_dir": "BULL",
            "note": "Short at GEX floor below spot — collect credit while floor holds",
        },
        # ── DIRECTIONAL (moderate conviction) ────────────────────────────────
        {
            "name": "Long Put",
            "stars": 3,
            "legs": [
                {"strike": atm, "opt": "PE", "action": "BUY", "qty": 1},
            ],
            "best_iv": "EXPANDING", "best_sess": "Afternoon",
            "best_wr": 60.0, "cascade_dir": "BEAR",
            "note": "Best in EXPANDING IV afternoon — 60% WR when bear cascade >= 150",
        },
        {
            "name": "Long Call",
            "stars": 3,
            "legs": [
                {"strike": atm, "opt": "CE", "action": "BUY", "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Afternoon",
            "best_wr": 50.0, "cascade_dir": "BULL",
            "note": "Best with Support Floor + COMPRESSING IV, afternoon (13–15h) — 84.6% WR, Sharpe 96.5 (highest backtest)",
        },
        # ── RANGE / NEUTRAL ───────────────────────────────────────────────────
        {
            "name": "Iron Condor",
            "stars": 3,
            "legs": [
                {"strike": bull_short,                      "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": nearest(bull_short+interval*2),  "opt": "CE", "action": "BUY",  "qty": 1},
                {"strike": bear_short,                      "opt": "PE", "action": "SELL", "qty": 1},
                {"strike": nearest(bear_short-interval*2),  "opt": "PE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Any",
            "best_wr": 55.0, "cascade_dir": "NEUTRAL",
            "note": "Short strikes at GEX walls — natural range boundaries from cascade",
        },
        {
            "name": "Iron Butterfly",
            "stars": 2,
            "legs": [
                {"strike": atm,                    "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": nearest(atm+interval*4),"opt": "CE", "action": "BUY",  "qty": 1},
                {"strike": atm,                    "opt": "PE", "action": "SELL", "qty": 1},
                {"strike": nearest(atm-interval*4),"opt": "PE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Any",
            "best_wr": 45.0, "cascade_dir": "NEUTRAL",
            "note": "Body at ATM GEX peak — works best on expiry pinning days",
        },
        # ── VOLATILITY ────────────────────────────────────────────────────────
        {
            "name": "Long Straddle",
            "stars": 1,  # poor backtest — 1-2% WR
            "legs": [
                {"strike": atm, "opt": "CE", "action": "BUY", "qty": 1},
                {"strike": atm, "opt": "PE", "action": "BUY", "qty": 1},
            ],
            "best_iv": "EXPANDING", "best_sess": "Morning",
            "best_wr": 20.0, "cascade_dir": "NEUTRAL",
            "note": "WARNING: Backtest shows <2% WR — IV decay destroys both legs",
        },
        {
            "name": "Long Strangle",
            "stars": 2,
            "legs": [
                {"strike": nearest(atm+interval*2), "opt": "CE", "action": "BUY", "qty": 1},
                {"strike": nearest(atm-interval*2), "opt": "PE", "action": "BUY", "qty": 1},
            ],
            "best_iv": "EXPANDING", "best_sess": "Morning",
            "best_wr": 25.0, "cascade_dir": "NEUTRAL",
            "note": "OTM strangle — cheaper than straddle, needs bigger move to profit",
        },
        {
            "name": "Short Strangle",
            "stars": 3,
            "legs": [
                {"strike": bull_short, "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": bear_short, "opt": "PE", "action": "SELL", "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Any",
            "best_wr": 55.0, "cascade_dir": "NEUTRAL",
            "note": "Short at GEX walls — unlimited risk, only in low cascade regimes",
        },
        # ── ADVANCED ─────────────────────────────────────────────────────────
        {
            "name": "Synthetic Future",
            "stars": 2,
            "legs": [
                {"strike": atm, "opt": "CE", "action": "BUY",  "qty": 1},
                {"strike": atm, "opt": "PE", "action": "SELL", "qty": 1},
            ],
            "best_iv": "FLAT", "best_sess": "Any",
            "best_wr": 40.0, "cascade_dir": "BULL",
            "note": "Futures equivalent via options — use only when direction is very clear",
        },
        {
            "name": "Ratio Put Spread",
            "stars": 2,
            "legs": [
                {"strike": atm,                    "opt": "PE", "action": "BUY",  "qty": 1},
                {"strike": nearest(atm-interval*2),"opt": "PE", "action": "SELL", "qty": 2},
            ],
            "best_iv": "FLAT", "best_sess": "Any",
            "best_wr": 40.0, "cascade_dir": "BEAR",
            "note": "Asymmetric bear — profits from mild fall, danger if large fall",
        },
        {
            "name": "Ratio Call Spread",
            "stars": 2,
            "legs": [
                {"strike": atm,                    "opt": "CE", "action": "BUY",  "qty": 1},
                {"strike": nearest(atm+interval*2),"opt": "CE", "action": "SELL", "qty": 2},
            ],
            "best_iv": "FLAT", "best_sess": "Any",
            "best_wr": 40.0, "cascade_dir": "BULL",
            "note": "Asymmetric bull — profits from mild rise, danger if large rise",
        },
        {
            "name": "Jade Lizard",
            "stars": 3,
            "legs": [
                {"strike": bear_short,                     "opt": "PE", "action": "SELL", "qty": 1},
                {"strike": bull_short,                     "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": nearest(bull_short+interval*2), "opt": "CE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "COMPRESSING", "best_sess": "Any",
            "best_wr": 55.0, "cascade_dir": "BULL",
            "note": "No upside risk — short put + bear call spread, net credit strategy",
        },
        {
            "name": "Calendar Spread",
            "stars": 2,
            "legs": [
                {"strike": atm, "opt": "CE", "action": "SELL", "qty": 1},
                {"strike": atm, "opt": "CE", "action": "BUY",  "qty": 1},
            ],
            "best_iv": "FLAT", "best_sess": "Any",
            "best_wr": 45.0, "cascade_dir": "NEUTRAL",
            "note": "Sell near-term, buy far-term — profits from IV term structure",
        },
    ]

    results = []
    for tmpl in templates:
        legs = tmpl["legs"]
        # ── Compute P&L, cost, breakevens ────────────────────────────────────
        net_premium = 0.0
        leg_details = []
        all_iv = []
        for leg in legs:
            k, opt, act, qty = leg["strike"], leg["opt"], leg["action"], leg["qty"]
            price = px(k, opt)
            iv_v  = get_iv(k, opt)
            all_iv.append(iv_v)
            sign = 1 if act=="BUY" else -1
            net_premium += sign * price * qty
            iv_v_pct = iv_v if iv_v > 1 else iv_v * 100  # ensure pct form
            leg_details.append({"k":k,"opt":opt,"act":act,"qty":qty,"px":price,
                                 "iv":iv_v_pct, "iv_dec": iv_v_pct/100,
                                 "source": price_source(k)})

        total_cost = abs(net_premium) * lot_size
        is_debit   = net_premium > 0
        avg_iv     = sum(v/100 if v>1 else v for v in all_iv) / max(len(all_iv), 1)

        # Breakeven + POP
        spot_range = list(range(int(spot_price*0.90), int(spot_price*1.10), max(int(interval/2),1)))
        payoff_pts = []
        for s in spot_range:
            pnl = 0.0
            for leg in leg_details:
                intr = max(s-leg["k"],0) if leg["opt"]=="CE" else max(leg["k"]-s,0)
                lp   = (intr - leg["px"]) if leg["act"]=="BUY" else (leg["px"] - intr)
                pnl += lp * leg["qty"] * lot_size
            payoff_pts.append((s, pnl))

        breakevens = []
        for i in range(len(payoff_pts)-1):
            if payoff_pts[i][1] * payoff_pts[i+1][1] < 0:
                be = payoff_pts[i][0] - payoff_pts[i][1]*(
                    payoff_pts[i+1][0]-payoff_pts[i][0])/(
                    payoff_pts[i+1][1]-payoff_pts[i][1])
                breakevens.append(be)

        max_profit = max(p[1] for p in payoff_pts)
        max_loss   = min(p[1] for p in payoff_pts)

        # POP via BSM
        if breakevens and avg_iv > 0 and tte > 0:
            pop_vals = []
            for be in breakevens:
                pop_vals.append(_bs_pop(spot_price, be, tte, avg_iv))
            pop_pct = sum(pop_vals) / len(pop_vals)
            if not is_debit:
                pop_pct = 100 - pop_pct
        else:
            pop_pct = 50.0

        # R:R ratio
        rr = abs(max_profit / max_loss) if max_loss < -1 and max_profit < 1e6 else 0.0

        # ── Regime + cascade score (equal treatment for bear and bull) ─────────
        strat_stars    = tmpl.get("stars", 2)
        cascade_dir    = tmpl.get("cascade_dir", "NEUTRAL")
        regime_score   = 0

        # IV regime match
        if iv_regime == tmpl["best_iv"]:
            regime_score += 3
        elif iv_regime == "FLAT":
            regime_score += 1

        # BEAR cascade scoring — symmetric with BULL
        if cascade_dir == "BEAR":
            if cascade_bear >= 150:   regime_score += 3
            elif cascade_bear >= 100: regime_score += 2
            elif cascade_bear >= 50:  regime_score += 1
        elif cascade_dir == "BULL":
            if cascade_bull >= 150:   regime_score += 3
            elif cascade_bull >= 100: regime_score += 2
            elif cascade_bull >= 50:  regime_score += 1
        elif cascade_dir == "NEUTRAL":
            # Neutral strategies score higher when neither cascade dominates
            imbalance = abs(cascade_bear - cascade_bull)
            if imbalance < 50: regime_score += 2
            elif imbalance < 100: regime_score += 1

        # VANNA zone bonuses
        if vacuums and cascade_dir in ("BEAR","BULL"):
            regime_score += 1
        if floors and cascade_dir in ("NEUTRAL","BULL"):
            regime_score += 1
        if traps and cascade_dir == "BEAR":
            regime_score += 1

        # Star penalty: dangerous strategies get penalised
        if strat_stars == 1:  regime_score = max(0, regime_score - 3)
        if strat_stars == 2:  regime_score = max(0, regime_score - 1)

        # Historical WR from backtest
        hist_wr = _BT_WINNERS.get((iv_regime, "Afternoon"), ("",0,0))[1]
        if tmpl["name"] == _BT_WINNERS.get((iv_regime, "Afternoon"), ("",0,0))[0]:
            regime_score += 3

        # ── Overall score ─────────────────────────────────────────────────────
        # Weighted: 35% regime+cascade, 25% POP, 20% R:R, 10% hist WR, 10% stars
        overall_score = (
            regime_score / 11.0 * 35 +
            pop_pct / 100 * 25 +
            min(rr / 3.0, 1.0) * 20 +
            tmpl["best_wr"] / 100 * 10 +
            strat_stars / 5.0 * 10
        )

        results.append({
            "name":         tmpl["name"],
            "stars":        tmpl.get("stars", 2),
            "note":         tmpl.get("note", ""),
            "cascade_dir":  tmpl.get("cascade_dir", "NEUTRAL"),
            "legs":         leg_details,
            "net_premium":  net_premium,
            "total_cost":   total_cost,
            "is_debit":     is_debit,
            "breakevens":   breakevens,
            "max_profit":   max_profit,
            "max_loss":     max_loss,
            "pop_pct":      round(pop_pct, 1),
            "rr":           round(rr, 2),
            "regime_score": regime_score,
            "overall_score":round(overall_score, 1),
            "hist_wr":      tmpl["best_wr"],
            "best_iv":      tmpl["best_iv"],
        })

    return sorted(results, key=lambda x: x["overall_score"], reverse=True)


def render_live_strategy_screener(df_selected, spot_price, unit_label, symbol,
                                   meta, iv_regime, cascade_bear, cascade_bull, vanna_zones):
    """Live strategy screener — fetches real option prices and ranks strategies."""

    st.markdown("### &#x1F534; Live Strategy Screener")
    st.caption(
        "Real-time option premiums from fetched data. "
        "Strategies ranked by composite score: Regime Fit (40%) + POP (30%) + R:R (20%) + Historical WR (10%)."
    )

    if df_selected is None or len(df_selected) == 0:
        st.warning("&#x26A0;&#xFE0F; Please fetch data first (click 🚀 Fetch Data in sidebar) to run the live screener.")
        return

    cfg      = INDEX_CONFIG.get(symbol, {"contract_size":25,"strike_interval":50})
    lot_size = cfg.get("contract_size", 25)
    tte_days = 7 if meta.get("expiry_flag","WEEK")=="WEEK" else 30
    tte      = tte_days / 365

    # ── Controls ──────────────────────────────────────────────────────────────
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        min_pop = st.slider("Min POP %", 30, 80, 50, 5, key="screener_pop")
    with sc2:
        min_score = st.slider("Min Score", 0, 100, 40, 5, key="screener_score")
    with sc3:
        max_cost = st.number_input("Max Total Cost ₹", 1000, 200000, 50000, 1000,
                                    key="screener_cost")

    run_btn = st.button("&#x1F50D; Run Live Screener", type="primary",
                         use_container_width=True, key="run_screener_btn")

    if run_btn or st.session_state.get("screener_ran", False):
        st.session_state["screener_ran"] = True
        max_cas = max(cascade_bear, cascade_bull)
        with st.spinner("Scanning strategies against live prices..."):
            strikes_sorted = sorted(df_selected["strike"].unique().tolist())
            live_prices    = fetch_live_option_prices(symbol, df_selected, meta)
            all_results    = screen_all_strategies(
                spot_price, strikes_sorted, live_prices,
                iv_regime, cascade_bear, cascade_bull, vanna_zones,
                lot_size, tte, symbol
            )

        # ── Filter ────────────────────────────────────────────────────────────
        filtered = [r for r in all_results
                    if r["pop_pct"] >= min_pop
                    and r["overall_score"] >= min_score
                    and r["total_cost"] <= max_cost]

        if not filtered:
            st.info("No strategies match current filters. Try lowering POP or Score thresholds.")
            filtered = all_results[:5]  # show top 5 anyway

        # ── Current context banner ────────────────────────────────────────────
        iv_color = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")
        ctx = [
            '<div style="background:rgba(15,23,42,0.8);border:1px solid rgba(148,163,184,0.15);'
            'border-radius:10px;padding:12px 16px;margin-bottom:14px;display:flex;gap:12px;flex-wrap:wrap;">',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#94a3b8;">Market Context:</span>',
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:2px 10px;'
            'background:{0}20;border:1px solid {0}50;border-radius:12px;color:{0};">IV: {1}</span>'.format(iv_color, iv_regime),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:2px 10px;'
            'background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);border-radius:12px;color:#ef4444;">'
            'Bear Cascade: {:.0f}pts</span>'.format(cascade_bear),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:2px 10px;'
            'background:rgba(16,185,129,0.15);border:1px solid rgba(16,185,129,0.3);border-radius:12px;color:#10b981;">'
            'Bull Cascade: {:.0f}pts</span>'.format(cascade_bull),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:2px 10px;'
            'background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.3);border-radius:12px;color:#c4b5fd;">'
            'Spot: ₹{:,.0f}</span>'.format(spot_price),
            '</div>',
        ]
        st.markdown("".join(ctx), unsafe_allow_html=True)

        # ── Ranked strategy cards ─────────────────────────────────────────────
        # Count how many strikes have real API prices
        live_count = sum(1 for v in live_prices.values() if v.get("source")=="LIVE")
        bar_count  = sum(1 for v in live_prices.values() if v.get("source")=="BAR_CLOSE")
        bsm_count  = sum(1 for v in live_prices.values() if v.get("source")=="BSM")
        total_strikes = len(live_prices)
        if live_count > 0:
            source_note = "&#x1F7E2; LIVE LTP from option chain ({}/{} strikes)".format(live_count, total_strikes)
            src_color   = "#10b981"
        elif bar_count > 0:
            source_note = "&#x1F7E1; Bar close prices ({} strikes) — market may be closed, showing last bar LTP".format(bar_count)
            src_color   = "#f59e0b"
        else:
            source_note = "&#x1F534; BSM estimated ({} strikes) — option chain API unavailable, prices are theoretical".format(bsm_count)
            src_color   = "#ef4444"
        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;'
            'padding:5px 10px;background:{0}15;border:1px solid {0}40;border-radius:6px;'
            'color:{0};margin-bottom:8px;">{1}</div>'.format(src_color, source_note),
            unsafe_allow_html=True
        )
        st.markdown(f"**{len(filtered)} strategies matched** | Ranked by composite score")

        for rank, res in enumerate(filtered, 1):
            score      = res["overall_score"]
            pop        = res["pop_pct"]
            cost       = res["total_cost"]
            rr         = res["rr"]
            mp         = res["max_profit"]
            ml         = res["max_loss"]
            bes        = res["breakevens"]
            is_debit   = res["is_debit"]
            hist_wr    = res["hist_wr"]
            stars      = res.get("stars", 2)
            strat_note = res.get("note", "")
            cas_dir    = res.get("cascade_dir", "NEUTRAL")

            score_color = ("#10b981" if score >= 65 else
                           "#f59e0b" if score >= 45 else "#ef4444")
            pop_color   = ("#10b981" if pop >= 60 else
                           "#f59e0b" if pop >= 45 else "#ef4444")
            rank_icons  = ["1st","2nd","3rd","4th","5th","6th","7th","8th",
                           "9th","10th","11th","12th","13th","14th","15th"]
            rank_icon   = rank_icons[min(rank-1, 14)]
            type_label  = "DEBIT" if is_debit else "CREDIT"
            type_color  = "#ef4444" if is_debit else "#10b981"
            mp_str      = "Rs{:,.0f}".format(mp) if mp < 1e6 else "Unlimited"
            ml_str      = "Rs{:,.0f}".format(abs(ml)) if ml > -1e6 else "Unlimited"
            be_str      = " / ".join(["Rs{:,.0f}".format(b) for b in bes]) if bes else "N/A"
            star_str    = ("*" * stars) + ("-" * (5-stars))  # ASCII stars
            cas_color   = {"BEAR":"#ef4444","BULL":"#10b981","NEUTRAL":"#94a3b8"}.get(cas_dir,"#94a3b8")
            cas_label   = {"BEAR":"Bear Cascade","BULL":"Bull Cascade","NEUTRAL":"Neutral"}.get(cas_dir,"Neutral")

            exp_title = "{} #{} {}  [{}]  Score:{:.0f}  POP:{:.0f}%  Cost:Rs{:,.0f}".format(
                rank_icon, rank, res["name"], star_str, score, pop, cost)
            with st.expander(exp_title, expanded=(rank <= 3)):
                # Score bar + metrics row
                bar_parts = [
                    '<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.12);'
                    'border-radius:10px;padding:14px 16px;">',
                    # Stars + cascade direction
                    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">',
                    '<span style="font-family:JetBrains Mono,monospace;font-size:1.1rem;'
                    'color:#fbbf24;letter-spacing:2px;">{}</span>'.format(star_str.replace('*','&#x2B50;').replace('-','&#x2606;')),
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;'
                    'padding:2px 10px;background:{0}20;border:1px solid {0}50;'
                    'border-radius:12px;color:{0};">{1}</span>'.format(cas_color, cas_label),
                    '</div>',
                    # Score bar
                    '<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">',
                    '<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;'
                    'color:#94a3b8;min-width:80px;">Overall Score</span>',
                    '<div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:8px;">',
                    '<div style="background:{};width:{:.0f}%;height:8px;border-radius:4px;"></div>'.format(score_color, min(score,100)),
                    '</div>',
                    '<span style="font-family:Space Grotesk,sans-serif;font-size:0.90rem;'
                    'font-weight:800;color:{};">{:.0f}/100</span>'.format(score_color, score),
                    '</div>',
                    # Metrics grid
                    '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">',
                ]
                metrics = [
                    ("POP",         f"{pop:.1f}%",       pop_color),
                    ("Type",        type_label,           type_color),
                    ("Total Cost",  f"₹{cost:,.0f}",     "#e2e8f0"),
                    ("Max Profit",  mp_str,               "#10b981"),
                    ("Max Loss",    ml_str,               "#ef4444"),
                    ("R:R",         f"{rr:.2f}:1" if rr>0 else "N/A", "#06b6d4"),
                    ("Breakeven",   be_str,               "#f59e0b"),
                    ("Hist WR",     f"{hist_wr:.0f}%",   "#c4b5fd"),
                ]
                for lbl, val, col in metrics:
                    bar_parts += [
                        '<div style="flex:1;min-width:90px;padding:7px 10px;'
                        'background:rgba(255,255,255,0.03);border:1px solid rgba(148,163,184,0.10);'
                        'border-radius:6px;text-align:center;">',
                        '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#64748b;">{}</div>'.format(lbl),
                        '<div style="font-family:Space Grotesk,sans-serif;font-size:0.82rem;'
                        'font-weight:700;color:{};">{}</div>'.format(col, val),
                        '</div>',
                    ]
                bar_parts += ['</div>']

                # Legs table
                bar_parts += [
                    '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;'
                    'color:#94a3b8;margin-bottom:6px;">Leg Structure:</div>',
                    '<div style="display:flex;flex-direction:column;gap:3px;">',
                ]
                for i, leg in enumerate(res["legs"]):
                    act_col  = "#10b981" if leg["act"]=="BUY" else "#ef4444"
                    _leg_src = leg.get("source","BSM")
                    src_col  = ("#10b981" if _leg_src=="LIVE" else
                               "#06b6d4" if _leg_src=="BAR_CLOSE" else "#f59e0b")
                    src_lbl  = _leg_src

                    iv_disp  = leg["iv"] if leg["iv"] > 1 else leg["iv"]*100
                    bar_parts += [
                        '<div style="display:flex;gap:8px;align-items:center;'
                        'font-family:JetBrains Mono,monospace;font-size:0.70rem;margin-bottom:2px;">',
                        '<span style="color:{};font-weight:700;">{}</span>'.format(act_col, leg["act"]),
                        '<span style="color:#e2e8f0;">{} {}  Strike:{:,.0f}</span>'.format(
                            leg["opt"], symbol, leg["k"]),
                        '<span style="color:#f1f5f9;font-weight:600;"> @ Rs{:.2f}</span>'.format(leg["px"]),
                        '<span style="font-size:0.62rem;padding:1px 6px;background:{0}20;border:1px solid {0}40;border-radius:8px;color:{0};">{1}</span>'.format(src_col, src_lbl),
                        '<span style="color:#64748b;">IV:{:.1f}%</span>'.format(iv_disp),
                        '</div>',
                    ]

                # Regime fit note
                iv_match = iv_regime == res["best_iv"]
                regime_note_color = "#10b981" if iv_match else "#f59e0b"
                regime_note_icon  = "&#x2705;" if iv_match else "&#x26A0;&#xFE0F;"
                bar_parts += [
                    '<div style="margin-top:8px;padding:6px 10px;background:{}10;'
                    'border-left:3px solid {};border-radius:0 4px 4px 0;'
                    'font-family:JetBrains Mono,monospace;font-size:0.68rem;color:{};">'.format(
                        regime_note_color, regime_note_color, regime_note_color),
                    '{} Regime fit: {} (optimal: {}) | Hist WR in best setup: {:.0f}%'.format(
                        regime_note_icon,
                        "&#x2714; MATCHED" if iv_match else "&#x26A0; PARTIAL",
                        res["best_iv"], hist_wr),
                    '</div>',
                    '</div>',
                ]
                if strat_note:
                    bar_parts += ['<div style="margin-top:6px;padding:6px 10px;'
                        'background:rgba(124,58,237,0.08);border-left:3px solid #7c3aed;'
                        'border-radius:0 4px 4px 0;font-family:JetBrains Mono,monospace;'
                        'font-size:0.68rem;color:#c4b5fd;">Note: {}</div>'.format(strat_note)]
                bar_parts += ['</div>']
                st.markdown("".join(bar_parts), unsafe_allow_html=True)

                # Load into Builder
                if st.button(
                    "Load into Builder  ->",
                    key="load_screener_{}".format(rank),
                    use_container_width=True,
                    type="primary",
                    help="Loads this strategy into the Finder + Builder tab with GEX-selected strikes"
                ):
                    st.session_state["selected_strategy"] = res["name"]
                    st.session_state["auto_fill_triggered"] = True
                    st.session_state["screener_loaded_strategy"] = res["name"]
                    st.success("Loaded **{}** into Builder. Switch to the Finder + Builder tab.".format(res["name"]))

        # ── Summary comparison table ──────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### &#x1F4CA; Screener Summary")
        import pandas as _pd_sc
        summary_rows = []
        for r in all_results:
            summary_rows.append({
                "Strategy":   r["name"],
                "Score":      r["overall_score"],
                "POP %":      r["pop_pct"],
                "Cost ₹":     int(r["total_cost"]),
                "Max Profit": f"₹{r['max_profit']:,.0f}" if r["max_profit"]<1e6 else "Unlimited",
                "Max Loss":   f"₹{abs(r['max_loss']):,.0f}" if r["max_loss"]>-1e6 else "Unlimited",
                "R:R":        f"{r['rr']:.2f}" if r["rr"]>0 else "N/A",
                "Hist WR%":   r["hist_wr"],
                "Regime Fit": "✅" if iv_regime==r["best_iv"] else "⚠️",
            })
        sc_df = _pd_sc.DataFrame(summary_rows)

        def _score_color(val):
            if not isinstance(val,(int,float)): return ""
            if val >= 65: return "background-color:rgba(16,185,129,0.20);color:#6ee7b7;font-weight:700;"
            if val >= 45: return "background-color:rgba(245,158,11,0.12);color:#fcd34d;"
            return "background-color:rgba(239,68,68,0.10);color:#fca5a5;"

        def _pop_color(val):
            if not isinstance(val,(int,float)): return ""
            if val >= 60: return "color:#10b981;font-weight:700;"
            if val >= 45: return "color:#f59e0b;"
            return "color:#ef4444;"

        styled_sc = (sc_df.style
        .map(_score_color, subset=["Score"])
        .map(_pop_color,   subset=["POP %"]))
        st.dataframe(styled_sc, use_container_width=True, hide_index=True)

        st.markdown(
            '<div style="margin-top:8px;font-family:JetBrains Mono,monospace;font-size:0.62rem;'
            'color:#475569;">&#9888;&#65039; Premiums from last fetched data snapshot. '
            'Re-fetch for latest prices. POP uses BSM breakeven distance method. '
            'Not SEBI-registered investment advice.</div>',
            unsafe_allow_html=True,
        )

# ============================================================================
# PRICE LEVELS + VANNA STRATEGY PANEL
# Close price heatmap × VANNA support/resistance × best strategy
# ============================================================================

def build_price_level_analysis(df_selected, spot_price, vanna_zones, iv_regime,
                                 cascade_bear, cascade_bull, unit_label, symbol,
                                 lot_size, tte):
    """
    Build price level analysis:
    - Call/Put close prices per strike (heatmap style)
    - VANNA support/resistance classification
    - Best strategy recommendation based on levels
    Returns: (levels_df, fig, best_strategy_name, reasoning)
    """
    import pandas as pd
    import numpy as np
    import plotly.graph_objects as go

    if df_selected is None or len(df_selected) == 0:
        return None, None, None, None

    cfg      = INDEX_CONFIG.get(symbol, {"contract_size":25,"strike_interval":50})
    interval = cfg.get("strike_interval", 50)
    r        = 0.065

    # ── Per-strike close prices — use last available candle close ───────────────
    # Build a lookup: strike → {call_close, put_close, call_iv, put_iv}
    # Priority: last timestamp in df (actual candle close) → df_selected → BSM
    _last_bar_map = {}
    if df_selected is not None and len(df_selected) > 0:
        # Get the last available timestamp across all strikes
        _last_ts = df_selected["timestamp"].max() if "timestamp" in df_selected.columns else None
        for _, _br in df_selected.iterrows():
            _sk = float(_br["strike"])
            _cc = float(_br.get("call_close", 0) or 0)
            _pc = float(_br.get("put_close",  0) or 0)
            _ci = float(_br.get("call_iv", 18) or 18)
            _pi = float(_br.get("put_iv",  18) or 18)
            # Only update if this row has a valid close price
            if _sk not in _last_bar_map or (_cc > 0 or _pc > 0):
                _last_bar_map[_sk] = {"call_close": _cc, "put_close": _pc,
                                       "call_iv": _ci, "put_iv": _pi}

    rows = []
    for _, row in df_selected.iterrows():
        strike    = float(row["strike"])
        # Prefer the last bar lookup, fallback to current row
        _bar = _last_bar_map.get(strike, {})
        call_px   = float(_bar.get("call_close", 0) or row.get("call_close", 0) or 0)
        put_px    = float(_bar.get("put_close",  0) or row.get("put_close",  0) or 0)
        call_iv   = float(row.get("call_iv", 18) or 18)
        put_iv    = float(row.get("put_iv",  18) or 18)
        net_gex   = float(row.get("net_gex",  0) or 0)
        net_vanna = float(row.get("net_vanna",0) or 0)

        # BSM fallback if close price is zero
        if call_px <= 0 and tte > 0:
            iv_d = (call_iv/100) if call_iv > 1 else call_iv
            call_px = max(_bs_live(spot_price, strike, tte, r, max(iv_d,0.05), "CE"), 0)
        if put_px <= 0 and tte > 0:
            iv_d = (put_iv/100) if put_iv > 1 else put_iv
            put_px = max(_bs_live(spot_price, strike, tte, r, max(iv_d,0.05), "PE"), 0)

        moneyness = (strike - spot_price) / spot_price * 100
        dist_from_spot = strike - spot_price

        rows.append({
            "strike":        strike,
            "call_px":       call_px,
            "put_px":        put_px,
            "call_iv":       call_iv,
            "put_iv":        put_iv,
            "net_gex":       net_gex,
            "net_vanna":     net_vanna,
            "moneyness":     moneyness,
            "dist":          dist_from_spot,
        })

    if not rows:
        return None, None, None, None

    df_lvl = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)

    # ── VANNA zone classification per strike ──────────────────────────────────
    vanna_map = {}
    for z in vanna_zones:
        vanna_map[z["strike"]] = z["role"]

    def classify_strike(row):
        s = row["strike"]
        gex = row["net_gex"]
        # Match nearest VANNA zone
        role = vanna_map.get(s, None)
        if role is None:
            nearest_z = min(vanna_zones, key=lambda z: abs(z["strike"]-s), default=None)
            if nearest_z and abs(nearest_z["strike"]-s) <= interval:
                role = nearest_z["role"]

        if role == "SUPPORT_FLOOR":
            return "SUPPORT", "#06b6d4", "🛡️"
        elif role == "RESISTANCE_CEILING":
            return "RESISTANCE", "#ef4444", "🔴"
        elif role == "VACUUM_ZONE":
            return "VACUUM", "#a855f7", "🚀"
        elif role == "TRAP_DOOR":
            return "TRAP", "#f59e0b", "⚠️"
        elif gex > 0:
            if s > spot_price:
                return "RESISTANCE", "#ef4444", "🔴"
            else:
                return "SUPPORT", "#06b6d4", "🛡️"
        else:
            return "NEUTRAL", "#64748b", "⬜"

    df_lvl[["level_type","level_color","level_icon"]] = df_lvl.apply(
        lambda r: pd.Series(classify_strike(r)), axis=1)

    # ── Find highest green (support) and highest red (resistance) ─────────────
    resistances = df_lvl[df_lvl["level_type"]=="RESISTANCE"].sort_values("net_gex", ascending=False)
    supports    = df_lvl[df_lvl["level_type"]=="SUPPORT"].sort_values("net_gex", ascending=False)
    vacuums     = df_lvl[df_lvl["level_type"]=="VACUUM"]
    traps       = df_lvl[df_lvl["level_type"]=="TRAP"]

    top_resistance = resistances.iloc[0]["strike"] if len(resistances) > 0 else spot_price + interval*3
    top_support    = supports.iloc[0]["strike"]    if len(supports)    > 0 else spot_price - interval*3

    # Nearest resistance/support to spot
    resist_above = resistances[resistances["strike"] > spot_price]
    support_below = supports[supports["strike"] < spot_price]
    nearest_resist = resist_above.iloc[0]["strike"] if len(resist_above) > 0 else top_resistance
    nearest_support = support_below.iloc[0]["strike"] if len(support_below) > 0 else top_support

    price_range = nearest_resist - nearest_support
    spot_position_pct = (spot_price - nearest_support) / max(price_range, 1) * 100

    # ── Build Plotly figure: horizontal bar chart ─────────────────────────────
    fig = go.Figure()

    # Call close price bars (right side — above spot = resistance potential)
    call_colors = []
    for _, r2 in df_lvl.iterrows():
        if r2["level_type"] == "RESISTANCE":
            call_colors.append("rgba(239,68,68,0.75)")
        elif r2["level_type"] == "VACUUM":
            call_colors.append("rgba(168,85,247,0.75)")
        else:
            call_colors.append("rgba(99,102,241,0.55)")

    fig.add_trace(go.Bar(
        name="Call Close (CE)",
        y=df_lvl["strike"].astype(str),
        x=df_lvl["call_px"],
        orientation="h",
        marker_color=call_colors,
        opacity=0.85,
        text=[f"₹{v:.1f}" for v in df_lvl["call_px"]],
        textposition="outside",
        textfont=dict(size=9, color="rgba(255,255,255,0.7)"),
        hovertemplate="Strike: %{y}<br>Call Close: ₹%{x:.2f}<extra></extra>",
    ))

    # Put close price bars (left side — inverted — below spot = support potential)
    put_colors = []
    for _, r2 in df_lvl.iterrows():
        if r2["level_type"] == "SUPPORT":
            put_colors.append("rgba(16,185,129,0.75)")
        elif r2["level_type"] == "TRAP":
            put_colors.append("rgba(245,158,11,0.75)")
        else:
            put_colors.append("rgba(6,182,212,0.55)")

    fig.add_trace(go.Bar(
        name="Put Close (PE)",
        y=df_lvl["strike"].astype(str),
        x=[-v for v in df_lvl["put_px"]],
        orientation="h",
        marker_color=put_colors,
        opacity=0.85,
        text=[f"₹{v:.1f}" for v in df_lvl["put_px"]],
        textposition="outside",
        textfont=dict(size=9, color="rgba(255,255,255,0.7)"),
        hovertemplate="Strike: %{y}<br>Put Close: ₹%{customdata:.2f}<extra></extra>",
        customdata=df_lvl["put_px"],
    ))

    # Net GEX line overlay (secondary axis hint via scatter size)
    gex_abs   = df_lvl["net_gex"].abs()
    gex_max   = gex_abs.max() if gex_abs.max() > 0 else 1
    gex_sizes = (gex_abs / gex_max * 20 + 5).clip(5, 25)
    gex_cols  = ["#10b981" if v >= 0 else "#ef4444" for v in df_lvl["net_gex"]]

    fig.add_trace(go.Scatter(
        name="Net GEX",
        y=df_lvl["strike"].astype(str),
        x=[0] * len(df_lvl),
        mode="markers",
        marker=dict(size=gex_sizes, color=gex_cols, opacity=0.9,
                    line=dict(width=1, color="rgba(255,255,255,0.3)")),
        hovertemplate="Strike: %{y}<br>Net GEX: %{customdata:.3f}B<extra></extra>",
        customdata=df_lvl["net_gex"],
    ))

    # VANNA zone annotations
    shapes, annotations = [], []
    for _, r2 in df_lvl.iterrows():
        if r2["level_type"] in ("RESISTANCE","SUPPORT","VACUUM","TRAP"):
            lc = r2["level_color"]
            shapes.append(dict(
                type="line", xref="paper", x0=0, x1=1,
                yref="y", y0=str(r2["strike"]), y1=str(r2["strike"]),
                line=dict(color=lc, width=1.5, dash="dot"),
                opacity=0.6,
            ))

    # Spot price label
    atm_strike = df_lvl.iloc[(df_lvl["strike"]-spot_price).abs().argsort().iloc[0]]["strike"]
    annotations.append(dict(
        x=0, y=str(int(atm_strike)),
        xref="paper", yref="y",
        text=f"  ← SPOT ₹{spot_price:,.0f}",
        showarrow=False,
        font=dict(size=10, color="#fbbf24"),
        xanchor="left",
    ))

    fig.update_layout(
        barmode="overlay",
        template="plotly_dark",
        paper_bgcolor="rgba(10,10,26,0)",
        plot_bgcolor="rgba(10,10,26,0)",
        height=max(350, len(df_lvl) * 28),
        margin=dict(l=60, r=80, t=40, b=30),
        title=dict(
            text=f"<b>Strike Price Levels — Call/Put Close × VANNA Zones</b>  |  Spot: ₹{spot_price:,.0f}",
            font=dict(size=13, color="#e2e8f0"),
            x=0,
        ),
        xaxis=dict(
            title="← Put Premium (PE) &nbsp;&nbsp;&nbsp; Call Premium (CE) →",
            gridcolor="rgba(255,255,255,0.06)",
            zerolinecolor="rgba(255,255,255,0.25)",
            zerolinewidth=2,
            tickfont=dict(size=9),
        ),
        yaxis=dict(
            title="Strike",
            gridcolor="rgba(255,255,255,0.04)",
            tickfont=dict(size=9),
            autorange="reversed",
        ),
        legend=dict(
            orientation="h", y=1.02, x=0,
            font=dict(size=10, color="#94a3b8"),
            bgcolor="rgba(0,0,0,0)",
        ),
        shapes=shapes,
        annotations=annotations,
    )

    # ── Best strategy logic based on price levels ─────────────────────────────
    strategies = []

    def near(s1, s2): return abs(s1-s2) <= interval*1.5

    # 1. Spot near support → Bull bias strategies
    if near(spot_price, nearest_support) and spot_price >= nearest_support:
        if iv_regime == "COMPRESSING":
            strategies.append(("Bull Call Spread", 95,
                "CREDIT",
                f"Spot (₹{spot_price:,.0f}) sitting ON support ₹{nearest_support:,.0f} "
                f"with IV COMPRESSING. VANNA floor active — dealers buying delta. "
                f"Buy ATM CE, Sell resistance strike CE. "
                f"Target: ₹{nearest_resist:,.0f} | Floor: ₹{nearest_support:,.0f}",
                ["BUY ATM CE", f"SELL ₹{int(nearest_resist):,} CE"],
                "DEBIT"))
        elif iv_regime == "EXPANDING":
            strategies.append(("Bull Put Spread", 85,
                "CREDIT",
                f"Spot near VANNA support ₹{nearest_support:,.0f} with IV EXPANDING. "
                f"Sell OTM put at support — collect credit while floor absorbs selling. "
                f"Risk: floor breaks → accelerated fall.",
                [f"SELL ₹{int(nearest_support):,} PE", f"BUY ₹{int(nearest_support - interval*2):,} PE"],
                "CREDIT"))
        else:
            strategies.append(("Bull Call Spread", 78,
                "DEBIT",
                f"Spot holding VANNA support ₹{nearest_support:,.0f}, FLAT IV. "
                f"Debit spread limits premium decay risk.",
                ["BUY ATM CE", f"SELL ₹{int(nearest_resist):,} CE"],
                "DEBIT"))

    # 2. Spot near resistance → Bear bias strategies
    if near(spot_price, nearest_resist) and spot_price <= nearest_resist:
        if iv_regime == "EXPANDING":
            strategies.append(("Bear Call Spread", 92,
                "CREDIT",
                f"Spot (₹{spot_price:,.0f}) testing RESISTANCE ₹{nearest_resist:,.0f} "
                f"with IV EXPANDING (83.8% BEAR accuracy in midday). "
                f"Sell resistance CE — collect credit as GEX wall pushes back. "
                f"Floor: ₹{nearest_support:,.0f}",
                [f"SELL ₹{int(nearest_resist):,} CE", f"BUY ₹{int(nearest_resist + interval*2):,} CE"],
                "CREDIT"))
        elif iv_regime == "COMPRESSING":
            strategies.append(("Bear Put Spread", 80,
                "DEBIT",
                f"Spot at resistance ₹{nearest_resist:,.0f}, IV COMPRESSING. "
                f"Debit put spread — limited risk as IV may continue falling. "
                f"Target: ₹{nearest_support:,.0f}",
                ["BUY ATM PE", f"SELL ₹{int(nearest_support):,} PE"],
                "DEBIT"))
        else:
            strategies.append(("Iron Condor", 75,
                "CREDIT",
                f"Spot between support ₹{nearest_support:,.0f} and resistance ₹{nearest_resist:,.0f}. "
                f"Range-bound — sell both walls via Iron Condor. "
                f"Collect credit from FLAT IV premium.",
                [f"SELL ₹{int(nearest_resist):,} CE", f"BUY ₹{int(nearest_resist+interval*2):,} CE",
                 f"SELL ₹{int(nearest_support):,} PE", f"BUY ₹{int(nearest_support-interval*2):,} PE"],
                "CREDIT"))

    # 3. Spot in mid-range with clear walls → Iron Condor / range plays
    if not near(spot_price, nearest_resist) and not near(spot_price, nearest_support):
        if price_range > interval*4:
            strategies.append(("Iron Condor", 82,
                "CREDIT",
                f"Spot (₹{spot_price:,.0f}) mid-range: support ₹{nearest_support:,.0f} "
                f"↔ resistance ₹{nearest_resist:,.0f} ({price_range:.0f}pt range). "
                f"Range is wide enough for Iron Condor margin. "
                f"GEX walls at both strikes act as natural boundaries.",
                [f"SELL ₹{int(nearest_resist):,} CE", f"BUY ₹{int(nearest_resist+interval*2):,} CE",
                 f"SELL ₹{int(nearest_support):,} PE", f"BUY ₹{int(nearest_support-interval*2):,} PE"],
                "CREDIT"))
        if iv_regime == "EXPANDING" and cascade_bear >= 100:
            strategies.append(("Bear Call Spread", 88,
                "CREDIT",
                f"IV EXPANDING + Bear cascade {cascade_bear:.0f}pts active. "
                f"Sell nearest resistance CE. VANNA unwind favors downside — "
                f"75% historical accuracy (EXPANDING+BEAR midday).",
                [f"SELL ₹{int(nearest_resist):,} CE", f"BUY ₹{int(nearest_resist+interval*2):,} CE"],
                "CREDIT"))
        if iv_regime == "COMPRESSING" and cascade_bull >= 100:
            strategies.append(("Bull Call Spread", 85,
                "DEBIT",
                f"IV COMPRESSING + Bull cascade {cascade_bull:.0f}pts. "
                f"VANNA floor at ₹{nearest_support:,.0f} holds. "
                f"Debit call spread toward resistance.",
                ["BUY ATM CE", f"SELL ₹{int(nearest_resist):,} CE"],
                "DEBIT"))

    # 4. Vacuum zone above → explosive bull play
    if len(vacuums) > 0:
        vac_above = vacuums[vacuums["strike"] > spot_price]
        if len(vac_above) > 0:
            vac_strike = vac_above.iloc[0]["strike"]
            strategies.append(("Long Call", 80,
                "DEBIT",
                f"VACUUM ZONE at ₹{vac_strike:,.0f} above spot — "
                f"if resistance ₹{nearest_resist:,.0f} breaks, VANNA unwind "
                f"creates rapid move toward ₹{vac_strike:,.0f}. "
                f"Long ATM call for breakout play.",
                ["BUY ATM CE (breakout play)"],
                "DEBIT"))

    # 5. Trap door below → bearish acceleration play
    if len(traps) > 0:
        trap_below = traps[traps["strike"] < spot_price]
        if len(trap_below) > 0:
            trap_strike = trap_below.iloc[0]["strike"]
            strategies.append(("Long Put", 82,
                "DEBIT",
                f"TRAP DOOR at ₹{trap_strike:,.0f} — if support ₹{nearest_support:,.0f} fails, "
                f"VANNA acceleration toward ₹{trap_strike:,.0f}. "
                f"Long ATM put for breakdown play.",
                ["BUY ATM PE (breakdown play)"],
                "DEBIT"))

    # Sort by confidence score
    strategies.sort(key=lambda x: x[1], reverse=True)
    best = strategies[0] if strategies else None

    return df_lvl, fig, best, {
        "nearest_resist": nearest_resist,
        "nearest_support": nearest_support,
        "top_resistance": top_resistance,
        "top_support": top_support,
        "price_range": price_range,
        "spot_position_pct": spot_position_pct,
        "all_strategies": strategies,
    }


def render_price_levels_strategy_tab(df_selected, spot_price, vanna_zones,
                                      iv_regime, cascade_bear, cascade_bull,
                                      unit_label, symbol, meta):
    """
    Renders the Price Levels + Strategy sub-tab inside Strategy Hub.
    """
    st.markdown("### &#x1F4CA; Strike Price Levels + VANNA Strategy Finder")
    st.caption(
        "5-min close prices per strike × VANNA support/resistance levels. "
        "Highest RED = strongest resistance. Highest GREEN = strongest support. "
        "Best strategy auto-selected based on where spot sits relative to GEX walls."
    )

    if df_selected is None or len(df_selected) == 0:
        st.warning("&#x26A0;&#xFE0F; Please fetch data first.")
        return

    cfg      = INDEX_CONFIG.get(symbol, {"contract_size":25,"strike_interval":50})
    lot_size = cfg.get("contract_size", 25)
    tte_days = 7 if meta.get("expiry_flag","WEEK")=="WEEK" else 30
    tte      = tte_days / 365

    with st.spinner("Building price level analysis..."):
        df_lvl, fig, best_strat, level_info = build_price_level_analysis(
            df_selected, spot_price, vanna_zones, iv_regime,
            cascade_bear, cascade_bull, unit_label, symbol, lot_size, tte)

    if df_lvl is None:
        st.error("Unable to build price levels — check data.")
        return

    nr = level_info["nearest_resist"]
    ns = level_info["nearest_support"]
    pr = level_info["price_range"]
    sp_pct = level_info["spot_position_pct"]
    all_strats = level_info["all_strategies"]

    iv_color  = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")

    # ── Level summary bar ─────────────────────────────────────────────────────
    lev_parts = [
        '<div style="background:rgba(15,23,42,0.85);border:1px solid rgba(148,163,184,0.15);'
        'border-radius:12px;padding:14px 18px;margin-bottom:14px;">',
        '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">',

        # Resistance
        '<div style="flex:1;min-width:130px;padding:10px 14px;background:rgba(239,68,68,0.12);'
        'border:1.5px solid rgba(239,68,68,0.5);border-radius:8px;text-align:center;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:3px;">&#x1F534; NEAREST RESISTANCE</div>',
        f'<div style="font-size:1.3rem;font-weight:800;color:#ef4444;font-family:Space Grotesk,sans-serif;">&#x20B9;{nr:,.0f}</div>',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#94a3b8;">{nr-spot_price:+.0f} pts from spot</div>',
        '</div>',

        # Spot position bar
        '<div style="flex:2;min-width:200px;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#94a3b8;text-align:center;margin-bottom:6px;">',
        f'Spot &#x20B9;{spot_price:,.0f} &nbsp;|&nbsp; Range: {pr:.0f} pts &nbsp;|&nbsp; Position: {sp_pct:.0f}% from support',
        '</div>',
        '<div style="background:rgba(255,255,255,0.06);border-radius:6px;height:14px;position:relative;">',
        '<div style="background:linear-gradient(90deg,#06b6d4,#10b981,#f59e0b,#ef4444);'
        'width:100%;height:14px;border-radius:6px;opacity:0.3;"></div>',
        f'<div style="position:absolute;top:-2px;left:{min(max(sp_pct,2),98):.0f}%;transform:translateX(-50%);">',
        '<div style="width:4px;height:18px;background:#fbbf24;border-radius:2px;"></div>',
        '</div></div>',
        '<div style="display:flex;justify-content:space-between;font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#64748b;margin-top:3px;">',
        f'<span>&#x1F6E1;&#xFE0F; {ns:,.0f}</span><span>SPOT</span><span>&#x1F534; {nr:,.0f}</span>',
        '</div></div>',

        # Support
        '<div style="flex:1;min-width:130px;padding:10px 14px;background:rgba(16,185,129,0.12);'
        'border:1.5px solid rgba(16,185,129,0.5);border-radius:8px;text-align:center;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:3px;">&#x1F6E1;&#xFE0F; NEAREST SUPPORT</div>',
        f'<div style="font-size:1.3rem;font-weight:800;color:#10b981;font-family:Space Grotesk,sans-serif;">&#x20B9;{ns:,.0f}</div>',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#94a3b8;">{ns-spot_price:+.0f} pts from spot</div>',
        '</div>',

        '</div></div>',
    ]
    st.markdown("".join(lev_parts), unsafe_allow_html=True)

    # ── Plotly chart ──────────────────────────────────────────────────────────
    st.plotly_chart(fig, use_container_width=True)

    # ── VANNA level legend ────────────────────────────────────────────────────
    legend_items = [
        ("rgba(239,68,68,0.75)",  "Call bar = RESISTANCE — GEX absorption above spot"),
        ("rgba(16,185,129,0.75)", "Put bar = SUPPORT — GEX floor below spot"),
        ("rgba(168,85,247,0.75)", "Purple = VACUUM ZONE — explosive move if level breaks"),
        ("rgba(245,158,11,0.75)", "Amber = TRAP DOOR — acceleration on breakdown"),
        ("rgba(99,102,241,0.55)", "Indigo = Neutral call level"),
        ("rgba(6,182,212,0.55)",  "Cyan = Neutral put level"),
    ]
    leg_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;">'
    for col, label in legend_items:
        leg_html += (
            f'<div style="display:flex;align-items:center;gap:5px;">'
            f'<div style="width:12px;height:12px;border-radius:3px;background:{col};flex-shrink:0;"></div>'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#94a3b8;">{label}</span>'
            f'</div>'
        )
    leg_html += '</div>'
    st.markdown(leg_html, unsafe_allow_html=True)

    # ── Strike level table ────────────────────────────────────────────────────
    with st.expander("&#x1F4CB; Full Strike Level Table", expanded=False):
        tbl = df_lvl[["strike","call_px","put_px","call_iv","put_iv","net_gex","net_vanna","level_type","level_icon"]].copy()
        tbl.columns = ["Strike","Call Close","Put Close","Call IV%","Put IV%","Net GEX","Net VANNA","Level Type","Icon"]
        tbl["Call Close"] = tbl["Call Close"].round(2)
        tbl["Put Close"]  = tbl["Put Close"].round(2)
        tbl["Call IV%"]   = tbl["Call IV%"].round(1)
        tbl["Put IV%"]    = tbl["Put IV%"].round(1)
        tbl["Net GEX"]    = tbl["Net GEX"].round(4)
        tbl["Net VANNA"]  = tbl["Net VANNA"].round(4)

        def _lvl_style(row):
            t = row["Level Type"]
            if t == "RESISTANCE": return ["background-color:rgba(239,68,68,0.15)"]*len(row)
            if t == "SUPPORT":    return ["background-color:rgba(16,185,129,0.15)"]*len(row)
            if t == "VACUUM":     return ["background-color:rgba(168,85,247,0.15)"]*len(row)
            if t == "TRAP":       return ["background-color:rgba(245,158,11,0.15)"]*len(row)
            return [""]*len(row)

        st.dataframe(tbl.style.apply(_lvl_style, axis=1),
                     use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### &#x1F4CB; All Strategies — P&L + Probability Table")
    # Determine price source label
    _has_real_close = (
        "call_close" in df_selected.columns and
        df_selected["call_close"].fillna(0).abs().sum() > 0
    )
    _price_src = "5-min candle close prices from Dhan API" if _has_real_close else "BSM theoretical prices (no candle data)"
    _src_color = "#10b981" if _has_real_close else "#f59e0b"
    st.caption(
        f"Computed from {_price_src}. "
        "Max Profit / Max Loss = per lot (excluding brokerage). "
        "POP = Probability of Profit via Black-Scholes. "
        "Breakeven = spot price at expiry where P&L = 0."
    )
    st.markdown(
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;padding:4px 10px;'
        f'background:{_src_color}15;border:1px solid {_src_color}40;border-radius:5px;'
        f'color:{_src_color};margin-bottom:8px;">&#x1F4CA; Price Source: {_price_src}</div>',
        unsafe_allow_html=True,
    )

    if not all_strats:
        st.info("No strategies generated. Check VANNA zones or widen strike range.")
        return

    # ── Compute full P&L for every strategy using df_lvl prices ─────────────
    import numpy as _np

    def _px_from_lvl(df_l, strike, opt):
        """Get option close price from df_lvl (which already has last-bar close prices)."""
        row = df_l[df_l["strike"] == strike]
        if len(row) == 0:
            return _bs_live(spot_price, strike, tte, 0.065, 0.18, opt)
        # df_lvl stores call_px/put_px which are already fetched from call_close/put_close
        px = float(row.iloc[0]["call_px" if opt=="CE" else "put_px"])
        if px <= 0:
            iv_col = "call_iv" if opt=="CE" else "put_iv"
            iv_v   = float(row.iloc[0][iv_col]) if iv_col in row.columns else 18.0
            iv_d   = (iv_v/100) if iv_v > 1 else iv_v
            px = _bs_live(spot_price, strike, tte, 0.065, max(iv_d, 0.05), opt)
        return max(px, 0.01)

    # Full strategy definitions — all computed vs actual strikes
    atm_s    = min(df_lvl["strike"].tolist(), key=lambda x: abs(x-spot_price))
    strikes  = sorted(df_lvl["strike"].tolist())
    interval_s = strikes[1]-strikes[0] if len(strikes)>1 else 50

    def nearest_s(target):
        return min(strikes, key=lambda x: abs(x-target))

    resist_strikes = df_lvl[df_lvl["level_type"]=="RESISTANCE"]["strike"].tolist()
    support_strikes = df_lvl[df_lvl["level_type"]=="SUPPORT"]["strike"].tolist()
    resist_above = [s for s in resist_strikes if s > spot_price]
    support_below = [s for s in support_strikes if s < spot_price]

    r_wall = nearest_s(resist_above[0]) if resist_above else nearest_s(atm_s + interval_s*3)
    s_wall = nearest_s(support_below[0]) if support_below else nearest_s(atm_s - interval_s*3)

    ALL_STRATEGIES = [
        # name, legs: [(strike, opt, action, qty)]
        ("Bull Call Spread",    [(atm_s, "CE","BUY",1), (r_wall,"CE","SELL",1)], "DEBIT",  "BULL"),
        ("Bear Put Spread",     [(atm_s, "PE","BUY",1), (s_wall,"PE","SELL",1)], "DEBIT",  "BEAR"),
        ("Bear Call Spread",    [(r_wall,"CE","SELL",1),(nearest_s(r_wall+interval_s*2),"CE","BUY",1)], "CREDIT","BEAR"),
        ("Bull Put Spread",     [(s_wall,"PE","SELL",1),(nearest_s(s_wall-interval_s*2),"PE","BUY",1)], "CREDIT","BULL"),
        ("Iron Condor",         [(r_wall,"CE","SELL",1),(nearest_s(r_wall+interval_s*2),"CE","BUY",1),
                                 (s_wall,"PE","SELL",1),(nearest_s(s_wall-interval_s*2),"PE","BUY",1)], "CREDIT","NEUTRAL"),
        ("Iron Butterfly",      [(atm_s,"CE","SELL",1),(nearest_s(atm_s+interval_s*3),"CE","BUY",1),
                                 (atm_s,"PE","SELL",1),(nearest_s(atm_s-interval_s*3),"PE","BUY",1)], "CREDIT","NEUTRAL"),
        ("Long Straddle",       [(atm_s,"CE","BUY",1),(atm_s,"PE","BUY",1)], "DEBIT","NEUTRAL"),
        ("Short Strangle",      [(r_wall,"CE","SELL",1),(s_wall,"PE","SELL",1)], "CREDIT","NEUTRAL"),
        ("Long Call",           [(atm_s,"CE","BUY",1)], "DEBIT","BULL"),
        ("Long Put",            [(atm_s,"PE","BUY",1)], "DEBIT","BEAR"),
        ("Jade Lizard",         [(s_wall,"PE","SELL",1),(r_wall,"CE","SELL",1),
                                 (nearest_s(r_wall+interval_s*2),"CE","BUY",1)], "CREDIT","BULL"),
        ("Synthetic Long",      [(atm_s,"CE","BUY",1),(atm_s,"PE","SELL",1)], "DEBIT","BULL"),
        ("Ratio Put Spread",    [(atm_s,"PE","BUY",1),(nearest_s(atm_s-interval_s*2),"PE","SELL",2)], "CREDIT","BEAR"),
        ("Ratio Call Spread",   [(atm_s,"CE","BUY",1),(nearest_s(atm_s+interval_s*2),"CE","SELL",2)], "CREDIT","BULL"),
    ]

    rows = []
    for strat_name, legs, credit_debit, direction in ALL_STRATEGIES:
        net_prem = 0.0
        leg_detail = []
        all_iv_vals = []
        for (k, opt, act, qty) in legs:
            px   = _px_from_lvl(df_lvl, k, opt)
            iv_r = df_lvl[df_lvl["strike"]==k].iloc[0]["call_iv" if opt=="CE" else "put_iv"] if len(df_lvl[df_lvl["strike"]==k])>0 else 18.0
            all_iv_vals.append(float(iv_r))
            sign = 1 if act=="BUY" else -1
            net_prem += sign * px * qty
            leg_detail.append((k, opt, act, qty, px))

        avg_iv_d = sum(v/100 if v>1 else v for v in all_iv_vals) / max(len(all_iv_vals),1)

        # Payoff grid ±15% of spot
        spot_range = list(range(int(spot_price*0.88), int(spot_price*1.12), max(int(interval_s/2),1)))
        payoff = []
        for s in spot_range:
            pnl = 0.0
            for (k, opt, act, qty, px) in leg_detail:
                intr = max(s-k,0) if opt=="CE" else max(k-s,0)
                lp   = (intr-px) if act=="BUY" else (px-intr)
                pnl += lp * qty * lot_size
            payoff.append((s, pnl))

        max_profit = max(p[1] for p in payoff)
        max_loss   = min(p[1] for p in payoff)

        # Breakevens
        bes = []
        for i in range(len(payoff)-1):
            if payoff[i][1]*payoff[i+1][1] < 0:
                be = payoff[i][0] - payoff[i][1]*(payoff[i+1][0]-payoff[i][0])/(payoff[i+1][1]-payoff[i][1])
                bes.append(round(be, 0))

        # POP
        if bes and avg_iv_d > 0 and tte > 0:
            pop_vals = [_bs_pop(spot_price, be, tte, avg_iv_d) for be in bes]
            pop = sum(pop_vals)/len(pop_vals)
            if credit_debit == "CREDIT":
                pop = 100 - pop
        else:
            pop = 50.0

        # R:R
        rr = abs(max_profit/max_loss) if max_loss < -0.01 and max_profit < 1e7 else 0.0

        # Match confidence from scenario-based strategies
        conf_match = next((s[1] for s in all_strats if s[0]==strat_name), None)
        conf_score = conf_match if conf_match else None

        # IV regime fit
        iv_fit_map = {
            "Bull Call Spread": "COMPRESSING", "Bear Put Spread": "COMPRESSING",
            "Bear Call Spread": "EXPANDING",   "Bull Put Spread":  "COMPRESSING",
            "Iron Condor":      "FLAT",         "Iron Butterfly":   "FLAT",
            "Long Straddle":    "EXPANDING",    "Short Strangle":   "COMPRESSING",
            "Long Call":        "COMPRESSING",  "Long Put":         "EXPANDING",
            "Jade Lizard":      "COMPRESSING",  "Synthetic Long":   "FLAT",
            "Ratio Put Spread": "FLAT",         "Ratio Call Spread":"FLAT",
        }
        best_iv = iv_fit_map.get(strat_name, "FLAT")
        iv_match = (best_iv == iv_regime)

        net_prem_lot = net_prem * lot_size

        # Build legs string: "BUY 22200 CE @ ₹45 / SELL 22350 CE @ ₹12"
        legs_str = " / ".join(
            "{} {:,.0f} {} @ ₹{:.1f}{}".format(
                ld[2], ld[0], ld[1], ld[4],
                " ×{}".format(ld[3]) if ld[3] > 1 else ""
            )
            for ld in leg_detail
        )

        rows.append({
            "Strategy":       strat_name,
            "Legs":           legs_str,
            "Type":           credit_debit,
            "Dir":            direction,
            "Max Profit/Lot": round(max_profit, 0) if max_profit < 1e7 else float("inf"),
            "Max Loss/Lot":   round(abs(max_loss), 0) if abs(max_loss) < 1e7 else float("inf"),
            "Breakeven(s)":   " / ".join([f"₹{int(b):,}" for b in bes[:2]]) if bes else "N/A",
            "POP %":          round(pop, 1),
            "R:R":            round(rr, 2),
            "IV Match":       "✅" if iv_match else "❌",
            "Confidence":     conf_score,
            "_max_profit":    max_profit,
            "_max_loss":      max_loss,
            "_is_recommended": conf_score is not None,
        })

    import pandas as _pd2
    df_strats = _pd2.DataFrame(rows)

    # ── Recommended badge on top ──────────────────────────────────────────────
    recommended = [r for r in rows if r["_is_recommended"]]
    if recommended:
        top = max(recommended, key=lambda x: x["Confidence"])
        tc  = "#10b981" if top["Confidence"] >= 85 else "#f59e0b"
        type_c = "#ef4444" if top["Type"]=="DEBIT" else "#10b981"
        dir_c  = {"BULL":"#10b981","BEAR":"#ef4444","NEUTRAL":"#94a3b8"}.get(top["Dir"],"#94a3b8")
        mp_s   = "₹{:,.0f}".format(top["Max Profit/Lot"]) if top["Max Profit/Lot"] < 1e7 else "Unlimited"
        ml_s   = "₹{:,.0f}".format(top["Max Loss/Lot"])   if top["Max Loss/Lot"]   < 1e7 else "Unlimited"

        rec_parts = [
            '<div style="background:{}18;border:2px solid {}66;border-radius:14px;padding:16px 20px;margin-bottom:16px;">'.format(tc, tc),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:{}; text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;">&#x1F947; Best Strategy for Current Levels + IV Regime</div>'.format(tc),
            '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:10px;">',
            '<span style="font-family:Space Grotesk,sans-serif;font-size:1.4rem;font-weight:800;color:#e2e8f0;">{}</span>'.format(top["Strategy"]),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:3px 12px;background:{}25;border:1px solid {}55;border-radius:12px;color:{};">{}</span>'.format(type_c,type_c,type_c,top["Type"]),
            '<span style="font-family:JetBrains Mono,monospace;font-size:0.72rem;padding:3px 12px;background:{}25;border:1px solid {}55;border-radius:12px;color:{};">{}</span>'.format(dir_c,dir_c,dir_c,top["Dir"]),
            '<span style="font-family:Space Grotesk,sans-serif;font-size:1.1rem;font-weight:800;color:{};">{}% confidence</span>'.format(tc, top["Confidence"]),
            '</div>',
            '<div style="display:flex;gap:12px;flex-wrap:wrap;">',
            '<div style="padding:8px 16px;background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Max Profit/Lot</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:1.0rem;font-weight:700;color:#10b981;">{}</div>'.format(mp_s),
            '</div>',
            '<div style="padding:8px 16px;background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Max Loss/Lot</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:1.0rem;font-weight:700;color:#ef4444;">{}</div>'.format(ml_s),
            '</div>',
            '<div style="padding:8px 16px;background:rgba(6,182,212,0.12);border:1px solid rgba(6,182,212,0.3);border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">POP</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:1.0rem;font-weight:700;color:#06b6d4;">{}%</div>'.format(top["POP %"]),
            '</div>',
            '<div style="padding:8px 16px;background:rgba(124,58,237,0.12);border:1px solid rgba(124,58,237,0.3);border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Breakeven</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.85rem;font-weight:700;color:#c4b5fd;">{}</div>'.format(top["Breakeven(s)"]),
            '</div>',
            '<div style="padding:8px 16px;background:rgba(251,191,36,0.10);border:1px solid rgba(251,191,36,0.3);border-radius:8px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">R:R</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:1.0rem;font-weight:700;color:#fbbf24;">{}:1</div>'.format(top["R:R"]),
            '</div>',
            '</div></div>',
        ]
        st.markdown("".join(rec_parts), unsafe_allow_html=True)

    # ── Full strategy table ───────────────────────────────────────────────────
    disp = df_strats[[
        "Strategy","Legs","Type","Dir",
        "Max Profit/Lot","Max Loss/Lot","Breakeven(s)","POP %","R:R","IV Match"
    ]].copy()

    disp["Max Profit/Lot"] = disp["Max Profit/Lot"].apply(lambda x: "₹{:,.0f}".format(x) if x < 1e7 else "Unlimited")
    disp["Max Loss/Lot"]   = disp["Max Loss/Lot"].apply(lambda x: "₹{:,.0f}".format(x) if x < 1e7 else "Unlimited")
    disp["POP %"]          = disp["POP %"].apply(lambda x: "{:.1f}%".format(x))
    disp["R:R"]            = disp["R:R"].apply(lambda x: "{:.2f}:1".format(x) if x > 0 else "N/A")

    def _strat_row_style(row):
        t = row["Type"]
        d = row["Dir"]
        if t == "CREDIT" and d == "BEAR": return ["background-color:rgba(239,68,68,0.10)"]*len(row)
        if t == "CREDIT" and d == "BULL": return ["background-color:rgba(16,185,129,0.10)"]*len(row)
        if t == "CREDIT":                 return ["background-color:rgba(6,182,212,0.08)"]*len(row)
        if t == "DEBIT"  and d == "BULL": return ["background-color:rgba(16,185,129,0.06)"]*len(row)
        if t == "DEBIT"  and d == "BEAR": return ["background-color:rgba(239,68,68,0.06)"]*len(row)
        return [""]*len(row)

    st.dataframe(
        disp.style.apply(_strat_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
        height=530,
    )

    # Sort controls
    sort_col = st.selectbox(
        "Sort table by:",
        ["POP % (highest first)", "Max Profit/Lot", "R:R", "Confidence"],
        key="strat_sort_col",
    )
    sort_map = {
        "POP % (highest first)": ("POP %",          False),
        "Max Profit/Lot":        ("Max Profit/Lot",  False),
        "R:R":                   ("R:R",             False),
        "Confidence":            ("Confidence",      False),
    }
    sk, sa = sort_map[sort_col]
    if sk in df_strats.columns:
        df_sorted = df_strats.sort_values(sk, ascending=sa).head(10)
        disp2 = df_sorted[[
            "Strategy","Legs","Type","Dir",
            "Max Profit/Lot","Max Loss/Lot","Breakeven(s)","POP %","R:R","IV Match"
        ]].copy()
        disp2["Max Profit/Lot"] = disp2["Max Profit/Lot"].apply(lambda x: "₹{:,.0f}".format(x) if x < 1e7 else "Unlimited")
        disp2["Max Loss/Lot"]   = disp2["Max Loss/Lot"].apply(lambda x: "₹{:,.0f}".format(x) if x < 1e7 else "Unlimited")
        disp2["POP %"]          = disp2["POP %"].apply(lambda x: "{:.1f}%".format(x))
        disp2["R:R"]            = disp2["R:R"].apply(lambda x: "{:.2f}:1".format(x) if x > 0 else "N/A")
        st.markdown(f"**Top 10 by {sort_col}**")
        st.dataframe(disp2.style.apply(_strat_row_style, axis=1),
                     use_container_width=True, hide_index=True)

    # Download
    st.download_button(
        "&#x1F4E5; Download Full Strategy Table (CSV)",
        data=df_strats[[
            "Strategy","Legs","Type","Dir",
            "Max Profit/Lot","Max Loss/Lot","Breakeven(s)","POP %","R:R","IV Match"
        ]].to_csv(index=False),
        file_name="hedgex_strategy_pnl_{}.csv".format(symbol),
        mime="text/csv",
        use_container_width=True,
    )

    # IV context
    iv_note_map = {
        "EXPANDING":   "&#x26A0;&#xFE0F; EXPANDING IV: Dealer VANNA unwind is bearish. Credit spreads outperform. Avoid buying premium.",
        "COMPRESSING": "&#x2705; COMPRESSING IV: Dealer hedging supports price. Debit spreads and bull plays favored.",
        "FLAT":        "&#x27A1; FLAT IV: Range-bound regime. Iron Condors at GEX walls most efficient.",
    }
    st.markdown(
        '<div style="margin-top:10px;padding:8px 14px;background:{}15;'
        'border-left:3px solid {};border-radius:0 6px 6px 0;'
        'font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#e2e8f0;">'
        '{}</div>'.format(iv_color, iv_color, iv_note_map.get(iv_regime,"")),
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="margin-top:6px;font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#475569;">'
        '&#9888;&#xFE0F; For educational purposes only. Not financial advice. '
        'P&L computed from 5-min bar close prices. POP via Black-Scholes. '
        'Max Profit/Loss at expiry assuming held to expiry.'
        '</div>',
        unsafe_allow_html=True,
    )


# ============================================================================
# INTRADAY STRATEGIES — from 12pm IV + Morning Trend + 2pm transition
# Based on 4-year NIFTY backtest (826K bars, 596 sessions, 2021-2026)
# ============================================================================

def _compute_live_pcr(df_selected) -> float | None:
    """Compute live PCR from call/put volume in df_selected. Returns None if absent."""
    try:
        cv = float(df_selected['call_volume'].sum()) if 'call_volume' in df_selected.columns else 0
        pv = float(df_selected['put_volume'].sum())  if 'put_volume'  in df_selected.columns else 0
        if cv > 0:
            return round(pv / cv, 3)
    except Exception:
        pass
    return None


def _compute_live_morning_direction(df) -> str | None:
    """
    Determine morning direction: open (9:15-9:25) vs current/noon (12:00-12:10).
    Returns 'UP', 'DOWN', or None if not enough data.
    """
    try:
        ts = pd.to_datetime(df['timestamp'])
        open_rows = df[(ts.dt.hour == 9) & (ts.dt.minute <= 25)]
        noon_rows = df[(ts.dt.hour == 12) & (ts.dt.minute <= 10)]
        if open_rows.empty or noon_rows.empty:
            return None
        open_spot = float(open_rows['spot_price'].mean())
        noon_spot = float(noon_rows['spot_price'].mean())
        return 'UP' if noon_spot > open_spot else 'DOWN'
    except Exception:
        return None


def _compute_2pm_to_3pm_transition(df) -> tuple[str | None, str | None]:
    """Get IV regime at 2pm and 3pm for last-hour transition signal."""
    try:
        iv_df = compute_iv_trend(df)
        if iv_df.empty:
            return None, None
        ts = pd.to_datetime(iv_df['timestamp'] if 'timestamp' in iv_df.columns else df['timestamp'])
        # get 2pm and 3pm snapshots from main df
        ts_main = pd.to_datetime(df['timestamp'])
        rows_2pm = df[(ts_main.dt.hour == 14) & (ts_main.dt.minute <= 10)]
        rows_3pm = df[(ts_main.dt.hour == 15) & (ts_main.dt.minute <= 10)]
        if rows_2pm.empty or rows_3pm.empty:
            return None, None
        # re-compute iv_regime at each window
        def _regime(sub_df):
            if sub_df.empty or 'avg_iv' not in sub_df.columns:
                return 'FLAT'
            vals = sub_df['avg_iv'].dropna()
            if len(vals) < 2:
                return 'FLAT'
            slope = vals.iloc[-1] - vals.iloc[0]
            if slope > 0.08:
                return 'EXPANDING'
            elif slope < -0.08:
                return 'COMPRESSING'
            return 'FLAT'
        return _regime(rows_2pm), _regime(rows_3pm)
    except Exception:
        return None, None


def _iv_color(regime: str) -> str:
    return {'COMPRESSING': '#10b981', 'EXPANDING': '#ef4444', 'FLAT': '#94a3b8'}.get(regime, '#94a3b8')


def _signal_box(label: str, value: str, color: str, sub: str = '') -> str:
    return (
        f'<div style="background:{color}18;border:1.5px solid {color}55;border-radius:10px;'
        f'padding:10px 14px;text-align:center;min-width:110px;">'
        f'<div style="font-size:0.72rem;color:{color};text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:1.15rem;font-weight:700;color:{color};">{value}</div>'
        + (f'<div style="font-size:0.7rem;color:#94a3b8;margin-top:3px;">{sub}</div>' if sub else '')
        + '</div>'
    )


def _strategy_card(num: str, name: str, color: str, signal: str,
                   entry: str, stats_rows: list[tuple], notes: list[str],
                   active: bool = False, avoid: str = '') -> str:
    border = f'border:2px solid {color};' if active else f'border:1px solid {color}44;'
    active_badge = (
        f'<span style="background:{color};color:#fff;font-size:0.65rem;font-weight:700;'
        f'padding:2px 8px;border-radius:20px;margin-left:10px;vertical-align:middle;">'
        f'&#x25CF; LIVE NOW</span>'
    ) if active else ''

    rows_html = ''
    for label, val, note in stats_rows:
        rows_html += (
            f'<tr>'
            f'<td style="padding:5px 8px;color:#94a3b8;font-size:0.78rem;">{label}</td>'
            f'<td style="padding:5px 8px;font-weight:600;font-size:0.85rem;color:#e2e8f0;">{val}</td>'
            f'<td style="padding:5px 8px;color:#64748b;font-size:0.75rem;">{note}</td>'
            f'</tr>'
        )

    notes_html = ''.join(
        f'<li style="color:#94a3b8;font-size:0.78rem;margin-bottom:3px;">{n}</li>'
        for n in notes
    )

    avoid_html = (
        f'<div style="background:#ef444418;border-left:3px solid #ef4444;padding:6px 10px;'
        f'border-radius:0 6px 6px 0;margin-top:8px;font-size:0.78rem;color:#ef4444;">'
        f'<strong>AVOID:</strong> {avoid}</div>'
    ) if avoid else ''

    return (
        f'<div style="background:#0f172a;{border}border-radius:14px;padding:16px 18px;margin-bottom:14px;">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">'
        f'<span style="background:{color};color:#fff;font-size:0.7rem;font-weight:700;'
        f'padding:3px 9px;border-radius:20px;">{num}</span>'
        f'<span style="font-size:1.0rem;font-weight:700;color:#f1f5f9;">{name}</span>'
        f'{active_badge}</div>'
        f'<div style="font-size:0.82rem;color:{color};margin-bottom:10px;">{signal}</div>'
        f'<div style="font-size:0.8rem;color:#cbd5e1;background:#1e293b;padding:8px 12px;'
        f'border-radius:8px;margin-bottom:10px;">'
        f'<strong style="color:#94a3b8;">Entry:</strong> {entry}</div>'
        f'<table style="width:100%;border-collapse:collapse;margin-bottom:8px;">'
        f'<thead><tr>'
        f'<th style="background:#1e293b;padding:5px 8px;text-align:left;font-size:0.75rem;'
        f'color:#64748b;border-radius:4px 0 0 4px;">Metric</th>'
        f'<th style="background:#1e293b;padding:5px 8px;text-align:left;font-size:0.75rem;color:#64748b;">Value</th>'
        f'<th style="background:#1e293b;padding:5px 8px;text-align:left;font-size:0.75rem;'
        f'color:#64748b;border-radius:0 4px 4px 0;">Note</th>'
        f'</tr></thead><tbody>{rows_html}</tbody></table>'
        f'<ul style="margin:0 0 4px 14px;padding:0;">{notes_html}</ul>'
        f'{avoid_html}'
        f'</div>'
    )


def render_intraday_strategy_tab(df, df_selected, spot_price, iv_regime, unit_label):
    """Renders the Intraday Strategy sub-tab inside Strategy Hub."""

    st.markdown("### &#x23F0; Intraday Strategies — 12pm Entry → 3:10pm Exit")
    st.caption(
        "3 strategies derived from 826,456 bars of NIFTY data (2021–2026). "
        "Entry at 12:00 PM. Exit at 3:10 PM same day. "
        "PCR computed from live call/put volume if OI not available."
    )

    # ── Live signal computation ──────────────────────────────────────────────
    morning_dir  = _compute_live_morning_direction(df)
    live_pcr     = _compute_live_pcr(df_selected)
    current_hour = pd.Timestamp.now().hour

    # ── Live signal banner ───────────────────────────────────────────────────
    banner_parts = []

    iv_col   = _iv_color(iv_regime)
    banner_parts.append(_signal_box("12pm IV Regime", iv_regime, iv_col))

    if morning_dir:
        m_col = '#10b981' if morning_dir == 'UP' else '#ef4444'
        banner_parts.append(_signal_box("Morning Trend", morning_dir, m_col, "9:15am → 12pm"))
    else:
        banner_parts.append(_signal_box("Morning Trend", "—", '#64748b', "Data after 12pm"))

    if live_pcr is not None:
        pcr_col = '#ef4444' if live_pcr < 0.8 else ('#10b981' if live_pcr > 1.0 else '#94a3b8')
        pcr_label = 'BEARISH' if live_pcr < 0.8 else ('BULLISH' if live_pcr > 1.0 else 'NEUTRAL')
        banner_parts.append(_signal_box("Vol PCR", f"{live_pcr:.2f}", pcr_col, pcr_label))
    else:
        banner_parts.append(_signal_box("PCR", "N/A", '#64748b', "Vol-based proxy"))

    # 2pm→3pm transition
    iv_2pm, iv_3pm = _compute_2pm_to_3pm_transition(df)
    if iv_2pm and iv_3pm:
        trans_str = f"{iv_2pm}→{iv_3pm}"
        trans_col = '#10b981' if iv_3pm == 'COMPRESSING' else ('#ef4444' if iv_3pm == 'EXPANDING' else '#94a3b8')
        banner_parts.append(_signal_box("2pm→3pm IV", trans_str, trans_col, "Last-hr signal"))
    else:
        banner_parts.append(_signal_box("2pm→3pm IV", "—", '#64748b', "After 2pm"))

    banner_html = (
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px;">'
        + ''.join(banner_parts) +
        '</div>'
    )
    st.markdown(banner_html, unsafe_allow_html=True)

    # ── Active signal recommender ────────────────────────────────────────────
    if morning_dir and current_hour >= 12:
        reco_lines = []
        # IS-1 signal
        if iv_regime in ('EXPANDING', 'FLAT'):
            trade = 'CALL' if morning_dir == 'UP' else 'PUT'
            wr    = '61%' if iv_regime == 'EXPANDING' else '58%'
            reco_lines.append(
                f"<strong>IS-1</strong> — {iv_regime} + Morning {morning_dir} → "
                f"<span style='color:{'#10b981' if trade=='CALL' else '#ef4444'};font-weight:700;'>{trade}</span> "
                f"({wr} WR historically)"
            )
        elif iv_regime == 'COMPRESSING':
            reco_lines.append(
                "<strong>IS-1</strong> — COMPRESSING IV: weak signal (49–52%). "
                "Reduce size or skip. Prefer IS-2 confirmation."
            )
        # IS-2 signal from volume PCR
        if live_pcr is not None:
            if live_pcr < 0.8 and morning_dir == 'DOWN':
                reco_lines.append(
                    f"<strong>IS-2</strong> — PCR {live_pcr:.2f} (bearish) + Morning DOWN → "
                    "<span style='color:#ef4444;font-weight:700;'>PUT</span> (85% WR, N=160)"
                )
            elif live_pcr > 1.0 and morning_dir == 'UP':
                reco_lines.append(
                    f"<strong>IS-2</strong> — PCR {live_pcr:.2f} (bullish) + Morning UP → "
                    "<span style='color:#10b981;font-weight:700;'>CALL</span> (78% WR, N=112)"
                )
            elif (live_pcr < 0.8 and morning_dir == 'UP') or (live_pcr > 1.0 and morning_dir == 'DOWN'):
                reco_lines.append(
                    f"<strong>IS-2</strong> — PCR {live_pcr:.2f} conflicts with morning {morning_dir}. "
                    "<span style='color:#f59e0b;'>SKIP IS-2.</span>"
                )
        else:
            reco_lines.append(
                "<strong>IS-2</strong> — PCR unavailable (no OI data). Use IS-1 signal only."
            )
        # IS-3 signal
        if iv_2pm and iv_3pm and current_hour >= 14:
            if iv_2pm == 'COMPRESSING' and iv_3pm == 'EXPANDING':
                reco_lines.append(
                    "<strong>IS-3</strong> — COMP→EXP at 3pm: sellers capitulating → "
                    "<span style='color:#ef4444;font-weight:700;'>PUT</span> (39% up = 61% PUT, last hour)"
                )
            elif iv_2pm == 'FLAT' and iv_3pm == 'COMPRESSING':
                reco_lines.append(
                    "<strong>IS-3</strong> — FLAT→COMP at 3pm: late sellers in → "
                    "<span style='color:#10b981;font-weight:700;'>CALL</span> (mild +5 pts, N=52)"
                )

        if reco_lines:
            reco_html = (
                '<div style="background:#0f172a;border:1.5px solid #3b82f6;border-radius:12px;'
                'padding:12px 16px;margin-bottom:16px;">'
                '<div style="font-size:0.72rem;color:#3b82f6;text-transform:uppercase;'
                'letter-spacing:0.08em;margin-bottom:8px;">&#x26A1; Live Signal Recommendation</div>'
                + ''.join(
                    f'<div style="font-size:0.85rem;color:#cbd5e1;margin-bottom:5px;">&#x2714; {r}</div>'
                    for r in reco_lines
                )
                + '</div>'
            )
            st.markdown(reco_html, unsafe_allow_html=True)

    # ── IS-1: Morning Trend + 12pm IV ───────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Strategy Cards")

    active_is1 = bool(morning_dir and iv_regime in ('EXPANDING','FLAT') and current_hour >= 12)
    is1_html = _strategy_card(
        num="IS-1", name="Morning Trend + 12pm IV Confirmation",
        color="#3b82f6",
        signal="Check which way NIFTY moved 9:15am→12pm. Combine with 12pm IV regime. "
               "When both agree, enter. Highest-N signal in 4-year dataset.",
        entry="At 12:00pm — note if spot is above/below 9:15am open. "
              "Check IV regime. EXP/FLAT + morning UP = CALL. EXP/FLAT + morning DOWN = PUT. "
              "COMPRESSING = reduce size or skip.",
        stats_rows=[
            ("EXP + Morning UP → CALL",  "61% WR, +22 pts",   "N=76, Sharpe 0.22"),
            ("FLAT + Morning UP → CALL", "58% WR, +15 pts",   "N=113, Sharpe 0.07"),
            ("EXP + Morning DN → PUT",   "63% WR, −13 pts",   "N=52, Sharpe 0.14"),
            ("FLAT + Morning DN → PUT",  "55% WR, −8 pts",    "N=82, Sharpe 0.34"),
            ("COMP + Morning UP/DN",     "49–52% WR (noise)", "Skip or half size"),
        ],
        notes=[
            "Stop loss: 65 pts (CALL side), 40 pts (PUT side) — 25th pct of bad days.",
            "Signal stronger in new era (Tue expiry): FLAT+DN now 88% PUT accuracy.",
            "Exit strictly at 3:10pm. No overnight hold with this strategy.",
        ],
        active=active_is1,
        avoid="COMPRESSING + any morning direction — 49–52% WR, effectively coin flip."
    )
    st.markdown(is1_html, unsafe_allow_html=True)

    # ── IS-2: PCR + Morning Trend ────────────────────────────────────────────
    active_is2 = bool(
        morning_dir and live_pcr is not None and current_hour >= 12 and
        ((live_pcr < 0.8 and morning_dir == 'DOWN') or (live_pcr > 1.0 and morning_dir == 'UP'))
    )
    pcr_note = (
        "PCR computed from live call/put volume (proxy for OI PCR). "
        "Signal direction is the same."
    ) if live_pcr is not None else (
        "PCR not available — call/put volume data absent. This strategy cannot fire today."
    )
    is2_html = _strategy_card(
        num="IS-2", name="12pm PCR Band + Morning Trend",
        color="#10b981",
        signal=f"PCR < 0.8 = more calls written = bearish. PCR > 1.0 = more puts written = bullish. "
               f"Combine with morning direction. {pcr_note}",
        entry="At 12:00pm — check morning direction AND PCR. "
              "PCR > 1.0 + morning UP = CALL. PCR < 0.8 + morning DOWN = PUT. "
              "Conflicting PCR and morning = SKIP. Exit 3:10pm.",
        stats_rows=[
            ("PCR < 0.8 + Morning DN → PUT", "85% WR, −5 pts median", "N=160, highest WR intraday"),
            ("PCR > 1.0 + Morning UP → CALL","78% WR, +9 pts median", "N=112"),
            ("PCR < 0.8 + Morning UP → CALL","71% WR, +30 pts",       "N=56, strong momentum"),
            ("PCR > 1.0 + Morning DN → PUT", "82% WR, −10 pts",       "N=28, less frequent"),
        ],
        notes=[
            "PCR < 0.8 + morning DOWN is the highest win-rate intraday setup (85%, N=160).",
            "Uses call/put volume as proxy when OI PCR is absent — same signal direction.",
            "Best on E-3 and E-2 days. Avoid using on expiry day — dynamics override.",
            "Stop: 50 pts CALL side, 40 pts PUT side.",
        ],
        active=active_is2,
        avoid="Conflicting PCR + morning direction (e.g., PCR > 1.0 but morning DOWN). SKIP."
    )
    st.markdown(is2_html, unsafe_allow_html=True)

    # ── IS-3: 2pm→3pm IV Transition ─────────────────────────────────────────
    trans_label = f"{iv_2pm}→{iv_3pm}" if iv_2pm and iv_3pm else "Not yet available"
    active_is3 = bool(
        iv_2pm and iv_3pm and current_hour >= 14 and
        ((iv_2pm == 'COMPRESSING' and iv_3pm == 'EXPANDING') or
         (iv_2pm == 'FLAT' and iv_3pm == 'COMPRESSING'))
    )
    is3_html = _strategy_card(
        num="IS-3", name="2pm→3pm IV Transition — Last Hour Trade",
        color="#f59e0b",
        signal=f"Current transition: {trans_label}. "
               "COMP→EXP = sellers capitulating → PUT. "
               "FLAT→COMP = late sellers entering → mild CALL. "
               "Weakest of the 3 — use only when IS-1 and IS-2 have no clear signal.",
        entry="At 2:00pm check IV regime. At 3:00pm check again. "
              "COMP→EXP: enter PUT immediately. FLAT→COMP: enter CALL. "
              "Exit strictly at 3:10pm. Do NOT hold overnight.",
        stats_rows=[
            ("COMP → EXPANDING → PUT",  "61% PUT WR, −13 pts",  "N=54, Sharpe −0.19"),
            ("FLAT → COMPRESSING → CALL","52% UP, +5 pts",       "N=52, Sharpe 0.09"),
            ("EXP → COMP (OLD era)",    "55% UP, +6 pts",        "N=44 — skip in new era"),
            ("EXP → COMP (NEW era)",    "31% UP, −14 pts",       "N=16 — AVOID"),
        ],
        notes=[
            "This is the weakest strategy. Use only when IS-1 and IS-2 give no signal.",
            "COMP→EXP is reliable for PUT. FLAT→COMP is mild — small size only.",
            "Small position size recommended — Sharpe is low on both sides.",
            "Stop: 20 pts. Very tight given the 60-min window.",
        ],
        active=active_is3,
        avoid="EXP→COMP in new era (Sep 2025+): 31% win rate, −14 pts median. Do not trade."
    )
    st.markdown(is3_html, unsafe_allow_html=True)

    # ── universal rules ──────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;'
        'padding:12px 16px;margin-top:4px;">'
        '<div style="font-size:0.75rem;color:#f59e0b;font-weight:700;margin-bottom:8px;">'
        '&#x26A1; Universal Intraday Rules</div>'
        '<ul style="margin:0;padding-left:16px;color:#94a3b8;font-size:0.8rem;">'
        '<li>Morning trend (9:15→12pm) is always <strong style="color:#e2e8f0;">primary</strong>. Never trade against a confirmed morning trend.</li>'
        '<li>12pm is the only hour with strong IV predictive power. Ignore IV at 9am or 11am.</li>'
        '<li>IS-1 + IS-2 agreeing = maximum conviction. Size up to 100% allocation.</li>'
        '<li>IS-1 or IS-2 alone = 60-70% allocation. IS-3 alone = 20% max.</li>'
        '<li>All exits at 3:10pm sharp. No overnight from intraday setups.</li>'
        '</ul></div>',
        unsafe_allow_html=True
    )


# ============================================================================
# BTST STRATEGIES — from 3:05–3:20 PM close signal
# Based on 4-year NIFTY backtest (826K bars, 596 sessions, 2021-2026)
# ============================================================================

def _compute_btst_transitions(df) -> tuple[str | None, str | None]:
    """
    Get IV regime at 3:05 PM window and 3:20 PM window.
    Returns (iv_305, iv_320) or (None, None) if data not available.
    """
    try:
        ts = pd.to_datetime(df['timestamp'])
        rows_305 = df[(ts.dt.hour == 15) & (ts.dt.minute >= 3) & (ts.dt.minute <= 8)]
        rows_320 = df[(ts.dt.hour == 15) & (ts.dt.minute >= 18) & (ts.dt.minute <= 22)]

        def _regime(sub):
            if sub.empty or 'avg_iv' not in sub.columns:
                return 'FLAT'
            vals = sub['avg_iv'].dropna()
            if len(vals) < 2:
                return 'FLAT'
            slope = vals.iloc[-1] - vals.iloc[0]
            if slope > 0.05:
                return 'EXPANDING'
            elif slope < -0.05:
                return 'COMPRESSING'
            return 'FLAT'

        iv_305 = _regime(rows_305) if not rows_305.empty else None
        iv_320 = _regime(rows_320) if not rows_320.empty else None
        return iv_305, iv_320
    except Exception:
        return None, None


def _compute_dte_label(df) -> str:
    """Compute DTE label (E, E-1, E-2, E-3, E-4) from the df's trade date."""
    try:
        ts = pd.to_datetime(df['timestamp'])
        trade_date = ts.iloc[-1].date()
        dow = trade_date.weekday()
        cutoff = pd.Timestamp('2025-09-01').date()
        expiry_dow = 1 if trade_date >= cutoff else 3
        dte = (expiry_dow - dow) % 7
        return {0: 'E (Expiry)', 1: 'E-1', 2: 'E-2', 3: 'E-3', 4: 'E-4'}.get(dte, 'E-3')
    except Exception:
        return 'Unknown'


def render_btst_strategy_tab(df, df_selected, spot_price, iv_regime, unit_label):
    """Renders the BTST Strategy sub-tab inside Strategy Hub."""

    st.markdown("### &#x1F319; BTST Strategies — Buy Today, Sell Tomorrow")
    st.caption(
        "3 strategies derived from 826,456 bars of NIFTY data (2021–2026). "
        "Entry: 3:05–3:15 PM. Exit A: Next-day open. Exit B: 11:00 AM next day. "
        "PCR computed from live volume when OI PCR is absent."
    )

    # ── Live computation ─────────────────────────────────────────────────────
    iv_305, iv_320    = _compute_btst_transitions(df)
    morning_dir       = _compute_live_morning_direction(df)
    live_pcr          = _compute_live_pcr(df_selected)
    dte_label         = _compute_dte_label(df)
    current_hour      = pd.Timestamp.now().hour
    closing_regime    = iv_regime   # 3pm snapshot passed from precompute

    transition_str = (
        f"{iv_305}→{iv_320}" if iv_305 and iv_320
        else ("3:05 data only" if iv_305 else "Available after 3:05 PM")
    )

    # ── Live signal banner ───────────────────────────────────────────────────
    banner_parts = [
        _signal_box("DTE Today", dte_label, '#8b5cf6'),
        _signal_box("Closing IV", closing_regime, _iv_color(closing_regime), "3pm regime"),
    ]
    if iv_305 and iv_320:
        t_col = '#10b981' if iv_320 == 'COMPRESSING' else ('#ef4444' if iv_320 == 'EXPANDING' else '#94a3b8')
        banner_parts.append(_signal_box("3:05→3:20 IV", transition_str, t_col))
    else:
        banner_parts.append(_signal_box("3:05→3:20 IV", transition_str, '#64748b'))

    if morning_dir:
        m_col = '#10b981' if morning_dir == 'UP' else '#ef4444'
        banner_parts.append(_signal_box("Morning Trend", morning_dir, m_col, "9:15am→12pm"))
    else:
        banner_parts.append(_signal_box("Morning Trend", "—", '#64748b', "After 12pm"))

    if live_pcr is not None:
        pcr_col = '#ef4444' if live_pcr < 0.8 else ('#10b981' if live_pcr > 1.0 else '#94a3b8')
        banner_parts.append(_signal_box("Vol PCR", f"{live_pcr:.2f}", pcr_col,
                                        'BEARISH' if live_pcr < 0.8 else ('BULLISH' if live_pcr > 1.0 else 'NEUTRAL')))
    else:
        banner_parts.append(_signal_box("PCR", "N/A", '#64748b', "Vol proxy"))

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:18px;">'
        + ''.join(banner_parts) + '</div>',
        unsafe_allow_html=True
    )

    # ── BTST live signal recommender ─────────────────────────────────────────
    reco_lines = []

    # BS-1: transition signal
    if iv_305 and iv_320:
        if iv_320 == 'COMPRESSING' and iv_305 in ('FLAT', 'EXPANDING'):
            strength = '73% GapUP, +45 pts O/N' if iv_305 == 'FLAT' else '61% GapUP, +46 pts O/N'
            reco_lines.append(
                f"<strong>BS-1 ACTIVE</strong> — {iv_305}→COMP transition: "
                f"<span style='color:#10b981;font-weight:700;'>BUY CALL at 3:10pm</span> ({strength})"
            )
        elif iv_305 == 'EXPANDING' and iv_320 == 'EXPANDING':
            reco_lines.append(
                "<strong>BS-1 TRAP</strong> — EXP→EXP: gap up may appear next morning but "
                "<span style='color:#ef4444;font-weight:700;'>AVOID overnight hold</span>. "
                "Median O/N = −26 pts."
            )
        elif iv_305 == 'EXPANDING' and iv_320 == 'FLAT':
            reco_lines.append(
                "<strong>BS-1 WARNING</strong> — EXP→FLAT: 40% gap up, −23 pts median. "
                "<span style='color:#ef4444;'>Do not take BTST.</span>"
            )

    # BS-2: E-3 day
    if 'E-3' in dte_label and closing_regime in ('FLAT', 'COMPRESSING'):
        wr = '74%' if closing_regime == 'FLAT' else '73%'
        med = '+26.5 pts' if closing_regime == 'FLAT' else '+27.1 pts'
        reco_lines.append(
            f"<strong>BS-2 ACTIVE</strong> — E-3 day + {closing_regime} close: "
            f"<span style='color:#10b981;font-weight:700;'>BUY CALL at 3:10pm</span> "
            f"(GapUP {wr}, O/N median {med})"
        )
    elif 'E-3' in dte_label and closing_regime == 'EXPANDING':
        reco_lines.append(
            "<strong>BS-2 AVOID</strong> — E-3 + EXPANDING close: "
            "<span style='color:#ef4444;'>skip overnight</span>. Median O/N = −10.8 pts."
        )

    # BS-3: morning UP + PCR
    if morning_dir == 'UP' and live_pcr is not None and live_pcr > 1.0:
        reco_lines.append(
            f"<strong>BS-3 ACTIVE</strong> — Morning UP + PCR {live_pcr:.2f} (>1.0): "
            f"<span style='color:#10b981;font-weight:700;'>BUY CALL at 3:10pm</span> "
            "(67% O/N UP, median +64 pts)"
        )
    elif morning_dir == 'DOWN' and live_pcr is not None and live_pcr < 0.8:
        reco_lines.append(
            f"<strong>BS-3 NOTE</strong> — Morning DN + PCR {live_pcr:.2f} (<0.8): "
            "PUT side has negative Sharpe (−0.12). "
            "<span style='color:#f59e0b;'>Skip — not reliable.</span>"
        )

    if not reco_lines and current_hour >= 15:
        reco_lines.append(
            "No high-confidence BTST signal today. "
            "Check BS-1 after 3:20pm for transition confirmation."
        )

    if reco_lines:
        reco_html = (
            '<div style="background:#0f172a;border:1.5px solid #8b5cf6;border-radius:12px;'
            'padding:12px 16px;margin-bottom:16px;">'
            '<div style="font-size:0.72rem;color:#8b5cf6;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:8px;">&#x1F319; Live BTST Signal</div>'
            + ''.join(
                f'<div style="font-size:0.85rem;color:#cbd5e1;margin-bottom:5px;">&#x2714; {r}</div>'
                for r in reco_lines
            )
            + '</div>'
        )
        st.markdown(reco_html, unsafe_allow_html=True)

    # ── BS-1 strategy card ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### BTST Strategy Cards")

    active_bs1 = bool(iv_305 and iv_320 == 'COMPRESSING' and iv_305 in ('FLAT', 'EXPANDING'))
    bs1_html = _strategy_card(
        num="BS-1", name="3:05→3:20 PM IV Transition — Overnight Gap Signal",
        color="#10b981",
        signal=f"Current transition: {transition_str}. "
               "When IV moves INTO Compressing between 3:05 and 3:20pm, sellers stepped in at close. "
               "Their pressure releases as a gap-up next morning. Most reliable BTST signal (2021–2026).",
        entry="At 3:05pm: note IV regime. At 3:20pm: check if changed. "
              "FLAT→COMP or EXP→COMP → BUY CALL at 3:10pm. "
              "Exit A: sell at next-day open (gap capture). Exit B: hold till 11am (+46 pts median).",
        stats_rows=[
            ("FLAT → COMPRESSING → CALL",     "73% GapUP, +45.5 O/N",  "N=52, Sharpe 0.24, 4/4 yrs"),
            ("EXPANDING → COMPRESSING → CALL","61% GapUP, +46.2 O/N",  "N=72, Sharpe 0.18, 4/4 yrs"),
            ("COMPRESSING → FLAT",            "53% GapUP, +31.5 O/N",  "N=51 — broke in 2026, avoid"),
            ("EXP → EXP (TRAP)",              "58% GapUP but −26 O/N", "Gap appears, reverses by 11am"),
            ("EXP → FLAT",                    "46% GapUP, −23 O/N",    "PUT territory — do not buy CALL"),
        ],
        notes=[
            "Fires ~50–70 days per year. High frequency and reliability.",
            "O/N pts are even higher in new era (Tue expiry): +68–73 pts median vs +43–44 old era.",
            "Stop: exit if next-day open is >25 pts below your call entry premium value.",
            "If both FLAT→COMP and EXP→COMP fire together (rare): maximum conviction, full size.",
        ],
        active=active_bs1,
        avoid="COMP→FLAT: broke in 2026 (0% win rate). EXP→EXP: gap trap — do not hold overnight."
    )
    st.markdown(bs1_html, unsafe_allow_html=True)

    # ── BS-2 strategy card ───────────────────────────────────────────────────
    active_bs2 = bool('E-3' in dte_label and closing_regime in ('FLAT', 'COMPRESSING'))
    bs2_html = _strategy_card(
        num="BS-2", name="E-3 Day Close — Weekly Drift Overnight",
        color="#1d9e75",
        signal=f"Today is {dte_label}. E-3 is the quietest expiry day — no active seller defense. "
               "When E-3 closes FLAT or COMP, the next morning (E-2) gaps up as MMs load new positions. "
               "Structural weekly pattern — not a directional bet.",
        entry="Confirm today is E-3 (Mon in old era / Thu or Fri in new era). "
              "At 3:05–3:15pm: check closing IV. FLAT or COMP → BUY CALL at 3:10pm. "
              "EXPANDING → DO NOT take the BTST. Exit: next-day open or 11am.",
        stats_rows=[
            ("E-3 + FLAT → CALL",     "74% GapUP, 64% O/N, +26.5 pts", "N=50, Sharpe 0.26"),
            ("E-3 + COMP → CALL",     "73% GapUP, 68% O/N, +27.1 pts", "N=22, Sharpe 0.36"),
            ("E-3 + EXPANDING",       "58% GapUP, −10.8 O/N",           "AVOID — gap fades"),
        ],
        notes=[
            "E-3 in new era (Sep 2025+) is Thursday or Friday — check DTE label above.",
            "Sharpe 0.36 on E-3 COMP is the most consistent single-cell BTST setup.",
            "2025 FLAT win rate dipped to 47% (choppy year). Use BS-1 as primary in new era.",
            "Stop: 35 pts (FLAT), 28 pts (COMP) — 25th pct of bad days.",
        ],
        active=active_bs2,
        avoid="E-3 + EXPANDING close: 47% overnight up, median −10.8 pts. Skip entirely."
    )
    st.markdown(bs2_html, unsafe_allow_html=True)

    # ── BS-3 strategy card ───────────────────────────────────────────────────
    active_bs3 = bool(morning_dir == 'UP' and live_pcr is not None and live_pcr > 1.0)
    pcr_note_bs3 = (
        f"Live volume PCR = {live_pcr:.2f} (proxy for OI PCR, same signal direction)."
        if live_pcr is not None
        else "PCR not available from this data source — skip BS-3 today."
    )
    bs3_html = _strategy_card(
        num="BS-3", name="Morning Trend + Closing PCR — Overnight Continuation",
        color="#3b82f6",
        signal=f"Morning was {morning_dir or '—'}. {pcr_note_bs3} "
               "When market trended UP all morning AND put writers are confident (PCR > 1.0) at close, "
               "gap-up continuation is high probability.",
        entry="At 12pm: confirm NIFTY is above 9:15am open (morning UP). "
              "At 3:05pm: check PCR — must be above 1.0. "
              "Both conditions met → BUY CALL at 3:10pm. "
              "Exit A: next-day open (median gap +32 pts). Exit B: 11am (+64 pts median).",
        stats_rows=[
            ("Morning UP + PCR > 1.0 → CALL","67% O/N UP, +63.9 pts", "N=91, Sharpe 0.17"),
            ("Morning DN + PCR < 0.8",        "44% O/N UP, −20.5 pts", "AVOID — negative Sharpe"),
            ("Year consistency",              "100% (2021), 54–68% recent", "Normalising over years"),
        ],
        notes=[
            "PCR must be checked at 3:05pm (not 12pm) — it shifts significantly in the afternoon.",
            "Best on E-3 and E-2 days. Avoid on E-1 or expiry day — gamma overrides PCR signal.",
            "Morning DOWN + PCR < 0.8 as PUT: −0.12 Sharpe, deteriorating. Do not trade.",
            "If PCR is absent: use call/put volume ratio as computed above.",
        ],
        active=active_bs3,
        avoid="Morning DOWN + PCR < 0.8 PUT: −0.12 Sharpe. Skip. BS-1 is the primary BTST."
    )
    st.markdown(bs3_html, unsafe_allow_html=True)

    # ── BTST universal rules ──────────────────────────────────────────────────
    st.markdown(
        '<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;'
        'padding:12px 16px;margin-top:4px;">'
        '<div style="font-size:0.75rem;color:#8b5cf6;font-weight:700;margin-bottom:8px;">'
        '&#x1F319; Universal BTST Rules</div>'
        '<ul style="margin:0;padding-left:16px;color:#94a3b8;font-size:0.8rem;">'
        '<li><strong style="color:#e2e8f0;">EXP→EXP at 3:20pm = overnight trap always.</strong> Gap looks bullish. Reverse by 11am. Never hold.</li>'
        '<li>BS-1 is primary. BS-2 and BS-3 are secondary confirmations.</li>'
        '<li>BS-1 + BS-2 both firing on same E-3 day = maximum conviction.</li>'
        '<li>Exit A (open) is safe. Exit B (11am) captures full move but needs tight stop at open.</li>'
        '<li>Never use BS-3 PUT side (morning DN + PCR low) — negative Sharpe across all years.</li>'
        '</ul></div>',
        unsafe_allow_html=True
    )



# ============================================================================
# NEXT-DAY STRATEGY FROM 3:15 PM VANNA FLIP ZONE READING
# Uses compute_breakout_probability output at 3:15 PM window
# Includes primary strategy + inverse hedge for risk management
# ============================================================================

def compute_315pm_flip_signal(df: pd.DataFrame, spot_price: float, tte: float) -> dict:
    """
    Reads VANNA flip zone directional probabilities specifically from
    the 3:00–3:15 PM window. Returns aggregated direction, IV regime,
    top zones and scores for next-day strategy design.
    """
    if df is None or len(df) == 0:
        return {"status": "NO_DATA"}

    try:
        ts_col = df["timestamp"].dt
        window_df_raw = df[
            (ts_col.hour == 15) & (ts_col.minute <= 15)
        ].copy()
    except Exception:
        return {"status": "NO_DATA"}

    if len(window_df_raw) == 0:
        return {"status": "NO_DATA", "message": "No data in 3:00–3:15 PM window"}

    # Use last timestamp in window (3:15 or nearest)
    last_ts = window_df_raw["timestamp"].max()
    df_slice = window_df_raw[window_df_raw["timestamp"] == last_ts].copy()

    spot_ts = float(df_slice["spot_price"].iloc[0]) if len(df_slice) > 0 else spot_price

    # Compute IV trend from full df but read only window value
    iv_df_full = compute_iv_trend(df)
    iv_window  = iv_df_full[iv_df_full["timestamp"] <= last_ts]
    if iv_window.empty:
        iv_window = iv_df_full.iloc[:1]
    iv_at_315  = iv_window.iloc[-1]
    iv_regime  = str(iv_at_315.get("iv_regime", "FLAT"))
    iv_skew    = float(iv_at_315.get("iv_skew",   0.0))
    avg_iv     = float(iv_at_315.get("avg_iv",    15.0))
    iv_slope   = float(iv_at_315.get("iv_slope",   0.0))

    # Identify VANNA flip zones at 3:15 PM
    vanna_zones_315 = identify_vanna_flip_zones(df_slice, spot_ts)
    if not vanna_zones_315:
        return {"status": "NO_ZONES", "iv_regime": iv_regime, "iv_skew": iv_skew}

    # Compute directional probabilities
    prob_df = compute_breakout_probability(vanna_zones_315, iv_window, spot_ts, tte, df_slice)
    if prob_df.empty:
        return {"status": "NO_PROB", "iv_regime": iv_regime}

    # Aggregate direction — weighted by final_score
    total_score = prob_df["final_score"].sum() or 1
    weighted_bull = (prob_df["bull_score"] * prob_df["final_score"]).sum() / total_score
    weighted_bear = (prob_df["bear_score"] * prob_df["final_score"]).sum() / total_score

    # Dominant direction from majority of zones
    bull_zones = (prob_df["direction"] == "BULLISH").sum()
    bear_zones = (prob_df["direction"] == "BEARISH").sum()
    conf_zones = (prob_df["direction"] == "CONFLICTED").sum()

    if bull_zones > bear_zones and weighted_bull > weighted_bear:
        agg_direction = "BULLISH"
        agg_confidence = round(weighted_bull, 1)
    elif bear_zones > bull_zones and weighted_bear > weighted_bull:
        agg_direction = "BEARISH"
        agg_confidence = round(weighted_bear, 1)
    elif conf_zones >= bull_zones and conf_zones >= bear_zones:
        agg_direction = "CONFLICTED"
        agg_confidence = round(max(weighted_bull, weighted_bear), 1)
    else:
        agg_direction = "NEUTRAL"
        agg_confidence = 50.0

    # Top 3 zones by score
    top_zones = prob_df.head(3).to_dict("records")

    # Key strikes for strategy construction
    strikes_sorted = sorted(df_slice["strike"].unique().tolist())
    interval = strikes_sorted[1] - strikes_sorted[0] if len(strikes_sorted) > 1 else 50

    resist_zones = prob_df[prob_df["role"].isin(["RESISTANCE_CEILING"])]["strike"].tolist()
    support_zones = prob_df[prob_df["role"].isin(["SUPPORT_FLOOR"])]["strike"].tolist()
    vacuum_zones  = prob_df[prob_df["role"] == "VACUUM_ZONE"]["strike"].tolist()
    trap_zones    = prob_df[prob_df["role"] == "TRAP_DOOR"]["strike"].tolist()

    nearest_resist = min([s for s in resist_zones if s > spot_ts], default=spot_ts + interval*3, key=lambda x: abs(x-spot_ts))
    nearest_support = min([s for s in support_zones if s < spot_ts], default=spot_ts - interval*3, key=lambda x: abs(x-spot_ts))

    return {
        "status":           "OK",
        "timestamp":        str(last_ts),
        "spot_at_315":      spot_ts,
        "iv_regime":        iv_regime,
        "iv_skew":          iv_skew,
        "avg_iv":           avg_iv,
        "iv_slope":         iv_slope,
        "agg_direction":    agg_direction,
        "agg_confidence":   agg_confidence,
        "weighted_bull":    round(weighted_bull, 1),
        "weighted_bear":    round(weighted_bear, 1),
        "bull_zones":       int(bull_zones),
        "bear_zones":       int(bear_zones),
        "conf_zones":       int(conf_zones),
        "top_zones":        top_zones,
        "prob_df":          prob_df,
        "nearest_resist":   nearest_resist,
        "nearest_support":  nearest_support,
        "vacuum_zones":     vacuum_zones,
        "trap_zones":       trap_zones,
        "strikes_sorted":   strikes_sorted,
        "interval":         interval,
    }


def design_nextday_strategy(sig: dict, lot_size: int, tte_next: float, symbol: str) -> dict:
    """
    Given the 3:15 PM signal dict, design:
    - PRIMARY strategy aligned to direction + IV regime
    - HEDGE strategy to cap loss if market inverts
    Returns full strategy spec with legs, P&L, reasoning.
    """
    direction  = sig["agg_direction"]
    iv_regime  = sig["iv_regime"]
    iv_skew    = sig["iv_skew"]
    spot       = sig["spot_at_315"]
    conf       = sig["agg_confidence"]
    nr         = sig["nearest_resist"]
    ns         = sig["nearest_support"]
    interval   = sig["interval"]
    vacuums    = sig["vacuum_zones"]
    traps      = sig["trap_zones"]
    r          = 0.065

    def nearest_s(target, strikes):
        return min(strikes, key=lambda x: abs(x-target)) if strikes else target

    strikes = sig["strikes_sorted"]

    def _bs(S, K, T, sigma, opt):
        try:
            return max(_bs_live(S, K, T, r, max(sigma,0.05), opt), 0.01)
        except Exception:
            return 5.0

    avg_iv_d = (sig["avg_iv"]/100) if sig["avg_iv"] > 1 else sig["avg_iv"]
    avg_iv_d = max(avg_iv_d, 0.10)

    atm = nearest_s(spot, strikes)

    # ─────────────────────────────────────────────────────────────────────────
    # PRIMARY STRATEGY DESIGN
    # ─────────────────────────────────────────────────────────────────────────
    primary = {}
    hedge   = {}

    if direction == "BULLISH":
        if iv_regime == "COMPRESSING":
            # Bull Call Spread — debit, defined risk, best in compressing IV
            buy_k   = atm
            sell_k  = nearest_s(nr, strikes) if nr > atm else nearest_s(atm + interval*3, strikes)
            buy_px  = _bs(spot, buy_k,  tte_next, avg_iv_d, "CE")
            sell_px = _bs(spot, sell_k, tte_next, avg_iv_d, "CE")
            net_deb = (buy_px - sell_px) * lot_size
            max_prf = (sell_k - buy_k - (buy_px - sell_px)) * lot_size
            max_los = net_deb
            be      = buy_k + (buy_px - sell_px)
            primary = {
                "name":     "Bull Call Spread",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY",  "strike":buy_k,  "opt":"CE", "px":buy_px,  "qty":1},
                    {"action":"SELL", "strike":sell_k, "opt":"CE", "px":sell_px, "qty":1},
                ],
                "max_profit": max_prf, "max_loss": max_los,
                "breakeven":  round(be, 0),
                "reasoning":  (
                    f"COMPRESSING IV + BULLISH zones at 3:15 PM. "
                    f"Buy ATM CE ₹{buy_k:,.0f}, sell resistance CE ₹{sell_k:,.0f}. "
                    f"Target: ₹{sell_k:,.0f} | IV compression reduces premium decay."
                ),
            }
            # Hedge: Bull Put Spread below support — collect credit if market dips
            h_sell_k = nearest_s(ns, strikes) if ns < atm else nearest_s(atm - interval*2, strikes)
            h_buy_k  = nearest_s(h_sell_k - interval*2, strikes)
            h_sell_px = _bs(spot, h_sell_k, tte_next, avg_iv_d, "PE")
            h_buy_px  = _bs(spot, h_buy_k,  tte_next, avg_iv_d, "PE")
            h_credit  = (h_sell_px - h_buy_px) * lot_size
            hedge = {
                "name":     "Bull Put Spread (Hedge)",
                "type":     "CREDIT",
                "legs": [
                    {"action":"SELL", "strike":h_sell_k, "opt":"PE", "px":h_sell_px, "qty":1},
                    {"action":"BUY",  "strike":h_buy_k,  "opt":"PE", "px":h_buy_px,  "qty":1},
                ],
                "max_profit": h_credit,
                "max_loss":   (h_sell_k - h_buy_k - h_sell_px + h_buy_px) * lot_size,
                "breakeven":  round(h_sell_k - (h_sell_px - h_buy_px), 0),
                "reasoning":  (
                    f"Hedge: If market falls below VANNA support ₹{h_sell_k:,.0f}, "
                    f"this credit spread collects ₹{h_credit:,.0f}/lot. "
                    f"Protects primary debit cost on inversion. "
                    f"Net hedge cost: ZERO (credit received)."
                ),
            }

        elif iv_regime == "EXPANDING":
            # Long Call — EXPANDING IV increases call premium value
            buy_k  = atm
            buy_px = _bs(spot, buy_k, tte_next, avg_iv_d * 1.1, "CE")  # IV expanding → higher
            max_prf = float("inf")
            max_los = buy_px * lot_size
            be      = buy_k + buy_px
            primary = {
                "name":     "Long Call (IV Expansion Play)",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY", "strike":buy_k, "opt":"CE", "px":buy_px, "qty":1},
                ],
                "max_profit": max_prf, "max_loss": max_los,
                "breakeven":  round(be, 0),
                "reasoning":  (
                    f"EXPANDING IV + BULLISH VANNA zones. LOC at "
                    f"₹{vacuums[0]:,.0f} above spot if market breaks resistance. "
                    f"Long ATM call benefits from IV expansion + directional move."
                ),
            }
            # Hedge: Bear Put Spread — caps loss if EXPANDING IV triggers bear cascade
            h_buy_k  = atm
            h_sell_k = nearest_s(atm - interval*2, strikes)
            h_buy_px  = _bs(spot, h_buy_k,  tte_next, avg_iv_d, "PE")
            h_sell_px = _bs(spot, h_sell_k, tte_next, avg_iv_d, "PE")
            h_net_deb = (h_buy_px - h_sell_px) * lot_size
            hedge = {
                "name":     "Bear Put Spread (Hedge)",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY",  "strike":h_buy_k,  "opt":"PE", "px":h_buy_px,  "qty":1},
                    {"action":"SELL", "strike":h_sell_k, "opt":"PE", "px":h_sell_px, "qty":1},
                ],
                "max_profit": (h_buy_k - h_sell_k - h_buy_px + h_sell_px) * lot_size,
                "max_loss":   h_net_deb,
                "breakeven":  round(h_buy_k - (h_buy_px - h_sell_px), 0),
                "reasoning":  (
                    f"Hedge: EXPANDING IV can flip bearish if TRAP DOOR at "
                    f"₹{ns:,.0f} breaks. Bear put spread limits downside to "
                    f"₹{h_net_deb:,.0f}/lot while primary call rides the bull move."
                ),
            }

        else:  # FLAT
            # Bull Call Spread — conservative, FLAT IV = stable premium
            buy_k   = atm
            sell_k  = nearest_s(nr, strikes)
            buy_px  = _bs(spot, buy_k,  tte_next, avg_iv_d, "CE")
            sell_px = _bs(spot, sell_k, tte_next, avg_iv_d, "CE")
            net_deb = (buy_px - sell_px) * lot_size
            primary = {
                "name":     "Bull Call Spread (Conservative)",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY",  "strike":buy_k,  "opt":"CE", "px":buy_px,  "qty":1},
                    {"action":"SELL", "strike":sell_k, "opt":"CE", "px":sell_px, "qty":1},
                ],
                "max_profit": (sell_k - buy_k - buy_px + sell_px) * lot_size,
                "max_loss":   net_deb,
                "breakeven":  round(buy_k + buy_px - sell_px, 0),
                "reasoning":  f"FLAT IV + BULLISH zones. Conservative spread capped at resistance ₹{sell_k:,.0f}.",
            }
            # Hedge: OTM Put — simple downside protection
            h_k  = nearest_s(atm - interval*2, strikes)
            h_px = _bs(spot, h_k, tte_next, avg_iv_d, "PE")
            hedge = {
                "name":     "OTM Put (Downside Hedge)",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY", "strike":h_k, "opt":"PE", "px":h_px, "qty":1},
                ],
                "max_profit": (h_k - h_px) * lot_size,
                "max_loss":   h_px * lot_size,
                "breakeven":  round(h_k - h_px, 0),
                "reasoning":  f"Simple OTM put hedge at ₹{h_k:,.0f}. Activates if bull thesis fails.",
            }

    elif direction == "BEARISH":
        if iv_regime == "EXPANDING":
            # Bear Call Spread — CREDIT, best in EXPANDING IV (backtest: 83.8% accuracy)
            sell_k = nearest_s(nr, strikes)
            buy_k  = nearest_s(sell_k + interval*2, strikes)
            sell_px = _bs(spot, sell_k, tte_next, avg_iv_d * 1.1, "CE")
            buy_px  = _bs(spot, buy_k,  tte_next, avg_iv_d * 1.1, "CE")
            credit  = (sell_px - buy_px) * lot_size
            primary = {
                "name":     "Bear Call Spread",
                "type":     "CREDIT",
                "legs": [
                    {"action":"SELL", "strike":sell_k, "opt":"CE", "px":sell_px, "qty":1},
                    {"action":"BUY",  "strike":buy_k,  "opt":"CE", "px":buy_px,  "qty":1},
                ],
                "max_profit": credit,
                "max_loss":   (buy_k - sell_k - sell_px + buy_px) * lot_size,
                "breakeven":  round(sell_k + sell_px - buy_px, 0),
                "reasoning":  (
                    f"EXPANDING IV + BEARISH flip zones at 3:15 PM → 83.8% accuracy (midday backtest). "
                    f"Sell resistance CE ₹{sell_k:,.0f}, buy protection CE ₹{buy_k:,.0f}. "
                    f"Credit ₹{credit:,.0f}/lot keeps profit if market stays below ₹{sell_k:,.0f}."
                ),
            }
            # Hedge: Bull Put Spread — if bull squeeze fires from VANNA vacuum
            h_k_s = nearest_s(atm - interval, strikes)
            h_k_b = nearest_s(atm - interval*3, strikes)
            h_sell_px = _bs(spot, h_k_s, tte_next, avg_iv_d, "PE")
            h_buy_px  = _bs(spot, h_k_b, tte_next, avg_iv_d, "PE")
            h_credit  = (h_sell_px - h_buy_px) * lot_size
            hedge = {
                "name":     "Bull Put Spread (Hedge)",
                "type":     "CREDIT",
                "legs": [
                    {"action":"SELL", "strike":h_k_s, "opt":"PE", "px":h_sell_px, "qty":1},
                    {"action":"BUY",  "strike":h_k_b, "opt":"PE", "px":h_buy_px,  "qty":1},
                ],
                "max_profit": h_credit,
                "max_loss":   (h_k_s - h_k_b - h_sell_px + h_buy_px) * lot_size,
                "breakeven":  round(h_k_s - (h_sell_px - h_buy_px), 0),
                "reasoning":  (
                    f"Hedge: VANNA support at ₹{ns:,.0f} could trigger bull squeeze. "
                    f"Put spread below spot collects credit ₹{h_credit:,.0f}/lot. "
                    f"If market reverses bullishly, this hedge reduces net loss."
                ),
            }

        elif iv_regime == "COMPRESSING":
            # Bear Put Spread — debit, COMPRESSING IV = cheaper puts
            buy_k  = atm
            sell_k = nearest_s(ns, strikes)
            buy_px  = _bs(spot, buy_k,  tte_next, avg_iv_d, "PE")
            sell_px = _bs(spot, sell_k, tte_next, avg_iv_d, "PE")
            net_deb = (buy_px - sell_px) * lot_size
            primary = {
                "name":     "Bear Put Spread",
                "type":     "DEBIT",
                "legs": [
                    {"action":"BUY",  "strike":buy_k,  "opt":"PE", "px":buy_px,  "qty":1},
                    {"action":"SELL", "strike":sell_k, "opt":"PE", "px":sell_px, "qty":1},
                ],
                "max_profit": (buy_k - sell_k - buy_px + sell_px) * lot_size,
                "max_loss":   net_deb,
                "breakeven":  round(buy_k - (buy_px - sell_px), 0),
                "reasoning":  (
                    f"COMPRESSING IV + BEARISH flip zones. Cheap puts (IV falling). "
                    f"Target VANNA support ₹{sell_k:,.0f}. "
                    f"Risk limited to debit ₹{net_deb:,.0f}/lot."
                ),
            }
            # Hedge: Bear Call Spread above resistance — zero cost if market rallies
            h_k_s = nearest_s(nr, strikes)
            h_k_b = nearest_s(nr + interval*2, strikes)
            h_sell_px = _bs(spot, h_k_s, tte_next, avg_iv_d, "CE")
            h_buy_px  = _bs(spot, h_k_b, tte_next, avg_iv_d, "CE")
            h_credit  = (h_sell_px - h_buy_px) * lot_size
            hedge = {
                "name":     "Bear Call Spread (Hedge)",
                "type":     "CREDIT",
                "legs": [
                    {"action":"SELL", "strike":h_k_s, "opt":"CE", "px":h_sell_px, "qty":1},
                    {"action":"BUY",  "strike":h_k_b, "opt":"CE", "px":h_buy_px,  "qty":1},
                ],
                "max_profit": h_credit,
                "max_loss":   (h_k_b - h_k_s - h_sell_px + h_buy_px) * lot_size,
                "breakeven":  round(h_k_s + h_sell_px - h_buy_px, 0),
                "reasoning":  (
                    f"Hedge: If bear thesis fails and market rallies past ₹{nr:,.0f}, "
                    f"call spread at resistance pays credit ₹{h_credit:,.0f}/lot. "
                    f"Partially offsets primary debit loss."
                ),
            }

        else:  # FLAT
            # Bear Call Spread at resistance — neutral to bearish
            sell_k = nearest_s(nr, strikes)
            buy_k  = nearest_s(nr + interval*2, strikes)
            sell_px = _bs(spot, sell_k, tte_next, avg_iv_d, "CE")
            buy_px  = _bs(spot, buy_k,  tte_next, avg_iv_d, "CE")
            credit  = (sell_px - buy_px) * lot_size
            primary = {
                "name":     "Bear Call Spread (Flat IV)",
                "type":     "CREDIT",
                "legs": [
                    {"action":"SELL", "strike":sell_k, "opt":"CE", "px":sell_px, "qty":1},
                    {"action":"BUY",  "strike":buy_k,  "opt":"CE", "px":buy_px,  "qty":1},
                ],
                "max_profit": credit,
                "max_loss":   (buy_k - sell_k - sell_px + buy_px) * lot_size,
                "breakeven":  round(sell_k + sell_px - buy_px, 0),
                "reasoning":  f"FLAT IV + BEARISH zones. Credit at resistance ₹{sell_k:,.0f}. FLAT IV = stable premium collection.",
            }
            h_k  = nearest_s(atm + interval*2, strikes)
            h_px = _bs(spot, h_k, tte_next, avg_iv_d, "CE")
            hedge = {
                "name":     "OTM Call (Bull Hedge)",
                "type":     "DEBIT",
                "legs": [{"action":"BUY", "strike":h_k, "opt":"CE", "px":h_px, "qty":1}],
                "max_profit": float("inf"),
                "max_loss":   h_px * lot_size,
                "breakeven":  round(h_k + h_px, 0),
                "reasoning":  f"OTM call at ₹{h_k:,.0f} hedges if market breaks resistance unexpectedly.",
            }

    else:  # CONFLICTED or NEUTRAL → Iron Condor
        sell_c = nearest_s(nr, strikes)
        buy_c  = nearest_s(nr + interval*2, strikes)
        sell_p = nearest_s(ns, strikes)
        buy_p  = nearest_s(ns - interval*2, strikes)
        sc_px  = _bs(spot, sell_c, tte_next, avg_iv_d, "CE")
        bc_px  = _bs(spot, buy_c,  tte_next, avg_iv_d, "CE")
        sp_px  = _bs(spot, sell_p, tte_next, avg_iv_d, "PE")
        bp_px  = _bs(spot, buy_p,  tte_next, avg_iv_d, "PE")
        credit = (sc_px - bc_px + sp_px - bp_px) * lot_size
        primary = {
            "name":     "Iron Condor (VANNA Range)",
            "type":     "CREDIT",
            "legs": [
                {"action":"SELL", "strike":sell_c, "opt":"CE", "px":sc_px, "qty":1},
                {"action":"BUY",  "strike":buy_c,  "opt":"CE", "px":bc_px, "qty":1},
                {"action":"SELL", "strike":sell_p, "opt":"PE", "px":sp_px, "qty":1},
                {"action":"BUY",  "strike":buy_p,  "opt":"PE", "px":bp_px, "qty":1},
            ],
            "max_profit": credit,
            "max_loss":   min(
                (buy_c - sell_c - sc_px + bc_px) * lot_size,
                (sell_p - buy_p - sp_px + bp_px) * lot_size,
            ),
            "breakeven":  None,
            "reasoning":  (
                f"CONFLICTED/NEUTRAL VANNA signal at 3:15 PM. "
                f"Short calls at resistance ₹{sell_c:,.0f}, short puts at support ₹{sell_p:,.0f}. "
                f"Market expected to range between VANNA walls. Credit: ₹{credit:,.0f}/lot."
            ),
        }
        # Hedge: Long Straddle 1/4 size — cheap insurance if big move fires
        atm_c_px = _bs(spot, atm, tte_next, avg_iv_d, "CE")
        atm_p_px = _bs(spot, atm, tte_next, avg_iv_d, "PE")
        hedge = {
            "name":     "ATM Straddle (Breakout Hedge — small size)",
            "type":     "DEBIT",
            "legs": [
                {"action":"BUY", "strike":atm, "opt":"CE", "px":atm_c_px, "qty":1},
                {"action":"BUY", "strike":atm, "opt":"PE", "px":atm_p_px, "qty":1},
            ],
            "max_profit": float("inf"),
            "max_loss":   (atm_c_px + atm_p_px) * lot_size,
            "breakeven":  None,
            "reasoning":  (
                f"Small-size straddle at ATM ₹{atm:,.0f} hedges if CONFLICTED signal resolves "
                f"into a large directional move. Keep 25% of normal lot size."
            ),
        }

    # Net combined P&L estimate
    p_mp = primary.get("max_profit", 0)
    p_ml = primary.get("max_loss", 0)
    h_mp = hedge.get("max_profit", 0)
    h_ml = hedge.get("max_loss", 0)

    # Net loss if both go wrong (worst case)
    net_worst = -(p_ml + h_ml) if primary["type"] == "DEBIT" else (
        primary["max_profit"] - h_ml)

    return {
        "primary":          primary,
        "hedge":            hedge,
        "direction":        direction,
        "iv_regime":        iv_regime,
        "confidence":       sig["agg_confidence"],
        "weighted_bull":    sig["weighted_bull"],
        "weighted_bear":    sig["weighted_bear"],
        "bull_zones":       sig["bull_zones"],
        "bear_zones":       sig["bear_zones"],
        "net_worst_case":   net_worst,
        "spot_at_315":      sig["spot_at_315"],
        "top_zones":        sig["top_zones"],
        "timestamp":        sig["timestamp"],
    }


def render_nextday_strategy_tab(df, df_selected, spot_price, symbol, meta,
                                 vanna_zones, iv_regime, unit_label):
    """Renders the Next-Day Strategy tab inside Strategy Hub."""

    st.markdown("### &#x1F52E; Next-Day Strategy — from 3:15 PM VANNA Reading")
    st.caption(
        "Reads All Flip Zone directional probabilities at 3:00–3:15 PM. "
        "Designs an exclusive next-day strategy aligned to IV regime + dominant direction. "
        "Includes a hedge leg to cap loss if market inverts."
    )

    if df is None or len(df) == 0:
        st.warning("&#x26A0;&#xFE0F; Please fetch data first.")
        return

    cfg      = INDEX_CONFIG.get(symbol, {"contract_size":25,"strike_interval":50})
    lot_size = cfg.get("contract_size", 25)
    tte_days = 7 if meta.get("expiry_flag","WEEK")=="WEEK" else 30
    tte_curr = tte_days / 365
    tte_next = max(1, tte_days - 1) / 365   # next day = one day less

    with st.spinner("Reading 3:15 PM VANNA flip zones..."):
        sig = compute_315pm_flip_signal(df, spot_price, tte_curr)

    # ── Status check ──────────────────────────────────────────────────────────
    if sig.get("status") != "OK":
        msg = sig.get("message", "")
        if sig["status"] == "NO_DATA":
            st.info(
                "&#x23F3; 3:00–3:15 PM window data not yet available. "
                "This tab activates after 3:00 PM. "
                + (f"\n{msg}" if msg else "")
            )
        else:
            st.warning(f"&#x26A0;&#xFE0F; Could not compute flip zones: {sig.get('status')}")
        return

    direction  = sig["agg_direction"]
    iv_reg     = sig["iv_regime"]
    conf       = sig["agg_confidence"]
    spot_315   = sig["spot_at_315"]
    ts_str     = sig["timestamp"]

    iv_color  = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_reg,"#94a3b8")
    dir_color = {"BULLISH":"#10b981","BEARISH":"#ef4444","CONFLICTED":"#f59e0b","NEUTRAL":"#94a3b8"}.get(direction,"#94a3b8")
    dir_icon  = {"BULLISH":"&#x1F7E2;","BEARISH":"&#x1F534;","CONFLICTED":"&#x26A1;","NEUTRAL":"&#x2B1C;"}.get(direction,"&#x2B1C;")

    # ── 3:15 PM Signal Banner ─────────────────────────────────────────────────
    banner = [
        '<div style="background:{}15;border:2px solid {}55;border-radius:14px;padding:16px 20px;margin-bottom:16px;">'.format(dir_color, dir_color),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:rgba(192,132,252,0.7);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:10px;">&#x23F0; 3:15 PM VANNA Flip Zone Reading — {}</div>'.format(ts_str[:16] if ts_str else ""),
        '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:stretch;">',

        # Direction
        '<div style="flex:1.5;min-width:160px;padding:12px 16px;background:{}18;border:2px solid {}66;border-radius:10px;text-align:center;">'.format(dir_color, dir_color),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:4px;">AGGREGATE DIRECTION</div>',
        '<div style="font-size:1.4rem;font-weight:800;color:{};font-family:Space Grotesk,sans-serif;">{} {}</div>'.format(dir_color, dir_icon, direction),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:{};margin-top:4px;">Confidence: {:.1f}%</div>'.format(dir_color, conf),
        '</div>',

        # IV Regime
        '<div style="flex:1;min-width:120px;padding:12px 16px;background:{}18;border:1px solid {}55;border-radius:10px;text-align:center;">'.format(iv_color, iv_color),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:4px;">IV REGIME</div>',
        '<div style="font-size:1.1rem;font-weight:700;color:{};font-family:Space Grotesk,sans-serif;">{}</div>'.format(iv_color, iv_reg),
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#64748b;margin-top:2px;">Skew: {:+.1f}%</div>'.format(sig["iv_skew"]),
        '</div>',

        # Zone vote
        '<div style="flex:1;min-width:110px;padding:12px 16px;background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:10px;text-align:center;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:4px;">ZONE VOTES</div>',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.88rem;">',
        '<span style="color:#10b981;font-weight:700;">&#x1F7E2; {} Bull</span><br>'.format(sig["bull_zones"]),
        '<span style="color:#ef4444;font-weight:700;">&#x1F534; {} Bear</span><br>'.format(sig["bear_zones"]),
        '<span style="color:#f59e0b;">&#x26A1; {} Conflict</span>'.format(sig["conf_zones"]),
        '</div></div>',

        # Probability bars
        '<div style="flex:1.2;min-width:130px;padding:12px 16px;background:rgba(15,23,42,0.6);border:1px solid rgba(148,163,184,0.15);border-radius:10px;">',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#94a3b8;margin-bottom:8px;">WEIGHTED PROBABILITY</div>',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;margin-bottom:4px;">',
        '&#x1F7E2; Bull: <b style="color:#10b981;">{:.1f}%</b>'.format(sig["weighted_bull"]),
        '</div>',
        '<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:5px;margin-bottom:6px;">',
        '<div style="background:#10b981;width:{:.0f}%;height:5px;border-radius:3px;"></div>'.format(min(sig["weighted_bull"],100)),
        '</div>',
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.68rem;margin-bottom:4px;">',
        '&#x1F534; Bear: <b style="color:#ef4444;">{:.1f}%</b>'.format(sig["weighted_bear"]),
        '</div>',
        '<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:5px;">',
        '<div style="background:#ef4444;width:{:.0f}%;height:5px;border-radius:3px;"></div>'.format(min(sig["weighted_bear"],100)),
        '</div></div>',

        '</div></div>',
    ]
    st.markdown("".join(banner), unsafe_allow_html=True)

    # ── Top flip zones table ───────────────────────────────────────────────────
    with st.expander("&#x1F4CB; Top Flip Zones at 3:15 PM", expanded=False):
        top_z = sig.get("top_zones", [])
        if top_z:
            import pandas as _pd3
            tz_df = _pd3.DataFrame(top_z)[[
                "strike","role","direction","bull_score","bear_score","final_score","signal","iv_regime"
            ]].copy()
            tz_df.columns = ["Strike","Role","Direction","Bull%","Bear%","Score","Signal","IV"]
            tz_df["Strike"] = tz_df["Strike"].apply(lambda x: "₹{:,.0f}".format(x))
            tz_df["Bull%"]  = tz_df["Bull%"].round(1)
            tz_df["Bear%"]  = tz_df["Bear%"].round(1)
            tz_df["Score"]  = tz_df["Score"].round(1)

            def _zone_style(row):
                d = row["Direction"]
                if d == "BULLISH":    return ["background-color:rgba(16,185,129,0.15)"]*len(row)
                if d == "BEARISH":    return ["background-color:rgba(239,68,68,0.15)"]*len(row)
                if d == "CONFLICTED": return ["background-color:rgba(245,158,11,0.12)"]*len(row)
                return [""]*len(row)
            st.dataframe(tz_df.style.apply(_zone_style, axis=1), use_container_width=True, hide_index=True)

    # ── Design strategy ───────────────────────────────────────────────────────
    with st.spinner("Designing next-day strategy..."):
        strat = design_nextday_strategy(sig, lot_size, tte_next, symbol)

    primary = strat["primary"]
    hedge   = strat["hedge"]

    def _render_strat_card(s, is_primary=True):
        label = "&#x1F3AF; PRIMARY STRATEGY" if is_primary else "&#x1F6E1;&#xFE0F; HEDGE STRATEGY"
        stype = s["type"]
        tc    = "#ef4444" if stype == "DEBIT" else "#10b981"
        mp    = s["max_profit"]
        ml    = s["max_loss"]
        be    = s["breakeven"]
        mp_s  = "&#x20B9;{:,.0f}".format(mp) if isinstance(mp, (int,float)) and mp < 1e7 else "Unlimited"
        ml_s  = "&#x20B9;{:,.0f}".format(ml) if isinstance(ml, (int,float)) and ml < 1e7 else "Unlimited"
        be_s  = "&#x20B9;{:,.0f}".format(be) if isinstance(be, (int,float)) else "N/A"
        border_col = dir_color if is_primary else "#94a3b8"
        bg_col     = dir_color if is_primary else "#94a3b8"

        parts = [
            '<div style="background:{}10;border:{}solid {}55;border-radius:12px;padding:16px 18px;margin-bottom:12px;">'.format(
                bg_col, "2px " if is_primary else "1px ", border_col),
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:{};text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">{}</div>'.format(border_col, label),
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;">',
            '<span style="font-family:Space Grotesk,sans-serif;font-size:{}rem;font-weight:800;color:#e2e8f0;">{}</span>'.format("1.2" if is_primary else "1.0", s["name"]),
            '<span style="padding:3px 12px;background:{}25;border:1px solid {}55;border-radius:12px;font-family:JetBrains Mono,monospace;font-size:0.68rem;color:{};">{}</span>'.format(tc,tc,tc,stype),
            '</div>',
            # Legs
            '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">',
        ]
        for leg in s["legs"]:
            lc = "#10b981" if leg["action"]=="BUY" else "#ef4444"
            qty_str = " ×{}".format(leg["qty"]) if leg["qty"] > 1 else ""
            parts.append(
                '<div style="padding:5px 14px;background:{}20;border:1px solid {}55;border-radius:20px;'
                'font-family:JetBrains Mono,monospace;font-size:0.72rem;color:{};">'
                '{} &#x20B9;{:,.0f} {} @ &#x20B9;{:.1f}{}</div>'.format(
                    lc,lc,lc, leg["action"], leg["strike"], leg["opt"], leg["px"], qty_str)
            )
        parts.append('</div>')
        # Metrics
        parts += [
            '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">',
            '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.25);border-radius:6px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Max Profit/Lot</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.90rem;font-weight:700;color:#10b981;">{}</div>'.format(mp_s),
            '</div>',
            '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(239,68,68,0.10);border:1px solid rgba(239,68,68,0.25);border-radius:6px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Max Loss/Lot</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.90rem;font-weight:700;color:#ef4444;">{}</div>'.format(ml_s),
            '</div>',
            '<div style="flex:1;min-width:100px;padding:7px 10px;background:rgba(251,191,36,0.10);border:1px solid rgba(251,191,36,0.25);border-radius:6px;text-align:center;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">Breakeven</div>',
            '<div style="font-family:Space Grotesk,sans-serif;font-size:0.90rem;font-weight:700;color:#fbbf24;">{}</div>'.format(be_s),
            '</div>',
            '</div>',
            # Reasoning
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;color:#94a3b8;'
            'padding:8px 12px;background:rgba(0,0,0,0.2);border-radius:6px;line-height:1.65;">{}</div>'.format(s["reasoning"]),
            '</div>',
        ]
        st.markdown("".join(parts), unsafe_allow_html=True)

    _render_strat_card(primary, is_primary=True)
    _render_strat_card(hedge,   is_primary=False)

    # ── Combined net P&L summary ───────────────────────────────────────────────
    p_ml = primary.get("max_loss", 0)
    h_mp = hedge.get("max_profit", 0)
    if isinstance(p_ml, (int,float)) and isinstance(h_mp, (int,float)) and p_ml < 1e7 and h_mp < 1e7:
        net_loss_hedged = p_ml - h_mp
        net_parts = [
            '<div style="background:rgba(124,58,237,0.10);border:1px solid rgba(124,58,237,0.3);'
            'border-radius:10px;padding:12px 16px;margin-top:4px;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#c4b5fd;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.08em;">&#x26A1; Net Risk Summary (Primary + Hedge)</div>',
            '<div style="display:flex;gap:10px;flex-wrap:wrap;">',
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.78rem;color:#e2e8f0;">',
            'Primary max loss: <b style="color:#ef4444;">&#x20B9;{:,.0f}</b> &nbsp;'.format(p_ml),
            '&#x2212; Hedge offsets: <b style="color:#10b981;">&#x20B9;{:,.0f}</b> &nbsp;'.format(h_mp),
            '= Net worst case: <b style="color:{};">&#x20B9;{:,.0f}</b>'.format(
                "#10b981" if net_loss_hedged <= 0 else "#f59e0b", abs(net_loss_hedged)),
            '</div></div></div>',
        ]
        st.markdown("".join(net_parts), unsafe_allow_html=True)

    st.markdown(
        '<div style="margin-top:10px;font-family:JetBrains Mono,monospace;font-size:0.62rem;color:#475569;">'
        '&#9888;&#xFE0F; Strategy designed using BSM pricing from 5-min bar close. '
        'Premiums are indicative — actual next-day prices will differ. '
        'For educational purposes only. Not financial advice.'
        '</div>',
        unsafe_allow_html=True,
    )

# ============================================================================
# TRAILING 15-MIN + OVERALL FLIP ZONE PROBABILITY BOXES
# ============================================================================

def compute_trailing_flip_signal(df: pd.DataFrame, spot_price: float,
                                  tte: float, minutes: int = 15) -> dict:
    """
    Compute average flip zone bull/bear probability over the last N minutes.
    Uses net_vanna (structural VANNA, same as transition chart).
    Returns averaged scores and dominant direction for the window.
    """
    if df is None or len(df) == 0:
        return {"status": "NO_DATA"}
    try:
        last_ts = df["timestamp"].max()
        cutoff  = last_ts - pd.Timedelta(minutes=minutes)
        window  = df[df["timestamp"] >= cutoff].copy()
    except Exception:
        return {"status": "NO_DATA"}

    if len(window) == 0:
        return {"status": "NO_DATA", "message": f"No data in last {minutes} minutes"}

    iv_full = compute_iv_trend(df)
    timestamps = sorted(window["timestamp"].unique())

    bull_scores, bear_scores, directions = [], [], []
    iv_regimes, iv_skews = [], []

    for ts in timestamps:
        df_ts = window[window["timestamp"] == ts].copy()
        if df_ts.empty:
            continue
        spot_ts = float(df_ts["spot_price"].iloc[0])
        iv_slice = iv_full[iv_full["timestamp"] <= ts]
        if iv_slice.empty:
            iv_slice = iv_full.iloc[:1]

        zones = identify_vanna_flip_zones(df_ts, spot_ts)
        if not zones:
            continue
        pz_df = compute_breakout_probability(zones, iv_slice, spot_ts, tte, df_ts)
        if pz_df.empty:
            continue

        top = pz_df.iloc[0]
        bull_scores.append(float(top["bull_score"]))
        bear_scores.append(float(top["bear_score"]))
        directions.append(str(top["direction"]))
        iv_regimes.append(str(top["iv_regime"]))
        iv_skews.append(float(top.get("iv_skew", 0.0)))

    if not bull_scores:
        return {"status": "NO_ZONES"}

    avg_bull  = sum(bull_scores) / len(bull_scores)
    avg_bear  = sum(bear_scores) / len(bear_scores)
    diff      = avg_bull - avg_bear

    # Dominant direction by vote
    from collections import Counter
    dir_vote = Counter(directions).most_common(1)[0][0]
    iv_vote  = Counter(iv_regimes).most_common(1)[0][0]
    avg_skew = sum(iv_skews) / len(iv_skews)

    dir_threshold = 15.0
    if   diff >  dir_threshold: agg_dir = "BULLISH"
    elif diff < -dir_threshold: agg_dir = "BEARISH"
    elif max(avg_bull, avg_bear) >= 25: agg_dir = "CONFLICTED"
    else:                       agg_dir = "NEUTRAL"

    return {
        "status":     "OK",
        "avg_bull":   round(avg_bull, 1),
        "avg_bear":   round(avg_bear, 1),
        "direction":  agg_dir,
        "dir_vote":   dir_vote,
        "iv_regime":  iv_vote,
        "avg_skew":   round(avg_skew, 2),
        "n_bars":     len(bull_scores),
        "minutes":    minutes,
        "bull_trend": "RISING" if len(bull_scores) >= 2 and bull_scores[-1] > bull_scores[0] else "FALLING",
        "bear_trend": "RISING" if len(bear_scores) >= 2 and bear_scores[-1] > bear_scores[0] else "FALLING",
    }


def compute_overall_flip_signal(df: pd.DataFrame, spot_price: float,
                                 tte: float) -> dict:
    """
    Compute overall session flip zone signal combining:
    - net_vanna (structural VANNA from total OI)
    - net_gex   (total GEX from OI × gamma)
    - net_oi    (raw call_oi - put_oi tilt)
    Aggregates across all timestamps, returns a multi-signal consensus.
    """
    if df is None or len(df) == 0:
        return {"status": "NO_DATA"}

    iv_full = compute_iv_trend(df)
    timestamps = sorted(df["timestamp"].unique())

    # Per-timestamp signals
    vanna_bulls, vanna_bears = [], []
    gex_bias_vals   = []   # net_gex sum: positive = bull
    oi_bias_vals    = []   # call_oi - put_oi: positive = bull
    iv_regimes      = []

    for ts in timestamps:
        df_ts = df[df["timestamp"] == ts].copy()
        if df_ts.empty:
            continue
        spot_ts = float(df_ts["spot_price"].iloc[0])
        iv_slice = iv_full[iv_full["timestamp"] <= ts]
        if iv_slice.empty:
            iv_slice = iv_full.iloc[:1]

        # VANNA flip signal
        zones = identify_vanna_flip_zones(df_ts, spot_ts)
        if zones:
            pz_df = compute_breakout_probability(zones, iv_slice, spot_ts, tte, df_ts)
            if not pz_df.empty:
                top = pz_df.iloc[0]
                vanna_bulls.append(float(top["bull_score"]))
                vanna_bears.append(float(top["bear_score"]))
                iv_regimes.append(str(top["iv_regime"]))

        # GEX bias: sum of net_gex across all strikes
        if "net_gex" in df_ts.columns:
            gex_sum = float(df_ts["net_gex"].sum())
            gex_bias_vals.append(gex_sum)

        # OI bias: call_oi - put_oi
        if "call_oi" in df_ts.columns and "put_oi" in df_ts.columns:
            oi_bias = float((df_ts["call_oi"] - df_ts["put_oi"]).sum())
            oi_bias_vals.append(oi_bias)

    if not vanna_bulls:
        return {"status": "NO_ZONES"}

    avg_vanna_bull = sum(vanna_bulls) / len(vanna_bulls)
    avg_vanna_bear = sum(vanna_bears) / len(vanna_bears)

    # GEX signal: positive = net long gamma = bull-absorbing = mild bull
    avg_gex_bias = sum(gex_bias_vals) / len(gex_bias_vals) if gex_bias_vals else 0.0
    gex_direction = "BULLISH" if avg_gex_bias > 0 else "BEARISH"
    gex_strength  = min(abs(avg_gex_bias) * 10, 100)   # scale to 0-100

    # OI bias: call skew = bull tilt, put skew = bear tilt
    avg_oi_bias = sum(oi_bias_vals) / len(oi_bias_vals) if oi_bias_vals else 0.0
    oi_direction = "BULLISH" if avg_oi_bias > 0 else "BEARISH"

    # Dominant IV regime
    from collections import Counter
    iv_vote = Counter(iv_regimes).most_common(1)[0][0] if iv_regimes else "FLAT"

    # Weighted consensus: VANNA 50%, GEX 30%, OI 20%
    vanna_score = avg_vanna_bull - avg_vanna_bear   # positive = bull
    gex_score   = gex_strength if gex_direction == "BULLISH" else -gex_strength
    oi_score    = 20 if oi_direction == "BULLISH" else -20

    composite = 0.50 * vanna_score + 0.30 * gex_score + 0.20 * oi_score

    if   composite >  15: overall_dir = "BULLISH"
    elif composite < -15: overall_dir = "BEARISH"
    elif abs(composite) >= 5: overall_dir = "CONFLICTED"
    else:                 overall_dir = "NEUTRAL"

    return {
        "status":          "OK",
        "avg_vanna_bull":  round(avg_vanna_bull, 1),
        "avg_vanna_bear":  round(avg_vanna_bear, 1),
        "gex_direction":   gex_direction,
        "gex_strength":    round(gex_strength, 1),
        "oi_direction":    oi_direction,
        "avg_gex_bias":    round(avg_gex_bias, 4),
        "avg_oi_bias":     round(avg_oi_bias, 0),
        "composite":       round(composite, 1),
        "overall_dir":     overall_dir,
        "iv_regime":       iv_vote,
        "n_bars":          len(vanna_bulls),
    }


def render_trailing_probability_box(sig: dict, label: str) -> None:
    """Render a compact bull/bear probability box for trailing or overall signal."""
    if not sig or sig.get("status") != "OK":
        st.markdown(
            f'<div style="background:rgba(15,23,42,0.7);border:1px solid rgba(148,163,184,0.2);'
            f'border-radius:10px;padding:10px 14px;margin-bottom:8px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#64748b;">'
            f'&#x23F3; {label}: data not yet available</span></div>',
            unsafe_allow_html=True,
        )
        return

    direction = sig.get("direction") or sig.get("overall_dir", "NEUTRAL")
    dir_color = {"BULLISH":"#10b981","BEARISH":"#ef4444",
                 "CONFLICTED":"#f59e0b","NEUTRAL":"#94a3b8"}.get(direction, "#94a3b8")
    dir_icon  = {"BULLISH":"&#x1F7E2;","BEARISH":"&#x1F534;",
                 "CONFLICTED":"&#x26A1;","NEUTRAL":"&#x2B1C;"}.get(direction, "&#x2B1C;")
    iv_regime = sig.get("iv_regime", "FLAT")
    iv_color  = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")
    n_bars    = sig.get("n_bars", 0)

    # Determine which scores to display
    if "avg_bull" in sig:
        bull_v = sig["avg_bull"]
        bear_v = sig["avg_bear"]
        bull_trend = "&#x2191;" if sig.get("bull_trend") == "RISING" else "&#x2193;"
        bear_trend = "&#x2191;" if sig.get("bear_trend") == "RISING" else "&#x2193;"
        extra_rows = [
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.67rem;color:#64748b;">'
            f'VANNA flip zone average over last {sig["minutes"]} min &nbsp;|&nbsp; {n_bars} bars</div>'
        ]
    else:
        bull_v = sig["avg_vanna_bull"]
        bear_v = sig["avg_vanna_bear"]
        bull_trend = bear_trend = ""
        gex_d = sig.get("gex_direction","?")
        oi_d  = sig.get("oi_direction","?")
        gex_c = "#10b981" if gex_d == "BULLISH" else "#ef4444"
        oi_c  = "#10b981" if oi_d  == "BULLISH" else "#ef4444"
        extra_rows = [
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.67rem;color:#64748b;margin-top:4px;">'
            f'GEX bias: <b style="color:{gex_c};">{gex_d}</b> &nbsp;|&nbsp; '
            f'OI tilt: <b style="color:{oi_c};">{oi_d}</b> &nbsp;|&nbsp; '
            f'Composite: <b style="color:{dir_color};">{sig.get("composite",0):+.1f}</b> &nbsp;|&nbsp; '
            f'{n_bars} bars</div>'
        ]

    parts = [
        f'<div style="background:{dir_color}10;border:1.5px solid {dir_color}55;'
        f'border-radius:10px;padding:12px 16px;margin-bottom:8px;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:rgba(192,132,252,0.7);'
        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">{label}</div>',
        f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">',
        # Bull
        f'<div style="flex:1;min-width:100px;padding:8px 12px;background:rgba(16,185,129,0.10);'
        f'border:1px solid rgba(16,185,129,0.3);border-radius:8px;text-align:center;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">&#x1F7E2; BULL AVG</div>',
        f'<div style="font-size:1.4rem;font-weight:800;color:#10b981;font-family:Space Grotesk,sans-serif;">'
        f'{bull_v:.0f}% {bull_trend}</div>',
        f'<div style="background:rgba(16,185,129,0.2);border-radius:3px;height:4px;margin-top:4px;">'
        f'<div style="background:#10b981;width:{min(bull_v,100):.0f}%;height:4px;border-radius:3px;"></div></div>',
        f'</div>',
        # Direction
        f'<div style="flex:1.3;min-width:130px;padding:8px 12px;background:{dir_color}18;'
        f'border:2px solid {dir_color}66;border-radius:8px;text-align:center;">',
        f'<div style="font-size:1.0rem;font-weight:800;color:{dir_color};font-family:Space Grotesk,sans-serif;">'
        f'{dir_icon} {direction}</div>',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;'
        f'color:{iv_color};margin-top:3px;">IV: <b>{iv_regime}</b></div>',
        f'</div>',
        # Bear
        f'<div style="flex:1;min-width:100px;padding:8px 12px;background:rgba(239,68,68,0.10);'
        f'border:1px solid rgba(239,68,68,0.3);border-radius:8px;text-align:center;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">&#x1F534; BEAR AVG</div>',
        f'<div style="font-size:1.4rem;font-weight:800;color:#ef4444;font-family:Space Grotesk,sans-serif;">'
        f'{bear_v:.0f}% {bear_trend}</div>',
        f'<div style="background:rgba(239,68,68,0.2);border-radius:3px;height:4px;margin-top:4px;">'
        f'<div style="background:#ef4444;width:{min(bear_v,100):.0f}%;height:4px;border-radius:3px;"></div></div>',
        f'</div>',
        f'</div>',
    ]
    parts.extend(extra_rows)
    parts.append('</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def _render_snapshot_prob_box(prob_df, iv_at_ts, spot_price, unit_label, label, accent_color):
    """
    Render a flip zone probability snapshot box for a specific timestamp.
    Shows all detected flip zones with bull/bear scores, direction, IV regime.
    label: 'Standard GEX' or 'Enhanced OI GEX'
    accent_color: hex color for the box border/header
    """
    iv_regime = "FLAT"
    iv_skew   = 0.0
    if iv_at_ts is not None and len(iv_at_ts) > 0:
        _liv = iv_at_ts.iloc[-1]
        iv_regime = str(_liv.get("iv_regime", "FLAT"))
        iv_skew   = float(_liv.get("iv_skew",   0.0))

    iv_color = {"EXPANDING":"#ef4444","COMPRESSING":"#10b981","FLAT":"#94a3b8"}.get(iv_regime,"#94a3b8")

    if prob_df is None or (hasattr(prob_df,"empty") and prob_df.empty):
        st.markdown(
            f'<div style="background:rgba(15,23,42,0.7);border:1px solid {accent_color}44;'
            f'border-radius:10px;padding:10px 16px;margin-bottom:10px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#64748b;">'
            f'No flip zones detected for {label} at this timestamp. '
            f'Try selecting more strikes (ATM±5+).</span></div>',
            unsafe_allow_html=True,
        )
        return

    # Header bar
    header_parts = [
        f'<div style="background:{accent_color}12;border:1.5px solid {accent_color}55;'
        f'border-radius:12px;padding:12px 16px;margin-bottom:10px;">',
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:6px;">',
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.65rem;'
        f'color:{accent_color};text-transform:uppercase;letter-spacing:0.08em;">'
        f'&#x1F4CD; {label} — {len(prob_df)} Flip Zone(s) at ₹{spot_price:,.0f}</span>',
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;">'
        f'IV: <b style="color:{iv_color};">{iv_regime}</b> &nbsp;|&nbsp; Skew: '
        f'<b style="color:{"#10b981" if iv_skew>0 else "#ef4444"};">{iv_skew:+.1f}%</b></span>',
        f'</div>',
    ]
    st.markdown("".join(header_parts), unsafe_allow_html=True)

    # Per-zone rows
    role_icons = {"VACUUM_ZONE":"🚀","RESISTANCE_CEILING":"🔴",
                  "TRAP_DOOR":"⚠️","SUPPORT_FLOOR":"🛡️"}
    dir_colors = {"BULLISH":"#10b981","BEARISH":"#ef4444",
                  "CONFLICTED":"#f59e0b","NEUTRAL":"#64748b"}

    for _, row in prob_df.iterrows():
        direction = str(row["direction"])
        dir_col   = dir_colors.get(direction, "#64748b")
        dir_icon  = {"BULLISH":"🟢","BEARISH":"🔴","CONFLICTED":"⚡","NEUTRAL":"⬜"}.get(direction,"⬜")
        role      = str(row["role"])
        r_icon    = role_icons.get(role, "📍")
        bull_s    = float(row["bull_score"])
        bear_s    = float(row["bear_score"])
        signal    = str(row.get("signal",""))
        strike    = float(row["strike"])
        dist_pct  = float(row.get("distance_pct", 0))
        above     = bool(row.get("above_spot", strike > spot_price))
        pos_label = "Above" if above else "Below"

        zone_parts = [
            f'<div style="display:flex;gap:8px;align-items:center;padding:7px 10px;'
            f'background:{dir_col}10;border-left:3px solid {dir_col};border-radius:0 6px 6px 0;'
            f'margin-bottom:6px;flex-wrap:wrap;">',
            # Strike + role
            f'<div style="min-width:200px;">',
            f'<span style="font-family:Space Grotesk,sans-serif;font-size:0.82rem;font-weight:700;'
            f'color:#e2e8f0;">{r_icon} ₹{strike:,.0f}</span> '
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;color:#94a3b8;">'
            f'({pos_label} spot, {dist_pct:.2f}%)</span><br>',
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.65rem;'
            f'color:#64748b;">{role.replace("_"," ")} [{iv_regime}]</span>',
            f'</div>',
            # Bull bar
            f'<div style="flex:1;min-width:80px;">',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">🟢 Bull</div>',
            f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:5px;margin:2px 0;">',
            f'<div style="background:#10b981;width:{min(bull_s,100):.0f}%;height:5px;border-radius:3px;"></div></div>',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            f'font-weight:700;color:#10b981;">{bull_s:.1f}%</div>',
            f'</div>',
            # Bear bar
            f'<div style="flex:1;min-width:80px;">',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;color:#94a3b8;">🔴 Bear</div>',
            f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:5px;margin:2px 0;">',
            f'<div style="background:#ef4444;width:{min(bear_s,100):.0f}%;height:5px;border-radius:3px;"></div></div>',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            f'font-weight:700;color:#ef4444;">{bear_s:.1f}%</div>',
            f'</div>',
            # Direction verdict
            f'<div style="min-width:120px;text-align:center;padding:4px 10px;'
            f'background:{dir_col}20;border:1px solid {dir_col}55;border-radius:20px;">',
            f'<div style="font-family:Space Grotesk,sans-serif;font-size:0.78rem;'
            f'font-weight:700;color:{dir_col};">{dir_icon} {direction}</div>',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.60rem;'
            f'color:#64748b;">{signal}</div>',
            f'</div>',
            f'</div>',
        ]
        st.markdown("".join(zone_parts), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================================
# OI-ENHANCED VANNA PROBABILITY
# Combines structural VANNA (total OI) + flow VANNA (OI change) per zone
# ============================================================================

def identify_vanna_flip_zones_oi_enhanced(
    df: pd.DataFrame,
    spot_price: float,
    scaling_factor: float = 1e9,
) -> List[Dict]:
    """
    Identifies VANNA flip zones enriched with OI flow data.

    Each zone contains:
      structural_vanna  — from total call_oi / put_oi (existing net_vanna)
      flow_vanna        — from call_oi_change / put_oi_change × vanna greek
      combined_magnitude — structural × (1 + flow_weight), clamped
      oi_confirmation   — CONFIRMING / FADING / BUILDING / NEUTRAL
      call_flow_sum     — net call OI change at zone strikes
      put_flow_sum      — net put OI change at zone strikes
      flow_direction    — BULLISH / BEARISH / NEUTRAL

    Flow VANNA formula mirrors net_vanna but uses OI change:
      flow_vanna = (call_oi_change × call_vanna_greek + put_oi_change × put_vanna_greek)
                   × spot × contract_size / scaling_factor
    Falls back to call_oi_change - put_oi_change tilt when greek columns absent.
    """
    if df is None or len(df) == 0:
        return []

    df_s = df.sort_values('strike').reset_index(drop=True).copy()

    # Ensure required columns exist
    for col in ['net_vanna', 'call_oi', 'put_oi', 'call_oi_change', 'put_oi_change']:
        if col not in df_s.columns:
            df_s[col] = 0.0

    has_greek_cols = ('call_vanna' in df_s.columns and 'put_vanna' in df_s.columns and
                      df_s['call_vanna'].abs().sum() > 0)

    # ── Compute flow_vanna per row ───────────────────────────────────────
    if has_greek_cols:
        # Exact formula: OI_change × vanna_greek (already scaled in call_vanna col)
        # call_vanna col = call_oi × cv × spot × cs / sc  →  cv = call_vanna / (call_oi × spot × cs / sc)
        # So flow_vanna = call_oi_change × cv × spot × cs / sc
        # Approximate: flow_vanna ≈ call_oi_change / call_oi × call_vanna (when call_oi > 0)
        eps = 1e-6
        call_v_greek = df_s['call_vanna'] / (df_s['call_oi'].clip(lower=eps))
        put_v_greek  = df_s['put_vanna']  / (df_s['put_oi'].clip(lower=eps))
        df_s['_flow_vanna'] = (
            df_s['call_oi_change'] * call_v_greek +
            df_s['put_oi_change']  * put_v_greek
        )
    else:
        # Fallback: use normalised OI change tilt as proxy
        max_oi = max(df_s['call_oi'].abs().max(), df_s['put_oi'].abs().max(), 1.0)
        df_s['_flow_vanna'] = (
            (df_s['call_oi_change'] - df_s['put_oi_change']) / max_oi
        )

    # ── Find structural flip zones (same logic as identify_vanna_flip_zones) ─
    zones = []
    for i in range(len(df_s) - 1):
        cur_v = float(df_s.iloc[i]['net_vanna'])
        nxt_v = float(df_s.iloc[i+1]['net_vanna'])
        cur_k = float(df_s.iloc[i]['strike'])
        nxt_k = float(df_s.iloc[i+1]['strike'])

        if not ((cur_v > 0 and nxt_v < 0) or (cur_v < 0 and nxt_v > 0)):
            continue

        # Interpolated flip level
        w         = abs(cur_v) / (abs(cur_v) + abs(nxt_v) + 1e-12)
        flip_k    = cur_k + (nxt_k - cur_k) * w
        above_spot = flip_k > spot_price
        flip_type  = 'POS_TO_NEG' if cur_v > 0 else 'NEG_TO_POS'

        # Structural magnitude (from total OI VANNA)
        struct_mag = (abs(cur_v) + abs(nxt_v)) / 2.0

        # Role (same mapping as identify_vanna_flip_zones)
        if above_spot and flip_type == 'POS_TO_NEG':
            role = 'RESISTANCE_CEILING'
            role_desc = 'Resistance ceiling — IV↑ = breakdown'
            color = '#ef4444'; icon = '🔴'
        elif above_spot and flip_type == 'NEG_TO_POS':
            role = 'VACUUM_ZONE'
            role_desc = 'Vacuum zone — IV↑ = rapid squeeze UP'
            color = '#10b981'; icon = '🚀'
        elif not above_spot and flip_type == 'POS_TO_NEG':
            role = 'TRAP_DOOR'
            role_desc = 'Trap door — IV↑ = drop accelerates'
            color = '#f59e0b'; icon = '⚠️'
        else:
            role = 'SUPPORT_FLOOR'
            role_desc = 'Support floor — IV compression holds price'
            color = '#06b6d4'; icon = '🛡️'

        # ── OI flow at the two bounding strikes ──────────────────────────
        row_cur = df_s.iloc[i]
        row_nxt = df_s.iloc[i+1]

        call_flow = float(row_cur.get('call_oi_change', 0)) + float(row_nxt.get('call_oi_change', 0))
        put_flow  = float(row_cur.get('put_oi_change',  0)) + float(row_nxt.get('put_oi_change',  0))
        net_flow  = call_flow - put_flow

        flow_vanna_cur = float(df_s.iloc[i]['_flow_vanna'])
        flow_vanna_nxt = float(df_s.iloc[i+1]['_flow_vanna'])
        flow_mag  = (abs(flow_vanna_cur) + abs(flow_vanna_nxt)) / 2.0

        # Flow direction: call adds = bullish flow, put adds = bearish flow
        if   net_flow > 0:  flow_direction = 'BULLISH'
        elif net_flow < 0:  flow_direction = 'BEARISH'
        else:               flow_direction = 'NEUTRAL'

        # ── OI Confirmation logic ─────────────────────────────────────────
        # Is the OI flow directionally aligned with what the zone predicts?
        zone_is_bullish = role in ('VACUUM_ZONE', 'SUPPORT_FLOOR')
        flow_aligned    = (zone_is_bullish and flow_direction == 'BULLISH') or                           (not zone_is_bullish and flow_direction == 'BEARISH')
        flow_opposed    = (zone_is_bullish and flow_direction == 'BEARISH') or                           (not zone_is_bullish and flow_direction == 'BULLISH')

        # BUILDING: flow magnitude > 30% of structural (new zone forming)
        is_building = flow_mag > struct_mag * 0.30 and struct_mag > 0

        if   flow_aligned and is_building:  oi_confirmation = 'CONFIRMING'
        elif flow_aligned:                  oi_confirmation = 'CONFIRMING'
        elif flow_opposed and is_building:  oi_confirmation = 'FADING'
        elif flow_opposed:                  oi_confirmation = 'FADING'
        elif is_building:                   oi_confirmation = 'BUILDING'
        else:                               oi_confirmation = 'NEUTRAL'

        # ── Combined magnitude ────────────────────────────────────────────
        # flow_weight: how much the flow amplifies/damps the structural signal
        # Range: −0.5 (heavy fading) to +0.5 (heavy confirmation)
        if struct_mag > 0:
            flow_ratio = min(flow_mag / struct_mag, 1.0)
        else:
            flow_ratio = 0.0

        if   oi_confirmation == 'CONFIRMING': flow_weight =  flow_ratio * 0.50
        elif oi_confirmation == 'FADING':     flow_weight = -flow_ratio * 0.50
        elif oi_confirmation == 'BUILDING':   flow_weight =  flow_ratio * 0.25
        else:                                 flow_weight =  0.0

        combined_mag = max(struct_mag * (1.0 + flow_weight), 1e-8)

        zones.append({
            # Standard fields (compatible with compute_breakout_probability)
            'strike'           : flip_k,
            'lower_strike'     : cur_k,
            'upper_strike'     : nxt_k,
            'flip_type'        : flip_type,
            'role'             : role,
            'role_desc'        : role_desc,
            'color'            : color,
            'icon'             : icon,
            'above_spot'       : above_spot,
            'distance_pct'     : abs(flip_k - spot_price) / spot_price * 100,
            # OI-enhanced fields
            'magnitude'        : combined_mag,         # ← replaces raw struct_mag
            'struct_magnitude' : struct_mag,
            'flow_magnitude'   : flow_mag,
            'flow_weight'      : round(flow_weight, 3),
            'combined_magnitude': combined_mag,
            'oi_confirmation'  : oi_confirmation,
            'call_flow_sum'    : round(call_flow, 0),
            'put_flow_sum'     : round(put_flow, 0),
            'net_flow'         : round(net_flow, 0),
            'flow_direction'   : flow_direction,
        })

    return sorted(zones, key=lambda z: z['distance_pct'])


def compute_oi_enhanced_probability(
    df: pd.DataFrame,
    iv_df: pd.DataFrame,
    spot_price: float,
    tte: float = 7/365,
) -> pd.DataFrame:
    """
    Full OI-enhanced VANNA breakout probability.

    Extends compute_breakout_probability() with:
      1. OI flow confirmation bonus (±15 pts) on top of skew/VANNA balance
      2. combined_magnitude (structural × flow weight) as the magnitude input
      3. Returns extra columns: oi_confirmation, call_flow_sum, put_flow_sum,
         net_flow, flow_direction, struct_magnitude, flow_weight
    """
    # Get OI-enhanced zones
    zones = identify_vanna_flip_zones_oi_enhanced(df, spot_price)
    if not zones:
        return pd.DataFrame()

    if iv_df is None or len(iv_df) == 0:
        return pd.DataFrame()

    latest_iv   = iv_df.iloc[-1]
    iv_regime   = str(latest_iv.get('iv_regime', 'FLAT'))
    iv_skew     = float(latest_iv.get('iv_skew', 0.0))

    vanna_above = sum(z['combined_magnitude'] for z in zones if z['above_spot'])
    vanna_below = sum(z['combined_magnitude'] for z in zones if not z['above_spot'])
    total_mag   = vanna_above + vanna_below or 1.0
    vanna_balance_pct = vanna_above / total_mag * 100
    skew_bias_pct     = float(np.clip(50 + iv_skew * 4, 0, 100))
    max_mag = max(z['combined_magnitude'] for z in zones) or 1.0

    rows = []
    for z in zones:
        dist_pct = z['distance_pct']
        role     = z['role']
        oi_conf  = z['oi_confirmation']

        # ── Multipliers ───────────────────────────────────────────────────
        dist_mult = float(np.exp(-dist_pct / 1.5))
        mag_mult  = min(1.0, z['combined_magnitude'] / max_mag)
        tte_mult  = min(1.0, 1.0 / (tte * 365 * 0.5 + 1))

        # ── Base IV scores (same role × regime logic as before) ───────────
        if role == 'VACUUM_ZONE':
            if iv_regime == 'EXPANDING':   bull_iv, bear_iv = 90, 10
            elif iv_regime == 'FLAT':      bull_iv, bear_iv = 35, 65
            else:                          bull_iv, bear_iv = 15, 85

        elif role == 'RESISTANCE_CEILING':
            if iv_regime == 'EXPANDING':   bull_iv, bear_iv = 10, 90
            elif iv_regime == 'FLAT':      bull_iv, bear_iv = 35, 65
            else:                          bull_iv, bear_iv = 65, 35

        elif role == 'TRAP_DOOR':
            if iv_regime == 'EXPANDING':   bull_iv, bear_iv = 5,  95
            elif iv_regime == 'FLAT':      bull_iv, bear_iv = 30, 70
            else:                          bull_iv, bear_iv = 70, 30

        else:  # SUPPORT_FLOOR
            if iv_regime == 'COMPRESSING': bull_iv, bear_iv = 90, 10
            elif iv_regime == 'FLAT':      bull_iv, bear_iv = 60, 40
            else:                          bull_iv, bear_iv = 15, 85

        # ── Skew bonus (±15 pts) ─────────────────────────────────────────
        skew_bull_bonus = float(np.clip(iv_skew * 3, -15, 15))
        skew_bear_bonus = float(np.clip(-iv_skew * 3, -15, 15))

        # ── VANNA balance bonus (±10 pts) ────────────────────────────────
        if z['above_spot']:
            vb_bull = float(np.clip((vanna_balance_pct - 50) * 0.6, -10, 10))
            vb_bear = -vb_bull
        else:
            vb_bear = float(np.clip((50 - vanna_balance_pct) * 0.6, -10, 10))
            vb_bull = -vb_bear

        # ── OI Confirmation bonus (±15 pts) — the new signal ────────────
        # CONFIRMING: flow agrees with zone direction → amplify dominant side
        # FADING:     flow opposes zone direction → penalise dominant side
        # BUILDING:   new flow forming → mild amplification
        # NEUTRAL:    no flow signal → no bonus
        zone_is_bullish = role in ('VACUUM_ZONE', 'SUPPORT_FLOOR')

        if oi_conf == 'CONFIRMING':
            oi_bull_bonus = 15.0 if zone_is_bullish else -15.0
            oi_bear_bonus = -15.0 if zone_is_bullish else 15.0
        elif oi_conf == 'FADING':
            oi_bull_bonus = -15.0 if zone_is_bullish else 15.0
            oi_bear_bonus = 15.0 if zone_is_bullish else -15.0
        elif oi_conf == 'BUILDING':
            oi_bull_bonus = 8.0 if zone_is_bullish else -8.0
            oi_bear_bonus = -8.0 if zone_is_bullish else 8.0
        else:
            oi_bull_bonus = oi_bear_bonus = 0.0

        # ── Final scores ─────────────────────────────────────────────────
        amplitude  = dist_mult * mag_mult
        bull_score = float(np.clip(
            bull_iv * amplitude + tte_mult * 5 +
            skew_bull_bonus + vb_bull + oi_bull_bonus, 0, 100))
        bear_score = float(np.clip(
            bear_iv * amplitude + tte_mult * 5 +
            skew_bear_bonus + vb_bear + oi_bear_bonus, 0, 100))

        final_score = max(bull_score, bear_score)

        # Direction — same adaptive threshold
        dir_threshold = 15 + dist_pct * 10
        diff = bull_score - bear_score
        if   diff >  dir_threshold: direction = 'BULLISH'
        elif diff < -dir_threshold: direction = 'BEARISH'
        elif final_score >= 25:     direction = 'CONFLICTED'
        else:                       direction = 'NEUTRAL'

        dir_color = {'BULLISH':'#10b981','BEARISH':'#ef4444',
                     'CONFLICTED':'#f59e0b','NEUTRAL':'#64748b'}[direction]
        dir_icon  = {'BULLISH':'🟢','BEARISH':'🔴',
                     'CONFLICTED':'⚡','NEUTRAL':'⬜'}[direction]

        if   final_score >= 70: signal = '🔥 HIGH'
        elif final_score >= 50: signal = '⚡ MOD'
        elif final_score >= 30: signal = '👁️ WATCH'
        else:                   signal = '💤 LOW'

        # OI confirmation badge
        conf_color = {'CONFIRMING':'#10b981','FADING':'#ef4444',
                      'BUILDING':'#f59e0b','NEUTRAL':'#64748b'}.get(oi_conf,'#64748b')
        conf_icon  = {'CONFIRMING':'✅','FADING':'❌','BUILDING':'🔨','NEUTRAL':'—'}.get(oi_conf,'—')

        rows.append({
            # Standard fields
            'strike'          : z['strike'],
            'role'            : role,
            'role_desc'       : z['role_desc'],
            'icon'            : z['icon'],
            'color'           : z['color'],
            'distance_pct'    : dist_pct,
            'flip_type'       : z['flip_type'],
            'above_spot'      : z['above_spot'],
            'bull_score'      : round(bull_score, 1),
            'bear_score'      : round(bear_score, 1),
            'final_score'     : round(final_score, 1),
            'direction'       : direction,
            'dir_color'       : dir_color,
            'dir_icon'        : dir_icon,
            'signal'          : signal,
            'iv_regime'       : iv_regime,
            'iv_skew'         : iv_skew,
            'vanna_balance_pct': vanna_balance_pct,
            'skew_bias_pct'   : skew_bias_pct,
            'iv_dir_bias'     : 'BULLISH' if vanna_above > vanna_below else 'BEARISH',
            # OI-enhanced extra fields
            'oi_confirmation' : oi_conf,
            'conf_color'      : conf_color,
            'conf_icon'       : conf_icon,
            'call_flow_sum'   : z['call_flow_sum'],
            'put_flow_sum'    : z['put_flow_sum'],
            'net_flow'        : z['net_flow'],
            'flow_direction'  : z['flow_direction'],
            'struct_magnitude': round(z['struct_magnitude'], 6),
            'combined_mag'    : round(z['combined_magnitude'], 6),
            'flow_weight'     : round(z['flow_weight'], 3),
            'oi_bull_bonus'   : round(oi_bull_bonus, 1),
            'oi_bear_bonus'   : round(oi_bear_bonus, 1),
        })

    return pd.DataFrame(rows).sort_values('final_score', ascending=False).reset_index(drop=True)


def render_oi_enhanced_prob_box(df_selected, iv_at_ts, spot_price, unit_label):
    """
    Render the OI-Enhanced VANNA Probability box.
    Shows per-zone breakdown with structural vs flow VANNA, OI confirmation badge,
    OI bonus applied, and final direction verdict.
    """
    iv_regime = 'FLAT'
    iv_skew   = 0.0
    if iv_at_ts is not None and len(iv_at_ts) > 0:
        _liv = iv_at_ts.iloc[-1]
        iv_regime = str(_liv.get('iv_regime', 'FLAT'))
        iv_skew   = float(_liv.get('iv_skew', 0.0))

    iv_color = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981',
                'FLAT':'#94a3b8'}.get(iv_regime,'#94a3b8')

    with st.spinner('Computing OI-enhanced VANNA probabilities...'):
        prob_df = compute_oi_enhanced_probability(df_selected, iv_at_ts, spot_price)

    accent = '#a855f7'  # violet — distinct from purple/pink used elsewhere

    if prob_df is None or (hasattr(prob_df,'empty') and prob_df.empty):
        st.markdown(
            f'<div style="background:rgba(15,23,42,0.7);border:1px solid {accent}44;'
            f'border-radius:10px;padding:10px 16px;margin-bottom:10px;">'
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.75rem;color:#64748b;">'
            f'No VANNA flip zones detected. Try wider strikes (ATM±5+).</span></div>',
            unsafe_allow_html=True,
        )
        return

    # ── Header ────────────────────────────────────────────────────────────
    top = prob_df.iloc[0]
    top_dir   = str(top['direction'])
    top_color = {'BULLISH':'#10b981','BEARISH':'#ef4444',
                 'CONFLICTED':'#f59e0b','NEUTRAL':'#64748b'}.get(top_dir,'#64748b')
    top_icon  = {'BULLISH':'🟢','BEARISH':'🔴','CONFLICTED':'⚡','NEUTRAL':'⬜'}.get(top_dir,'⬜')
    top_conf  = str(top['oi_confirmation'])
    conf_color = str(top['conf_color'])
    conf_icon  = str(top['conf_icon'])

    header = [
        f'<div style="background:{accent}10;border:1.5px solid {accent}55;'
        f'border-radius:12px;padding:14px 18px;margin-bottom:10px;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:{accent};'
        f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">'
        f'&#x1F52C; OI-Enhanced VANNA Probability &nbsp;·&nbsp; {len(prob_df)} Zone(s) &nbsp;·&nbsp; '
        f'IV: <b style="color:{iv_color};">{iv_regime}</b> &nbsp;|&nbsp; Skew: '
        f'<b style="color:{"#10b981" if iv_skew>0 else "#ef4444"};">{iv_skew:+.1f}%</b></div>',

        # Top zone summary row
        f'<div style="display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;align-items:stretch;">',

        # Bull
        f'<div style="flex:1;min-width:90px;padding:10px 12px;background:rgba(16,185,129,0.10);'
        f'border:1px solid rgba(16,185,129,0.35);border-radius:8px;text-align:center;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#94a3b8;">&#x1F7E2; TOP ZONE BULL</div>',
        f'<div style="font-size:1.5rem;font-weight:800;color:#10b981;font-family:Space Grotesk,sans-serif;">'
        f'{top["bull_score"]:.0f}%</div>',
        f'<div style="background:rgba(16,185,129,0.2);border-radius:3px;height:4px;margin-top:4px;">'
        f'<div style="background:#10b981;width:{min(top["bull_score"],100):.0f}%;height:4px;border-radius:3px;"></div></div>',
        f'</div>',

        # Direction + OI status
        f'<div style="flex:1.5;min-width:160px;padding:10px 14px;background:{top_color}15;'
        f'border:2px solid {top_color}66;border-radius:8px;text-align:center;">',
        f'<div style="font-size:1.0rem;font-weight:800;color:{top_color};font-family:Space Grotesk,sans-serif;">'
        f'{top_icon} {top_dir}</div>',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#94a3b8;margin-top:4px;">'
        f'&#x20B9;{top["strike"]:,.0f} &nbsp;|&nbsp; {top["signal"]}</div>',
        f'<div style="margin-top:5px;padding:3px 8px;background:{conf_color}25;border:1px solid {conf_color}55;'
        f'border-radius:10px;display:inline-block;">'
        f'<span style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:{conf_color};">'
        f'{conf_icon} OI: {top_conf}</span></div>',
        f'</div>',

        # Bear
        f'<div style="flex:1;min-width:90px;padding:10px 12px;background:rgba(239,68,68,0.10);'
        f'border:1px solid rgba(239,68,68,0.35);border-radius:8px;text-align:center;">',
        f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#94a3b8;">&#x1F534; TOP ZONE BEAR</div>',
        f'<div style="font-size:1.5rem;font-weight:800;color:#ef4444;font-family:Space Grotesk,sans-serif;">'
        f'{top["bear_score"]:.0f}%</div>',
        f'<div style="background:rgba(239,68,68,0.2);border-radius:3px;height:4px;margin-top:4px;">'
        f'<div style="background:#ef4444;width:{min(top["bear_score"],100):.0f}%;height:4px;border-radius:3px;"></div></div>',
        f'</div>',

        f'</div>',  # close summary row
    ]
    st.markdown(''.join(header), unsafe_allow_html=True)

    # ── Per-zone detail rows ──────────────────────────────────────────────
    role_icons = {'VACUUM_ZONE':'🚀','RESISTANCE_CEILING':'🔴',
                  'TRAP_DOOR':'⚠️','SUPPORT_FLOOR':'🛡️'}
    dir_colors = {'BULLISH':'#10b981','BEARISH':'#ef4444',
                  'CONFLICTED':'#f59e0b','NEUTRAL':'#64748b'}

    for _, row in prob_df.iterrows():
        direction = str(row['direction'])
        dir_col   = dir_colors.get(direction,'#64748b')
        dir_icon  = {'BULLISH':'🟢','BEARISH':'🔴','CONFLICTED':'⚡','NEUTRAL':'⬜'}.get(direction,'⬜')
        role      = str(row['role'])
        r_icon    = role_icons.get(role,'📍')
        oi_conf   = str(row['oi_confirmation'])
        c_col     = str(row['conf_color'])
        c_icon    = str(row['conf_icon'])
        bull_s    = float(row['bull_score'])
        bear_s    = float(row['bear_score'])
        above     = bool(row['above_spot'])
        strike    = float(row['strike'])
        dist_pct  = float(row['distance_pct'])
        net_flow  = float(row['net_flow'])
        flow_dir  = str(row['flow_direction'])
        fw        = float(row['flow_weight'])
        oi_b_b    = float(row['oi_bull_bonus'])

        flow_dir_col = '#10b981' if flow_dir == 'BULLISH' else ('#ef4444' if flow_dir == 'BEARISH' else '#64748b')
        pos_label = 'Above' if above else 'Below'

        zone_html = [
            f'<div style="border-left:3px solid {dir_col};border-radius:0 8px 8px 0;'
            f'background:{dir_col}08;padding:8px 12px;margin-bottom:8px;">',

            # Row 1: strike + role + direction
            f'<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px;">',
            f'<span style="font-family:Space Grotesk,sans-serif;font-size:0.85rem;font-weight:700;'
            f'color:#e2e8f0;">{r_icon} &#x20B9;{strike:,.0f}</span>',
            f'<span style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#94a3b8;">'
            f'({pos_label} spot, {dist_pct:.2f}%)</span>',
            f'<span style="padding:2px 8px;background:{dir_col}25;border:1px solid {dir_col}55;'
            f'border-radius:10px;font-family:JetBrains Mono,monospace;font-size:0.65rem;color:{dir_col};">'
            f'{dir_icon} {direction}</span>',
            f'<span style="padding:2px 8px;background:{c_col}22;border:1px solid {c_col}44;'
            f'border-radius:10px;font-family:JetBrains Mono,monospace;font-size:0.63rem;color:{c_col};">'
            f'{c_icon} {oi_conf}</span>',
            f'</div>',

            # Row 2: role + IV regime
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;color:#64748b;margin-bottom:6px;">'
            f'{role.replace("_"," ")} [{row["iv_regime"]}] &nbsp;|&nbsp; Signal: {row["signal"]}</div>',

            # Row 3: bull / bear bars
            f'<div style="display:flex;gap:8px;margin-bottom:6px;flex-wrap:wrap;">',
            # Bull
            f'<div style="flex:1;min-width:80px;">',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#94a3b8;">🟢 Bull</div>',
            f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;margin:2px 0;">'
            f'<div style="background:#10b981;width:{min(bull_s,100):.0f}%;height:4px;border-radius:3px;"></div></div>',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;font-weight:700;color:#10b981;">'
            f'{bull_s:.1f}%</div></div>',
            # Bear
            f'<div style="flex:1;min-width:80px;">',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.58rem;color:#94a3b8;">🔴 Bear</div>',
            f'<div style="background:rgba(255,255,255,0.06);border-radius:3px;height:4px;margin:2px 0;">'
            f'<div style="background:#ef4444;width:{min(bear_s,100):.0f}%;height:4px;border-radius:3px;"></div></div>',
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;font-weight:700;color:#ef4444;">'
            f'{bear_s:.1f}%</div></div>',
            f'</div>',

            # Row 4: OI flow detail
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.63rem;'
            f'color:#64748b;border-top:1px solid rgba(255,255,255,0.06);padding-top:5px;display:flex;gap:12px;flex-wrap:wrap;">',
            f'<span>&#x1F4C8; Call flow: <b style="color:#10b981;">{row["call_flow_sum"]:+,.0f}</b></span>',
            f'<span>&#x1F4C9; Put flow: <b style="color:#ef4444;">{row["put_flow_sum"]:+,.0f}</b></span>',
            f'<span>Net: <b style="color:{flow_dir_col};">{net_flow:+,.0f} ({flow_dir})</b></span>',
            f'<span>Flow weight: <b style="color:{"#10b981" if fw>0 else "#ef4444" if fw<0 else "#64748b"};">'
            f'{fw:+.2f}</b></span>',
            f'<span>OI bonus: <b style="color:{"#10b981" if oi_b_b>0 else "#ef4444" if oi_b_b<0 else "#64748b"};">'
            f'{oi_b_b:+.1f} pts</b></span>',
            f'</div>',

            f'</div>',  # close zone div
        ]
        st.markdown(''.join(zone_html), unsafe_allow_html=True)

    # Close the outer box
    st.markdown('</div>', unsafe_allow_html=True)

def _compute_enhanced_oi_vanna_column(df, spot_price, unit_label='B', tte=7/365):
    """Computes enhanced_oi_vanna per strike. Uses call_oi_change/put_oi_change
    weighted by vanna greek, volume, IV adjustment and distance from spot."""
    df_out = df.copy()
    df_out['enhanced_oi_vanna'] = 0.0
    for col in ['call_oi_change','put_oi_change','total_volume','call_iv','put_iv']:
        if col not in df_out.columns:
            df_out[col] = 0.0
        df_out[col] = df_out[col].fillna(0)
    bs_calc   = BlackScholesCalculator()
    total_vol = max(df_out['total_volume'].sum(), 1.0)
    sc        = 1e9 if unit_label == 'B' else 1e7
    try:
        for idx, row in df_out.iterrows():
            spot_r = float(row.get('spot_price', spot_price))
            strike = float(row['strike'])
            if spot_r <= 0 or strike <= 0: continue
            civ = row['call_iv']/100 if row['call_iv'] > 1 else float(row['call_iv'])
            piv = row['put_iv'] /100 if row['put_iv']  > 1 else float(row['put_iv'])
            civ = max(civ, 0.05); piv = max(piv, 0.05)
            cv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, civ)
            pv  = bs_calc.calculate_vanna(spot_r, strike, tte, 0.07, piv)
            vw  = 1.0 + (float(row['total_volume']) / total_vol)
            iv_adj = 1.0 + ((civ + piv) / 2 * 3)
            dw  = 1.0 / (1 + abs(strike - spot_r) / spot_r * 1.5)
            df_out.loc[idx, 'enhanced_oi_vanna'] = (
                (float(row['call_oi_change']) * cv * 2.0 * vw * iv_adj * dw * spot_r * 25) / sc +
                (float(row['put_oi_change'])  * pv * 2.0 * vw * iv_adj * dw * spot_r * 25) / sc
            )
    except Exception:
        pass
    return df_out

def main():
    # ── Auth gate — must login before anything else renders ───────────────
    if not _ensure_authenticated():
        return

    # ── Landing page gate ─────────────────────────────────────────────────
    if 'app_entered' not in st.session_state:
        st.session_state.app_entered = False
    if not st.session_state.app_entered:
        entered = show_landing()
        if entered:
            st.session_state.app_entered = True
            st.rerun()
        return   # don't render rest of app until user enters
    # ── App from here ─────────────────────────────────────────────────────


    # ════════════════════════════════════════════════════════════════════
    # HORIZONTAL NAV BAR — replaces sidebar entirely
    # Row 1: Brand | Market status | User badge | Home | Logout
    # Row 2 (expander): All configuration controls
    # ════════════════════════════════════════════════════════════════════

    # ── Row 1: top bar ───────────────────────────────────────────────────────
    current_time   = datetime.now(IST).strftime('%H:%M:%S IST')
    is_market_open = cache_manager.is_market_hours()
    market_status  = "🟢 OPEN" if is_market_open else "🔴 CLOSED"
    market_color   = "#10b981" if is_market_open else "#ef4444"
    _role_badge    = "👑 Admin" if _is_admin() else "👤 User"

    st.markdown(
        f'''<div style="display:flex;align-items:center;justify-content:space-between;
        padding:8px 18px;background:rgba(10,15,30,0.95);
        border-bottom:1.5px solid rgba(99,102,241,0.35);
        border-radius:0 0 12px 12px;margin-bottom:10px;gap:12px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:10px;">
            <span style="font-family:'Space Grotesk',sans-serif;font-size:2.1rem;
            font-weight:900;letter-spacing:-0.03em;color:#ffffff;
            line-height:1;">Hed<span style="color:#06b6d4;">GEX</span></span>
            <div style="display:flex;flex-direction:column;justify-content:center;gap:1px;">
              <span style="font-family:'Space Grotesk',sans-serif;font-size:0.58rem;
              font-weight:600;color:#818cf8;text-transform:uppercase;
              letter-spacing:0.18em;line-height:1;">by NYZTrade</span>
              <span style="font-family:JetBrains Mono,monospace;font-size:0.50rem;
              color:#334155;letter-spacing:0.08em;">GEX · VANNA · CASCADE</span>
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;
            padding:3px 10px;border-radius:12px;border:1px solid {market_color}55;
            color:{market_color};">{market_status}</span>
            <span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;
            color:#64748b;">{current_time}</span>
            <span style="font-family:JetBrains Mono,monospace;font-size:0.68rem;
            padding:3px 10px;border-radius:12px;background:rgba(99,102,241,0.12);
            border:1px solid rgba(99,102,241,0.3);color:#a5b4fc;">
            {_current_user()} · {_role_badge}</span>
          </div>
        </div>''',
        unsafe_allow_html=True,
    )

    # ── Home / Logout buttons ─────────────────────────────────────────────────
    _nb1, _nb2, _nb3, _nb4 = st.columns([8, 1, 1, 0.01])
    with _nb2:
        if st.button("🏠 Home", use_container_width=True):
            st.session_state.app_entered = False
            st.rerun()
    with _nb3:
        if st.button("🔒 Logout", use_container_width=True, type="secondary"):
            for k in ["auth_logged_in", "auth_user", "auth_role", "app_entered"]:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Configuration expander ────────────────────────────────────────────────
    with st.expander("⚙️ Configuration & Controls", expanded=not st.session_state.get('data_fetched', False)):

        # Row A: instrument type + symbol + expiry
        _ca1, _ca2, _ca3, _ca4 = st.columns([2, 2, 2, 2])
        with _ca1:
            instrument_type = st.radio("📈 Instrument", ["Index Options","Stock Options"],
                                       index=0, horizontal=True)
        with _ca2:
            if instrument_type == "Index Options":
                symbol = st.selectbox("🎯 Index", ["NIFTY","BANKNIFTY","FINNIFTY","MIDCPNIFTY","SENSEX"], index=0)
                cfg    = INDEX_CONFIG.get(symbol, INDEX_CONFIG["NIFTY"])
                exchange_label = "BSE" if symbol in BSE_FNO_SYMBOLS else "NSE"
                default_expiry_type = "Monthly" if symbol in BSE_FNO_SYMBOLS else "Weekly"
                st.markdown(f'<div style="font-size:0.70rem;color:#06b6d4;">📊 {exchange_label} · Lot:{cfg["contract_size"]} · Strike:₹{cfg["strike_interval"]}</div>',
                            unsafe_allow_html=True)
            else:
                category = st.selectbox("📂 Category", list(STOCK_CATEGORIES.keys()), index=0)
                symbol   = st.selectbox("🎯 Stock", STOCK_CATEGORIES[category], index=0)
                cfg      = STOCK_CONFIG.get(symbol, {"lot_size":500,"strike_interval":10})
                default_expiry_type = "Monthly"
                st.markdown(f'<div style="font-size:0.70rem;color:#10b981;">📈 STOCK · Lot:{cfg["lot_size"]} · Strike:₹{cfg["strike_interval"]}</div>',
                            unsafe_allow_html=True)
        with _ca3:
            if symbol in BSE_FNO_SYMBOLS:
                expiry_type = st.selectbox("📆 Expiry Type", ["Weekly","Monthly"], index=1)
            else:
                expiry_type = st.selectbox("📆 Expiry Type", ["Weekly","Monthly"],
                                           index=0 if default_expiry_type=="Weekly" else 1)
            expiry_flag = "WEEK" if expiry_type=="Weekly" else "MONTH"
        with _ca4:
            expiry_code = st.selectbox("Expiry Code", [1,2,3], index=0,
                                       format_func=lambda x:{1:"Current",2:"Next",3:"Far"}[x])

        # Row B: date + strikes + interval
        _cb1, _cb2, _cb3 = st.columns([2, 5, 1])
        with _cb1:
            target_date  = st.date_input("📅 Date", value=datetime.now(),
                                         max_value=datetime.now()).strftime('%Y-%m-%d')
            is_current_day = cache_manager.is_current_trading_day(target_date)
            if is_current_day:
                st.caption("📡 LIVE — incremental")
            else:
                st.caption("📦 HISTORICAL — cached")
        with _cb2:
            all_strikes     = ["ATM"]+[f"ATM+{i}" for i in range(1,16)]+[f"ATM-{i}" for i in range(1,16)]
            default_strikes = ["ATM"]+[f"ATM+{i}" for i in range(1,11)]+[f"ATM-{i}" for i in range(1,11)]
            strikes  = st.multiselect("⚡ Strikes", all_strikes, default=default_strikes)
        with _cb3:
            interval = st.selectbox("⏱️ Interval", ["1","5","15","60"], index=1,
                                    format_func=lambda x:f"{x}m")

        # Row C: fetch controls + cache + auto-refresh
        _cc1, _cc2, _cc3, _cc4, _cc5 = st.columns([1.5, 1.5, 1, 2, 2])
        with _cc1:
            fetch_button   = st.button("🚀 Fetch Data", use_container_width=True, type="primary")
        with _cc2:
            refresh_button = st.button("🔄 Update" if is_current_day else "🔄 Refresh",
                                       use_container_width=True)
        with _cc3:
            force_refresh  = st.checkbox("🔥 Force", value=False, help="Ignore cache")
        with _cc4:
            auto_refresh_enabled = is_current_day and is_market_open
            auto_refresh, refresh_interval = False, 60
            if auto_refresh_enabled:
                auto_refresh = st.checkbox("🔄 Auto-Refresh", value=False)
                if auto_refresh:
                    refresh_interval = st.slider("Interval (s)", 10, 300, 60, 10)
            else:
                st.caption("Auto-refresh: " + ("market closed" if not is_market_open else "historical"))
        with _cc5:
            cs = cache_manager.get_cache_stats()
            st.caption(f"📦 Cache: {cs['num_entries']} entries · {cs['total_size_mb']:.1f} MB")
            if _is_admin():
                if st.button("🗑️ Clear Cache", use_container_width=True):
                    cache_manager.clear_cache(); st.success("Cache cleared!"); st.rerun()

    # ── Session state ─────────────────────────────────────────────────────────
    # ── Session state ─────────────────────────────────────────────────────────
    if 'last_refresh_time' not in st.session_state:
        st.session_state.last_refresh_time = None

    if fetch_button or refresh_button:
        st.session_state.fetch_config = {
            'symbol': symbol, 'target_date': target_date, 'strikes': strikes,
            'interval': interval, 'expiry_code': expiry_code, 'expiry_flag': expiry_flag,
            'force_refresh': force_refresh,
        }
        st.session_state.data_fetched      = False
        st.session_state.last_refresh_time = datetime.now()

    if auto_refresh and auto_refresh_enabled:
        if st.session_state.last_refresh_time is None:
            st.session_state.last_refresh_time = datetime.now()
        elapsed   = (datetime.now() - st.session_state.last_refresh_time).total_seconds()
        remaining = max(0, int(refresh_interval - elapsed))
        if remaining > 0:
            st.sidebar.success(f"⏳ Next update in: **{remaining}s**")
        else:
            st.sidebar.warning("🔄 Updating...")
        if elapsed >= refresh_interval and hasattr(st.session_state, 'fetch_config'):
            st.session_state.fetch_config['force_refresh'] = False
            st.session_state.data_fetched = False
            st.session_state.last_refresh_time = datetime.now()
        time.sleep(1); st.rerun()

    # ── Main content ──────────────────────────────────────────────────────────
    if fetch_button or refresh_button or (hasattr(st.session_state, 'fetch_config') and st.session_state.get('data_fetched', False)):
        if hasattr(st.session_state, 'fetch_config'):
            fc = st.session_state.fetch_config
            symbol        = fc['symbol'];       target_date   = fc['target_date']
            strikes       = fc['strikes'];      interval      = fc['interval']
            expiry_code   = fc.get('expiry_code', 1)
            expiry_flag   = fc.get('expiry_flag', 'WEEK')
            force_refresh = fc.get('force_refresh', False)

        if not strikes:
            st.error("❌ Please select at least one strike"); return

        need_fetch = (not st.session_state.get('data_fetched', False) or
                      'df_data' not in st.session_state or fetch_button or refresh_button)
        if need_fetch:
            try:
                df, meta, fetch_mode = fetch_data_with_smart_cache(
                    symbol, target_date, strikes, interval, expiry_code, expiry_flag, force_refresh)
                if df is None or len(df) == 0:
                    st.error("❌ No data available for the selected date/time."); return
                st.session_state.df_data      = df
                st.session_state.meta_data    = meta
                st.session_state.fetch_mode   = fetch_mode
                st.session_state.data_fetched = True
                if not auto_refresh: st.rerun()
            except Exception as e:
                st.error(f"❌ Error: {e}"); return

        df         = st.session_state.df_data
        meta       = st.session_state.meta_data
        fetch_mode = st.session_state.get('fetch_mode', 'unknown')
        unit_label = meta.get('unit_label', 'B')

        all_timestamps = sorted(df['timestamp'].unique())
        if 'timestamp_idx' not in st.session_state:
            st.session_state.timestamp_idx = len(all_timestamps) - 1

        selected_ts_idx = st.slider("⏱️ Select Time Point", 0, len(all_timestamps)-1,
                                    min(st.session_state.timestamp_idx, len(all_timestamps)-1),
                                    format="%d")
        selected_ts   = all_timestamps[selected_ts_idx]
        # Show selected date + time clearly below the slider
        _ts_date = selected_ts.strftime("%d %b %Y")  # e.g. 13 Apr 2026
        _ts_time = selected_ts.strftime("%H:%M:%S")  # e.g. 11:35:00
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace;font-size:0.72rem;'
            f'padding:4px 10px;background:rgba(6,182,212,0.10);border:1px solid rgba(6,182,212,0.30);'
            f'border-radius:6px;color:#06b6d4;margin-top:-6px;margin-bottom:4px;'
            f'display:inline-block;">&#x1F4C5; {_ts_date} &nbsp; &#x23F0; {_ts_time} IST</div>',
            unsafe_allow_html=True,
        )
        df_selected   = df[df['timestamp'] == selected_ts].copy()
        spot_price    = df_selected['spot_price'].iloc[0] if len(df_selected) > 0 else 0

        # ── FUTURES / SPOT TOGGLE ────────────────────────────────────────────
        _is_index_sym  = symbol in DHAN_INDEX_SECURITY_IDS
        _fut_cache_key = f"fut_ltp_{symbol}"
        _fut_ts_key    = f"fut_ltp_ts_{symbol}"
        _man_key       = f"fut_manual_{symbol}"   # manual override key

        if _is_index_sym:
            # Try live fetch — cache 15 s so we don't hammer the API every render
            _now_ts = time.time()
            if (_fut_cache_key not in st.session_state or
                    _now_ts - st.session_state.get(_fut_ts_key, 0) > 15):
                _fetched = fetch_futures_ltp(symbol)
                if _fetched > 0:
                    st.session_state[_fut_cache_key] = _fetched
                    st.session_state[_man_key]       = _fetched   # seed manual input
                st.session_state[_fut_ts_key] = _now_ts
            _live_futures = float(st.session_state.get(_fut_cache_key, 0.0))
            _live_ok      = _live_futures > 0
        else:
            _live_futures = 0.0
            _live_ok      = False

        # ── Layout: toggle | basis panel ─────────────────────────────────────
        _ref_col1, _ref_col2 = st.columns([2, 3])

        with _ref_col1:
            if _is_index_sym:
                # Toggle is ALWAYS shown for index symbols
                _price_mode = st.radio(
                    "📐 Reference price for GEX",
                    ["Spot", "Futures"],
                    horizontal=True,
                    key="price_mode_toggle",
                    help=(
                        "Spot: all GEX calculations anchored to the index cash price "
                        "(standard, correct for settlement).\n\n"
                        "Futures: ATM strike and all GEX/gamma maths anchored to the "
                        "near-month futures LTP. Detects regime shift ~30 s earlier "
                        "than spot. Most useful during contango > 100 pts."
                    ),
                )

                if _price_mode == "Futures":
                    if _live_ok:
                        futures_price = _live_futures
                        st.caption(f"\u2705 Live futures LTP: \u20b9{futures_price:,.2f}")
                    else:
                        # Manual fallback — persisted in session state across re-renders
                        _default_manual = float(
                            st.session_state.get(_man_key, float(spot_price) + 60.0)
                        )
                        futures_price = float(st.number_input(
                            "\u270f\ufe0f Enter Futures LTP (manual)",
                            min_value=float(spot_price) * 0.90,
                            max_value=float(spot_price) * 1.10,
                            value=_default_manual,
                            step=0.5,
                            format="%.2f",
                            key=f"fut_manual_input_{symbol}",
                            help=(
                                "Live fetch unavailable (market closed or API limit). "
                                "Enter the near-month futures LTP from your broker terminal."
                            ),
                        ))
                        st.session_state[_man_key] = futures_price
                        st.caption("\U0001f4dd Manual entry — live fetch unavailable")
                else:
                    futures_price = 0.0
            else:
                _price_mode   = "Spot"
                futures_price = 0.0
                st.caption("\U0001f4d0 Spot reference (stocks only)")

        with _ref_col2:
            if _is_index_sym and _price_mode == "Futures" and futures_price > 0:
                _basis     = futures_price - spot_price
                _basis_pct = (_basis / spot_price * 100) if spot_price else 0
                _basis_col = (
                    "#ef4444" if abs(_basis) > 300 else
                    "#f59e0b" if abs(_basis) > 150 else
                    "#10b981"
                )
                _warn = " \u26a0\ufe0f EXTREME" if abs(_basis) > 300 else " \u26a0\ufe0f HIGH" if abs(_basis) > 150 else ""
                st.markdown(
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;'
                    f'background:rgba(15,23,42,0.6);border:1px solid {_basis_col}44;'
                    f'border-radius:6px;padding:6px 12px;line-height:1.9;">'
                    f'Spot &nbsp;<b style="color:#06b6d4;">\u20b9{spot_price:,.2f}</b>'
                    f'&nbsp;&nbsp;|&nbsp;&nbsp;'
                    f'Futures <b style="color:#a78bfa;">\u20b9{futures_price:,.2f}</b>'
                    f'<br>'
                    f'Basis <b style="color:{_basis_col};">{_basis:+.1f} pts '
                    f'({_basis_pct:+.2f}%){_warn}</b>'
                    f'&nbsp;&nbsp;|&nbsp;&nbsp;'
                    f'\U0001f534 GEX anchored to Futures'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            elif _is_index_sym:
                st.markdown(
                    f'<div style="font-family:JetBrains Mono,monospace;font-size:0.75rem;'
                    f'background:rgba(15,23,42,0.4);border:1px solid #1e293b;'
                    f'border-radius:6px;padding:6px 12px;color:#64748b;line-height:1.9;">'
                    f'Reference: <b style="color:#06b6d4;">Spot \u20b9{spot_price:,.2f}</b>'
                    f'&nbsp;&nbsp;|&nbsp;&nbsp;'
                    f'Select <b style="color:#a78bfa;">Futures</b> above to use basis-adjusted GEX'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── reference_price: single variable consumed by every chart/calc ────
        # Spot mode    → reference_price == spot_price  (unchanged behaviour)
        # Futures mode → reference_price == futures_price (ATM anchor shifts)
        reference_price = (
            futures_price
            if (_price_mode == "Futures" and futures_price > 0)
            else spot_price
        )
        _ref_label = "Futures" if reference_price != spot_price else "Spot"

        mode_cfg = {'cached':('📦 CACHED','#10b981'), 'incremental':(f"📡 INCREMENTAL (+{meta.get('new_records',0)} new)",'#06b6d4'),
                    'full_fetch':('🚀 FULL FETCH','#8b5cf6')}
        mode_badge, mode_color = mode_cfg.get(fetch_mode, ('❓ UNKNOWN','#64748b'))
        inst_badge = (f'<span class="index-badge">📊 INDEX</span>' if meta.get('instrument_type') == 'INDEX'
                      else f'<span class="stock-badge">📈 STOCK</span>')
        st.markdown(f"""
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
            {inst_badge}
            <span style="padding:6px 12px;background:{mode_color}20;border:1px solid {mode_color}40;border-radius:8px;
                  color:{mode_color};font-family:'JetBrains Mono',monospace;font-size:0.8rem;">{mode_badge}</span>
            <span style="color:#94a3b8;font-family:'JetBrains Mono',monospace;font-size:0.85rem;">
                {meta.get('symbol',symbol)} | {selected_ts.strftime('%H:%M:%S IST')} | Ref({_ref_label}): ₹{reference_price:,.2f} | Spot: ₹{spot_price:,.2f} | Records: {meta.get('total_records',0)}
            </span>
        </div>
        """, unsafe_allow_html=True)

        net_gex    = df_selected['net_gex'].sum()
        net_dex    = df_selected['net_dex'].sum()
        net_vanna  = df_selected['net_vanna'].sum()
        total_vol  = df_selected['total_volume'].sum() if 'total_volume' in df_selected.columns else 0
        flip_zones = identify_gamma_flip_zones(df_selected, reference_price)

        c1,c2,c3,c4,c5,c6 = st.columns(6)
        for col, label, val, sub, clr in [
            (c1,'NET GEX',    f'{net_gex:.4f}{unit_label}',  '🟢 Bullish' if net_gex>0 else '🔴 Bearish',   'positive' if net_gex>0 else 'negative'),
            (c2,'NET DEX',    f'{net_dex:.4f}{unit_label}',  '📈 Long' if net_dex>0 else '📉 Short',         'positive' if net_dex>0 else 'negative'),
            (c3,'NET VANNA',  f'{net_vanna:.4f}{unit_label}','Vol Sensitivity',                               'positive' if net_vanna>0 else 'negative'),
            (c4,'SPOT PRICE', f'₹{spot_price:,.2f}',         meta.get('symbol',symbol),                      'neutral'),
            (c5,'TOTAL VOL',  f'{total_vol:,.0f}',           '📊 Contracts',                                 'neutral'),
            (c6,'FLIP ZONES', str(len(flip_zones)),           'Gamma Crossovers',                             'neutral'),
        ]:
            with col:
                st.markdown(f'<div class="metric-card {clr}"><div class="metric-label">{label}</div>'
                            f'<div class="metric-value {clr}">{val}</div>'
                            f'<div class="metric-delta">{sub}</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        tabs = st.tabs([
            "🎯 Standard GEX",
            "🚀 Enhanced GEX Overlay",
            "🚀 Enhanced OI GEX",
            "🌊 Standard VANNA",
            "🌊 VANNA + ⚡ Flip Breakout",
            "🌊 Enhanced OI VANNA",
            "🎯 Strategy Hub (Beta)",
        ])

        # ── Pre-compute cascade for Strategy tab ────────────────────────────────
        _cfg_strategy  = INDEX_CONFIG.get(symbol, {}).get('contract_size', 25)
        _strat_vanna   = identify_vanna_flip_zones(df_selected, reference_price)
        _strat_iv_df   = compute_iv_trend(df)
        _strat_iv_raw  = _strat_iv_df.iloc[-1] if len(_strat_iv_df) > 0 else None
        _strat_iv_reg  = str(_strat_iv_raw['iv_regime']) if _strat_iv_raw is not None and 'iv_regime' in _strat_iv_raw.index else 'FLAT'
        _strat_cascade = compute_gex_cascade(df_selected, reference_price, unit_label, _cfg_strategy,
                            'net_gex', vanna_zones=_strat_vanna, iv_regime=_strat_iv_reg, symbol=symbol)
        _strat_bear_pts = float(_strat_cascade[(_strat_cascade['cascade_direction']=='BEAR') & (_strat_cascade['gex_raw']<0)]['pts_impact'].sum()) if not _strat_cascade.empty else 0.0
        _strat_bull_pts = float(_strat_cascade[(_strat_cascade['cascade_direction']=='BULL') & (_strat_cascade['gex_raw']<0)]['pts_impact'].sum()) if not _strat_cascade.empty else 0.0

        # ── TAB 0: Standard GEX ───────────────────────────────────────────────
        with tabs[0]:
            st.markdown("### 🎯 Standard Gamma Exposure (GEX)")
            st.plotly_chart(create_separate_gex_chart(df_selected, reference_price, unit_label), use_container_width=True)
            c1,c2,c3 = st.columns(3)
            c1.metric("Positive GEX", f"{df_selected[df_selected['net_gex']>0]['net_gex'].sum():.4f}{unit_label}")
            c2.metric("Negative GEX", f"{df_selected[df_selected['net_gex']<0]['net_gex'].sum():.4f}{unit_label}")
            c3.metric("Total Volume",  f"{df_selected.get('total_volume', pd.Series([0])).sum():,.0f}" if 'total_volume' in df_selected.columns else "N/A")

        # ── TAB 1: Enhanced GEX Overlay ───────────────────────────────────────
        with tabs[1]:
            st.markdown("### 🚀 Enhanced GEX Overlay")
            st.plotly_chart(create_enhanced_gex_overlay_chart(df_selected, reference_price, unit_label), use_container_width=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Original GEX Total", f"{df_selected['net_gex'].sum():.4f}{unit_label}")
            c4.metric("Total Volume", f"{df_selected['total_volume'].sum():,.0f}" if 'total_volume' in df_selected.columns else "N/A")

        # ── TAB 2: Enhanced OI GEX ────────────────────────────────────────────
        with tabs[2]:
            st.markdown("### 🚀 Enhanced OI GEX")
            st.caption("OI-weighted GEX incorporating Greeks · Volume · IV · Distance. Purple = Positive, Gold = Negative.")
            _cfg_cs = INDEX_CONFIG.get(symbol, {}).get('contract_size', 25)
            if 'enhanced_oi_gex' not in df_selected.columns or df_selected['enhanced_oi_gex'].abs().sum() == 0:
                df_selected = compute_enhanced_oi_gex_column(df_selected, reference_price, unit_label)
            enh_gex_fig = create_enhanced_oi_gex_only_chart(df_selected, reference_price, unit_label)
            st.plotly_chart(enh_gex_fig, use_container_width=True)
            g1, g2, g3 = st.columns(3)
            if 'enhanced_oi_gex' in df_selected.columns:
                pos_sum = df_selected['enhanced_oi_gex'].clip(lower=0).sum()
                neg_sum = df_selected['enhanced_oi_gex'].clip(upper=0).sum()
                net_sum = df_selected['enhanced_oi_gex'].sum()
                g1.metric("🟣 Positive OI GEX", f"{pos_sum:.4f}{unit_label}")
                g2.metric("🟡 Negative OI GEX", f"{neg_sum:.4f}{unit_label}")
                g3.metric("⚡ Net Enhanced GEX", f"{net_sum:.4f}{unit_label}")
            st.markdown("---")

            _INST_PARAMS = {
                'NIFTY':     {'pts': 0.010, 'cap': 150},
                'BANKNIFTY': {'pts': 0.033, 'cap': 300},
                'FINNIFTY':  {'pts': 0.050, 'cap': 150},
                'MIDCPNIFTY':{'pts': 0.050, 'cap':  75},
                'SENSEX':    {'pts': 0.025, 'cap': 500},
            }
            if unit_label == 'Cr':
                pts_per_unit = 0.100; strike_cap_pts = 20
            else:
                _ip = _INST_PARAMS.get(symbol, _INST_PARAMS['NIFTY'])
                pts_per_unit   = _ip['pts']
                strike_cap_pts = _ip['cap']
            gex_per_100pts = 100 / pts_per_unit
            sc_val = 1e9 if unit_label == 'B' else 1e7
            gamma_atm = 0.00012
            st.markdown("#### ⚡ GEX ↔ Price Move Calculator")
            calc_c1, calc_c2, calc_c3 = st.columns(3)
            calc_c1.metric(f"GEX needed for 100-pt move", f"{gex_per_100pts:,.0f}{unit_label}",
                help=f"Calibrated for {symbol}: {gex_per_100pts:,.0f}{unit_label} of GEX release = 100pt dealer cascade")
            calc_c2.metric(f"Points per 1{unit_label} GEX", f"{pts_per_unit:.4f} pts",
                help=f"Each 1{unit_label} of GEX released → {pts_per_unit:.4f} pts on {symbol}")
            calc_c3.metric(f"Single-Strike Cap", f"{strike_cap_pts} pts",
                help=f"Max pts contribution per strike for {symbol}")

            st.markdown("---")
            _vanna_zones_cascade = identify_vanna_flip_zones(df_selected, reference_price)
            _iv_df_cascade = compute_iv_trend(df)
            _iv_raw_cascade = _iv_df_cascade.iloc[-1] if len(_iv_df_cascade) > 0 else None
            _iv_regime_cascade = str(_iv_raw_cascade['iv_regime']) if _iv_raw_cascade is not None and 'iv_regime' in _iv_raw_cascade.index else 'FLAT'
            _iv_skew_cascade   = float(_iv_raw_cascade['iv_skew'])  if _iv_raw_cascade is not None and 'iv_skew'   in _iv_raw_cascade.index else 0.0
            _floors   = [z for z in _vanna_zones_cascade if z['role']=='SUPPORT_FLOOR']
            _traps    = [z for z in _vanna_zones_cascade if z['role']=='TRAP_DOOR']
            _vacuums  = [z for z in _vanna_zones_cascade if z['role']=='VACUUM_ZONE']
            _ceilings = [z for z in _vanna_zones_cascade if z['role']=='RESISTANCE_CEILING']
            _iv_color = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(_iv_regime_cascade,'#94a3b8')

            vanna_ctx_parts = [
                '<div style="background:rgba(6,182,212,0.08);border:1px solid rgba(6,182,212,0.3);padding:10px 14px;border-radius:6px;font-size:0.82rem;line-height:1.9;">',
                '<b>🌊 VANNA Zone Context (integrated into cascade below)</b><br>',
                f'🛡️ Support Floors: <b>{len(_floors)}</b> ',
                ('— ' + ' · '.join([f"₹{z['strike']:,.0f}" for z in _floors[:3]])) if _floors else '— None detected',
                '<br>⚠️ Trap Doors: <b>' + str(len(_traps)) + '</b> ',
                ('— ' + ' · '.join([f"₹{z['strike']:,.0f}" for z in _traps[:3]])) if _traps else '— None detected',
                '<br>🚀 Vacuum Zones: <b>' + str(len(_vacuums)) + '</b> ',
                ('— ' + ' · '.join([f"₹{z['strike']:,.0f}" for z in _vacuums[:3]])) if _vacuums else '— None detected',
                '<br>🔴 Resistance Ceilings: <b>' + str(len(_ceilings)) + '</b> ',
                ('— ' + ' · '.join([f"₹{z['strike']:,.0f}" for z in _ceilings[:3]])) if _ceilings else '— None detected',
                f'<br>IV Regime: <b style="color:{_iv_color};">{_iv_regime_cascade}</b> | Skew: {_iv_skew_cascade:+.1f}%',
                '</div>',
            ]
            st.markdown("".join(vanna_ctx_parts), unsafe_allow_html=True)

        with tabs[3]:
            st.markdown("###  Standard VANNA Exposure")
            st.plotly_chart(create_standard_vanna_chart(
                df_selected, reference_price, unit_label,
                iv_regime=_strat_iv_reg
            ), use_container_width=True)
            c1,c2,c3 = st.columns(3)
            c1.metric("Call VANNA", f"{df_selected['call_vanna'].sum():.4f}{unit_label}")
            c2.metric("Put VANNA",  f"{df_selected['put_vanna'].sum():.4f}{unit_label}")
            c3.metric("Net VANNA",  f"{df_selected['net_vanna'].sum():.4f}{unit_label}")

            st.markdown("---")

            # ── Cascade Mathematics (moved from Enhanced OI GEX tab) ──────────
            _vanna_zones_cas3   = identify_vanna_flip_zones(df_selected, reference_price)
            _iv_df_cas3         = compute_iv_trend(df)
            _iv_raw_cas3        = _iv_df_cas3.iloc[-1] if len(_iv_df_cas3) > 0 else None
            _iv_regime_cas3     = str(_iv_raw_cas3['iv_regime']) if _iv_raw_cas3 is not None and 'iv_regime' in _iv_raw_cas3.index else 'FLAT'
            _cfg_cs3            = INDEX_CONFIG.get(symbol, {}).get('contract_size', 25)
            _INST_PARAMS3 = {
                'NIFTY':     {'pts': 0.010, 'cap': 150},
                'BANKNIFTY': {'pts': 0.033, 'cap': 300},
                'FINNIFTY':  {'pts': 0.050, 'cap': 150},
                'MIDCPNIFTY':{'pts': 0.050, 'cap':  75},
                'SENSEX':    {'pts': 0.025, 'cap': 500},
            }
            if unit_label == 'Cr':
                _gex_per_100pts3 = 100 / 0.100
            else:
                _ip3 = _INST_PARAMS3.get(symbol, _INST_PARAMS3['NIFTY'])
                _gex_per_100pts3 = 100 / _ip3['pts']

            with st.expander("Cascade Mathematics - Standard GEX (reference) + Enhanced OI GEX (primary signal)", expanded=True):
                _cascade_info3 = ("<div style='background:rgba(15,23,42,0.8);border-left:4px solid #8b5cf6;"
                    "padding:12px 16px;border-radius:6px;margin-bottom:12px;font-size:0.85rem;line-height:1.7;'>"
                    "<b>How Cascade Math Works</b><br>"
                    "When price breaks a strike, dealers holding short gamma <b>must hedge by selling futures (bear) or buying futures (bull)</b>.<br>"
                    "Each strike GEX releases dealer pressure - cascades into the next strike - chain reaction.<br>"
                    "Left = Standard GEX (total dealer exposure - context/reference) | "
                    "<b>Right = Enhanced OI GEX (OI change x Greeks x Vol x IV - PRIMARY signal)</b><br>"
                    "<b>Use the RIGHT column (Enhanced OI GEX) as your primary cascade reference</b></div>")
                st.markdown(_cascade_info3, unsafe_allow_html=True)

                cas3_col1, cas3_col2 = st.columns(2)

                def _render_cascade_col3(cascade_df, label):
                    if cascade_df.empty:
                        st.info(f"{label} data not available."); return
                    disp_cols = ['strike','gex_raw_disp','pts_raw','vanna_adj_pct','pts_impact','cumulative_pts','role']
                    rename_map = {'strike':'Strike','gex_raw_disp':'GEX','pts_raw':'Raw Pts',
                                  'vanna_adj_pct':'VANNA Adj','pts_impact':'Adj Pts',
                                  'cumulative_pts':'Cum. Pts','role':'Effect'}
                    for direction in ['BEAR', 'BULL']:
                        sub = cascade_df[cascade_df['cascade_direction']==direction].head(10)
                        spot_label = 'Below Spot' if direction == 'BEAR' else 'Above Spot'
                        dir_label  = 'Bear' if direction == 'BEAR' else 'Bull'
                        st.markdown(f"**{dir_label} Cascade ({spot_label})**")
                        accel = sub[sub['gex_raw'] < 0]
                        brake = sub[sub['gex_raw'] >= 0]
                        accel_pts = accel['pts_impact'].sum()
                        brake_pts = brake['pts_impact'].sum()
                        m1, m2 = st.columns(2)
                        m1.metric("Cascade Fuel (Neg GEX)", f"~{accel_pts:.0f} pts",
                            delta=('Accelerating' if accel_pts > 50 else 'Low fuel'),
                            delta_color="inverse" if direction == 'BEAR' else "normal")
                        m2.metric("Absorption (Pos GEX)", f"~{brake_pts:.0f} pts",
                            delta="Absorbing move" if brake_pts > accel_pts else "Weak absorption",
                            delta_color="normal" if direction == 'BEAR' else "inverse")
                        net_pts   = max(0, accel_pts - brake_pts * 0.5)
                        net_color = "#ef4444" if direction == 'BEAR' else "#10b981"
                        st.markdown(
                            f'<div style="background:rgba(15,23,42,0.7);border-left:3px solid {net_color};'
                            f'padding:6px 12px;border-radius:4px;font-size:0.82rem;margin-bottom:6px;">'
                            f'<b>Estimated Net Realised: ~{net_pts:.0f} pts</b> (fuel - 50% absorption)</div>',
                            unsafe_allow_html=True)
                        sub_sorted = pd.concat([accel, brake]).reset_index(drop=True)
                        sub_sorted['Type'] = sub_sorted['gex_raw'].apply(lambda x: 'Fuel' if x < 0 else 'Brake')
                        disp = [c for c in disp_cols + ['Type'] if c in sub_sorted.columns]
                        st.dataframe(sub_sorted[disp].rename(columns={**rename_map,'Type':'Type'}),
                                     use_container_width=True, height=280)

                with cas3_col1:
                    st.markdown("##### Standard GEX Cascade")
                    st.caption("Total dealer gamma exposure. Use as reference/context only.")
                    orig_c3 = compute_gex_cascade(df_selected, reference_price, unit_label, _cfg_cs3,
                        gex_col='net_gex', vanna_zones=_vanna_zones_cas3,
                        iv_regime=_iv_regime_cas3, symbol=symbol)
                    _render_cascade_col3(orig_c3, "Standard GEX")

                with cas3_col2:
                    st.markdown("##### Enhanced OI GEX Cascade (Purple/Gold)")
                    if 'enhanced_oi_gex' in df_selected.columns:
                        enh_c3 = compute_gex_cascade(df_selected, reference_price, unit_label, _cfg_cs3,
                            gex_col='enhanced_oi_gex', vanna_zones=_vanna_zones_cas3,
                            iv_regime=_iv_regime_cas3, symbol=symbol)
                        _render_cascade_col3(enh_c3, "Enhanced OI GEX")
                    else:
                        st.info("Fetch data first to compute Enhanced OI GEX cascade.")

                st.markdown("---")
                st.markdown("##### Combined Cascade Summary")
                s1, s2, s3, s4 = st.columns(4)
                try:
                    _oc3 = compute_gex_cascade(df_selected, reference_price, unit_label, _cfg_cs3, 'net_gex',
                        vanna_zones=_vanna_zones_cas3, iv_regime=_iv_regime_cas3, symbol=symbol)
                    _ec3 = compute_gex_cascade(df_selected, reference_price, unit_label, _cfg_cs3, 'enhanced_oi_gex',
                        vanna_zones=_vanna_zones_cas3, iv_regime=_iv_regime_cas3, symbol=symbol) if 'enhanced_oi_gex' in df_selected.columns else pd.DataFrame()
                    ob3 = _oc3[(_oc3['cascade_direction']=='BEAR') & (_oc3['gex_raw']<0)]['pts_impact'].sum() if not _oc3.empty else 0
                    ou3 = _oc3[(_oc3['cascade_direction']=='BULL') & (_oc3['gex_raw']<0)]['pts_impact'].sum() if not _oc3.empty else 0
                    eb3 = _ec3[(_ec3['cascade_direction']=='BEAR') & (_ec3['gex_raw']<0)]['pts_impact'].sum() if not _ec3.empty else 0
                    eu3 = _ec3[(_ec3['cascade_direction']=='BULL') & (_ec3['gex_raw']<0)]['pts_impact'].sum() if not _ec3.empty else 0
                    s1.metric("Std GEX Bear",  f"~{ob3:.0f} pts")
                    s2.metric("Std GEX Bull",  f"~{ou3:.0f} pts")
                    s3.metric("Enh Bear",      f"~{eb3:.0f} pts")
                    s4.metric("Enh Bull",      f"~{eu3:.0f} pts")
                    _bear3 = eb3; _bull3 = eu3
                    _conf3 = abs(_bear3 - _bull3)
                    if _bear3 > _bull3:   _bias3 = "BEAR DEALER FLOW";    _bc3 = '#ef4444'; _bn3 = f"Bear: ~{_bear3:.0f} vs Bull: ~{_bull3:.0f} pts"
                    elif _bull3 > _bear3: _bias3 = "BULL DEALER FLOW";    _bc3 = '#10b981'; _bn3 = f"Bull: ~{_bull3:.0f} vs Bear: ~{_bear3:.0f} pts"
                    else:                 _bias3 = "NEUTRAL DEALER FLOW"; _bc3 = '#94a3b8'; _bn3 = "Balanced"
                    st.markdown(
                        f'<div style="background:rgba(15,23,42,0.9);border:1px solid {_bc3};'
                        f'padding:12px 16px;border-radius:8px;text-align:center;margin-top:8px;">'
                        f'<span style="font-size:1.1rem;font-weight:700;color:{_bc3};">{_bias3}</span><br>'
                        f'<span style="font-size:0.85rem;color:#e2e8f0;margin-top:4px;display:block;">{_bn3}</span>'
                        f'<span style="font-size:0.78rem;color:#94a3b8;">Asymmetry: {_conf3:.0f} pts | GEX/100pts: {_gex_per_100pts3:,.0f}{unit_label}</span>'
                        f'</div>', unsafe_allow_html=True)
                except Exception as _ce3:
                    st.warning(f"Cascade summary error: {_ce3}")

        #  TAB 4: Enhanced VANNA + Flip Breakout 
        with tabs[4]:
            st.markdown("###  Enhanced VANNA Overlay + [ZAP] VANNA Flip Breakout Probability")
            st.markdown("""<div class="spike-legend">
            🔴 <b style="color:#ef4444">Resistance Ceiling</b> = POS→NEG flip above spot — IV↑ forces dealers to SELL delta<br>
            🚀 <b style="color:#10b981">LOC (Line of Control)</b> = NEG→POS flip above spot — IV↑ forces dealers to BUY delta<br>
            ⚠️ <b style="color:#f59e0b">Trap Door</b> = POS→NEG flip below spot — IV↑ below = drop accelerates<br>
            🛡️ <b style="color:#06b6d4">Support Floor</b> = NEG→POS flip below spot — IV compression holds price
            </div>""", unsafe_allow_html=True)

            tte_days = 7 if meta.get('expiry_flag','WEEK') == 'WEEK' else 30
            tte_val  = tte_days / 365
            iv_df_full = compute_iv_trend(df)
            if 'timestamp' in iv_df_full.columns and len(iv_df_full) > 0:
                iv_at_ts = iv_df_full[iv_df_full['timestamp'] <= selected_ts]
                if iv_at_ts.empty: iv_at_ts = iv_df_full.iloc[:1]
            else:
                iv_at_ts = iv_df_full

            vf_zones  = identify_vanna_flip_zones(df_selected, reference_price)
            bias_data = compute_session_bias(vf_zones, iv_at_ts, df_selected, reference_price)
            prob_df   = compute_breakout_probability(vf_zones, iv_at_ts, reference_price, tte_val, df_selected)

            _raw_iv = iv_at_ts.iloc[-1]
            latest_iv = {
                'iv_regime': str(_raw_iv['iv_regime'])  if 'iv_regime' in _raw_iv.index else 'N/A',
                'iv_skew'  : float(_raw_iv['iv_skew'])  if 'iv_skew'   in _raw_iv.index else 0.0,
                'call_iv'  : float(_raw_iv['call_iv'])  if 'call_iv'   in _raw_iv.index else 0.0,
                'put_iv'   : float(_raw_iv['put_iv'])   if 'put_iv'    in _raw_iv.index else 0.0,
            }

            enh_fig, _, _ = create_enhanced_vanna_overlay_chart(
                df_selected, reference_price, unit_label, df_full=df, tte=tte_val, iv_df_override=iv_at_ts)
            st.plotly_chart(enh_fig, use_container_width=True)

            with st.expander("⚡ Volume Spike × VANNA Coincidence", expanded=True):
                _spike_z = st.slider("Spike sensitivity (Z-threshold)", 1.5, 4.0, 2.0, 0.1,
                    key="vanna_spike_z", help="Lower = more spikes.")
                _sp_fig, _sp_df = create_vanna_spike_panel(df, unit_label, z_threshold=_spike_z)
                st.plotly_chart(_sp_fig, use_container_width=True)
                _sp_events = _sp_df[_sp_df['vol_spike']][[
                    'timestamp','spike_type','spike_strength','gex_confirmation','vol_z_score']].rename(columns={
                    'timestamp':'Time','spike_type':'Type','spike_strength':'Strength',
                    'gex_confirmation':'GEX Confirmation','vol_z_score':'Z-Score'})
                if not _sp_events.empty:
                    _sp_events['Time'] = _sp_events['Time'].dt.strftime('%H:%M')
                    _sp_events['Z-Score'] = _sp_events['Z-Score'].round(2)
                    st.dataframe(_sp_events, use_container_width=True, hide_index=True)

            st.markdown("#### 📊 Flip Zone Probability Transition — Full Session")
            transition_fig = create_bias_transition_chart(df, reference_price, selected_ts, tte_val)
            st.plotly_chart(transition_fig, use_container_width=True)

            # ── MATRIX-BASED PROBABILITY SCORING (3:05→3:20 IV Transition) ───
            # Based on 592 closing sessions, Apr 2021–Apr 2026 (826K bars)
            # Each cell = empirically measured open→11am win rate + Sharpe
            _IV_TRANSITION_MATRIX = {
                ('EXPANDING',   'EXPANDING'):   {'bull':41,'bear':59,'trade':'PUT',  'sharpe':5.23,'consist':'3/4','avg_pts':-31.4,'gap_up':57.1,'label':'Sustained vol expansion — dealers over-hedged long vol'},
                ('EXPANDING',   'FLAT'):        {'bull':49,'bear':51,'trade':'PUT',  'sharpe':3.32,'consist':'3/4','avg_pts':-21.3,'gap_up':47.3,'label':'Vol spike fading — incomplete resolution'},
                ('EXPANDING',   'COMPRESSING'): {'bull':56,'bear':44,'trade':'CALL', 'sharpe':3.29,'consist':'3/4','avg_pts':14.9, 'gap_up':63.9,'label':'Vol absorbed at close — shorts forced to cover'},
                ('FLAT',        'EXPANDING'):   {'bull':47,'bear':53,'trade':'PUT',  'sharpe':0.91,'consist':'3/4','avg_pts':-4.3,  'gap_up':60.4,'label':'Late vol spike — ambiguous, weak signal'},
                ('FLAT',        'FLAT'):        {'bull':54,'bear':46,'trade':'SKIP', 'sharpe':0.87,'consist':'2/4','avg_pts':-4.5,  'gap_up':60.4,'label':'No institutional conviction at close — skip'},
                ('FLAT',        'COMPRESSING'): {'bull':58,'bear':42,'trade':'CALL', 'sharpe':2.15,'consist':'3/4','avg_pts':8.7,   'gap_up':73.1,'label':'Steady compression — highest gap-up rate (73%)'},
                ('COMPRESSING', 'EXPANDING'):   {'bull':50,'bear':50,'trade':'PUT',  'sharpe':1.65,'consist':'3/4','avg_pts':-9.7,  'gap_up':57.7,'label':'Compression reversed — late vol surge'},
                ('COMPRESSING', 'FLAT'):        {'bull':59,'bear':41,'trade':'CALL', 'sharpe':4.04,'consist':'4/4','avg_pts':18.7,  'gap_up':51.0,'label':'Full absorption + stabilisation — 4/4 yrs consistent'},
                ('COMPRESSING', 'COMPRESSING'): {'bull':56,'bear':44,'trade':'CALL', 'sharpe':0.02,'consist':'3/4','avg_pts':0.1,   'gap_up':52.2,'label':'Sustained compression — use as background filter only'},
            }

            # ── Support Floor Override (rare, highest conviction) ─────────────
            _has_support_floor = any(z['role'] == 'SUPPORT_FLOOR' for z in vf_zones)
            _has_trap_door     = any(z['role'] == 'TRAP_DOOR'     for z in vf_zones)

            # ── Get current and previous IV regime ────────────────────────────
            _iv_df_m   = compute_iv_trend(df)
            _curr_iv_m = str(_iv_df_m.iloc[-1]['iv_regime']) if len(_iv_df_m) > 0 and 'iv_regime' in _iv_df_m.columns else 'FLAT'
            _prev_iv_m = str(_iv_df_m.iloc[-2]['iv_regime']) if len(_iv_df_m) > 1 and 'iv_regime' in _iv_df_m.columns else _curr_iv_m
            _avg_iv_m  = float(_iv_df_m.iloc[-1]['avg_iv']) if len(_iv_df_m) > 0 and 'avg_iv' in _iv_df_m.columns else 20.0

            _matrix_key = (_prev_iv_m, _curr_iv_m)
            _mx = _IV_TRANSITION_MATRIX.get(_matrix_key,
                {'bull':50,'bear':50,'trade':'SKIP','sharpe':0.0,'consist':'?','avg_pts':0.0,'gap_up':50.0,'label':'Transition not in matrix'})

            # Support Floor override
            _sf_override = False
            if _has_support_floor:
                if _curr_iv_m == 'COMPRESSING':
                    _mx = {**_mx, 'bull':84,'bear':16,'trade':'CALL','sharpe':96.5,'consist':'4/4','label':'SUPPORT FLOOR + IV COMPRESSING (13–15h) — highest Sharpe CALL (84.6% WR, Sharpe 96.5)'}
                    _sf_override = True
                elif _curr_iv_m == 'EXPANDING':
                    _mx = {**_mx, 'bull':35,'bear':65,'trade':'PUT','sharpe':3.80,'consist':'4/4','label':'SUPPORT FLOOR BREAKING (IV expanding) — floor collapses, BUY PUT (65.4% bear WR)'}
                    _sf_override = True

            # Trap Door override
            _td_override = False
            if _has_trap_door and _curr_iv_m == 'EXPANDING':
                _mx = {**_mx, 'bull':5,'bear':95,'trade':'PUT','sharpe':3.50,'consist':'4/4','label':'TRAP DOOR + IV EXPANDING — strongest structural bear signal'}
                _td_override = True

            # ── Determine colors and labels ───────────────────────────────────
            _trade_m   = _mx['trade']
            _bull_m    = _mx['bull']
            _bear_m    = _mx['bear']
            _sharpe_m  = _mx['sharpe']
            _consist_m = _mx['consist']
            _avgpts_m  = _mx['avg_pts']
            _gapup_m   = _mx['gap_up']
            _label_m   = _mx['label']

            _tc = {'CALL':'#10b981','PUT':'#ef4444','SKIP':'#94a3b8'}.get(_trade_m,'#94a3b8')
            _ti = {'CALL':'🟢','PUT':'🔴','SKIP':'⬜'}.get(_trade_m,'⬜')
            _iv_c_m = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(_curr_iv_m,'#94a3b8')
            _iv_p_c = {'EXPANDING':'#ef4444','COMPRESSING':'#10b981','FLAT':'#94a3b8'}.get(_prev_iv_m,'#94a3b8')

            st.markdown("---")

            # ── MATRIX PROBABILITY BANNER ─────────────────────────────────────
            _override_note = ""
            if _sf_override:   _override_note = "⚠️ <b>Support Floor Override Active</b> — zone mechanics override transition matrix"
            elif _td_override: _override_note = "⚠️ <b>Trap Door Override Active</b> — structural bear signal confirmed"

            _banner_html = f"""
            <div style='border:2px solid {_tc}40;border-radius:14px;padding:16px 20px;margin:10px 0;background:{_tc}08;'>
              <div style='font-size:0.72rem;color:#94a3b8;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:10px;'>
                ⚡ Matrix-Based Probability  &nbsp;|&nbsp;
                3:05 IV: <b style='color:{_iv_p_c}'>{_prev_iv_m}</b>  →  3:20 IV: <b style='color:{_iv_c_m}'>{_curr_iv_m}</b>
                &nbsp;|&nbsp; Avg IV: <b>{_avg_iv_m:.1f}%</b>
                {'&nbsp;|&nbsp; ' + _override_note if _override_note else ''}
              </div>
              <div style='display:flex;gap:12px;align-items:stretch;flex-wrap:wrap;'>
                <div style='flex:1;min-width:110px;padding:12px 14px;background:rgba(16,185,129,0.10);
                     border:1.5px solid rgba(16,185,129,0.40);border-radius:10px;text-align:center;'>
                  <div style='font-size:2.2rem;font-weight:800;color:#10b981;font-family:JetBrains Mono,monospace;'>{_bull_m}%</div>
                  <div style='font-size:0.80rem;color:#10b981;margin-top:2px;'>🟢 BULL</div>
                  <div style='background:rgba(16,185,129,0.2);border-radius:4px;height:5px;margin-top:7px;'>
                    <div style='background:#10b981;width:{_bull_m}%;height:5px;border-radius:4px;'></div></div>
                </div>
                <div style='flex:1.4;min-width:160px;padding:12px 16px;background:{_tc}14;
                     border:2px solid {_tc}55;border-radius:10px;text-align:center;'>
                  <div style='font-size:1.5rem;font-weight:800;color:{_tc};font-family:JetBrains Mono,monospace;'>{_ti} {_trade_m}</div>
                  <div style='font-size:0.75rem;color:#94a3b8;margin-top:5px;'>
                    Avg next-day open→11am: <b style='color:{_tc};'>{_avgpts_m:+.1f} pts</b>
                  </div>
                  <div style='font-size:0.70rem;color:#64748b;margin-top:4px;'>
                    Sharpe: <b>{_sharpe_m:.2f}</b> &nbsp;|&nbsp; Consistency: <b>{_consist_m} yrs</b>
                    &nbsp;|&nbsp; Gap Up: <b>{_gapup_m:.0f}%</b>
                  </div>
                </div>
                <div style='flex:1;min-width:110px;padding:12px 14px;background:rgba(239,68,68,0.10);
                     border:1.5px solid rgba(239,68,68,0.40);border-radius:10px;text-align:center;'>
                  <div style='font-size:2.2rem;font-weight:800;color:#ef4444;font-family:JetBrains Mono,monospace;'>{_bear_m}%</div>
                  <div style='font-size:0.80rem;color:#ef4444;margin-top:2px;'>🔴 BEAR</div>
                  <div style='background:rgba(239,68,68,0.2);border-radius:4px;height:5px;margin-top:7px;'>
                    <div style='background:#ef4444;width:{_bear_m}%;height:5px;border-radius:4px;'></div></div>
                </div>
              </div>
              <div style='margin-top:10px;font-size:0.78rem;color:#94a3b8;border-top:1px solid #1e2d3d;padding-top:8px;'>
                <b style='color:#cbd5e1;'>Signal logic:</b> {_label_m}
              </div>
            </div>"""
            st.markdown(_banner_html, unsafe_allow_html=True)

            # ── FULL 3×3 MATRIX REFERENCE TABLE ──────────────────────────────
            with st.expander("📊 Full 3×3 IV Transition Matrix (click to expand)", expanded=False):
                _matrix_note = (
                    "<div style='background:rgba(15,23,42,0.7);border-left:4px solid #7c3aed;"
                    "padding:10px 14px;border-radius:6px;margin-bottom:12px;font-size:0.80rem;line-height:1.7;'>"
                    "<b>How to read this matrix:</b> Row = IV regime at 3:05 PM candle. "
                    "Column = IV regime at 3:20 PM candle. "
                    "The <b>transition direction</b> (not the endpoint) is the signal. "
                    "Win% = next-day open→11am bullish sessions. "
                    "Avg pts = average NIFTY spot move open→11am. "
                    "Highlighted cell = current session. "
                    "Based on 592 sessions, Apr 2021–Apr 2026.</div>"
                )
                st.markdown(_matrix_note, unsafe_allow_html=True)
                _rows_3x3  = ['EXPANDING','FLAT','COMPRESSING']
                _cols_3x3  = ['EXPANDING','FLAT','COMPRESSING']
                _tbl_header = "| 3:05 → 3:20 | → EXPANDING | → FLAT | → COMPRESSING |"
                _tbl_sep    = "|---|---|---|---|"
                _tbl_rows   = [_tbl_header, _tbl_sep]
                for _r in _rows_3x3:
                    _row_parts = [f"**{_r}**"]
                    for _c in _cols_3x3:
                        _k = (_r, _c)
                        _d = _IV_TRANSITION_MATRIX.get(_k, {})
                        _is_curr = (_r == _prev_iv_m and _c == _curr_iv_m)
                        _tr = _d.get('trade','?')
                        _sh = _d.get('sharpe', 0.0)
                        _av = _d.get('avg_pts', 0.0)
                        _co = _d.get('consist','?')
                        _tr_icon = {'CALL':'🟢','PUT':'🔴','SKIP':'⬜'}.get(_tr,'⬜')
                        _cell = f"{_tr_icon} **{_tr}** Sh:{_sh:.2f} Avg:{_av:+.0f}pt {_co}"
                        if _is_curr:
                            _cell = f"**◀ {_cell} ◀**"
                        _row_parts.append(_cell)
                    _tbl_rows.append("| " + " | ".join(_row_parts) + " |")
                st.markdown("\n".join(_tbl_rows))

                # Ranked signals
                st.markdown("##### Ranked by Sharpe (empirical, n≥5 per cell)")
                _ranked = sorted(_IV_TRANSITION_MATRIX.items(), key=lambda x: x[1]['sharpe'], reverse=True)
                _rk_data = []
                for (_r2,_c2), _d2 in _ranked:
                    _rk_data.append({
                        'Transition': f"{_r2[:4]}→{_c2[:4]}",
                        'Trade': _d2['trade'],
                        'Sharpe': _d2['sharpe'],
                        'Avg 11am (pts)': _d2['avg_pts'],
                        'Gap Up %': _d2['gap_up'],
                        'Yr Consistent': _d2['consist'],
                        'Logic': _d2['label'],
                    })
                import pandas as _pd2
                _rk_df = _pd2.DataFrame(_rk_data)
                def _rk_color(row):
                    t = row['Trade']
                    if t == 'CALL': return ['background-color:rgba(16,185,129,0.12)']*len(row)
                    if t == 'PUT':  return ['background-color:rgba(239,68,68,0.12)']*len(row)
                    return ['background-color:rgba(148,163,184,0.08)']*len(row)
                st.dataframe(_rk_df.style.apply(_rk_color, axis=1),
                             use_container_width=True, hide_index=True)

            # ── VANNA ZONE METRICS (kept — zone counts are still useful) ──────
            st.markdown("---")
            k1,k2,k3,k4,k5,k6 = st.columns(6)
            k1.metric("Flip Zones",    len(vf_zones))
            k2.metric("🚀 LOC",        sum(1 for z in vf_zones if z['role']=='VACUUM_ZONE'))
            k3.metric("🔴 Resistance", sum(1 for z in vf_zones if z['role']=='RESISTANCE_CEILING'))
            k4.metric("⚠️ Trap Doors", sum(1 for z in vf_zones if z['role']=='TRAP_DOOR'))
            k5.metric("🛡️ Sup Floor",  sum(1 for z in vf_zones if z['role']=='SUPPORT_FLOOR'))
            k6.metric("IV Regime",     _curr_iv_m)

        # ── TAB 5: Enhanced OI VANNA ──────────────────────────────────────────

        with tabs[5]:
            st.markdown("### 🌊 Enhanced OI VANNA")
            st.caption("OI-weighted VANNA incorporating Volume · IV · Distance. Pink = Positive, Deep Pink = Negative.")
            try: _iv_for_tab6 = iv_at_ts
            except NameError: _iv_for_tab6 = compute_iv_trend(df)
            _tte_tab6 = 7/365 if meta.get('expiry_flag','WEEK') == 'WEEK' else 30/365
            enh_vanna_fig = create_enhanced_oi_vanna_only_chart(df_selected, reference_price, unit_label,
                df_full=df, tte=_tte_tab6, iv_df_override=_iv_for_tab6)
            st.plotly_chart(enh_vanna_fig, use_container_width=True)
            v1, v2, v3 = st.columns(3)
            if 'enhanced_oi_vanna' in df_selected.columns:
                v1.metric("🩷 Positive OI VANNA", f"{df_selected['enhanced_oi_vanna'].clip(lower=0).sum():.4f}{unit_label}")
                v2.metric("💜 Negative OI VANNA", f"{df_selected['enhanced_oi_vanna'].clip(upper=0).sum():.4f}{unit_label}")
                v3.metric("⚡ Net Enhanced VANNA", f"{df_selected['enhanced_oi_vanna'].sum():.4f}{unit_label}")
            else:
                v1.metric("Call VANNA", f"{df_selected['call_vanna'].sum():.4f}{unit_label}")
                v2.metric("Put VANNA",  f"{df_selected['put_vanna'].sum():.4f}{unit_label}")
                v3.metric("Net VANNA",  f"{df_selected['net_vanna'].sum():.4f}{unit_label}")

        # ── TAB 6: Strategy Hub ───────────────────────────────────────────────
        with tabs[6]:
            strat_sub1, strat_sub2, strat_sub3, strat_sub4 = st.tabs([
                "💰 Profitable Setups",
                "📊 Price Levels + Strategy",
                "⏰ Intraday Strategies",
                "🌙 BTST Strategies",
            ])
            with strat_sub1:
                render_profit_setups_tab()
            with strat_sub2:
                render_price_levels_strategy_tab(
                    df_selected  = df_selected,
                    spot_price   = reference_price,
                    vanna_zones  = _strat_vanna,
                    iv_regime    = _strat_iv_reg,
                    cascade_bear = _strat_bear_pts,
                    cascade_bull = _strat_bull_pts,
                    unit_label   = unit_label,
                    symbol       = symbol,
                    meta         = meta,
                )
            with strat_sub3:
                render_intraday_strategy_tab(
                    df           = df,
                    df_selected  = df_selected,
                    spot_price   = reference_price,
                    iv_regime    = _strat_iv_reg,
                    unit_label   = unit_label,
                )
            with strat_sub4:
                render_btst_strategy_tab(
                    df           = df,
                    df_selected  = df_selected,
                    spot_price   = reference_price,
                    iv_regime    = _strat_iv_reg,
                    unit_label   = unit_label,
                )


    else:
        st.info("""
        👋 **Welcome to NYZTrade UNIFIED Dashboard!**
        Select your instrument and click 🚀 Fetch Data to begin!
        """)

    # ── VIDEO TUTORIALS — always visible, no data required ───────────────
    # Rendered outside the data-gate so it shows even before Fetch Data
    st.markdown("---")
    st.markdown("### &#x1F3AC; Video Tutorials")
    st.caption("Videos hosted on Veed.io. Add embed codes in HEDGEX_VIDEOS at the top of the file.")
    _video_list = [
        {
            "key":       str(_vi),
            "title":     str(_vd.get("title", f"Video {_vi+1}")),
            "embed":     str(_vd.get("embed", "")),
            "desc":      str(_vd.get("desc", "")),
            "topics":    list(_vd.get("topics", [])),
            "thumbnail": str(_vd.get("thumbnail", "")),
        }
        for _vi, _vd in enumerate(HEDGEX_VIDEOS)
        if isinstance(_vd, dict)
    ]
    if not _video_list:
        st.info("No videos configured yet. Add <iframe> embed codes in HEDGEX_VIDEOS at the top of the file.")
    else:
        for _vid in _video_list:
            _topics   = _vid.get("topics", [])
            _thumb    = _vid.get("thumbnail", "").strip()
            # Auto-inject &download=0 into any Veed.io src URL at render time
            import re as _re
            _raw_embed = _vid["embed"].strip()
            if "veed.io/embed" in _raw_embed and "download=0" not in _raw_embed:
                _raw_embed = _re.sub(
                    r'(src="https://veed\.io/embed/[^"]*?)(")',
                    lambda m: m.group(1) + ("&" if "?" in m.group(1) else "?") + "download=0" + m.group(2),
                    _raw_embed
                )
            _has_vid  = _raw_embed.startswith("<")

            # Section header
            st.markdown(
                f'<div style="background:rgba(99,102,241,0.08);border:1.5px solid '
                f'rgba(99,102,241,0.25);border-radius:12px;padding:12px 18px;margin-bottom:8px;">'
                f'<div style="font-family:Space Grotesk,sans-serif;font-size:1.05rem;'
                f'font-weight:700;color:#a5b4fc;">&#x1F3AC; {_vid["title"]}</div>'
                + (f'<div style="font-family:JetBrains Mono,monospace;font-size:0.70rem;'
                   f'color:#64748b;margin-top:3px;">{_vid["desc"]}</div>' if _vid["desc"] else "")
                + '</div>',
                unsafe_allow_html=True,
            )

            # Two-column layout: video (left) | topics (right)
            _vcol, _tcol = st.columns([3, 2])

            with _vcol:
                if _has_vid:
                    if _thumb:
                        st.markdown(
                            '<div style="border-radius:8px;overflow:hidden;'
                            'margin-bottom:6px;border:1px solid rgba(99,102,241,0.25);">'
                            f'<img src="{_thumb}" style="width:100%;display:block;">'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(
                        '<div style="position:relative;border-radius:10px;'
                        'overflow:hidden;margin-bottom:16px;">'
                        f'{_raw_embed}'
                        # Transparent overlay blocks right-click + download button
                        '<div style="position:absolute;top:0;left:0;width:100%;height:100%;'
                        'z-index:9;pointer-events:none;'
                        'background:transparent;'
                        'oncontextmenu=\"return false;\">'
                        '</div>'
                        # Bottom-right blocker covers Veed.io download button area
                        '<div style="position:absolute;bottom:0;right:0;'
                        'width:120px;height:44px;z-index:10;'
                        'background:rgba(0,0,0,0.01);cursor:default;'
                        'title=\"\"></div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    # Placeholder — thumbnail with play overlay, or blank card
                    if _thumb:
                        st.markdown(
                            '<div style="border-radius:10px;overflow:hidden;'
                            'margin-bottom:16px;border:1px solid rgba(99,102,241,0.25);'
                            'position:relative;">'
                            f'<img src="{_thumb}" style="width:100%;display:block;opacity:0.6;">'
                            '<div style="position:absolute;top:50%;left:50%;'
                            'transform:translate(-50%,-50%);font-size:3rem;">'
                            '&#x25B6;&#xFE0F;</div></div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            '<div style="background:rgba(15,23,42,0.6);'
                            'border:1.5px dashed rgba(99,102,241,0.30);'
                            'border-radius:10px;height:220px;'
                            'display:flex;flex-direction:column;'
                            'align-items:center;justify-content:center;margin-bottom:16px;">'
                            '<div style="font-size:2.5rem;margin-bottom:8px;">&#x1F3AC;</div>'
                            '<div style="font-family:JetBrains Mono,monospace;'
                            'font-size:0.72rem;color:#475569;text-align:center;'
                            'padding:0 20px;">Video coming soon<br>'
                            '<span style="color:#334155;">Add embed in HEDGEX_VIDEOS</span>'
                            '</div></div>',
                            unsafe_allow_html=True,
                        )
            with _tcol:
                if _topics:
                    _topics_html = (
                        '<div style="background:linear-gradient(160deg,rgba(15,23,42,0.7),rgba(30,27,75,0.5));'
                        'border:1.5px solid rgba(129,140,248,0.30);'
                        'border-radius:12px;padding:18px 20px;height:100%;'
                        'box-shadow:inset 0 1px 0 rgba(255,255,255,0.04);">'
                        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">'
                        '<span style="font-size:1.05rem;">&#x1F4CB;</span>'
                        '<span style="font-family:Space Grotesk,sans-serif;font-size:0.88rem;'
                        'font-weight:700;color:#a5b4fc;letter-spacing:0.02em;'
                        '>Areas Covered</span></div>'
                        '<ol style="margin:0;padding-left:20px;">'
                        + ''.join(
                            f'<li style="font-family:Space Grotesk,sans-serif;font-size:0.82rem;'
                            f'font-weight:500;color:#cbd5e1;margin-bottom:8px;'
                            f'line-height:1.5;padding-left:4px;">{t}</li>'
                            for t in _topics
                        )
                        + '</ol></div>'
                    )
                    st.markdown(_topics_html, unsafe_allow_html=True)
                else:
                    st.caption("No topics listed for this video.")

            st.markdown("<br>", unsafe_allow_html=True)


    st.markdown("---")
    st.markdown(f"""
    <div style="text-align:center;padding:20px;color:#64748b;">
        <p style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;">
            NYZTrade Unified GEX/DEX Dashboard | INDEX + STOCK Options<br>
            Smart Caching | VANNA/CHARM | Gamma Flip Zones | Volume Spike Detection | Drawing Tools
        </p>
        <p style="font-size:0.75rem;margin-top:8px;">
            ⚠️ For educational and research purposes only. Not financial advice.
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
