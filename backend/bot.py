import html as _html
import os
import logging
from dotenv import load_dotenv
import telebot
from telebot import types

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN   = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")

_cached_admin_ids: set = set()

def _admin_ids() -> set:
    global _cached_admin_ids
    if not _cached_admin_ids:
        raw = os.getenv("ADMIN_ID", "0")
        _cached_admin_ids = {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}
    return _cached_admin_ids

def is_admin(uid: int) -> bool:
    return uid in _admin_ids()

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown", threaded=False)

MINIAPP_URL = f"{WEBHOOK_URL}/static/index.html" if WEBHOOK_URL else ""


def make_main_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    if MINIAPP_URL:
        kb.add(
            types.InlineKeyboardButton(
                "🚀 Открыть CHM Smart Money Academy",
                web_app=types.WebAppInfo(url=MINIAPP_URL),
            )
        )
    else:
        kb.add(types.InlineKeyboardButton("ℹ️ Бот не настроен", callback_data="noop"))
    return kb


@bot.message_handler(commands=["start"])
def cmd_start(message: types.Message):
    user = message.from_user
    bot.reply_to(
        message,
        f"👋 Привет, *{user.first_name}*!\n\n"
        "Добро пожаловать в *CHM Smart Money Academy* 🏆\n\n"
        "Здесь ты научишься торговать как Smart Money — крупные институциональные игроки.\n\n"
        "*Что тебя ждёт:*\n"
        "📚 10 модулей с реальными графиками BTC/ETH\n"
        "⚔️ Квесты, квизы и задания на разметку\n"
        "⏰ Дедлайны как на реальном рынке — 72 часа на модуль\n"
        "🏅 7 уровней трейдера: от Наблюдателя до Архитектора рынка\n"
        "🏆 CHM Smart Money Certificate после прохождения\n\n"
        "_Биткоин не ждал тебя в 2017. Не будет ждать и сейчас._\n\n"
        "Нажми кнопку ниже и начни — Модуль 1 бесплатно:",
        reply_markup=make_main_keyboard(),
    )


@bot.message_handler(commands=["app"])
def cmd_app(message: types.Message):
    bot.reply_to(
        message,
        "📱 *CHM Smart Money Academy*\nОткрой и продолжай обучение:",
        reply_markup=make_main_keyboard(),
    )


@bot.message_handler(commands=["top"])
def cmd_top(message: types.Message):
    from progress import get_leaderboard
    try:
        board = get_leaderboard(10)
        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 *Лидерборд CHM Academy:*\n"]
        for i, p in enumerate(board, start=1):
            medal = medals[i - 1] if i <= 3 else f"{i})"
            streak_txt = f" 🔥{p['streak']}" if p.get("streak", 0) >= 3 else ""
            lines.append(
                f"{medal} *{p['name']}* — {p['rank']}\n"
                f"   Lvl {p['level']} | {p['xp']} XP | Модуль {p['module']}{streak_txt}"
            )
        bot.reply_to(message, "\n\n".join(lines[:4]) + "\n\n" + "\n".join(lines[4:]))
    except Exception as e:
        logger.error(f"top error: {e}")
        bot.reply_to(message, "Ошибка получения лидерборда.")


