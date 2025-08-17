import os
import logging
from flask import Flask, request, jsonify
import telebot
from telebot import types

# -------------------- Config --------------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN env var missing")

# Render के लिए अपना public URL देना ज़रूरी है (Settings → Environment → RENDER_EXTERNAL_URL)
PUBLIC_BASE_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
if not PUBLIC_BASE_URL:
    # fallback: कोशिश करेंगे request से पकड़ने की (पहले deploy पर setwebhook में काम आए)
    logging.warning("RENDER_EXTERNAL_URL not set; set it to your Render primary URL.")

WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = (PUBLIC_BASE_URL + WEBHOOK_PATH) if PUBLIC_BASE_URL else None

# Admin users (comma-separated ids)
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
}

# Flask + TeleBot
app = Flask(__name__)
bot = telebot.TeleBot(TOKEN, threaded=False, parse_mode="HTML")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("server")

# -------------------- Helpers --------------------
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS if ADMIN_IDS else False

def set_webhook(url: str) -> bool:
    try:
        bot.remove_webhook()
        ok = bot.set_webhook(url=url, drop_pending_updates=True, allowed_updates=["message","callback_query"])
        log.info("Webhook set to: %s | ok=%s", url, ok)
        return bool(ok)
    except Exception as e:
        log.exception("Failed to set webhook: %s", e)
        return False

def delete_webhook() -> bool:
    try:
        ok = bot.delete_webhook(drop_pending_updates=True)
        log.info("Webhook deleted | ok=%s", ok)
        return bool(ok)
    except Exception as e:
        log.exception("Failed to delete webhook: %s", e)
        return False

# -------------------- UI Pieces --------------------
def main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Help", "Wallet")
    kb.row("Premium", "Games")
    return kb

def wallet_inline() -> types.InlineKeyboardMarkup:
    ik = types.InlineKeyboardMarkup()
    ik.row(types.InlineKeyboardButton("Check Balance", callback_data="wallet_balance"))
    ik.row(types.InlineKeyboardButton("Add Funds (demo)", callback_data="wallet_add"))
    return ik

def premium_inline() -> types.InlineKeyboardMarkup:
    ik = types.InlineKeyboardMarkup()
    ik.row(types.InlineKeyboardButton("Buy Premium (demo)", callback_data="premium_buy"))
    ik.row(types.InlineKeyboardButton("Benefits", callback_data="premium_benefits"))
    return ik

def games_inline() -> types.InlineKeyboardMarkup:
    ik = types.InlineKeyboardMarkup()
    ik.row(types.InlineKeyboardButton("🎯 Mini Game (demo)", callback_data="game_play"))
    return ik

# -------------------- Commands --------------------
@bot.message_handler(commands=["start"])
def cmd_start(m: types.Message):
    text = (
        "🚀 <b>Bot chal raha hai! Welcome!</b>\n\n"
        "👇 नीचे दिए बटन से features इस्तेमाल करो या /help देखो।"
    )
    bot.send_message(m.chat.id, text, reply_markup=main_menu_keyboard())

@bot.message_handler(commands=["help"])
def cmd_help(m: types.Message):
    text = (
        "🛟 <b>Help</b>\n"
        "/start – मुख्य मेनू\n"
        "/help – ये मदद स्क्रीन\n"
        "/ping – बॉट की health\n"
        "/id – आपका Telegram ID\n"
        "/about – बॉट info\n"
        "\n<b>Admin</b>: /broadcast <msg>, /setwebhook, /deletewebhook"
    )
    bot.send_message(m.chat.id, text, reply_markup=main_menu_keyboard())

@bot.message_handler(commands=["ping"])
def cmd_ping(m: types.Message):
    bot.reply_to(m, "🏓 Pong! Bot is alive.")

@bot.message_handler(commands=["id"])
def cmd_id(m: types.Message):
    bot.reply_to(m, f"🆔 Your ID: <code>{m.from_user.id}</code>")

@bot.message_handler(commands=["about"])
def cmd_about(m: types.Message):
    bot.reply_to(m, "ℹ️ Demo multi-feature bot (Flask + Webhook + pyTelegramBotAPI).")

