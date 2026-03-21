import asyncio
import hashlib
import hmac
import html as _html
import io
import os
import base64
import logging
import random
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── TELEGRAM INIT DATA VALIDATION ─────────────────────────────────────────────

def validate_telegram_init_data(init_data: str) -> Optional[dict]:
    """
    Validate Telegram Mini App initData HMAC signature.
    Returns parsed user dict on success, None on HMAC failure (spoofing attempt).
    Returns empty dict {} when BOT_TOKEN is not configured (skip validation).
    Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        logger.warning("BOT_TOKEN not set — skipping initData HMAC validation")
        # Parse user info from initData without verifying signature
        try:
            import json as _json
            params = dict(parse_qsl(init_data, keep_blank_values=True))
            user_raw = params.get("user", "{}")
            return _json.loads(unquote(user_raw)) if user_raw else {}
        except Exception:
            return {}
    if not init_data:
        return None
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop("hash", None)
        if not received_hash:
            return None
        # Check auth_date freshness (24 hour window — Telegram may cache initData)
        auth_date = int(params.get("auth_date", 0))
        if time.time() - auth_date > 86400:
            logger.warning("initData expired: auth_date=%d (>24h old)", auth_date)
            return None
        # Build check string: sorted key=value pairs joined by \n
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        # secret_key = HMAC-SHA256("WebAppData", BOT_TOKEN)
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            logger.warning("initData HMAC mismatch")
            return None
        # Parse nested user JSON
        import json as _json
        user_raw = params.get("user", "{}")
        return _json.loads(unquote(user_raw))
    except Exception as e:
        logger.warning("validate_telegram_init_data error: %r", e)
        return None


# ── SESSION TOKEN STORE ────────────────────────────────────────────────────────
# Maps user_id → session_token (in-memory; resets on redeploy, which is fine)
_session_tokens: Dict[int, str] = {}

def _new_session_token(user_id: int) -> str:
    token = uuid.uuid4().hex
    _session_tokens[user_id] = token
    return token

def _check_session(user_id: int, token: Optional[str]) -> bool:
    """Return True if token matches stored session for user_id (or no token stored yet)."""
    if not token:
        return True   # soft enforcement: allow requests without token
    stored = _session_tokens.get(user_id)
    if not stored:
        return True   # no session established yet (first open)
    return hmac.compare_digest(stored, token)


# ── IN-MEMORY RATE LIMITER ────────────────────────────────────────────────────
# Simple sliding-window per user_id
_rate_buckets: Dict[int, list] = defaultdict(list)

def _rate_limit(user_id: int, window_seconds: int = 5, max_calls: int = 10) -> bool:
    """Return True if request is within rate limit, False if throttled."""
    now = time.monotonic()
    bucket = _rate_buckets[user_id]
    # Remove timestamps outside window
    _rate_buckets[user_id] = [t for t in bucket if now - t < window_seconds]
    if len(_rate_buckets[user_id]) >= max_calls:
        return False
    _rate_buckets[user_id].append(now)
    return True


from progress import (
    get_user_state, save_progress, add_xp,
    set_module_deadline, is_deadline_expired,
    reset_user_progress, get_leaderboard,
    user_progress, load_progress,
    MAX_EXTENSIONS, DEFAULT_DEADLINE_HOURS,
    update_streak, claim_daily_bonus, award_badge,
    get_deadline_hours_remaining, apply_penalty_extension,
    MODULE_PENALTIES, MODULE_FULL_REPURCHASE,
    BADGE_DEFS, SMC_LEVELS, get_level_and_rank,
    # Pet system
    get_pet_state, pet_register_tap, apply_lesson_pet_effect, add_pet_coins,
    PET_LEVEL_XP,
    # Evolution + DNA
    check_and_update_evolution, EVOLUTION_STAGES, update_trader_dna, get_trader_dna,
    # Souls system
    add_souls, spend_souls, drop_souls, retrieve_souls, burn_dropped_souls,
    use_estus_flask, refill_estus, check_hollow, exit_hollow, update_title,
    get_souls_state, get_streak_multiplier,
)
from market_feed import refresh_market_data, start_market_feed_loop, get_cached_pulse
from oracle_engine import generate_oracle
from dream_generator import generate_dream
from lessons import LESSONS, MODULES
from quests import QUESTS, QUIZZES
from charts import generate_chart
from bot import bot as telegram_bot, setup_webhook, process_update, make_hw_keyboard
from boss import router as boss_router
from social import router as social_router, get_daily_challenge, _msk_now
from notification_service import notification_service

@asynccontextmanager
async def lifespan(application: FastAPI):
    """Unified application lifespan — runs on startup, tears down on shutdown."""
    # ── Load persisted data ────────────────────────────────────────────────
    load_progress()
    logger.info("Progress loaded: %d users", len(user_progress))

    # ── Log & validate critical env vars ──────────────────────────────────
    _raw_channel = os.getenv("ADMIN_CHANNEL_ID", "NOT SET").strip()
    _raw_admins  = os.getenv("ADMIN_ID", "NOT SET").strip()
    _raw_token   = os.getenv("BOT_TOKEN", "").strip()
    _raw_webhook = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
    logger.info("ADMIN_CHANNEL_ID = %r", _raw_channel)
    try:
        _ch_int = int(_raw_channel) if _raw_channel not in ("NOT SET", "") else None
        if _ch_int is not None and _ch_int > 0:
            logger.error("⚠️  ADMIN_CHANNEL_ID is POSITIVE (%d) — must be NEGATIVE for groups!", _ch_int)
        elif _ch_int is not None and _ch_int < 0:
            logger.info("✅ ADMIN_CHANNEL_ID is negative (correct): %d", _ch_int)
        else:
            logger.warning("⚠️  ADMIN_CHANNEL_ID not set — HW notifications go to individual admin DMs only")
    except ValueError:
        logger.error("⚠️  ADMIN_CHANNEL_ID is not a valid integer: %r", _raw_channel)
    logger.info("ADMIN_ID         = %r", _raw_admins)
    logger.info("BOT_TOKEN        = %s", f"SET (len={len(_raw_token)})" if _raw_token else "NOT SET ⚠️")
    logger.info("WEBHOOK_URL      = %r", _raw_webhook)

    # ── Setup Telegram webhook (non-blocking) ──────────────────────────────
    if _raw_webhook:
        await asyncio.get_running_loop().run_in_executor(None, setup_webhook)
    else:
        logger.info("WEBHOOK_URL not set — webhook not configured (polling mode)")

    # ── Wire notification service ──────────────────────────────────────────
    notification_service.set_bot(telegram_bot)
    logger.info("NotificationService bot wired")

    # ── Start background tasks ─────────────────────────────────────────────
    asyncio.create_task(start_market_feed_loop())
    logger.info("Market feed background task started")
    asyncio.create_task(_daily_challenge_loop())
    logger.info("Daily challenge loop started")
    asyncio.create_task(_invasion_weekly_loop())
    logger.info("Invasion weekly loop started")
    asyncio.create_task(_homunculus_health_loop())
    logger.info("Homunculus health loop started")
    asyncio.create_task(_streak_warning_loop())
    logger.info("Streak warning loop started")
    asyncio.create_task(_notification_queue_flush_loop())
    logger.info("Notification queue flush loop started")
    asyncio.create_task(_deadline_check_loop())
    logger.info("Deadline check loop started")
    if _raw_webhook:
        asyncio.create_task(_keep_alive_loop(_raw_webhook))
        logger.info("Keep-alive loop started")

    yield
    # (shutdown cleanup goes here if needed)

app = FastAPI(title="CHM Smart Money Academy API", version="4.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s: %r", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"ok": False, "error": "Internal server error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Boss & Social routers ──────────────────────────────────────────────────
app.include_router(boss_router)
app.include_router(social_router)

# ── Static frontend ───────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
    logger.info(f"Frontend: {FRONTEND_DIR}")
else:
    logger.warning(f"Frontend folder not found: {FRONTEND_DIR}")


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class UserInitRequest(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    init_data: Optional[str] = None   # Telegram WebApp initData for HMAC validation


class QuestSubmitRequest(BaseModel):
    user_id:       int
    quest_id:      str
    photo:         Optional[str] = None   # base64 data URL of homework screenshot
    session_token: Optional[str] = None


class QuizAnswerRequest(BaseModel):
    user_id:       int
    quest_id:      str
    question_index: int
    is_correct:    bool
    session_token: Optional[str] = None


class AdminApproveRequest(BaseModel):
    admin_id: int
    user_id: int
    quest_id: str


class AdminRejectRequest(BaseModel):
    admin_id: int
    user_id: int
    quest_id: str
    comment: Optional[str] = "Нужно доработать."
    status: Optional[str] = "rejected"   # "rejected" or "revision"


class ExtendRequest(BaseModel):
    admin_id: int
    user_id: int
    days: int = 2


class PenaltyPaymentRequest(BaseModel):
    user_id: int
    module_index: int
    payment_type: str = "penalty"   # "penalty" or "repurchase"


class PetTapRequest(BaseModel):
    user_id: int


class OracleAnswerRequest(BaseModel):
    user_id: int
    correct: bool


class DreamAnswerRequest(BaseModel):
    user_id: int
    correct: bool
    concept: Optional[str] = None


# ── UTILS ─────────────────────────────────────────────────────────────────────

_cached_admin_ids: set = set()

def _get_admin_ids() -> set:
    """Parse and cache admin IDs from ADMIN_ID env var."""
    global _cached_admin_ids
    if not _cached_admin_ids:
        raw = os.getenv("ADMIN_ID", "0")
        _cached_admin_ids = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    return _cached_admin_ids

def _get_admin_channel_id() -> int | None:
    raw = os.getenv("ADMIN_CHANNEL_ID", "").strip()
    try:
        return int(raw) if raw else None
    except ValueError:
        return None

def _send_hw_notification(chat_id: int, admin_text: str, photo_b64: str | None,
                          user_id: int, quest_id: str) -> None:
    """Send homework notification to a chat/channel with inline buttons and photo fallback.

    chat_id must be negative for groups/channels (e.g. -1001234567890).
    For user DMs it is a positive integer.
    """
    kb = make_hw_keyboard(user_id, quest_id)
    logger.info("Sending HW notification to chat_id=%s (type=%s)", chat_id,
                "group/channel" if chat_id < 0 else "user DM")
    if photo_b64:
        try:
            photo_bytes = base64.b64decode(photo_b64.split(",", 1)[-1])
            buf = io.BytesIO(photo_bytes)
            buf.name = "homework.jpg"
            telegram_bot.send_photo(chat_id, buf, caption=admin_text, parse_mode="HTML",
                                    reply_markup=kb)
            logger.info("send_photo OK → chat_id=%s", chat_id)
            return
        except Exception as e:
            logger.error("send_photo FAILED → chat_id=%s error=%r (falling back to text)", chat_id, e)
    try:
        telegram_bot.send_message(chat_id, admin_text, parse_mode="HTML", reply_markup=kb)
        logger.info("send_message OK → chat_id=%s", chat_id)
    except Exception as e:
        logger.error("send_message FAILED → chat_id=%s error=%r", chat_id, e)
        raise  # re-raise so caller can log the failure context

def check_admin(admin_id: int):
    """Raise 403 if admin_id is not in the allowed admin set."""
    if admin_id not in _get_admin_ids():
        raise HTTPException(status_code=403, detail="Нет доступа")


# ── CHART CACHE (TTL-based, avoids regenerating expensive matplotlib charts) ─
_chart_cache: dict = {}
_CHART_CACHE_TTL = 3600  # 1 hour


def try_advance_module(user_id: int) -> bool:
    """Advance user to next module if all current module quests are completed."""
    state = get_user_state(user_id)
    idx = state["module_index"]
    if idx >= len(MODULES) - 1:
        return False
    module_quests = [q["id"] for q in QUESTS if q["module_index"] == idx]
    completed = set(state["completed_quests"])
    if all(qid in completed for qid in module_quests):
        state["module_index"] += 1
        set_module_deadline(state, hours=DEFAULT_DEADLINE_HOURS)
        save_progress()
        return True
    return False


def build_deadline_info(state: dict) -> dict:
    """Build deadline info dict for API responses."""
    dl = state.get("module_deadline")
    hours_left = get_deadline_hours_remaining(state)
    expired = is_deadline_expired(state)

    info = {
        "deadline": dl.split("T")[0] if dl else None,
        "deadline_iso": dl,
        "hours_remaining": round(hours_left, 2) if hours_left != float("inf") else None,
        "deadline_expired": expired,
        "extensions_used": state.get("deadline_extensions", 0),
        "max_extensions": MAX_EXTENSIONS,
        "can_extend": state.get("deadline_extensions", 0) < MAX_EXTENSIONS,
    }

    if not expired and hours_left != float("inf"):
        if hours_left <= 1:
            info["urgency"] = "critical"   # Red countdown
        elif hours_left <= 6:
            info["urgency"] = "danger"     # Pulsing red
        elif hours_left <= 24:
            info["urgency"] = "warning"    # Orange
        else:
            info["urgency"] = "normal"
    else:
        info["urgency"] = "expired" if expired else "none"

    return info


# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve frontend index or return API info."""
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "CHM Smart Money Academy API v4.0", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"ok": True, "users": len(user_progress), "version": "4.0.0"}


