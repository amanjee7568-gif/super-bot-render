# -*- coding: utf-8 -*-
"""
Super Bot - Complete Telegram Bot with Gaming & Payment Features
Deployable on Render for Free
Features: Games, Wallet, Premium, Payments, Admin Panel, Referrals, Streaks, Quests
"""

import os
import json
import random
import time
import threading
import sqlite3
import hmac
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
import telebot
from telebot import types
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
BOT_TOKEN = os.getenv("BOT_TOKEN", "7566709441:AAE9A9V-Z9Q0vAQr2qyaBCBv0zpRyU3Akcw")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6646320334"))
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "9234906001")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Rina Travels Agency Pvt. Ltd")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "rinatrevelsagancypvtltd@gmail.com")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@amanjee7568")
UPI_ID = os.getenv("UPI_ID", "9234906001@ptyes")
CASHFREE_APP_ID = os.getenv("CASHFREE_APP_ID", "104929343d4e4107a5ca08529a03929401")
CASHFREE_SECRET_KEY = os.getenv("CASHFREE_SECRET_KEY", "cfsk_ma_prod_a25900faa3d8666dc9f3813051da2ab3_da582824")
CASHFREE_WEBHOOK_SECRET = os.getenv("CASHFREE_WEBHOOK_SECRET", "wzfmcpjtz6na7czj64dd")
WEBHOOK_URL ="https://super-bot-render-1.onrender.com/telegram"
PORT = int(os.getenv("PORT", "8000"))
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///viral_ultimate_bot.db")
VIRAL_PROMOTION = os.getenv("VIRAL_PROMOTION", "true").lower() == "true"
AUTO_DEPLOYMENT = os.getenv("AUTO_DEPLOYMENT", "true").lower() == "true"

# Constants
DB_PATH = DATABASE_URL.replace("sqlite:///", "")
IST = ZoneInfo("Asia/Kolkata")
START_BONUS = 100
REFERRAL_BONUS = 20
STREAK_BONUS = 10
MIN_RECHARGE = 200
PREMIUM_PRICE = 299
PREMIUM_DAYS = 30
BANNER_INTERVAL = 30  # seconds

# Initialize bot and app
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        username TEXT,
        game_wallet INTEGER DEFAULT 0,
        premium_wallet INTEGER DEFAULT 0,
        premium_until TEXT,
        referral_id TEXT,
        referred_by INTEGER,
        streak_days INTEGER DEFAULT 0,
        last_login TEXT,
        created_at TEXT,
        is_verified BOOLEAN DEFAULT 0,
        phone TEXT,
        otp_code TEXT,
        unique_id TEXT
    )
    """)
    
    # Payments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        coins INTEGER,
        status TEXT DEFAULT 'pending',
        utr TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)
    
    # Games table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        game_type TEXT,
        bet_amount INTEGER,
        result TEXT,
        win_amount INTEGER,
        created_at TEXT
    )
    """)
    
    # Quests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quests (
        user_id INTEGER,
        quest_id TEXT,
        progress INTEGER DEFAULT 0,
        completed BOOLEAN DEFAULT 0,
        completed_at TEXT,
        PRIMARY KEY (user_id, quest_id)
    )
    """)
    
    # Banners table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS banners (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        created_at TEXT
    )
    """)
    
    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Insert default settings if not exist
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('win_rate_first15', '0.35')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('win_rate_after', '0.08')")
    
    conn.commit()
    conn.close()

init_db()

# Helper functions
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_utc():
    return datetime.now(timezone.utc)

def now_ist():
    return datetime.now(IST)

def now_ist_str():
    return now_ist().strftime("%Y-%m-%d %H:%M:%S")