# -------------------- Admin Commands --------------------
@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(m: types.Message):
    if not is_admin(m.from_user.id):
        return bot.reply_to(m, "❌ Admin only.")
    parts = m.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        return bot.reply_to(m, "Usage: <code>/broadcast your message</code>")
    msg = parts[1].strip()
    try:
        # Simple broadcast to current chat only (safe demo). 
        # जरुरत हो तो chats store करके वहाँ भेजना।
        bot.send_message(m.chat.id, f"📢 Broadcast:\n{msg}")
        bot.reply_to(m, "✅ Sent.")
    except Exception as e:
        bot.reply_to(m, f"⚠️ Failed: {e}")

@bot.message_handler(commands=["setwebhook"])
def cmd_setwebhook(m: types.Message):
    if not is_admin(m.from_user.id):
        return bot.reply_to(m, "❌ Admin only.")
    base = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if not base:
        return bot.reply_to(m, "⚠️ Set RENDER_EXTERNAL_URL env var first.")
    ok = set_webhook(base + WEBHOOK_PATH)
    bot.reply_to(m, "✅ Webhook set." if ok else "❌ Failed to set webhook.")

@bot.message_handler(commands=["deletewebhook"])
def cmd_deletewebhook(m: types.Message):
    if not is_admin(m.from_user.id):
        return bot.reply_to(m, "❌ Admin only.")
    ok = delete_webhook()
    bot.reply_to(m, "✅ Webhook deleted." if ok else "❌ Failed to delete webhook.")

# -------------------- Text Buttons (Reply Keyboard) --------------------
@bot.message_handler(func=lambda m: m.text and m.text.lower() == "help")
def on_help_btn(m: types.Message):
    cmd_help(m)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "wallet")
def on_wallet(m: types.Message):
    bot.send_message(m.chat.id, "👛 Wallet menu (demo):", reply_markup=wallet_inline())

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "premium")
def on_premium(m: types.Message):
    bot.send_message(m.chat.id, "⭐ Premium menu (demo):", reply_markup=premium_inline())

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "games")
def on_games(m: types.Message):
    bot.send_message(m.chat.id, "🎮 Games (demo):", reply_markup=games_inline())

# -------------------- Callbacks --------------------
@bot.callback_query_handler(func=lambda c: True)
def on_callback(c: types.CallbackQuery):
    try:
        if c.data == "wallet_balance":
            bot.answer_callback_query(c.id, "Balance checked")
            bot.edit_message_text("👛 Balance: <b>₹0.00</b> (demo)", c.message.chat.id, c.message.message_id, reply_markup=wallet_inline())
        elif c.data == "wallet_add":
            bot.answer_callback_query(c.id, "Funds added (demo)")
            bot.edit_message_text("👛 Added ₹10 (demo). New balance: <b>₹10.00</b>", c.message.chat.id, c.message.message_id, reply_markup=wallet_inline())
        elif c.data == "premium_buy":
            bot.answer_callback_query(c.id, "Premium purchased (demo)")
            bot.edit_message_text("⭐ Premium active! (demo)", c.message.chat.id, c.message.message_id, reply_markup=premium_inline())
        elif c.data == "premium_benefits":
            bot.answer_callback_query(c.id)
            bot.edit_message_text("⭐ Benefits:\n• Faster support\n• Extra features\n( demo )", c.message.chat.id, c.message.message_id, reply_markup=premium_inline())
        elif c.data == "game_play":
            bot.answer_callback_query(c.id)
            bot.edit_message_text("🎯 You scored <b>7</b>! (demo mini-game)", c.message.chat.id, c.message.message_id, reply_markup=games_inline())
        else:
            bot.answer_callback_query(c.id, "Unknown action")
    except Exception as e:
        log.exception("Callback error: %s", e)
        bot.answer_callback_query(c.id, "Error")
        
# -------------------- Webhook Endpoints --------------------
@app.route("/", methods=["GET", "HEAD"])
def index():
    return "OK", 200

@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify(ok=True, version="1.0"), 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    try:
        json_str = request.get_data(as_text=True)
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        log.exception("Update processing failed: %s", e)
    return "OK", 200

# -------------------- Startup: set webhook --------------------
with app.app_context():
    if PUBLIC_BASE_URL:
        set_webhook(WEBHOOK_URL)
    else:
        log.warning("Webhook NOT set automatically because RENDER_EXTERNAL_URL is missing.")

# -------------------- Main --------------------
if __name__ == "__main__":
    # Render automatically runs this; keep port=8000
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