# ── USER ──────────────────────────────────────────────────────────────────────

@app.post("/api/user/init")
async def user_init(req: UserInitRequest):
    """Initialize or update user session: set name, update streak, claim daily bonus."""
    # ── Telegram initData validation (when provided) ───────────────────────
    # Non-blocking: log warnings but never reject the request.
    # Strict enforcement can be enabled once HMAC is verified against live traffic.
    user_id = req.user_id
    if req.init_data:
        tg_user = validate_telegram_init_data(req.init_data)
        if tg_user is None:
            # Validation failed — log for monitoring but allow through
            logger.warning("initData validation failed for user_id=%s (non-blocking)", req.user_id)
        else:
            # Override user_id with the validated one — prevents spoofing
            validated_id = tg_user.get("id")
            if validated_id and validated_id != req.user_id:
                logger.warning("user_id mismatch: req=%s validated=%s — using validated", req.user_id, validated_id)
                user_id = validated_id
            # Trust names from validated initData
            if not req.username:
                req.username = tg_user.get("username")
            if not req.first_name:
                req.first_name = tg_user.get("first_name")
            if not req.last_name:
                req.last_name = tg_user.get("last_name")
            # Hard rejection only for HMAC mismatches (actual spoofing attempt).
            # None means validation ran with a BOT_TOKEN and the signature was wrong.
            logger.warning("Rejecting user_id=%d: initData HMAC validation failed", user_id)
            raise HTTPException(status_code=403, detail="Invalid Telegram initData")
        # tg_user is a dict (possibly empty if BOT_TOKEN not set — soft validation)
        # Override user_id with the validated one — prevents spoofing
        user_id = tg_user.get("id", user_id)
        # Trust names from validated initData
        if not req.username:
            req.username = tg_user.get("username")
        if not req.first_name:
            req.first_name = tg_user.get("first_name")
        if not req.last_name:
            req.last_name = tg_user.get("last_name")

    state = get_user_state(user_id)
    name = (
        req.username
        or f"{req.first_name or ''} {req.last_name or ''}".strip()
        or str(user_id)
    )
    state["name"] = name

    # Set initial deadline for module 0 (no deadline - free module)
    if state["module_index"] == 0 and not state.get("module_deadline"):
        set_module_deadline(state)

    # Track last_online for dream system
    state["last_online"] = datetime.utcnow().isoformat()

    # Track daily streak
    streak, is_new_day = update_streak(user_id)

    # Daily bonus XP (also calls save_progress internally)
    daily_xp, got_bonus = claim_daily_bonus(user_id)

    # Update evolution stage
    evo = check_and_update_evolution(user_id)

    # Check hollow status (inactivity penalty)
    hollow = check_hollow(user_id)

    # Update display title
    update_title(user_id)

    # Award daily souls bonus (matches daily XP bonus)
    souls_bonus = 0
    if is_new_day:
        souls_result = add_souls(user_id, 20, source="daily_login")
        souls_bonus = souls_result.get("delta", 0)

    # Pulse (non-blocking: return cached if available)
    pulse = get_cached_pulse()

    # Issue a session token tied to this user
    session_token = _new_session_token(user_id)

    save_progress()
    # Note: update_streak and claim_daily_bonus already call save_progress()
    # Only save if name changed and neither function triggered a save
    if not is_new_day and not got_bonus:
        save_progress()
    return {
        "ok": True,
        "user_id": user_id,
        "session_token": session_token,
        "state": state,
        "streak": streak,
        "is_new_day": is_new_day,
        "daily_bonus_xp": daily_xp if got_bonus else 0,
        "evolution": evo,
        "market_pulse": pulse,
        "hollow": hollow,
        "souls_state": get_souls_state(user_id),
        "daily_souls_bonus": souls_bonus,
        "onboarding_complete": state.get("onboarding_complete", False),
    }


def _state_safe(state: dict) -> dict:
    """Return state without large binary fields."""
    return {k: v for k, v in state.items() if k != "homework_photo"}


class OnboardingRequest(BaseModel):
    user_id: int

@app.post("/api/onboarding/complete")
async def onboarding_complete_api(req: OnboardingRequest):
    """Mark onboarding as complete and award 50 starting souls."""
    state = get_user_state(req.user_id)
    if state.get("onboarding_complete"):
        return {"ok": True, "already_done": True, "souls": state.get("souls", 0)}
    state["onboarding_complete"] = True
    # Award 50 starting souls (in addition to the 50 from ritual itself)
    result = add_souls(req.user_id, 50, source="onboarding")
    save_progress()
    # Optionally send a welcome notification
    try:
        from notification_service import notification_service
        await notification_service.send(req.user_id, "onboarding_welcome")
    except Exception:
        pass
    return {"ok": True, "souls_awarded": result.get("delta", 50), "total_souls": state.get("souls", 0)}


@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    """Return user state (excluding large binary fields)."""
    state = get_user_state(user_id)
    return _state_safe(state)


@app.get("/api/user/{user_id}/full")
async def get_user_full(user_id: int):
    """Full user state with computed deadline info."""
    state = get_user_state(user_id)
    result = _state_safe(state)
    result["deadline_info"] = build_deadline_info(state)
    result["next_level_xp"] = None
    current_xp = state.get("xp", 0)
    for threshold, _lvl, _name in SMC_LEVELS:
        if threshold > current_xp:
            result["next_level_xp"] = threshold
            break
    return result


# ── MODULES & LESSONS ────────────────────────────────────────────────────────

@app.get("/api/modules")
async def get_modules():
    """Return all course modules."""
    return {"modules": MODULES}


@app.get("/api/lessons/meta")
async def lessons_meta():
    """Return lesson titles and short texts for all lessons."""
    data = {k: {"title": v.get("title", k), "text": v.get("text", "")} for k, v in LESSONS.items()}
    return JSONResponse(data)


@app.get("/api/lesson/{lesson_key}")
async def get_lesson(lesson_key: str):
    """Return full lesson content by key."""
    lesson = LESSONS.get(lesson_key)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не найден")
    return {
        "key": lesson_key,
        "title": lesson["title"],
        "text": lesson["text"],
        "article": lesson["article"],
        "video": lesson.get("video", ""),
    }


# ── CHARTS ───────────────────────────────────────────────────────────────────

