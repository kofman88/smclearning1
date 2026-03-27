import json
import logging
import os
from pathlib import Path

try:
    import fcntl
    def _lock_file(f, exclusive=False):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    def _unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
except ImportError:
    def _lock_file(f, exclusive=False): pass
    def _unlock_file(f): pass
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
                _lock_file(f, exclusive=False)
                try:
                    data = json.load(f)
                finally:
                    _unlock_file(f)
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
            _lock_file(f, exclusive=True)
            try:
                json.dump(user_progress, f, ensure_ascii=False, indent=2)
            finally:
                _unlock_file(f)
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
            # ── CHM SYSTEM (Phase 1: Souls-like) ──
            "chm": 0,                    # current CHM balance
            "chm_total_earned": 0,       # all-time counter
            "chm_total_burned": 0,       # all-time burned counter
            "chm_total_spent": 0,        # spent in shop
            "chm_dropped": 0,            # CHM on the ground after failure
            "chm_dropped_module_id": None,  # which module they dropped from
            "chm_can_retrieve": False,      # one retrieval attempt allowed
            "hollow_since": None,     # ISO datetime when hollow started (None = not hollow)
            "current_title": "Ликвидность",   # displayed title
            "ng_plus_level": 0,       # 0 = normal, 1 = NG+, 2 = NG++
            "chm_flasks": 3,             # hint charges (refill at bonfire)
            "chm_flasks_max": 3,         # max flask count
            "chm_module_earned": 0,      # CHM earned in current module (at stake)
            "ton_wallet": None,          # TON wallet for withdrawal
            "chm_last_snapshot": None,
            # ── ONBOARDING ──
            "onboarding_complete": False,
        }
    state = user_progress[user_id]
    # Back-compat: ensure new fields on old user records
    state.setdefault("streak", 0)
    state.setdefault("last_active_date", None)
    state.setdefault("badges", [])
    state.setdefault("daily_bonus_claimed", None)
    state.setdefault("module_unlocked", [0])
    # CHM system back-compat (with Souls→CHM migration for existing users)
    if "souls" in state and "chm" not in state:
        state["chm"] = state.pop("souls")
    if "total_souls_earned" in state and "chm_total_earned" not in state:
        state["chm_total_earned"] = state.pop("total_souls_earned")
    if "dropped_souls" in state and "chm_dropped" not in state:
        state["chm_dropped"] = state.pop("dropped_souls")
    if "dropped_souls_module_id" in state and "chm_dropped_module_id" not in state:
        state["chm_dropped_module_id"] = state.pop("dropped_souls_module_id")
    if "can_retrieve_souls" in state and "chm_can_retrieve" not in state:
        state["chm_can_retrieve"] = state.pop("can_retrieve_souls")
    if "souls_module_earned" in state and "chm_module_earned" not in state:
        state["chm_module_earned"] = state.pop("souls_module_earned")
    if "estus_flasks" in state and "chm_flasks" not in state:
        state["chm_flasks"] = state.pop("estus_flasks")
    if "estus_max" in state and "chm_flasks_max" not in state:
        state["chm_flasks_max"] = state.pop("estus_max")
    state.setdefault("chm", 0)
    state.setdefault("chm_total_earned", 0)
    state.setdefault("chm_total_burned", 0)
    state.setdefault("chm_total_spent", 0)
    state.setdefault("chm_dropped", 0)
    state.setdefault("chm_dropped_module_id", None)
    state.setdefault("chm_can_retrieve", False)
    state.setdefault("hollow_since", None)
    state.setdefault("current_title", "Ликвидность")
    state.setdefault("ng_plus_level", 0)
    state.setdefault("chm_flasks", 3)
    state.setdefault("chm_flasks_max", 3)
    state.setdefault("chm_module_earned", 0)
    state.setdefault("ton_wallet", None)
    state.setdefault("chm_last_snapshot", None)
    # Onboarding back-compat
    state.setdefault("onboarding_complete", False)
    # Notification state back-compat
    state.setdefault("last_hollow_notif", None)
    # Boss system back-compat
    state.setdefault("boss_attempts", [])
    state.setdefault("bonfire_rested", [])  # list of module_ids where bonfire was rested

    # ── Timed boost expiry cleanup ────────────────────────────────────────
    # Clear expired timed boosts so they don't persist after expiry
    _now_iso = datetime.utcnow()
    for _boost_key in ("double_tap_until", "catalyst_shield_until"):
        _val = state.get(_boost_key)
        if _val:
            try:
                if datetime.fromisoformat(_val) <= _now_iso:
                    state[_boost_key] = None
            except Exception:
                state[_boost_key] = None

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
# ── CHM SYSTEM  ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# Streak → CHM multiplier (like in Duolingo but darker)
_STREAK_MULTIPLIERS: List[Tuple[int, float]] = [
    (30, 5.0),  # 30+ days → x5
    (14, 3.0),  # 14+ days → x3
    (7,  2.0),  # 7+ days  → x2
    (3,  1.5),  # 3+ days  → x1.5
    (0,  1.0),  # default  → x1
]