@bot.message_handler(commands=["stats"])
def cmd_stats(message: types.Message):
    from progress import get_user_state, is_deadline_expired, get_deadline_hours_remaining
    from lessons import MODULES
    uid = message.from_user.id
    try:
        st = get_user_state(uid)
        idx = st.get("module_index", 0)
        mod_title = MODULES[idx]["title"] if idx < len(MODULES) else "Завершено"
        hours_left = get_deadline_hours_remaining(st)
        expired = is_deadline_expired(st)
        streak = st.get("streak", 0)
        badges = st.get("badges", [])

        if expired:
            dl_text = "⚠️ ПРОСРОЧЕН — оплати штраф!"
        elif hours_left == float("inf"):
            dl_text = "Нет (свободный модуль)"
        elif hours_left <= 1:
            mins = int(hours_left * 60)
            dl_text = f"🔴 КРИТИЧНО: {mins} минут!"
        elif hours_left <= 6:
            dl_text = f"🟠 {hours_left:.1f} часов — торопись!"
        elif hours_left <= 24:
            dl_text = f"🟡 {hours_left:.1f} часов"
        else:
            dl_text = f"🟢 {hours_left:.0f} часов"

        streak_line = f"🔥 Стрик: {streak} дн." if streak > 0 else "Стрик: 0 дней"
        badges_line = f"🏅 Бейджей: {len(badges)}" if badges else "Бейджей: пока нет"

        bot.reply_to(
            message,
            f"📊 *Твоя статистика — CHM Academy:*\n\n"
            f"👤 {st.get('name', str(uid))}\n"
            f"⭐ Уровень: *{st['level']}* — _{st['rank']}_\n"
            f"💎 XP: *{st['xp']}*\n"
            f"📦 Модуль: *{idx + 1}* — {mod_title}\n"
            f"✅ Квестов: {len(st.get('completed_quests', []))}\n"
            f"⏰ Дедлайн: {dl_text}\n"
            f"{streak_line}\n"
            f"{badges_line}",
        )
    except Exception as e:
        logger.error(f"stats error: {e}")
        bot.reply_to(message, "Ошибка получения статистики.")


@bot.message_handler(commands=["deadline"])
def cmd_deadline(message: types.Message):
    """Show deadline info with rhetoric."""
    from progress import get_user_state, is_deadline_expired, get_deadline_hours_remaining
    uid = message.from_user.id
    try:
        st = get_user_state(uid)
        hours_left = get_deadline_hours_remaining(st)
        expired = is_deadline_expired(st)

        if expired:
            bot.reply_to(
                message,
                f"🔴 *Дедлайн истёк.*\n\n"
                f"Именно так рынок закрывает позиции у тех, кто медлит.\n\n"
                f"Открой приложение → оплати штраф → продолжи путь.",
                reply_markup=make_main_keyboard(),
            )
        elif hours_left == float("inf"):
            bot.reply_to(message, "✅ Модуль 1 бесплатный — дедлайн не установлен.")
        elif hours_left <= 1:
            mins = int(hours_left * 60)
            bot.reply_to(
                message,
                f"🚨 *ПОСЛЕДНИЙ ЧАС — {mins} МИНУТ!*\n\n"
                "Каждая минута промедления — потерянный сетап.\n"
                "Профессионалы работают по расписанию. Сдавай СЕЙЧАС.",
                reply_markup=make_main_keyboard(),
            )
        elif hours_left <= 6:
            bot.reply_to(
                message,
                f"⚠️ *До дедлайна {hours_left:.1f} часов.*\n\n"
                "Рынок не ждал никого — и мы тоже.\n"
                "Сдай домашку сейчас или готовься платить штраф. Это твой выбор.",
                reply_markup=make_main_keyboard(),
            )
        else:
            bot.reply_to(
                message,
                f"⏰ До дедлайна: *{hours_left:.0f} часов*\n\n"
                "Каждый час промедления — это потерянный сетап на реальном рынке.",
            )
    except Exception as e:
        logger.error(f"deadline error: {e}")
        bot.reply_to(message, "Ошибка.")