def _get_cached_chart(lesson_key: str) -> Optional[bytes]:
    """Get chart bytes from cache or generate and cache."""
    import time
    now = time.time()
    cached = _chart_cache.get(lesson_key)
    if cached and (now - cached[1]) < _CHART_CACHE_TTL:
        return cached[0]
    buf = generate_chart(lesson_key)
    if buf is None:
        return None
    data = buf.read()
    _chart_cache[lesson_key] = (data, now)
    return data


@app.get("/api/chart/{lesson_key}")
async def get_chart(lesson_key: str):
    """Return chart as base64-encoded PNG JSON response."""
    
    data = await asyncio.get_running_loop().run_in_executor(None, _get_cached_chart, lesson_key)
    if data is None:
        raise HTTPException(status_code=404, detail="График не найден")
    img_b64 = base64.b64encode(data).decode()
    return {"image_base64": img_b64, "mime": "image/png"}


@app.get("/api/chart/{lesson_key}/png")
async def get_chart_png(lesson_key: str):
    """Return chart as raw PNG binary response."""
    
    data = await asyncio.get_running_loop().run_in_executor(None, _get_cached_chart, lesson_key)
    if data is None:
        raise HTTPException(status_code=404, detail="График не найден")
    return Response(content=data, media_type="image/png")


# ── QUESTS & QUIZZES ─────────────────────────────────────────────────────────

@app.get("/api/quests/{user_id}")
async def get_quests(user_id: int):
    """Return quests for user's current module with deadline info."""
    state = get_user_state(user_id)
    idx = state["module_index"]
    completed = set(state["completed_quests"])
    module_quests = [q for q in QUESTS if q["module_index"] == idx]
    result = [
        {
            "id": q["id"],
            "title": q["title"],
            "type": q["type"],
            "xp_reward": q["xp_reward"],
            "description": q.get("description", ""),
            "completed": q["id"] in completed,
            "is_active": state.get("active_quest") == q["id"],
        }
        for q in module_quests
    ]

    dl_info = build_deadline_info(state)

    return {
        "quests": result,
        "module_index": idx,
        "module_title": MODULES[idx]["title"] if idx < len(MODULES) else "Завершено",
        "module_subtitle": MODULES[idx].get("subtitle", "") if idx < len(MODULES) else "",
        "deadline_expired": dl_info["deadline_expired"],
        "deadline": dl_info["deadline"],
        "deadline_info": dl_info,
        "completed_count": len([q for q in result if q["completed"]]),
        "total_count": len(result),
    }


@app.post("/api/quest/start")
async def start_quest(req: QuestSubmitRequest):
    """Start a quest; for quizzes, shuffle and return questions."""
    state = get_user_state(req.user_id)
    if is_deadline_expired(state):
        return {
            "ok": False,
            "error": "deadline_expired",
            "message": "Дедлайн истёк. Оплати штраф для продолжения.",
            "penalty_amount": MODULE_PENALTIES.get(state["module_index"], 5),
            "can_extend": state.get("deadline_extensions", 0) < MAX_EXTENSIONS,
        }

    quest = next((q for q in QUESTS if q["id"] == req.quest_id), None)
    if not quest:
        raise HTTPException(status_code=404, detail="Квест не найден")
    if req.quest_id in state["completed_quests"]:
        return {"ok": False, "error": "already_completed"}

    state["active_quest"] = req.quest_id
    save_progress()

    response = {"ok": True, "quest": quest}

    if quest["type"] == "quiz":
        quiz_id = quest.get("quiz_ref", "")
        quiz_list = QUIZZES.get(quiz_id, [])
        shuffled = []
        for q in quiz_list:
            opts = q["options"].copy()
            random.shuffle(opts)
            shuffled.append({
                "question": q["question"],
                "options": [o[0] for o in opts],
                "correct_index": next(i for i, o in enumerate(opts) if o[1]),
            })
        state["quiz_state"] = {
            "quiz_id": quiz_id,
            "index": 0,
            "correct": 0,
            "total": len(quiz_list),
            "questions": shuffled,
        }
        save_progress()
        response["quiz"] = {"questions": shuffled, "total": len(quiz_list)}

    return response


@app.post("/api/quiz/answer")
async def quiz_answer(req: QuizAnswerRequest):
    """Process a quiz answer; finalize quiz if all questions answered."""
    if not _check_session(req.user_id, req.session_token):
        raise HTTPException(status_code=403, detail="Invalid session")
    state = get_user_state(req.user_id)
    qstate = state.get("quiz_state")
    if not qstate:
        raise HTTPException(status_code=400, detail="Квиз не активен")

    if req.is_correct:
        qstate["correct"] += 1
    qstate["index"] = req.question_index + 1
    state["quiz_state"] = qstate
    save_progress()

    total = qstate["total"]
    current_index = qstate["index"]

    if current_index >= total:
        score = qstate["correct"] / total if total > 0 else 0
        if score >= 0.7:
            quest_id = state.get("active_quest")
            quest = next((q for q in QUESTS if q["id"] == quest_id), None)
            if quest and quest_id not in state["completed_quests"]:
                state["completed_quests"].append(quest_id)
                state["active_quest"] = None
                state["quiz_state"] = None
                level, leveled_up = add_xp(req.user_id, quest["xp_reward"])

                # Award "first blood" badge on first quiz
                if len([q for q in state["completed_quests"] if "quiz" in q]) == 1:
                    award_badge(req.user_id, "first_blood")

                advanced = try_advance_module(req.user_id)

                # Pet effect: boost fox stats based on quiz topic
                quiz_ref = quest.get("quiz_ref", "")
                lesson_key = _QUIZ_REF_TO_LESSON.get(quiz_ref, "")
                pet_effect = {}
                if lesson_key:
                    try:
                        pet_effect = apply_lesson_pet_effect(req.user_id, lesson_key, round(score * 100))
                    except Exception as pe:
                        logger.warning(f"Pet effect error: {pe}")

                save_progress()
                # add_xp, award_badge, try_advance_module already save;
                # no extra save_progress() needed here
                return {
                    "ok": True, "finished": True, "passed": True,
                    "score": round(score * 100), "correct": qstate["correct"], "total": total,
                    "xp_earned": quest["xp_reward"],
                    "new_level": level, "leveled_up": leveled_up,
                    "module_advanced": advanced,
                    "rank": get_user_state(req.user_id)["rank"],
                    "pet_effect": pet_effect,
                }
        else:
            state["quiz_state"] = None
            state["active_quest"] = None
            save_progress()
            return {
                "ok": True, "finished": True, "passed": False,
                "score": round(score * 100), "correct": qstate["correct"], "total": total,
                "required": 70,
            }

    return {"ok": True, "finished": False, "next_index": current_index}


@app.post("/api/quest/submit")
async def submit_task(req: QuestSubmitRequest):
    """Submit homework task with optional photo; notify admins asynchronously."""
    if not _check_session(req.user_id, req.session_token):
        raise HTTPException(status_code=403, detail="Invalid session")
    state = get_user_state(req.user_id)
    if is_deadline_expired(state):
        return {
            "ok": False,
            "error": "deadline_expired",
            "penalty_amount": MODULE_PENALTIES.get(state["module_index"], 5),
            "can_extend": state.get("deadline_extensions", 0) < MAX_EXTENSIONS,
        }

    # Check if submitted within first 12 hours → "time is money" badge
    dl = state.get("module_deadline")
    if dl:
        try:
            deadline_dt = datetime.fromisoformat(dl)
            hours_used = DEFAULT_DEADLINE_HOURS - (deadline_dt - datetime.utcnow()).total_seconds() / 3600
            if hours_used <= 12:
                award_badge(req.user_id, "time_is_money")
        except Exception:
            pass

    state["active_quest"] = req.quest_id
    state["homework_status"] = "pending"
    state["homework_comment"] = ""
    if req.photo:
        # Cap at 1.5 MB decoded (~2 MB base64) to prevent JSON bloat
        # Always keep the full data-URL prefix; truncate only excess payload
        state["homework_photo"] = req.photo[:2_000_000]
    save_progress()

    # ── Notify admins (non-blocking executor so we don't block the response) ──
    quest_obj   = next((q for q in QUESTS if q["id"] == req.quest_id), None)
    quest_title = quest_obj["title"] if quest_obj else req.quest_id
    user_name   = state.get("name") or str(req.user_id)
    admin_text  = (
        f"📬 <b>Новое домашнее задание!</b>\n\n"
        f"👤 Студент: <b>{_html.escape(str(user_name))}</b> (<code>{req.user_id}</code>)\n"
        f"📝 Задание: <b>{_html.escape(str(quest_title))}</b>\n\n"
        f"✅ Принять: <code>/approve {req.user_id} {req.quest_id}</code>\n"
        f"🔄 Доработка: <code>/revision {req.user_id} {req.quest_id} комментарий</code>\n"
        f"⛔ Отклонить: <code>/reject {req.user_id} {req.quest_id} причина</code>"
    )

    # Capture values before going into executor (avoid closure over mutable state)
    _photo_snapshot   = req.photo
    _user_id_snapshot = req.user_id
    _quest_id_snapshot = req.quest_id
    _channel_id        = _get_admin_channel_id()
    _admin_ids         = list(_get_admin_ids())

    def _dispatch_hw_notifications():
        """Send HW notification to admin channel (primary) + individual admins (fallback).

        Runs in a thread executor so the HTTP response is returned immediately.
        NOTE: We send to the channel OR to individual admins — not both — to avoid spam.
        If channel is configured it is the primary target; individual DMs serve as fallback.
        """
        sent_to_channel = False

        # 1. Primary: admin group/channel
        if _channel_id:
            try:
                _send_hw_notification(_channel_id, admin_text, _photo_snapshot,
                                      _user_id_snapshot, _quest_id_snapshot)
                sent_to_channel = True
            except Exception as e:
                logger.error("HW notify FAILED → channel %s: %r — falling back to DMs", _channel_id, e)

        # 2. Fallback: individual admin DMs (only if channel delivery failed or no channel set)
        if not sent_to_channel:
            for aid in _admin_ids:
                try:
                    _send_hw_notification(aid, admin_text, _photo_snapshot,
                                          _user_id_snapshot, _quest_id_snapshot)
                except Exception as e:
                    logger.error("HW notify FAILED → admin DM %s: %r", aid, e)

    asyncio.get_running_loop().run_in_executor(None, _dispatch_hw_notifications)

    return {
        "ok": True,
        "message": "Задание принято на проверку. Преподаватель проверит в течение 24 часов.",
    }


