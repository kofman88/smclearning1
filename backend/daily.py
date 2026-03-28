"""
daily.py — Система ежедневных заданий SMC Learning.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from progress import get_user_state, save_progress, add_chm

# ── DAILY TEMPLATES ───────────────────────────────────────────────────────────

DAILY_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id":    "daily_quiz_3",
        "title": "Мастер квизов",
        "desc":  "Пройди 3 квиза",
        "icon":  "🧠",
        "type":  "quiz_count",
        "goal":  3,
        "reward": {"chm": 30, "bp_xp": 30},
    },
    {
        "id":    "daily_tap_5",
        "title": "Охотник зон",
        "desc":  "Правильно определи 5 зон на графике",
        "icon":  "🎯",
        "type":  "tap_correct",
        "goal":  5,
        "reward": {"chm": 25, "bp_xp": 25},
    },
    {
        "id":    "daily_lesson_1",
        "title": "Студент",
        "desc":  "Открой 1 урок",
        "icon":  "📖",
        "type":  "lesson_open",
        "goal":  1,
        "reward": {"chm": 15, "bp_xp": 15},
    },
    {
        "id":    "daily_combo_10",
        "title": "Комбо-мастер",
        "desc":  "Набери комбо ×10",
        "icon":  "⚡",
        "type":  "combo_reach",
        "goal":  10,
        "reward": {"chm": 20, "bp_xp": 20},
    },
    {
        "id":    "daily_streak_login",
        "title": "Верный ученик",
        "desc":  "Войди в приложение сегодня",
        "icon":  "🌅",
        "type":  "login",
        "goal":  1,
        "reward": {"chm": 10, "bp_xp": 10},
    },
]

# Bonus for completing ALL dailies
ALL_COMPLETE_BONUS = {"chm": 50, "bp_xp": 50}


# ── STATE HELPERS ─────────────────────────────────────────────────────────────

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _init_daily_state(state: Dict[str, Any]) -> None:
    """Ensure daily state is fresh for today."""
    today = _today_str()
    ds = state.setdefault("daily_quests", {})

    if ds.get("date") != today:
        # New day — reset progress
        state["daily_quests"] = {
            "date":     today,
            "progress": {t["id"]: 0 for t in DAILY_TEMPLATES},
            "claimed":  [],
            "all_bonus_claimed": False,
        }
    else:
        # Ensure all keys exist (back-compat)
        ds.setdefault("progress", {t["id"]: 0 for t in DAILY_TEMPLATES})
        ds.setdefault("claimed", [])
        ds.setdefault("all_bonus_claimed", False)
        for t in DAILY_TEMPLATES:
            ds["progress"].setdefault(t["id"], 0)


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def get_daily_quests(user_id: int) -> Dict[str, Any]:
    """Return daily quest list with current progress."""
    state = get_user_state(user_id)
    _init_daily_state(state)
    save_progress()

    ds = state["daily_quests"]
    quests = []
    for t in DAILY_TEMPLATES:
        prog  = ds["progress"].get(t["id"], 0)
        done  = prog >= t["goal"]
        claimed = t["id"] in ds["claimed"]
        quests.append({
            "id":      t["id"],
            "title":   t["title"],
            "desc":    t["desc"],
            "icon":    t["icon"],
            "goal":    t["goal"],
            "progress": min(prog, t["goal"]),
            "done":    done,
            "claimed": claimed,
            "reward":  t["reward"],
        })

    all_done = all(q["done"] for q in quests)
    return {
        "ok":                True,
        "date":              ds["date"],
        "quests":            quests,
        "all_done":          all_done,
        "all_bonus_claimed": ds.get("all_bonus_claimed", False),
        "all_bonus":         ALL_COMPLETE_BONUS,
    }


def update_daily_progress(user_id: int, event_type: str, value: int = 1) -> None:
    """
    Increment daily quest progress for matching event type.
    event_type: "quiz_count" | "tap_correct" | "lesson_open" | "combo_reach" | "login"
    value: for combo_reach pass the combo count; others default to 1.
    """
    state = get_user_state(user_id)
    _init_daily_state(state)
    ds = state["daily_quests"]

    for t in DAILY_TEMPLATES:
        if t["type"] != event_type:
            continue
        tid  = t["id"]
        goal = t["goal"]
        cur  = ds["progress"].get(tid, 0)

        if event_type == "combo_reach":
            # Track max combo reached
            ds["progress"][tid] = max(cur, value)
        else:
            if cur < goal:
                ds["progress"][tid] = min(cur + value, goal)

    save_progress()


def claim_daily_reward(user_id: int, quest_id: str) -> Dict[str, Any]:
    """Claim reward for a completed daily quest."""
    from season import add_bp_xp
    state = get_user_state(user_id)
    _init_daily_state(state)
    ds = state["daily_quests"]

    # Handle all-bonus claim
    if quest_id == "all_bonus":
        all_done = all(
            ds["progress"].get(t["id"], 0) >= t["goal"]
            for t in DAILY_TEMPLATES
        )
        if not all_done:
            return {"ok": False, "error": "not_all_complete"}
        if ds.get("all_bonus_claimed"):
            return {"ok": False, "error": "already_claimed"}
        ds["all_bonus_claimed"] = True
        chm = ALL_COMPLETE_BONUS["chm"]
        bp  = ALL_COMPLETE_BONUS.get("bp_xp", 0)
        add_chm(user_id, chm, source="daily_all_bonus")
        if bp:
            add_bp_xp(user_id, bp)
        save_progress()
        return {"ok": True, "chm": chm, "bp_xp": bp, "message": "Все задания выполнены! Бонус получен."}

    # Normal quest claim
    template = next((t for t in DAILY_TEMPLATES if t["id"] == quest_id), None)
    if not template:
        return {"ok": False, "error": "quest_not_found"}

    prog = ds["progress"].get(quest_id, 0)
    if prog < template["goal"]:
        return {"ok": False, "error": "not_complete"}
    if quest_id in ds["claimed"]:
        return {"ok": False, "error": "already_claimed"}

    ds["claimed"].append(quest_id)
    reward = template["reward"]
    chm = reward.get("chm", 0)
    bp  = reward.get("bp_xp", 0)
    add_chm(user_id, chm, source="daily_reward")
    if bp:
        add_bp_xp(user_id, bp)
    save_progress()

    return {"ok": True, "chm": chm, "bp_xp": bp, "quest_id": quest_id}