@bot.message_handler(commands=["extend"])
def cmd_extend(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    from progress import get_user_state, save_progress
    from datetime import datetime, timedelta
    args = message.text.split()[1:]
    if len(args) < 2:
        bot.reply_to(message, "Использование: /extend user_id дни"); return
    try:
        uid, days = int(args[0]), int(args[1])
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат"); return
    state = get_user_state(uid)
    now = datetime.utcnow()
    dl = state.get("module_deadline")
    base = datetime.fromisoformat(dl) if dl else now
    new_dl = base + timedelta(days=days)
    state["module_deadline"] = new_dl.isoformat()
    save_progress()
    new_date = new_dl.date().isoformat()
    bot.reply_to(message, f"✅ Дедлайн продлён до {new_date}")
    try:
        bot.send_message(
            uid,
            f"📅 *Дедлайн продлён на {days} дн.*\n"
            f"Новый дедлайн: {new_date}\n\n"
            "Используй это время с умом. Рынок не будет ждать вечно."
        )
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя %d о продлении: %s", uid, e)


@bot.message_handler(commands=["approve"])
def cmd_approve(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    from progress import get_user_state, save_progress, add_xp, set_module_deadline, DEFAULT_DEADLINE_HOURS
    from quests import QUESTS
    from lessons import MODULES
    args = message.text.split()[1:]
    if len(args) < 2:
        bot.reply_to(message, "Использование: /approve user_id quest_id"); return
    uid, quest_id = int(args[0]), args[1]
    state = get_user_state(uid)
    quest = next((q for q in QUESTS if q["id"] == quest_id), None)
    if not quest:
        bot.reply_to(message, "❌ Квест не найден"); return
    if quest_id not in state["completed_quests"]:
        state["completed_quests"].append(quest_id)
    state["active_quest"] = None
    state["homework_status"] = "approved"
    level, leveled_up = add_xp(uid, quest["xp_reward"])
    advanced = False
    if quest_id.endswith("_boss"):
        idx = state["module_index"]
        module_quests = [q["id"] for q in QUESTS if q["module_index"] == idx]
        if all(qid in state["completed_quests"] for qid in module_quests):
            if idx < len(MODULES) - 1:
                state["module_index"] += 1
                set_module_deadline(state, hours=DEFAULT_DEADLINE_HOURS)
                advanced = True
    save_progress()
    bot.reply_to(message, f"✅ Квест {quest_id} засчитан пользователю {uid}.")

    notify = f"✅ <b>Домашнее задание принято!</b>\n+{quest['xp_reward']} XP"
    if advanced:
        new_idx = state["module_index"]
        new_mod = MODULES[new_idx]["title"] if new_idx < len(MODULES) else "Завершено"
        notify += (
            f"\n\n🎉 <b>Модуль {new_idx} разблокирован: {_html.escape(new_mod)}</b>\n"
            f"⏰ Дедлайн: 72 часа\n\n"
            "<i>Биткоин не ждал тебя в 2017. Не будет ждать и сейчас. Начинай.</i>"
        )
    if leveled_up:
        notify += f"\n⬆️ <b>Новый уровень: {level}!</b>\n<i>{_html.escape(str(state['rank']))}</i>"
    try:
        bot.send_message(uid, notify, parse_mode="HTML")
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя %d об одобрении: %s", uid, e)


@bot.message_handler(commands=["reject"])
def cmd_reject(message: types.Message):
    """Reject or request revision for a homework submission.

    Handles both /reject (serious errors) and /revision (needs corrections).
    Usage: /reject user_id quest_id [комментарий]
    """
    if not is_admin(message.from_user.id):
        return
    from progress import get_user_state, save_progress
    cmd = message.text.split()[0].lstrip("/")   # "reject" or "revision"
    args = message.text.split(None, 3)[1:]
    if len(args) < 2:
        bot.reply_to(message, f"Использование: /{cmd} user_id quest_id [комментарий]"); return
    uid, quest_id = int(args[0]), args[1]
    comment = args[2] if len(args) > 2 else "Нужно доработать."
    status = "revision" if cmd == "revision" else "rejected"
    state = get_user_state(uid)
    state["homework_status"] = status
    save_progress()
    bot.reply_to(message, f"{'🔄 На доработке' if status == 'revision' else '⛔ Отклонено'}.")
    if status == "revision":
        msg = (
            f"🔄 <b>Нужна доработка домашки</b>\n\n"
            f"Фидбек:\n<i>{_html.escape(comment)}</i>\n\n"
            "Исправь разметку и отправь скрин снова. Модуль откроется после принятия."
        )
    else:
        msg = (
            f"⛔ <b>Домашка не принята</b>\n\n"
            f"Причина:\n<i>{_html.escape(comment)}</i>\n\n"
            "Серьёзные ошибки в структуре. Пересмотри уроки и сделай разметку заново."
        )
    try:
        bot.send_message(uid, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning("Не удалось уведомить пользователя %d об отклонении: %s", uid, e)


@bot.message_handler(commands=["revision"])
def cmd_revision(message: types.Message):
    """Alias: /revision → calls cmd_reject with revision status."""
    cmd_reject(message)


def make_hw_keyboard(user_id: int, quest_id: str) -> types.InlineKeyboardMarkup:
    """Inline buttons under homework notification."""
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("✅ Принять",   callback_data=f"hw_ap:{user_id}:{quest_id}"),
        types.InlineKeyboardButton("🔄 Доработка", callback_data=f"hw_rv:{user_id}:{quest_id}"),
        types.InlineKeyboardButton("⛔ Отклонить", callback_data=f"hw_rj:{user_id}:{quest_id}"),
    )
    return kb


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("hw_"))
def handle_hw_callback(call: types.CallbackQuery):
    logger.info(f"HW callback received: {call.data!r} from uid={call.from_user.id}")
    try:
        _do_hw_callback(call)
    except Exception as exc:
        logger.error(f"HW callback unhandled error: {exc}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка сервера", show_alert=True)
        except Exception:
            pass


def _do_hw_callback(call: types.CallbackQuery):
    from progress import get_user_state, save_progress, add_xp, set_module_deadline, DEFAULT_DEADLINE_HOURS
    from quests import QUESTS
    from lessons import MODULES

    if not call.message:
        bot.answer_callback_query(call.id, "❌ Нет данных сообщения", show_alert=True)
        return

    parts = call.data.split(":", 2)
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "❌ Неверный формат", show_alert=True)
        return

    action, uid_str, quest_id = parts
    uid = int(uid_str)
    state = get_user_state(uid)
    quest = next((q for q in QUESTS if q["id"] == quest_id), None)

    admin_name = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name

    if action == "hw_ap":
        if not quest:
            bot.answer_callback_query(call.id, "❌ Квест не найден", show_alert=True); return

        # ── 1. Answer immediately so Telegram doesn't show spinner ──
        bot.answer_callback_query(call.id, "✅ Принято!")

        # ── 2. Update progress ──
        if quest_id not in state["completed_quests"]:
            state["completed_quests"].append(quest_id)
        state["active_quest"]    = None
        state["homework_status"] = "approved"
        level, leveled_up = add_xp(uid, quest["xp_reward"])
        advanced = False
        idx = state["module_index"]
        if quest_id.endswith("_boss"):
            module_quests = [q["id"] for q in QUESTS if q["module_index"] == idx]
            if all(qid in state["completed_quests"] for qid in module_quests):
                if idx < len(MODULES) - 1:
                    state["module_index"] += 1
                    set_module_deadline(state, hours=DEFAULT_DEADLINE_HOURS)
                    advanced = True
        save_progress()

        # ── 3. Remove buttons + mark message ──
        done_text = f"✅ <b>Принято</b> — {_html.escape(admin_name)}"
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e:
            logger.warning(f"edit_markup approve: {e}")
        try:
            bot.send_message(call.message.chat.id, done_text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"send done_text approve: {e}")

        # ── 4. Notify student ──
        notify = f"✅ <b>Домашнее задание принято!</b>\n+{quest['xp_reward']} XP"
        if advanced:
            new_idx = state["module_index"]
            new_mod = MODULES[new_idx]["title"] if new_idx < len(MODULES) else "Завершено"
            notify += (
                f"\n\n🎉 <b>Модуль {new_idx} разблокирован: {_html.escape(new_mod)}</b>\n"
                f"⏰ Дедлайн: 72 часа\n\n"
                "<i>Биткоин не ждал тебя в 2017. Не будет ждать и сейчас. Начинай.</i>"
            )
        if leveled_up:
            notify += f"\n⬆️ <b>Новый уровень: {level}!</b>\n<i>{_html.escape(str(state['rank']))}</i>"
        try:
            bot.send_message(uid, notify, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"notify student approve: {e}")

    elif action in ("hw_rv", "hw_rj"):
        status          = "revision" if action == "hw_rv" else "rejected"
        label           = "🔄 На доработку" if status == "revision" else "⛔ Отклонено"
        default_comment = "Нужно доработать." if status == "revision" else "Не принято."

        # ── 1. Answer immediately ──
        bot.answer_callback_query(call.id, label)

        # ── 2. Update progress ──
        state["homework_status"]  = status
        state["homework_comment"] = default_comment
        save_progress()

        # ── 3. Remove buttons + hint in group ──
        hint = (
            f"{label} — {_html.escape(admin_name)}\n\n"
            f"<i>Для кастомного комментария:\n"
            f"/{('revision' if status == 'revision' else 'reject')} "
            f"{uid} {quest_id} ваш комментарий</i>"
        )
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception as e:
            logger.warning(f"edit_markup {status}: {e}")
        try:
            bot.send_message(call.message.chat.id, hint, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"send hint {status}: {e}")

        # ── 4. Notify student ──
        if status == "revision":
            msg = (
                f"🔄 <b>Нужна доработка домашки</b>\n\n"
                f"Фидбек:\n<i>{_html.escape(default_comment)}</i>\n\n"
                "Исправь разметку и отправь скрин снова."
            )
        else:
            msg = (
                f"⛔ <b>Домашка не принята</b>\n\n"
                f"Причина:\n<i>{_html.escape(default_comment)}</i>\n\n"
                "Пересмотри уроки и сделай разметку заново."
            )
        try:
            bot.send_message(uid, msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"notify student {status}: {e}")


