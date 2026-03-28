"""
loot.py — Система лута и инвентарь SMC Learning.
"""
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from progress import get_user_state, save_progress

# ── RARITY TABLE ─────────────────────────────────────────────────────────────

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]

RARITY_WEIGHTS = {
    "default": {"common": 60, "uncommon": 25, "rare": 10, "epic": 4, "legendary": 1},
    "boss":    {"common": 30, "uncommon": 32, "rare": 25, "epic": 10, "legendary": 3},
}

RARITY_COLORS = {
    "common":    "#94a3b8",
    "uncommon":  "#10b981",
    "rare":      "#3b82f6",
    "epic":      "#a855f7",
    "legendary": "#f59e0b",
}

# ── ITEM DEFINITIONS ─────────────────────────────────────────────────────────

ITEMS: Dict[str, Dict[str, Any]] = {
    # ── Common ───────────────────────────────────────────────────────────────
    "scroll_xp":    {"name": "Свиток знаний",   "icon": "📜", "rarity": "common",
                     "desc": "+5% XP на 1 час", "type": "boost",
                     "effect": {"type": "xp_boost", "value": 0.05, "duration_h": 1}},
    "potion_chm10": {"name": "Зелье CHM",       "icon": "💧", "rarity": "common",
                     "desc": "+10 CHM немедленно", "type": "consumable",
                     "effect": {"type": "chm_instant", "value": 10}},
    "combo_shard":  {"name": "Осколок комбо",   "icon": "🔷", "rarity": "common",
                     "desc": "Комбо не сбрасывается 1 раз", "type": "consumable",
                     "effect": {"type": "combo_shield", "value": 1}},

    # ── Uncommon ─────────────────────────────────────────────────────────────
    "lens_tf":      {"name": "Линза Таймфрейма", "icon": "🔭", "rarity": "uncommon",
                     "desc": "Подсказка на следующем квизе", "type": "consumable",
                     "effect": {"type": "quiz_hint", "value": 1}},
    "potion_chm50": {"name": "Большое зелье CHM","icon": "⚗️", "rarity": "uncommon",
                     "desc": "+50 CHM немедленно", "type": "consumable",
                     "effect": {"type": "chm_instant", "value": 50}},
    "zone_magnet":  {"name": "Магнит зон",       "icon": "🧲", "rarity": "uncommon",
                     "desc": "Зоны подсвечены на следующем графике", "type": "consumable",
                     "effect": {"type": "zone_hint", "value": 1}},

    # ── Rare ─────────────────────────────────────────────────────────────────
    "artifact_class":{"name": "Артефакт класса","icon": "💎", "rarity": "rare",
                     "desc": "Бонус класса +50% на 24ч", "type": "consumable",
                     "effect": {"type": "class_boost", "value": 0.5, "duration_h": 24}},
    "spare_flask":  {"name": "Запасная фласка",  "icon": "🏺", "rarity": "rare",
                     "desc": "+1 подсказка (CHM фласка)", "type": "consumable",
                     "effect": {"type": "flask_charge", "value": 1}},
    "elixir_actions":{"name": "Эликсир действий","icon": "⚡","rarity": "rare",
                     "desc": "+5 действий прямо сейчас", "type": "consumable",
                     "effect": {"type": "actions_boost", "value": 5}},

    # ── Epic ─────────────────────────────────────────────────────────────────
    "skin_flame":   {"name": "Скин «Пламя»",    "icon": "🔥", "rarity": "epic",
                     "desc": "Огненная аура гомункула", "type": "cosmetic",
                     "effect": {"type": "skin", "value": "flame"}},
    "skin_ice":     {"name": "Скин «Лёд»",      "icon": "❄️", "rarity": "epic",
                     "desc": "Ледяная аура гомункула", "type": "cosmetic",
                     "effect": {"type": "skin", "value": "ice"}},
    "double_loot":  {"name": "Двойной лут",     "icon": "🎲", "rarity": "epic",
                     "desc": "Двойной лут 24ч", "type": "consumable",
                     "effect": {"type": "loot_boost", "value": 2.0, "duration_h": 24}},

    # ── Legendary ────────────────────────────────────────────────────────────
    "title_master": {"name": "Титул «Мастер SMC»","icon": "👑","rarity": "legendary",
                     "desc": "Уникальный золотой титул", "type": "cosmetic",
                     "effect": {"type": "title", "value": "master_smc"}},
    "seal_alchemist":{"name":"Печать Алхимика",  "icon": "🔮","rarity": "legendary",
                     "desc": "+10% перманентный множитель CHM", "type": "permanent",
                     "effect": {"type": "chm_perm_mult", "value": 0.10}},
}

