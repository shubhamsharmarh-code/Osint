
import logging
import re
import requests
import pytz
import json
import asyncio
import time
from datetime import datetime, timedelta
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

# --- Data Stores with extra safety ---
user_credits = {}
referred_users = set()
user_referrals = {}  # Track who referred whom: {referrer_id: [referred_user_ids]}
referral_rewards = {}  # Track referral rewards given: {user_id: count}

# --- Rate limiting to prevent spam ---
user_last_search = {}  # Track last search time per user
SEARCH_COOLDOWN = 2  # 2 seconds between searches per user

# --- Data validation helpers ---
def safe_int(value, default=0):
    """Safely convert to int with fallback"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_get_credits(uid):
    """Safely get user credits with validation"""
    try:
        return user_credits.get(uid, 0) if isinstance(uid, int) else 0
    except:
        return 0

def safe_set_credits(uid, amount):
    """Safely set user credits with validation"""
    try:
        if isinstance(uid, int) and isinstance(amount, (int, float)) and amount >= 0:
            user_credits[uid] = int(amount)
            return True
    except:
        pass
    return False

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

    if args and len(args) > 0 and args[0].startswith("ref_"):
        try:
            ref_id = safe_int(args[0][4:])
            
            # Extra strong validation checks
            if (ref_id > 0 and                              # Valid referrer ID
                ref_id != uid and                           # Can't refer yourself
                ref_id in user_credits and                  # Referrer must exist
                uid not in referred_users and               # User not already referred
                ref_id != OWNER_ID and                      # Owner can't get referral rewards
                uid != OWNER_ID and                         # Owner can't be referred
                isinstance(uid, int) and uid > 0):          # Valid user ID
                
                # Initialize referral tracking safely
                if ref_id not in user_referrals:
                    user_referrals[ref_id] = []
                if ref_id not in referral_rewards:
                    referral_rewards[ref_id] = 0
                
                # Unlimited referrals - no daily limit
                # Simple 5 coins per referral with safe credit handling
                current_ref_credits = safe_get_credits(ref_id)
                safe_set_credits(ref_id, current_ref_credits + 5)
                referred_users.add(uid)
                user_referrals[ref_id].append(uid)
                referral_rewards[ref_id] += 1
                
                try:
                    await context.bot.send_message(
                        ref_id, 
                        f"✨ <b>REFERRAL SUCCESS!</b>\n"
                        f"👤 New user joined via your link\n"
                        f"💰 +5 coins awarded\n"
                        f"📊 Total referrals: {referral_rewards[ref_id]}\n"
                        f"💳 New balance: {user_credits[ref_id]} coins",
                        parse_mode='HTML'
                    )
                except:
                    pass
        except (ValueError, IndexError):
            # Invalid referral code format
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
        try:
            coins = safe_get_credits(uid)
            await query.message.reply_text(f"💰 Your balance: {coins} coins")
        except Exception as e:
            logging.error(f"Error showing balance for {uid}: {e}")
            await query.message.reply_text("❌ Error retrieving balance")

    elif query.data == "add_funds":
        try:
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
        except Exception as e:
            logging.error(f"Error showing pricing for {uid}: {e}")

    elif query.data == "referral":
        try:
            bot_info = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start=ref_{uid}"
            
            # Get referral stats with safety
            total_referrals = referral_rewards.get(uid, 0) if isinstance(uid, int) else 0
            total_earned = total_referrals * 5
        
            await query.message.reply_text(
                f"💎 <b>REFERRAL PROGRAM</b>\n"
                f"━━━━━━━━━━━━━━\n"
                f"🎁 Simple Reward: 5 coins per referral\n"
                f"━━━━━━━━━━━━━━\n"
                f"📊 <b>Your Stats:</b>\n"
                f"┃ ✅ Total Referrals: {total_referrals}\n"
                f"┃ 💰 Total Earned: {total_earned} coins\n"
                f"━━━━━━━━━━━━━━\n"
                f"🔗 <b>Your Referral Link:</b>\n"
                f"<code>{ref_link}</code>",
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error showing referral for {uid}: {e}")

def is_valid_data(data):
    """Check if the response contains valid searchable data"""
    if not data or not isinstance(data, str):
        return False
    
    data = data.strip()
    if not data:
        return False
    
    # Check for empty JSON responses
    if data in ['[]', '{}', 'null', 'None']:
        return False
    
    data_lower = data.lower()
    
    # Check for API error messages (most important - check first)
    error_patterns = [
        "rate limit exceeded",
        "try again after",
        "error",
        "failed",
        "timeout",
        "server error",
        "invalid",
        "blocked",
        "denied",
        "unauthorized",
        "forbidden",
        "service unavailable",
        "internal server error",
        "bad request",
        "api limit",
        "quota exceeded"
    ]
    
    for pattern in error_patterns:
        if pattern in data_lower:
            return False
    
    # Check for various "no records found" patterns
    no_records_patterns = [
        "no records found",
        "no record found", 
        "not found",
        "no data available",
        "no results",
        "data not found",
        "no information",
        "empty result",
        "nothing found"
    ]
    
    for pattern in no_records_patterns:
        if pattern in data_lower:
            return False
    
    # Check if response looks like JSON error format
    try:
        import json
        parsed = json.loads(data)
        if isinstance(parsed, dict):
            # Check for common error keys
            error_keys = ['error', 'status', 'message']
            for key in error_keys:
                if key in parsed:
                    error_value = str(parsed[key]).lower()
                    if any(err in error_value for err in ['error', 'fail', 'limit', 'exceeded', 'timeout']):
                        return False
    except:
        pass
    
    return True

def format_data_response(data, query_type):
    """Format the API response in a very stylish way"""
    if not is_valid_data(data):
        return None
    
    # Double check for error patterns in the data before formatting
    data_lower = data.lower()
    if any(pattern in data_lower for pattern in ["rate limit", "error", "try again", "exceeded"]):
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
            
        elif isinstance(parsed_data, dict) and parsed_data:
            formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
            formatted += "╔════════════════════════╗\n"
            
            for key, value in parsed_data.items():
                if value and str(value).strip():
                    formatted += f"┃ 📌 <b>{key.replace('_', ' ').title()}:</b> <code>{value}</code>\n"
            
            formatted += "╚════════════════════════╝"
            return formatted
    except json.JSONDecodeError:
        pass
    except Exception:
        pass
    
    # If not JSON, format as plain text with style
    lines = data.strip().split('\n')
    useful_lines = [line for line in lines if line.strip()]
    
    if not useful_lines:
        return None
    
    formatted = "🎯 <b>SEARCH RESULTS FOUND</b>\n"
    formatted += "╔════════════════════════╗\n"
    
    for line in useful_lines:
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
    
    # Extra safety checks
    if not uid or not isinstance(uid, int):
        return
        
    query = update.message.text.strip() if update.message and update.message.text else ""
    
    # Input validation
    if not query or len(query) > 100:  # Prevent very long queries
        await update.message.reply_text("❌ Invalid query. Please enter a valid search term (max 100 characters).")
        return
    
    # Rate limiting check
    current_time = time.time()
    if uid in user_last_search:
        time_diff = current_time - user_last_search[uid]
        if time_diff < SEARCH_COOLDOWN:
            await update.message.reply_text(f"⏰ Please wait {SEARCH_COOLDOWN - int(time_diff)} seconds before searching again.")
            return
    
    user_last_search[uid] = current_time

    # Initialize credits safely
    if uid not in user_credits:
        safe_set_credits(uid, 5)  # new users get 5 coins

    coins = safe_get_credits(uid)
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
    
    # Variable to track if we should deduct credits
    should_deduct_credits = False
    response_text = ""
    
    try:
        r = requests.get(url, timeout=15)
        
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
            
        # Check for specific error types first
        response_lower = response_text.lower()
        
        # Rate limit error handling
        if "rate limit" in response_lower and "exceeded" in response_lower:
            await searching_msg.edit_text(
                "⏰ <b>RATE LIMIT EXCEEDED</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🚫 API rate limit hit        ┃\n"
                "┃ ⏱️ Please wait 1-2 minutes   ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return
            
        # Other API errors
        if any(err in response_lower for err in ["error", "failed", "timeout", "invalid", "blocked"]):
            await searching_msg.edit_text(
                "❌ <b>API ERROR</b>\n"
                "╔══════════════════════╗\n"
                "┃ ⚠️ Server returned error     ┃\n"
                "┃ 🔄 Please try again later    ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )
            return
        
        # Check if the data is valid using our validation function
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
            
        # Try to format the response
        formatted_result = format_data_response(response_text, query)
        
        if formatted_result:
            # Only NOW we deduct credits - after confirming we have good formatted data
            should_deduct_credits = True
            current_balance = safe_get_credits(uid)
            if current_balance >= 5:
                safe_set_credits(uid, current_balance - 5)
            
            final_balance = safe_get_credits(uid)
            await searching_msg.edit_text(
                f"{formatted_result}\n\n"
                f"🎯 <b>Query:</b> <code>{query}</code>\n"
                f"💰 <b>Coins Left:</b> {final_balance}",
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
    except requests.exceptions.RequestException as e:
        await searching_msg.edit_text(
            "❌ <b>NETWORK ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🌐 Network request failed    ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
    except Exception as e:
        # Log the actual error for debugging
        logging.error(f"Unexpected error in handle_text: {str(e)}")
        
        # If credits were deducted, refund them
        if should_deduct_credits:
            user_credits[uid] += 5
            
        await searching_msg.edit_text(
            "⚠️ <b>SYSTEM ERROR</b>\n"
            "╔══════════════════════╗\n"
            "┃ 🔧 Unexpected error occurred ┃\n"
            "┃ 💳 Credits not deducted      ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )

async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Unauthorized")
        return

    args = context.args if context.args else []
    if len(args) != 2:
        await update.message.reply_text("Usage: /addcoin <user_id> <amount>")
        return

    try:
        user_id = safe_int(args[0])
        amount = safe_int(args[1])
        
        # Extra validation
        if user_id <= 0 or amount < 0 or amount > 10000:  # Prevent negative or excessive amounts
            await update.message.reply_text("⚠️ Invalid user ID or amount (max: 10000)")
            return
            
        current_balance = safe_get_credits(user_id)
        new_balance = current_balance + amount
        
        if safe_set_credits(user_id, new_balance):
            await update.message.reply_text(f"✅ Added {amount} coins to user {user_id}. New balance: {new_balance}")
            try:
                await context.bot.send_message(user_id, f"💰 You've received {amount} coins from admin. Balance: {new_balance}")
            except Exception as e:
                logging.warning(f"Could not notify user {user_id}: {e}")
        else:
            await update.message.reply_text("⚠️ Failed to update credits")
    except Exception as e:
        logging.error(f"Error in addcoin: {e}")
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

        