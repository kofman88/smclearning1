"""
market_feed.py — Live BTC market data with multi-provider fallback.

Providers (tried in order):
  1. CoinGecko  – /coins/bitcoin/market_chart (no auth, global access)
  2. Kraken     – /0/public/OHLC (US exchange, no geo-block)

Fetches every 60 s, caches in memory.
Computes: price_change_1h, volatility_index, market_state → pet_mood.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL    = 60      # seconds before re-fetch
_FETCH_TIMEOUT = 8.0   # httpx timeout

_cache: Dict[str, Any] = {}
_fetch_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _fetch_lock
    if _fetch_lock is None:
        _fetch_lock = asyncio.Lock()
    return _fetch_lock


# ── Market state classification ───────────────────────────────────────────────

_STATE_RULES = [
    ("crash",    lambda ch, v: ch <= -4.0),
    ("dump",     lambda ch, v: ch <= -1.5),
    ("pump",     lambda ch, v: ch >= 3.0),
    ("rally",    lambda ch, v: ch >= 1.0),
    ("volatile", lambda ch, v: v >= 65),
    ("flat",     lambda ch, v: abs(ch) < 0.3 and v < 25),
]

_MOOD_MAP: Dict[str, Dict[str, Any]] = {
    "crash":    {"visual": "sick",    "aura": "#ef4444", "pulse_speed": 0.35, "label": "Крэш рынка 📉"},
    "dump":     {"visual": "hungry",  "aura": "#f97316", "pulse_speed": 0.65, "label": "Нисходящий тренд"},
    "pump":     {"visual": "excited", "aura": "#fbbf24", "pulse_speed": 1.7,  "label": "Бычий импульс 🚀"},
    "rally":    {"visual": "happy",   "aura": "#10b981", "pulse_speed": 1.3,  "label": "Восходящий тренд"},
    "volatile": {"visual": "excited", "aura": "#a855f7", "pulse_speed": 2.2,  "label": "Высокая волатильность ⚡"},
    "flat":     {"visual": "idle",    "aura": "#64748b", "pulse_speed": 0.45, "label": "Флет. Лисичка дремлет..."},
    "neutral":  {"visual": "idle",    "aura": "#ff8c42", "pulse_speed": 1.0,  "label": "Нейтральный рынок"},
}


def _classify(price_change_1h: float, volatility: float) -> str:
    for state, fn in _STATE_RULES:
        if fn(price_change_1h, volatility):
            return state
    return "neutral"


def _build_pet_mood(state: str, change: float, vol: float) -> Dict[str, Any]:
    m = dict(_MOOD_MAP.get(state, _MOOD_MAP["neutral"]))
    m["market_state"]     = state
    m["price_change_1h"]  = round(change, 2)
    m["volatility_index"] = round(vol, 1)
    return m


def _calc_volatility_from_ohlc(rows: List[Any], high_idx: int, low_idx: int, close_idx: int) -> float:
    """Normalized ATR volatility 0-100 from high-low range / close."""
    if not rows:
        return 50.0
    ranges = []
    for r in rows:
        try:
            high  = float(r[high_idx])
            low   = float(r[low_idx])
            close = float(r[close_idx])
            if close > 0:
                ranges.append((high - low) / close * 100)
        except (IndexError, ValueError, TypeError):
            continue
    if not ranges:
        return 50.0
    avg = sum(ranges) / len(ranges)
    return min(100.0, max(0.0, (avg - 0.3) / 2.7 * 100))


# ── Provider 1: CoinGecko ────────────────────────────────────────────────────

async def _fetch_coingecko() -> Dict[str, Any]:
    """
    Uses /coins/bitcoin/market_chart?days=2&interval=hourly
    Returns: prices [[ts_ms, price], ...]
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "2", "interval": "hourly"}
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    prices: List[List[float]] = data.get("prices", [])
    if len(prices) < 3:
        raise ValueError("CoinGecko: insufficient price data")

    close_now  = prices[-1][1]
    close_prev = prices[-2][1]   # 1 h ago
    open_24h   = prices[max(0, len(prices) - 25)][1]

    change_1h  = (close_now - close_prev) / close_prev * 100
    change_24h = (close_now - open_24h)   / open_24h   * 100

    # estimate volatility from price swings over last 6 points
    recent = prices[-7:]
    vol_vals = []
    for i in range(1, len(recent)):
        prev_p = recent[i - 1][1]
        curr_p = recent[i][1]
        if prev_p > 0:
            vol_vals.append(abs(curr_p - prev_p) / prev_p * 100)
    raw_vol = sum(vol_vals) / len(vol_vals) if vol_vals else 0.5
    volatility = min(100.0, max(0.0, (raw_vol - 0.3) / 2.7 * 100))

    logger.info(f"CoinGecko OK: BTC=${close_now:.0f} 1h={change_1h:+.2f}% vol={volatility:.0f}")
    return {
        "btc_price":        round(close_now, 2),
        "price_change_1h":  round(change_1h, 2),
        "price_change_24h": round(change_24h, 2),
        "volatility_index": round(volatility, 1),
    }


# ── Provider 2: Kraken ───────────────────────────────────────────────────────