# CHM per tap (base, before multiplier)
_CHM_PER_TAP_BASE = 2
_CHM_PER_TAP_COMBO5 = 5    # combo 5+
_CHM_PER_TAP_COMBO2 = 3    # combo 2-4


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
    """Return CHM-per-tap multiplier based on current streak."""
    for threshold, mult in _STREAK_MULTIPLIERS:
        if streak >= threshold:
            return mult
    return 1.0


def add_chm(user_id: int, amount: int, *, source: str = "tap") -> Dict[str, Any]:
    """Award CHM to user. Returns CHM delta info."""
    if amount <= 0:
        return {"chm": 0, "delta": 0, "total": 0}

    state = get_user_state(user_id)
    mult  = get_streak_multiplier(state.get("streak", 0))
    # Hollow penalty: x0.5 if hollow
    if state.get("hollow_since"):
        mult *= 0.5

    awarded = round(amount * mult)
    state["chm"]               = state.get("chm", 0) + awarded
    state["chm_total_earned"]  = state.get("chm_total_earned", 0) + awarded
    # Track how many CHM earned in current module (at stake for boss fights)
    state["chm_module_earned"] = state.get("chm_module_earned", 0) + awarded
    save_progress()
    return {"delta": awarded, "total": state["chm"], "multiplier": mult, "source": source}

# Back-compat alias
add_souls = add_chm


def spend_chm(user_id: int, amount: int, *, reason: str = "purchase") -> Dict[str, Any]:
    """Spend CHM. Returns {ok, delta, total} — fails if insufficient."""
    state  = get_user_state(user_id)
    current = state.get("chm", 0)
    if current < amount:
        return {"ok": False, "reason": "insufficient_chm", "have": current, "need": amount}
    state["chm"] = current - amount
    save_progress()
    return {"ok": True, "delta": -amount, "total": state["chm"], "reason": reason}

# Back-compat alias
spend_souls = spend_chm


def drop_chm(user_id: int) -> Dict[str, Any]:
    """
    Player failed a module boss: drop all CHM earned in this module.
    The CHM lands on the ground — one retrieval attempt is allowed.
    Returns the amount dropped.
    """
    state = get_user_state(user_id)
    earned_in_module = state.get("chm_module_earned", 0)
    if earned_in_module <= 0:
        return {"dropped": 0, "can_retrieve": False}

    # Transfer module earnings to "dropped" pool
    state["chm"]               = max(0, state.get("chm", 0) - earned_in_module)
    state["chm_dropped"]       = earned_in_module
    state["chm_dropped_module_id"] = state.get("module_index", 0)
    state["chm_dropped_expires_at"] = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    state["chm_can_retrieve"]  = True
    state["chm_module_earned"] = 0
    save_progress()
    return {"dropped": earned_in_module, "can_retrieve": True}

# Back-compat alias
drop_souls = drop_chm


def retrieve_chm(user_id: int) -> Dict[str, Any]:
    """
    One-shot attempt to recover dropped CHM (must retry the boss first).
    Returns amount recovered or 0 if not available.
    """
    state = get_user_state(user_id)
    if not state.get("chm_can_retrieve", False):
        return {"ok": False, "reason": "no_dropped_chm"}
    if state.get("chm_dropped", 0) <= 0:
        return {"ok": False, "reason": "nothing_to_retrieve"}

    recovered = state["chm_dropped"]
    state["chm"]              = state.get("chm", 0) + recovered
    state["chm_total_earned"] = state.get("chm_total_earned", 0) + recovered
    state["chm_dropped"]      = 0
    state["chm_dropped_module_id"] = None
    state["chm_dropped_expires_at"] = None
    state["chm_can_retrieve"] = False
    save_progress()
    return {"ok": True, "recovered": recovered, "total": state["chm"]}

# Back-compat alias
retrieve_souls = retrieve_chm