def setup_webhook():
    # Re-read and strip env vars in case they were set after module load
    token = os.getenv("BOT_TOKEN", "").strip()
    webhook_url = os.getenv("WEBHOOK_URL", "").strip().rstrip("/")
    if not token or not webhook_url:
        logger.warning("BOT_TOKEN или WEBHOOK_URL не установлены, вебхук не настроен")
        return
    target = f"{webhook_url}/webhook"
    logger.info("Устанавливаем вебхук: %r (len=%d)", target, len(target))
    for attempt in range(3):
        try:
            bot.set_webhook(
                url=target,
                allowed_updates=["message", "callback_query", "channel_post", "edited_channel_post"],
                drop_pending_updates=False,
            )
            logger.info("✅ Вебхук установлен успешно: %s", target)
            return
        except Exception as e:
            logger.error("Ошибка установки вебхука (попытка %d/3): %s", attempt + 1, e)
            if attempt < 2:
                import time; time.sleep(2 ** attempt)
    logger.critical("Не удалось установить вебхук после 3 попыток!")


def process_update(update_dict: dict):
    try:
        update = telebot.types.Update.de_json(update_dict)
        bot.process_new_updates([update])
    except Exception as e:
        logger.error(f"Ошибка обработки апдейта: {e}")


def notify_deadline_warning(user_id: int, hours_left: float):
    """Send deadline warning notification to user."""
    try:
        if hours_left <= 1:
            mins = int(hours_left * 60)
            bot.send_message(
                user_id,
                f"🚨 *ПОСЛЕДНИЙ ЧАС — {mins} МИНУТ!*\n\n"
                "Красный экран. Таймер идёт.\n"
                "Сдавай домашку ПРЯМО СЕЙЧАС пока не заблокировали.",
                reply_markup=make_main_keyboard(),
            )
        elif hours_left <= 6:
            bot.send_message(
                user_id,
                f"⚠️ *До дедлайна {hours_left:.0f} часов. Последний шанс.*\n\n"
                "Рынок не ждал никого — и мы тоже.\n"
                "Сдай домашку сейчас или готовься платить штраф. Это твой выбор.",
                reply_markup=make_main_keyboard(),
            )
        elif hours_left <= 24:
            bot.send_message(
                user_id,
                f"⏰ *Напоминание: до дедлайна {hours_left:.0f} часов.*\n\n"
                "Каждый час промедления — это потерянный сетап на реальном рынке.\n"
                "Профессионалы работают по расписанию. Любители — когда удобно.",
                reply_markup=make_main_keyboard(),
            )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления {user_id}: {e}")


