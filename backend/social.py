"""
Phase 3 Social Systems:
  - Phantom Messages  (per-quest community hints with vote)
  - Daily Challenge   (scheduled at 09:00 MSK, streak tracking)
  - Clans             (group of ≤5, shared progress, collective hollow penalty)
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_data_dir = Path(os.getenv("DATA_DIR", "."))
_data_dir.mkdir(parents=True, exist_ok=True)

PHANTOMS_FILE     = _data_dir / "phantoms.json"
DAILY_FILE        = _data_dir / "daily_challenges.json"
CLANS_FILE        = _data_dir / "clans.json"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path, default) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            return default() if callable(default) else default
    return default() if callable(default) else default


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _msk_now() -> datetime:
    """Moscow time = UTC+3."""
    return _now_utc() + timedelta(hours=3)


# ─────────────────────────────────────────────────────────────────────────────
# PHANTOM MESSAGES
# ─────────────────────────────────────────────────────────────────────────────
# Storage: { quest_id: [ {id, user_id, username, text, votes_up, votes_down, voters: [uid]}, … ] }

MAX_PHANTOMS_PER_QUEST = 20   # keep newest 20
MAX_PHANTOM_LEN        = 200   # chars

def _load_phantoms() -> Dict[str, List[Dict]]:
    return _load_json(PHANTOMS_FILE, dict)

def _save_phantoms(data: Dict) -> None:
    _save_json(PHANTOMS_FILE, data)


def add_phantom(quest_id: str, user_id: int, username: str, text: str) -> Dict:
    """Leave a phantom message on a quest. Returns the created phantom."""
    text = text.strip()[:MAX_PHANTOM_LEN]
    if not text:
        raise ValueError("Empty phantom text")

    data = _load_phantoms()
    lst  = data.setdefault(quest_id, [])

    # One phantom per user per quest (replace existing)
    lst = [p for p in lst if p["user_id"] != user_id]

    phantom = {
        "id":         str(uuid.uuid4())[:8],
        "user_id":    user_id,
        "username":   username or "Призрак",
        "text":       text,
        "votes_up":   0,
        "votes_down": 0,
        "voters":     [],
        "created_at": _now_utc().isoformat(),
    }
    lst.append(phantom)

    # Keep newest MAX_PHANTOMS_PER_QUEST
    lst = sorted(lst, key=lambda x: x["created_at"])[-MAX_PHANTOMS_PER_QUEST:]
    data[quest_id] = lst
    _save_phantoms(data)
    return phantom


def vote_phantom(quest_id: str, phantom_id: str, user_id: int, vote: str) -> Dict:
    """vote: 'up' or 'down'. Each user can vote once per phantom."""
    data = _load_phantoms()
    lst  = data.get(quest_id, [])
    ph   = next((p for p in lst if p["id"] == phantom_id), None)
    if not ph:
        raise ValueError("Phantom not found")
    if user_id in ph["voters"]:
        raise ValueError("Already voted")
    if vote == "up":
        ph["votes_up"] += 1
    else:
        ph["votes_down"] += 1
    ph["voters"].append(user_id)
    data[quest_id] = lst
    _save_phantoms(data)
    return _phantom_public(ph)


def get_phantoms(quest_id: str, viewer_id: int) -> List[Dict]:
    """Return phantoms for a quest, excluding the viewer's own, sorted by score."""
    data = _load_phantoms()
    lst  = data.get(quest_id, [])
    # Exclude own phantom
    lst  = [p for p in lst if p["user_id"] != viewer_id]
    # Sort: votes_up - votes_down desc, then newest
    lst  = sorted(lst, key=lambda p: (p["votes_up"] - p["votes_down"], p["created_at"]), reverse=True)
    return [_phantom_public(p) for p in lst[:5]]  # top-5 visible at once


