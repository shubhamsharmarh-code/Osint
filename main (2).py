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
        user_credits[uid] = 5  # 1 free search = 5 coins

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
            "🔍 Examples:\n"
            "• 918601308969          (Phone)\n"
            "• example@mail.com      (Email)\n"
            "• t.me/xyz              (Telegram)\n"
            "• 192.168.1.1           (IP Address)\n"
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

def format_data_response(data, query_type):
    """Format the API response in a very stylish way"""
    if not data or data.strip() == "":
        return None
    
    # Check for various "no records found" patterns
    no_records_patterns = [
        "no records found",
        "no record found", 
        "not found",
        "no data available",
        "no results",
        "data not found"
    ]
    
    data_lower = data.lower()
    if any(pattern in data_lower for pattern in no_records_patterns):
        return None
    
    # Try to parse if it's JSON-like data
    try:
        import json
        parsed_data = json.loads(data)
        if isinstance(parsed_data, list) and len(parsed_data) > 0:
            formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
            formatted += "╔════════════════════════╗\n"
            
            for i, item in enumerate(parsed_data, 1):
                formatted += f"┃ <b>📋 Record #{i}</b>\n"
                formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
                
                if isinstance(item, dict):
                    for key, value in item.items():
                        if value and str(value).strip():
                            if key == "name":
                                formatted += f"┃ 👤 <b>Name:</b> <code>{value}</code>\n"
                            elif key == "mobile":
                                formatted += f"┃ 📱 <b>Mobile:</b> <code>{value}</code>\n"
                            elif key == "father_name":
                                formatted += f"┃ 👨‍👦 <b>Father:</b> <code>{value}</code>\n"
                            elif key == "address":
                                formatted += f"┃ 🏠 <b>Address:</b> <code>{value}</code>\n"
                            elif key == "circle":
                                formatted += f"┃ 📡 <b>Circle:</b> <code>{value}</code>\n"
                            elif key == "id_number":
                                formatted += f"┃ 🆔 <b>ID:</b> <code>{value}</code>\n"
                            elif key == "email" and value:
                                formatted += f"┃ 📧 <b>Email:</b> <code>{value}</code>\n"
                            elif key == "alt_mobile" and value:
                                formatted += f"┃ 📞 <b>Alt Mobile:</b> <code>{value}</code>\n"
                
                if i < len(parsed_data):
                    formatted += "┣━━━━━━━━━━━━━━━━━━━━━━━━┫\n"
            
            formatted += "╚════════════════════════╝"
            return formatted
            
        elif isinstance(parsed_data, dict):
            formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
            formatted += "╔════════════════════════╗\n"
            
            for key, value in parsed_data.items():
                if value and str(value).strip():
                    formatted += f"┃ 📌 <b>{key.replace('_', ' ').title()}:</b> <code>{value}</code>\n"
            
            formatted += "╚════════════════════════╝"
            return formatted
    except:
        pass
    
    # If not JSON, format as plain text with style
    lines = data.strip().split('\n')
    formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
    formatted += "╔════════════════════════╗\n"
    
    for line in lines:
        if line.strip():
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    formatted += f"┃ 📌 <b>{parts[0].strip()}:</b> <code>{parts[1].strip()}</code>\n"
                else:
                    formatted += f"┃ • {line.strip()}\n"
            else:
                formatted += f"┃ • {line.strip()}\n"
    
    formatted += "╚════════════════════════╝"
    return formatted

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    query = update.message.text.strip()

    if uid not in user_credits:
        user_credits[uid] = 5  # new users get 5 coins

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

    # Show searching message
    searching_msg = await update.message.reply_text("🔍 Searching...")
    
    query = clean_input(query)
    url = API_URL + query
    try:
        r = requests.get(url, timeout=15)  # Increased timeout
        
        # Check if request was successful
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
        
        # Check if response is empty
        if not response_text:
            await searching_msg.edit_text(
                "❌ <b>NO DATA FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 Server returned empty     ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return
            
        # Check for various "no records found" patterns
        no_records_patterns = [
            "no records found",
            "no record found", 
            "not found",
            "no data",
            "no results",
            "[]",
            "{}",
            "null"
        ]
        
        response_lower = response_text.lower()
        if any(pattern in response_lower for pattern in no_records_patterns):
            await searching_msg.edit_text(
                "❌ <b>NO RECORDS FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 No data available         ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return
            
        # Try to format the response
        formatted_result = format_data_response(response_text, query)
        
        if formatted_result:
            # Only deduct coins when we have successfully formatted useful data
            user_credits[uid] -= 5
            
            await searching_msg.edit_text(
                f"{formatted_result}\n\n"
                f"🎯 <b>Query:</b> <code>{query}</code>\n"
                f"💰 <b>Coins Left:</b> {user_credits[uid]}",
                parse_mode='HTML'
            )
        else:
            # Raw response exists but couldn't be formatted properly
            await searching_msg.edit_text(
                "❌ <b>NO USEFUL DATA FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 Data format not supported ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            
    except requests.exceptions.Timeout:
        await searching_msg.edit_text(
            "⏰ <b>SEARCH TIMEOUT</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🕐 Request took too long     ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
    except requests.exceptions.ConnectionError:
        await searching_msg.edit_text(
            "❌ <b>CONNECTION ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🌐 Can't reach API server    ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
    except Exception as e:
        await searching_msg.edit_text(
            "⚠️ <b>UNEXPECTED ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🔧 System error occurred     ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )

async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /addcoin <user_id> <amount>")
        return

    try:
        user_id = int(args[0])
        amount = int(args[1])
        user_credits[user_id] = user_credits.get(user_id, 0) + amount
        await update.message.reply_text(f"✅ Added {amount} coins to user {user_id}.")
        try:
            await context.bot.send_message(user_id, f"💰 You've received {amount} coins from admin. Balance: {user_credits[user_id]}")
        except:
            pass
    except:
        await update.message.reply_text("⚠️ Invalid input")

# --- Main ---
if __name__ == '__main__':
    print("✅ Bot is starting...")

    scheduler = AsyncIOScheduler(timezone=pytz.UTC)

    app = Application.builder().token(BOT_TOKEN).build()
    app.job_queue.scheduler = scheduler

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcoin", addcoin))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure no other bot instance is running.")
    
