import json
import logging
import os
import fcntl
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

_data_dir = Path(os.getenv("DATA_DIR", "."))
_data_dir.mkdir(parents=True, exist_ok=True)
PROGRESS_FILE = _data_dir / "progress_smc.json"

_save_scheduled = False

# ── CONSTANTS ────────────────────────────────────────────────────────────────
DEFAULT_DEADLINE_HOURS = 72   # 72 hours per module (the market doesn't wait)
MAX_EXTENSIONS = 1            # Only ONE extension per module — then full repurchase
DAILY_BONUS_XP = 20           # XP for daily login streak
REFERRAL_BONUS_XP = 300       # XP for inviting a friend

# Per-module penalty amounts (USD) — "биржевая комиссия за промедление"
MODULE_PENALTIES = {
    0: 0,   # Free module
    1: 3,
    2: 3,
    3: 5,
    4: 5,
    5: 5,
    6: 7,
    7: 7,
    8: 10,
    9: 10,
}
MODULE_FULL_REPURCHASE = {
    0: 0,
    1: 9,
    2: 9,
    3: 12,
    4: 12,
    5: 12,
    6: 15,
    7: 15,
    8: 19,
    9: 29,   # Final exam module
}

# ── SMC TRADER LEVELS — 7 levels from Observer to Market Architect ────────
SMC_LEVELS: List[Tuple[int, int, str]] = [
    (0,    1, "Наблюдатель рынка"),
    (300,  2, "Охотник за ликвидностью"),
    (700,  3, "Снайпер ордер-блоков"),
    (1300, 4, "SMC Практик"),
    (2100, 5, "Smart Money Инсайдер"),
    (3200, 6, "Институциональный призрак"),
    (5000, 7, "Архитектор рынка"),
]

# ── BADGES ───────────────────────────────────────────────────────────────────
BADGE_DEFS = {
    # ── Progress milestones ───────────────────────────────────────────────
    "first_blood":      {"title": "Первая кровь",             "icon": "🩸",
                         "desc": "Первый квиз пройден"},
    "module_3":         {"title": "Полпути",                  "icon": "🎯",
                         "desc": "Завершены 3 модуля"},
    "module_5":         {"title": "Середина пути",            "icon": "⚡",
                         "desc": "Завершены 5 модулей"},
    "chm_legend":       {"title": "Легенда CHM",              "icon": "🏆",
                         "desc": "Весь курс пройден"},
    "no_sleep":         {"title": "Без сна",                  "icon": "🌙",
                         "desc": "Модуль завершён за одну сессию"},

    # ── Discipline / deadline ─────────────────────────────────────────────
    "disciplined":      {"title": "Дисциплинированный трейдер","icon": "📐",
                         "desc": "Дедлайн выполнен вовремя"},
    "time_is_money":    {"title": "Время — деньги",           "icon": "⏰",
                         "desc": "Домашку сдал за первые 12 часов"},
    "never_late":       {"title": "Никогда не опаздываю",     "icon": "🚀",
                         "desc": "5 модулей без просрочки дедлайна"},

    # ── Knowledge / quiz ─────────────────────────────────────────────────
    "sniper":           {"title": "Снайпер",                  "icon": "🎯",
                         "desc": "10 квизов без единой ошибки"},
    "quiz_streak_5":    {"title": "5 квизов подряд",          "icon": "🔥",
                         "desc": "Пять правильных ответов подряд"},
    "perfect_quiz":     {"title": "Идеальный квиз",           "icon": "💎",
                         "desc": "Квиз сдан без ошибок с первого раза"},
    "liquidity_hunter": {"title": "Охотник ликвидности",      "icon": "🌊",
                         "desc": "Мастер sweep-уровней"},
    "ob_master":        {"title": "Мастер ордер-блоков",      "icon": "📦",
                         "desc": "3 задания по OB выполнены с первой попытки"},

    # ── Activity / streak ────────────────────────────────────────────────
    "streak_3":         {"title": "3 дня подряд",             "icon": "🌱",
                         "desc": "3 дня активности подряд"},
    "streak_7":         {"title": "Неделя без пропусков",     "icon": "🔥",
                         "desc": "7 дней активности подряд"},
    "streak_30":        {"title": "Железная воля",            "icon": "💪",
                         "desc": "30 дней активности подряд"},
    "streak_60":        {"title": "Легенда дисциплины",       "icon": "👑",
                         "desc": "60 дней активности подряд"},

    # ── Community ────────────────────────────────────────────────────────
    "ghost":            {"title": "Призрак",                  "icon": "👻",
                         "desc": "Топ-1% недели по XP"},
    "top_3":            {"title": "Пьедестал",                "icon": "🥉",
                         "desc": "Попал в топ-3 таблицы лидеров"},
    "referral_1":       {"title": "Вербовщик",                "icon": "👥",
                         "desc": "Пригласил первого друга"},
    "referral_5":       {"title": "Командир",                 "icon": "🎖️",
                         "desc": "Пригласил 5 друзей"},

    # ── Teacher awards (manual) ──────────────────────────────────────────
    "star_student":     {"title": "Звёздный студент",         "icon": "⭐",
                         "desc": "Отмечен преподавателем"},
    "best_analysis":    {"title": "Лучший анализ",            "icon": "📊",
                         "desc": "Лучшая домашняя работа недели"},
    "speed_trader":     {"title": "Скоростной трейдер",       "icon": "⚡",
                         "desc": "Выдан преподавателем за скорость"},

    # ── Boss / Souls system ───────────────────────────────────────────────
    "boss_0_clear":     {"title": "Убийца Структуры",         "icon": "⚔️",
                         "desc": "Побеждён Structure Breaker"},
    "boss_1_clear":     {"title": "Охотник Побеждён",         "icon": "🏹",
                         "desc": "Побеждён Liquidity Hunter"},
    "boss_2_clear":     {"title": "Мастер OB",                "icon": "🛡️",
                         "desc": "Побеждён OB Guardian"},
    "boss_3_clear":     {"title": "Видящий Фантом",           "icon": "👁️",
                         "desc": "Побеждён FVG Phantom"},
    "boss_0_flawless":  {"title": "Без смертей: Структура",   "icon": "💀",
                         "desc": "Босс модуля 1 — без единой смерти"},
    "boss_1_flawless":  {"title": "Без смертей: Ликвидность", "icon": "💀",
                         "desc": "Босс модуля 2 — без единой смерти"},
    "boss_2_flawless":  {"title": "Без смертей: OB",          "icon": "💀",
                         "desc": "Босс модуля 3 — без единой смерти"},
    "hollow_escaped":   {"title": "Вышел из Hollow",          "icon": "🔥",
                         "desc": "Оплатил выход из состояния Hollow"},
    "soul_retriever":   {"title": "Душесборщик",              "icon": "⚡",
                         "desc": "Подобрал упавшие души после поражения"},
    # Phase 4
    "invader_slayer":   {"title": "Охотник на вторжения",     "icon": "⚔️",
                         "desc": "Отразил вторжение за 30 минут"},
    "roulette_lucky":   {"title": "Удача Рынка",              "icon": "🎰",
                         "desc": "Выиграл в рулетке знаний x3"},
    "pvp_champion":     {"title": "Чемпион разметки",         "icon": "🏆",
                         "desc": "Победил в 5 PvP-битвах"},
    "darkwraith":       {"title": "Darkwraith",               "icon": "🌑",
                         "desc": "10 побед во вторжениях"},
}

