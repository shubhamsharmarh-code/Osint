import logging
import re
import json
import asyncio
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# ---------------- CONFIG ----------------
BOT_TOKEN = "8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw"  # <-- replace with your bot token
OWNER_ID = 7835198116
RATION_URL = 'https://appi.ytcampss.store/Osint/ration.php?id='

# ---------------- DATA STORES ----------------
user_credits = {}       # in-memory credit store (uid -> coins)
referred_users = set()  # track which users were already credited via referral

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- HELPERS ----------------
def is_ration_card_number(text: str) -> bool:
    """Validate 12-digit ration card number (digits only)."""
    if not text:
        return False
    t = re.sub(r"\s+", "", text)
    return t.isdigit() and len(t) == 12

async def http_get(url: str, timeout: int = 15):
    """Perform blocking requests.get inside a thread to avoid blocking event loop."""
    return await asyncio.to_thread(lambda: requests.get(url, timeout=timeout))

def format_old_style_box(title: str, lines: list) -> str:
    """Return a string that mimics the old box-style output used earlier."""
    out = f"🎯 <b>{title}</b>\n"
    out += "╔════════════════════════╗\n"
    for line in lines:
        out += f"┃ {line}\n"
    out += "╚════════════════════════╝"
    return out

def format_ration_response(raw_text: str) -> str:
    """Try to parse JSON; fall back to plain text. Format in old box style."""
    lines = []
    try:
        data = json.loads(raw_text)

        # If API returns list, take first element
        if isinstance(data, list) and len(data) > 0:
            data = data[0]

        if isinstance(data, dict):
            # Prefer common ration card fields if present
            field_map = [
                ("ration_no", "🆔 Ration No"),
                ("name", "👤 Name"),
                ("holder_name", "👤 Holder"),
                ("address", "🏠 Address"),
                ("village", "🏘️ Village"),
                ("district", "📍 District"),
                ("state", "🏷️ State"),
                ("family_count", "👥 Family Members"),
                ("members", "👪 Members"),
                ("card_type", "💳 Card Type"),
            ]

            # Print mapped fields if present
            for key, label in field_map:
                if key in data and data[key] not in (None, "", []):
                    val = data[key]
                    # If members is a list, show count and first few names
                    if key == 'members' and isinstance(val, list):
                        members_preview = ', '.join(str(m) for m in val[:5])
                        lines.append(f"{label}: {members_preview} ({len(val)} total)")
                    else:
                        lines.append(f"{label}: {val}")

            # If nothing matched above, dump all keys
            if not lines:
                for k, v in data.items():
                    if v not in (None, "", []):
                        lines.append(f"📌 {k.replace('_', ' ').title()}: {v}")
        else:
            # Non-dict JSON (e.g., a string)
            lines.append(raw_text)

    except json.JSONDecodeError:
        # Plain text response — show raw but trimmed
        raw = raw_text.strip()
        if len(raw.splitlines()) > 8:
            # show first 8 lines then indicate truncated
            preview = '\n'.join(raw.splitlines()[:8])
            lines.append(preview)
            lines.append("... (truncated)")
        else:
            lines.append(raw)

    return format_old_style_box("RATION CARD SEARCH RESULT", lines)

# ---------------- KEYBOARDS ----------------
main_keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔍 Search", callback_data="search"),
        InlineKeyboardButton("💰 Balance", callback_data="balance")
    ],
    [
        InlineKeyboardButton("💸 Add Funds", callback_data="add_funds"),
        InlineKeyboardButton("💎 Referral", callback_data="referral")
    ],
    [
        InlineKeyboardButton("🔐 Contact Admin", url="https://t.me/Cyreo")
    ]
])