# Organize items by rarity
_BY_RARITY: Dict[str, List[str]] = {r: [] for r in RARITIES}
for _iid, _idef in ITEMS.items():
    _BY_RARITY[_idef["rarity"]].append(_iid)


# ── ROLL LOOT ────────────────────────────────────────────────────────────────

def roll_loot(user_id: int, source: str, difficulty_mult: float = 1.0,
              rarity_floor: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Roll for a loot drop.
    source: "quiz", "boss", "daily", "tap_combo_10", "tap_combo_20", "lesson_complete"
    difficulty_mult: boss=2.0 for shifted chances

    Returns loot dict or None if no drop.
    """
    # Base chance to get any loot (not 100% — adds excitement)
    # BP sources are guaranteed (rarity_floor set)
    if rarity_floor:
        base_chance = 1.0
    else:
        base_chance = {
            "quiz":            0.35,
            "boss":            0.85,
            "daily":           0.60,
            "tap_combo_10":    0.50,
            "tap_combo_20":    0.80,
            "lesson_complete": 0.20,
        }.get(source, 0.25)

    if random.random() > base_chance:
        return None  # no loot this time

    # Apply loot boost effect if active
    state = get_user_state(user_id)
    _clean_expired_effects(state)
    active = state.get("active_effects", [])
    loot_mult = 1.0
    for eff in active:
        if eff.get("type") == "loot_boost":
            loot_mult = eff.get("value", 1.0)
            break

    # Select rarity
    weights_key = "boss" if source == "boss" else "default"
    w = RARITY_WEIGHTS[weights_key].copy()
    # Shift towards better loot with high difficulty_mult
    if difficulty_mult > 1.0:
        shift = int((difficulty_mult - 1.0) * 10)
        w["common"]    = max(5, w["common"] - shift * 3)
        w["uncommon"]  = max(10, w["uncommon"] - shift)
        w["rare"]      = w["rare"] + shift * 2
        w["epic"]      = w["epic"] + shift
        w["legendary"] = w["legendary"] + max(0, shift - 1)

    # Apply loot_mult by re-weighting rarer tiers
    if loot_mult > 1.0:
        for r in ["rare", "epic", "legendary"]:
            w[r] = int(w[r] * loot_mult)

    rarity = random.choices(RARITIES, weights=[w[r] for r in RARITIES], k=1)[0]

    # Enforce rarity floor (for BP guaranteed drops)
    if rarity_floor and RARITIES.index(rarity) < RARITIES.index(rarity_floor):
        rarity = rarity_floor

    candidates = _BY_RARITY.get(rarity, [])
    if not candidates:
        candidates = _BY_RARITY.get("common", list(ITEMS.keys()))

    item_id = random.choice(candidates)
    item_def = ITEMS[item_id]

    # Add to inventory
    inv = state.setdefault("inventory", [])
    existing = next((x for x in inv if x["item_id"] == item_id), None)
    if existing:
        existing["quantity"] = existing.get("quantity", 1) + 1
    else:
        inv.append({"item_id": item_id, "quantity": 1, "obtained_at": datetime.utcnow().isoformat()})

    save_progress()

    return {
        "item_id": item_id,
        "rarity":  rarity,
        "name":    item_def["name"],
        "icon":    item_def["icon"],
        "desc":    item_def["desc"],
        "color":   RARITY_COLORS[rarity],
    }


# ── INVENTORY ────────────────────────────────────────────────────────────────

def get_inventory(user_id: int) -> Dict[str, Any]:
    """Return full inventory with item details + active effects."""
    state = get_user_state(user_id)
    _clean_expired_effects(state)
    save_progress()

    raw_inv = state.get("inventory", [])
    enriched = []
    for entry in raw_inv:
        iid = entry.get("item_id")
        if not iid or iid not in ITEMS:
            continue
        idef = ITEMS[iid]
        enriched.append({
            **entry,
            "name":     idef["name"],
            "icon":     idef["icon"],
            "rarity":   idef["rarity"],
            "desc":     idef["desc"],
            "type":     idef["type"],
            "color":    RARITY_COLORS[idef["rarity"]],
            "usable":   idef["type"] in ("consumable",),
        })

    active = []
    for eff in state.get("active_effects", []):
        active.append({**eff})

    return {
        "ok":            True,
        "inventory":     enriched,
        "active_effects": active,
        "item_count":    len(enriched),
    }


# ── USE ITEM ─────────────────────────────────────────────────────────────────

def use_item(user_id: int, item_id: str) -> Dict[str, Any]:
    """Activate an item. Returns result dict."""
    from progress import add_chm, get_user_state
    state = get_user_state(user_id)

    if item_id not in ITEMS:
        return {"ok": False, "error": "item_not_found"}

    inv = state.get("inventory", [])
    entry = next((x for x in inv if x["item_id"] == item_id), None)
    if not entry or entry.get("quantity", 0) < 1:
        return {"ok": False, "error": "not_in_inventory"}

    item_def = ITEMS[item_id]
    if item_def["type"] not in ("consumable",):
        return {"ok": False, "error": "not_usable"}

    # Consume 1
    entry["quantity"] -= 1
    if entry["quantity"] <= 0:
        inv.remove(entry)

    effect = item_def["effect"]
    eff_type = effect["type"]
    result_data: Dict[str, Any] = {"applied": eff_type}

    now = datetime.utcnow()

    if eff_type == "chm_instant":
        add_chm(user_id, effect["value"], source="item_use")
        result_data["chm_gained"] = effect["value"]

    elif eff_type == "quiz_hint":
        state["chm_flasks"] = min(
            state.get("chm_flasks_max", 3),
            state.get("chm_flasks", 0) + effect["value"]
        )

    elif eff_type == "flask_charge":
        state["chm_flasks"] = min(
            state.get("chm_flasks_max", 3) + 1,
            state.get("chm_flasks", 0) + effect["value"]
        )

    elif eff_type == "actions_boost":
        from progress import user_progress
        hom = state.setdefault("homunculus", {})
        # Grant extra actions by reducing used count
        used = state.get("actions_used", 0)
        state["actions_used"] = max(0, used - effect["value"])

    elif eff_type in ("xp_boost", "combo_shield", "zone_hint", "class_boost", "loot_boost"):
        expires_at = None
        if "duration_h" in effect:
            expires_at = (now + timedelta(hours=effect["duration_h"])).isoformat()
        active = state.setdefault("active_effects", [])
        # Remove existing same-type effect
        state["active_effects"] = [e for e in active if e.get("type") != eff_type]
        state["active_effects"].append({
            "type":       eff_type,
            "value":      effect["value"],
            "expires_at": expires_at,
            "item_id":    item_id,
            "applied_at": now.isoformat(),
        })

    elif eff_type == "chm_perm_mult":
        state["chm_perm_mult"] = round(state.get("chm_perm_mult", 0) + effect["value"], 3)

    save_progress()
    return {
        "ok":      True,
        "item_id": item_id,
        "name":    item_def["name"],
        "icon":    item_def["icon"],
        **result_data,
    }


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _clean_expired_effects(state: Dict[str, Any]) -> None:
    """Remove expired active effects in-place."""
    now = datetime.utcnow()
    active = state.get("active_effects", [])
    cleaned = []
    for eff in active:
        exp = eff.get("expires_at")
        if not exp:
            cleaned.append(eff)
            continue
        try:
            if datetime.fromisoformat(exp) > now:
                cleaned.append(eff)
        except Exception:
            cleaned.append(eff)
    state["active_effects"] = cleaned
