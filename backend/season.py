"""
season.py — Battle Pass и сезонная система CHM Academy.
Сезон = 30 дней. Battle Pass = 30 уровней.
1 уровень BP = 100 BP XP.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# ── Текущий сезон ────────────────────────────────────────────────────────────
CURRENT_SEASON = {
    "id": 1,
    "name": "Сезон 1: Волатильность",
    "theme": "volatility",
    "accent_color": "#ff4d6d",
    "starts_at": "2026-03-01T00:00:00",
    "ends_at":   "2026-03-31T23:59:59",
    "boss_name": "Босс Волатильности",
    "description": "Рынок нестабилен. Только лучшие выживут.",
}

# ── Награды Battle Pass (30 уровней) ─────────────────────────────────────────
BATTLE_PASS_REWARDS: List[Dict[str, Any]] = [
    {"level":  1, "type":"souls",   "amount":   50, "label":"50 Душ"},
    {"level":  2, "type":"estus",   "amount":    1, "label":"Estus-фласка"},
    {"level":  3, "type":"souls",   "amount":  100, "label":"100 Душ"},
    {"level":  4, "type":"boost",   "amount":    1, "label":"Буст тапов 1ч"},
    {"level":  5, "type":"souls",   "amount":  150, "label":"150 Душ"},
    {"level":  6, "type":"estus",   "amount":    2, "label":"Estus ×2"},
    {"level":  7, "type":"souls",   "amount":  200, "label":"200 Душ"},
    {"level":  8, "type":"isotope", "amount":    1, "label":"Нестабильный Изотоп"},
    {"level":  9, "type":"souls",   "amount":  300, "label":"300 Душ"},
    {"level": 10, "type":"frame",   "amount":    1, "label":"Рамка «Волатильность»"},
    {"level": 11, "type":"souls",   "amount":  300, "label":"300 Душ"},
    {"level": 12, "type":"boost",   "amount":    3, "label":"Буст XP 1ч"},
    {"level": 13, "type":"souls",   "amount":  400, "label":"400 Душ"},
    {"level": 14, "type":"estus",   "amount":    3, "label":"Estus ×3"},
    {"level": 15, "type":"souls",   "amount":  500, "label":"500 Душ"},
    {"level": 16, "type":"souls",   "amount":  500, "label":"500 Душ"},
    {"level": 17, "type":"isotope", "amount":    1, "label":"Нестабильный Изотоп"},
    {"level": 18, "type":"souls",   "amount":  600, "label":"600 Душ"},
    {"level": 19, "type":"boost",   "amount":    1, "label":"Буст тапов 3ч"},
    {"level": 20, "type":"skin",    "amount":    1, "label":"Скин Гомункула «Пламенный»"},
    {"level": 21, "type":"souls",   "amount":  700, "label":"700 Душ"},
    {"level": 22, "type":"souls",   "amount":  700, "label":"700 Душ"},
    {"level": 23, "type":"estus",   "amount":    5, "label":"Estus ×5"},
    {"level": 24, "type":"souls",   "amount":  800, "label":"800 Душ"},
    {"level": 25, "type":"souls",   "amount": 1000, "label":"1000 Душ"},
    {"level": 26, "type":"boost",   "amount":    1, "label":"Двойная реакция 24ч"},
    {"level": 27, "type":"souls",   "amount": 1000, "label":"1000 Душ"},
    {"level": 28, "type":"isotope", "amount":    2, "label":"Изотопы ×2"},
    {"level": 29, "type":"souls",   "amount": 1500, "label":"1500 Душ"},
    {"level": 30, "type":"title",   "amount":    1, "label":"Титул «Выживший» + 2000 душ"},
]


def get_season_progress(user_id: int, user_progress: dict) -> Dict[str, Any]:
    """Прогресс пользователя в Battle Pass текущего сезона."""
    st = user_progress.get(user_id, {})
    now = datetime.utcnow()

    try:
        ends = datetime.fromisoformat(CURRENT_SEASON["ends_at"])
        days_left = max(0, (ends - now).days)
        is_active = now <= ends
    except Exception:
        days_left = 0
        is_active = False

    bp_level = st.get("bp_level", 0)
    bp_xp    = st.get("bp_xp", 0)
    bp_xp_to_next = max(0, 100 - bp_xp % 100) if bp_level < 30 else 0
    claimed  = st.get("bp_claimed", [])

    claimable = [r for r in BATTLE_PASS_REWARDS
                 if r["level"] <= bp_level and r["level"] not in claimed]

    return {
        "season": CURRENT_SEASON,
        "days_left": days_left,
        "is_active": is_active,
        "bp_level": bp_level,
        "bp_xp": bp_xp % 100,
        "bp_xp_to_next": bp_xp_to_next,
        "bp_pct": bp_xp % 100,
        "claimable_count": len(claimable),
        "claimable": claimable,
        "claimed": claimed,
        "rewards": BATTLE_PASS_REWARDS,
        "next_reward": next((r for r in BATTLE_PASS_REWARDS if r["level"] > bp_level), None),
    }


def add_bp_xp(user_id: int, amount: int, user_progress: dict) -> Dict[str, Any]:
    """Начислить Battle Pass XP. 100 XP = 1 уровень BP."""
    st = user_progress.get(user_id, {})
    old_level = st.get("bp_level", 0)
    st["bp_xp"] = st.get("bp_xp", 0) + amount
    new_level = min(30, st["bp_xp"] // 100)
    st["bp_level"] = new_level
    leveled_up = new_level > old_level
    return {"bp_level": new_level, "leveled_up": leveled_up, "levels_gained": new_level - old_level}


def claim_bp_reward(user_id: int, level: int, user_progress: dict) -> Dict[str, Any]:
    """Забрать награду Battle Pass уровня."""
    st = user_progress.get(user_id, {})
    bp_level = st.get("bp_level", 0)
    claimed = st.setdefault("bp_claimed", [])

    if level > bp_level:
        return {"ok": False, "error": "level_not_reached"}
    if level in claimed:
        return {"ok": False, "error": "already_claimed"}

    reward = next((r for r in BATTLE_PASS_REWARDS if r["level"] == level), None)
    if not reward:
        return {"ok": False, "error": "reward_not_found"}

    claimed.append(level)
    rtype = reward["type"]
    now = datetime.utcnow()

    if rtype == "souls":
        st["souls"] = round(st.get("souls", 0) + reward["amount"], 1)
    elif rtype == "estus":
        st["estus_flasks"] = st.get("estus_flasks", 0) + reward["amount"]
    elif rtype == "boost":
        st["double_tap_until"] = (now + timedelta(hours=reward["amount"])).isoformat()
    elif rtype == "isotope":
        st["unstable_isotopes"] = st.get("unstable_isotopes", 0) + reward["amount"]
    elif rtype in ("frame", "skin", "title"):
        st.setdefault("owned_cosmetics", []).append(f"bp_s1_{rtype}")
        if rtype == "title":
            st["souls"] = round(st.get("souls", 0) + 2000, 1)

    return {"ok": True, "reward": reward, "label": reward["label"]}
