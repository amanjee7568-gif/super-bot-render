# server.py
import os
import telebot
from flask import Flask, request

# ==========================
# CONFIG
# ==========================
TOKEN = os.getenv("BOT_TOKEN", "PUT-YOUR-TELEGRAM-BOT-TOKEN-HERE")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Dummy user wallets (production में DB use कर लेना)
user_wallets = {}   # {user_id: {"game": int, "premium": int}}

# ==========================
# COMMAND HANDLERS
# ==========================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    if user_id not in user_wallets:
        user_wallets[user_id] = {"game": 100, "premium": 0}  # default coins
    
    text = (
        f"🚀 Welcome {message.from_user.first_name}!\n\n"
        f"🪙 Game Wallet: {user_wallets[user_id]['game']} coins\n"
        f"💎 Premium Wallet: {user_wallets[user_id]['premium']} coins\n\n"
        f"👉 Use /wallet to check balance\n"
        f"👉 Use /bet to place a bet\n"
        f"👉 Use /pay to add balance\n"
        f"👉 Use /help for assistance"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['wallet'])
def wallet(message):
    user_id = message.chat.id
    if user_id not in user_wallets:
        user_wallets[user_id] = {"game": 100, "premium": 0}
    bal = user_wallets[user_id]
    bot.reply_to(message, f"🪙 Game Wallet: {bal['game']} coins\n💎 Premium Wallet: {bal['premium']} coins")

@bot.message_handler(commands=['bet'])
def bet(message):
    user_id = message.chat.id
    if user_id not in user_wallets:
        user_wallets[user_id] = {"game": 100, "premium": 0}
    
    text = (
        "🎲 Place your bet!\n"
        "Send in this format:\n"
        "`/bet <amount> <odds>`\n\n"
        "Example: `/bet 50 2` → Bet 50 coins at 2x odds"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("/bet "))
def bet_custom(message):
    try:
        user_id = message.chat.id
        _, amt, odds = message.text.split()
        amt, odds = int(amt), float(odds)

        if user_id not in user_wallets:
            user_wallets[user_id] = {"game": 100, "premium": 0}

        if user_wallets[user_id]["game"] < amt:
            bot.reply_to(message, "❌ Not enough balance in Game Wallet.")
            return

        # deduct first
        user_wallets[user_id]["game"] -= amt

        import random
        if random.choice([True, False]):  # win
            win_amt = int(amt * odds)
            user_wallets[user_id]["game"] += win_amt
            bot.reply_to(message, f"🎉 You won! You got {win_amt} coins.\nNew Balance: {user_wallets[user_id]['game']}")
        else:  # lose
            bot.reply_to(message, f"😢 You lost {amt} coins.\nNew Balance: {user_wallets[user_id]['game']}")

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error in bet format. Use `/bet 50 2`")

@bot.message_handler(commands=['pay'])
def pay(message):
    text = (
        "💳 Payment Options:\n\n"
        "100₹ → [Click Here](https://payments.cashfree.com/links?code=r9179auduhe0)\n"
        "200₹ → [Click Here](https://payments.cashfree.com/links?code=i917ad964he0)\n"
        "300₹ → [Click Here](https://payments.cashfree.com/links?code=u917aj2p65s0)\n\n"
        "After payment, send screenshot to Admin."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.chat.id
    if user_id in user_wallets and user_wallets[user_id]["premium"] > 0:
        bot.reply_to(message, "💎 Premium Helpdesk:\nYou can contact admin directly for VIP support.")
    else:
        bot.reply_to(message, "ℹ️ This service is for Premium users only. Upgrade via /pay to unlock full features.")

# ==========================
# FLASK WEBHOOK SETUP
# ==========================
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def home():
    return "Bot is running!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
