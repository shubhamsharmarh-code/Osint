import logging
import re
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# --- Config ---
BOT_TOKEN = '8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw'
OWNER_ID = 7835198116

# --- Data Stores ---
user_credits = {}
referred_users = set()

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Normalize Query ---
def clean_input(text):
    text = text.strip().replace(" ", "").replace("-", "")
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
        user_credits[uid] = 5  # 1 free search = 5 coins

    if args and args[0].startswith("ref_"):
        ref_id = int(args[0][4:])
        if ref_id != uid and ref_id in user_credits and uid not in referred_users:
            user_credits[ref_id] += 5
            referred_users.add(uid)
            try:
                await context.bot.send_message(
                    ref_id,
                    f"✨ You got 5 coins from referral! New balance: {user_credits[ref_id]}"
                )
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
            "🔍 Examples:\n"
            "• example@mail.com      (Email)\n"
            "• t.me/xyz              (Telegram)\n"
            "• example.com           (Domain)\n"
            "• facebook.com/xyz      (Facebook)\n"
            "• instagram.com/xyz     (Instagram)\n\n"
            "🧠 Better input = better results\n"
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

def is_valid_data(data):
    if not data or not isinstance(data, str):
        return False
    data = data.strip()
    if not data or data in ['[]', '{}', 'null', 'None']:
        return False

    data_lower = data.lower()
    error_patterns = [
        "rate limit exceeded", "try again after", "status: error", "error:",
        "failed", "server error", "internal error", "service unavailable",
        "timeout", "too many requests", "limit reached", "quota exceeded"
    ]
    if any(p in data_lower for p in error_patterns):
        return False

    no_records_patterns = [
        "no records found", "no record found", "not found", "no data available",
        "no results", "data not found", "no information", "empty result", "nothing found"
    ]
    if any(p in data_lower for p in no_records_patterns):
        return False

    return True

def format_combined_response(primary_data):
    if not is_valid_data(primary_data):
        return None
    formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
    formatted += "╔════════════════════════╗\n"
    try:
        import json
        parsed_data = json.loads(primary_data)

        if isinstance(parsed_data, list) and len(parsed_data) > 0:
            for i, item in enumerate(parsed_data, 1):
                formatted += f"┃ <b>📋 Record #{i}</b>\n"
                formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
                if isinstance(item, dict):
                    for key, value in item.items():
                        if value and str(value).strip():
                            formatted += f"┃ 📌 <b>{key.replace('_', ' ').title()}:</b> <code>{value}</code>\n"

        elif isinstance(parsed_data, dict) and parsed_data:
            formatted += f"┃ <b>📋 Primary Data</b>\n"
            formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            for key, value in parsed_data.items():
                if value and str(value).strip():
                    formatted += f"┃ 📌 <b>{key.replace('_', ' ').title()}:</b> <code>{value}</code>\n"

    except:
        lines = primary_data.strip().split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    formatted += f"┃ 📌 <b>{parts[0].strip()}:</b> <code>{parts[1].strip()}</code>\n"
            else:
                formatted += f"┃ • {line.strip()}\n"

    formatted += "╚════════════════════════╝"
    return formatted

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    query = update.message.text.strip()

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

    searching_msg = await update.message.reply_text("🔍 Searching...")

    query = clean_input(query)
    should_deduct_credits = False
    response_text = ""

    try:
        payload = {
            "token": "8217808614:04wbEZ3i",
            "request": query,
            "limit": 100,
            "lang": "ru"
        }
        url = "https://leakosintapi.com/"
        r = requests.post(url, json=payload, timeout=15)

        if r.status_code != 200:
            await searching_msg.edit_text(
                "❌ <b>SERVER ERROR</b>\n"
                "╔══════════════════════╗\n"
                "┃ ⚠️ API server not responding ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return

        response_text = r.text.strip()
        if not is_valid_data(response_text):
            await searching_msg.edit_text(
                "❌ <b>NO RECORDS FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 No data available         ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return

        formatted_result = format_combined_response(response_text)
        if formatted_result:
            should_deduct_credits = True
            user_credits[uid] -= 5
            result_message = f"{formatted_result}\n\n"
            result_message += f"🎯 <b>Query:</b> <code>{query}</code>\n"
            result_message += f"💰 <b>Coins Left:</b> {user_credits[uid]}"
            await searching_msg.edit_text(result_message, parse_mode='HTML')
        else:
            await searching_msg.edit_text(
                "❌ <b>NO USEFUL DATA FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 Data format not supported ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )

    except requests.exceptions.Timeout:
        await searching_msg.edit_text("⏰ <b>SEARCH TIMEOUT</b>", parse_mode='HTML')
    except requests.exceptions.ConnectionError:
        await searching_msg.edit_text("❌ <b>CONNECTION ERROR</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        if should_deduct_credits:
            user_credits[uid] += 5
        await searching_msg.edit_text("⚠️ <b>SYSTEM ERROR</b>", parse_mode='HTML')

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