def burn_dropped_chm(user_id: int) -> int:
    """Permanently burn dropped CHM (called when opportunity expires)."""
    state = get_user_state(user_id)
    # Check expiry — only burn after 24h
    expires_at = state.get("chm_dropped_expires_at")
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) > datetime.utcnow():
                return 0  # not yet expired — don't burn
        except Exception:
            pass
    burned = state.get("chm_dropped", 0)
    state["chm_total_burned"]  = round(state.get("chm_total_burned", 0) + burned, 9)
    state["chm_dropped"]      = 0
    state["chm_dropped_module_id"] = None
    state["chm_dropped_expires_at"] = None
    state["chm_can_retrieve"] = False
    save_progress()
    return burned

# Back-compat alias
burn_dropped_souls = burn_dropped_chm


def use_estus_flask(user_id: int) -> Dict[str, Any]:
    """Use one CHM flask (hint charge). Returns {ok, remaining}."""
    state = get_user_state(user_id)
    flasks = state.get("chm_flasks", 3)
    if flasks <= 0:
        return {"ok": False, "remaining": 0, "reason": "no_flasks"}
    state["chm_flasks"] = flasks - 1
    save_progress()
    return {"ok": True, "remaining": state["chm_flasks"]}


def refill_estus(user_id: int) -> int:
    """Refill CHM flasks to max (called at bonfire checkpoint)."""
    state = get_user_state(user_id)
    max_flasks = state.get("chm_flasks_max", 3)
    state["chm_flasks"] = max_flasks
    # Also reset module earned CHM (new module = new session)
    state["chm_module_earned"] = 0
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


def exit_hollow(user_id: int, chm_cost: int = 100) -> Dict[str, Any]:
    """Pay CHM to exit hollow state. Returns {ok, ..}."""
    state = get_user_state(user_id)
    if not state.get("hollow_since"):
        return {"ok": False, "reason": "not_hollow"}
    result = spend_chm(user_id, chm_cost, reason="exit_hollow")
    if not result["ok"]:
        return result
    state["hollow_since"] = None
    save_progress()
    return {"ok": True, "chm_spent": chm_cost, "total_chm": result["total"]}


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


def get_chm_state(user_id: int) -> Dict[str, Any]:
    """Return a CHM summary for the user."""
    state = get_user_state(user_id)
    return {
        "chm":              state.get("chm", 0),
        "total_earned":     state.get("chm_total_earned", 0),
        "chm_total_burned": state.get("chm_total_burned", 0),
        "chm_total_spent":  state.get("chm_total_spent", 0),
        "chm_dropped":      state.get("chm_dropped", 0),
        "can_retrieve":     state.get("chm_can_retrieve", False),
        "chm_flasks":       state.get("chm_flasks", 3),
        "chm_flasks_max":   state.get("chm_flasks_max", 3),
        "is_hollow":        bool(state.get("hollow_since")),
        "hollow_since":     state.get("hollow_since"),
        "current_title":    state.get("current_title", "Ликвидность"),
        "streak_mult":      get_streak_multiplier(state.get("streak", 0)),
        "ng_plus_level":    state.get("ng_plus_level", 0),
        "ton_wallet":       state.get("ton_wallet"),
    }

# Back-compat alias
get_souls_state = get_chm_state


# ══════════════════════════════════════════════════════════════════════════════
# ── HOMUNCULUS SYSTEM (Алхимическая тапалка, 7 стадий эволюции) ──────────────
# ══════════════════════════════════════════════════════════════════════════════

HOMUNCULUS_STAGES = [
    {"id": 1, "name": "Реагент",           "chm_req": 0,      "modules_req": 0,  "mult": 1.0,  "desc": "Мерцающая колба с мутной жидкостью"},
    {"id": 2, "name": "Зародыш",           "chm_req": 500,    "modules_req": 1,  "mult": 1.2,  "desc": "В колбе появляется силуэт существа"},
    {"id": 3, "name": "Гомункул",          "chm_req": 2000,   "modules_req": 3,  "mult": 1.5,  "desc": "Существо вылезло из колбы"},
    {"id": 4, "name": "Фамильяр",          "chm_req": 5000,   "modules_req": 9,  "mult": 2.0,  "desc": "Существо с чертами дракона. Парит в воздухе"},
    {"id": 5, "name": "Элементаль",        "chm_req": 15000,  "modules_req": 10, "mult": 3.0,  "desc": "Существо из чистой энергии"},
    {"id": 6, "name": "Архонт",            "chm_req": 50000,  "modules_req": 10, "mult": 5.0,  "desc": "Величественная сущность в тёмной ауре"},
    {"id": 7, "name": "Философский Камень","chm_req": 100000, "modules_req": 10, "mult": 10.0, "desc": "Абстрактная геометрическая форма"},
]