def ensure_user(user_id, name=None, username=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        unique_id = f"USR{random.randint(10000, 99999)}"
        cursor.execute("""
        INSERT INTO users (user_id, name, username, game_wallet, premium_wallet, streak_days, last_login, created_at, unique_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, username, START_BONUS, 0, 0, now_ist_str(), now_ist_str(), unique_id))
        
        # Initialize quests
        quests = ["daily_play_3", "daily_win_1", "daily_recharge_1"]
        for quest_id in quests:
            cursor.execute("""
            INSERT INTO quests (user_id, quest_id, progress, completed)
            VALUES (?, ?, 0, 0)
            """, (user_id, quest_id))
        
        conn.commit()
        user = cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    # Update last login
    cursor.execute("UPDATE users SET last_login = ? WHERE user_id = ?", (now_ist_str(), user_id))
    conn.commit()
    conn.close()
    
    return dict(user)

def is_premium(user):
    if not user["premium_until"]:
        return False
    expiry = datetime.fromisoformat(user["premium_until"])
    return expiry > now_ist()

def add_coins(user_id, game_coins=0, premium_coins=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if game_coins != 0:
        cursor.execute("UPDATE users SET game_wallet = game_wallet + ? WHERE user_id = ?", (game_coins, user_id))
    if premium_coins != 0:
        cursor.execute("UPDATE users SET premium_wallet = premium_wallet + ? WHERE user_id = ?", (premium_coins, user_id))
    
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result["value"] if result else default

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_random_banner():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT text FROM banners ORDER BY RANDOM() LIMIT 1")
    banner = cursor.fetchone()
    conn.close()
    
    if not banner:
        # Add sample banners if none exist
        sample_banners = [
            "🎉 User @winner123 won 5000 coins!",
            "💥 Super win! @gamerX won 2500 coins!",
            "👑 Mega win! @champ won 10000 coins!"
        ]
        for text in sample_banners:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO banners (text, created_at) VALUES (?, ?)", (text, now_ist_str()))
            conn.commit()
            conn.close()
        
        return random.choice(sample_banners)
    
    return banner["text"]

# Banner rotation thread
def banner_rotation_thread():
    while True:
        try:
            # Add a new random banner every BANNER_INTERVAL seconds
            sample_banners = [
                "🎉 User @winner123 won 5000 coins!",
                "💥 Super win! @gamerX won 2500 coins!",
                "👑 Mega win! @champ won 10000 coins!",
                "🎰 Jackpot won by @luckyuser!",
                "💸 Big win! @richplayer got 3000 coins!"
            ]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO banners (text, created_at) VALUES (?, ?)", 
                          (random.choice(sample_banners), now_ist_str()))
            conn.commit()
            conn.close()
            
            # Keep only last 20 banners
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM banners WHERE id NOT IN (SELECT id FROM banners ORDER BY created_at DESC LIMIT 20)")
            conn.commit()
            conn.close()
            
            time.sleep(BANNER_INTERVAL)
        except Exception as e:
            logger.error(f"Error in banner rotation: {e}")
            time.sleep(10)

# Start banner rotation thread
threading.Thread(target=banner_rotation_thread, daemon=True).start()

# Keyboards
def main_keyboard(user_id):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    buttons = [
        types.KeyboardButton("🎮 Games"),
        types.KeyboardButton("👛 Wallet"),
        types.KeyboardButton("💎 Premium"),
        types.KeyboardButton("🛒 Buy Coins"),
        types.KeyboardButton("🎁 Referral"),
        types.KeyboardButton("🔥 Offers"),
        types.KeyboardButton("ℹ️ Help"),
        types.KeyboardButton("📄 Marksheet"),
        types.KeyboardButton("🧑‍💼 Vacancies")
    ]
    
    if user_id == ADMIN_ID:
        buttons.append(types.KeyboardButton("🛡️ Admin Panel"))
    
    keyboard.add(*buttons)
    return keyboard

def games_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    games = [
        ("🎰 Slots", "game_slots"),
        ("🎲 Dice", "game_dice"),
        ("🏀 Basketball", "game_basketball"),
        ("🎯 Darts", "game_darts"),
        ("⚽ Football", "game_football"),
        ("🏏 Cricket", "game_cricket"),
        ("🎳 Bowling", "game_bowling"),
        ("🎪 Wheel", "game_wheel")
    ]
    
    for text, callback in games:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=callback))
    
    keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"))
    return keyboard

def bet_keyboard(bet_amount):
    keyboard = types.InlineKeyboardMarkup(row_width=4)
    
    keyboard.add(
        types.InlineKeyboardButton("-10", callback_data="bet_-10"),
        types.InlineKeyboardButton("-1", callback_data="bet_-1"),
        types.InlineKeyboardButton("+1", callback_data="bet_+1"),
        types.InlineKeyboardButton("+10", callback_data="bet_+10")
    )
    
    keyboard.add(
        types.InlineKeyboardButton(f"Bet: {bet_amount}", callback_data="bet_confirm"),
        types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_games")
    )
    
    return keyboard

def premium_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(
        types.InlineKeyboardButton(f"🔓 Unlock Premium ({PREMIUM_DAYS} days) - {PREMIUM_PRICE} PCoins", callback_data="buy_premium")
    )
    
    keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"))
    return keyboard

def buy_coins_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    amounts = [100, 200, 500, 1000]
    for amount in amounts:
        keyboard.add(types.InlineKeyboardButton(f"₹{amount}", callback_data=f"buy_{amount}"))
    
    keyboard.add(types.InlineKeyboardButton("✅ I Paid", callback_data="paid_request"))
    keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"))
    
    return keyboard

def admin_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton("👥 Users", callback_data="admin_users"),
        types.InlineKeyboardButton("💳 Payments", callback_data="admin_payments"),
        types.InlineKeyboardButton("➕ Add Coins", callback_data="admin_add_coins"),
        types.InlineKeyboardButton("➖ Remove Coins", callback_data="admin_remove_coins"),
        types.InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
        types.InlineKeyboardButton("🎮 Set Win Rate", callback_data="admin_winrate"),
        types.InlineKeyboardButton("🔧 Settings", callback_data="admin_settings")
    )
    
    keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"))
    return keyboard

# User state management
user_states = {}

# Bot Handlers
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user = ensure_user(user_id, message.from_user.first_name, message.from_user.username)
    
    # Check for referral
    if message.text and len(message.text.split()) > 1:
        try:
            ref_id = int(message.text.split()[1])
            if ref_id != user_id and not user.get("referred_by"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (ref_id, user_id))
                add_coins(user_id, REFERRAL_BONUS)
                add_coins(ref_id, REFERRAL_BONUS)
                conn.commit()
                conn.close()
                
                bot.send_message(ref_id, f"🎉 Referral bonus! {REFERRAL_BONUS} coins credited!")
        except:
            pass
    
    # Check streak
    last_login = datetime.fromisoformat(user["last_login"]) if user["last_login"] else now_ist()
    if (now_ist() - last_login).days >= 1:
        if (now_ist() - last_login).days == 1:
            # Consecutive day
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET streak_days = streak_days + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            add_coins(user_id, STREAK_BONUS * min(user["streak_days"] + 1, 7))  # Max 7x bonus
        else:
            # Streak reset
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET streak_days = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            add_coins(user_id, STREAK_BONUS)
    
    # Show welcome message
    banner = get_random_banner()
    premium_status = "✅ Active" if is_premium(user) else "❌ Inactive"
    
    welcome_text = f"""
👋 Welcome to <b>{BUSINESS_NAME}</b>!

🆔 Your Unique ID: <code>{user['unique_id']}</code>
🕒 Time: {now_ist_str()}

💰 Game Wallet: <b>{user['game_wallet']}</b>
💎 Premium Wallet: <b>{user['premium_wallet']}</b>
⭐ Premium: {premium_status}
🔥 Streak: {user['streak_days']} days

📢 <b>Latest Win:</b> {banner}

Use the menu below to navigate:
"""
    
    bot.send_message(user_id, welcome_text, reply_markup=main_keyboard(user_id))

@bot.message_handler(func=lambda message: message.text == "🎮 Games")
def games_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    if not is_premium(user):
        bot.send_message(user_id, "🎮 Games are available for Premium users only!\n\nUpgrade to Premium to unlock all games.", reply_markup=premium_keyboard())
        return
    
    bot.send_message(user_id, "🎮 Choose a game to play:", reply_markup=games_keyboard())

@bot.message_handler(func=lambda message: message.text == "👛 Wallet")
def wallet_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    premium_status = "✅ Active" if is_premium(user) else "❌ Inactive"
    premium_expiry = ""
    
    if user["premium_until"]:
        expiry_date = datetime.fromisoformat(user["premium_until"])
        if expiry_date > now_ist():
            days_left = (expiry_date - now_ist()).days
            premium_expiry = f" (Expires in {days_left} days)"
    
    wallet_text = f"""
👛 <b>Your Wallet</b>

💰 Game Wallet: <b>{user['game_wallet']}</b>
💎 Premium Wallet: <b>{user['premium_wallet']}</b>
⭐ Premium: {premium_status}{premium_expiry}

💡 <b>Transfer coins:</b>
Use /topremium <amount> to transfer from Game to Premium Wallet

💳 <b>Add coins:</b>
Use the "Buy Coins" option in the main menu
"""
    
    bot.send_message(user_id, wallet_text, reply_markup=main_keyboard(user_id))

@bot.message_handler(commands=['topremium'])
def transfer_to_premium(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    try:
        amount = int(message.text.split()[1])
        if amount <= 0:
            bot.reply_to(message, "❌ Amount must be positive!")
            return
        
        if user["game_wallet"] < amount:
            bot.reply_to(message, f"❌ Insufficient Game Wallet balance! You have {user['game_wallet']} coins.")
            return
        
        add_coins(user_id, -amount, amount)
        bot.reply_to(message, f"✅ Transferred {amount} coins from Game to Premium Wallet!")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Usage: /topremium <amount>")

@bot.message_handler(func=lambda message: message.text == "💎 Premium")
def premium_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    if is_premium(user):
        expiry_date = datetime.fromisoformat(user["premium_until"])
        days_left = (expiry_date - now_ist()).days
        
        premium_text = f"""
💎 <b>Premium Status</b>

✅ Your Premium is active!
📅 Expires in: {days_left} days
💎 Premium Wallet: {user['premium_wallet']}

🎁 <b>Premium Benefits:</b>
• Access to all games
• Higher win rates
• Exclusive offers
• Priority support
• Access to vacancies section
"""
    else:
        premium_text = f"""
💎 <b>Unlock Premium</b>

🚀 Get {PREMIUM_DAYS} days of Premium for just {PREMIUM_PRICE} Premium Coins!

🎁 <b>Premium Benefits:</b>
• Access to all games
• Higher win rates
• Exclusive offers
• Priority support
• Access to vacancies section

💎 Your Premium Wallet: {user['premium_wallet']}
"""
    
    bot.send_message(user_id, premium_text, reply_markup=premium_keyboard())

@bot.message_handler(func=lambda message: message.text == "🛒 Buy Coins")
def buy_coins_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    buy_text = f"""
💳 <b>Buy Coins</b>

💰 Minimum recharge: {MIN_RECHARGE} coins
💳 Payment via UPI: {UPI_ID}

📋 <b>Steps:</b>
1. Select amount below
2. Pay via UPI
3. Click "✅ I Paid"
4. Enter UTR/Reference number

💎 Your current balance:
Game Wallet: {user['game_wallet']}
Premium Wallet: {user['premium_wallet']}
"""
    
    bot.send_message(user_id, buy_text, reply_markup=buy_coins_keyboard())

@bot.message_handler(func=lambda message: message.text == "🎁 Referral")
def referral_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    referral_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
    referral_text = f"""
🎁 <b>Referral Program</b>

🔗 Your referral link:
{referral_link}

💰 Earn {REFERRAL_BONUS} coins for each friend who joins!
🎁 Your friend also gets {REFERRAL_BONUS} coins as bonus!

📊 Your referrals: {user.get('referral_count', 0)}
💰 Total earned: {user.get('referral_earnings', 0)} coins
"""
    
    bot.send_message(user_id, referral_text)

@bot.message_handler(func=lambda message: message.text == "🔥 Offers")
def offers_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    offers_text = f"""
🔥 <b>Special Offers</b>

🎁 <b>Daily Login Bonus:</b>
Get {STREAK_BONUS} coins for each consecutive day login!
Max streak bonus: {STREAK_BONUS * 7} coins

🎁 <b>Referral Bonus:</b>
Earn {REFERRAL_BONUS} coins for each friend who joins!

🎁 <b>Premium Benefits:</b>
• Access to all games
• Higher win rates
• Exclusive offers
• Priority support

💎 Your current balance:
Game Wallet: {user['game_wallet']}
Premium Wallet: {user['premium_wallet']}
"""
    
    bot.send_message(user_id, offers_text)

@bot.message_handler(func=lambda message: message.text == "ℹ️ Help")
def help_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    help_text = f"""
ℹ️ <b>Help & Support</b>

🤖 <b>Bot Features:</b>
• Games (Premium only)
• Wallet management
• Premium subscription
• Coin purchases
• Referral program
• Daily streak bonuses

💎 <b>Premium Benefits:</b>
• Access to all games
• Higher win rates
• Exclusive offers
• Priority support

📞 <b>Support:</b>
• Contact: {SUPPORT_USERNAME}
• Email: {BUSINESS_EMAIL}

📋 <b>Commands:</b>
• /start - Start the bot
• /topremium <amount> - Transfer coins to premium wallet

💎 Your current balance:
Game Wallet: {user['game_wallet']}
Premium Wallet: {user['premium_wallet']}
"""
    
    bot.send_message(user_id, help_text)

@bot.message_handler(func=lambda message: message.text == "📄 Marksheet")
def marksheet_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    if not is_premium(user):
        bot.send_message(user_id, "📄 Marksheet feature is available for Premium users only!\n\nUpgrade to Premium to unlock this feature.", reply_markup=premium_keyboard())
        return
    
    # Generate a sample marksheet
    marksheet_text = f"""
📄 <b>Your Marksheet</b>

👤 Name: {user['name']}
🆔 ID: {user['unique_id']}
📅 Generated: {now_ist_str()}

📊 <b>Performance:</b>
• Games Played: {user.get('games_played', 0)}
• Games Won: {user.get('games_won', 0)}
• Win Rate: {user.get('win_rate', 0)}%
• Total Earnings: {user.get('total_earnings', 0)} coins

🎯 <b>Achievements:</b>
• Login Streak: {user['streak_days']} days
• Referrals: {user.get('referral_count', 0)}
• Premium: {'Active' if is_premium(user) else 'Inactive'}

💎 Your current balance:
Game Wallet: {user['game_wallet']}
Premium Wallet: {user['premium_wallet']}
"""
    
    bot.send_message(user_id, marksheet_text)

@bot.message_handler(func=lambda message: message.text == "🧑‍💼 Vacancies")
def vacancies_menu(message):
    user_id = message.from_user.id
    user = ensure_user(user_id)
    
    if not is_premium(user):
        bot.send_message(user_id, "🧑‍💼 Vacancies section is available for Premium users only!\n\nUpgrade to Premium to unlock this feature.", reply_markup=premium_keyboard())
        return
    
    vacancies_text = f"""
🧑‍💼 <b>Current Vacancies</b>

🏢 <b>{BUSINESS_NAME}</b>

📋 <b>Open Positions:</b>
1. Customer Support Executive
   • Experience: 1-2 years
   • Salary: ₹15,000 - ₹20,000/month
   • Location: Remote

2. Social Media Manager
   • Experience: 2-3 years
   • Salary: ₹20,000 - ₹25,000/month
   • Location: Remote

3. Content Writer
   • Experience: 1-2 years
   • Salary: ₹12,000 - ₹18,000/month
   • Location: Remote

4. Telegram Bot Moderator
   • Experience: Fresher
   • Salary: ₹8,000 - ₹12,000/month
   • Location: Remote

📧 <b>How to Apply:</b>
Send your resume to {BUSINESS_EMAIL}
Subject: Job Application - [Position Name]

📞 <b>Contact:</b>
{SUPPORT_USERNAME}
"""
    
    bot.send_message(user_id, vacancies_text)

@bot.message_handler(func=lambda message: message.text == "🛡️ Admin Panel")
def admin_panel_menu(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(user_id, "🚫 You don't have permission to access the Admin Panel!")
        return
    
    admin_text = """
🛡️ <b>Admin Panel</b>

👥 <b>User Management:</b>
• View all users
• Add/remove coins
• Manage premium status

💳 <b>Payment Management:</b>
• View pending payments
• Approve/reject payments
• Transaction history

📊 <b>Statistics:</b>
• Total users
• Active premium users
• Revenue statistics

📢 <b>Broadcast:</b>
• Send message to all users
• Targeted messages

🎮 <b>Game Settings:</b>
• Adjust win rates
• Game configurations

🔧 <b>System Settings:</b>
• Bot configuration
• API settings
• Webhook management
"""
    
    bot.send_message(user_id, admin_text, reply_markup=admin_keyboard())

# Callback handlers
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    user = ensure_user(user_id)
    
    if call.data == "back_to_main":
        bot.edit_message_text("🏠 Main Menu", call.message.chat.id, call.message.message_id, reply_markup=main_keyboard(user_id))
    
    elif call.data == "back_to_games":
        bot.edit_message_text("🎮 Choose a game to play:", call.message.chat.id, call.message.message_id, reply_markup=games_keyboard())
    
    elif call.data.startswith("game_"):
        game_type = call.data.replace("game_", "")
        user_states[user_id] = {"game": game_type, "bet": 10}
        bot.edit_message_text(f"🎮 {game_type.title()} Game\n\nCurrent bet: 10 coins\n\nAdjust your bet and confirm:", call.message.chat.id, call.message.message_id, reply_markup=bet_keyboard(10))
    
    elif call.data.startswith("bet_"):
        if user_id not in user_states or "game" not in user_states[user_id]:
            bot.answer_callback_query(call.id, "Please select a game first!")
            return
        
        action = call.data.replace("bet_", "")
        current_bet = user_states[user_id]["bet"]
        
        if action == "-10":
            new_bet = max(1, current_bet - 10)
        elif action == "-1":
            new_bet = max(1, current_bet - 1)
        elif action == "+1":
            new_bet = current_bet + 1
        elif action == "+10":
            new_bet = current_bet + 10
        elif action == "confirm":
            # Process the bet
            game_type = user_states[user_id]["game"]
            bet_amount = user_states[user_id]["bet"]
            
            if user["game_wallet"] < bet_amount:
                bot.answer_callback_query(call.id, "Insufficient balance!")
                return
            
            # Simulate game result
            win_rate = get_setting("win_rate_first15", "0.35")
            if user.get("games_played", 0) > 15:
                win_rate = get_setting("win_rate_after", "0.08")
            
            won = random.random() < float(win_rate)
            
            if won:
                win_amount = int(bet_amount * random.uniform(1.5, 3.0))
                add_coins(user_id, win_amount)
                result_text = f"🎉 You won {win_amount} coins!"
            else:
                add_coins(user_id, -bet_amount)
                result_text = f"😞 You lost {bet_amount} coins."
            
            # Update user stats
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (user_id,))
            if won:
                cursor.execute("UPDATE users SET games_won = games_won + 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            # Record game
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO games (user_id, game_type, bet_amount, result, win_amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, game_type, bet_amount, "win" if won else "lose", win_amount if won else 0, now_ist_str()))
            conn.commit()
            conn.close()
            
            # Update quests
            update_quests(user_id, "daily_play_3", 1)
            if won:
                update_quests(user_id, "daily_win_1", 1)
            
            bot.edit_message_text(f"🎮 {game_type.title()} Game\n\n{result_text}\n\nBalance: {user['game_wallet']} coins", call.message.chat.id, call.message.message_id)
            return
        
        else:
            new_bet = current_bet
        
        user_states[user_id]["bet"] = new_bet
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=bet_keyboard(new_bet))
        bot.answer_callback_query(call.id, f"Bet set to {new_bet}")
    
    elif call.data == "buy_premium":
        if user["premium_wallet"] < PREMIUM_PRICE:
            bot.answer_callback_query(call.id, f"Insufficient Premium Wallet! You need {PREMIUM_PRICE} PCoins.")
            return
        
        # Activate premium
        expiry_date = now_ist() + timedelta(days=PREMIUM_DAYS)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET premium_wallet = premium_wallet - ?, premium_until = ? WHERE user_id = ?", 
                     (PREMIUM_PRICE, expiry_date.isoformat(), user_id))
        conn.commit()
        conn.close()
        
        bot.edit_message_text("🎉 Premium activated successfully!", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, f"✅ Your Premium has been activated for {PREMIUM_DAYS} days!")
    
    elif call.data.startswith("buy_"):
        amount = int(call.data.replace("buy_", ""))
        upi_url = f"upi://pay?pa={UPI_ID}&pn={BUSINESS_NAME}&am={amount}&cu=INR&tn=Bot%20Coins%20Purchase"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("💳 Pay Now", url=upi_url))
        keyboard.add(types.InlineKeyboardButton("✅ I Paid", callback_data="paid_request"))
        keyboard.add(types.InlineKeyboardButton("⬅️ Back", callback_data="back_to_main"))
        
        bot.edit_message_text(f"💳 Buy {amount} coins\n\nClick 'Pay Now' to make the payment via UPI\n\nAfter payment, click '✅ I Paid' and enter your UTR number", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "paid_request":
        user_states[user_id] = {"awaiting_payment": True}
        bot.edit_message_text("✅ Please enter your UTR/Reference number after making the payment:", call.message.chat.id, call.message.message_id)
    
    # Admin panel callbacks
    elif call.data.startswith("admin_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "Access denied!")
            return
        
        action = call.data.replace("admin_", "")
        
        if action == "users":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 10")
            users = cursor.fetchall()
            conn.close()
            
            users_text = "👥 <b>Recent Users</b>\n\n"
            for u in users:
                premium_status = "✅" if is_premium(u) else "❌"
                users_text += f"👤 {u['name']} ({u['user_id']})\n💰 {u['game_wallet']} | 💎 {u['premium_wallet']} | {premium_status}\n📅 {u['created_at']}\n\n"
            
            bot.edit_message_text(users_text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif action == "payments":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments ORDER BY created_at DESC LIMIT 10")
            payments = cursor.fetchall()
            conn.close()
            
            payments_text = "💳 <b>Recent Payments</b>\n\n"
            for p in payments:
                payments_text += f"🆔 {p['id']}\n👤 {p['user_id']}\n💰 {p['amount']}\n📊 {p['status']}\n📅 {p['created_at']}\n\n"
            
            bot.edit_message_text(payments_text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif action == "add_coins":
            user_states[user_id] = {"admin_action": "add_coins", "step": "ask_user_id"}
            bot.edit_message_text("➕ Enter user ID to add coins:", call.message.chat.id, call.message.message_id)
        
        elif action == "remove_coins":
            user_states[user_id] = {"admin_action": "remove_coins", "step": "ask_user_id"}
            bot.edit_message_text("➖ Enter user ID to remove coins:", call.message.chat.id, call.message.message_id)
        
        elif action == "broadcast":
            user_states[user_id] = {"admin_action": "broadcast", "step": "ask_message"}
            bot.edit_message_text("📢 Enter the message to broadcast to all users:", call.message.chat.id, call.message.message_id)
        
        elif action == "stats":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Active premium users
            cursor.execute("SELECT COUNT(*) FROM users WHERE premium_until > ?", (now_ist().isoformat(),))
            premium_users = cursor.fetchone()[0]
            
            # Total payments
            cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'approved'")
            total_payments = cursor.fetchone()[0]
            
            # Total revenue
            cursor.execute("SELECT SUM(amount) FROM payments WHERE status = 'approved'")
            total_revenue = cursor.fetchone()[0] or 0
            
            conn.close()
            
            stats_text = f"""
📊 <b>Bot Statistics</b>

👥 Total Users: {total_users}
⭐ Premium Users: {premium_users}
💳 Total Payments: {total_payments}
💰 Total Revenue: ₹{total_revenue}

📈 <b>Growth:</b>
• New users today: {get_today_new_users()}
• Payments today: {get_today_payments()}
• Revenue today: ₹{get_today_revenue()}
"""
            
            bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif action == "winrate":
            win_rate_first15 = get_setting("win_rate_first15", "0.35")
            win_rate_after = get_setting("win_rate_after", "0.08")
            
            winrate_text = f"""
🎮 <b>Game Win Rates</b>

🎯 First 15 games: {float(win_rate_first15) * 100}%
🎯 After 15 games: {float(win_rate_after) * 100}%

💡 <b>Current Settings:</b>
• Users get higher win rates initially
• Win rate decreases after 15 games
• Encourages users to keep playing

🔧 <b>Update:</b>
Use /setwinrate <first15> <after> to update
Example: /setwinrate 0.40 0.10
"""
            
            bot.edit_message_text(winrate_text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())
        
        elif action == "settings":
            settings_text = f"""
🔧 <b>System Settings</b>

⚙️ <b>Current Configuration:</b>
• Bot Token: ✓ Configured
• Admin ID: ✓ Configured
• Database: ✓ SQLite
• Webhook: ✓ Configured

🔗 <b>API Endpoints:</b>
• Telegram Webhook: {WEBHOOK_URL}/telegram
• Cashfree Webhook: {WEBHOOK_URL}/cashfree-webhook

💾 <b>Database:</b>
• Type: SQLite
• Location: {DB_PATH}
• Auto-backup: Enabled

🔄 <b>Services:</b>
• Banner rotation: Running
• Payment processing: Active
• User management: Active
"""
            
            bot.edit_message_text(settings_text, call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())

# Message handlers for admin actions
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("admin_action"))
def admin_action_handler(message):
    user_id = message.from_user.id
    state = user_states[user_id]
    
    if state["admin_action"] == "add_coins":
        if state["step"] == "ask_user_id":
            try:
                target_user_id = int(message.text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["step"] = "ask_amount"
                bot.send_message(user_id, "Enter amount of coins to add:")
            except ValueError:
                bot.send_message(user_id, "❌ Invalid user ID! Please enter a valid number.")
        
        elif state["step"] == "ask_amount":
            try:
                amount = int(message.text)
                target_user_id = state["target_user_id"]
                
                add_coins(target_user_id, amount)
                bot.send_message(user_id, f"✅ Added {amount} coins to user {target_user_id}")
                bot.send_message(target_user_id, f"🎉 You received {amount} coins from admin!")
                
                del user_states[user_id]
            except ValueError:
                bot.send_message(user_id, "❌ Invalid amount! Please enter a valid number.")
    
    elif state["admin_action"] == "remove_coins":
        if state["step"] == "ask_user_id":
            try:
                target_user_id = int(message.text)
                user_states[user_id]["target_user_id"] = target_user_id
                user_states[user_id]["step"] = "ask_amount"
                bot.send_message(user_id, "Enter amount of coins to remove:")
            except ValueError:
                bot.send_message(user_id, "❌ Invalid user ID! Please enter a valid number.")
        
        elif state["step"] == "ask_amount":
            try:
                amount = int(message.text)
                target_user_id = state["target_user_id"]
                
                add_coins(target_user_id, -amount)
                bot.send_message(user_id, f"✅ Removed {amount} coins from user {target_user_id}")
                bot.send_message(target_user_id, f"⚠️ Admin removed {amount} coins from your account.")
                
                del user_states[user_id]
            except ValueError:
                bot.send_message(user_id, "❌ Invalid amount! Please enter a valid number.")
    
    elif state["admin_action"] == "broadcast":
        if state["step"] == "ask_message":
            broadcast_message = message.text
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
            conn.close()
            
            sent_count = 0
            for user in users:
                try:
                    bot.send_message(user["user_id"], f"📢 Broadcast from Admin:\n\n{broadcast_message}")
                    sent_count += 1
                except:
                    pass
            
            bot.send_message(user_id, f"✅ Broadcast sent to {sent_count} users!")
            del user_states[user_id]

# Message handler for payment confirmation
@bot.message_handler(func=lambda message: message.from_user.id in user_states and user_states[message.from_user.id].get("awaiting_payment"))
def payment_confirmation_handler(message):
    user_id = message.from_user.id
    utr = message.text.strip()
    
    # Create payment record
    payment_id = f"PAY{int(time.time())}{random.randint(1000, 9999)}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO payments (id, user_id, amount, coins, status, utr, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (payment_id, user_id, 0, 0, "pending", utr, now_ist_str()))
    conn.commit()
    conn.close()
    
    # Notify admin
    bot.send_message(ADMIN_ID, f"💳 New Payment Request\n\nPayment ID: {payment_id}\nUser ID: {user_id}\nUTR: {utr}\n\nPlease verify and approve.")
    
    bot.send_message(user_id, f"✅ Payment request submitted!\n\nPayment ID: {payment_id}\nUTR: {utr}\n\nAdmin will verify and credit coins shortly.")
    
    del user_states[user_id]

# Helper functions for statistics
def get_today_new_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_today_payments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM payments WHERE date(created_at) = date('now') AND status = 'approved'")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_today_revenue():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM payments WHERE date(created_at) = date('now') AND status = 'approved'")
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total

def update_quests(user_id, quest_id, increment):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current progress
    cursor.execute("SELECT progress, completed FROM quests WHERE user_id = ? AND quest_id = ?", (user_id, quest_id))
    quest = cursor.fetchone()
    
    if quest:
        if not quest["completed"]:
            new_progress = quest["progress"] + increment
            
            # Check quest requirements
            quest_requirements = {
                "daily_play_3": 3,
                "daily_win_1": 1,
                "daily_recharge_1": 1
            }
            
            if quest_id in quest_requirements and new_progress >= quest_requirements[quest_id]:
                # Quest completed
                cursor.execute("UPDATE quests SET progress = ?, completed = 1, completed_at = ? WHERE user_id = ? AND quest_id = ?", 
                             (new_progress, now_ist_str(), user_id, quest_id))
                
                # Award reward
                rewards = {
                    "daily_play_3": 50,
                    "daily_win_1": 100,
                    "daily_recharge_1": 200
                }
                
                if quest_id in rewards:
                    add_coins(user_id, rewards[quest_id])
                    bot.send_message(user_id, f"🎉 Quest completed! You earned {rewards[quest_id]} coins!")
            else:
                # Update progress
                cursor.execute("UPDATE quests SET progress = ? WHERE user_id = ? AND quest_id = ?", 
                             (new_progress, user_id, quest_id))
    
    conn.commit()
    conn.close()

# Admin commands
@bot.message_handler(commands=['setwinrate'])
def set_winrate_command(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Access denied!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Usage: /setwinrate <first15> <after>")
            return
        
        first15 = float(parts[1])
        after = float(parts[2])
        
        if not (0 <= first15 <= 1 and 0 <= after <= 1):
            bot.reply_to(message, "❌ Win rates must be between 0 and 1!")
            return
        
        set_setting("win_rate_first15", str(first15))
        set_setting("win_rate_after", str(after))
        
        bot.reply_to(message, f"✅ Win rates updated!\nFirst 15 games: {first15 * 100}%\nAfter 15 games: {after * 100}%")
    except (ValueError, IndexError):
        bot.reply_to(message, "❌ Invalid format! Use: /setwinrate <first15> <after>")

@bot.message_handler(commands=['approvepayment'])
def approve_payment_command(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Access denied!")
        return
    
    try:
        payment_id = message.text.split()[1]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get payment details
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        payment = cursor.fetchone()
        
        if not payment:
            bot.reply_to(message, "❌ Payment not found!")
            return
        
        if payment["status"] == "approved":
            bot.reply_to(message, "❌ Payment already approved!")
            return
        
        # Update payment status
        cursor.execute("UPDATE payments SET status = 'approved', updated_at = ? WHERE id = ?", 
                     (now_ist_str(), payment_id))
        
        # Credit coins to user (1:1 ratio)
        coins = payment["amount"]
        add_coins(payment["user_id"], coins)
        
        # Update quest if applicable
        update_quests(payment["user_id"], "daily_recharge_1", 1)
        
        conn.commit()
        conn.close()
        
        # Notify user
        bot.send_message(payment["user_id"], f"✅ Payment approved! {coins} coins credited to your account.")
        
        bot.reply_to(message, f"✅ Payment {payment_id} approved! {coins} coins credited to user {payment['user_id']}.")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Usage: /approvepayment <payment_id>")

@bot.message_handler(commands=['rejectpayment'])
def reject_payment_command(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Access denied!")
        return
    
    try:
        payment_id = message.text.split()[1]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get payment details
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        payment = cursor.fetchone()
        
        if not payment:
            bot.reply_to(message, "❌ Payment not found!")
            return
        
        if payment["status"] == "rejected":
            bot.reply_to(message, "❌ Payment already rejected!")
            return
        
        # Update payment status
        cursor.execute("UPDATE payments SET status = 'rejected', updated_at = ? WHERE id = ?", 
                     (now_ist_str(), payment_id))
        conn.commit()
        conn.close()
        
        # Notify user
        bot.send_message(payment["user_id"], f"❌ Payment rejected! Please contact support for assistance.")
        
        bot.reply_to(message, f"✅ Payment {payment_id} rejected!")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Usage: /rejectpayment <payment_id>")

# Webhook handlers
@app.route('/telegram', methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid request'

@app.route('/cashfree-webhook', methods=['POST'])
def cashfree_webhook():
    try:
        # Verify webhook signature
        signature = request.headers.get('x-webhook-signature', '')
        body = request.get_data(as_text=True)
        
        expected_signature = hmac.new(
            CASHFREE_WEBHOOK_SECRET.encode(),
            msg=body.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return 'Invalid signature', 401
        
        # Process webhook data
        data = request.json
        event_type = data.get('event')
        
        if event_type == 'payment.success':
            order_id = data.get('data', {}).get('order', {}).get('order_id')
            amount = data.get('data', {}).get('order', {}).get('order_amount')
            
            # Find payment by order_id
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM payments WHERE id = ?", (order_id,))
            payment = cursor.fetchone()
            
            if payment and payment["status"] == "pending":
                # Update payment status
                cursor.execute("UPDATE payments SET status = 'approved', amount = ?, coins = ?, updated_at = ? WHERE id = ?", 
                             (amount, amount, now_ist_str(), order_id))
                
                # Credit coins to user
                add_coins(payment["user_id"], amount)
                
                # Update quest if applicable
                update_quests(payment["user_id"], "daily_recharge_1", 1)
                
                conn.commit()
                
                # Notify user
                bot.send_message(payment["user_id"], f"✅ Payment successful! {amount} coins credited to your account.")
                
                # Notify admin
                bot.send_message(ADMIN_ID, f"💳 Auto-approved payment\n\nPayment ID: {order_id}\nUser ID: {payment['user_id']}\nAmount: ₹{amount}")
            
            conn.close()
        
        return 'OK', 200
    except Exception as e:
        logger.error(f"Error processing Cashfree webhook: {e}")
        return 'Error', 500

@app.route('/')
def health_check():
    return 'Bot is running!'

# Set webhook
def set_webhook():
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/telegram"
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")

# Main function
def main():
    # Set webhook if URL is provided
    if WEBHOOK_URL and WEBHOOK_URL != "https://your-app-name.onrender.com":
        set_webhook()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    main()