async def _fetch_kraken() -> Dict[str, Any]:
    """
    Uses /0/public/OHLC?pair=XBTUSD&interval=60
    Row: [time, open, high, low, close, vwap, volume, count]
    """
    url = "https://api.kraken.com/0/public/OHLC"
    params = {"pair": "XBTUSD", "interval": 60}
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    if data.get("error"):
        raise ValueError(f"Kraken error: {data['error']}")

    result = data.get("result", {})
    pair_key = next((k for k in result if k != "last"), None)
    if not pair_key:
        raise ValueError("Kraken: no OHLC pair found")

    rows: List[list] = result[pair_key]
    if len(rows) < 3:
        raise ValueError("Kraken: insufficient OHLC data")

    # row indices: 0=time, 1=open, 2=high, 3=low, 4=close
    close_now  = float(rows[-1][4])
    close_prev = float(rows[-2][4])
    open_24h   = float(rows[max(0, len(rows) - 25)][1])

    change_1h  = (close_now - close_prev) / close_prev * 100
    change_24h = (close_now - open_24h)   / open_24h   * 100
    volatility = _calc_volatility_from_ohlc(rows[-7:], high_idx=2, low_idx=3, close_idx=4)

    logger.info(f"Kraken OK: BTC=${close_now:.0f} 1h={change_1h:+.2f}% vol={volatility:.0f}")
    return {
        "btc_price":        round(close_now, 2),
        "price_change_1h":  round(change_1h, 2),
        "price_change_24h": round(change_24h, 2),
        "volatility_index": round(volatility, 1),
    }


# ── Main refresh ─────────────────────────────────────────────────────────────

async def refresh_market_data() -> Dict[str, Any]:
    """Fetch & compute market pulse. Returns full pulse dict."""
    lock = _get_lock()
    async with lock:
        now = time.time()
        cached = _cache.get("pulse")
        if cached and now - cached.get("_fetched_at", 0) < _CACHE_TTL:
            return cached

        raw: Optional[Dict[str, Any]] = None
        last_err: Exception = Exception("no providers tried")

        for provider_fn, name in [(_fetch_kraken, "Kraken"), (_fetch_coingecko, "CoinGecko")]:
            try:
                raw = await provider_fn()
                break
            except Exception as e:
                logger.warning(f"{name} failed: {e}")
                last_err = e

        if raw is None:
            logger.error(f"market_feed: all providers failed: {last_err}")
            fallback = dict(_cache.get("pulse") or {})
            fallback["ok"]    = False
            fallback["error"] = str(last_err)
            if "pet_mood" not in fallback:
                fallback["pet_mood"] = _build_pet_mood("neutral", 0.0, 50.0)
            return fallback

        state = _classify(raw["price_change_1h"], raw["volatility_index"])
        result = {
            "ok":               True,
            "btc_price":        raw["btc_price"],
            "price_change_1h":  raw["price_change_1h"],
            "price_change_24h": raw["price_change_24h"],
            "volatility_index": raw["volatility_index"],
            "market_state":     state,
            "pet_mood":         _build_pet_mood(state, raw["price_change_1h"], raw["volatility_index"]),
            "_fetched_at":      now,
        }
        _cache["pulse"] = result
        return result


def get_cached_pulse() -> Optional[Dict[str, Any]]:
    return _cache.get("pulse")


async def start_market_feed_loop():
    """Infinite background loop — refresh market data every 60 s."""
    logger.info("Market feed loop started")
    while True:
        try:
            await refresh_market_data()
        except Exception as e:
            logger.error(f"Market feed loop error: {e}")
        await asyncio.sleep(60)


# ── LIVE SIGNAL ───────────────────────────────────────────────────────────────

LIVE_SIGNAL_PATTERNS = {
    "crash":    {"lesson": "liquidity",        "concept": "Sweep ликвидности",    "module": 1},
    "dump":     {"lesson": "market_structure", "concept": "Break of Structure",   "module": 0},
    "pump":     {"lesson": "order_blocks",     "concept": "Ордер-блоки на лонг",  "module": 2},
    "rally":    {"lesson": "fvg",              "concept": "Fair Value Gap",        "module": 3},
    "volatile": {"lesson": "inducement",       "concept": "Inducement + sweep",   "module": 4},
    "flat":     {"lesson": "killzones",        "concept": "Kill Zones + AMD",     "module": 6},
    "neutral":  {"lesson": "premium_discount", "concept": "Premium/Discount зоны","module": 6},
}

_last_signal_state: str = ""


def detect_live_signal(pulse: dict) -> "dict | None":
    """Если состояние рынка изменилось — вернуть Live Signal. Иначе None."""
    import datetime as _dtime
    global _last_signal_state
    state = pulse.get("market_state", "neutral")
    if state == _last_signal_state:
        return None
    _last_signal_state = state

    pattern = LIVE_SIGNAL_PATTERNS.get(state, LIVE_SIGNAL_PATTERNS["neutral"])
    btc = pulse.get("btc_price", 0)
    change = pulse.get("price_change_1h", 0)
    mood_label = pulse.get("pet_mood", {}).get("label", "")

    return {
        "active": True,
        "market_state": state,
        "mood_label": mood_label,
        "btc_price": btc,
        "price_change_1h": change,
        "lesson_key": pattern["lesson"],
        "concept": pattern["concept"],
        "module_required": pattern["module"],
        "message": f"Рынок сейчас: {mood_label}. Это {pattern['concept']}. Открой урок.",
        "created_at": _dtime.datetime.utcnow().isoformat(),
    }