_HOM_STATUS_MULT = {"active": 1.0, "hungry": 0.8, "dying": 0.3, "dead": 0.1, "enraged": 2.0}
_HOM_DAILY_CAP   = 1000   # taps per day before efficiency drops
_HOM_REVIVE_COST = 200    # CHM to revive dead homunculus


def _default_homunculus() -> Dict[str, Any]:
    return {
        "stage":        1,
        "status":       "active",
        "souls_fed":    0,        # lifetime CHM fed (drives evolution)
        "total_taps":   0,
        "taps_today":   0,
        "last_tap_at":  None,
        "last_daily_reset": None,
        "combo_best":   0,
        "enraged_until": None,
        "died_at":      None,
        "created_at":   datetime.utcnow().isoformat(),
    }


def get_homunculus_state(user_id: int) -> Dict[str, Any]:
    """Get homunculus state, creating default if missing."""
    state = get_user_state(user_id)
    if "homunculus" not in state:
        state["homunculus"] = _default_homunculus()
    hom = state["homunculus"]
    for k, v in _default_homunculus().items():
        hom.setdefault(k, v)

    # Check enrage expiry
    if hom.get("status") == "enraged" and hom.get("enraged_until"):
        try:
            if datetime.fromisoformat(hom["enraged_until"]) < datetime.utcnow():
                hom["status"] = "active"
                hom["enraged_until"] = None
                save_progress()
        except Exception:
            pass

    # Reset taps_today if new day
    last_reset = hom.get("last_daily_reset")
    today_str = date.today().isoformat()
    if last_reset != today_str:
        hom["taps_today"] = 0
        hom["last_daily_reset"] = today_str
        save_progress()

    stage = hom.get("stage", 1)
    stage_data = HOMUNCULUS_STAGES[stage - 1]
    next_stage = HOMUNCULUS_STAGES[stage] if stage < 7 else None

    return {
        "stage":        stage,
        "stage_name":   stage_data["name"],
        "stage_desc":   stage_data["desc"],
        "stage_mult":   stage_data["mult"],
        "status":       hom.get("status", "active"),
        "souls_fed":    hom.get("souls_fed", 0),
        "total_taps":   hom.get("total_taps", 0),
        "taps_today":   hom.get("taps_today", 0),
        "combo_best":   hom.get("combo_best", 0),
        "daily_cap":    _HOM_DAILY_CAP,
        "last_tap_at":  hom.get("last_tap_at"),
        "enraged_until": hom.get("enraged_until"),
        "next_stage":   next_stage,
        "progress_pct": round(min(100, hom.get("souls_fed", 0) / next_stage["chm_req"] * 100)) if next_stage else 100,
    }


