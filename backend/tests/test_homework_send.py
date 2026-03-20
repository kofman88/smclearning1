"""
test_homework_send.py — тест отправки ДЗ в группу админов.

Запуск:
    cd backend
    python tests/test_homework_send.py

Требования:
    pip install python-dotenv telebot

Что проверяет:
    1. Загрузка .env (BOT_TOKEN, ADMIN_CHANNEL_ID, ADMIN_ID)
    2. Отправка текстового сообщения в группу/канал
    3. Отправка текстового сообщения каждому из ADMIN_ID
    4. Полный ответ Telegram API при ошибке (TeleApiError)
"""
import os
import sys
import logging
from pathlib import Path

# ── Locate .env — try backend/ and project root ───────────────────────────
_here = Path(__file__).resolve()
for _candidate in [_here.parent.parent / ".env", _here.parent.parent.parent / ".env"]:
    if _candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(str(_candidate), override=True)
        print(f"[dotenv] Loaded: {_candidate}")
        break
else:
    print("[dotenv] .env not found — reading OS environment only")

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("hw_test")

BOT_TOKEN        = os.getenv("BOT_TOKEN", "")
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "").strip()
ADMIN_IDS_RAW    = os.getenv("ADMIN_ID", "").strip()

print("\n" + "="*60)
print("=== ENV VARIABLES ===")
print(f"BOT_TOKEN        : {'SET (len=' + str(len(BOT_TOKEN)) + ')' if BOT_TOKEN else '⚠️  NOT SET'}")
print(f"ADMIN_CHANNEL_ID : {ADMIN_CHANNEL_ID!r}")
print(f"ADMIN_ID         : {ADMIN_IDS_RAW!r}")
print("="*60 + "\n")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN is not set. Aborting.")
    sys.exit(1)

# Validate ADMIN_CHANNEL_ID
try:
    channel_int = int(ADMIN_CHANNEL_ID) if ADMIN_CHANNEL_ID else None
except ValueError:
    channel_int = None

if channel_int is not None:
    if channel_int > 0:
        print("⚠️  WARNING: ADMIN_CHANNEL_ID is POSITIVE — groups/channels must use NEGATIVE ids")
        print(f"   Current value: {channel_int}")
        print("   Fix: use the id with a minus sign, e.g. -1001234567890")
    else:
        print(f"✅ ADMIN_CHANNEL_ID looks correct (negative): {channel_int}")
else:
    print("⚠️  ADMIN_CHANNEL_ID is empty — only individual admin DMs will be used")

# Parse admin user IDs
admin_ids = []
for part in ADMIN_IDS_RAW.split(","):
    part = part.strip()
    if part.lstrip("-").isdigit():
        admin_ids.append(int(part))
print(f"Parsed admin user IDs: {admin_ids}\n")

import telebot  # noqa: E402

bot = telebot.TeleBot(BOT_TOKEN)

TEST_TEXT = (
    "🧪 <b>Тест отправки ДЗ</b>\n\n"
    "Если ты видишь это сообщение — отправка работает корректно.\n\n"
    "👤 Студент: <b>Test User</b> (<code>123456789</code>)\n"
    "📝 Задание: <b>test_homework_task</b>\n\n"
    "✅ Принять: <code>/approve 123456789 test_task</code>\n"
    "🔄 Доработка: <code>/revision 123456789 test_task комментарий</code>\n"
    "⛔ Отклонить: <code>/reject 123456789 test_task причина</code>"
)


def send_and_report(label: str, chat_id: int):
    print(f"\n--- Sending to {label} (chat_id={chat_id}) ---")
    try:
        result = bot.send_message(chat_id, TEST_TEXT, parse_mode="HTML")
        print(f"✅ SUCCESS — message_id={result.message_id}, chat={result.chat.id}")
    except telebot.apihelper.ApiTelegramException as e:
        print(f"❌ TELEGRAM API ERROR:")
        print(f"   status_code : {e.error_code}")
        print(f"   description : {e.description}")
        print(f"   result_json : {e.result_json}")
        print(f"\n   Common causes:")
        if e.error_code == 403:
            print("   → Bot is not a member of the group/channel. Add the bot first!")
        elif e.error_code == 400 and "chat not found" in str(e.description).lower():
            print("   → chat_id is wrong or bot has never interacted with this chat.")
        elif e.error_code == 400:
            print("   → Bad request. Check chat_id format (negative for groups).")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")


# ── Run tests ──────────────────────────────────────────────────────────────
results = []

if channel_int is not None:
    send_and_report("admin group/channel", channel_int)
else:
    print("\n[SKIP] ADMIN_CHANNEL_ID not set — skipping channel test")

if admin_ids:
    for aid in admin_ids:
        send_and_report(f"admin DM", aid)
else:
    print("\n[SKIP] No ADMIN_ID values found — skipping DM tests")

print("\n=== Test complete ===")