# ── DEADLINE PENALTY PAYMENT ──────────────────────────────────────────────────

@app.post("/api/deadline/penalty")
async def pay_deadline_penalty(req: PenaltyPaymentRequest):
    """
    Process deadline penalty payment.
    In production: integrate with payment gateway before calling this.
    payment_type: 'penalty' = first miss, 48h extension
                  'repurchase' = second miss, full module repurchase
    """
    state = get_user_state(req.user_id)

    if req.payment_type == "penalty":
        if state.get("deadline_extensions", 0) >= MAX_EXTENSIONS:
            return {
                "ok": False,
                "error": "max_extensions_reached",
                "message": "Лимит продлений исчерпан. Требуется полная перепокупка модуля.",
                "repurchase_amount": MODULE_FULL_REPURCHASE.get(req.module_index, 15),
            }

        success = apply_penalty_extension(state)
        if success:
            save_progress()
            new_dl = state.get("module_deadline")
            dl_info = build_deadline_info(state)
            return {
                "ok": True,
                "message": "Штраф оплачен. У тебя есть 48 часов. Рынок не прощает промедления.",
                "new_deadline_iso": new_dl,
                "deadline_info": dl_info,
                "extensions_remaining": MAX_EXTENSIONS - state.get("deadline_extensions", 0),
            }
        return {"ok": False, "error": "extension_failed"}

    elif req.payment_type == "repurchase":
        # Full repurchase: reset module progress, set fresh 72h deadline
        module_idx = state["module_index"]
        # Remove all quests for this module from completed
        module_quest_ids = {q["id"] for q in QUESTS if q["module_index"] == module_idx}
        state["completed_quests"] = [
            qid for qid in state["completed_quests"] if qid not in module_quest_ids
        ]
        state["homework_status"] = "idle"
        state["active_quest"] = None
        state["deadline_extensions"] = 0
        set_module_deadline(state, hours=DEFAULT_DEADLINE_HOURS)
        save_progress()
        return {
            "ok": True,
            "message": "Модуль перекуплен. Новый дедлайн: 72 часа. Не повторяй ошибку.",
            "deadline_info": build_deadline_info(state),
        }

    raise HTTPException(status_code=400, detail="Неизвестный тип оплаты")


@app.get("/api/deadline/status/{user_id}")
async def get_deadline_status(user_id: int):
    """Return deadline status with penalty/repurchase amounts."""
    state = get_user_state(user_id)
    info = build_deadline_info(state)
    info["module_index"] = state["module_index"]
    info["penalty_amount"] = MODULE_PENALTIES.get(state["module_index"], 5)
    info["repurchase_amount"] = MODULE_FULL_REPURCHASE.get(state["module_index"], 15)
    return info


# ── DAILY BONUS ───────────────────────────────────────────────────────────────

@app.post("/api/user/daily-bonus")
async def daily_bonus_endpoint(user_id: int):
    """Claim daily login bonus XP."""
    xp, got_bonus = claim_daily_bonus(user_id)
    streak, _ = update_streak(user_id)
    if got_bonus:
        return {"ok": True, "xp_earned": xp, "streak": streak}
    return {"ok": False, "message": "Бонус уже получен сегодня", "streak": streak}


# ── LEADERBOARD & STATS ──────────────────────────────────────────────────────

@app.get("/api/leaderboard")
async def leaderboard(limit: int = Query(default=10, ge=1, le=50)):
    """Return top users leaderboard."""
    board = get_leaderboard(limit)
    return {"leaderboard": board}


@app.get("/api/stats/{user_id}")
async def user_stats(user_id: int):
    """Return detailed user statistics with deadline and module progress."""
    state = get_user_state(user_id)
    idx = state["module_index"]
    module_title = MODULES[idx]["title"] if idx < len(MODULES) else "Завершено"
    dl_info = build_deadline_info(state)
    all_module_quests = [q for q in QUESTS if q["module_index"] == idx]
    completed_module = sum(1 for q in all_module_quests if q["id"] in state["completed_quests"])

    return {
        "name": state.get("name", str(user_id)),
        "level": state["level"], "xp": state["xp"], "rank": state["rank"],
        "module_index": idx, "module_title": module_title,
        "total_quests_completed": len(state["completed_quests"]),
        "module_quests_completed": completed_module,
        "module_quests_total": len(all_module_quests),
        "streak": state.get("streak", 0),
        "badges": state.get("badges", []),
        "deadline_info": dl_info,
        "is_expired": dl_info["deadline_expired"],
    }


# ── ADMIN ─────────────────────────────────────────────────────────────────────

@app.post("/api/admin/approve")
async def admin_approve(req: AdminApproveRequest):
    """Admin: approve homework, award XP, and optionally advance module."""
    check_admin(req.admin_id)
    state = get_user_state(req.user_id)
    quest = next((q for q in QUESTS if q["id"] == req.quest_id), None)
    if not quest:
        raise HTTPException(status_code=404, detail="Квест не найден")
    if req.quest_id not in state["completed_quests"]:
        state["completed_quests"].append(req.quest_id)
    state["active_quest"] = None
    state["homework_status"] = "approved"
    level, leveled_up = add_xp(req.user_id, quest["xp_reward"])

    # Award "disciplined" badge if homework submitted on time
    if not is_deadline_expired(state) and state.get("module_deadline"):
        award_badge(req.user_id, "disciplined")

    advanced = False
    if req.quest_id.endswith("_boss"):
        advanced = try_advance_module(req.user_id)

    # Check if all modules completed → CHM Legend badge
    if state["module_index"] >= len(MODULES) - 1:
        all_done = all(q["id"] in state["completed_quests"] for q in QUESTS)
        if all_done:
            award_badge(req.user_id, "chm_legend")

    # Give pet coins for approved homework
    try:
        coin_reward = 50 if req.quest_id.endswith("_boss") else 30
        add_pet_coins(req.user_id, coin_reward)
    except Exception as ce:
        logger.warning(f"Pet coins error on approval: {ce}")

    save_progress()
    return {"ok": True, "new_level": level, "leveled_up": leveled_up, "module_advanced": advanced}


@app.post("/api/admin/reject")
async def admin_reject(req: AdminRejectRequest):
    """Admin: reject or request revision for homework submission."""
    check_admin(req.admin_id)
    state = get_user_state(req.user_id)
    # "revision" = needs correction + resubmit; "rejected" = serious errors
    state["homework_status"] = req.status if req.status in ("rejected", "revision") else "rejected"
    state["homework_comment"] = req.comment or ""
    save_progress()
    return {"ok": True, "comment": req.comment, "status": state["homework_status"]}


@app.post("/api/admin/extend")
async def admin_extend(req: ExtendRequest):
    """Admin: extend user deadline by N days (does not count against MAX_EXTENSIONS)."""
    check_admin(req.admin_id)
    state = get_user_state(req.user_id)
    now = datetime.utcnow()
    dl = state.get("module_deadline")
    try:
        base = datetime.fromisoformat(dl) if dl else now
    except Exception:
        base = now
    new_dl = base + timedelta(days=req.days)
    state["module_deadline"] = new_dl.isoformat()
    # Admin extension doesn't count against MAX_EXTENSIONS
    save_progress()
    return {"ok": True, "new_deadline": new_dl.date().isoformat()}


@app.get("/api/admin/users")
async def admin_users(admin_id: int):
    """Admin: list all users with progress, deadline, and homework status."""
    check_admin(admin_id)
    result = [
        {
            "user_id": uid,
            "name": st.get("name", str(uid)),
            "level": st.get("level", 1), "xp": st.get("xp", 0),
            "rank": st.get("rank", "Наблюдатель рынка"),
            "module_index": st.get("module_index", 0),
            "homework_status": st.get("homework_status", "idle"),
            "homework_comment": st.get("homework_comment", ""),
            "has_photo": bool(st.get("homework_photo")),
            "active_quest": st.get("active_quest"),
            "streak": st.get("streak", 0),
            "badges": st.get("badges", []),
            "is_expired": is_deadline_expired(st),
            "hours_remaining": round(get_deadline_hours_remaining(st), 1),
        }
        for uid, st in user_progress.items()
    ]
    return {"users": result}


@app.get("/api/admin/homework_photo/{user_id}")
async def get_homework_photo(user_id: int, admin_id: int):
    """Return the homework photo submitted by a user (admin only)."""
    check_admin(admin_id)
    st = get_user_state(user_id)
    photo = st.get("homework_photo")
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    return {"photo": photo}


# ── WEBHOOK ───────────────────────────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    """Process incoming Telegram webhook updates."""
    try:
        data = await request.json()
        await asyncio.get_running_loop().run_in_executor(None, process_update, data)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return {"ok": True}


