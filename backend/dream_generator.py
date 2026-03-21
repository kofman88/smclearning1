"""
dream_generator.py — Personalized SMC mini-challenges for returning users.

When a user opens the app after 2+ hours offline, the fox "dreams"
of a real SMC scenario. User answers a quiz → coins + happiness boost.
"""
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)
BINANCE_BASE = "https://api.binance.com"

_MIN_OFFLINE_HOURS = 2.0

# ── Concept → quests mapping (to detect weakest area) ────────────────────────
_CONCEPT_QUESTS: Dict[str, List[str]] = {
    "OB":          ["m3_quiz", "m3_task", "m3_boss"],
    "FVG":         ["m4_quiz", "m4_task", "m4_boss"],
    "Liquidity":   ["m2_quiz", "m2_task", "m2_boss"],
    "Structure":   ["m1_quiz", "m1_task", "m1_boss"],
    "Inducement":  ["m5_quiz", "m5_task", "m5_boss"],
    "KillZones":   ["m7_quiz", "m7_task", "m7_boss"],
    "Risk":        ["m8_quiz", "m8_task", "m8_boss"],
}

_CONCEPT_META: Dict[str, Dict[str, str]] = {
    "OB":         {"name": "Ордер-блоки",    "emoji": "📦", "lesson": "order_blocks"},
    "FVG":        {"name": "Fair Value Gap", "emoji": "📊", "lesson": "fvg"},
    "Liquidity":  {"name": "Ликвидность",   "emoji": "🌊", "lesson": "liquidity"},
    "Structure":  {"name": "Структура рынка","emoji": "📈", "lesson": "market_structure"},
    "Inducement": {"name": "Индусмент",      "emoji": "🎣", "lesson": "inducement"},
    "KillZones":  {"name": "Кил-зоны",       "emoji": "🎯", "lesson": "killzones"},
    "Risk":       {"name": "Риск-менеджмент","emoji": "⚖️",  "lesson": "risk_management"},
}