def notify_inactivity(user_id: int, user_name: str):
    """Notify user after 48+ hours of inactivity."""
    try:
        bot.send_message(
            user_id,
            f"Эй, *{user_name}*. Пока ты отдыхал — биткоин сделал несколько сетапов "
            f"по системе, которую ты ещё не изучил.\n\n"
            f"Вернись. Дедлайн тикает. Рынок не будет ждать.",
            reply_markup=make_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления о неактивности {user_id}: {e}")


# ══════════════════════════════════════════════════════════════════════
# ── TELEGRAM STARS SHOP ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════

# Защита = от потери (психологически сильнее чем "получить бонус")
SHOP_ITEMS = [
    {
        "id": "shield_24h",
        "name": "🛡 Щит от Катализатора",
        "desc": "24ч полная защита от дренажа. Катализатор тебя не видит.",
        "stars": 15,
        "effect": "catalyst_shield",
        "hours": 24,
    },
    {
        "id": "revival",
        "name": "🧬 Воскрешение Гомункула",
        "desc": "Оживить мёртвого Гомункула. Стадия −1, но живой.",
        "stars": 25,
        "effect": "revive_homunculus",
    },
    {
        "id": "estus_x3",
        "name": "⚗️ Estus-фласки ×3",
        "desc": "3 подсказки для боссов. Рынок не ждёт пока ты думаешь.",
        "stars": 10,
        "effect": "estus_refill",
        "count": 3,
    },
    {
        "id": "double_tap_3h",
        "name": "⚡ Двойная реакция 3ч",
        "desc": "Множитель тапов ×2 на 3 часа. Фарм в максимуме.",
        "stars": 20,
        "effect": "double_tap",
        "hours": 3,
    },
    {
        "id": "souls_300",
        "name": "💀 300 Душ",
        "desc": "Экстренное пополнение резерва.",
        "stars": 50,
        "effect": "souls_bonus",
        "amount": 300,
    },
]


@bot.message_handler(commands=["shop", "buy"])
def cmd_shop(message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for item in SHOP_ITEMS:
        kb.add(types.InlineKeyboardButton(
            f"{item['name']} — {item['stars']} ⭐",
            callback_data=f"buy_{item['id']}"
        ))
    bot.send_message(
        message.chat.id,
        "⚗️ <b>Лаборатория Алхимика</b>\n\n"
        "Всё, что нужно чтобы выжить в академии.\n"
        "Оплата через Telegram Stars (⭐):",
        parse_mode="HTML", reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("buy_"))
def cb_buy(call):
    item_id = call.data[4:]
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        return
    bot.answer_callback_query(call.id)
    bot.send_invoice(
        call.message.chat.id,
        title=item["name"],
        description=item["desc"],
        payload=f"{item_id}:{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(item["name"], item["stars"])],
    )


@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)


@bot.message_handler(content_types=["successful_payment"])
def payment_done(message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) != 2:
        return
    item_id, uid_str = parts
    user_id = int(uid_str)
    item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
    if not item:
        return
    try:
        from progress import user_progress, save_progress
        st = user_progress.setdefault(user_id, {})
        effect = item["effect"]
        msg = ""
        from datetime import datetime, timedelta

        if effect == "catalyst_shield":
            exp = (datetime.utcnow() + timedelta(hours=item["hours"])).isoformat()
            st["catalyst_shield_until"] = exp
            msg = f"🛡 Щит активен на {item['hours']}ч. Катализатор тебя не видит."

        elif effect == "revive_homunculus":
            hom = st.get("homunculus", {})
            if hom.get("status") == "dead":
                hom["status"] = "active"
                hom["stage"] = max(1, hom.get("stage", 1) - 1)
                hom["health"] = 60
                st["homunculus"] = hom
                msg = "🧬 Гомункул воскрешён! Стадия −1, но живой."
            else:
                msg = "🧬 Гомункул жив — фласка на будущее добавлена."
                st["revival_stored"] = st.get("revival_stored", 0) + 1

        elif effect == "estus_refill":
            st["estus_flasks"] = st.get("estus_flasks", 0) + item["count"]
            msg = f"⚗️ +{item['count']} Estus-фласки. Используй с умом."

        elif effect == "double_tap":
            exp = (datetime.utcnow() + timedelta(hours=item["hours"])).isoformat()
            st["double_tap_until"] = exp
            msg = f"⚡ Множитель ×2 активен на {item['hours']}ч!"

        elif effect == "souls_bonus":
            st["souls"] = round(st.get("souls", 0) + item["amount"], 2)
            msg = f"💀 +{item['amount']} Душ зачислено. Баланс: {st['souls']:.0f}"

        save_progress()
        bot.send_message(user_id,
            f"✅ <b>Покупка подтверждена!</b>\n\n{msg}\n\n"
            f"<i>Рынок не прощает. Ты — да.</i>",
            parse_mode="HTML")
    except Exception as e:
        logger.error("payment_done: %r", e)
