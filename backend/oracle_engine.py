"""
oracle_engine.py — SMC pattern detection from Binance 4H OHLCV data.

Detects: Fair Value Gaps, Order Blocks, Liquidity Levels.
Formats real analysis as pet "prophecy" text. Cached 24 h.
"""
import asyncio
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

BINANCE_BASE  = "https://api.binance.com"
_ORACLE_TTL   = 14_400   # 4 h cache (was 24 h — keep it fresher)
_oracle_cache: Dict[str, Any] = {}


# ── Binance fetch ─────────────────────────────────────────────────────────────

async def _fetch_klines(symbol: str, interval: str, limit: int) -> List[list]:
    url = f"{BINANCE_BASE}/api/v3/klines"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params={"symbol": symbol, "interval": interval, "limit": limit})
        r.raise_for_status()
        return r.json()


async def _fetch_ticker_24h(symbol: str) -> Dict[str, Any]:
    url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params={"symbol": symbol})
        r.raise_for_status()
        return r.json()


# ── FVG Detection ─────────────────────────────────────────────────────────────

def detect_fvg(klines: List[list]) -> Optional[Dict[str, Any]]:
    """Find the most recent unmitigated Fair Value Gap."""
    current_price = float(klines[-1][4])
    for i in range(len(klines) - 1, 1, -1):
        c0_high = float(klines[i - 2][2])
        c0_low  = float(klines[i - 2][3])
        c2_high = float(klines[i][2])
        c2_low  = float(klines[i][3])

        # Bullish FVG: c2_low > c0_high  (gap up, price above it)
        if c2_low > c0_high and current_price >= c0_high:
            size_pct = (c2_low - c0_high) / c0_high * 100
            if size_pct > 0.05:   # ignore tiny noise
                return {
                    "type":    "bullish",
                    "top":     round(c2_low, 1),
                    "bottom":  round(c0_high, 1),
                    "mid":     round((c2_low + c0_high) / 2, 1),
                    "size_pct":round(size_pct, 2),
                }

        # Bearish FVG: c2_high < c0_low  (gap down, price below it)
        if c2_high < c0_low and current_price <= c0_low:
            size_pct = (c0_low - c2_high) / c2_high * 100
            if size_pct > 0.05:
                return {
                    "type":    "bearish",
                    "top":     round(c0_low, 1),
                    "bottom":  round(c2_high, 1),
                    "mid":     round((c0_low + c2_high) / 2, 1),
                    "size_pct":round(size_pct, 2),
                }
    return None


# ── Order Block Detection ─────────────────────────────────────────────────────

def detect_order_block(klines: List[list]) -> Optional[Dict[str, Any]]:
    """Last unmitigated order block: opposite candle before impulse move."""
    if len(klines) < 4:
        return None
    for i in range(len(klines) - 3, 1, -1):
        o  = float(klines[i][1])
        h  = float(klines[i][2])
        l  = float(klines[i][3])
        c  = float(klines[i][4])
        n_h = float(klines[i + 1][2])
        n_l = float(klines[i + 1][3])
        n_o = float(klines[i + 1][1])
        n_c = float(klines[i + 1][4])

        # Bullish OB: bearish candle before strong bullish impulse (>0.8% up)
        if c < o and (n_c - n_o) / n_o > 0.008:
            return {
                "type":  "bullish",
                "top":   round(o, 1),
                "bottom":round(l, 1),
                "label": "Бычий ордер-блок",
            }

        # Bearish OB: bullish candle before strong bearish impulse (>0.8% down)
        if c > o and (n_o - n_c) / n_o > 0.008:
            return {
                "type":  "bearish",
                "top":   round(h, 1),
                "bottom":round(o, 1),
                "label": "Медвежий ордер-блок",
            }
    return None


# ── Liquidity Level Detection ─────────────────────────────────────────────────

def detect_liquidity(klines: List[list]) -> Dict[str, Any]:
    highs   = [float(k[2]) for k in klines]
    lows    = [float(k[3]) for k in klines]
    current = float(klines[-1][4])
    bsl     = max(highs)
    ssl     = min(lows)

    # Equal highs: wicks within 0.2% of BSL
    bsl_count = sum(1 for h in highs if abs(h - bsl) / bsl < 0.002)
    ssl_count = sum(1 for l in lows  if abs(l - ssl) / ssl < 0.002)

    return {
        "bsl":        round(bsl, 1),
        "ssl":        round(ssl, 1),
        "bsl_touches":bsl_count,
        "ssl_touches":ssl_count,
        "current":    round(current, 1),
    }


# ── Prophecy text templates ───────────────────────────────────────────────────