# ---------------- HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args

    if uid not in user_credits:
        user_credits[uid] = 5  # give new users 5 coins (1 free search = 5 coins)

    # handle referral start
    if args and args[0].startswith("ref_"):
        try:
            ref_id = int(args[0][4:])
            if ref_id != uid and ref_id in user_credits and uid not in referred_users:
                user_credits[ref_id] += 5
                referred_users.add(uid)
                try:
                    await context.bot.send_message(ref_id, f"✨ You got 5 coins from referral! New balance: {user_credits[ref_id]}")
                except Exception:
                    pass
        except Exception:
            pass

    await update.message.reply_text(
        "🕵️ I can help with Ration Card searches. Send a 12-digit ration card number to begin.",
        reply_markup=main_keyboard
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "search":
        await query.message.reply_text(
            "📨 Send a 12-digit Ration Card number (e.g., 275440386092) to search.\n\n"
            "🚫 All other OSINT searches have been disabled.\n"
            "✅ Currently only Ration Card search is available due to government security rules.\n\n"
            "💸 Each search costs 5 coins."
        )

    elif query.data == "balance":
        coins = user_credits.get(uid, 0)
        await query.message.reply_text(f"💰 Your balance: {coins} coins")

    elif query.data == "add_funds":
        await query.message.reply_text(
            "💸 <b>Pricing List</b>\n"
            "━━━━━━━━━━━━━━\n"
            "🔍 1 Search = 5 Coins\n\n"
            "💳 Coin Packages:\n"
            "• 100 Coins — ₹100 (20 searches)\n"
            "• 250 Coins — ₹250 (50 searches)\n"
            "• 500 Coins — ₹500 (100 searches)\n"
            "• 1000 Coins — ₹1000 (200 searches)\n"
            "━━━━━━━━━━━━━━\n"
            "📩 Contact @Cyreo to top-up.",
            parse_mode='HTML'
        )

    elif query.data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
        await query.message.reply_text(
            f"💎 <b>Referral Program</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"🎁 Earn 5 coins per referral!\n"
            f"🔗 Your link:\n<code>{ref_link}</code>",
            parse_mode='HTML'
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    query = update.message.text.strip()

    # Ensure user has credits entry
    if uid not in user_credits:
        user_credits[uid] = 5

    coins = user_credits.get(uid, 0)
    if coins < 5:
        await update.message.reply_text(
            "💸 <b>INSUFFICIENT FUNDS!</b>\n"
            "╔══════════════════════╗\n"
            "┃ ❌ <b>Balance:</b> <code>0 coins</code>      ┃\n"
            "┃ 💳 <b>Required:</b> <code>5 coins</code>     ┃\n"
            "┃ 🚀 Click /start → Add Funds ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
        return

    # Validate Ration Card input
    if not is_ration_card_number(query):
        await update.message.reply_text(
            "🚫 All other OSINT searches have been disabled.\n"
            "✅ Currently only Ration Card search is available due to government security rules.\n\n"
            "📌 Send a 12-digit Ration Card number (e.g., 275440386092) to search."
        )
        return

    # Inform user we're searching
    searching_msg = await update.message.reply_text("🔍 Searching Ration Card details...")

    try:
        url = RATION_URL + query
        r = await http_get(url, timeout=18)

        if r.status_code != 200 or not r.text.strip():
            await searching_msg.edit_text(
                "❌ <b>NO DATA FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 Server returned no results     ┃\n"
                "┃ 💳 Credits not deducted           ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return

        response_text = r.text.strip()

        # Use format function to build old style box
        formatted = format_ration_response(response_text)

        # Deduct credits only if we have something to show
        user_credits[uid] -= 5

        result_message = f"{formatted}\n\n"
        result_message += f"🎯 <b>Query:</b> <code>{query}</code>\n"
        result_message += f"💰 <b>Coins Left:</b> {user_credits[uid]}"

        await searching_msg.edit_text(result_message, parse_mode='HTML')

    except requests.exceptions.Timeout:
        await searching_msg.edit_text(
            "⏰ <b>SEARCH TIMEOUT</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🕐 Request took too long     ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error in handle_text: {e}")
        await searching_msg.edit_text(
            "⚠️ <b>SYSTEM ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🔧 Unexpected error occurred ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )

# ---------------- COMMANDS ----------------
async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("To add coins, contact @Cyreo")

# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler('addcoin', addcoin))

    print("Bot starting...")
    app.run_polling()

if __name__ == '__main__':
    main()
            
