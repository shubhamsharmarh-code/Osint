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
BOT_TOKEN = '8227679174:AAFlje8cX3pgLS1hW8in1D8uWaulGPcPWB0'
OWNER_ID = 7835198116
API_URL = ''
AADHAAR_API_URL = ''

# --- Data Stores ---
user_credits = {}
referred_users = set()

# Add periodic cleanup to prevent memory leaks
import time
last_cleanup = time.time()

def cleanup_old_data():
    """Clean up old user data to prevent memory issues"""
    global last_cleanup
    current_time = time.time()

    # Run cleanup every 6 hours
    if current_time - last_cleanup > 21600:
        # Keep only users with credits > 0 or recent activity
        active_users = {uid: credits for uid, credits in user_credits.items() if credits > 0}
        user_credits.clear()
        user_credits.update(active_users)

        last_cleanup = current_time
        logging.info(f"Cleaned up user data. Active users: {len(user_credits)}")

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- Normalize Query ---
def clean_input(text):
    """Enhanced input cleaning for mobile numbers, Aadhaar, and other data"""
    if not text:
        return text

    # Remove all spaces, dashes, brackets, and other common separators
    cleaned = re.sub(r'[\s\-\(\)\+]', '', text.strip())
    digits_only = re.sub(r'[^\d]', '', text.strip())

    # First, check for phone number patterns (priority over Aadhaar)
    # Pattern 1: +919821932773, +91 98219 32773, 919821932773 -> extract 10 digits
    phone_match = re.match(r'^(?:\+?91[\s\-]?)?([6-9]\d{9})$', cleaned)
    if phone_match:
        return phone_match.group(1)

    # Pattern 2: Check if digits form a valid phone number
    if len(digits_only) == 10 and digits_only[0] in '6789':
        return digits_only
    elif len(digits_only) == 12 and digits_only.startswith('91') and digits_only[2] in '6789':
        return digits_only[2:]  # Remove 91 prefix

    # Pattern 3: Look for phone number in longer strings
    if len(digits_only) > 10:
        # Try to find a 10-digit mobile number pattern
        mobile_match = re.search(r'91([6-9]\d{9})', digits_only)
        if mobile_match:
            return mobile_match.group(1)

        # Also try to find standalone 10-digit mobile
        mobile_match = re.search(r'([6-9]\d{9})', digits_only)
        if mobile_match:
            return mobile_match.group(1)

    # Check if it's an Aadhaar number (12 digits, not starting with 0 or 1, and not a phone)
    if len(digits_only) == 12 and digits_only.isdigit() and digits_only[0] not in '01':
        # Make sure it's not a phone number with 91 prefix
        if not (digits_only.startswith('91') and digits_only[2] in '6789'):
            return digits_only

    # If no mobile pattern found, return original for other types of searches
    return text.strip()

def extract_aadhaar_from_response(response_text):
    """Extract Aadhaar number from API response"""
    if not response_text:
        return None

    # Look for 12-digit Aadhaar patterns
    aadhaar_patterns = [
        r'["\']?(?:aadhaar|aadhar|id_number|aadhaar_number)["\']?\s*:\s*["\']?(\d{12})["\']?',
        r'["\']?(\d{4}\s*\d{4}\s*\d{4})["\']?',
        r'["\']?(\d{12})["\']?'
    ]

    for pattern in aadhaar_patterns:
        matches = re.findall(pattern, response_text, re.IGNORECASE)
        for match in matches:
            # Clean the match (remove spaces)
            clean_aadhaar = re.sub(r'\s+', '', match)
            # Validate it's exactly 12 digits
            if len(clean_aadhaar) == 12 and clean_aadhaar.isdigit():
                return clean_aadhaar

    return None

