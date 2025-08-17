# -*- coding: utf-8 -*-
import os
import random
import logging
from flask import Flask, request
import telebot

# ================= CONFIG =================
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"   # यहां अपना बॉट टोकन भरो
ADMIN_ID = 123456789                # यहां अपना Telegram ID भरो

PAYMENT_LINKS = {
    "100₹": "https://payments.cashfree.com/links?code=r9179auduhe0",
    "200₹": "https://payments.cashfree.com/links?code=i917ad964he0",
    "300₹": "https://payments.cashfree.com/links?code=u917aj2p65s0",
}

# Odds (default: 50/50)
GAME_ODDS = {"win": 50, "lose": 50}

# Data Store
USERS = {}

# Flask App
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)


# ================= HELPERS =================
def get_user(user_id, name="Guest"):
    if user_id not in USERS:
        USERS[user_id] = {
            "name": name,
            "game_wallet": 100,
            "premium_wallet": 0,
            "premium": False,
        }
    return USERS[user_id]


def make_keyboard(options):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup()
    for opt in options:
        kb.add(InlineKeyboardButton(opt, callback_data=opt))
    return kb


# ================= BOT COMMANDS =================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    user = get_user(message.chat.id, message.from_user.first_name)
    text = f"""
👋 Welcome {user['name']}!

🆔 ID: {message.chat.id}
💰 Game Wallet: {user['game_wallet']} coins
💎 Premium Wallet: {user['premium_wallet']} coins
"""
    kb = make_keyboard(["🎮 Games", "💰 Wallet", "⭐ Premium", "📢 Help"])
    bot.send_message(message.chat.id, text, reply_markup=kb)


@bot.message_handler(commands=["setodds"])
def set_odds(message):
    if message.chat.id != ADMIN_ID:
        return bot.reply_to(message, "⛔ You are not admin!")
    try:
        _, win, lose = message.text.split()
        GAME_ODDS["win"] = int(win)
        GAME_ODDS["lose"] = int(lose)
        bot.reply_to(message, f"✅ Odds updated: Win {win}% | Lose {lose}%")
    except:
        bot.reply_to(message, "❌ Usage: /setodds <win%> <lose%>")


@bot.message_handler(commands=["addcoins"])
def add_coins(message):
    if message.chat.id != ADMIN_ID:
        return
    try:
        _, uid, amount = message.text.split()
        uid, amount = int(uid), int(amount)
        USERS[uid]["game_wallet"] += amount
        bot.send_message(uid, f"💰 {amount} coins added by Admin!")
    except:
        bot.reply_to(message, "❌ Usage: /addcoins <id> <amount>")


# ================= CALLBACKS =================
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user = get_user(call.message.chat.id, call.from_user.first_name)

    if call.data == "🎮 Games":
        kb = make_keyboard(["🎲 Dice", "🃏 Cards", "🎡 Spin", "🏏 Cricket"])
        bot.edit_message_text("Choose a game:", call.message.chat.id, call.message.id, reply_markup=kb)

    elif call.data in ["🎲 Dice", "🃏 Cards", "🎡 Spin", "🏏 Cricket"]:
        kb = make_keyboard(["100", "200", "500"])
        bot.edit_message_text(f"{call.data} selected 🎮\nChoose bet amount:", call.message.chat.id, call.message.id, reply_markup=kb)

    elif call.data.isdigit():
        amount = int(call.data)
        if user["game_wallet"] < amount:
            return bot.answer_callback_query(call.id, "Not enough balance!", show_alert=True)

        user["game_wallet"] -= amount
        result = "Win" if random.randint(1, 100) <= GAME_ODDS["win"] else "Lose"
        if result == "Win":
            user["game_wallet"] += amount * 2

        bot.send_message(call.message.chat.id, f"🎲 Result: {result}\n💰 Balance: {user['game_wallet']}")

    elif call.data == "💰 Wallet":
        kb = make_keyboard(["Transfer to Premium", "Buy Premium Coins"])
        bot.edit_message_text("Wallet Options:", call.message.chat.id, call.message.id, reply_markup=kb)

    elif call.data == "Buy Premium Coins":
        links = "\n".join([f"{k}: {v}" for k, v in PAYMENT_LINKS.items()])
        bot.send_message(call.message.chat.id, f"💎 Buy Premium:\n{links}")

    elif call.data == "⭐ Premium":
        if user["premium"]:
            bot.send_message(call.message.chat.id, "✅ You are Premium!")
        else:
            bot.send_message(call.message.chat.id, "🚫 Premium only! Please upgrade.")

    elif call.data == "📢 Help":
        if user["premium"]:
            bot.send_message(call.message.chat.id, "💎 Premium Help: Direct support available.")
        else:
            bot.send_message(call.message.chat.id, "ℹ️ Help: Upgrade to Premium for direct support.")


# ================= WEBHOOK =================
@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/")
def home():
    return "🤖 Bot is running!"


if __name__ == "__main__":
    import threading
    import time
    import requests

    def set_webhook():
        time.sleep(1)
        url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url=https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook/{TOKEN}"
        requests.get(url)

    threading.Thread(target=set_webhook).start()
    app.run(host="0.0.0.0", port=8000)