_FVG_BULLISH = [
    "Вижу бычий FVG между ${bottom} и ${top} — Smart Money оставили пустоту. Рынок вернётся.",
    "Fair Value Gap ${bottom}–${top}: цена уйдёт вниз за ликвидностью перед следующим импульсом.",
    "Дисбаланс на ${mid} — бычий, незаполненный. Следи за реакцией при возврате в зону.",
]
_FVG_BEARISH = [
    "Медвежий FVG ${bottom}–${top}: зона интереса продавцов. Retest может быть ловушкой.",
    "Чувствую пустоту ${bottom}–${top} — медвежья FVG. Smart Money продавали здесь.",
    "Дисбаланс на ${mid}: рынок оставил след. Шорт-активность при возврате в зону.",
]
_OB_BULLISH = [
    "Бычий ордер-блок ${bottom}–${top}: институционалы набирали лонги здесь. Смотри реакцию.",
    "На уровне ${top}–${bottom} — зона покупок Smart Money. OB ещё не смягчён.",
    "Ордер-блок ${bottom} сильный — там стояли биды маркет-мейкеров.",
]
_OB_BEARISH = [
    "Медвежий OB ${bottom}–${top}: зона распределения. Short-ловушка для незнающих.",
    "Ордер-блок продавцов ${top}–${bottom} — если цена вернётся, жди шорт-импульс.",
    "На ${top} смотри. Там институционалы продавали. OB жив, не тронут.",
]
_LIQ_BSL = [
    "Над ${bsl} скопились стопы покупателей ({touches}× касания). Sweep — и разворот.",
    "Равные максимумы на ${bsl}: ловушка для ретейла. Smart Money охотятся за BSL.",
]
_LIQ_SSL = [
    "Под ${ssl} — тихий омут ({touches}× касания). Sweep SSL перед бычьим разворотом.",
    "Sell-side ликвидность на ${ssl}. Маркет-мейкер заберёт её — следи за реакцией.",
]
_GENERIC = [
    "Рынок накапливает позицию вблизи ${price}. Ожидай сетап в ближайшие 4–12 часов.",
    "Smart Money молчат. Накопление у ${price} — взрывной ход готовится.",
]


def _prophecy(fvg, ob, liq, btc_price: float) -> str:
    parts = []
    rng = random.Random(int(time.time() // 86400))   # same seed all day

    if fvg:
        tpls = _FVG_BULLISH if fvg["type"] == "bullish" else _FVG_BEARISH
        t = rng.choice(tpls)
        parts.append(t.format(**{k: f"{v:,.0f}" if isinstance(v, (int, float)) else v
                                 for k, v in fvg.items()}))

    if ob and len(parts) < 2:
        tpls = _OB_BULLISH if ob["type"] == "bullish" else _OB_BEARISH
        t = rng.choice(tpls)
        parts.append(t.format(**{k: f"{v:,.0f}" if isinstance(v, (int, float)) else v
                                 for k, v in ob.items()}))

    if not parts and liq:
        if liq["bsl_touches"] >= 3:
            t = rng.choice(_LIQ_BSL)
            parts.append(t.format(bsl=f"{liq['bsl']:,.0f}", touches=liq["bsl_touches"]))
        elif liq["ssl_touches"] >= 3:
            t = rng.choice(_LIQ_SSL)
            parts.append(t.format(ssl=f"{liq['ssl']:,.0f}", touches=liq["ssl_touches"]))

    if not parts:
        t = rng.choice(_GENERIC)
        parts.append(t.format(price=f"{btc_price:,.0f}"))

    return " ".join(parts[:2])


# ── Public API ────────────────────────────────────────────────────────────────

def _get_sentiment(fvg, ob) -> str:
    if fvg and fvg["type"] == "bullish":
        return "bullish"
    if ob and ob["type"] == "bullish":
        return "bullish"
    if fvg and fvg["type"] == "bearish":
        return "bearish"
    if ob and ob["type"] == "bearish":
        return "bearish"
    return "neutral"


async def generate_oracle() -> Dict[str, Any]:
    """Generate (or return cached) oracle. Valid for 4 h."""
    now = time.time()
    cached = _oracle_cache.get("oracle")
    if cached and cached.get("ok") and now - cached.get("_ts", 0) < _ORACLE_TTL:
        return cached

    try:
        klines, ticker = await asyncio.gather(
            _fetch_klines("BTCUSDT", "4h", 60),
            _fetch_ticker_24h("BTCUSDT"),
        )
        price      = float(klines[-1][4])
        change_pct = float(ticker.get("priceChangePercent", 0))
        change_str = ("+" if change_pct >= 0 else "") + f"{change_pct:.2f}%"

        fvg  = detect_fvg(klines)
        ob   = detect_order_block(klines)
        liq  = detect_liquidity(klines)
        text = _prophecy(fvg, ob, liq, price)

        sentiment = _get_sentiment(fvg, ob)
        concept   = "FVG" if fvg else ("OB" if ob else "Ликвидность")

        result = {
            "ok":           True,
            # Legacy fields (still used by parts of the UI)
            "text":         text,
            "concept":      concept,
            "btc_price":    round(price, 0),
            # New structured fields
            "title":        "Оракул открыл глаз",
            "asset":        "BTC/USDT",
            "prophecy":     text,
            "sentiment":    sentiment,
            "price":        round(price, 0),
            "change_24h":   change_str,
            "fvg":          fvg,
            "ob":           ob,
            "liq":          liq,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "_ts":          now,
        }
        _oracle_cache["oracle"] = result
        logger.info(f"Oracle: sentiment={sentiment} concept={concept} change={change_str}")
        return result

    except Exception as e:
        logger.error(f"Oracle error: {e}")
        fallback = dict(_oracle_cache.get("oracle") or {})
        if fallback.get("ok"):
            return fallback
        return {
            "ok":        False,
            "text":      "Мистические силы недоступны. Попробуй позже.",
            "prophecy":  "Мистические силы недоступны. Попробуй позже.",
            "concept":   "unknown",
            "sentiment": "neutral",
            "title":     "Оракул молчит",
            "asset":     "BTC/USDT",
        }
