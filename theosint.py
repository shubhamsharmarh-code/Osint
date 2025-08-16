import logging
import re
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# --- Config ---
BOT_TOKEN = "8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw"  # replace with your bot token
OWNER_ID = 7835198116
API_URL = "https://meowmeow.rf.gd/uu.php?num="
AADHAAR_API_URL = "http://meowmeow.rf.gd/addhar.php/info?aadhar="

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


# --- Aadhaar Extract ---
def extract_aadhaar_from_response(response_text):
    if not response_text:
        return None
    aadhaar_patterns = [
        r"(\d{12})",
        r"(\d{4}\s*\d{4}\s*\d{4})"
    ]
    for pattern in aadhaar_patterns:
        matches = re.findall(pattern, response_text)
        for match in matches:
            clean_aadhaar = re.sub(r"\s+", "", match)
            if len(clean_aadhaar) == 12 and clean_aadhaar.isdigit():
                return clean_aadhaar
    return None


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
        user_credits[uid] = 5  # free 5 coins

    if args and args[0].startswith("ref_"):
        ref_id = int(args[0][4:])
        if ref_id != uid and ref_id in user_credits and uid not in referred_users:
            user_credits[ref_id] += 5
            referred_users.add(uid)
            try:
                await context.bot.send_message(
                    ref_id, f"✨ You got 5 coins from referral! New balance: {user_credits[ref_id]}"
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
            "📨 Send phone number, email, username, IP, or domain to search.\n\n"
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
            "• 100 Coins — ₹100\n"
            "• 250 Coins — ₹250\n"
            "• 500 Coins — ₹500\n"
            "• 1000 Coins — ₹1000\n"
            "━━━━━━━━━━━━━━\n"
            "📩 Contact @Cyreo to top-up.",
            parse_mode="HTML"
        )
    elif query.data == "referral":
        bot_info = await context.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
        await query.message.reply_text(
            f"💎 <b>Referral Program</b>\n"
            f"🎁 Earn 5 coins per referral!\n"
            f"🔗 Your link:\n<code>{ref_link}</code>",
            parse_mode="HTML"
        )


# --- Helpers ---
def is_valid_data(data):
    if not data or not isinstance(data, str):
        return False
    if data.strip() in ["[]", "{}", "null", "None"]:
        return False
    if "not found" in data.lower() or "no records" in data.lower():
        return False
    return True


async def fetch_aadhaar_details(aadhaar_number):
    try:
        url = AADHAAR_API_URL + aadhaar_number
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and is_valid_data(r.text):
            return r.text.strip()
    except Exception as e:
        logging.error(f"Aadhaar fetch error: {e}")
    return None


# --- Format Response ---
def format_combined_response(primary_data, aadhaar_data=None):
    formatted = "🎯 <b>SEARCH RESULTS</b>\n\n"
    formatted += f"<code>{primary_data}</code>\n"

    if aadhaar_data:
        formatted += "\n\n🔗 <b>Aadhaar Linked Data</b>\n"
        formatted += f"<code>{aadhaar_data}</code>\n"

    return formatted


# --- Search Handler ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    query = update.message.text.strip()

    if uid not in user_credits:
        user_credits[uid] = 5

    if user_credits[uid] < 5:
        await update.message.reply_text("❌ Not enough coins. Use /start → Add Funds.")
        return

    searching_msg = await update.message.reply_text("🔍 Searching...")

    query = clean_input(query)
    url = API_URL + query

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200 or not is_valid_data(r.text):
            await searching_msg.edit_text("❌ No data found or server error.")
            return

        response_text = r.text.strip()

        aadhaar_number = extract_aadhaar_from_response(response_text)
        aadhaar_data = None
        if aadhaar_number:
            aadhaar_data = await fetch_aadhaar_details(aadhaar_number)

        formatted = format_combined_response(response_text, aadhaar_data)

        user_credits[uid] -= 5
        await searching_msg.edit_text(
            f"{formatted}\n\n💰 Coins left: {user_credits[uid]}",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Search error: {e}")
        await searching_msg.edit_text("⚠️ System error occurred.")


# --- Owner Command: Add Coins ---
async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        if target_id not in user_credits:
            user_credits[target_id] = 0
        user_credits[target_id] += amount
        await update.message.reply_text(
            f"✅ Added {amount} coins to {target_id}. New balance: {user_credits[target_id]}"
        )
    except:
        await update.message.reply_text("⚠️ Usage: /addcoin <user_id> <amount>")


# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CommandHandler("addcoin", addcoin))

    logging.info("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
        
