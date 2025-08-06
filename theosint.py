import logging
import re
import requests
import pytz
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Config ---
BOT_TOKEN = '8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw'
OWNER_ID = 7835198116
API_URL = 'https://millionmack.com/god.php?term='
AADHAAR_API_URL = 'https://millionmack.com/adhar.php?term='

# --- Data Stores ---
user_credits = {}
referred_users = set()

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Normalize Query ---
def clean_input(text):
    text = text.strip().replace(" ", "").replace("-", "")
    match = re.match(r"^(?:\+91|91)?(\d{10})$", text)
    if match:
        return match.group(1)
    return text

# --- Keyboards ---
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

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args

    if uid not in user_credits:
        user_credits[uid] = 5  # Free coins

    if args and args[0].startswith("ref_"):
        ref_id = int(args[0][4:])
        if ref_id != uid and ref_id in user_credits and uid not in referred_users:
            user_credits[ref_id] += 5
            referred_users.add(uid)
            try:
                await context.bot.send_message(ref_id, f"✨ You got 5 coins from referral! New balance: {user_credits[ref_id]}")
            except:
                pass

    await update.message.reply_text(
        "🕵️ I can look for almost everything. Just send me your request.",
        reply_markup=main_keyboard
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "search":
        await query.message.reply_text(
            "📨 Send phone number, email, username, IP, domain, or social profile to search.\n\n"
            "⚠️ <b>Note:</b> Search feature is currently <b>disabled</b> due to legal reasons.",
            parse_mode='HTML'
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

# 🔒 TEMPORARY DISABLED SEARCH FUNCTION
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    warning_msg = (
        "⚠️ <b>NOTICE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 The search feature is <b>temporarily disabled</b>.\n\n"
        "🚫 Due to recent government action against bots accessing personal data from illegal sources, we've paused this feature to comply with legal and privacy regulations.\n\n"
        "⏳ Please wait while we assess and resolve the situation.\n"
        "Thank you for understanding.\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(warning_msg, parse_mode="HTML")

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
