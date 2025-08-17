# server.py
import os
import telebot
from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN", "7566709441:AAE9A9V-Z9Q0vAQr2qyaBCBv0zpRyU3Akcw")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Simple start command
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "🚀 Bot chal raha hai! Welcome!")

# Webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    if request.headers.get("content-type") == "application/json":
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "ok", 200
    else:
        return "Unsupported request", 403

@app.route("/", methods=["GET"])
def index():
    return "✅ Bot is live!"

if __name__ == "__main__":
    # Render domain se webhook set karega
    WEBHOOK_URL = f"{os.environ.get('RENDER_EXTERNAL_URL', 'https://super-bot-render.onrender.com')}/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)
    app.run(host="0.0.0.0", port=8000)
