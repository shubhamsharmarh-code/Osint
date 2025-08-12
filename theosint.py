
import logging
import re
import requests
import json
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

# --- Config ---
BOT_TOKEN = '8259380902:AAHcbQF6-IKh0tHm5-paYp4tnrpy4B7tcgw'
OWNER_ID = 7835198116

# --- API Config (can be changed by owner) ---
api_config = {
    "token": "8217808614:04wbEZ3i",
    "url": "https://leakosintapi.com/"
}

# --- Data Stores ---
user_credits = {}
referred_users = set()
all_users = set()  # Track all users for broadcasting

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Translation function ---
def translate_to_english(text):
    """Simple translation mapping for common Russian terms"""
    if not text or not isinstance(text, str):
        return text
    
    russian_to_english = {
        'имя': 'Name',
        'фамилия': 'Last Name', 
        'телефон': 'Phone',
        'email': 'Email',
        'адрес': 'Address',
        'город': 'City',
        'страна': 'Country',
        'дата': 'Date',
        'возраст': 'Age',
        'пол': 'Gender',
        'работа': 'Job',
        'компания': 'Company',
        'должность': 'Position',
        'зарплата': 'Salary',
        'образование': 'Education',
        'университет': 'University',
        'школа': 'School',
        'социальные': 'Social Networks',
        'профиль': 'Profile',
        'аккаунт': 'Account',
        'пароль': 'Password',
        'логин': 'Login',
        'регистрация': 'Registration',
        'последний': 'Last Seen',
        'статус': 'Status',
        'друзья': 'Friends',
        'подписчики': 'Followers',
        'местоположение': 'Location',
        'ip': 'IP Address',
        'домен': 'Domain',
        'сайт': 'Website',
        'владелец': 'Owner',
        'администратор': 'Administrator',
        'модератор': 'Moderator',
        'пользователь': 'User',
        'активность': 'Activity',
        'онлайн': 'Online',
        'офлайн': 'Offline',
        'неизвестно': 'Unknown',
        'данные': 'Data',
        'информация': 'Information',
        'результат': 'Result',
        'найдено': 'Found',
        'записи': 'Records',
        'база': 'Database',
        'источник': 'Source'
    }
    
    # Replace Russian words with English equivalents
    translated = text
    for russian, english in russian_to_english.items():
        translated = translated.replace(russian, english)
    
    return translated

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

# --- Admin Commands ---
async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "🔧 <b>API Configuration</b>\n\n"
            f"Current Token: <code>{api_config['token']}</code>\n\n"
            "Usage:\n"
            "• <code>/api NEW_TOKEN</code>\n"
            "Example: <code>/api 1234567890:ABCDEF</code>",
            parse_mode='HTML'
        )
        return
    
    new_token = ' '.join(args)
    api_config["token"] = new_token
    await update.message.reply_text(f"✅ API token updated to: <code>{new_token}</code>", parse_mode='HTML')