@app.post("/api/admin/reset-webhook")
async def reset_webhook(admin_id: int):
    """Re-register the Telegram webhook. Call this if callbacks stop working."""
    check_admin(admin_id)
    webhook_url = os.getenv("WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=500, detail="WEBHOOK_URL не настроен")
    try:
        from bot import setup_webhook
        await asyncio.get_running_loop().run_in_executor(None, setup_webhook)
        return {"ok": True, "webhook_url": f"{webhook_url}/webhook"}
    except Exception as e:
        logger.error(f"reset-webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/webhook-info")
async def get_webhook_info(admin_id: int):
    """Get current Telegram webhook info for debugging."""
    check_admin(admin_id)
    try:
        import telebot
        from bot import bot as tg_bot
        info = tg_bot.get_webhook_info()
        return {
            "ok": True,
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── MARKET PULSE ──────────────────────────────────────────────────────────────

@app.get("/api/market/pulse")
async def market_pulse_endpoint():
    data = await refresh_market_data()
    return data


# ── ORACLE ────────────────────────────────────────────────────────────────────

@app.get("/api/oracle/daily")
async def oracle_daily(user_id: int):
    oracle = await generate_oracle()
    # Mark that user viewed the oracle today
    state = get_user_state(user_id)
    pet   = state.setdefault("pet", {})
    pet["oracle_viewed_today"] = True
    save_progress()
    return oracle


@app.post("/api/oracle/answer")
async def oracle_answer(req: OracleAnswerRequest):
    state = get_user_state(req.user_id)
    pet   = state.setdefault("pet", {})
    if req.correct:
        pet["oracle_correct"] = pet.get("oracle_correct", 0) + 1
        add_pet_coins(req.user_id, 25)
        pet["happiness"] = min(100, pet.get("happiness", 0) + 15)
        update_trader_dna(req.user_id, "prediction_correct")
    else:
        update_trader_dna(req.user_id, "prediction_wrong")
    save_progress()
    evo = check_and_update_evolution(req.user_id)
    return {
        "ok":            True,
        "oracle_correct":pet.get("oracle_correct", 0),
        "coins_earned":  25 if req.correct else 0,
        "evolution":     evo,
    }


# ── DREAM SYSTEM ──────────────────────────────────────────────────────────────

@app.get("/api/pet/dream/{user_id}")
async def pet_dream_get(user_id: int):
    state = get_user_state(user_id)
    dream = await generate_dream(user_id, state)
    # Update last_online AFTER dream check (dream check uses the old value)
    state["last_online"] = datetime.utcnow().isoformat()
    save_progress()
    if not dream:
        return {"ok": True, "has_dream": False}
    return dream


@app.post("/api/pet/dream/answer")
async def pet_dream_answer(req: DreamAnswerRequest):
    state = get_user_state(req.user_id)
    pet   = state.setdefault("pet", {})
    pet["last_dream_shown"] = datetime.utcnow().isoformat()

    coins = 0
    xp_   = 0
    if req.correct:
        coins = 20
        xp_   = 12
        add_pet_coins(req.user_id, coins)
        pet["happiness"] = min(100, pet.get("happiness", 0) + 20)
        pet["hunger"]    = min(100, pet.get("hunger", 0) + 10)
        if req.concept:
            update_trader_dna(req.user_id, "quiz_correct")
    else:
        if req.concept:
            update_trader_dna(req.user_id, "quiz_wrong")

    save_progress()
    return {"ok": True, "correct": req.correct, "coins_earned": coins, "xp_earned": xp_}


# ── EVOLUTION ─────────────────────────────────────────────────────────────────

@app.get("/api/pet/evolution/{user_id}")
async def pet_evolution(user_id: int):
    evo = check_and_update_evolution(user_id)
    return {"ok": True, **evo, "all_stages": EVOLUTION_STAGES}


# ── TRADER DNA ────────────────────────────────────────────────────────────────

@app.get("/api/user/dna/{user_id}")
async def user_dna(user_id: int):
    return {"ok": True, **get_trader_dna(user_id)}


# ── SOULS SYSTEM ──────────────────────────────────────────────────────────────

class SoulsSpendRequest(BaseModel):
    user_id: int
    amount: int
    reason: Optional[str] = "purchase"

class EstusUseRequest(BaseModel):
    user_id: int

class HollowExitRequest(BaseModel):
    user_id: int

@app.get("/api/souls/{user_id}")
async def souls_get(user_id: int):
    """Return souls summary: balance, dropped, flasks, hollow status, title."""
    return get_souls_state(user_id)


@app.post("/api/souls/earn")
async def souls_earn(req: PetTapRequest):
    """Manually award souls (for testing / admin use). Normally souls come from taps."""
    result = add_souls(req.user_id, 10, source="admin")
    return {"ok": True, **result}


@app.post("/api/souls/spend")
async def souls_spend(req: SoulsSpendRequest):
    """Spend souls on a purchase (hint, customization, roulette, etc.)."""
    result = spend_souls(req.user_id, req.amount, reason=req.reason)
    return result


@app.post("/api/souls/drop/{user_id}")
async def souls_drop(user_id: int):
    """Drop souls on boss failure. Returns amount dropped."""
    result = drop_souls(user_id)
    return {"ok": True, **result}


@app.post("/api/souls/retrieve/{user_id}")
async def souls_retrieve(user_id: int):
    """Retrieve dropped souls (one shot). Call after boss retry success."""
    result = retrieve_souls(user_id)
    return result


@app.post("/api/souls/burn/{user_id}")
async def souls_burn(user_id: int):
    """Permanently burn dropped souls (timeout expired)."""
    burned = burn_dropped_souls(user_id)
    return {"ok": True, "burned": burned}


@app.post("/api/souls/hollow-exit")
async def hollow_exit(req: HollowExitRequest):
    """Pay 100 souls to exit hollow state."""
    result = exit_hollow(req.user_id, souls_cost=100)
    return result


@app.get("/api/souls/hollow-check/{user_id}")
async def hollow_check(user_id: int):
    """Check & update hollow status. Call on user login."""
    result = check_hollow(user_id)
    return result


@app.post("/api/souls/estus-use")
async def estus_use(req: EstusUseRequest):
    """Use one Estus flask (consume a hint charge)."""
    result = use_estus_flask(req.user_id)
    return result


@app.post("/api/souls/bonfire/{user_id}")
async def bonfire_rest(user_id: int):
    """Rest at bonfire: refill Estus flasks, reset module soul tracking, record checkpoint."""
    from boss import get_bloodstains
    state  = get_user_state(user_id)
    module_idx = state.get("module_index", 0)

    # Mark bonfire as rested for this module
    rested = state.setdefault("bonfire_rested", [])
    if module_idx not in rested:
        rested.append(module_idx)

    flasks = refill_estus(user_id)
    title  = update_title(user_id)

    # Burn any unclaimed dropped souls (expired opportunity)
    burned = burn_dropped_souls(user_id)
    if burned > 0:
        logger.info("Bonfire: burned %d unclaimed dropped souls for user %d", burned, user_id)

    # Fetch bloodstains for next module boss (if exists)
    next_module_id = module_idx + 1
    bloodstains = None
    try:
        bloodstains = get_bloodstains(next_module_id)
    except Exception:
        pass

    save_progress()
    return {
        "ok": True,
        "message": "Пламя бонфайра восстановлено. Готовься к следующему испытанию.",
        "estus_flasks": flasks,
        "current_title": title,
        "souls": state.get("souls", 0),
        "burned_dropped": burned,
        "next_boss_bloodstains": bloodstains,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ── HOMUNCULUS SYSTEM (API) ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

from progress import (
    get_homunculus_state, homunculus_process_taps,
    homunculus_revive as _homunculus_revive_fn,
    homunculus_enrage, check_homunculus_health,
    HOMUNCULUS_STAGES,
)

MAX_TAP_BATCH       = 20    # max taps per batch (matches frontend 2-second window cap)
MAX_COMBO_ALLOWED   = 50    # physically impossible to exceed 50 in 2s

class HomunculusTapRequest(BaseModel):
    user_id:        int
    tap_count:      int = 1
    max_combo:      int = 0
    session_token:  Optional[str] = None

class HomunculusReviveRequest(BaseModel):
    user_id:       int
    session_token: Optional[str] = None

@app.get("/api/homunculus/{user_id}")
async def get_homunculus_api(user_id: int):
    """Return homunculus state: stage, status, souls_fed, taps_today, progress, etc."""
    return {"ok": True, **get_homunculus_state(user_id)}

@app.post("/api/homunculus/tap")
async def homunculus_tap_api(req: HomunculusTapRequest):
    """Process a batch of taps. Returns souls_earned, evolution flag, new_stage."""
    # ── Session check ──────────────────────────────────────────────────────
    if not _check_session(req.user_id, req.session_token):
        raise HTTPException(status_code=403, detail="Invalid session")
    # ── Rate limiting: max 10 tap-batches per 5 seconds per user ──────────
    if not _rate_limit(req.user_id, window_seconds=5, max_calls=10):
        raise HTTPException(status_code=429, detail="Too many requests")
    # ── Server-side anti-cheat: cap tap_count and max_combo ───────────────
    tap_count = max(1, min(req.tap_count, MAX_TAP_BATCH))
    max_combo  = max(0, min(req.max_combo, MAX_COMBO_ALLOWED))
    result = homunculus_process_taps(req.user_id, tap_count, max_combo)
    if result.get("evolution"):
        stage_name = result["stage_name"]
        uid = req.user_id
        def _notify_evo():
            try:
                telegram_bot.send_message(
                    uid,
                    f"🧬 <b>ЭВОЛЮЦИЯ!</b>\n\nТвой Гомункул перешёл на стадию:\n<b>{stage_name}</b>!\n\n"
                    f"Множитель тапов: x{result['stage_mult']}",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("homunculus evo notify: %r", e)
        asyncio.get_running_loop().run_in_executor(None, _notify_evo)
    return result

@app.post("/api/homunculus/revive")
async def homunculus_revive_api(req: HomunculusReviveRequest):
    """Spend 200 souls to revive dead homunculus. Stage rolls back by 1."""
    return _homunculus_revive_fn(req.user_id)

@app.get("/api/homunculus/stages")
async def homunculus_stages_api():
    """Return all 7 stage definitions."""
    return {"ok": True, "stages": HOMUNCULUS_STAGES}


# ── PET SYSTEM ────────────────────────────────────────────────────────────────

# Map quiz_ref → lesson_key for pet effects on quiz completion
_QUIZ_REF_TO_LESSON: Dict[str, str] = {
    "basics_quiz":         "market_structure",
    "liquidity_quiz":      "liquidity",
    "poi_quiz":            "order_blocks",
    "fvg_quiz":            "fvg",
    "manipulation_quiz":   "inducement",
    "advanced_blocks_quiz":"breaker_blocks",
    "advanced_models_quiz":"ote",
    "risk_quiz":           "risk_management",
    "strategies_quiz":     "market_maker_model",
}


@app.get("/api/pet/{user_id}")
async def get_pet(user_id: int):
    pet = get_pet_state(user_id)
    return {
        "ok": True,
        "hunger":           round(pet["hunger"]),
        "happiness":        round(pet["happiness"]),
        "health":           round(pet["health"]),
        "pet_xp":           pet["pet_xp"],
        "pet_level":        pet["pet_level"],
        "coins":            pet["coins"],
        "visual_state":     pet["visual_state"],
        "total_taps":       pet["total_taps"],
        "next_level_xp":    pet["next_level_xp"],
        "current_level_xp": pet["current_level_xp"],
    }


@app.post("/api/pet/tap")
async def pet_tap(req: PetTapRequest):
    result = pet_register_tap(req.user_id)
    return {"ok": True, **result}


# ══════════════════════════════════════════════════════════════════════════════
# ── PHASE 4: KNOWLEDGE ROULETTE ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# Topics and questions for the roulette wheel
_ROULETTE_TOPICS = [
    {
        "id": "market_structure",
        "label": "Структура рынка",
        "color": "#c8a84e",
        "questions": [
            {"q": "Что такое Break of Structure (BOS)?", "a": "Слом структуры — пробой последнего значимого HH или LL, подтверждающий смену тренда"},
            {"q": "Чем BOS отличается от CHoCH?", "a": "BOS — продолжение тренда (HH в аптренде), CHoCH — Change of Character, разворот (LH после серии HH)"},
            {"q": "Как определить Higher High (HH) на графике?", "a": "Следующий максимум выше предыдущего максимума при восходящем тренде"},
        ]
    },
    {
        "id": "liquidity",
        "label": "Ликвидность",
        "color": "#00d4ff",
        "questions": [
            {"q": "Где Smart Money чаще всего охотится за ликвидностью?", "a": "За очевидными уровнями поддержки/сопротивления, за ровными числами и swing high/low"},
            {"q": "Что такое Equal Highs (EQH) и почему они важны?", "a": "EQH — два или более максимума на одном уровне. Они накапливают стопы быков — идеальная цель для sweep"},
            {"q": "Что происходит после sweep ликвидности?", "a": "Цена разворачивается — Smart Money набирают позицию против хвоста. Ищи OB или FVG для входа"},
        ]
    },
    {
        "id": "order_blocks",
        "label": "Ордер-блоки",
        "color": "#a78bfa",
        "questions": [
            {"q": "Как определить валидный бычий Order Block?", "a": "Последняя медвежья свеча перед импульсным движением вверх. Должен быть создан BOS выше него"},
            {"q": "Что делает Order Block невалидным?", "a": "Если цена полностью проходит сквозь него (mitigation) или если не был создан новый BOS"},
            {"q": "Что такое Breaker Block?", "a": "Бывший OB, который был пробит. Меняет полярность: медвежий OB становится зоной сопротивления для лонгов"},
        ]
    },
    {
        "id": "fvg",
        "label": "Fair Value Gap",
        "color": "#00e87a",
        "questions": [
            {"q": "Из скольких свечей формируется FVG?", "a": "Из трёх свечей: тело средней свечи не перекрывается тенями первой и третьей"},
            {"q": "Как торговать на FVG?", "a": "Жди возврата (retracement) цены в зону FVG. Ищи реакцию (отскок или поглощение) и входи по направлению импульса"},
            {"q": "В чём разница между Bullish FVG и Bearish FVG?", "a": "Bullish FVG — gap направлен вверх (бычий импульс), цена должна вернуться снизу. Bearish — наоборот"},
        ]
    },
    {
        "id": "inducement",
        "label": "Inducement",
        "color": "#f59e0b",
        "questions": [
            {"q": "Что такое Inducement в SMC?", "a": "Ложный прорыв или уровень, созданный для привлечения розничных трейдеров перед реальным движением"},
            {"q": "Как Inducement связан с ликвидностью?", "a": "Inducement создаёт пулы ликвидности (стопы и ордера). Smart Money используют их для набора крупных позиций"},
            {"q": "Как определить Inducement на графике?", "a": "Ищи swing high/low, который выглядит как очевидный уровень для большинства трейдеров — именно туда пойдёт цена за стопами"},
        ]
    },
    {
        "id": "premium_discount",
        "label": "Premium/Discount",
        "color": "#ff4d6d",
        "questions": [
            {"q": "Что такое Premium и Discount зоны?", "a": "Premium — верхние 50% торгового диапазона (дорого для покупки). Discount — нижние 50% (выгодно для лонга)"},
            {"q": "Как определить середину диапазона?", "a": "Fibonacci 50% между последним значимым swing high и swing low текущей структуры"},
            {"q": "В какой зоне Smart Money предпочитают покупать?", "a": "В Discount зоне (ниже 50% диапазона) при бычьем тренде. В Premium — продают"},
        ]
    },
    {
        "id": "risk_management",
        "label": "Риск-менеджмент",
        "color": "#e8751a",
        "questions": [
            {"q": "Какой максимальный риск рекомендуется на одну сделку?", "a": "1-2% от депозита. Более 2% — азартная игра, не торговля"},
            {"q": "Что такое Risk/Reward Ratio (RRR) и какой минимум?", "a": "Соотношение потенциальной прибыли к убытку. Минимум 1:2, в SMC ищут 1:3 и выше"},
            {"q": "Как рассчитать размер позиции?", "a": "Size = (Капитал × %риска) / (Entry − Стоп). Стоп всегда определяет размер, не наоборот"},
        ]
    },
    {
        "id": "killzones",
        "label": "Killzones",
        "color": "#78716c",
        "questions": [
            {"q": "Назови три основные Killzone сессии", "a": "Asian Killzone (02:00-05:00 UTC), London Killzone (07:00-10:00 UTC), New York Killzone (13:00-16:00 UTC)"},
            {"q": "Почему Killzone важны для трейдера?", "a": "В это время наибольший объём и манипуляции Smart Money. Лучшие сетапы формируются именно тут"},
            {"q": "Что такое AMD Model в контексте сессий?", "a": "Accumulation (Asian) → Manipulation (London open) → Distribution (New York). Классическая трёхфазная модель"},
        ]
    },
]

# In-memory store for active roulette spins: spin_id → {user_id, topic, question, bet, timestamp}
_active_spins: dict = {}

class RouletteSpinRequest(BaseModel):
    user_id: int
    bet: int  # 10 / 25 / 50 / 100

class RouletteAnswerRequest(BaseModel):
    user_id: int
    spin_id: str
    is_correct: bool  # frontend validates answer vs displayed correct_answer

@app.post("/api/roulette/spin")
async def roulette_spin(req: RouletteSpinRequest):
    """Spend souls to spin the roulette. Returns topic + question. Answer via /roulette/answer."""
    VALID_BETS = {10, 25, 50, 100}
    if req.bet not in VALID_BETS:
        raise HTTPException(status_code=400, detail=f"Ставка должна быть одной из: {sorted(VALID_BETS)}")

    # Deduct souls upfront
    result = spend_souls(req.user_id, req.bet, reason="roulette_bet")
    if not result["ok"]:
        return {"ok": False, "error": "not_enough_souls", "souls": result.get("total", 0)}

    # Pick random topic and question
    topic = random.choice(_ROULETTE_TOPICS)
    question_data = random.choice(topic["questions"])

    spin_id = f"{req.user_id}_{int(datetime.utcnow().timestamp())}"
    _active_spins[spin_id] = {
        "user_id": req.user_id,
        "topic_id": topic["id"],
        "topic_label": topic["label"],
        "question": question_data["q"],
        "answer": question_data["a"],
        "bet": req.bet,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Clean old spins (older than 10 minutes)
    cutoff = datetime.utcnow().timestamp() - 600
    stale = [k for k, v in _active_spins.items() if float(v["timestamp"].split(".")[0].replace("T", " ").replace("-", "").replace(":", "").replace(" ", "")[:14]) < cutoff * 0 + 0 or
             datetime.fromisoformat(v["timestamp"]).timestamp() < cutoff]
    for k in stale:
        _active_spins.pop(k, None)

    return {
        "ok": True,
        "spin_id": spin_id,
        "topic": {"id": topic["id"], "label": topic["label"], "color": topic["color"]},
        "all_topics": [{"id": t["id"], "label": t["label"], "color": t["color"]} for t in _ROULETTE_TOPICS],
        "question": question_data["q"],
        "correct_answer": question_data["a"],
        "bet": req.bet,
        "potential_win": req.bet * 3,
        "souls_remaining": result.get("total", 0),
    }


@app.post("/api/roulette/answer")
async def roulette_answer(req: RouletteAnswerRequest):
    """Submit roulette answer. Win x3 souls or lose the bet."""
    spin = _active_spins.pop(req.spin_id, None)
    if not spin:
        return {"ok": False, "error": "spin_not_found_or_expired"}
    if spin["user_id"] != req.user_id:
        return {"ok": False, "error": "spin_belongs_to_another_user"}

    if req.is_correct:
        # Win: get back bet + 2x profit = 3x total
        winnings = spin["bet"] * 3
        result = add_souls(req.user_id, winnings, source="roulette_win")
        return {
            "ok": True,
            "outcome": "win",
            "souls_won": winnings,
            "total_souls": result.get("total", 0),
            "message": f"⚡ Правильно! +{winnings} душ (x3)",
        }
    else:
        # Already deducted. Return confirmation of loss.
        state = get_user_state(req.user_id)
        return {
            "ok": True,
            "outcome": "loss",
            "souls_lost": spin["bet"],
            "total_souls": state.get("souls", 0),
            "message": f"💀 Неверно. -{spin['bet']} душ.",
        }


# ══════════════════════════════════════════════════════════════════════════════
# ── PHASE 4: INVASIONS ───────────────────────────────────────════════════════
# ══════════════════════════════════════════════════════════════════════════════

_INVASION_TASKS = [
    {
        "id": "inv_bos_1",
        "question": "На H4 графике BTC сформировался BOS вниз. Определи первый валидный медвежий OB выше текущей цены.",
        "answer": "Последняя бычья свеча перед импульсным снижением, после которого был создан BOS. Уровень от её High до Low — это медвежий OB.",
        "difficulty": "hard",
        "souls_reward": 50,
    },
    {
        "id": "inv_liq_1",
        "question": "На M15 есть три Equal Lows под ценой. Ниже них — FVG. Опиши твой план входа в лонг.",
        "answer": "Жди sweep Equal Lows (сбор ликвидности), затем реакцию в FVG зоне с бычьим подтверждением (bullish engulfing/pin bar). Стоп под FVG.",
        "difficulty": "hard",
        "souls_reward": 50,
    },
    {
        "id": "inv_fvg_1",
        "question": "Цена создала Bearish FVG на H1 и теперь ретестирует её снизу. Какие условия делают вход в шорт валидным?",
        "answer": "1) Bearish структура на старшем ТФ. 2) FVG не заполнена полностью. 3) Есть ликвидность выше текущей цены для сбора. 4) Вход с подтверждением на M5/M15.",
        "difficulty": "hard",
        "souls_reward": 50,
    },
    {
        "id": "inv_rb_1",
        "question": "Объясни разницу между Rejection Block и Order Block. Когда ты торгуешь первый вместо второго?",
        "answer": "Rejection Block — зона отторжения с длинным хвостом без реального тела. OB — последняя противоположная свеча перед импульсом. RB торгуем когда нет чёткого OB, но есть явное отторжение от уровня.",
        "difficulty": "medium",
        "souls_reward": 50,
    },
    {
        "id": "inv_mm_1",
        "question": "Как Market Maker Model объясняет движение цены от AMD? Разбери на примере лонговой позиции.",
        "answer": "A (Accumulation/Asia): консолидация, набор позиций MM. M (Manipulation/London): ложный пробой вниз, сбор стопов лонговщиков. D (Distribution/NY): реальное движение вверх, ликвидация шортистов.",
        "difficulty": "hard",
        "souls_reward": 75,
    },
]

class InvasionAnswerRequest(BaseModel):
    user_id: int
    invasion_id: str
    answer_text: str  # free text — admin grades later; auto-pass for now after time check

@app.get("/api/invasion/check/{user_id}")
async def invasion_check(user_id: int):
    """Check if user has an active invasion. Returns task if active."""
    state = get_user_state(user_id)
    inv = state.get("active_invasion")
    if not inv:
        return {"ok": True, "has_invasion": False}

    # Check deadline
    deadline = datetime.fromisoformat(inv["deadline"])
    now = datetime.utcnow()
    if now > deadline:
        # Expired — mark as failed
        if inv.get("result") is None:
            inv["result"] = "defeated"
            # Streak penalty
            state["streak"] = max(0, state.get("streak", 0) - 1)
            save_progress()
        return {"ok": True, "has_invasion": True, "expired": True, "invasion": inv}

    return {
        "ok": True,
        "has_invasion": True,
        "expired": False,
        "invasion": inv,
        "minutes_left": max(0, int((deadline - now).total_seconds() / 60)),
    }


@app.post("/api/invasion/answer")
async def invasion_answer(req: InvasionAnswerRequest):
    """Submit invasion answer. Awards souls + badge."""
    state = get_user_state(req.user_id)
    inv = state.get("active_invasion")
    if not inv or inv.get("id") != req.invasion_id:
        return {"ok": False, "error": "no_active_invasion"}

    deadline = datetime.fromisoformat(inv["deadline"])
    if datetime.utcnow() > deadline:
        inv["result"] = "defeated"
        save_progress()
        return {"ok": False, "error": "invasion_expired", "result": "defeated"}

    if inv.get("result"):
        return {"ok": False, "error": "already_answered", "result": inv["result"]}

    # Mark survived
    inv["result"] = "survived"
    inv["answer"] = req.answer_text
    inv["answered_at"] = datetime.utcnow().isoformat()

    souls_reward = inv.get("souls_reward", 50)
    add_souls(req.user_id, souls_reward, source="invasion_survived")
    award_badge(req.user_id, "invader_slayer")

    # Update invasion stats
    stats = state.setdefault("invasion_stats", {"survived": 0, "defeated": 0})
    stats["survived"] = stats.get("survived", 0) + 1
    save_progress()

    return {
        "ok": True,
        "result": "survived",
        "souls_earned": souls_reward,
        "total_souls": state.get("souls", 0),
        "message": "⚔️ Вторжение отражено! +50 душ",
    }


async def _send_invasion(user_id: int, task: dict):
    """Send invasion notification to user via bot."""
    deadline = datetime.utcnow() + timedelta(minutes=30)
    state = get_user_state(user_id)
    state["active_invasion"] = {
        "id": task["id"],
        "question": task["question"],
        "answer_hint": task["answer"],
        "souls_reward": task["souls_reward"],
        "deadline": deadline.isoformat(),
        "result": None,
        "sent_at": datetime.utcnow().isoformat(),
    }
    save_progress()
    try:
        text = (
            f"⚔️ <b>ВТОРЖЕНИЕ!</b>\n\n"
            f"У тебя <b>30 минут</b> на решение.\n\n"
            f"❓ <b>{task['question']}</b>\n\n"
            f"Награда: <b>{task['souls_reward']} душ</b>\n"
            f"Провалишь — потеряешь streak.\n\n"
            f"Открой приложение, чтобы ответить!"
        )
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda u=user_id, t=text: telegram_bot.send_message(u, t, parse_mode="HTML")
        )
        logger.info("Invasion sent to user %d", user_id)
    except Exception as e:
        logger.warning("Invasion notify failed for %d: %r", user_id, e)


async def _invasion_weekly_loop():
    """Every Monday at 12:00 MSK, send invasions to random active users."""
    _last_invasion_week: str | None = None
    while True:
        await asyncio.sleep(60)
        try:
            now_msk = _msk_now()
            # Monday = 0, hour 12, minute 0
            week_key = f"{now_msk.isocalendar()[1]}-{now_msk.year}"
            if now_msk.weekday() != 0 or now_msk.hour != 12 or now_msk.minute != 0:
                continue
            if _last_invasion_week == week_key:
                continue
            _last_invasion_week = week_key
            logger.info("Invasion weekly dispatch: week %s", week_key)

            # Select users who completed at least 1 module and have no active invasion
            eligible = [
                uid for uid, st in user_progress.items()
                if st.get("module_index", 0) >= 1
                and not st.get("active_invasion", {}).get("result") is None is False
            ]
            # Pick up to 20% of users (min 1)
            count = max(1, len(eligible) // 5)
            targets = random.sample(eligible, min(count, len(eligible)))
            task = random.choice(_INVASION_TASKS)
            for uid in targets:
                await _send_invasion(int(uid), task)
        except Exception as e:
            logger.error("_invasion_weekly_loop error: %r", e)


# ══════════════════════════════════════════════════════════════════════════════
# ── PHASE 4: PvP BATTLE MARKUP ───────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# In-memory matchmaking queue: {user_id: {joined_at, module_index, chart_seed}}
_pvp_queue: dict = {}
# Active matches: {match_id: {p1, p2, chart_seed, chart_key, started_at, submissions}}
_pvp_matches: dict = {}

_PVP_CHART_KEYS = [
    "market_structure", "liquidity", "order_blocks", "fvg",
    "inducement", "killzones", "risk_management",
]

class PvPFindRequest(BaseModel):
    user_id: int

class PvPSubmitRequest(BaseModel):
    user_id: int
    match_id: str
    # Markup data: list of zones/annotations the player drew
    markup: list  # [{"type": "ob"|"fvg"|"bos"|"liq", "x1": float, "x2": float, "y1": float, "y2": float}]
    # Self-assessment score (0-100) until we have auto-grading
    self_score: int

@app.post("/api/pvp/find-match")
async def pvp_find_match(req: PvPFindRequest):
    """Find or create a PvP match. Returns match_id and chart info."""
    state = get_user_state(req.user_id)
    user_module = state.get("module_index", 0)

    # Check if already in queue
    if req.user_id in _pvp_queue:
        entry = _pvp_queue[req.user_id]
        # Still waiting
        wait_sec = (datetime.utcnow() - datetime.fromisoformat(entry["joined_at"])).seconds
        if wait_sec > 120:
            # Timeout — remove from queue
            del _pvp_queue[req.user_id]
            return {"ok": False, "status": "timeout", "message": "Не удалось найти соперника. Попробуй позже."}
        return {"ok": True, "status": "waiting", "wait_seconds": wait_sec}

    # Look for opponent in queue (within ±1 module level)
    opponent_id = None
    for uid, entry in list(_pvp_queue.items()):
        if uid == req.user_id:
            continue
        if abs(entry["module_index"] - user_module) <= 1:
            opponent_id = uid
            break

    if opponent_id:
        # Match found! Create match
        opp_entry = _pvp_queue.pop(opponent_id)
        chart_key = random.choice(_PVP_CHART_KEYS)
        chart_seed = random.randint(1000, 9999)
        match_id = f"pvp_{req.user_id}_{opponent_id}_{chart_seed}"
        _pvp_matches[match_id] = {
            "p1": req.user_id,
            "p2": opponent_id,
            "chart_key": chart_key,
            "chart_seed": chart_seed,
            "started_at": datetime.utcnow().isoformat(),
            "submissions": {},
            "result": None,
        }
        return {
            "ok": True,
            "status": "matched",
            "match_id": match_id,
            "chart_key": chart_key,
            "chart_seed": chart_seed,
            "opponent_module": opp_entry["module_index"],
            "time_limit_seconds": 180,
        }
    else:
        # Add to queue
        _pvp_queue[req.user_id] = {
            "joined_at": datetime.utcnow().isoformat(),
            "module_index": user_module,
        }
        return {"ok": True, "status": "waiting", "wait_seconds": 0}


@app.post("/api/pvp/submit")
async def pvp_submit(req: PvPSubmitRequest):
    """Submit PvP markup. When both players submit, calculate winner."""
    match = _pvp_matches.get(req.match_id)
    if not match:
        return {"ok": False, "error": "match_not_found"}
    if req.user_id not in (match["p1"], match["p2"]):
        return {"ok": False, "error": "not_in_match"}
    if req.user_id in match["submissions"]:
        return {"ok": False, "error": "already_submitted"}

    match["submissions"][req.user_id] = {
        "markup": req.markup,
        "self_score": req.self_score,
        "submitted_at": datetime.utcnow().isoformat(),
    }

    # Check if both submitted
    if len(match["submissions"]) < 2:
        return {"ok": True, "status": "waiting_for_opponent"}

    # Both submitted — determine winner by self_score (until auto-grading)
    p1_score = match["submissions"].get(match["p1"], {}).get("self_score", 0)
    p2_score = match["submissions"].get(match["p2"], {}).get("self_score", 0)

    if p1_score > p2_score:
        winner, loser = match["p1"], match["p2"]
    elif p2_score > p1_score:
        winner, loser = match["p2"], match["p1"]
    else:
        winner, loser = None, None  # Draw

    match["result"] = {
        "winner": winner,
        "loser": loser,
        "p1_score": p1_score,
        "p2_score": p2_score,
        "draw": winner is None,
    }

    # Award souls
    if winner:
        add_souls(winner, 30, source="pvp_win")
        pvp_stats_w = get_user_state(winner).setdefault("pvp_stats", {"wins": 0, "losses": 0})
        pvp_stats_w["wins"] = pvp_stats_w.get("wins", 0) + 1
        pvp_stats_l = get_user_state(loser).setdefault("pvp_stats", {"wins": 0, "losses": 0})
        pvp_stats_l["losses"] = pvp_stats_l.get("losses", 0) + 1
    else:
        # Draw: both get 10
        for pid in [match["p1"], match["p2"]]:
            add_souls(pid, 10, source="pvp_draw")
    save_progress()

    is_winner = req.user_id == winner
    is_draw = winner is None
    my_score = match["submissions"][req.user_id]["self_score"]
    opp_id = match["p2"] if req.user_id == match["p1"] else match["p1"]
    opp_score = match["submissions"][opp_id]["self_score"]

    return {
        "ok": True,
        "status": "complete",
        "result": "win" if is_winner else ("draw" if is_draw else "loss"),
        "my_score": my_score,
        "opponent_score": opp_score,
        "souls_earned": 30 if is_winner else (10 if is_draw else 0),
        "match": match["result"],
    }


@app.get("/api/pvp/result/{match_id}")
async def pvp_result(match_id: str, user_id: int):
    """Poll for match result (used by waiting player)."""
    match = _pvp_matches.get(match_id)
    if not match:
        return {"ok": False, "error": "match_not_found"}
    if not match.get("result"):
        return {"ok": True, "status": "pending"}
    r = match["result"]
    is_winner = user_id == r.get("winner")
    is_draw = r.get("draw", False)
    return {
        "ok": True,
        "status": "complete",
        "result": "win" if is_winner else ("draw" if is_draw else "loss"),
        "match": r,
    }


@app.get("/api/pvp/stats/{user_id}")
async def pvp_stats(user_id: int):
    state = get_user_state(user_id)
    stats = state.get("pvp_stats", {"wins": 0, "losses": 0})
    return {"ok": True, "stats": stats}


# Startup is handled entirely by the lifespan context manager above.


async def _keep_alive_loop(base_url: str):
    """Ping /health every 10 minutes so Render free tier doesn't sleep.
    Also re-registers the webhook every 2 hours as a safeguard."""
    import httpx
    health_url = f"{base_url}/health"
    ping_count = 0
    while True:
        await asyncio.sleep(10 * 60)  # 10 minutes
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(health_url)
            ping_count += 1
            # Re-register webhook every 2 hours (12 pings × 10 min = 120 min)
            if ping_count % 12 == 0:
                await asyncio.get_running_loop().run_in_executor(None, setup_webhook)
                logger.info("Keep-alive: webhook re-registered")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")


# ── Homunculus health loop (hourly) ──────────────────────────────────────────

async def _homunculus_health_loop():
    """Check homunculus health every hour. Sends Telegram notifications on status change."""
    while True:
        await asyncio.sleep(3600)  # every hour
        try:
            for uid in list(user_progress.keys()):
                try:
                    result = check_homunculus_health(int(uid))
                    if not result.get("changed"):
                        continue
                    new_status = result["new_status"]
                    tpl = None
                    if new_status == "hungry":
                        tpl = "homunculus_hungry"
                    elif new_status == "dying":
                        tpl = "homunculus_dying"
                    elif new_status == "dead":
                        tpl = "homunculus_dead"
                    if tpl:
                        await notification_service.send(int(uid), tpl)
                except Exception as e:
                    logger.debug("homunculus health check user %s: %r", uid, e)
        except Exception as e:
            logger.error("_homunculus_health_loop error: %r", e)


# ── Daily Challenge push loop (09:00 MSK) ─────────────────────────────────────

async def _daily_challenge_loop():
    """At 09:00 MSK every day, push the daily challenge to all known users via bot."""
    from datetime import timezone
    _sent_date: str | None = None

    while True:
        await asyncio.sleep(60)  # check every minute
        try:
            now_msk = _msk_now()
            today   = now_msk.strftime("%Y-%m-%d")
            # Fire once per day at 09:00 MSK (window 09:00–09:01)
            if now_msk.hour != 9 or now_msk.minute != 0:
                continue
            if _sent_date == today:
                continue  # already sent today

            _sent_date = today
            logger.info("Daily challenge push: %s", today)

            
            user_ids = list(user_progress.keys())
            sent = 0
            for uid in user_ids:
                try:
                    ch = get_daily_challenge(int(uid))
                    text = (
                        f"⚔️ <b>Ежедневный вызов</b> — {today}\n\n"
                        f"<b>{ch['question']}</b>\n\n"
                        f"Серия: {ch['streak']} дней 🔥\n"
                        f"Награда: <b>{ch['souls_reward']} душ</b>\n\n"
                        f"Открой приложение, чтобы ответить!"
                    )
                    await asyncio.get_running_loop().run_in_executor(
                        None,
                        lambda u=int(uid), t=text: telegram_bot.send_message(
                            u, t, parse_mode="HTML"
                        )
                    )
                    sent += 1
                except Exception as e:
                    logger.debug("Daily push failed for %s: %r", uid, e)
            logger.info("Daily challenge: pushed to %d/%d users", sent, len(user_ids))
        except Exception as e:
            logger.error("_daily_challenge_loop error: %r", e)


# ── Streak warning loop (20:00 MSK) ──────────────────────────────────────────

async def _streak_warning_loop():
    """At 20:00 MSK, warn users who haven't done their daily challenge yet."""
    _warned_date: str | None = None
    while True:
        await asyncio.sleep(60)
        try:
            now_msk = _msk_now()
            today   = now_msk.strftime("%Y-%m-%d")
            if now_msk.hour != 20 or now_msk.minute != 0:
                continue
            if _warned_date == today:
                continue
            _warned_date = today
            for uid in list(user_progress.keys()):
                try:
                    st = get_user_state(int(uid))
                    # Only warn if daily challenge not yet completed today
                    last_daily = st.get("daily_bonus_claimed")
                    if last_daily and last_daily.startswith(today):
                        continue  # already done today
                    streak = st.get("streak", 0)
                    if streak < 1:
                        continue  # nothing to lose
                    await notification_service.send(
                        int(uid), "streak_warning",
                        {"streak_days": streak}
                    )
                except Exception as e:
                    logger.debug("streak_warning uid=%s: %r", uid, e)
        except Exception as e:
            logger.error("_streak_warning_loop error: %r", e)


# ── Notification queue flush loop (08:00 MSK) ────────────────────────────────

async def _notification_queue_flush_loop():
    """At 08:00 MSK flush queued notifications (quiet-hour holdovers)."""
    _flushed_date: str | None = None
    while True:
        await asyncio.sleep(60)
        try:
            now_msk = _msk_now()
            today   = now_msk.strftime("%Y-%m-%d")
            if now_msk.hour != 8 or now_msk.minute != 0:
                continue
            if _flushed_date == today:
                continue
            _flushed_date = today
            await notification_service.flush_all_queues()
            logger.info("Notification queues flushed at 08:00 MSK")
        except Exception as e:
            logger.error("_notification_queue_flush_loop error: %r", e)


# ── Homework deadline check loop (hourly) ────────────────────────────────────

async def _deadline_check_loop():
    """Every hour, warn users whose module deadline is within 3 hours."""
    while True:
        await asyncio.sleep(3600)
        try:
            now_utc = datetime.utcnow()
            for uid in list(user_progress.keys()):
                try:
                    st = get_user_state(int(uid))
                    dl = st.get("module_deadline")
                    if not dl:
                        continue
                    dl_dt = datetime.fromisoformat(dl)
                    hours_left = (dl_dt - now_utc).total_seconds() / 3600
                    if 2.5 <= hours_left <= 3.5:
                        await notification_service.send(
                            int(uid), "homework_deadline"
                        )
                except Exception as e:
                    logger.debug("deadline_check uid=%s: %r", uid, e)
        except Exception as e:
            logger.error("_deadline_check_loop error: %r", e)
