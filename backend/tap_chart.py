"""
tap_chart.py — Генерация мини-графиков для тапалки Алхимии.
Каждый график = набор свечей + зоны для идентификации.
Игрок тапает на правильную зону → получает CHM.
"""
import random
import uuid
from typing import Dict, List, Any


ZONE_TYPES = ["order_block", "fvg", "liquidity_sweep", "bos"]

ZONE_QUESTIONS = {
    "order_block":     "Найди Order Block на графике",
    "fvg":             "Найди Fair Value Gap (FVG)",
    "liquidity_sweep": "Найди Liquidity Sweep",
    "bos":             "Найди Break of Structure (BOS)",
}


def _gen_candles(n: int, trend: float = 0.6) -> List[Dict[str, float]]:
    """
    Генерирует n реалистичных свечей.
    trend: вероятность бычьего движения (0.5 = нейтральный).
    """
    candles = []
    price = 100.0
    for i in range(n):
        bull = random.random() < trend
        move = random.uniform(0.5, 2.5) * (1 if bull else -1)
        open_ = price
        close = round(open_ + move, 2)
        high  = round(max(open_, close) + random.uniform(0.1, 1.5), 2)
        low   = round(min(open_, close) - random.uniform(0.1, 1.5), 2)
        candles.append({"o": round(open_, 2), "h": high, "l": low, "c": round(close, 2)})
        price = close
    return candles


def _insert_order_block(candles: List, difficulty: int) -> Dict[str, Any]:
    """
    Вставляет OB-паттерн: последняя медвежья свеча перед сильным бычьим движением.
    Возвращает зону.
    """
    n = len(candles)
    # Выбираем позицию в середине (не в самом конце)
    pos = random.randint(3, n - 5)
    # Делаем свечу pos медвежьей (OB)
    ref = candles[pos]
    ob_high = ref["h"]
    ob_low  = ref["l"]
    ob_open = max(ref["o"], ref["c"]) + random.uniform(0.2, 0.8)
    ob_close = min(ref["o"], ref["c"]) - random.uniform(0.2, 0.8)
    candles[pos] = {"o": round(ob_open,2), "h": round(ob_high,2), "l": round(ob_low,2), "c": round(ob_close,2)}
    # После OB — сильный бычий импульс
    price = ob_close
    for i in range(pos+1, min(pos+3, n)):
        move = random.uniform(1.5, 3.5)
        o = price; c = round(o + move, 2)
        candles[i] = {"o":round(o,2), "h":round(c+0.5,2), "l":round(o-0.2,2), "c":c}
        price = c
    return {"type": "order_block", "x1": pos, "x2": pos, "y1": ob_low, "y2": ob_high}


def _insert_fvg(candles: List, difficulty: int) -> Dict[str, Any]:
    """
    FVG: разрыв между high свечи [i] и low свечи [i+2] при сильном движении вверх.
    """
    n = len(candles)
    pos = random.randint(2, n - 5)
    # Убеждаемся что есть разрыв: high[pos] < low[pos+2]
    base = candles[pos]["c"]
    move1 = random.uniform(2.0, 4.0)
    move2 = random.uniform(2.0, 4.0)
    c1 = round(base + move1, 2)
    c2 = round(c1 + move2, 2)
    candles[pos]   = {"o":base,           "h":round(base+move1*0.3,2), "l":round(base-0.3,2), "c":round(base+move1*0.3,2)}
    candles[pos+1] = {"o":candles[pos]["c"],"h":c1+random.uniform(0.5,1),  "l":candles[pos]["c"]-0.2,  "c":c1}
    candles[pos+2] = {"o":c1,              "h":c2+random.uniform(0.3,1),  "l":c1+random.uniform(0.5,1.5),"c":c2}
    gap_low  = candles[pos]["h"]
    gap_high = candles[pos+2]["l"]
    if gap_high <= gap_low:
        gap_high = round(gap_low + 1.0, 2)
    return {"type": "fvg", "x1": pos, "x2": pos+2, "y1": gap_low, "y2": gap_high}


def _insert_liquidity_sweep(candles: List, difficulty: int) -> Dict[str, Any]:
    """
    Sweep: серия равных лоёв, затем фитиль ниже с возвратом.
    """
    n = len(candles)
    pos = random.randint(2, n - 6)
    sweep_level = candles[pos]["l"]
    # Устанавливаем несколько равных лоёв
    for i in range(pos, min(pos+3, n)):
        candles[i]["l"] = round(sweep_level + random.uniform(-0.1, 0.1), 2)
    # Свеча sweep: фитиль ниже, тело возвращается
    sweep_pos = min(pos+3, n-1)
    c = candles[sweep_pos]
    spike_low = round(sweep_level - random.uniform(1.5, 3.0), 2)
    candles[sweep_pos] = {"o": c["o"], "h": c["h"], "l": spike_low, "c": round(sweep_level + random.uniform(0.5, 1.5), 2)}
    return {"type": "liquidity_sweep", "x1": pos, "x2": sweep_pos, "y1": spike_low, "y2": sweep_level}