user_progress: Dict[int, Dict[str, Any]] = {}


# ── LOAD / SAVE ───────────────────────────────────────────────────────────────

def load_progress():
    """Load user progress from JSON file with file locking."""
    global user_progress
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            user_progress = {int(k): v for k, v in data.items()}
            logger.info("Прогресс загружен: %d пользователей", len(user_progress))
        except Exception as e:
            logger.error("Ошибка загрузки прогресса: %s", e)
            user_progress = {}
    else:
        logger.info("Файл прогресса не найден, начинаем с нуля")


def save_progress():
    """Save user progress to JSON file with atomic write and file locking."""
    try:
        tmp = PROGRESS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(user_progress, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        tmp.replace(PROGRESS_FILE)
    except Exception as e:
        logger.error("Ошибка сохранения прогресса: %s", e)


# ── USER STATE ────────────────────────────────────────────────────────────────

def get_user_state(user_id: int) -> Dict[str, Any]:
    """Get or create user state dict. Ensures all fields exist via back-compat defaults."""
    if user_id not in user_progress:
        user_progress[user_id] = {
            "name": str(user_id),
            "xp": 0,
            "level": 1,
            "rank": "Наблюдатель рынка",
            "module_index": 0,
            "completed_quests": [],
            "active_quest": None,
            "homework_status": "idle",
            "module_deadline": None,
            "deadline_extensions": 0,
            "quiz_state": None,
            # ── Activity / streak ──
            "streak": 0,
            "last_active_date": None,
            "badges": [],
            "daily_bonus_claimed": None,
            "module_unlocked": [0],  # free module always unlocked
            # ── SOULS SYSTEM (Phase 1: Souls-like) ──
            "souls": 0,               # current souls balance
            "total_souls_earned": 0,  # all-time counter
            "dropped_souls": 0,       # souls on the ground after failure
            "dropped_souls_module_id": None,  # which module they dropped from
            "can_retrieve_souls": False,      # one retrieval attempt allowed
            "hollow_since": None,     # ISO datetime when hollow started (None = not hollow)
            "current_title": "Ликвидность",   # displayed title
            "ng_plus_level": 0,       # 0 = normal, 1 = NG+, 2 = NG++
            "estus_flasks": 3,        # hint charges (refill at bonfire)
            "estus_max": 3,           # max flask count
            "souls_module_earned": 0, # souls earned in current module (at stake)
        }
    state = user_progress[user_id]
    # Back-compat: ensure new fields on old user records
    state.setdefault("streak", 0)
    state.setdefault("last_active_date", None)
    state.setdefault("badges", [])
    state.setdefault("daily_bonus_claimed", None)
    state.setdefault("module_unlocked", [0])
    # Souls system back-compat
    state.setdefault("souls", 0)
    state.setdefault("total_souls_earned", 0)
    state.setdefault("dropped_souls", 0)
    state.setdefault("dropped_souls_module_id", None)
    state.setdefault("can_retrieve_souls", False)
    state.setdefault("hollow_since", None)
    state.setdefault("current_title", "Ликвидность")
    state.setdefault("ng_plus_level", 0)
    state.setdefault("estus_flasks", 3)
    state.setdefault("estus_max", 3)
    state.setdefault("souls_module_earned", 0)
    # Boss system back-compat
    state.setdefault("boss_attempts", [])
    state.setdefault("bonfire_rested", [])  # list of module_ids where bonfire was rested
    return state


# ── LEVELS & RANKS ────────────────────────────────────────────────────────────

def get_level_and_rank(xp: int) -> Tuple[int, str]:
    """Return (level, rank_name) for a given XP total."""
    level, rank = 1, "Наблюдатель рынка"
    for threshold, lvl, name in SMC_LEVELS:
        if xp >= threshold:
            level, rank = lvl, name
    return level, rank


def get_next_level_xp(current_xp: int) -> int:
    """Returns XP needed for next level. Returns -1 if max level."""
    for threshold, _lvl, _name in SMC_LEVELS:
        if threshold > current_xp:
            return threshold
    return -1


def add_xp(user_id: int, amount: int) -> Tuple[int, bool]:
    """Add XP to user, recalculate level/rank, save. Returns (new_level, leveled_up)."""
    state = get_user_state(user_id)
    old_level = state["level"]
    state["xp"] += amount
    new_level, new_rank = get_level_and_rank(state["xp"])
    state["level"] = new_level
    state["rank"] = new_rank
    save_progress()
    leveled_up = new_level > old_level
    return new_level, leveled_up


# ── STREAK SYSTEM ─────────────────────────────────────────────────────────────

def update_streak(user_id: int) -> Tuple[int, bool]:
    """Update daily login streak. Returns (streak_count, is_new_day)."""
    state = get_user_state(user_id)
    today = date.today().isoformat()
    last = state.get("last_active_date")

    if last == today:
        return state["streak"], False   # already visited today

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last == yesterday:
        state["streak"] = state.get("streak", 0) + 1
    else:
        state["streak"] = 1  # streak broken or first visit

    state["last_active_date"] = today

    streak = state["streak"]

    # Milestone badges & bonus XP
    if streak == 3 and "streak_3" not in state["badges"]:
        state["badges"].append("streak_3")
        state["xp"] += 30
        new_level, new_rank = get_level_and_rank(state["xp"])
        state["level"] = new_level
        state["rank"] = new_rank

    if streak == 7 and "streak_7" not in state["badges"]:
        state["badges"].append("streak_7")
        state["xp"] += 100          # bonus XP for 7-day streak
        new_level, new_rank = get_level_and_rank(state["xp"])
        state["level"] = new_level
        state["rank"] = new_rank

    if streak == 30 and "streak_30" not in state["badges"]:
        state["badges"].append("streak_30")
        state["xp"] += 500          # bonus XP for 30-day streak
        new_level, new_rank = get_level_and_rank(state["xp"])
        state["level"] = new_level
        state["rank"] = new_rank

    if streak == 60 and "streak_60" not in state["badges"]:
        state["badges"].append("streak_60")
        state["xp"] += 1000
        new_level, new_rank = get_level_and_rank(state["xp"])
        state["level"] = new_level
        state["rank"] = new_rank

    save_progress()
    return streak, True


def claim_daily_bonus(user_id: int) -> Tuple[int, bool]:
    """Claim daily bonus XP (+20 XP). Returns (xp_earned, was_new)."""
    state = get_user_state(user_id)
    today = date.today().isoformat()

    if state.get("daily_bonus_claimed") == today:
        return 0, False

    state["daily_bonus_claimed"] = today
    add_xp(user_id, DAILY_BONUS_XP)
    return DAILY_BONUS_XP, True


# ── DEADLINE SYSTEM ───────────────────────────────────────────────────────────

def set_module_deadline(state: Dict[str, Any], hours: int = DEFAULT_DEADLINE_HOURS):
    """Set 72-hour deadline for a module. Module 0 (free) gets no deadline."""
    if state.get("module_index", 0) == 0:
        state["module_deadline"] = None   # free module — no timer
        return
    deadline = datetime.utcnow() + timedelta(hours=hours)
    state["module_deadline"] = deadline.isoformat()
    state["deadline_extensions"] = 0     # reset extensions for new module


def is_deadline_expired(state: Dict[str, Any]) -> bool:
    """Check if the module deadline has passed."""
    dl = state.get("module_deadline")
    if not dl:
        return False
    try:
        return datetime.utcnow() > datetime.fromisoformat(dl)
    except Exception:
        return False


def get_deadline_hours_remaining(state: Dict[str, Any]) -> float:
    """Returns hours remaining until deadline. +inf if no deadline. Negative if expired."""
    dl = state.get("module_deadline")
    if not dl:
        return float("inf")
    try:
        remaining = datetime.fromisoformat(dl) - datetime.utcnow()
        return remaining.total_seconds() / 3600
    except Exception:
        return float("inf")


def apply_penalty_extension(state: Dict[str, Any]) -> bool:
    """Apply 48-hour penalty extension (first miss). Returns False if already extended."""
    if state.get("deadline_extensions", 0) >= MAX_EXTENSIONS:
        return False
    new_dl = datetime.utcnow() + timedelta(hours=48)
    state["module_deadline"] = new_dl.isoformat()
    state["deadline_extensions"] = state.get("deadline_extensions", 0) + 1
    return True


# ── BADGE SYSTEM ─────────────────────────────────────────────────────────────

def award_badge(user_id: int, badge_id: str) -> bool:
    """Award a badge. Returns True if newly awarded."""
    if badge_id not in BADGE_DEFS:
        return False
    state = get_user_state(user_id)
    if badge_id in state["badges"]:
        return False
    state["badges"].append(badge_id)
    save_progress()
    return True


# ── RESET ─────────────────────────────────────────────────────────────────────

def reset_user_progress(user_id: int):
    """Reset user course progress while preserving streak and badges."""
    state = get_user_state(user_id)
    streak = state.get("streak", 0)
    last_active = state.get("last_active_date")
    badges = state.get("badges", [])
    state.update({
        "xp": 0, "level": 1, "rank": "Наблюдатель рынка",
        "module_index": 0, "completed_quests": [],
        "active_quest": None, "homework_status": "idle",
        "module_deadline": None, "deadline_extensions": 0,
        "quiz_state": None,
        # Preserve streak and badges on reset
        "streak": streak,
        "last_active_date": last_active,
        "badges": badges,
        "daily_bonus_claimed": None,
        "module_unlocked": [0],
    })
    save_progress()


# ── LEADERBOARD ───────────────────────────────────────────────────────────────

def get_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Return top users sorted by XP descending."""
    entries = [
        {
            "user_id": uid,
            "name": st.get("name", str(uid)),
            "xp": st.get("xp", 0),
            "level": st.get("level", 1),
            "rank": st.get("rank", "Наблюдатель рынка"),
            "module": st.get("module_index", 0) + 1,
            "streak": st.get("streak", 0),
        }
        for uid, st in user_progress.items()
    ]
    return sorted(entries, key=lambda x: x["xp"], reverse=True)[:limit]


load_progress()


# ══════════════════════════════════════════════════════════════════════════════
# ── SOULS SYSTEM (Dark Souls × SMC)  ─────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# Streak → souls multiplier (like in Duolingo but darker)
_STREAK_MULTIPLIERS: List[Tuple[int, float]] = [
    (30, 5.0),  # 30+ days → x5
    (14, 3.0),  # 14+ days → x3
    (7,  2.0),  # 7+ days  → x2
    (3,  1.5),  # 3+ days  → x1.5
    (0,  1.0),  # default  → x1
]

# Souls per tap (base, before multiplier)
_SOULS_PER_TAP_BASE = 2
_SOULS_PER_TAP_COMBO5 = 5    # combo 5+
_SOULS_PER_TAP_COMBO2 = 3    # combo 2-4


# Title progression rules (applied in order; first matching rule wins)
TITLE_RULES: List[Tuple[str, str]] = [
    ("all_modules_flawless",  "Flawless"),      # all bosses no deaths
    ("ng_plus_2",             "Композитный Оператор"),
    ("ng_plus_1",             "Market Maker"),
    ("all_modules_done",      "Smart Money"),
    ("three_bosses",          "Начинающий трейдер"),
    ("one_module",            "Ретейл"),
    ("default",               "Ликвидность"),
]

HOLLOW_DAYS_THRESHOLD = 7
HOLLOW_PENALTY_DAYS   = 14  # if hollow > 14 days → lose 1 module level


def get_streak_multiplier(streak: int) -> float:
    """Return souls-per-tap multiplier based on current streak."""
    for threshold, mult in _STREAK_MULTIPLIERS:
        if streak >= threshold:
            return mult
    return 1.0


def add_souls(user_id: int, amount: int, *, source: str = "tap") -> Dict[str, Any]:
    """Award souls to user. Returns souls delta info."""
    if amount <= 0:
        return {"souls": 0, "delta": 0, "total": 0}

    state = get_user_state(user_id)
    mult  = get_streak_multiplier(state.get("streak", 0))
    # Hollow penalty: x0.5 if hollow
    if state.get("hollow_since"):
        mult *= 0.5

    awarded = round(amount * mult)
    state["souls"]               = state.get("souls", 0) + awarded
    state["total_souls_earned"]  = state.get("total_souls_earned", 0) + awarded
    # Track how many souls earned in current module (at stake for boss fights)
    state["souls_module_earned"] = state.get("souls_module_earned", 0) + awarded
    save_progress()
    return {"delta": awarded, "total": state["souls"], "multiplier": mult, "source": source}


def spend_souls(user_id: int, amount: int, *, reason: str = "purchase") -> Dict[str, Any]:
    """Spend souls. Returns {ok, delta, total} — fails if insufficient."""
    state  = get_user_state(user_id)
    current = state.get("souls", 0)
    if current < amount:
        return {"ok": False, "reason": "insufficient_souls", "have": current, "need": amount}
    state["souls"] = current - amount
    save_progress()
    return {"ok": True, "delta": -amount, "total": state["souls"], "reason": reason}


def drop_souls(user_id: int) -> Dict[str, Any]:
    """
    Player failed a module boss: drop all souls earned in this module.
    The souls land on the ground — one retrieval attempt is allowed.
    Returns the amount dropped.
    """
    state = get_user_state(user_id)
    earned_in_module = state.get("souls_module_earned", 0)
    if earned_in_module <= 0:
        return {"dropped": 0, "can_retrieve": False}

    # Transfer module earnings to "dropped" pool
    state["souls"]               = max(0, state.get("souls", 0) - earned_in_module)
    state["dropped_souls"]       = earned_in_module
    state["dropped_souls_module_id"] = state.get("module_index", 0)
    state["can_retrieve_souls"]  = True
    state["souls_module_earned"] = 0
    save_progress()
    return {"dropped": earned_in_module, "can_retrieve": True}


def retrieve_souls(user_id: int) -> Dict[str, Any]:
    """
    One-shot attempt to recover dropped souls (must retry the boss first).
    Returns amount recovered or 0 if not available.
    """
    state = get_user_state(user_id)
    if not state.get("can_retrieve_souls", False):
        return {"ok": False, "reason": "no_dropped_souls"}
    if state.get("dropped_souls", 0) <= 0:
        return {"ok": False, "reason": "nothing_to_retrieve"}

    recovered = state["dropped_souls"]
    state["souls"]              = state.get("souls", 0) + recovered
    state["total_souls_earned"] = state.get("total_souls_earned", 0) + recovered
    state["dropped_souls"]      = 0
    state["dropped_souls_module_id"] = None
    state["can_retrieve_souls"] = False
    save_progress()
    return {"ok": True, "recovered": recovered, "total": state["souls"]}


def burn_dropped_souls(user_id: int) -> int:
    """Permanently burn dropped souls (called when opportunity expires)."""
    state = get_user_state(user_id)
    burned = state.get("dropped_souls", 0)
    state["dropped_souls"]      = 0
    state["dropped_souls_module_id"] = None
    state["can_retrieve_souls"] = False
    save_progress()
    return burned


def use_estus_flask(user_id: int) -> Dict[str, Any]:
    """Use one Estus flask (hint charge). Returns {ok, remaining}."""
    state = get_user_state(user_id)
    flasks = state.get("estus_flasks", 3)
    if flasks <= 0:
        return {"ok": False, "remaining": 0, "reason": "no_flasks"}
    state["estus_flasks"] = flasks - 1
    save_progress()
    return {"ok": True, "remaining": state["estus_flasks"]}


def refill_estus(user_id: int) -> int:
    """Refill Estus flasks to max (called at bonfire checkpoint)."""
    state = get_user_state(user_id)
    max_flasks = state.get("estus_max", 3)
    state["estus_flasks"] = max_flasks
    # Also reset module earned souls (new module = new session)
    state["souls_module_earned"] = 0
    save_progress()
    return max_flasks


def check_hollow(user_id: int) -> Dict[str, Any]:
    """
    Check and update hollow status.
    User goes hollow after HOLLOW_DAYS_THRESHOLD days of inactivity.
    After HOLLOW_PENALTY_DAYS days of being hollow, lose 1 module level.
    """
    state = get_user_state(user_id)
    last_active = state.get("last_active_date")
    now = datetime.utcnow()

    # Determine days since last activity
    days_inactive = 0
    if last_active:
        try:
            last_dt = datetime.fromisoformat(last_active)
            days_inactive = (now - last_dt).days
        except Exception:
            pass

    hollow_since = state.get("hollow_since")
    was_hollow   = bool(hollow_since)
    became_hollow = False
    lost_level    = False

    if days_inactive >= HOLLOW_DAYS_THRESHOLD and not was_hollow:
        # User just went hollow
        state["hollow_since"] = now.isoformat()
        became_hollow = True
        save_progress()
    elif was_hollow and hollow_since:
        # Check hollow duration
        try:
            hollow_dt = datetime.fromisoformat(hollow_since)
            hollow_days = (now - hollow_dt).days
            if hollow_days >= HOLLOW_PENALTY_DAYS:
                # Lose 1 module level as penalty
                idx = state.get("module_index", 0)
                if idx > 0:
                    state["module_index"] = idx - 1
                    lost_level = True
                    # Reset hollow timer so penalty only applies once per cycle
                    state["hollow_since"] = now.isoformat()
                    save_progress()
        except Exception:
            pass

    return {
        "is_hollow":    bool(state.get("hollow_since")),
        "became_hollow": became_hollow,
        "lost_level":   lost_level,
        "days_inactive": days_inactive,
        "hollow_since": state.get("hollow_since"),
    }


def exit_hollow(user_id: int, souls_cost: int = 100) -> Dict[str, Any]:
    """Pay souls to exit hollow state. Returns {ok, ..}."""
    state = get_user_state(user_id)
    if not state.get("hollow_since"):
        return {"ok": False, "reason": "not_hollow"}
    result = spend_souls(user_id, souls_cost, reason="exit_hollow")
    if not result["ok"]:
        return result
    state["hollow_since"] = None
    save_progress()
    return {"ok": True, "souls_spent": souls_cost, "total_souls": result["total"]}


def update_title(user_id: int) -> str:
    """Recompute and persist user's display title. Returns new title."""
    state    = get_user_state(user_id)
    completed = set(state.get("completed_quests", []))
    bosses    = [q for q in completed if q.endswith("_boss")]
    modules   = state.get("module_index", 0)
    ng        = state.get("ng_plus_level", 0)

    # Determine title
    title = "Ликвидность"
    if ng >= 2:
        title = "Композитный Оператор"
    elif ng >= 1:
        title = "Market Maker"
    elif modules >= 9 and len(bosses) >= 9:
        title = "Smart Money"
    elif len(bosses) >= 3:
        title = "Начинающий трейдер"
    elif modules >= 1:
        title = "Ретейл"

    state["current_title"] = title
    save_progress()
    return title


def get_souls_state(user_id: int) -> Dict[str, Any]:
    """Return a souls summary for the user."""
    state = get_user_state(user_id)
    return {
        "souls":           state.get("souls", 0),
        "total_earned":    state.get("total_souls_earned", 0),
        "dropped_souls":   state.get("dropped_souls", 0),
        "can_retrieve":    state.get("can_retrieve_souls", False),
        "estus_flasks":    state.get("estus_flasks", 3),
        "estus_max":       state.get("estus_max", 3),
        "is_hollow":       bool(state.get("hollow_since")),
        "hollow_since":    state.get("hollow_since"),
        "current_title":   state.get("current_title", "Ликвидность"),
        "streak_mult":     get_streak_multiplier(state.get("streak", 0)),
        "ng_plus_level":   state.get("ng_plus_level", 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ── PET SYSTEM (SMC Fox companion) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# 20 pet levels — XP thresholds
PET_LEVEL_XP: List[int] = [
    0, 50, 120, 220, 350, 510, 700, 920, 1170, 1450,
    1760, 2100, 2470, 2870, 3300, 3760, 4250, 4770, 5320, 5900,
]

# Lesson completion → pet stat bonuses
LESSON_PET_EFFECTS: Dict[str, Dict[str, int]] = {
    # Module 1: Basics
    "what_is_smc":        {"happiness": 10, "hunger": 5},
    "timeframes":         {"happiness": 8,  "hunger": 5},
    "market_structure":   {"hunger": 15,    "health": 5},
    # Module 2: Liquidity
    "liquidity":          {"happiness": 15, "pet_xp": 10},
    "liquidity_pools":    {"happiness": 12, "hunger": 8},
    # Module 3: OB & FVG
    "order_blocks":       {"hunger": 20,    "health": 5,  "pet_xp": 15},
    "fvg":                {"health": 15,    "happiness": 8},
    # Module 4: Inducement
    "inducement":         {"happiness": 10, "hunger": 10},
    "stop_hunting":       {"health": 10,    "pet_xp": 10},
    # Module 5: Breakers
    "breaker_blocks":     {"hunger": 15,    "happiness": 10},
    "mitigation_blocks":  {"health": 12,    "pet_xp": 10},
    # Module 6: Entries
    "ote":                {"happiness": 12, "hunger": 12, "pet_xp": 15},
    "premium_discount":   {"health": 10,    "hunger": 10},
    # Module 7: Sessions
    "killzones":          {"happiness": 15, "pet_xp": 12},
    "amd_model":          {"hunger": 18,    "health": 8},
    "power_of_three":     {"happiness": 15, "pet_xp": 15},
    # Module 8: Risk
    "risk_management":    {"health": 20,    "happiness": 10, "pet_xp": 20},
    "psychology":         {"happiness": 20, "health": 15},
    # Module 9: Advanced
    "market_maker_model": {"hunger": 20,    "health": 10, "pet_xp": 25},
    "ict_2022_model":     {"happiness": 18, "pet_xp": 20},
    "live_trade_btc":     {"hunger": 15,    "happiness": 15, "pet_xp": 20},
    "live_trade_eth":     {"health": 15,    "happiness": 12, "pet_xp": 20},
    # Module 10: Exam / Certification
    "session_sweep_model":{"happiness": 20, "pet_xp": 25},
    "exam_overview":      {"hunger": 15,    "health": 10},
    "certification":      {"happiness": 30, "health": 20, "pet_xp": 50, "coins": 100},
}

_PET_DECAY_PER_HOUR = {"hunger": 3.0, "happiness": 2.5, "health": 1.0}
_COMBO_WINDOW_SECS = 5    # consecutive taps within this window count as combo
_MAX_COMBO = 10


def _default_pet() -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "hunger":          80,
        "happiness":       80,
        "health":          100,
        "pet_xp":          0,
        "pet_level":       1,
        "coins":           0,
        "last_updated":    now,
        "last_tap":        None,
        "tap_combo":       0,
        "tap_combo_start": None,
        "total_taps":      0,
    }


def decay_pet_stats(pet: Dict[str, Any]) -> Dict[str, Any]:
    """Apply time-based stat decay since last_updated. Modifies in-place."""
    now = datetime.utcnow()
    last = pet.get("last_updated")
    if last:
        try:
            delta_hours = (now - datetime.fromisoformat(last)).total_seconds() / 3600
            for stat, rate in _PET_DECAY_PER_HOUR.items():
                pet[stat] = max(0.0, pet.get(stat, 0) - rate * delta_hours)
        except Exception:
            pass
    pet["last_updated"] = now.isoformat()
    return pet


def _get_pet_level(pet_xp: int) -> int:
    level = 1
    for i, threshold in enumerate(PET_LEVEL_XP):
        if pet_xp >= threshold:
            level = i + 1
    return min(level, 20)


def get_pet_visual_state(pet: Dict[str, Any]) -> str:
    """Returns one of: idle | happy | hungry | sick | excited"""
    hp  = pet.get("health",    100)
    h   = pet.get("hunger",    100)
    hap = pet.get("happiness", 100)
    if hp < 30:
        return "sick"
    if h < 25:
        return "hungry"
    if hap > 80 and h > 70:
        return "excited"
    if hap > 55:
        return "happy"
    return "idle"


def get_pet_state(user_id: int) -> Dict[str, Any]:
    """Get full pet state with decay applied. Creates default pet if missing."""
    state = get_user_state(user_id)
    if "pet" not in state:
        state["pet"] = _default_pet()
    pet = state["pet"]
    for k, v in _default_pet().items():
        pet.setdefault(k, v)
    decay_pet_stats(pet)
    pet["pet_level"] = _get_pet_level(pet.get("pet_xp", 0))
    pet["visual_state"] = get_pet_visual_state(pet)
    lvl = pet["pet_level"]
    pet["next_level_xp"] = PET_LEVEL_XP[lvl] if lvl < 20 else None
    pet["current_level_xp"] = PET_LEVEL_XP[lvl - 1]
    save_progress()
    return pet


def pet_register_tap(user_id: int) -> Dict[str, Any]:
    """Register a pet tap. Returns tap result dict."""
    pet = get_pet_state(user_id)
    now = datetime.utcnow()

    last_tap = pet.get("tap_combo_start")
    combo_active = False
    if last_tap:
        try:
            elapsed = (now - datetime.fromisoformat(last_tap)).total_seconds()
            combo_active = elapsed <= _COMBO_WINDOW_SECS
        except Exception:
            pass

    if combo_active:
        pet["tap_combo"] = min(pet.get("tap_combo", 0) + 1, _MAX_COMBO)
    else:
        pet["tap_combo"] = 1
        pet["tap_combo_start"] = now.isoformat()

    pet["last_tap"] = now.isoformat()
    pet["total_taps"] = pet.get("total_taps", 0) + 1

    combo = pet["tap_combo"]
    xp_gain = max(1, round(1 + (combo - 1) * 0.5))

    # DATA UNITS awarded per tap (scaled by combo) — kept for pet system
    if combo >= 5:
        data_tap = 10
    elif combo >= 2:
        data_tap = 4
    else:
        data_tap = 2
    pet["coins"] = pet.get("coins", 0) + data_tap

    # ── SOULS per tap (Souls-like farm mechanic) ──────────────────────────
    if combo >= 5:
        souls_tap = _SOULS_PER_TAP_COMBO5
    elif combo >= 2:
        souls_tap = _SOULS_PER_TAP_COMBO2
    else:
        souls_tap = _SOULS_PER_TAP_BASE
    # add_souls handles multiplier (streak, hollow) and module tracking
    souls_result = add_souls(user_id, souls_tap, source="tap")

    pet["happiness"] = min(100, pet.get("happiness", 0) + 2)
    pet["pet_xp"]    = pet.get("pet_xp", 0) + xp_gain

    old_level = pet.get("pet_level", 1)
    new_level = _get_pet_level(pet["pet_xp"])
    pet["pet_level"] = new_level
    level_up = new_level > old_level

    # Milestone bonus coins (stacks on top of per-tap)
    coins_earned = 0
    total = pet["total_taps"]
    milestone_map = {100: 10, 500: 25, 1000: 50, 5000: 100}
    if total in milestone_map:
        coins_earned = milestone_map[total]
        pet["coins"] = pet.get("coins", 0) + coins_earned

    pet["visual_state"] = get_pet_visual_state(pet)
    save_progress()

    lvl = pet["pet_level"]
    return {
        "xp_gained":        xp_gain,
        "combo":            combo,
        "pet_xp":           pet["pet_xp"],
        "pet_level":        new_level,
        "level_up":         level_up,
        "coins_earned":     coins_earned,
        "data_awarded":     data_tap,
        "total_data":       pet["coins"],
        "coins":            pet["coins"],
        "visual_state":     pet["visual_state"],
        "hunger":           round(pet["hunger"]),
        "happiness":        round(pet["happiness"]),
        "health":           round(pet["health"]),
        "next_level_xp":    PET_LEVEL_XP[lvl] if lvl < 20 else None,
        "current_level_xp": PET_LEVEL_XP[lvl - 1],
        # Souls system
        "souls_earned":     souls_result.get("delta", 0),
        "total_souls":      souls_result.get("total", 0),
        "souls_multiplier": souls_result.get("multiplier", 1.0),
    }


def apply_lesson_pet_effect(user_id: int, lesson_key: str, score_pct: float = 100.0) -> Dict[str, Any]:
    """Apply pet bonuses when a quiz/lesson is completed."""
    effects = LESSON_PET_EFFECTS.get(lesson_key, {"happiness": 5})
    pet = get_pet_state(user_id)
    applied: Dict[str, int] = {}

    for stat, val in effects.items():
        if stat == "coins":
            pet["coins"] = pet.get("coins", 0) + val
            applied["coins"] = val
        elif stat == "pet_xp":
            bonus = max(1, round(val * score_pct / 100))
            pet["pet_xp"] = pet.get("pet_xp", 0) + bonus
            applied["pet_xp"] = bonus
        elif stat in ("hunger", "happiness", "health"):
            pet[stat] = min(100, pet.get(stat, 0) + val)
            applied[stat] = val

    old_level = pet.get("pet_level", 1)
    pet["pet_level"] = _get_pet_level(pet["pet_xp"])
    pet["visual_state"] = get_pet_visual_state(pet)
    save_progress()

    return {
        "applied":      applied,
        "pet_level":    pet["pet_level"],
        "level_up":     pet["pet_level"] > old_level,
        "visual_state": pet["visual_state"],
    }


def add_pet_coins(user_id: int, amount: int) -> int:
    """Add coins to pet wallet. Returns new total."""
    pet = get_pet_state(user_id)
    pet["coins"] = pet.get("coins", 0) + amount
    save_progress()
    return pet["coins"]


# ══════════════════════════════════════════════════════════════════════════════
# ── EVOLUTION SYSTEM ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

EVOLUTION_STAGES: List[Dict[str, Any]] = [
    {"stage": 1, "name": "Cell Cipher",    "emoji": "🧬",  "req": "Начало пути. Организм пробуждается."},
    {"stage": 2, "name": "Neural Cipher",  "emoji": "⚡",  "req": "Order Block протокол пройден"},
    {"stage": 3, "name": "Circuit Cipher", "emoji": "🔋",  "req": "OB + FVG + Market Structure"},
    {"stage": 4, "name": "Quantum Cipher", "emoji": "💠",  "req": "Стрик 7 дней исследований"},
    {"stage": 5, "name": "Shadow Cipher",  "emoji": "🌑",  "req": "5 Oracle-предсказаний подтверждено"},
    {"stage": 6, "name": "Apex Cipher",    "emoji": "💎",  "req": "Все модули + 30-дн. стрик"},
    {"stage": 7, "name": "Genesis Cipher", "emoji": "✨",  "req": "Топ-10 + абсолютный архитектор рынка"},
]


def _calc_evolution_stage(state: Dict[str, Any]) -> int:
    pet       = state.get("pet", {})
    completed = set(state.get("completed_quests", []))
    streak    = state.get("streak", 0)
    oracle_ok = pet.get("oracle_correct", 0)
    lb_rank   = state.get("leaderboard_rank", 9999)

    stage = 1

    if "m3_quiz" in completed:
        stage = 2

    if all(q in completed for q in ("m1_quiz", "m3_quiz", "m4_quiz")):
        stage = max(stage, 3)

    if streak >= 7:
        stage = max(stage, 4)

    if oracle_ok >= 5:
        stage = max(stage, 5)

    if streak >= 30 and len(completed) >= 27:
        stage = max(stage, 6)

    if lb_rank <= 10 and len(completed) >= 30 and oracle_ok >= 5:
        stage = max(stage, 7)

    return stage


def check_and_update_evolution(user_id: int) -> Dict[str, Any]:
    """Compute new evolution stage, persist, return result."""
    state     = get_user_state(user_id)
    pet       = state.setdefault("pet", {})
    new_stage = _calc_evolution_stage(state)
    old_stage = pet.get("evolution_stage", 1)

    pet["evolution_stage"] = new_stage
    evolved = new_stage > old_stage
    if evolved:
        save_progress()

    info = EVOLUTION_STAGES[new_stage - 1]
    nxt  = EVOLUTION_STAGES[new_stage] if new_stage < 7 else None
    return {
        "stage":      new_stage,
        "evolved":    evolved,
        "info":       info,
        "next_stage": nxt,
    }


# ── TRADER DNA ────────────────────────────────────────────────────────────────

def update_trader_dna(user_id: int, event: str, value: Any = 1) -> None:
    """
    Accumulate lightweight DNA signals.
    event: 'quiz_correct', 'quiz_wrong', 'tap', 'prediction_correct',
           'prediction_wrong', 'lesson_{key}'
    """
    state = get_user_state(user_id)
    dna   = state.setdefault("dna", {})

    if event == "quiz_correct":
        dna["quiz_correct"] = dna.get("quiz_correct", 0) + 1
    elif event == "quiz_wrong":
        dna["quiz_wrong"]   = dna.get("quiz_wrong", 0) + 1
    elif event == "tap":
        dna["total_taps"]   = dna.get("total_taps", 0) + 1
    elif event == "prediction_correct":
        dna["pred_correct"] = dna.get("pred_correct", 0) + 1
    elif event == "prediction_wrong":
        dna["pred_wrong"]   = dna.get("pred_wrong", 0) + 1
    elif event.startswith("lesson_"):
        key = event[7:]
        lessons = dna.setdefault("lessons_studied", {})
        lessons[key] = lessons.get(key, 0) + 1

    save_progress()


def get_trader_dna(user_id: int) -> Dict[str, Any]:
    state = get_user_state(user_id)
    dna   = state.get("dna", {})
    qc    = dna.get("quiz_correct", 0)
    qw    = dna.get("quiz_wrong",   0)
    pc    = dna.get("pred_correct", 0)
    pw    = dna.get("pred_wrong",   0)
    acc   = round(qc / (qc + qw) * 100) if (qc + qw) > 0 else None
    pred  = round(pc / (pc + pw) * 100) if (pc + pw) > 0 else None
    return {
        "quiz_accuracy":       acc,
        "prediction_accuracy": pred,
        "total_taps":          dna.get("total_taps", 0),
        "lessons_studied":     dna.get("lessons_studied", {}),
        "raw":                 dna,
    }
