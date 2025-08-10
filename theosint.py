import logging
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# --- Config ---
BOT_TOKEN = '8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw'
OWNER_ID = 7835198116
API_URL = 'https://appi.ytcampss.store/Osint/ration.php?id='

# --- Data Stores ---
user_credits = {}
referred_users = set()

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Keyboards ---
main_keyboard = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔍 Ration Search", callback_data="search"),
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

# --- Format Function ---
def format_ration_response(data):
    """Format ration card API response in a beautiful style"""
    if not data:
        return None

    try:
        info = requests.utils.json.loads(data)
    except:
        return None

    if not isinstance(info, dict) or not info:
        return None

    formatted = "🎯 <b>RATION CARD DETAILS</b>\n"
    formatted += "╔════════════════════════╗\n"

    if "name" in info:
        formatted += f"┃ 👤 <b>Name:</b> <code>{info['name']}</code>\n"
    if "ration_number" in info:
        formatted += f"┃ 🆔 <b>Ration No:</b> <code>{info['ration_number']}</code>\n"
    if "father_name" in info:
        formatted += f"┃ 👨‍👦 <b>Father:</b> <code>{info['father_name']}</code>\n"
    if "address" in info:
        formatted += f"┃ 🏠 <b>Address:</b> <code>{info['address']}</code>\n"
    if "category" in info:
        formatted += f"┃ 🏷️ <b>Category:</b> <code>{info['category']}</code>\n"

    # Members list
    if "members" in info and isinstance(info["members"], list) and info["members"]:
        formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
        formatted += "┃ 👥 <b>Family Members</b>\n"
        formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
        for i, member in enumerate(info["members"], 1):
            formatted += f"┃ #{i}\n"
            if "name" in member:
                formatted += f"┃ 👤 Name: <code>{member['name']}</code>\n"
            if "relation" in member:
                formatted += f"┃ 🔗 Relation: <code>{member['relation']}</code>\n"
            if "age" in member:
                formatted += f"┃ 🎂 Age: <code>{member['age']}</code>\n"
            formatted += "┃ ─────────────────────\n"

    formatted += "╚════════════════════════╝"
    return formatted

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args

    if uid not in user_credits:
        user_credits[uid] = 5  # 1 free search = 5 coins

    # Referral system
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
        "🛡️ <b>Security Notice:</b> Due to privacy concerns, only Ration Card search is available now.\n\n"
        "Send your ration card number to search.",
        parse_mode='HTML',
        reply_markup=main_keyboard
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "search":
        await query.message.reply_text(
            "📨 Send your <b>Ration Card Number</b> to search.\n\n"
            "💸 Each search costs 5 coins.",
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

    try:
        r = requests.get(API_URL + query, timeout=15)

        if r.status_code != 200 or not r.text.strip():
            await searching_msg.edit_text(
                "❌ <b>NO DATA FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 Server returned empty     ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return

        formatted_result = format_ration_response(r.text)
        if formatted_result:
            user_credits[uid] -= 5
            result_message = f"{formatted_result}\n\n"
            result_message += f"🎯 <b>Query:</b> <code>{query}</code>\n"
            result_message += f"💰 <b>Coins Left:</b> {user_credits[uid]}"
            await searching_msg.edit_text(result_message, parse_mode='HTML')
        else:
            await searching_msg.edit_text(
                "❌ <b>INVALID DATA FORMAT</b>\n"
                "╔══════════════════════╗\n"
                "┃ 📄 Could not parse response ┃\n"
                "┃ 💳 Credits not deducted     ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )

    except requests.exceptions.Timeout:
        await searching_msg.edit_text(
            "⏰ <b>SEARCH TIMEOUT</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🕐 Request took too long    ┃\n"
            "┃ 💳 Credits not deducted     ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
    except requests.exceptions.ConnectionError:
        await searching_msg.edit_text(
            "❌ <b>CONNECTION ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🌐 Can't reach API server   ┃\n"
            "┃ 💳 Credits not deducted     ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
        