def _insert_bos(candles: List, difficulty: int) -> Dict[str, Any]:
    """
    BOS: свеча пробивает предыдущий свинг-хай.
    """
    n = len(candles)
    pos = random.randint(3, n - 4)
    swing_high = max(candles[i]["h"] for i in range(max(0, pos-3), pos))
    bos_close = round(swing_high + random.uniform(1.0, 2.5), 2)
    o = candles[pos]["o"]
    candles[pos] = {"o": o, "h": round(bos_close + 0.3, 2), "l": round(o - 0.2, 2), "c": bos_close}
    return {"type": "bos", "x1": pos, "x2": pos, "y1": swing_high - 0.2, "y2": swing_high + 0.2}


_PATTERN_INSERTERS = {
    "order_block":     _insert_order_block,
    "fvg":             _insert_fvg,
    "liquidity_sweep": _insert_liquidity_sweep,
    "bos":             _insert_bos,
}


def generate_tap_chart(user_id: int, user_level: int = 1) -> Dict[str, Any]:
    """
    Генерирует мини-график с зонами для тапалки.

    difficulty:
      Уровни 1-5:  2 зоны (1 правильная, 1 ловушка)
      Уровни 6-10: 3 зоны
      Уровни 11+:  4 зоны

    Возвращает dict с candles, zones (без correct_zone_id), correct_zone_id, question, difficulty.
    """
    if user_level <= 5:
        difficulty = 1
        n_zones = 2
        n_candles = random.randint(15, 18)
    elif user_level <= 10:
        difficulty = 2
        n_zones = 3
        n_candles = random.randint(18, 22)
    else:
        difficulty = 3
        n_zones = 4
        n_candles = random.randint(20, 25)

    trend = random.uniform(0.35, 0.65)
    candles = _gen_candles(n_candles, trend)

    # Pick correct zone type
    correct_type = random.choice(ZONE_TYPES)
    # Decoy types (different from correct)
    other_types = [t for t in ZONE_TYPES if t != correct_type]
    decoy_types = random.sample(other_types, min(n_zones - 1, len(other_types)))

    zones_raw = []

    # Insert correct zone
    try:
        correct_raw = _PATTERN_INSERTERS[correct_type](candles, difficulty)
    except Exception:
        correct_raw = {"type": correct_type, "x1": 5, "x2": 5, "y1": 99.0, "y2": 101.0}
    correct_id = f"z_{uuid.uuid4().hex[:6]}"
    correct_raw["id"] = correct_id
    correct_raw["correct"] = True
    zones_raw.append(correct_raw)

    # Insert decoy zones
    for dtype in decoy_types:
        try:
            decoy_raw = _PATTERN_INSERTERS[dtype](candles, difficulty)
        except Exception:
            decoy_raw = {"type": dtype, "x1": 10, "x2": 10, "y1": 95.0, "y2": 97.0}
        decoy_raw["id"] = f"z_{uuid.uuid4().hex[:6]}"
        decoy_raw["correct"] = False
        zones_raw.append(decoy_raw)

    random.shuffle(zones_raw)

    chart_id = uuid.uuid4().hex
    return {
        "chart_id":        chart_id,
        "candles":         candles,
        "zones":           zones_raw,
        "correct_zone_id": correct_id,
        "question":        ZONE_QUESTIONS[correct_type],
        "difficulty":      difficulty,
        "zone_type":       correct_type,
    }


def check_tap_answer(chart_data: Dict[str, Any], tapped_zone_id: str) -> Dict[str, Any]:
    """
    Проверяет ответ пользователя.
    Возвращает correct, zone_type, chm_multiplier.
    """
    correct_id = chart_data.get("correct_zone_id")
    zones = chart_data.get("zones", [])

    # Find tapped zone
    tapped_zone = next((z for z in zones if z["id"] == tapped_zone_id), None)
    if not tapped_zone:
        return {"correct": False, "zone_type": "unknown", "chm_multiplier": 0.0}

    is_correct = tapped_zone_id == correct_id
    return {
        "correct":        is_correct,
        "zone_type":      tapped_zone.get("type", "unknown"),
        "correct_type":   chart_data.get("zone_type", "unknown"),
        "chm_multiplier": 1.0 if is_correct else 0.1,
    }