def extract_phone_from_aadhaar_response(response_text):
    """Extract phone numbers from Aadhaar API response"""
    phone_numbers = []
    # Regex to find 10-digit phone numbers, potentially with country code
    phone_patterns = [
        r'(?:phone|mobile|contact)["\']?\s*:\s*["\']?(?:\+91|91)?\s*(\d{10})["\']?',
        r'["\']?(\d{10})["\']?' # Simple 10 digit number
    ]

    for pattern in phone_patterns:
        matches = re.findall(pattern, response_text)
        for match in matches:
            # Ensure it's a 10-digit number and not already added
            if len(match) == 10 and match.isdigit() and match not in phone_numbers:
                phone_numbers.append(match)

    # Remove duplicates by converting to set and back to list
    return list(set(phone_numbers))

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
        user_credits[uid] = 30  # 6 free searches = 30 coins

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

async def addcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add coins to a user - only for owner"""
    uid = update.effective_user.id

    if uid != OWNER_ID:
        await update.message.reply_text("❌ Only admin can use this command.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addcoin <user_id> <coins>")
        return

    try:
        target_uid = int(context.args[0])
        coins = int(context.args[1])

        if target_uid not in user_credits:
            user_credits[target_uid] = 0

        user_credits[target_uid] += coins

        await update.message.reply_text(
            f"✅ Added {coins} coins to user {target_uid}\n"
            f"New balance: {user_credits[target_uid]} coins"
        )

        # Notify the user
        try:
            await context.bot.send_message(
                target_uid,
                f"🎉 You received {coins} coins from admin!\n"
                f"💰 New balance: {user_credits[target_uid]} coins"
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or coin amount.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "search":
        await query.message.reply_text(
            "📨 Send phone number to search.\n\n"
            "🔍 Examples:\n"
            "• 918601308969          (Phone)\n"
            "• +918601308969\n"
            "• +91 8601 308969\n"
            "•  8601308969\n\n"
            "🛡️ Currently only Indian number data is available\n"
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

    # Check for critical API error responses only
    critical_errors = [
        "rate limit exceeded",
        "try again after",
        "server error",
        "internal error",
        "service unavailable",
        "timeout",
        "too many requests",
        "limit reached",
        "quota exceeded"
    ]

    for pattern in critical_errors:
        if pattern in data_lower:
            return False

    # Accept almost any response from APIs - even "no records found" is valuable information
    if len(data) > 3:
        return True

    return False

def has_meaningful_data(primary_data, secondary_data=None):
    """Check if the API responses contain actual user data, not just empty fields"""
    all_data = [primary_data, secondary_data] if secondary_data else [primary_data]

    for data in all_data:
        if not data:
            continue

        data_lower = data.lower()

        # Check for indicators of no data
        no_data_indicators = [
            "no records found",
            "no data available",
            "n/a",
            "not available",
            "name: n/a",
            "father name: n/a",
            "address:\nn/a",
            "phone: n/a"
        ]

        # If response contains mostly empty/N/A fields, consider it as no meaningful data
        empty_field_count = 0
        for indicator in no_data_indicators:
            if indicator in data_lower:
                empty_field_count += 1

        # If more than 3 empty field indicators, likely no meaningful data
        if empty_field_count >= 3:
            continue

        # Check for actual data patterns (names, addresses, valid phone numbers)
        meaningful_patterns = [
            r'name["\']?\s*:\s*["\']?[a-zA-Z]{2,}',  # Name with actual letters
            r'mobile["\']?\s*:\s*["\']?\d{10}',      # Valid mobile number
            r'address["\']?\s*:\s*["\']?[a-zA-Z0-9\s,.-]{5,}',  # Address with content
            r'father["\']?\s*:\s*["\']?[a-zA-Z]{2,}' # Father name with letters
        ]

        for pattern in meaningful_patterns:
            if re.search(pattern, data_lower):
                return True

    return False



def is_mobile_number(query):
    """Check if the query string looks like a mobile number"""
    if not query:
        return False

    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', query)

    # Check for various phone number formats
    # 1. Standard 10-digit mobile (starts with 6-9)
    if len(digits_only) == 10 and digits_only[0] in '6789':
        return True

    # 2. 12-digit with 91 prefix (+919xxxxxxxxx)
    if len(digits_only) == 12 and digits_only.startswith('91') and digits_only[2] in '6789':
        return True

    # 3. 13-digit with 91 prefix (for some edge cases)
    if len(digits_only) == 13 and digits_only.startswith('91') and digits_only[2] in '6789':
        return True

    # 4. Check if query contains phone pattern with +91 format
    phone_pattern = re.search(r'\+?91[\s\-]?([6-9]\d{9})', query)
    if phone_pattern:
        return True

    # 5. Check for standalone phone number pattern
    phone_pattern = re.search(r'([6-9]\d{9})', digits_only)
    if phone_pattern and len(phone_pattern.group(1)) == 10:
        return True

    return False

def is_aadhaar_number(query):
    """Check if the query string looks like an Aadhaar number"""
    if not query:
        return False

    # Remove all non-digit characters
    digits_only = re.sub(r'[^\d]', '', query)

    # Aadhaar is exactly 12 digits, doesn't start with 0 or 1
    if len(digits_only) == 12 and digits_only.isdigit() and digits_only[0] not in '01':
        # Make sure it's not a phone number with 91 prefix
        if not (digits_only.startswith('91') and digits_only[2] in '6789'):
            return True

    return False





async def fetch_phone_details(phone_number):
    """Fetch details using the phone number API"""
    try:
        url = API_URL + phone_number
        r = requests.get(url, timeout=15)

        # Check if response has data regardless of status code
        if r.text.strip():
            response_text = r.text.strip()
            # Check for common error responses that should not be processed
            if any(error in response_text.lower() for error in ['error', 'failed', 'invalid', 'not found']):
                logging.warning(f"API returned error for {phone_number}: {response_text[:100]}")
                return None
            if is_valid_data(response_text):
                logging.info(f"Got valid data for {phone_number} with status {r.status_code}")
                return response_text
        
        logging.warning(f"API returned status {r.status_code} for {phone_number}")
    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching phone details for {phone_number}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching phone details for {phone_number}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error fetching phone details for {phone_number}: {e}")
    return None

async def fetch_aadhaar_details(aadhaar_number):
    """Fetch details using the Aadhaar number API"""
    try:
        url = AADHAAR_API_URL + aadhaar_number
        r = requests.get(url, timeout=15)

        # Check if response has data regardless of status code
        if r.text.strip():
            response_text = r.text.strip()
            # Check for common error responses
            if any(error in response_text.lower() for error in ['error', 'failed', 'invalid', 'not found']):
                logging.warning(f"Aadhaar API returned error for {aadhaar_number}: {response_text[:100]}")
                return None
            if is_valid_data(response_text):
                logging.info(f"Got valid Aadhaar data for {aadhaar_number} with status {r.status_code}")
                return response_text
        
        logging.warning(f"Aadhaar API returned status {r.status_code} for {aadhaar_number}")
    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching Aadhaar details for {aadhaar_number}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching Aadhaar details for {aadhaar_number}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error fetching Aadhaar details for {aadhaar_number}: {e}")
    return None



def format_combined_response(primary_data, secondary_data=None):
    """Format combined response from both APIs with merged data"""
    if not primary_data or not primary_data.strip():
        return None

    formatted = "🎯 <b>SEARCH RESULTS</b>\n"
    formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Collect all data from both APIs
    all_records = []

    # Parse primary data
    try:
        import json
        parsed_primary = json.loads(primary_data)

        if isinstance(parsed_primary, dict):
            all_records.append(parsed_primary)
        elif isinstance(parsed_primary, list):
            all_records.extend(parsed_primary)
    except json.JSONDecodeError:
        # Handle as raw data if not JSON - format it nicely
        return format_raw_data_stylish(primary_data)

    # Parse secondary data and merge
    if secondary_data:
        try:
            parsed_secondary = json.loads(secondary_data)
            if isinstance(parsed_secondary, list):
                all_records.extend(parsed_secondary)
            elif isinstance(parsed_secondary, dict):
                all_records.append(parsed_secondary)
        except json.JSONDecodeError:
            pass

    # Remove duplicates based on mobile number and id
    unique_records = {}
    for record in all_records:
        if isinstance(record, dict) and record.get("mobile"):
            # Use mobile + id as unique key, or just mobile if no id
            key = f"{record['mobile']}_{record.get('id', '')}"
            unique_records[key] = record

    # Display each record individually
    record_count = 1
    for key, record in unique_records.items():
        formatted += f"📋 <b>Record {record_count}:</b>\n"

        # Mobile Number
        if record.get("mobile"):
            formatted += f"📱 <b>Mobile Number:</b> {record['mobile']}\n"

        # Name
        if record.get("name"):
            formatted += f"👤 <b>Name:</b> {record['name']}\n"

        # Father Name
        father = record.get("father_name") or record.get("father") or record.get("guardian_name")
        if father:
            formatted += f"👨‍👦 <b>Father Name:</b> {father}\n"

        # Address
        if record.get("address"):
            formatted += f"🏠 <b>Address:</b> {record['address']}\n"

        # Circle/Operator
        if record.get("circle"):
            formatted += f"📍 <b>Circle/Operator:</b> {record['circle']}\n"

        # Aadhaar
        aadhaar = (record.get("aadhaar") or record.get("id_number") or 
                   record.get("aadhar") or record.get("aadhaar_number"))
        if aadhaar:
            formatted += f"🆔 <b>Aadhaar Number:</b> {aadhaar}\n"

        # Alternative number
        alt_num = record.get("alternative_number") or record.get("alt_number")
        if alt_num:
            formatted += f"📞 <b>Alternative Number:</b> {alt_num}\n"

        # ID
        if record.get("id"):
            formatted += f"🔸 <b>Record ID:</b> {record['id']}\n"

        formatted += "\n"
        record_count += 1

    # Collect all linked numbers
    linked_numbers = set()
    operators = set()

    for record in unique_records.values():
        if record.get("mobile"):
            linked_numbers.add(record["mobile"])
        if record.get("alternative_number"):
            linked_numbers.add(record["alternative_number"])
        if record.get("alt_number"):
            linked_numbers.add(record["alt_number"])
        if record.get("circle"):
            operators.add(record["circle"].split()[-1] if record["circle"] else "")

    # Show linked numbers summary
    if linked_numbers and len(linked_numbers) > 1:
        formatted += f"🔗 <b>Linked Numbers ({len(linked_numbers)} found):</b>\n"
        for number in sorted(linked_numbers):
            formatted += f"• {number}\n"
        formatted += "\n"

        if operators:
            formatted += f"📡 <b>Network Operators:</b> {', '.join(sorted(filter(None, operators)))}\n\n"

    formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    formatted += "💰 <b>5 coins deducted from your balance</b>"

    return formatted

def format_raw_data_stylish(raw_data):
    """Format raw/non-JSON data in a stylish way similar to JSON responses"""
    formatted = "🎯 <b>SEARCH RESULTS</b>\n"
    formatted += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # Try to extract information from raw data
    lines = raw_data.strip().split('\n')
    record_count = 1

    formatted += f"📋 <b>Record {record_count}:</b>\n"

    # Look for common patterns in raw data
    mobile_found = False
    name_found = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to identify mobile numbers
        mobile_match = re.search(r'(\d{10})', line)
        if mobile_match and not mobile_found:
            formatted += f"📱 <b>Mobile Number:</b> {mobile_match.group(1)}\n"
            mobile_found = True
            continue

        # Try to identify names (lines with alphabets, not just numbers)
        if re.search(r'[a-zA-Z]{3,}', line) and not re.search(r'^\d+$', line) and not name_found:
            # Clean up common API response artifacts
            cleaned_line = re.sub(r'^["\'\[\]\{\}\,\:\;]+|["\'\[\]\{\}\,\:\;]+$', '', line)
            cleaned_line = re.sub(r'["\']', '', cleaned_line).strip()

            if len(cleaned_line) > 2 and not cleaned_line.lower() in ['null', 'none', 'n/a']:
                formatted += f"👤 <b>Name:</b> {cleaned_line}\n"
                name_found = True
                continue

        # For other data, show as general info
        if len(line) > 3:
            cleaned_line = re.sub(r'^["\'\[\]\{\}\,\:\;]+|["\'\[\]\{\}\,\:\;]+$', '', line)
            cleaned_line = re.sub(r'["\']', '', cleaned_line).strip()

            if cleaned_line and not cleaned_line.lower() in ['null', 'none', 'n/a', '{', '}', '[', ']']:
                formatted += f"🔸 <b>Additional Info:</b> {cleaned_line}\n"

    formatted += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    formatted += "💰 <b>5 coins deducted from your balance</b>"

    return formatted

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Periodic cleanup
    cleanup_old_data()

    uid = update.effective_user.id
    query = update.message.text.strip()

    if uid not in user_credits:
        user_credits[uid] = 30

    if user_credits[uid] < 5:
        await update.message.reply_text(
            "💸 <b>INSUFFICIENT FUNDS!</b>\n"
            "╔══════════════════════╗\n"
            f"┃ ❌ Balance: {user_credits[uid]} coins      ┃\n"
            "┃ 💳 Required: 5 coins     ┃\n"
            "┃ 🚀 Click /start → Add Funds ┃\n"
            "╚══════════════════════╝",
            parse_mode='HTML'
        )
        return

    # Input validation
    if len(query) > 50:
        await update.message.reply_text("❌ Input too long. Please send a valid phone number.")
        return

    if not re.search(r'\d', query):
        await update.message.reply_text("❌ Please send a valid phone number with digits.")
        return

    # Clean and normalize the input
    cleaned_query = clean_input(query)
    logging.info(f"Original query: '{query}' -> Cleaned: '{cleaned_query}'")

    if not cleaned_query or len(cleaned_query) < 10:
        await update.message.reply_text(
            "❌ Please send a valid phone number.\n\n"
            "📱 Examples:\n"
            "• 9876543210\n"
            "• +919876543210\n"
            "• 919876543210"
        )
        return

    # Show processing message
    processing_msg = await update.message.reply_text("🔍 Searching... Please wait.")

    try:
        primary_result = None
        secondary_result = None

        # Only handle phone numbers
        if is_mobile_number(cleaned_query):
            logging.info(f"Detected mobile number: {cleaned_query}")
            primary_result = await fetch_phone_details(cleaned_query)

            # Try to extract Aadhaar from phone response and fetch additional data
            if primary_result:
                aadhaar_from_response = extract_aadhaar_from_response(primary_result)
                if aadhaar_from_response:
                    logging.info(f"Found Aadhaar in phone response: {aadhaar_from_response}")
                    secondary_result = await fetch_aadhaar_details(aadhaar_from_response)
        else:
            # If not a valid mobile number format, still try the phone API
            logging.info(f"Trying phone API for: {cleaned_query}")
            primary_result = await fetch_phone_details(cleaned_query)

        # Process results
        if primary_result or secondary_result:
            # Check if we actually have meaningful data
            formatted_response = None

            # Use secondary result if it has more comprehensive data
            if secondary_result and has_meaningful_data(secondary_result):
                formatted_response = format_combined_response(secondary_result, primary_result)
            elif primary_result and has_meaningful_data(primary_result):
                formatted_response = format_combined_response(primary_result, secondary_result)

            if formatted_response:
                user_credits[uid] -= 5
                await processing_msg.edit_text(formatted_response, parse_mode='HTML')
            else:
                await processing_msg.edit_text(
                    "❌ <b>NO RECORDS FOUND</b>\n"
                    "╔══════════════════════╗\n"
                    "┃ 🔍 No data available         ┃\n"
                    "┃ 💳 Credits not deducted      ┃\n"
                    "╚══════════════════════╝",
                    parse_mode='HTML'
                )
        else:
            await processing_msg.edit_text(
                "❌ <b>NO RECORDS FOUND</b>\n"
                "╔══════════════════════╗\n"
                "┃ 🔍 No data available         ┃\n"
                "┃ 💳 Credits not deducted      ┃\n"
                "╚══════════════════════╝",
                parse_mode='HTML'
            )

    except Exception as e:
        logging.error(f"Error processing search: {e}")
        await processing_msg.edit_text(
            "❌ Search failed. Please try again."
        )

# --- Main ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcoin", addcoin))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is starting...")
    app.run_polling()