def homunculus_process_taps(user_id: int, tap_count: int, max_combo: int = 0) -> Dict[str, Any]:
    """Process a batch of taps. Anti-cheat: max 20 per 2s batch. Returns CHM earned + evolution info."""
    state = get_user_state(user_id)
    if "homunculus" not in state:
        state["homunculus"] = _default_homunculus()
    hom = state["homunculus"]
    for k, v in _default_homunculus().items():
        hom.setdefault(k, v)

    # Anti-cheat cap
    tap_count = max(1, min(tap_count, 20))

    # Reset daily taps if new day
    today_str = date.today().isoformat()
    if hom.get("last_daily_reset") != today_str:
        hom["taps_today"] = 0
        hom["last_daily_reset"] = today_str

    # Daily cap efficiency
    taps_done = hom.get("taps_today", 0)
    if taps_done >= _HOM_DAILY_CAP:
        efficiency = 0.1
    else:
        efficiency = 1.0

    # Multipliers
    stage = hom.get("stage", 1)
    stage_mult = HOMUNCULUS_STAGES[stage - 1]["mult"]
    streak_mult = get_streak_multiplier(state.get("streak", 0))
    hollow_mult = 0.5 if state.get("hollow_since") else 1.0

    status = hom.get("status", "active")
    # Check enrage expiry
    if status == "enraged" and hom.get("enraged_until"):
        try:
            if datetime.fromisoformat(hom["enraged_until"]) < datetime.utcnow():
                status = "active"
                hom["status"] = "active"
                hom["enraged_until"] = None
        except Exception:
            pass

    # If tapping revives hungry/dying
    if status in ("hungry", "dying"):
        hom["status"] = "active"
        status = "active"

    status_mult = _HOM_STATUS_MULT.get(status, 1.0)

    # Combo bonus souls (added to last tap of batch)
    combo_bonus = 0
    if max_combo >= 100:
        combo_bonus = 10
    elif max_combo >= 50:
        combo_bonus = 5
    elif max_combo >= 25:
        combo_bonus = 2
    elif max_combo >= 10:
        combo_bonus = 1

    base_per_tap = stage_mult * streak_mult * hollow_mult * status_mult * efficiency
    souls_earned = max(1, int(tap_count * base_per_tap) + combo_bonus)

    # Update homunculus
    now = datetime.utcnow()
    hom["taps_today"]  = hom.get("taps_today", 0) + tap_count
    hom["total_taps"]  = hom.get("total_taps", 0) + tap_count
    hom["last_tap_at"] = now.isoformat()
    hom["souls_fed"]   = hom.get("souls_fed", 0) + souls_earned
    if max_combo > hom.get("combo_best", 0):
        hom["combo_best"] = max_combo

    # Check evolution
    evolved = False
    new_stage = stage
    modules_done = state.get("module_index", 0)
    for s in HOMUNCULUS_STAGES:
        if s["id"] <= stage:
            continue
        if hom["souls_fed"] >= s["chm_req"] and modules_done >= s["modules_req"]:
            new_stage = s["id"]
            evolved = True
    if evolved:
        hom["stage"] = new_stage

    # Award CHM
    result = add_chm(user_id, souls_earned, source="homunculus_tap")
    save_progress()

    next_stage_data = HOMUNCULUS_STAGES[new_stage] if new_stage < 7 else None
    return {
        "ok":           True,
        "chm_earned":   souls_earned,
        "total_chm":    result.get("total", 0),
        "evolution":    evolved,
        "new_stage":    new_stage,
        "stage_name":   HOMUNCULUS_STAGES[new_stage - 1]["name"],
        "stage_mult":   HOMUNCULUS_STAGES[new_stage - 1]["mult"],
        "status":       hom["status"],
        "taps_today":   hom["taps_today"],
        "combo_best":   hom["combo_best"],
        "souls_fed":    hom["souls_fed"],
        "progress_pct": round(min(100, hom["souls_fed"] / next_stage_data["chm_req"] * 100)) if next_stage_data else 100,
        "next_chm_req": next_stage_data["chm_req"] if next_stage_data else None,
    }


def homunculus_revive(user_id: int) -> Dict[str, Any]:
    """Pay 200 CHM to revive dead homunculus. Stage goes back by 1."""
    state = get_user_state(user_id)
    hom = state.get("homunculus", {})
    if hom.get("status") != "dead":
        return {"ok": False, "reason": "not_dead"}
    result = spend_chm(user_id, _HOM_REVIVE_COST, reason="homunculus_revive")
    if not result["ok"]:
        return {"ok": False, "reason": "not_enough_chm", "need": _HOM_REVIVE_COST}
    stage = max(1, hom.get("stage", 1) - 1)
    hom["stage"]    = stage
    hom["status"]   = "active"
    hom["died_at"]  = None
    # Reduce souls_fed to match rollback threshold
    hom["souls_fed"] = max(0, HOMUNCULUS_STAGES[stage - 1]["chm_req"])
    save_progress()
    return {
        "ok":         True,
        "new_stage":  stage,
        "stage_name": HOMUNCULUS_STAGES[stage - 1]["name"],
        "total_chm": result.get("total", 0),
    }


def homunculus_enrage(user_id: int) -> None:
    """Called after boss death. Homunculus enters enraged state for 10 minutes."""
    state = get_user_state(user_id)
    hom = state.setdefault("homunculus", _default_homunculus())
    if hom.get("status") == "dead":
        return  # can't enrage dead
    hom["status"]       = "enraged"
    hom["enraged_until"] = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    save_progress()