def _phantom_public(p: Dict) -> Dict:
    return {
        "id":         p["id"],
        "username":   p["username"],
        "text":       p["text"],
        "votes_up":   p["votes_up"],
        "votes_down": p["votes_down"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# DAILY CHALLENGE
# ─────────────────────────────────────────────────────────────────────────────
# Storage:
#   {
#     "challenges": { "2026-03-20": { question, options, correct_idx, quest_id, souls_reward } },
#     "completions": { user_id: { "2026-03-20": { completed, streak, souls_earned } } }
#   }

DAILY_SOUL_REWARDS = [50, 75, 100, 150, 200, 250, 500]   # indexed by streak day (7+ = 500)

# Hand-crafted pool of daily challenge questions (cycling)
DAILY_QUESTION_POOL = [
    {
        "question": "Что происходит после sweep уровня ликвидности?",
        "options":  ["Рынок продолжает тренд", "Рынок разворачивается после захвата ликвидности",
                     "Объём исчезает", "Спред расширяется навсегда"],
        "correct_idx": 1,
        "quest_id": "m1_quiz",
    },
    {
        "question": "Ордер-блок бычий — это ...",
        "options":  ["Последняя медвежья свеча перед импульсным движением вверх",
                     "Первая бычья свеча после дна",
                     "Зона поддержки на дневном графике",
                     "Крупный ордер на покупку в стакане"],
        "correct_idx": 0,
        "quest_id": "m2_quiz",
    },
    {
        "question": "Fair Value Gap (FVG) образуется когда ...",
        "options":  ["Три последовательных свечи, средняя не перекрыта тенями крайних",
                     "Цена пробивает уровень с объёмом",
                     "Спред увеличивается в два раза",
                     "Свеча закрывается выше открытия"],
        "correct_idx": 0,
        "quest_id": "m3_quiz",
    },
    {
        "question": "Change of Character (ChoCH) — сигнал ...",
        "options":  ["Продолжения тренда",
                     "Первого слома структуры, предвестник разворота",
                     "Входа по тренду",
                     "Закрытия позиции"],
        "correct_idx": 1,
        "quest_id": "m0_quiz",
    },
    {
        "question": "В концепции SMC Premium зона — это ...",
        "options":  ["Уровень Фибоначчи 0.618–0.786",
                     "Зона выше 50% предыдущего движения (0.0–0.5 по Фибо)",
                     "Верхняя четверть диапазона дня",
                     "Ордер-блок на часовом графике"],
        "correct_idx": 1,
        "quest_id": "m1_quiz",
    },
    {
        "question": "Liquidity Void отличается от FVG тем, что ...",
        "options":  ["Не заполняется никогда",
                     "Образован одной свечой с огромным телом, нет перекрытия теней",
                     "Формируется только на дневном таймфрейме",
                     "Возникает только в азиатскую сессию"],
        "correct_idx": 1,
        "quest_id": "m3_quiz",
    },
    {
        "question": "Institutional Order Flow (IOF) направлен вверх, когда ...",
        "options":  ["Цена делает HH и HL на старшем тайм-фрейме",
                     "RSI выше 50",
                     "MACD пересекает сигнальную линию",
                     "Объём превышает 20-дневную среднюю"],
        "correct_idx": 0,
        "quest_id": "m0_quiz",
    },
    {
        "question": "Mitigation Block — это ...",
        "options":  ["Ордер-блок, уже отработавший однажды",
                     "Блок, сформированный при высоком объёме",
                     "Зона консолидации перед пробоем",
                     "Нереализованный ордер маркет-мейкера"],
        "correct_idx": 0,
        "quest_id": "m2_quiz",
    },
    {
        "question": "Breaker Block возникает когда ...",
        "options":  ["Ордер-блок пробивается и превращается в Supply/Demand зону противоположного типа",
                     "Цена консолидируется на уровне поддержки 3 дня подряд",
                     "Объём резко падает на уровне",
                     "Свеча закрывается выше предыдущего максимума"],
        "correct_idx": 0,
        "quest_id": "m2_quiz",
    },
    {
        "question": "Optimal Trade Entry (OTE) по Фибоначчи — это зона ...",
        "options":  ["0.618–0.786 от импульсного движения",
                     "0.236–0.382 от коррекции",
                     "0.5 ровно",
                     "1.0–1.618 (экстensия)"],
        "correct_idx": 0,
        "quest_id": "m1_quiz",
    },
]


def _today_msk() -> str:
    return _msk_now().strftime("%Y-%m-%d")


def _load_daily() -> Dict:
    return _load_json(DAILY_FILE, lambda: {"challenges": {}, "completions": {}})


def _save_daily(data: Dict) -> None:
    _save_json(DAILY_FILE, data)


def get_daily_challenge(user_id: int) -> Dict:
    """Return today's challenge and the user's status."""
    data  = _load_daily()
    today = _today_msk()

    # Auto-generate today's challenge if missing
    if today not in data["challenges"]:
        import hashlib
        idx = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(DAILY_QUESTION_POOL)
        q   = DAILY_QUESTION_POOL[idx]
        data["challenges"][today] = {
            **q,
            "date":         today,
            "souls_reward": DAILY_SOUL_REWARDS[6],  # base; personalised below
        }
        _save_daily(data)

    challenge = data["challenges"][today]
    user_rec  = data["completions"].get(str(user_id), {})
    today_rec = user_rec.get(today, {})

    # Calculate streak
    streak = _calc_daily_streak(user_rec, today)
    reward = DAILY_SOUL_REWARDS[min(streak, len(DAILY_SOUL_REWARDS) - 1)]

    return {
        "date":        today,
        "question":    challenge["question"],
        "options":     challenge["options"],
        "quest_id":    challenge["quest_id"],
        "souls_reward": reward,
        "streak":      streak,
        "completed":   today_rec.get("completed", False),
        "correct":     today_rec.get("correct", None),
    }


def submit_daily_challenge(user_id: int, answer_idx: int) -> Dict:
    """Submit answer to today's challenge. Returns result + souls awarded."""
    from progress import add_souls  # import here to avoid circular

    data  = _load_daily()
    today = _today_msk()

    challenge = data["challenges"].get(today)
    if not challenge:
        raise ValueError("No challenge today")

    user_key  = str(user_id)
    user_rec  = data["completions"].setdefault(user_key, {})
    today_rec = user_rec.get(today, {})

    if today_rec.get("completed"):
        raise ValueError("Already completed today")

    streak     = _calc_daily_streak(user_rec, today)
    is_correct = (answer_idx == challenge["correct_idx"])
    souls_won  = 0

    if is_correct:
        souls_won = DAILY_SOUL_REWARDS[min(streak, len(DAILY_SOUL_REWARDS) - 1)]
        add_souls(user_id, souls_won, source="daily_challenge")

    user_rec[today] = {
        "completed":   True,
        "correct":     is_correct,
        "answer_idx":  answer_idx,
        "souls_earned": souls_won,
        "streak":      streak + (1 if is_correct else 0),
    }
    _save_daily(data)

    # Update streak on user progress record
    new_streak = streak + (1 if is_correct else 0)

    return {
        "correct":      is_correct,
        "correct_idx":  challenge["correct_idx"],
        "souls_won":    souls_won,
        "streak":       new_streak,
        "streak_bonus": souls_won > DAILY_SOUL_REWARDS[0],
    }


def _calc_daily_streak(user_rec: Dict, today: str) -> int:
    """Count consecutive completed days ending yesterday (today not yet counted)."""
    streak = 0
    msk    = _msk_now()
    for i in range(1, 31):
        day = (msk - timedelta(days=i)).strftime("%Y-%m-%d")
        rec = user_rec.get(day, {})
        if rec.get("correct"):
            streak += 1
        else:
            break
    return streak


# ─────────────────────────────────────────────────────────────────────────────
# CLANS
# ─────────────────────────────────────────────────────────────────────────────
# Storage:
#   {
#     "clans": { clan_id: { id, name, tag, members:[uid], souls_pool, created_at,
#                            hollow_count, penalty_applied_at } },
#     "memberships": { user_id: clan_id }
#   }

MAX_CLAN_MEMBERS  = 5
CLAN_SOULS_WEEKLY = 1000   # shared weekly target
HOLLOW_PENALTY_SOULS = 200  # souls drained from clan pool per hollow member per week


def _load_clans() -> Dict:
    return _load_json(CLANS_FILE, lambda: {"clans": {}, "memberships": {}})


def _save_clans(data: Dict) -> None:
    _save_json(CLANS_FILE, data)


def create_clan(user_id: int, name: str, tag: str) -> Dict:
    data = _load_clans()
    if str(user_id) in data["memberships"]:
        raise ValueError("Already in a clan")
    name = name.strip()[:30]
    tag  = tag.strip()[:5].upper()
    if not name or not tag:
        raise ValueError("Invalid name/tag")

    # Check tag uniqueness
    for c in data["clans"].values():
        if c["tag"] == tag:
            raise ValueError(f"Tag [{tag}] already taken")

    clan_id = str(uuid.uuid4())[:8]
    clan = {
        "id":                 clan_id,
        "name":               name,
        "tag":                tag,
        "leader_id":          user_id,
        "members":            [user_id],
        "souls_pool":         0,
        "weekly_souls":       0,
        "week_start":         _today_msk(),
        "created_at":         _now_utc().isoformat(),
        "hollow_count":       0,
        "penalty_applied_at": None,
    }
    data["clans"][clan_id]              = clan
    data["memberships"][str(user_id)]   = clan_id
    _save_clans(data)
    return _clan_public(clan, data)


def join_clan(user_id: int, tag: str) -> Dict:
    data = _load_clans()
    if str(user_id) in data["memberships"]:
        raise ValueError("Already in a clan")
    tag  = tag.strip().upper()
    clan = next((c for c in data["clans"].values() if c["tag"] == tag), None)
    if not clan:
        raise ValueError("Clan not found")
    if len(clan["members"]) >= MAX_CLAN_MEMBERS:
        raise ValueError("Clan is full")
    clan["members"].append(user_id)
    data["memberships"][str(user_id)] = clan["id"]
    _save_clans(data)
    return _clan_public(clan, data)


def leave_clan(user_id: int) -> Dict:
    data    = _load_clans()
    clan_id = data["memberships"].pop(str(user_id), None)
    if not clan_id:
        raise ValueError("Not in a clan")
    clan = data["clans"].get(clan_id)
    if clan:
        clan["members"] = [m for m in clan["members"] if m != user_id]
        if not clan["members"]:
            del data["clans"][clan_id]  # disband empty clan
        elif clan.get("leader_id") == user_id and clan["members"]:
            clan["leader_id"] = clan["members"][0]  # pass leadership
    _save_clans(data)
    return {"ok": True, "clan_disbanded": clan_id not in data["clans"]}


def get_user_clan(user_id: int) -> Optional[Dict]:
    data    = _load_clans()
    clan_id = data["memberships"].get(str(user_id))
    if not clan_id:
        return None
    clan = data["clans"].get(clan_id)
    if not clan:
        return None
    return _clan_public(clan, data)


def contribute_souls_to_clan(user_id: int, amount: int) -> Dict:
    """Contribute souls from user to clan pool (deducted from user by caller)."""
    data    = _load_clans()
    clan_id = data["memberships"].get(str(user_id))
    if not clan_id:
        raise ValueError("Not in a clan")
    clan = data["clans"][clan_id]
    clan["souls_pool"]   += amount
    clan["weekly_souls"] += amount
    _save_clans(data)
    return _clan_public(clan, data)


def apply_hollow_clan_penalty(user_id: int) -> int:
    """Called when a member goes hollow. Drains souls from clan pool."""
    data    = _load_clans()
    clan_id = data["memberships"].get(str(user_id))
    if not clan_id:
        return 0
    clan   = data["clans"][clan_id]
    drain  = min(HOLLOW_PENALTY_SOULS, clan["souls_pool"])
    clan["souls_pool"] = max(0, clan["souls_pool"] - drain)
    clan["hollow_count"] = clan.get("hollow_count", 0) + 1
    _save_clans(data)
    logger.info("Clan %s penalised %d souls (member %d went hollow)", clan_id, drain, user_id)
    return drain


def list_clans(limit: int = 20) -> List[Dict]:
    data = _load_clans()
    clans = sorted(data["clans"].values(), key=lambda c: c["souls_pool"], reverse=True)[:limit]
    return [_clan_public(c, data) for c in clans]


def _clan_public(clan: Dict, data: Dict) -> Dict:
    return {
        "id":           clan["id"],
        "name":         clan["name"],
        "tag":          clan["tag"],
        "leader_id":    clan.get("leader_id"),
        "members":      clan["members"],
        "member_count": len(clan["members"]),
        "souls_pool":   clan["souls_pool"],
        "weekly_souls": clan.get("weekly_souls", 0),
        "weekly_target": CLAN_SOULS_WEEKLY,
        "progress_pct": min(100, round(clan.get("weekly_souls", 0) / CLAN_SOULS_WEEKLY * 100)),
        "hollow_count": clan.get("hollow_count", 0),
        "created_at":   clan["created_at"],
    }


def get_clan_leaderboard(limit: int = 10) -> List[Dict]:
    return list_clans(limit)


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI ROUTER
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/social", tags=["social"])


# ── Phantom request models ────────────────────────────────────────────────────

class PhantomCreateRequest(BaseModel):
    user_id:  int
    username: Optional[str] = None
    text:     str


class PhantomVoteRequest(BaseModel):
    user_id: int
    vote:    str  # "up" or "down"


# ── Daily request models ──────────────────────────────────────────────────────

class DailySubmitRequest(BaseModel):
    user_id:    int
    answer_idx: int


# ── Clan request models ───────────────────────────────────────────────────────

class ClanCreateRequest(BaseModel):
    user_id: int
    name:    str
    tag:     str


class ClanJoinRequest(BaseModel):
    user_id: int
    tag:     str


class ClanLeaveRequest(BaseModel):
    user_id: int


class ClanContributeRequest(BaseModel):
    user_id: int
    amount:  int


# ── Phantom endpoints ─────────────────────────────────────────────────────────

@router.get("/phantoms/{quest_id}")
async def api_get_phantoms(quest_id: str, user_id: int):
    return {"ok": True, "phantoms": get_phantoms(quest_id, user_id)}


@router.post("/phantoms/{quest_id}")
async def api_add_phantom(quest_id: str, req: PhantomCreateRequest):
    try:
        ph = add_phantom(quest_id, req.user_id, req.username or "", req.text)
        return {"ok": True, "phantom": _phantom_public(ph)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/phantoms/{quest_id}/{phantom_id}/vote")
async def api_vote_phantom(quest_id: str, phantom_id: str, req: PhantomVoteRequest):
    if req.vote not in ("up", "down"):
        raise HTTPException(400, "vote must be 'up' or 'down'")
    try:
        ph = vote_phantom(quest_id, phantom_id, req.user_id, req.vote)
        return {"ok": True, "phantom": ph}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Daily challenge endpoints ─────────────────────────────────────────────────

@router.get("/daily")
async def api_get_daily(user_id: int):
    ch = get_daily_challenge(user_id)
    return {"ok": True, **ch}


@router.post("/daily/submit")
async def api_submit_daily(req: DailySubmitRequest):
    try:
        result = submit_daily_challenge(req.user_id, req.answer_idx)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── Clan endpoints ────────────────────────────────────────────────────────────

@router.get("/clans")
async def api_list_clans():
    return {"ok": True, "clans": get_clan_leaderboard()}


@router.get("/clans/me")
async def api_my_clan(user_id: int):
    clan = get_user_clan(user_id)
    return {"ok": True, "clan": clan}


@router.post("/clans/create")
async def api_create_clan(req: ClanCreateRequest):
    try:
        clan = create_clan(req.user_id, req.name, req.tag)
        return {"ok": True, "clan": clan}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/clans/join")
async def api_join_clan(req: ClanJoinRequest):
    try:
        clan = join_clan(req.user_id, req.tag)
        return {"ok": True, "clan": clan}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/clans/leave")
async def api_leave_clan(req: ClanLeaveRequest):
    try:
        result = leave_clan(req.user_id)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(400, str(e))


# ── CLAN RAID ─────────────────────────────────────────────────────────────────

RAID_FILE = _data_dir / "raid_state.json"

RAID_BOSSES = [
    {"id": "rb_vol",  "name": "Босс Волатильности", "hp": 10000, "icon": "⚡",
     "question": "Цена создала False Breakout выше Equal Highs и вернулась. Это...",
     "answer": "Inducement + liquidity sweep. Ищи OB или FVG в зоне возврата для шорта.",
     "souls_reward": 200, "xp_reward": 100},
    {"id": "rb_flat", "name": "Босс Флета",          "hp":  8000, "icon": "❄️",
     "question": "BTC 6 часов в диапазоне. Как определить куда пойдёт цена на выходе?",
     "answer": "Смотри на сторону накопленной ликвидности (EQH или EQL) — туда и пойдёт sweep перед реальным движением.",
     "souls_reward": 150, "xp_reward": 75},
    {"id": "rb_bos",  "name": "Босс BOS",            "hp": 12000, "icon": "💀",
     "question": "На H4 произошёл CHoCH вниз. Что делаешь дальше?",
     "answer": "Ждёшь первый pullback на медвежий OB или FVG на H1/M15. Входишь шорт с SL выше CHoCH и целью на SSL.",
     "souls_reward": 300, "xp_reward": 150},
]


def get_raid_status() -> dict:
    return _load_json(RAID_FILE, {"active": False})


def _save_raid(data: dict) -> None:
    _save_json(RAID_FILE, data)


def start_weekly_raid(boss_id: str = None) -> dict:
    """Запустить еженедельный рейд."""
    import random
    import datetime as _dtime
    boss = next((b for b in RAID_BOSSES if b["id"] == boss_id), None) if boss_id else random.choice(RAID_BOSSES)
    now = _now_utc()
    raid = {
        "active": True,
        "boss": boss,
        "hp_current": boss["hp"],
        "hp_max": boss["hp"],
        "started_at": now.isoformat(),
        "ends_at": (now + _dtime.timedelta(days=7)).isoformat(),
        "participants": {},
        "top_clans": {},
    }
    _save_raid(raid)
    return raid


def raid_attack(user_id: int, user_level: int, clan_id: str, is_correct: bool) -> dict:
    """Атака рейд-босса."""
    import datetime as _dtime
    raid = get_raid_status()
    if not raid.get("active"):
        return {"ok": False, "error": "no_active_raid"}

    try:
        ends = _dtime.datetime.fromisoformat(raid["ends_at"]).replace(tzinfo=None)
        if _dtime.datetime.utcnow() > ends:
            return {"ok": False, "error": "raid_expired"}
    except Exception:
        pass

    uid_str = str(user_id)
    if raid.get("participants", {}).get(uid_str, {}).get("answered"):
        return {"ok": False, "error": "already_answered"}

    damage = user_level * 10 if is_correct else user_level * 2
    raid["hp_current"] = max(0, raid["hp_current"] - damage)
    raid.setdefault("participants", {})[uid_str] = {
        "clan_id": clan_id, "damage": damage, "answered": True,
        "is_correct": is_correct, "at": _now_utc().isoformat(),
    }

    if clan_id:
        raid.setdefault("top_clans", {})[clan_id] = raid["top_clans"].get(clan_id, 0) + damage

    boss_defeated = raid["hp_current"] <= 0
    if boss_defeated:
        raid["active"] = False
        raid["defeated_at"] = _now_utc().isoformat()

    _save_raid(raid)

    return {
        "ok": True,
        "damage": damage,
        "is_correct": is_correct,
        "hp_current": raid["hp_current"],
        "hp_max": raid["hp_max"],
        "hp_pct": round(raid["hp_current"] / raid["hp_max"] * 100) if raid["hp_max"] > 0 else 0,
        "boss_defeated": boss_defeated,
        "souls_reward": raid["boss"]["souls_reward"] if is_correct else 0,
        "xp_reward": raid["boss"]["xp_reward"] if is_correct else 0,
    }


@router.post("/clans/contribute")
async def api_contribute_souls(req: ClanContributeRequest):
    from progress import spend_souls
    if req.amount <= 0:
        raise HTTPException(400, "amount must be positive")
    spend_result = spend_souls(req.user_id, req.amount, reason="clan_contribution")
    if not spend_result["ok"]:
        raise HTTPException(400, spend_result.get("error", "Insufficient souls"))
    try:
        clan = contribute_souls_to_clan(req.user_id, req.amount)
        return {"ok": True, "clan": clan, "souls_remaining": spend_result["souls"]}
    except ValueError as e:
        raise HTTPException(400, str(e))