# ── Dream scenario templates per concept ─────────────────────────────────────
_DREAMS: Dict[str, List[Dict[str, Any]]] = {
    "OB": [
        {
            "setup": "Лисичка видела во сне ордер-блок на BTC {tf} у ${price}...",
            "question": "Что делает бычий ордер-блок валидным по SMC?",
            "choices": [
                "Это последняя медвежья свеча перед мощным бычьим импульсом (BOS/MSS)",
                "Свеча с наибольшим объёмом в серии",
                "Первая зелёная свеча после нисходящего тренда",
                "Любая свеча у круглого числа цены",
            ],
            "correct": 0,
            "xp": 15,
        },
        {
            "setup": "Во сне лисичка чуяла снайперскую зону OB на {tf}...",
            "question": "Когда ордер-блок считается смягчённым (mitigated)?",
            "choices": [
                "Когда цена возвращается в диапазон OB и торгуется внутри него",
                "Когда прошло 24 часа после формирования",
                "Когда цена достигла +5% от уровня OB",
                "OB нельзя смягчить — он действует всегда",
            ],
            "correct": 0,
            "xp": 15,
        },
    ],
    "FVG": [
        {
            "setup": "Лисичка видела пустоту в рынке BTC {tf} между ${low} и ${high}...",
            "question": "Что такое Fair Value Gap (FVG / IMB)?",
            "choices": [
                "Разрыв между свечами, где нет перекрытия — цена вернётся заполнить его",
                "Уровень скользящей средней 200",
                "Зона максимального объёма за последние 24 часа",
                "Разница между ценой открытия и закрытия недельной свечи",
            ],
            "correct": 0,
            "xp": 12,
        },
        {
            "setup": "Во сне лисичка указывала на дисбаланс BTC {tf}...",
            "question": "Как формируется бычий FVG?",
            "choices": [
                "Нижняя тень свечи i выше верхней тени свечи i-2 (разрыв вверх)",
                "Закрытие свечи выше предыдущего максимума",
                "Три подряд бычьих свечи без теней",
                "Большой объём при закрытии выше открытия",
            ],
            "correct": 0,
            "xp": 12,
        },
    ],
    "Liquidity": [
        {
            "setup": "Лисичка слышала во сне шёпот Smart Money у уровня ${price}...",
            "question": "Что такое Buy-Side Liquidity (BSL) в SMC?",
            "choices": [
                "Скопление стоп-лоссов покупателей над локальными максимумами",
                "Зона активных покупок маркет-мейкеров",
                "Область высокого торгового объёма",
                "Уровень ближайшего сопротивления по классическому ТА",
            ],
            "correct": 0,
            "xp": 12,
        },
        {
            "setup": "Во сне лисичка видела охоту за стопами на BTC {tf}...",
            "question": "Что такое Liquidity Sweep?",
            "choices": [
                "Движение за уровень ликвидности (стопы) с быстрым разворотом",
                "Сильный тренд в одном направлении без откатов",
                "Торговля в зоне высокого объёма",
                "Закрытие выше/ниже ключевого уровня с удержанием",
            ],
            "correct": 0,
            "xp": 14,
        },
    ],
    "Structure": [
        {
            "setup": "Лисичка видела смену тренда BTC {tf} у ${price}...",
            "question": "Что означает BOS (Break of Structure) в SMC?",
            "choices": [
                "Цена пробивает предыдущий значимый хай (в восходящем) или лой (в нисходящем)",
                "Разворот на объёме выше среднего за 20 периодов",
                "Пересечение двух скользящих средних",
                "Три отбоя от уровня поддержки",
            ],
            "correct": 0,
            "xp": 12,
        },
    ],
    "Inducement": [
        {
            "setup": "Лисичка видела ловушку для трейдеров на BTC {tf}...",
            "question": "Что такое Inducement (IDM) в SMC?",
            "choices": [
                "Ложный сетап-приманка: мелкие своинги перед реальным ходом",
                "Сигнал на вход по классическим индикаторам",
                "Уровень Фибоначчи 0.618",
                "Первый откат после BOS",
            ],
            "correct": 0,
            "xp": 15,
        },
    ],
    "KillZones": [
        {
            "setup": "Во сне лисичка чувствовала активность Smart Money в кил-зоне...",
            "question": "Что такое New York Kill Zone по SMC?",
            "choices": [
                "08:00–11:00 EST — перекрытие NY с London, пик институциональной активности",
                "00:00–04:00 EST — азиатская сессия, низкий объём",
                "16:00–20:00 EST — закрытие NYSE",
                "12:00–14:00 UTC — обед Европы",
            ],
            "correct": 0,
            "xp": 13,
        },
    ],
    "Risk": [
        {
            "setup": "Лисичка видела потерянный депозит трейдера во сне...",
            "question": "Какой максимальный риск на сделку рекомендуется по SMC?",
            "choices": [
                "0.5–1% от депозита на сделку для стабильного роста",
                "5–10% чтобы быстро увеличить счёт",
                "Всё зависит от уверенности в сетапе",
                "Не менее 2% иначе прибыль несущественна",
            ],
            "correct": 0,
            "xp": 10,
        },
    ],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_btc_price() -> float:
    url = f"{BINANCE_BASE}/api/v3/ticker/price"
    async with httpx.AsyncClient(timeout=6.0) as client:
        r = await client.get(url, params={"symbol": "BTCUSDT"})
        r.raise_for_status()
        return float(r.json()["price"])


def _weakest_concept(state: Dict[str, Any]) -> str:
    completed = set(state.get("completed_quests", []))
    scores = {c: sum(1 for q in qs if q in completed)
              for c, qs in _CONCEPT_QUESTS.items()}
    return min(scores, key=scores.get)


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_dream(user_id: int, user_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return a dream challenge if user was offline ≥2 h and hasn't seen
    a dream in the last 2 h. Returns None if no dream needed.
    """
    # Check offline time
    last_online = user_state.get("last_online")
    if not last_online:
        return None
    try:
        delta = (datetime.utcnow() - datetime.fromisoformat(last_online)).total_seconds()
        offline_hours = delta / 3600
    except Exception:
        return None

    if offline_hours < _MIN_OFFLINE_HOURS:
        return None

    # Don't re-show within 2 h
    pet = user_state.get("pet", {})
    last_shown = pet.get("last_dream_shown")
    if last_shown:
        try:
            since = (datetime.utcnow() - datetime.fromisoformat(last_shown)).total_seconds()
            if since < 7200:
                return None
        except Exception:
            pass

    concept = _weakest_concept(user_state)
    templates = _DREAMS.get(concept, _DREAMS["FVG"])
    tmpl = random.choice(templates)

    try:
        price = await _fetch_btc_price()
    except Exception:
        price = 90_000.0

    tfs = ["4H", "1H", "D1", "15M"]
    tf  = random.choice(tfs)
    lo  = round(price * 0.995, 0)
    hi  = round(price * 1.005, 0)

    setup = tmpl["setup"].format(
        price=f"{price:,.0f}", tf=tf,
        low=f"{lo:,.0f}", high=f"{hi:,.0f}",
    )

    return {
        "ok":           True,
        "has_dream":    True,
        "concept":      concept,
        "offline_hours":round(offline_hours, 1),
        "dream": {
            "setup":    setup,
            "question": tmpl["question"],
            "choices":  tmpl["choices"],
            "correct":  tmpl["correct"],
            "coins_reward": 20,
            "xp_reward":    tmpl.get("xp", 12),
            "timeframe":    tf,
            "btc_price":    round(price, 0),
        },
        "concept_meta": _CONCEPT_META.get(concept, {}),
    }