def check_homunculus_health(user_id: int) -> Dict[str, Any]:
    """Check & update homunculus status based on inactivity. Returns {changed, old_status, new_status}."""
    state = get_user_state(user_id)
    hom = state.get("homunculus")
    if not hom:
        return {"changed": False}
    last_tap = hom.get("last_tap_at")
    if not last_tap:
        return {"changed": False, "status": hom.get("status", "active")}

    now        = datetime.utcnow()
    last_dt    = datetime.fromisoformat(last_tap)
    hours_since = (now - last_dt).total_seconds() / 3600
    old_status  = hom.get("status", "active")
    new_status  = old_status

    if old_status == "enraged":
        if hom.get("enraged_until") and datetime.fromisoformat(hom["enraged_until"]) < now:
            new_status = "active"
    elif old_status not in ("dead",):
        if hours_since >= 168:    # 7 days → dead
            new_status = "dead"
        elif hours_since >= 72:   # 3 days → dying
            new_status = "dying"
        elif hours_since >= 24:   # 1 day → hungry
            new_status = "hungry"

    changed = new_status != old_status
    if changed:
        hom["status"] = new_status
        if new_status == "dead":
            hom["died_at"] = now.isoformat()
        save_progress()

    return {"changed": changed, "old_status": old_status, "new_status": new_status, "user_id": user_id}


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

    # ── CHM per tap (CHM farm mechanic) ──────────────────────────
    if combo >= 5:
        souls_tap = _CHM_PER_TAP_COMBO5
    elif combo >= 2:
        souls_tap = _CHM_PER_TAP_COMBO2
    else:
        souls_tap = _CHM_PER_TAP_BASE
    # add_chm handles multiplier (streak, hollow) and module tracking
    souls_result = add_chm(user_id, souls_tap, source="tap")

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
        # CHM system
        "chm_earned":       souls_result.get("delta", 0),
        "total_chm":        souls_result.get("total", 0),
        "chm_multiplier":   souls_result.get("multiplier", 1.0),
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


# ── ACTION POOL ────────────────────────────────────────────────────────────

def get_actions_pool(user_id: int, up: dict) -> dict:
    """
    Получить текущий пул действий пользователя.
    Автоматически сбрасывает при новом дне (00:00 UTC).
    """
    from datetime import datetime
    st = up.get(user_id, {})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    level = st.get("level", 1)
    daily_actions = level  # тапов в день = уровень

    # Сброс при новом дне
    if st.get("actions_date") != today:
        st["actions_date"] = today
        st["actions_used"] = 0
        # Шанс НЕ сбрасывается при новом дне — копится!

    used = st.get("actions_used", 0)
    left = max(0, daily_actions - used)

    return {
        "daily_total": daily_actions,
        "used": used,
        "left": left,
        "has_actions": left > 0,
        "catalyst_chance_pct": st.get("catalyst_chance_pct", 0),
        "catalyst_chance_cap": level * 15,  # максимум накопления
    }


def spend_action(user_id: int, action_type: str, up: dict) -> dict:
    """
    Потратить 1 действие из пула.
    action_type: "tap" | "attack_catalyst" | "catalyst_roll" | "roulette"
    Возвращает: {ok, actions_left, ...}
    """
    pool = get_actions_pool(user_id, up)
    if not pool["has_actions"]:
        level = up.get(user_id, {}).get("level", 1)
        return {
            "ok": False,
            "error": "no_actions",
            "message": f"Действий не осталось. Уровень {level} = {pool['daily_total']} в день. Сброс в 00:00 UTC.",
            "actions_left": 0,
            "resets_at": "00:00 UTC",
        }

    st = up.get(user_id, {})
    st["actions_used"] = st.get("actions_used", 0) + 1
    left = pool["left"] - 1

    result = {
        "ok": True,
        "action_type": action_type,
        "actions_left": left,
        "actions_total": pool["daily_total"],
    }

    # Обработка броска на Катализатора
    if action_type == "catalyst_roll":
        import random
        current_chance = st.get("catalyst_chance_pct", 0)
        cap = pool["catalyst_chance_cap"]

        # +10% к накопленному шансу (но не выше cap)
        new_chance = min(cap, current_chance + 10)
        st["catalyst_chance_pct"] = new_chance

        # Делаем бросок
        roll = random.randint(1, 100)
        became_catalyst = roll <= new_chance

        result["catalyst_roll"] = {
            "chance_pct": new_chance,
            "roll": roll,
            "became_catalyst": became_catalyst,
            "cap": cap,
        }

        if became_catalyst:
            st["catalyst_chance_pct"] = 0  # сброс после успеха
            result["catalyst_roll"]["message"] = f"🎲 Бросок {roll} ≤ {new_chance}% — УСПЕХ!"
        else:
            result["catalyst_roll"]["message"] = f"🎲 Бросок {roll} > {new_chance}% — шанс накопился"

    return result
