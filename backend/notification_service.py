"""
notification_service.py — Voice of the Alchemist

Unified Telegram notification system with:
- Message templates keyed by event type
- Priority queue (4 levels)
- Anti-spam: max 3 per day per user
- Quiet hours: 23:00–08:00 MSK
- Hollow mode: max 1 notification per 3 days
- Queuing with flush at quiet-hour exit (08:00)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── MSK timezone (UTC+3) ──────────────────────────────────────────────────────
MSK = timezone(timedelta(hours=3))

# ── Message templates ─────────────────────────────────────────────────────────
TEMPLATES: Dict[str, str] = {
    "daily_challenge":      "⚗️ Утренний вызов готов. {streak_days} дней без промаха. Не сломай серию.",
    "homunculus_hungry":    "⚗️ Твой Гомункул голодает. Зайди покорми его.",
    "homunculus_dying":     "☠️ Твой Гомункул при смерти. Воскрешение будет стоить 200 душ и стадию.",
    "homunculus_dead":      "💀 Твой Гомункул мёртв. Он ждал тебя.",
    "homunculus_evolution": "🧬 ЭВОЛЮЦИЯ! Твой Гомункул стал: <b>{stage_name}</b>!",
    "clan_suffering":       "⚔️ Твой клан <b>{clan_name}</b> теряет прогресс. Не подводи своих.",
    "invasion":             "⚔️ <b>ВТОРЖЕНИЕ!</b> Неизвестный бросил тебе вызов. 30 минут на ответ.",
    "rank_lost":            "📉 <b>{username}</b> забрал твою #{position} позицию. Вернёшь?",
    "rank_gained":          "📈 +1 позиция! Теперь ты #{position} в рейтинге.",
    "friend_evolved":       "🧬 <b>{username}</b> из клана достиг стадии {stage_name}. А ты — {your_stage}.",
    "streak_warning":       "🔥 Streak <b>{streak_days} дней</b> сгорит, если не зайдёшь до полуночи.",
    "homework_deadline":    "📝 Дедлайн через 3 часа. Не сдашь — потеряешь души модуля.",
    "boss_defeated_other":  "🏆 <b>{username}</b> победил босса {boss_name}. На нём полегло {death_rate}% учеников.",
    "hollow_reminder":      "🌑 Мы ждём тебя. Гомункул ждёт.",
    "onboarding_welcome":   "⚗️ Добро пожаловать! Твой первый Гомункул рождён. Тапай его, чтобы фармить <b>души</b>.",
    "referral_bonus":       "🧪 Новый ученик пришёл по твоей ссылке! <b>+{souls} душ</b> начислено.",
    "referral_boss":        "⚔️ Твой приглашённый ученик <b>{username}</b> победил первого босса! +200 душ тебе.",
    "season_end":           "🏆 Сезон <b>{season_name}</b> завершён! Новый сезон уже скоро.",
    "season_reward":        "🎁 Сезонная награда разблокирована: <b>{reward_name}</b>!",
    "boss_death":           "💀 Ты пал перед боссом <b>{boss_name}</b>. Потеряно {souls_lost} душ. Вернись и возьми реванш.",
}

# ── Priority levels (4 = critical, 1 = low) ───────────────────────────────────
PRIORITY: Dict[str, int] = {
    "invasion":             4,
    "homunculus_dead":      4,
    "daily_challenge":      3,
    "clan_suffering":       3,
    "homunculus_dying":     3,
    "streak_warning":       3,
    "homework_deadline":    3,
    "homunculus_evolution": 3,
    "onboarding_welcome":   3,
    "rank_lost":            2,
    "homunculus_hungry":    2,
    "referral_bonus":       2,
    "referral_boss":        2,
    "rank_gained":          2,
    "season_end":           2,
    "season_reward":        2,
    "friend_evolved":       1,
    "boss_defeated_other":  1,
    "hollow_reminder":      1,
    "boss_death":           2,
}

MAX_DAILY = 3
QUIET_START = 23   # 23:00 MSK — quiet begins
QUIET_END   = 8    # 08:00 MSK — quiet ends
HOLLOW_INTERVAL_DAYS = 3


def _msk_now() -> datetime:
    return datetime.now(MSK)


def _is_quiet_hour() -> bool:
    h = _msk_now().hour
    return h >= QUIET_START or h < QUIET_END


def _format(template_key: str, params: dict) -> str:
    tpl = TEMPLATES.get(template_key, template_key)
    try:
        return tpl.format(**params)
    except (KeyError, ValueError):
        return tpl


class NotificationService:
    """
    Manages all Telegram notifications.
    Works purely with in-memory state + existing JSON progress storage.
    """

    def __init__(self):
        self._bot = None
        # {user_id: {date_str: int}} — resets daily automatically
        self._daily_counts: Dict[int, Dict[str, int]] = {}
        # {user_id: [(priority, template, params)]}
        self._queues: Dict[int, list] = {}

    def set_bot(self, bot) -> None:
        self._bot = bot

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _today(self) -> str:
        return _msk_now().strftime("%Y-%m-%d")

    def _get_count(self, user_id: int) -> int:
        return self._daily_counts.get(user_id, {}).get(self._today(), 0)

    def _inc_count(self, user_id: int) -> None:
        today = self._today()
        if user_id not in self._daily_counts:
            self._daily_counts[user_id] = {}
        # Remove old dates
        self._daily_counts[user_id] = {today: self._daily_counts[user_id].get(today, 0)}
        self._daily_counts[user_id][today] += 1

    def _is_hollow(self, user_id: int) -> bool:
        try:
            from progress import get_user_state
            st = get_user_state(user_id)
            hs = st.get("hollow_since")
            if not hs:
                return False
            since = datetime.fromisoformat(hs)
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - since).days >= 7
        except Exception:
            return False

    def _hollow_rate_ok(self, user_id: int) -> bool:
        """Returns True if a hollow-mode notification may be sent now."""
        if not self._is_hollow(user_id):
            return True
        try:
            from progress import get_user_state
            st = get_user_state(user_id)
            last = st.get("last_hollow_notif")
            if last:
                last_dt = datetime.fromisoformat(last)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - last_dt).days < HOLLOW_INTERVAL_DAYS:
                    return False
        except Exception:
            pass
        return True

    def _record_hollow_notif(self, user_id: int) -> None:
        try:
            from progress import get_user_state, save_progress
            st = get_user_state(user_id)
            st["last_hollow_notif"] = datetime.now(timezone.utc).isoformat()
            save_progress()
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────────

    async def send(self, user_id: int, template: str, params: dict = None) -> bool:
        """
        Send a notification.
        Returns True if delivered immediately, False if queued or dropped.
        """
        if params is None:
            params = {}
        if not self._bot:
            logger.debug("NotificationService: bot not configured, skipping")
            return False

        priority = PRIORITY.get(template, 1)

        # Hollow mode: suppress all non-hollow-reminder notifications
        if self._is_hollow(user_id) and template != "hollow_reminder":
            return False
        # hollow_reminder rate limit
        if template == "hollow_reminder" and not self._hollow_rate_ok(user_id):
            return False

        text = _format(template, params)

        # Quiet hours → queue
        if _is_quiet_hour():
            self._enqueue(user_id, priority, template, params)
            return False

        # Daily limit → queue
        if self._get_count(user_id) >= MAX_DAILY:
            self._enqueue(user_id, priority, template, params)
            return False

        return await self._deliver(user_id, text, template, priority)

    async def _deliver(self, user_id: int, text: str, template: str, priority: int) -> bool:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._bot.send_message(user_id, text, parse_mode="HTML")
            )
            self._inc_count(user_id)
            if template == "hollow_reminder":
                self._record_hollow_notif(user_id)
            logger.debug("Notification sent uid=%d tpl=%s", user_id, template)
            return True
        except Exception as e:
            logger.warning("Notification failed uid=%d tpl=%s: %r", user_id, template, e)
            return False

    def _enqueue(self, user_id: int, priority: int, template: str, params: dict) -> None:
        if user_id not in self._queues:
            self._queues[user_id] = []
        # Deduplicate: remove existing entry for same template, keep new one (might have updated params)
        self._queues[user_id] = [q for q in self._queues[user_id] if q[1] != template]
        self._queues[user_id].append((priority, template, params))
        # Keep only top MAX_DAILY×2 items by priority
        self._queues[user_id].sort(key=lambda x: x[0], reverse=True)
        self._queues[user_id] = self._queues[user_id][: MAX_DAILY * 2]

    async def flush_queue(self, user_id: int) -> None:
        """Send queued notifications for one user (called at 08:00 or on app open)."""
        if user_id not in self._queues or not self._queues[user_id]:
            return
        if _is_quiet_hour():
            return
        queue = sorted(self._queues[user_id], key=lambda x: x[0], reverse=True)
        self._queues[user_id] = []
        for priority, template, params in queue:
            if self._get_count(user_id) >= MAX_DAILY:
                break
            text = _format(template, params)
            await self._deliver(user_id, text, template, priority)
            await asyncio.sleep(0.05)

    async def flush_all_queues(self) -> None:
        """Flush all pending queued notifications. Called at 08:00 MSK."""
        for uid in list(self._queues.keys()):
            try:
                await self.flush_queue(uid)
            except Exception as e:
                logger.debug("flush_all_queues uid=%s: %r", uid, e)

    async def send_to_all(self, template: str, params_fn=None) -> None:
        """
        Broadcast a notification to all known users.
        params_fn(user_id, state) → dict | None. Return None to skip user.
        """
        try:
            from progress import user_progress, get_user_state
            for uid_raw in list(user_progress.keys()):
                try:
                    uid = int(uid_raw)
                    p = params_fn(uid, get_user_state(uid)) if params_fn else {}
                    if p is None:
                        continue
                    await self.send(uid, template, p)
                    await asyncio.sleep(0.06)   # ~16 msg/s to avoid bot rate-limit
                except Exception as e:
                    logger.debug("send_to_all uid=%s: %r", uid_raw, e)
        except Exception as e:
            logger.error("send_to_all error: %r", e)


# ── Global singleton ──────────────────────────────────────────────────────────
notification_service = NotificationService()