async def addcoin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "💰 <b>Add Coins</b>\n\n"
            "Usage: <code>/addcoin USER_ID AMOUNT</code>\n"
            "Example: <code>/addcoin 123456789 100</code>",
            parse_mode='HTML'
        )
        return
    
    try:
        target_uid = int(args[0])
        amount = int(args[1])
        
        if target_uid not in user_credits:
            user_credits[target_uid] = 0
        
        user_credits[target_uid] += amount
        
        # Notify admin
        await update.message.reply_text(
            f"✅ <b>Coins Added Successfully!</b>\n"
            f"User ID: <code>{target_uid}</code>\n"
            f"Amount: <code>{amount} coins</code>\n"
            f"New Balance: <code>{user_credits[target_uid]} coins</code>",
            parse_mode='HTML'
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                target_uid,
                f"🎉 <b>COINS RECEIVED!</b>\n"
                f"╔══════════════════════╗\n"
                f"┃ 💰 <b>Amount:</b> <code>{amount} coins</code>     ┃\n"
                f"┃ 💳 <b>New Balance:</b> <code>{user_credits[target_uid]} coins</code> ┃\n"
                f"┃ 👑 <b>From:</b> Admin              ┃\n"
                f"╚══════════════════════╝",
                parse_mode='HTML'
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ User notified but couldn't send message: {str(e)}")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount. Please use numbers only.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

# Global variable to track broadcast state
broadcast_waiting = {}

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != OWNER_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    # Set broadcast waiting state
    broadcast_waiting[uid] = True
    await update.message.reply_text("📢 <b>Broadcast Mode</b>\n\nSend me the message you want to broadcast to all users:", parse_mode='HTML')

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str):
    uid = update.effective_user.id
    sent_count = 0
    failed_count = 0
    
    # Send status message
    status_msg = await update.message.reply_text("📤 Broadcasting message...")
    
    for user_id in all_users:
        try:
            # Send message directly without fancy formatting
            await context.bot.send_message(user_id, message_text, parse_mode='HTML')
            sent_count += 1
        except Exception:
            failed_count += 1
    
    # Update status
    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n"
        f"╔══════════════════════╗\n"
        f"┃ 📤 <b>Sent:</b> <code>{sent_count} users</code>        ┃\n"
        f"┃ ❌ <b>Failed:</b> <code>{failed_count} users</code>      ┃\n"
        f"┃ 👥 <b>Total:</b> <code>{len(all_users)} users</code>      ┃\n"
        f"╚══════════════════════╝\n\n"
        f"📝 <b>Message:</b> {message_text}",
        parse_mode='HTML'
    )
    
    # Clear broadcast waiting state
    broadcast_waiting[uid] = False

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args
    
    # Track all users
    all_users.add(uid)

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
        "🕵️ <b>Welcome to Cyreo Osint Bot!</b>\n\n"
        "🔍 I can search for:\n"
        "• Phone numbers\n"
        "• Email addresses\n"
        "• Usernames\n"
        "• Domains\n"
        "• Social profiles\n\n"
        "💰 Each search costs 5 coins",
        reply_markup=main_keyboard,
        parse_mode='HTML'
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
    
    try:
        parsed_data = json.loads(primary_data)
        
        if isinstance(parsed_data, dict):
            formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n\n"
            
            # Handle databases
            if 'List' in parsed_data or any(key for key in parsed_data.keys() if isinstance(parsed_data[key], dict) and 'Data' in parsed_data[key]):
                databases = parsed_data.get('List', parsed_data)
                
                for db_name, db_info in databases.items():
                    if isinstance(db_info, dict) and 'Data' in db_info:
                        formatted += f"🗃️ <b>{db_name}</b>\n"
                        formatted += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        
                        data_records = db_info['Data']
                        if isinstance(data_records, list):
                            for i, record in enumerate(data_records, 1):
                                if isinstance(record, dict):
                                    formatted += f"<b>📄 Record {i}:</b>\n"
                                    for key, value in record.items():
                                        if value and str(value).strip():
                                            translated_key = translate_to_english(str(key))
                                            translated_value = translate_to_english(str(value))
                                            formatted += f"• <b>{translated_key.replace('_', ' ').title()}:</b> <code>{translated_value}</code>\n"
                                    formatted += "\n"
                        
                        formatted += f"📊 <b>Results:</b> {db_info.get('NumOfResults', 'N/A')}\n\n"
            
            # Handle other data
            else:
                formatted += "📋 <b>Data Found:</b>\n"
                formatted += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                for key, value in parsed_data.items():
                    if value and str(value).strip():
                        translated_key = translate_to_english(str(key))
                        translated_value = translate_to_english(str(value))
                        formatted += f"• <b>{translated_key.replace('_', ' ').title()}:</b> <code>{translated_value}</code>\n"
            
            return formatted
            
    except Exception as e:
        # Fallback for non-JSON data
        formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n\n"
        lines = primary_data.strip().split('\n')
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    translated_key = translate_to_english(parts[0].strip())
                    translated_value = translate_to_english(parts[1].strip())
                    formatted += f"• <b>{translated_key}:</b> <code>{translated_value}</code>\n"
        return formatted
    
    return None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    query = update.message.text.strip()
    
    # Track all users
    all_users.add(uid)
    
    # Check if user is in broadcast waiting mode
    if uid in broadcast_waiting and broadcast_waiting[uid]:
        await handle_broadcast_message(update, context, query)
        return

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
            "token": api_config["token"],
            "request": query,
            "limit": 100,
            "lang": "en"  # Changed to English
        }
        url = api_config["url"]
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
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("api", api_command))
    app.add_handler(CommandHandler("addcoin", addcoin_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Other handlers
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    app.run_polling()

if __name__ == "__main__":
    main ()
